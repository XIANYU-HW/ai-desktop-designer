"""Everything that touches the operating system around the helper:
starting it in the background, opening previews, taking snapshots,
placing the page on the desktop (Lively Wallpaper on Windows, Plash on
macOS) and starting the helper when the user signs in.
"""
from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from . import VERSION, env
from .config import Workspace
from .server import ping

LIVELY_APP_ID = "{E3E43E1B-DEC8-44BF-84A6-243DBA3F2CB1}_is1"
LIVELY_PACKAGE = "orbit-desktop"
PLASH_APP_STORE = "https://apps.apple.com/app/plash/id1494023538"
LIVELY_WEBSITE = "https://www.rocksdanister.com/lively/"
AUTOSTART_NAME = "OrbitDesktop"
LAUNCH_AGENT_LABEL = "io.github.orbit-desktop.helper"


def base_url(port: int) -> str:
    return f"http://127.0.0.1:{port}"


# --------------------------------------------------------------------------- helper process

def helper_command(workspace: Workspace, windowless: bool = True) -> List[str]:
    console, quiet = env.python_executables()
    exe = quiet if windowless else console
    command = [str(exe), str(env.ORBIT_SCRIPT)]
    if os.environ.get("ORBIT_WORKSPACE"):
        command += ["--workspace", str(workspace.root)]
    return command + ["serve", "--quiet"]


def start_background(workspace: Workspace, wait: float = 10.0) -> Tuple[bool, str]:
    config = workspace.ensure()
    port = int(config["port"])
    if ping(port):
        return True, "already running"
    workspace.logs_dir.mkdir(parents=True, exist_ok=True)
    log_file = open(workspace.logs_dir / "console.log", "a", encoding="utf-8")
    kwargs: Dict[str, Any] = {"stdin": subprocess.DEVNULL, "stdout": log_file, "stderr": log_file, "close_fds": True, "cwd": str(workspace.root)}
    if env.IS_WINDOWS:
        kwargs["creationflags"] = env.DETACHED_PROCESS | env.CREATE_NEW_PROCESS_GROUP | env.CREATE_NO_WINDOW
    else:
        kwargs["start_new_session"] = True
    proc = subprocess.Popen(helper_command(workspace, windowless=True), **kwargs)
    log_file.close()
    deadline = time.time() + wait
    while time.time() < deadline:
        if ping(port):
            return True, "started"
        if proc.poll() is not None:  # the helper exited: say why
            return False, _last_log_lines(workspace) or f"the helper exited with code {proc.returncode}"
        time.sleep(0.25)
    return False, f"the helper did not answer; see {workspace.logs_dir / 'orbit.log'}"


def _last_log_lines(workspace: Workspace, count: int = 6) -> str:
    lines: List[str] = []
    for name in ("orbit.log", "console.log"):
        try:
            text = (workspace.logs_dir / name).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        lines += [l for l in text.splitlines() if l.strip()][-count:]
    return "\n".join(lines[-count:])


def stop_background(workspace: Workspace) -> bool:
    config = workspace.load()
    port = int(config.get("port") or 47321)
    if not ping(port):
        return True
    try:
        request = urllib.request.Request(
            f"{base_url(port)}/api/shutdown",
            data=b"{}",
            method="POST",
            headers={"Content-Type": "application/json", "X-Orbit-Token": str(config.get("token") or "")},
        )
        urllib.request.build_opener(urllib.request.ProxyHandler({})).open(request, timeout=3).read()
    except Exception:
        pass
    for _ in range(20):
        if not ping(port):
            return True
        time.sleep(0.25)
    info = env.read_json(workspace.server_file, {}) or {}
    pid = info.get("pid")
    if pid:
        try:
            os.kill(int(pid), signal.SIGTERM)  # our own helper process
        except OSError:
            pass
    time.sleep(0.5)
    return not ping(port)


# --------------------------------------------------------------------------- browsers

def find_browser() -> Optional[str]:
    """A Chromium-based browser for previews and snapshots (Edge ships with Windows)."""
    custom = os.environ.get("ORBIT_BROWSER")
    if custom and Path(custom).exists():
        return custom
    candidates: List[str] = []
    if env.IS_WINDOWS:
        roots = [os.environ.get(k) for k in ("ProgramFiles(x86)", "ProgramFiles", "LOCALAPPDATA")]
        for root in filter(None, roots):
            candidates += [
                os.path.join(root, "Microsoft", "Edge", "Application", "msedge.exe"),
                os.path.join(root, "Google", "Chrome", "Application", "chrome.exe"),
                os.path.join(root, "BraveSoftware", "Brave-Browser", "Application", "brave.exe"),
            ]
    elif env.IS_MAC:
        for root in ("/Applications", str(Path.home() / "Applications")):
            candidates += [
                f"{root}/Google Chrome.app/Contents/MacOS/Google Chrome",
                f"{root}/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
                f"{root}/Chromium.app/Contents/MacOS/Chromium",
                f"{root}/Brave Browser.app/Contents/MacOS/Brave Browser",
            ]
    else:
        for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "microsoft-edge", "brave-browser"):
            found = shutil.which(name)
            if found:
                candidates.append(found)
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return candidate
    return None


def open_preview(workspace: Workspace, url: str, fullscreen: bool = True) -> str:
    """Open the page in a chrome-less browser window that looks like a desktop."""
    browser = find_browser()
    if not browser:
        env.open_path(url)
        return "default-browser"
    profile = workspace.state_dir / "preview-browser"
    profile.mkdir(parents=True, exist_ok=True)
    args = [browser, f"--app={url}", f"--user-data-dir={profile}", "--no-first-run", "--no-default-browser-check"]
    if fullscreen:
        args.append("--start-fullscreen")
    kwargs: Dict[str, Any] = {"stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL, "close_fds": True}
    if env.IS_WINDOWS:
        kwargs["creationflags"] = env.DETACHED_PROCESS
    else:
        kwargs["start_new_session"] = True
    subprocess.Popen(args, **kwargs)
    return Path(browser).name


def snapshot(url: str, out: Path, width: int = 1920, height: int = 1080, wait_ms: int = 4000) -> Tuple[bool, str]:
    """Render a page with a headless browser into a PNG file."""
    browser = find_browser()
    if not browser:
        return False, "no Chrome, Edge, Chromium or Brave browser found (set ORBIT_BROWSER to one)"
    out = Path(out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="orbit-snap-") as profile:
        args = [
            browser, "--headless=new", "--hide-scrollbars", "--mute-audio", "--no-first-run",
            "--no-default-browser-check", "--disable-extensions", f"--user-data-dir={profile}",
            f"--window-size={width},{height}", f"--virtual-time-budget={wait_ms}",
            f"--screenshot={out}", url,
        ]
        try:
            proc = subprocess.run(args, capture_output=True, text=True, timeout=max(60, wait_ms / 1000 * 4))
        except subprocess.TimeoutExpired:
            return False, "the browser took too long"
    if out.exists() and out.stat().st_size > 0:
        return True, str(out)
    return False, (proc.stderr or proc.stdout or "no image produced")[-400:]


# --------------------------------------------------------------------------- Windows: Lively Wallpaper

def _registry_install_location() -> Optional[str]:
    try:
        import winreg  # type: ignore
    except ImportError:
        return None
    key_path = rf"Software\Microsoft\Windows\CurrentVersion\Uninstall\{LIVELY_APP_ID}"
    for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        for view in (0, getattr(winreg, "KEY_WOW64_64KEY", 0), getattr(winreg, "KEY_WOW64_32KEY", 0)):
            try:
                with winreg.OpenKey(hive, key_path, 0, winreg.KEY_READ | view) as key:
                    value, _ = winreg.QueryValueEx(key, "InstallLocation")
                    if value:
                        return str(value)
            except OSError:
                continue
    return None


def find_lively() -> Dict[str, Any]:
    """Locate Lively Wallpaper. The installer version can be controlled from the command line."""
    info: Dict[str, Any] = {"installed": False, "exe": None, "store": False}
    if not env.IS_WINDOWS:
        return info
    local = os.environ.get("LOCALAPPDATA", "")
    candidates = []
    location = _registry_install_location()
    if location:
        candidates.append(os.path.join(location, "Lively.exe"))
    candidates += [
        os.path.join(local, "Programs", "Lively Wallpaper", "Lively.exe"),
        os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"), "Lively Wallpaper", "Lively.exe"),
    ]
    for candidate in candidates:
        if candidate and os.path.isfile(candidate):
            info.update(installed=True, exe=candidate)
            break
    packages = Path(local) / "Packages"
    if packages.is_dir():
        store = [p for p in packages.glob("*rocksdanister.LivelyWallpaper*") if p.is_dir()]
        if store:
            info["store"] = True
            info["installed"] = True
            info["store_data"] = str(store[0] / "LocalCache" / "Local" / "Lively Wallpaper")
    return info


def lively_library(info: Dict[str, Any]) -> Path:
    local = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local")))
    data_dir = local / "Lively Wallpaper"
    if not info.get("exe") and info.get("store_data"):
        data_dir = Path(info["store_data"])
    settings = env.read_json(data_dir / "Settings.json", {}) or {}
    wallpaper_dir = settings.get("WallpaperDir") if isinstance(settings, dict) else None
    return Path(wallpaper_dir) if wallpaper_dir else data_dir / "Library"


def install_lively(workspace: Workspace, url: str, theme_dir: Optional[Path] = None) -> Tuple[bool, str]:
    info = find_lively()
    if not info["installed"]:
        return False, "lively-missing"
    package = lively_library(info) / "wallpapers" / LIVELY_PACKAGE
    package.mkdir(parents=True, exist_ok=True)
    thumbnail = ""
    if theme_dir and (Path(theme_dir) / "preview.png").exists():
        shutil.copy2(Path(theme_dir) / "preview.png", package / "thumbnail.png")
        thumbnail = "thumbnail.png"
    env.write_json(package / "LivelyInfo.json", {
        "AppVersion": "2.2.1.0",
        "Title": "Orbit Desktop",
        "Thumbnail": thumbnail,
        "Preview": "",
        "Desc": "Your Orbit Desktop theme, served by the local Orbit helper.",
        "Author": "Orbit Desktop",
        "License": "MIT",
        "Contact": url,
        "Type": 3,              # url wallpaper
        "FileName": url,
        "Arguments": "--pause-event true",
        "IsAbsolutePath": True,
    })
    if not info.get("exe"):
        return False, "lively-store"
    try:
        subprocess.run([info["exe"], "setwp", "--file", str(package)], timeout=30, creationflags=env.CREATE_NO_WINDOW)
    except (OSError, subprocess.SubprocessError) as exc:
        return False, f"lively-command-failed: {exc}"
    return True, str(package)


def reload_lively() -> None:
    info = find_lively()
    if info.get("exe"):
        try:
            subprocess.run([info["exe"], "setwp", "--file", "reload"], timeout=20, creationflags=env.CREATE_NO_WINDOW)
        except (OSError, subprocess.SubprocessError):
            pass


def uninstall_lively() -> Tuple[bool, str]:
    info = find_lively()
    if not info["installed"]:
        return True, "lively-missing"
    if info.get("exe"):
        try:
            subprocess.run([info["exe"], "closewp", "--monitor", "-1"], timeout=20, creationflags=env.CREATE_NO_WINDOW)
        except (OSError, subprocess.SubprocessError):
            pass
    package = lively_library(info) / "wallpapers" / LIVELY_PACKAGE
    if package.is_dir() and (package / "LivelyInfo.json").exists():
        shutil.rmtree(package, ignore_errors=True)  # the folder Orbit created, nothing else
    return True, str(package)


def copy_to_clipboard(text: str) -> bool:
    try:
        if env.IS_WINDOWS:
            data = ("﻿" + text).encode("utf-16-le")  # the BOM tells clip.exe the text is Unicode
            subprocess.run(["clip"], input=data, check=True, timeout=5, creationflags=env.CREATE_NO_WINDOW)
        elif env.IS_MAC:
            subprocess.run(["pbcopy"], input=text.encode("utf-8"), check=True, timeout=5)
        else:
            subprocess.run(["xclip", "-selection", "clipboard"], input=text.encode("utf-8"), check=True, timeout=5)
        return True
    except (OSError, subprocess.SubprocessError):
        return False


# --------------------------------------------------------------------------- macOS: Plash

def find_plash() -> Optional[str]:
    for root in ("/Applications", str(Path.home() / "Applications")):
        candidate = Path(root) / "Plash.app"
        if candidate.exists():
            return str(candidate)
    return None


def install_plash(url: str) -> Tuple[bool, str]:
    if not find_plash():
        return False, "plash-missing"
    query = urllib.parse.urlencode({"url": url, "title": "Orbit Desktop"}, quote_via=urllib.parse.quote)
    subprocess.run(["open", f"plash:add?{query}"], timeout=15)
    return True, "plash"


# --------------------------------------------------------------------------- start at sign-in

def _launch_agent_path() -> Path:
    return Path.home() / "Library" / "LaunchAgents" / f"{LAUNCH_AGENT_LABEL}.plist"


def _linux_autostart_path() -> Path:
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "autostart" / "orbit-desktop.desktop"


def autostart_enabled() -> bool:
    if env.IS_WINDOWS:
        try:
            import winreg  # type: ignore

            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run") as key:
                winreg.QueryValueEx(key, AUTOSTART_NAME)
                return True
        except OSError:
            return False
    if env.IS_MAC:
        return _launch_agent_path().exists()
    return _linux_autostart_path().exists()


def set_autostart(workspace: Workspace, enabled: bool) -> None:
    command = helper_command(workspace, windowless=True)
    if env.IS_WINDOWS:
        import winreg  # type: ignore

        line = subprocess.list2cmdline(command)
        run_key = r"Software\Microsoft\Windows\CurrentVersion\Run"
        if enabled:
            with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, run_key, 0, winreg.KEY_SET_VALUE) as key:
                winreg.SetValueEx(key, AUTOSTART_NAME, 0, winreg.REG_SZ, line)
            return
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, run_key, 0, winreg.KEY_SET_VALUE) as key:
                winreg.DeleteValue(key, AUTOSTART_NAME)
        except OSError:
            pass  # nothing to remove
        return
    if env.IS_MAC:
        plist = _launch_agent_path()
        if enabled:
            import plistlib

            plist.parent.mkdir(parents=True, exist_ok=True)
            plist.write_bytes(plistlib.dumps({
                "Label": LAUNCH_AGENT_LABEL,
                "ProgramArguments": command,
                "RunAtLoad": True,
                "KeepAlive": False,
                "StandardOutPath": str(workspace.logs_dir / "console.log"),
                "StandardErrorPath": str(workspace.logs_dir / "console.log"),
            }))
        elif plist.exists():
            subprocess.run(["launchctl", "unload", str(plist)], capture_output=True, timeout=10)
            plist.unlink()
        return
    path = _linux_autostart_path()
    if enabled:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "[Desktop Entry]\nType=Application\nName=Orbit Desktop\n"
            f"Exec={subprocess.list2cmdline(command)}\nX-GNOME-Autostart-enabled=true\n",
            encoding="utf-8",
        )
    elif path.exists():
        path.unlink()


# --------------------------------------------------------------------------- diagnostics

def doctor(workspace: Workspace) -> List[Tuple[str, str, str]]:
    """Return (status, item, detail) rows. Status is ok, warn or missing."""
    rows: List[Tuple[str, str, str]] = []
    version_ok = sys.version_info >= (3, 9)
    rows.append(("ok" if version_ok else "missing", "Python", f"{sys.version.split()[0]} at {sys.executable}"))
    rows.append(("ok", "System", f"{env.PLATFORM} ({sys.platform})"))
    rows.append(("ok", "Orbit", f"{VERSION} at {env.SKILL_ROOT}"))
    config = workspace.load() if workspace.exists() else None
    rows.append(("ok" if config else "warn", "Workspace", f"{workspace.root}" + ("" if config else " (run: orbit.py init)")))
    if config:
        port = int(config.get("port") or 47321)
        running = ping(port)
        rows.append(("ok" if running else "warn", "Helper", f"running at {base_url(port)}/" if running else "not running (run: orbit.py start)"))
        loc = (config.get("location") or {}).get("name")
        rows.append(("ok" if loc else "warn", "Weather place", loc or "not set (run: orbit.py set-location <city>)"))
        rows.append(("ok", "Language", str(config.get("language"))))
        rows.append(("ok", "Active theme", str(config.get("active_theme"))))
    browser = find_browser()
    rows.append(("ok" if browser else "warn", "Preview browser", browser or "none found; previews open in the default browser, snapshots need Chrome or Edge"))
    if env.IS_WINDOWS:
        lively = find_lively()
        detail = lively.get("exe") or ("Microsoft Store version (set the wallpaper by hand)" if lively.get("store") else "not installed")
        rows.append(("ok" if lively.get("exe") else "warn", "Lively Wallpaper", detail))
    elif env.IS_MAC:
        plash = find_plash()
        rows.append(("ok" if plash else "warn", "Plash", plash or f"not installed ({PLASH_APP_STORE})"))
    rows.append(("ok" if autostart_enabled() else "warn", "Start at sign-in", "on" if autostart_enabled() else "off"))
    return rows
