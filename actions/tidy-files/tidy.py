"""tidy-files: file loose items from a folder (the desktop by default) into category folders.

Safety rules this action keeps:
  * it never deletes anything; it only moves, and every move is journaled first
  * new journals support identity/content-checked undo (most recent run first)
  * shortcuts, hidden/system files, half-finished downloads and files changed in
    the last moments stay where they are; folders stay unless asked
  * it never overwrites: name clashes get a " (2)" suffix
  * source and destination must be inside the user's home folder
"""
from __future__ import annotations

import errno
import hashlib
import json
import os
import shutil
import stat as statmod
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
# Known Windows cloud/reparse flags and macOS dataless files. Providers that do
# not expose these flags are not detected; do not promise general cloud safety.
UNAVAILABLE_ATTRIBUTES = 0x400 | 0x1000 | 0x40000 | 0x400000
DATALESS_FLAG = getattr(statmod, "SF_DATALESS", 0x40000000)

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
                "name": category_name(str(item["name"]).strip()),
                "extensions": {("." + str(e).lower().lstrip(".")) for e in item.get("extensions") or []},
                "keywords": [str(k).lower() for k in item.get("keywords") or [] if str(k).strip()],
            })
        if result:
            return result
    return [{"name": name, "extensions": set(exts.split()), "keywords": []} for name, exts in PRESETS[preset_lang(ctx)]]


def category_name(name: str) -> str:
    """A category is one portable folder name, never a path."""
    reserved = {"CON", "PRN", "AUX", "NUL"} | {f"{p}{n}" for p in ("COM", "LPT") for n in range(1, 10)}
    if (not name or name in (".", "..") or name[-1] in " ."
            or any(c in name for c in '/\\:<>"|?*') or any(ord(c) < 32 for c in name)
            or name.split(".")[0].upper() in reserved):
        raise ValueError("Category must be a single safe folder name: " + repr(name))
    return name


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


def plain_path(path: Path) -> None:
    """Reject changed ancestors, symlinks and Windows junctions/reparse points."""
    if path.resolve() != path:
        raise OSError("Path now resolves somewhere else: " + str(path))
    for part in (path, *path.parents):
        if os.path.lexists(part):
            info = part.lstat()
            if statmod.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
                raise OSError("Links and reparse points are not moved through: " + str(part))


def archive_folder(library: Path, category: str) -> Path:
    folder = library / category
    if not _inside(folder, library) or folder == library:
        raise OSError("Category is outside the archive")
    plain_path(folder)
    if not _inside(folder.resolve(), library):
        raise OSError("Category resolves outside the archive")
    return folder


def identity(info: os.stat_result) -> Dict[str, Any]:
    if not info.st_ino:
        raise OSError("Filesystem does not expose a stable file identity; left in place")
    return {"device": info.st_dev, "inode": info.st_ino, "mode": statmod.S_IFMT(info.st_mode),
            "size": info.st_size, "mtime_ns": info.st_mtime_ns}


def parent_identity(path: Path) -> Dict[str, Any]:
    info = path.stat()
    if not info.st_ino:
        raise OSError("Filesystem does not expose a stable directory identity; left in place")
    return {"device": info.st_dev, "inode": info.st_ino}


def unavailable(info: os.stat_result, name: str = "") -> bool:
    return bool(getattr(info, "st_file_attributes", 0) & UNAVAILABLE_ATTRIBUTES
                or getattr(info, "st_flags", 0) & DATALESS_FLAG
                or name.lower().endswith(".icloud"))


def fingerprint(path: Path) -> Dict[str, Any]:
    """Read stable local content only; retain identity as well as a SHA-256 digest."""
    plain_path(path)
    before = path.lstat()
    if unavailable(before, path.name):
        raise OSError("Cloud placeholder or reparse item; leave it in place")
    expected = identity(before)
    if statmod.S_ISREG(before.st_mode):
        digest = hashlib.sha256()
        flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
        with os.fdopen(os.open(path, flags), "rb") as handle:
            if identity(os.fstat(handle.fileno())) != expected:
                raise OSError("File changed before it could be checked")
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
            if identity(os.fstat(handle.fileno())) != expected:
                raise OSError("File changed while it was being checked")
        kind = "file"
    elif statmod.S_ISDIR(before.st_mode):
        # include_folders is explicit opt-in. Every descendant must be local and
        # stable; a changed/replaced child prevents automatic undo of the folder.
        children = [(p.name, fingerprint(p)) for p in sorted(path.iterdir(), key=lambda p: p.name)]
        digest = hashlib.sha256(json.dumps(children, sort_keys=True).encode("utf-8"))
        kind = "folder"
    else:
        raise OSError("Only regular local files and folders can be moved")
    if identity(path.lstat()) != expected:
        raise OSError("Item changed while it was being checked")
    return {"version": 1, "kind": kind, "identity": expected, "sha256": digest.hexdigest()}


def checked_fingerprint(path: Path, expected: Dict[str, Any]) -> Dict[str, Any]:
    actual = fingerprint(path)
    if actual != expected:
        raise OSError("Item changed or was replaced; left in place")
    return actual


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
    plain_path(source)
    plain_path(library)
    with os.scandir(source) as entries:
        for entry in sorted(entries, key=lambda e: e.name.lower()):
            try:
                if _hidden(entry):
                    continue
                path = Path(entry.path)
                item: Dict[str, Any] = {"name": entry.name, "path": str(path)}
                # DirEntry.stat() omits file IDs on Windows; use lstat for the
                # identity that will later be compared with the opened file.
                info = path.lstat()
                if entry.is_symlink():
                    kept.append(dict(item, kind="link", reason=ctx.t("链接保持原位", "links stay")))
                    continue
                if unavailable(info, entry.name):
                    kept.append(dict(item, kind="unknown", reason=ctx.t("云占位文件或重解析项保持原位", "cloud placeholder or reparse item stays")))
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
                        move.append(dict(item, category=FOLDERS[lang], identity=identity(info)))
                    continue
                if not entry.is_file(follow_symlinks=False):
                    continue
                stat = info
                item.update(kind="file", size=stat.st_size, mtime=stat.st_mtime, identity=identity(stat))
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
    safe = []
    for item in move:
        try:
            archive_folder(library, item["category"])
        except OSError as exc:
            kept.append(dict(item, reason=str(exc)))
        else:
            safe.append(item)
    return safe, kept


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
    except OSError:
        # A rename fallback on POSIX could overwrite a file created after our
        # existence check. Unsupported filesystems must leave the source alone.
        raise
    try:
        os.unlink(src)
    except OSError:
        os.unlink(dst)
        raise


def move_to(src: Path, dst: Path, expected: Optional[Dict[str, Any]] = None) -> Path:
    """Move a verified item on the same volume, refusing unsafe copy/delete fallbacks."""
    plain_path(src)
    plain_path(dst.parent)
    dst.parent.mkdir(parents=True, exist_ok=True)
    if expected is not None:
        checked_fingerprint(src, expected)
    try:
        exclusive_move(src, dst)
        return dst
    except OSError as exc:
        if _cross_device(exc):
            raise OSError(errno.EXDEV, "Cross-volume moves are skipped; choose an archive on the same volume", str(src)) from exc
        raise


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
    """Pending moves, excluding each successfully restored item individually."""
    done = {(r["src"], r["dst"]) for r in records if r.get("type") == "done"}
    restored = {(r.get("move_src"), r.get("move_dst")) for r in records if r.get("type") == "restored"}
    for record in records:
        key = (record.get("move_src"), record.get("move_dst"))
        if record.get("type") == "restore_intent" and key not in restored and not os.path.lexists(record["src"]):
            try:
                checked_fingerprint(Path(record["dst"]), record["fingerprint"])
            except (OSError, KeyError):
                continue
            restored.add(key)  # interrupted after the restore, before its completion record
    result = []
    for record in records:
        if (record.get("src"), record.get("dst")) in restored:
            continue
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


def verifiable(record: Dict[str, Any]) -> bool:
    value = record.get("fingerprint")
    return (isinstance(value, dict) and value.get("version") == 1
            and isinstance(value.get("identity"), dict) and bool(value.get("sha256"))
            and isinstance(record.get("source_parent"), dict)
            and isinstance(record.get("archive_parent"), dict))


def can_undo(found: Optional[Tuple[Path, List[Dict[str, Any]]]]) -> bool:
    return bool(found and any(verifiable(r) for r in moves_of(found[1])))


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
            "manual_review": sum(not verifiable(r) for r in moves_of(undoable[1])) if undoable else 0,
            "available": {"run": len(move) > 0, "undo": can_undo(undoable), "open": True, "preview": True},
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
                    "data": {"moved": 0, "kept": len(kept), "library": str(library), "can_undo": can_undo(last_undoable(ctx))}}
        busy = open_files_mac([m["path"] for m in move if m["kind"] == "file"])
        run_id = datetime.now().strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:4]
        journal = runs_dir(ctx) / f"{run_id}.jsonl"
        kit.append_jsonl(journal, {"type": "begin", "version": 2, "run": run_id, "at": time.time(), "source": str(source), "library": str(library)})
        moved, results = 0, []
        total = len(move)
        for index, item in enumerate(move, 1):
            src = Path(item["path"])
            if item["path"] in busy:
                results.append({"name": item["name"], "status": "keep", "reason": ctx.t("正在被其他程序使用", "open in another program")})
                kit.progress(index / total, ctx.t(f"跳过（正在使用）：{item['name']}", f"Skipped (in use): {item['name']}"), item=item["name"], status="keep")
                continue
            try:
                plain_path(source)
                folder = archive_folder(library, item["category"])
                if identity(src.lstat()) != item["identity"]:
                    raise OSError("Source changed since scanning; left in place")
                original = fingerprint(src)
                if original["identity"] != item["identity"]:
                    raise OSError("Source changed since scanning; left in place")
                created, probe = [], folder
                while not probe.exists() and (probe == library or library in probe.parents):
                    created.append(probe)
                    probe = probe.parent
                for path in reversed(created):
                    # Record only directories we actually created, with identity.
                    path.mkdir(parents=True)
                    kit.append_jsonl(journal, {"type": "mkdir", "path": str(path), "identity": parent_identity(path)})
                archive_folder(library, item["category"])
                dst = unique_target(folder, src.name)
                record = {"src": str(src), "dst": str(dst), "fingerprint": original,
                          "source_parent": parent_identity(src.parent), "archive_parent": parent_identity(folder)}
                kit.append_jsonl(journal, dict(record, type="intent"))
                # Use exactly the journaled destination, and verify again just before moving.
                actual = move_to(src, dst, original)
                kit.append_jsonl(journal, dict(record, type="done", size=item.get("size")))
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
        restored, failed, manual = 0, 0, 0
        results = []
        for index, record in enumerate(moves, 1):
            src, dst = Path(record["src"]), Path(record["dst"])
            if not verifiable(record):
                manual += 1
                results.append({"name": src.name, "status": "keep", "reason": ctx.t(
                    "旧日志没有文件身份校验，请人工核对；本次不会移动。",
                    "Legacy journal has no identity checks; review manually. Nothing was moved.")})
                continue
            try:
                # The journal is evidence, not permission to write arbitrary locations.
                if (not any(_inside(src, root) for root in _allowed_roots())
                        or not any(_inside(dst, root) for root in _allowed_roots())):
                    raise OSError("Journal path is outside the allowed user folders")
                plain_path(src.parent)
                plain_path(dst.parent)
                if (parent_identity(src.parent) != record["source_parent"]
                        or parent_identity(dst.parent) != record["archive_parent"]):
                    raise OSError("A parent folder changed; review manually")
                checked_fingerprint(dst, record["fingerprint"])
                if os.path.lexists(src):  # something new took the old name; keep both
                    target = unique_target(src.parent, src.stem + ctx.t("（放回）", " (restored)") + src.suffix)
                else:
                    target = src
                kit.append_jsonl(journal, {"type": "restore_intent", "src": str(dst), "dst": str(target),
                                          "move_src": record["src"], "move_dst": record["dst"],
                                          "fingerprint": record["fingerprint"]})
                actual = move_to(dst, target, record["fingerprint"])
                kit.append_jsonl(journal, {"type": "restored", "src": str(dst), "dst": str(actual),
                                          "move_src": record["src"], "move_dst": record["dst"]})
                restored += 1
                results.append({"name": src.name, "status": "restored", "to": str(actual)})
                kit.progress(index / len(moves), ctx.t(f"放回：{src.name}", f"Back: {src.name}"), item=src.name, status="restored")
            except OSError as exc:
                failed += 1
                results.append({"name": src.name, "status": "keep", "reason": str(exc)})
                kit.progress(index / len(moves), ctx.t(f"未移动：{src.name}", f"Left in place: {src.name}"), item=src.name, status="failed", reason=str(exc)[:160])
        # Retain unresolved moves so temporary locks/missing files can be retried.
        remaining = moves_of(kit.read_jsonl(journal))
        if not remaining:
            begin = next((r for r in records if r.get("type") == "begin"), {})
            archive_root = Path(begin["library"]) if begin.get("library") else None
            for record in reversed(records):
                if record.get("type") == "mkdir" and record.get("identity"):
                    try:
                        path = Path(record["path"])
                        plain_path(path)
                        if (archive_root is not None and _inside(path, archive_root)
                                and any(_inside(path, root) for root in _allowed_roots())
                                and parent_identity(path) == record["identity"]):
                            os.rmdir(path)  # only unchanged, empty directories created by this run
                    except OSError:
                        pass
            kit.append_jsonl(journal, {"type": "undone", "at": time.time(), "restored": restored})
        message = ctx.t(f"已放回 {restored} 个", f"Put {restored} back")
        if failed:
            message += ctx.t(f"；{failed} 个未移动，请核对原因后重试", f"; {failed} left in place; review the reasons before retrying")
        if manual:
            message += ctx.t(f"；{manual} 个旧日志项目缺少身份校验，需人工核对", f"; {manual} legacy items need manual review because identity checks are missing")
        return {"ok": not (failed or manual), "message": message, "data": {
            "restored": restored, "missing": failed, "manual_review": manual,
            "remaining": len(remaining), "items": results[:300], "can_undo": can_undo(last_undoable(ctx)),
        }}


def op_open(ctx: kit.Context) -> Dict[str, Any]:
    library = resolve_library(ctx)
    library.mkdir(parents=True, exist_ok=True)
    kit.open_path(library)
    return {"ok": True, "message": ctx.t(f"已打开「{library.name}」", f"Opened '{library.name}'"), "data": {"path": str(library)}}


if __name__ == "__main__":
    kit.main({"status": op_status, "preview": op_preview, "run": op_run, "undo": op_undo, "open": op_open})
