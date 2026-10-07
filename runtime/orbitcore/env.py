"""Platform helpers shared by the runtime and by action scripts.

Standard library only. Everything here must work on Windows, macOS and Linux
with Python 3.9 or newer.
"""
from __future__ import annotations

import contextlib
import json
import locale
import os
import re
import subprocess
import sys
import tempfile
import uuid
import webbrowser
from pathlib import Path
from typing import Any, Dict, Iterator, Optional

SKILL_ROOT = Path(__file__).resolve().parents[2]
RUNTIME_DIR = SKILL_ROOT / "runtime"
ORBIT_SCRIPT = RUNTIME_DIR / "orbit.py"
SDK_DIR = SKILL_ROOT / "sdk"
BUILTIN_THEMES = SKILL_ROOT / "themes"
BUILTIN_ACTIONS = SKILL_ROOT / "actions"
TEMPLATES_DIR = SKILL_ROOT / "templates"


def platform_name() -> str:
    if sys.platform.startswith("win"):
        return "windows"
    if sys.platform == "darwin":
        return "macos"
    return "linux"


PLATFORM = platform_name()
IS_WINDOWS = PLATFORM == "windows"
IS_MAC = PLATFORM == "macos"
IS_LINUX = PLATFORM == "linux"

# Windows process creation flags (harmless constants elsewhere).
CREATE_NO_WINDOW = 0x08000000
DETACHED_PROCESS = 0x00000008
CREATE_NEW_PROCESS_GROUP = 0x00000200


def workspace_dir() -> Path:
    """The user's own folder for config, themes, custom actions and logs."""
    custom = os.environ.get("ORBIT_WORKSPACE")
    if custom:
        return Path(custom).expanduser().resolve()
    return Path.home() / "OrbitDesktop"


def ensure_utf8_stdio() -> None:
    """Print Chinese and other non-ASCII text safely, even when output is piped on Windows."""
    for stream in (sys.stdout, sys.stderr):
        if stream is not None and hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):
                pass


def python_executables() -> "tuple[Path, Path]":
    """Return (console interpreter, windowless interpreter).

    On Windows the windowless one is pythonw.exe so background helpers do not
    open a console window. Elsewhere both are the same interpreter.
    """
    exe = Path(sys.executable)
    if not IS_WINDOWS:
        return exe, exe
    name = exe.name.lower()
    console = exe.with_name("python.exe") if name == "pythonw.exe" else exe
    windowless = exe.with_name("pythonw.exe")
    if not console.exists():
        console = exe
    if not windowless.exists():
        windowless = console
    return console, windowless


# ---------------------------------------------------------------------------
# Language


def _lang_from_tag(tag: str) -> Optional[str]:
    tag = (tag or "").strip().strip('"').lower()
    if not tag or tag in ("c", "posix", "c.utf-8"):
        return None
    if tag.startswith("zh") or tag.startswith("chinese"):
        return "zh-CN"
    return "en"


def detect_language() -> str:
    """Best guess of the user's interface language: 'zh-CN' or 'en'."""
    forced = _lang_from_tag(os.environ.get("ORBIT_LANG", ""))
    if forced:
        return forced
    if IS_WINDOWS:
        try:
            import ctypes

            lang_id = ctypes.windll.kernel32.GetUserDefaultUILanguage()
            return "zh-CN" if (lang_id & 0x3FF) == 0x04 else "en"
        except Exception:
            pass
    if IS_MAC:
        try:
            out = subprocess.run(
                ["defaults", "read", "-g", "AppleLanguages"],
                capture_output=True, text=True, timeout=3,
            ).stdout
            match = re.search(r"\(\s*\"?([A-Za-z_-]+)", out)
            if match:
                found = _lang_from_tag(match.group(1))
                if found:
                    return found
        except Exception:
            pass
    for var in ("LC_ALL", "LC_MESSAGES", "LANG"):
        found = _lang_from_tag(os.environ.get(var, ""))
        if found:
            return found
    try:
        found = _lang_from_tag(locale.getlocale()[0] or "")
        if found:
            return found
    except Exception:
        pass
    return "en"


def pick(value: Any, lang: str, default: str = "") -> str:
    """Pick a localized string from either a plain string or {"en": ..., "zh-CN": ...}."""
    if value is None:
        return default
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        for key in (lang, lang.split("-")[0], "en", "zh-CN", "zh"):
            if key in value and value[key]:
                return str(value[key])
        for item in value.values():
            return str(item)
    return str(value)


# ---------------------------------------------------------------------------
# Known folders (Desktop may be redirected to OneDrive on Windows)

_WIN_FOLDER_IDS = {
    "desktop": "{B4BFCC3A-DB2C-424C-B029-7FE99A87C641}",
    "documents": "{FDD39AD0-238F-46AF-ADB4-6C85480369C7}",
    "downloads": "{374DE290-123F-4565-9164-39C4925E467B}",
    "pictures": "{33E28130-4E1E-4676-835A-98395C3BC3BB}",
    "music": "{4BD8D571-6D19-48D3-BE97-422220080E43}",
    "videos": "{18989B1D-99B5-455B-841C-AB7C74E4DDFC}",
}
_POSIX_FOLDER_NAMES = {
    "desktop": "Desktop",
    "documents": "Documents",
    "downloads": "Downloads",
    "pictures": "Pictures",
    "music": "Music",
    "videos": "Movies" if IS_MAC else "Videos",
}
_XDG_KEYS = {
    "desktop": "XDG_DESKTOP_DIR",
    "documents": "XDG_DOCUMENTS_DIR",
    "downloads": "XDG_DOWNLOAD_DIR",
    "pictures": "XDG_PICTURES_DIR",
    "music": "XDG_MUSIC_DIR",
    "videos": "XDG_VIDEOS_DIR",
}
KNOWN_FOLDERS = tuple(_WIN_FOLDER_IDS)


def _win_known_folder(folder_id: str) -> str:
    import ctypes
    from ctypes import wintypes

    class GUID(ctypes.Structure):
        _fields_ = [
            ("Data1", wintypes.DWORD),
            ("Data2", wintypes.WORD),
            ("Data3", wintypes.WORD),
            ("Data4", ctypes.c_ubyte * 8),
        ]

    u = uuid.UUID(folder_id)
    guid = GUID()
    guid.Data1 = u.time_low
    guid.Data2 = u.time_mid
    guid.Data3 = u.time_hi_version
    for index, byte in enumerate(u.bytes[8:]):
        guid.Data4[index] = byte

    shell32 = ctypes.WinDLL("shell32")
    ole32 = ctypes.WinDLL("ole32")
    get_path = shell32.SHGetKnownFolderPath
    get_path.argtypes = [ctypes.POINTER(GUID), wintypes.DWORD, wintypes.HANDLE, ctypes.POINTER(ctypes.c_wchar_p)]
    get_path.restype = ctypes.HRESULT
    ole32.CoTaskMemFree.argtypes = [ctypes.c_void_p]
    out = ctypes.c_wchar_p()
    get_path(ctypes.byref(guid), 0, None, ctypes.byref(out))
    try:
        return out.value or ""
    finally:
        ole32.CoTaskMemFree(ctypes.cast(out, ctypes.c_void_p))


def _xdg_folder(key: str) -> Optional[Path]:
    config = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "user-dirs.dirs"
    try:
        text = config.read_text(encoding="utf-8")
    except OSError:
        return None
    match = re.search(r'^%s="?([^"\n]+)"?' % re.escape(key), text, re.M)
    if not match:
        return None
    value = match.group(1).replace("$HOME", str(Path.home()))
    return Path(value)


def known_folder(name: str) -> Path:
    """Resolve 'desktop', 'documents', 'downloads', 'pictures', 'music', 'videos' or 'home'."""
    name = name.lower()
    if name == "home":
        return Path.home()
    if name == "workspace":
        return workspace_dir()
    if IS_WINDOWS and name in _WIN_FOLDER_IDS:
        try:
            found = _win_known_folder(_WIN_FOLDER_IDS[name])
            if found:
                return Path(found)
        except OSError:
            pass
    if IS_LINUX and name in _XDG_KEYS:
        found = _xdg_folder(_XDG_KEYS[name])
        if found:
            return found
    return Path.home() / _POSIX_FOLDER_NAMES.get(name, name)


_PLACEHOLDER = re.compile(r"\{([a-z]+)\}")


def expand_path(text: str, extra: Optional[Dict[str, str]] = None) -> Path:
    """Expand ~ and placeholders such as {desktop}, {documents}, {downloads}, {home}, {workspace}."""
    extra = extra or {}

    def replace(match: "re.Match[str]") -> str:
        key = match.group(1)
        if key in extra:
            return str(extra[key])
        if key in _WIN_FOLDER_IDS or key in ("home", "workspace"):
            return str(known_folder(key))
        return match.group(0)

    expanded = _PLACEHOLDER.sub(replace, str(text))
    return Path(os.path.expandvars(expanded)).expanduser()


def is_url(text: str) -> bool:
    return bool(re.match(r"^https?://", str(text), re.I))


def open_path(target: "str | Path") -> None:
    """Open a folder, file or web address with the system's default handler."""
    target = str(target)
    if is_url(target):
        webbrowser.open(target)
        return
    if IS_WINDOWS:
        os.startfile(target)  # type: ignore[attr-defined]
    elif IS_MAC:
        subprocess.run(["open", target], check=True, timeout=15)
    else:
        subprocess.run(["xdg-open", target], check=True, timeout=15)


# ---------------------------------------------------------------------------
# Files


def read_json(path: "str | Path", default: Any = None) -> Any:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return default


def write_json(path: "str | Path", data: Any, private: bool = False) -> None:
    """Write JSON atomically so a crash never leaves a half-written file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".tmp-", suffix=".json", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        if private and not IS_WINDOWS:
            os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise


def append_jsonl(path: "str | Path", record: Dict[str, Any]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def read_jsonl(path: "str | Path") -> "list[Dict[str, Any]]":
    records = []
    try:
        with open(path, encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(json.loads(line))
                except ValueError:
                    continue  # a torn last line after a crash is ignored
    except OSError:
        pass
    return records


class Busy(Exception):
    """Another process holds the lock."""


@contextlib.contextmanager
def file_lock(path: "str | Path") -> Iterator[None]:
    """A non-blocking cross-process lock. Raises Busy when someone else holds it."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = open(path, "a+")
    locked = False
    try:
        if IS_WINDOWS:
            import msvcrt

            handle.seek(0)
            try:
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as exc:
                raise Busy(str(path)) from exc
        else:
            import fcntl

            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as exc:
                raise Busy(str(path)) from exc
        locked = True
        yield
    finally:
        if locked:
            with contextlib.suppress(OSError):
                if IS_WINDOWS:
                    import msvcrt

                    handle.seek(0)
                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        handle.close()
