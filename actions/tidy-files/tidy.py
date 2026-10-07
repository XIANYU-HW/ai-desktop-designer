"""tidy-files: file loose items from a folder (the desktop by default) into category folders.

Safety rules this action keeps:
  * it never deletes anything; it only moves, and every move is journaled first
  * every run can be undone (most recent run first)
  * shortcuts, hidden/system files, half-finished downloads and files changed in
    the last moments stay where they are; folders stay unless asked
  * it never overwrites: name clashes get a " (2)" suffix
  * source and destination must be inside the user's home folder
"""
from __future__ import annotations

import errno
import os
import shutil
import subprocess
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, os.environ.get("ORBIT_RUNTIME") or str(Path(__file__).resolve().parents[2] / "runtime"))
from orbitcore import kit  # noqa: E402

KNOWN = ("desktop", "downloads", "documents", "pictures", "music", "videos")
SKIP_NAMES = {"desktop.ini", "thumbs.db", ".ds_store", ".localized", "icon\r"}
SHORTCUT_SUFFIXES = {".lnk", ".url", ".webloc", ".inetloc", ".alias", ".desktop"}
PARTIAL_SUFFIXES = {".crdownload", ".part", ".partial", ".download", ".tmp", ".temp", ".opdownload", ".aria2", ".!ut", ".downloading"}
FILE_ATTRIBUTE_HIDDEN = 0x2
FILE_ATTRIBUTE_SYSTEM = 0x4

PRESETS: Dict[str, List[Tuple[str, List[str]]]] = {
    "zh-CN": [
        ("文档", ".doc .docx .pdf .txt .md .rtf .odt .pages .wps .epub .mobi"),
        ("表格", ".xls .xlsx .xlsm .csv .numbers .ods .et"),
        ("演示", ".ppt .pptx .key .odp .dps"),
        ("图片", ".jpg .jpeg .png .gif .webp .heic .heif .bmp .tif .tiff .svg .ico .raw .dng .cr2 .nef .arw .avif"),
        ("视频", ".mp4 .mov .m4v .avi .mkv .webm .wmv .flv .mpg .mpeg .3gp"),
        ("音频", ".mp3 .wav .m4a .aac .flac .ogg .wma .aiff .opus .mid"),
        ("压缩包", ".zip .rar .7z .tar .gz .tgz .bz2 .xz .iso .dmg .cab"),
        ("安装包", ".exe .msi .msix .appx .appxbundle .pkg .apk .deb .rpm .appimage"),
        ("设计", ".psd .psb .ai .sketch .fig .xd .blend .c4d .aep .prproj .indd .eps .afdesign .afphoto .procreate"),
        ("代码", ".py .js .ts .tsx .jsx .html .htm .css .json .java .c .h .cpp .cs .go .rs .rb .php .sh .ps1 .bat .ipynb .sql .xml .yml .yaml .toml .swift .kt"),
    ],
    "en": [
        ("Documents", ".doc .docx .pdf .txt .md .rtf .odt .pages .wps .epub .mobi"),
        ("Spreadsheets", ".xls .xlsx .xlsm .csv .numbers .ods .et"),
        ("Presentations", ".ppt .pptx .key .odp .dps"),
        ("Images", ".jpg .jpeg .png .gif .webp .heic .heif .bmp .tif .tiff .svg .ico .raw .dng .cr2 .nef .arw .avif"),
        ("Videos", ".mp4 .mov .m4v .avi .mkv .webm .wmv .flv .mpg .mpeg .3gp"),
        ("Audio", ".mp3 .wav .m4a .aac .flac .ogg .wma .aiff .opus .mid"),
        ("Archives", ".zip .rar .7z .tar .gz .tgz .bz2 .xz .iso .dmg .cab"),
        ("Installers", ".exe .msi .msix .appx .appxbundle .pkg .apk .deb .rpm .appimage"),
        ("Design", ".psd .psb .ai .sketch .fig .xd .blend .c4d .aep .prproj .indd .eps .afdesign .afphoto .procreate"),
        ("Code", ".py .js .ts .tsx .jsx .html .htm .css .json .java .c .h .cpp .cs .go .rs .rb .php .sh .ps1 .bat .ipynb .sql .xml .yml .yaml .toml .swift .kt"),
    ],
}
OTHER = {"zh-CN": "其他", "en": "Other"}
FOLDERS = {"zh-CN": "文件夹", "en": "Folders"}
LIBRARY_NAME = {"zh-CN": "桌面收纳", "en": "Desktop Archive"}


# --------------------------------------------------------------------------- settings

def preset_lang(ctx: kit.Context) -> str:
    preset = str(ctx.param("preset", "") or "")
    if preset in PRESETS:
        return preset
    return "zh-CN" if ctx.zh else "en"


def categories(ctx: kit.Context) -> List[Dict[str, Any]]:
    custom = ctx.param("categories")
    if isinstance(custom, list) and custom:
        result = []
        for item in custom:
            if not isinstance(item, dict) or not item.get("name"):
                continue
            result.append({
                "name": str(item["name"]).strip(),
                "extensions": {("." + str(e).lower().lstrip(".")) for e in item.get("extensions") or []},
                "keywords": [str(k).lower() for k in item.get("keywords") or [] if str(k).strip()],
            })
        if result:
            return result
    return [{"name": name, "extensions": set(exts.split()), "keywords": []} for name, exts in PRESETS[preset_lang(ctx)]]


def _inside(path: Path, root: Path) -> bool:
    return path == root or root in path.parents


def _allowed_roots() -> List[Path]:
    roots = [Path.home().resolve()]
    for name in KNOWN:
        try:
            roots.append(kit.known_folder(name).resolve())
        except OSError:
            pass
    return roots


def resolve_source(ctx: kit.Context) -> Path:
    value = str(ctx.param("source", "desktop") or "desktop").strip()
    path = kit.known_folder(value) if value.lower() in KNOWN else kit.expand_path(value)
    path = path.resolve()
    if path == Path.home().resolve():
        raise ValueError(ctx.t("不能整理整个用户目录。", "Refusing to tidy the whole home folder."))
    if not any(_inside(path, root) for root in _allowed_roots()):
        raise ValueError(ctx.t("只能整理你用户目录里的文件夹。", "Only folders inside your home folder can be tidied."))
    if not path.is_dir():
        raise ValueError(ctx.t(f"找不到文件夹：{path}", f"Folder not found: {path}"))
    return path


def resolve_library(ctx: kit.Context) -> Path:
    value = str(ctx.param("library", "") or "").strip()
    path = kit.expand_path(value) if value else kit.known_folder("documents") / LIBRARY_NAME[preset_lang(ctx)]
    path = path.resolve()
    if not any(_inside(path, root) for root in _allowed_roots()):
        raise ValueError(ctx.t("收纳夹必须在你的用户目录里。", "The archive folder must be inside your home folder."))
    return path


# --------------------------------------------------------------------------- scanning

def _hidden(entry: os.DirEntry) -> bool:
    name = entry.name
    if name.startswith(".") or name.lower() in SKIP_NAMES or name.startswith("~$"):
        return True
    attrs = getattr(entry.stat(follow_symlinks=False), "st_file_attributes", 0)
    return bool(attrs & (FILE_ATTRIBUTE_HIDDEN | FILE_ATTRIBUTE_SYSTEM))


def classify(name: str, cats: List[Dict[str, Any]], other: str) -> str:
    lower = name.lower()
    for cat in cats:
        if any(keyword in lower for keyword in cat["keywords"]):
            return cat["name"]
    suffix = os.path.splitext(lower)[1]
    for cat in cats:
        if suffix and suffix in cat["extensions"]:
            return cat["name"]
    return other


def scan(ctx: kit.Context, source: Path, library: Path) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Return (to_move, kept). Hidden and system files are not reported at all."""
    cats = categories(ctx)
    lang = preset_lang(ctx)
    include_folders = bool(ctx.param("include_folders", False))
    min_age = float(ctx.param("min_age_seconds", 30) or 0)
    now = time.time()
    move: List[Dict[str, Any]] = []
    kept: List[Dict[str, Any]] = []
    with os.scandir(source) as entries:
        for entry in sorted(entries, key=lambda e: e.name.lower()):
            try:
                if _hidden(entry):
                    continue
                path = Path(entry.path)
                item: Dict[str, Any] = {"name": entry.name, "path": str(path)}
                if entry.is_symlink():
                    kept.append(dict(item, kind="link", reason=ctx.t("链接保持原位", "links stay")))
                    continue
                if entry.is_dir(follow_symlinks=False):
                    item["kind"] = "folder"
                    resolved = path.resolve()
                    if _inside(library, resolved) or resolved == library:
                        continue  # the archive itself, or a folder that contains it
                    if entry.name.lower().endswith((".app", ".bundle")):
                        kept.append(dict(item, reason=ctx.t("应用保持原位", "apps stay")))
                    elif not include_folders:
                        kept.append(dict(item, reason=ctx.t("文件夹保持原位", "folders stay")))
                    else:
                        move.append(dict(item, category=FOLDERS[lang]))
                    continue
                if not entry.is_file(follow_symlinks=False):
                    continue
                stat = entry.stat(follow_symlinks=False)
                item.update(kind="file", size=stat.st_size, mtime=stat.st_mtime)
                suffix = os.path.splitext(entry.name.lower())[1]
                if suffix in SHORTCUT_SUFFIXES:
                    kept.append(dict(item, reason=ctx.t("快捷方式保持原位", "shortcuts stay")))
                elif suffix in PARTIAL_SUFFIXES:
                    kept.append(dict(item, reason=ctx.t("正在下载，保持原位", "still downloading")))
                elif now - stat.st_mtime < min_age:
                    kept.append(dict(item, reason=ctx.t("刚刚改动过，稍后再收", "changed moments ago")))
                else:
                    move.append(dict(item, category=classify(entry.name, cats, OTHER[lang])))
            except OSError as exc:
                kept.append({"name": entry.name, "path": entry.path, "kind": "unknown", "reason": str(exc)[:120]})
    if ctx.param("group_by_month", False):
        for item in move:
            if item.get("mtime"):
                item["category"] = os.path.join(item["category"], datetime.fromtimestamp(item["mtime"]).strftime("%Y-%m"))
    return move, kept


def open_files_mac(paths: List[str]) -> set:
    """Files another program has open right now (macOS/Linux, via lsof)."""
    if not paths or kit.IS_WINDOWS or not shutil.which("lsof"):
        return set()
    busy = set()
    for start in range(0, len(paths), 200):
        chunk = paths[start:start + 200]
        try:
            out = subprocess.run(["lsof", "-F", "n", "--"] + chunk, capture_output=True, text=True, timeout=10).stdout
        except (OSError, subprocess.SubprocessError):
            continue
        for line in out.splitlines():
            if line.startswith("n"):
                busy.add(line[1:])
    return busy


# --------------------------------------------------------------------------- moving

def unique_target(folder: Path, name: str) -> Path:
    target = folder / name
    if not os.path.lexists(target):
        return target
    stem, suffix = os.path.splitext(name)
    for index in range(2, 10000):
        candidate = folder / f"{stem} ({index}){suffix}"
        if not os.path.lexists(candidate):
            return candidate
    raise OSError(errno.EEXIST, "no free name", str(target))


def _cross_device(exc: OSError) -> bool:
    return exc.errno == errno.EXDEV or getattr(exc, "winerror", None) == 17


def exclusive_move(src: Path, dst: Path) -> None:
    """Rename src to dst on the same drive without ever overwriting dst."""
    if os.path.lexists(dst):
        raise FileExistsError(str(dst))
    if kit.IS_WINDOWS or src.is_dir() or src.is_symlink():
        os.rename(src, dst)  # Windows refuses to overwrite; folders cannot be hard-linked
        return
    try:
        os.link(src, dst)  # atomic and fails if dst appeared meanwhile
    except OSError as exc:
        no_links = exc.errno in (errno.EPERM, errno.ENOTSUP, errno.EOPNOTSUPP, errno.EMLINK, errno.EACCES, errno.ENOSYS)
        if no_links and not _cross_device(exc) and not os.path.lexists(dst):
            os.rename(src, dst)  # file systems without hard links (FAT, some network drives)
            return
        raise
    try:
        os.unlink(src)
    except OSError:
        os.unlink(dst)
        raise


def move_to(src: Path, dst: Path) -> Path:
    """Move src to exactly dst, copying across drives when needed. Never overwrites."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    try:
        exclusive_move(src, dst)
        return dst
    except OSError as exc:
        if not _cross_device(exc) or src.is_dir():
            raise
    # Different drive: copy, verify, then remove the original.
    temp = unique_target(dst.parent, f".orbit-copy-{uuid.uuid4().hex[:8]}-{src.name}")
    shutil.copy2(src, temp)
    if temp.stat().st_size != src.stat().st_size:
        os.unlink(temp)
        raise OSError(errno.EIO, "copy size mismatch", str(src))
    exclusive_move(temp, dst)
    try:
        os.unlink(src)
    except OSError:
        os.unlink(dst)
        raise
    return dst


def move_item(src: Path, folder: Path) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    return move_to(src, unique_target(folder, src.name))


# --------------------------------------------------------------------------- journal

def runs_dir(ctx: kit.Context) -> Path:
    path = ctx.state_dir / "runs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def load_runs(ctx: kit.Context) -> List[Tuple[Path, List[Dict[str, Any]]]]:
    runs = []
    for path in sorted(runs_dir(ctx).glob("*.jsonl")):
        runs.append((path, kit.read_jsonl(path)))
    return runs


def moves_of(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Moves that happened, including ones interrupted right after the rename."""
    done = {(r["src"], r["dst"]) for r in records if r.get("type") == "done"}
    result = []
    for record in records:
        if record.get("type") == "done":
            result.append(record)
        elif record.get("type") == "intent" and (record["src"], record["dst"]) not in done:
            if os.path.lexists(record["dst"]) and not os.path.lexists(record["src"]):
                result.append(dict(record, type="done", recovered=True))
    return result


def last_undoable(ctx: kit.Context) -> Optional[Tuple[Path, List[Dict[str, Any]]]]:
    for path, records in reversed(load_runs(ctx)):
        if any(r.get("type") == "undone" for r in records):
            continue
        if moves_of(records):
            return path, records
    return None


# --------------------------------------------------------------------------- operations

def describe(ctx: kit.Context, move: List[Dict[str, Any]], kept: List[Dict[str, Any]], library: Path) -> List[Dict[str, Any]]:
    items = [
        {"name": m["name"], "kind": m["kind"], "status": "move", "category": m["category"], "to": str(library / m["category"])}
        for m in move
    ]
    items += [{"name": k["name"], "kind": k.get("kind"), "status": "keep", "reason": k.get("reason")} for k in kept]
    return items[:300]


def op_status(ctx: kit.Context) -> Dict[str, Any]:
    source, library = resolve_source(ctx), resolve_library(ctx)
    move, kept = scan(ctx, source, library)
    undoable = last_undoable(ctx)
    last = None
    if undoable:
        begin = next((r for r in undoable[1] if r.get("type") == "begin"), {})
        last = {"at": begin.get("at"), "moved": len(moves_of(undoable[1]))}
    return {
        "ok": True,
        "message": ctx.t(f"{len(move)} 个待收纳", f"{len(move)} waiting"),
        "data": {
            "pending": len(move),
            "kept": len(kept),
            "source": str(source),
            "library": str(library),
            "last_run": last,
            "available": {"run": len(move) > 0, "undo": undoable is not None, "open": True, "preview": True},
        },
    }


def op_preview(ctx: kit.Context) -> Dict[str, Any]:
    source, library = resolve_source(ctx), resolve_library(ctx)
    move, kept = scan(ctx, source, library)
    by_category: Dict[str, int] = {}
    for item in move:
        by_category[item["category"]] = by_category.get(item["category"], 0) + 1
    summary = "、".join(f"{k} {v}" for k, v in by_category.items()) if ctx.zh else ", ".join(f"{k} {v}" for k, v in by_category.items())
    if move:
        message = ctx.t(f"将收纳 {len(move)} 个：{summary}", f"Would file {len(move)}: {summary}")
    else:
        message = ctx.t("没有要收纳的文件。", "Nothing to file.")
    return {"ok": True, "message": message, "data": {
        "pending": len(move), "by_category": by_category, "source": str(source), "library": str(library),
        "items": describe(ctx, move, kept, library),
    }}


def op_run(ctx: kit.Context) -> Dict[str, Any]:
    source, library = resolve_source(ctx), resolve_library(ctx)
    with kit.file_lock(ctx.state_dir / "tidy.lock"):
        move, kept = scan(ctx, source, library)
        if not move:
            return {"ok": True, "message": ctx.t("桌面很清爽，没有要收纳的文件。", "Already tidy. Nothing to file."),
                    "data": {"moved": 0, "kept": len(kept), "library": str(library), "can_undo": last_undoable(ctx) is not None}}
        busy = open_files_mac([m["path"] for m in move if m["kind"] == "file"])
        run_id = datetime.now().strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:4]
        journal = runs_dir(ctx) / f"{run_id}.jsonl"
        kit.append_jsonl(journal, {"type": "begin", "run": run_id, "at": time.time(), "source": str(source), "library": str(library)})
        moved, results = 0, []
        total = len(move)
        for index, item in enumerate(move, 1):
            src = Path(item["path"])
            folder = library / item["category"]
            if item["path"] in busy:
                results.append({"name": item["name"], "status": "keep", "reason": ctx.t("正在被其他程序使用", "open in another program")})
                kit.progress(index / total, ctx.t(f"跳过（正在使用）：{item['name']}", f"Skipped (in use): {item['name']}"), item=item["name"], status="keep")
                continue
            try:
                created, probe = [], folder
                while not probe.exists() and (probe == library or library in probe.parents):
                    created.append(probe)
                    probe = probe.parent
                for path in reversed(created):  # remembered so undo can remove them again
                    kit.append_jsonl(journal, {"type": "mkdir", "path": str(path)})
                dst = unique_target(folder, src.name)
                kit.append_jsonl(journal, {"type": "intent", "src": str(src), "dst": str(dst)})
                folder.mkdir(parents=True, exist_ok=True)
                actual = move_item(src, folder)
                kit.append_jsonl(journal, {"type": "done", "src": str(src), "dst": str(actual), "size": item.get("size")})
                moved += 1
                results.append({"name": item["name"], "status": "moved", "category": item["category"], "to": str(actual)})
                kit.progress(index / total, f"{item['name']} → {item['category']}", item=item["name"], category=item["category"], status="moved")
            except PermissionError:
                results.append({"name": item["name"], "status": "keep", "reason": ctx.t("正在使用或没有权限", "in use or no permission")})
                kit.progress(index / total, ctx.t(f"跳过：{item['name']}", f"Skipped: {item['name']}"), item=item["name"], status="keep")
            except OSError as exc:
                results.append({"name": item["name"], "status": "keep", "reason": str(exc)[:120]})
                kit.progress(index / total, ctx.t(f"跳过：{item['name']}", f"Skipped: {item['name']}"), item=item["name"], status="keep")
        kit.append_jsonl(journal, {"type": "end", "at": time.time(), "moved": moved})
        if moved == 0:
            journal.unlink()
        skipped = len(move) - moved
        name = library.name
        message = ctx.t(
            f"已收纳 {moved} 个到「{name}」" + (f"，{skipped} 个暂未移动" if skipped else ""),
            f"Filed {moved} into '{name}'" + (f"; {skipped} left in place" if skipped else ""),
        )
        return {"ok": True, "message": message, "data": {
            "moved": moved, "skipped": skipped, "kept": len(kept), "library": str(library), "run": run_id,
            "can_undo": moved > 0, "items": results[:300],
        }}


def op_undo(ctx: kit.Context) -> Dict[str, Any]:
    with kit.file_lock(ctx.state_dir / "tidy.lock"):
        found = last_undoable(ctx)
        if not found:
            return {"ok": True, "message": ctx.t("没有可以撤销的收纳。", "Nothing to undo."), "data": {"restored": 0, "can_undo": False}}
        journal, records = found
        moves = list(reversed(moves_of(records)))
        restored, missing = 0, 0
        total = len(moves)
        for index, record in enumerate(moves, 1):
            src, dst = Path(record["src"]), Path(record["dst"])
            if not os.path.lexists(dst):
                missing += 1
                continue
            try:
                if os.path.lexists(src):  # something new took the old name; keep both
                    target = unique_target(src.parent, src.stem + ctx.t("（放回）", " (restored)") + src.suffix)
                else:
                    target = src
                actual = move_to(dst, target)
                kit.append_jsonl(journal, {"type": "restored", "src": str(dst), "dst": str(actual)})
                restored += 1
                kit.progress(index / total, ctx.t(f"放回：{src.name}", f"Back: {src.name}"), item=src.name, status="restored")
            except OSError as exc:
                missing += 1
                kit.progress(index / total, ctx.t(f"没能放回：{src.name}", f"Could not restore: {src.name}"), item=src.name, status="failed", reason=str(exc)[:80])
        for record in reversed(records):
            if record.get("type") == "mkdir":
                try:
                    os.rmdir(record["path"])  # only removes folders this run created, and only if empty
                except OSError:
                    pass
        kit.append_jsonl(journal, {"type": "undone", "at": time.time(), "restored": restored, "missing": missing})
        message = ctx.t(f"已放回 {restored} 个" + (f"，{missing} 个找不到了" if missing else ""),
                        f"Put {restored} back" + (f"; {missing} could not be found" if missing else ""))
        return {"ok": True, "message": message, "data": {"restored": restored, "missing": missing, "can_undo": last_undoable(ctx) is not None}}


def op_open(ctx: kit.Context) -> Dict[str, Any]:
    library = resolve_library(ctx)
    library.mkdir(parents=True, exist_ok=True)
    kit.open_path(library)
    return {"ok": True, "message": ctx.t(f"已打开「{library.name}」", f"Opened '{library.name}'"), "data": {"path": str(library)}}


if __name__ == "__main__":
    kit.main({"status": op_status, "preview": op_preview, "run": op_run, "undo": op_undo, "open": op_open})
