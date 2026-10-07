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
    # The child may run at sign-in with a different environment and working directory.
    # Always keep the selected workspace, including an explicit CLI --workspace.
    return [str(exe), str(env.ORBIT_SCRIPT), "--workspace",
            str(workspace.root.expanduser().resolve()), "serve", "--quiet"]


def start_background(workspace: Workspace, wait: float = 10.0) -> Tuple[bool, str]:
    config = workspace.ensure()
    port = int(config["port"])
    if ping(port):
        return True, "already running"
    workspace.logs_dir.mkdir(parents=True, exist_ok=True)
    kwargs: Dict[str, Any] = {"stdin": subprocess.DEVNULL, "close_fds": True, "cwd": str(workspace.root)}
    if env.IS_WINDOWS:
        kwargs["creationflags"] = env.DETACHED_PROCESS | env.CREATE_NEW_PROCESS_GROUP | env.CREATE_NO_WINDOW
    else:
        kwargs["start_new_session"] = True
    try:
        with open(workspace.logs_dir / "console.log", "a", encoding="utf-8") as log_file:
            proc = subprocess.Popen(helper_command(workspace, windowless=True),
                                    stdout=log_file, stderr=log_file, **kwargs)
    except OSError as exc:
        return False, f"could not launch the helper: {exc}"
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


def quiet_profile(profile: Path, lang: str) -> None:
    """Make a browser profile used for desktop windows quiet.

    A page in another language than the browser's makes Edge and Chrome pop up a "Translate this
    page?" bubble in the top-left corner. It steals the focus, comes back on every new window, and
    on a desktop it looks broken. Turn translation off and accept the user's languages.
    """
    prefs_path = Path(profile) / "Default" / "Preferences"
    prefs = env.read_json(prefs_path, {}) or {}
    if not isinstance(prefs, dict):
        prefs = {}
    prefs.setdefault("translate", {})["enabled"] = False
    blocked = prefs.setdefault("translate_blocked_languages", [])
    for code in ("zh-CN", "zh", "en"):
        if code not in blocked:
            blocked.append(code)
    intl = prefs.setdefault("intl", {})
    if "zh" not in str(intl.get("accept_languages") or ""):
        intl["accept_languages"] = "zh-CN,zh,en-US,en" if lang.startswith("zh") else "en-US,en,zh-CN,zh"
    prefs.setdefault("browser", {})["has_seen_welcome_page"] = True
    prefs.setdefault("profile", {}).update({"exit_type": "Normal", "exited_cleanly": True})
    env.write_json(prefs_path, prefs)


def browser_window_args(browser: str, url: str, profile: Path, lang: str, fullscreen: bool) -> List[str]:
    """Command line for a chrome-less app window that shows a theme page."""
    args = [
        browser, f"--app={url}", f"--user-data-dir={profile}", "--no-first-run", "--no-default-browser-check",
        "--lang=" + ("zh-CN" if lang.startswith("zh") else "en-US"),
        "--disable-sync", "--hide-crash-restore-bubble", "--disable-features=Translate,TranslateUI",
    ]
    if fullscreen:
        args.append("--start-fullscreen")
    return args


def open_preview(workspace: Workspace, url: str, fullscreen: bool = True) -> str:
    """Open the page in a chrome-less browser window that looks like a desktop."""
    browser = find_browser()
    if not browser:
        env.open_path(url)
        return "default-browser"
    profile = workspace.state_dir / "preview-browser"
    profile.mkdir(parents=True, exist_ok=True)
    lang = str((workspace.load() if workspace.exists() else {}).get("language") or env.detect_language())
    quiet_profile(profile, lang)
    args = browser_window_args(browser, url, profile, lang, fullscreen)
    kwargs: Dict[str, Any] = {"stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL, "close_fds": True}
    if env.IS_WINDOWS:
        kwargs["creationflags"] = env.DETACHED_PROCESS
    else:
        kwargs["start_new_session"] = True
    subprocess.Popen(args, **kwargs)
    return Path(browser).name


_BROWSER_CLEANUP_SECONDS = 5.0
_BROWSER_STDOUT_LIMIT = 16 * 1024 * 1024
_BROWSER_STDERR_LIMIT = 64 * 1024


def _stop_headless(proc: subprocess.Popen) -> str:
    """Stop only this render's isolated group/tree, then reap with a deadline.

    Never match browser names: the user's normal browser is a separate process.
    A process group is created at launch on POSIX; Windows taskkill targets only
    the new browser PID and its descendants.
    """
    cleanup_error = ""
    if env.IS_WINDOWS:
        try:
            result = subprocess.run(
                ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                timeout=_BROWSER_CLEANUP_SECONDS, creationflags=env.CREATE_NO_WINDOW,
            )
            if result.returncode:
                cleanup_error = "the render process tree cleanup failed"
                proc.kill()
        except (OSError, subprocess.SubprocessError):
            cleanup_error = "the render process tree cleanup failed"
            try:
                proc.kill()
            except OSError:
                pass
    else:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        except OSError:
            cleanup_error = "the isolated render process group cleanup failed"
            try:
                proc.kill()
            except OSError:
                pass
    try:
        proc.wait(timeout=_BROWSER_CLEANUP_SECONDS)
    except subprocess.TimeoutExpired:
        return "the render process did not exit within the cleanup deadline"
    return cleanup_error


def _run_headless(args: List[str], timeout: float) -> Tuple[bytes, bytes, bool, str]:
    """Capture output without pipes that surviving browser children can hold open."""
    with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
        kwargs: Dict[str, Any] = {"stdin": subprocess.DEVNULL, "stdout": stdout, "stderr": stderr}
        if env.IS_WINDOWS:
            kwargs["creationflags"] = env.CREATE_NO_WINDOW | env.CREATE_NEW_PROCESS_GROUP
        else:
            kwargs["start_new_session"] = True
        try:
            proc = subprocess.Popen(args, **kwargs)
        except OSError as exc:
            return b"", str(exc).encode("utf-8", errors="replace"), False, "could not start the browser"
        timed_out, cleanup_error = False, ""
        try:
            proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            cleanup_error = _stop_headless(proc)
        except BaseException:
            # A new POSIX session does not receive the terminal's Ctrl+C. Reap
            # our render before propagating cancellation to the caller.
            _stop_headless(proc)
            raise
        stdout.seek(0)
        output = stdout.read(_BROWSER_STDOUT_LIMIT + 1)
        if len(output) > _BROWSER_STDOUT_LIMIT:
            output = b""
            cleanup_error = cleanup_error or "browser DOM output exceeded the size limit"
        stderr.seek(0, os.SEEK_END)
        stderr.seek(max(0, stderr.tell() - _BROWSER_STDERR_LIMIT))
        errors = stderr.read(_BROWSER_STDERR_LIMIT)
        return output, errors, timed_out, cleanup_error


def _browser_error(message: str, stderr: bytes) -> str:
    detail = stderr.decode("utf-8", errors="replace").strip()[-400:]
    return message + (": " + detail if detail else "")


def snapshot(url: str, out: Path, width: int = 1920, height: int = 1080, wait_ms: int = 4000) -> Tuple[bool, str]:
    """Render a page with a headless browser into a PNG file."""
    browser = find_browser()
    if not browser:
        return False, "no Chrome, Edge, Chromium or Brave browser found (set ORBIT_BROWSER to one)"
    out = Path(out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()
    with tempfile.TemporaryDirectory(prefix="orbit-snap-") as profile:
        args = [
            browser, "--headless=new", "--hide-scrollbars", "--mute-audio", "--no-first-run",
            "--no-default-browser-check", "--disable-extensions", "--disable-sync",
            "--disable-background-networking", "--disable-component-update",
            "--use-mock-keychain",          # macOS: never wait on a keychain prompt
            "--password-store=basic",       # Linux: same for the desktop keyring
            f"--user-data-dir={profile}", f"--window-size={width},{height}",
            f"--virtual-time-budget={wait_ms}", f"--screenshot={out}", url,
        ]
        _, err, timed_out, cleanup_error = _run_headless(args, timeout=max(60, wait_ms / 1000 * 4))
        if cleanup_error:
            return False, _browser_error(cleanup_error, err)
        # Some browsers write the picture and then fail to exit; keep the image
        # only after bounded cleanup has reaped the process we started.
        if timed_out and not (out.exists() and out.stat().st_size > 0):
            return False, _browser_error("the browser took too long", err)
    if out.exists() and out.stat().st_size > 0:
        return True, str(out)
    return False, _browser_error("no image produced", err)


def dump_dom(url: str, width: int = 1920, height: int = 1080, wait_ms: int = 5000) -> Tuple[bool, str]:
    """Load a page in a headless browser and return its DOM after `wait_ms` of (virtual) time."""
    browser = find_browser()
    if not browser:
        return False, "no Chrome, Edge, Chromium or Brave browser found (set ORBIT_BROWSER to one)"
    with tempfile.TemporaryDirectory(prefix="orbit-dom-") as profile:
        args = [
            browser, "--headless=new", "--hide-scrollbars", "--mute-audio", "--no-first-run",
            "--no-default-browser-check", "--disable-extensions", "--disable-sync",
            "--disable-background-networking", "--disable-component-update",
            "--use-mock-keychain", "--password-store=basic",
            f"--user-data-dir={profile}", f"--window-size={width},{height}",
            f"--virtual-time-budget={wait_ms}", "--dump-dom", url,
        ]
        out, err, timed_out, cleanup_error = _run_headless(args, timeout=max(60, wait_ms / 1000 * 4))
        if cleanup_error or timed_out:
            return False, _browser_error(cleanup_error or "the browser took too long", err)
    text = out.decode("utf-8", errors="replace") if out else ""
    if text.strip():
        return True, text
    return False, _browser_error("no DOM produced", err)


def capture_screen(out: Path) -> Tuple[bool, str]:
    """Save a picture of the whole real screen (all monitors), wallpaper, icons and windows included.

    This is how an agent checks the installed desktop with its own eyes. It shows whatever is on the
    screen, so only do it when the user asked for the desktop to be checked.
    """
    out = Path(out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    try:
        if env.IS_WINDOWS:
            script = (
                "Add-Type -AssemblyName System.Windows.Forms,System.Drawing;"
                "Add-Type -Namespace Orbit -Name Dpi -MemberDefinition '[DllImport(\"user32.dll\")] public static extern bool SetProcessDPIAware();';"
                "[Orbit.Dpi]::SetProcessDPIAware() | Out-Null;"
                "$b=[System.Windows.Forms.SystemInformation]::VirtualScreen;"
                "$bmp=New-Object System.Drawing.Bitmap $b.Width,$b.Height;"
                "$g=[System.Drawing.Graphics]::FromImage($bmp);"
                "$g.CopyFromScreen($b.Left,$b.Top,0,0,$bmp.Size);"
                "$bmp.Save($env:ORBIT_CAPTURE,[System.Drawing.Imaging.ImageFormat]::Png);"
                "$g.Dispose();$bmp.Dispose()"
            )
            run_env = dict(os.environ, ORBIT_CAPTURE=str(out))
            subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
                           env=run_env, timeout=30, check=True, creationflags=env.CREATE_NO_WINDOW,
                           stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        elif env.IS_MAC:
            subprocess.run(["screencapture", "-x", str(out)], timeout=30, check=True)
        else:
            tool = shutil.which("gnome-screenshot") or shutil.which("import")
            if not tool:
                return False, "no screenshot tool (install gnome-screenshot or ImageMagick)"
            command = [tool, "-f", str(out)] if tool.endswith("gnome-screenshot") else [tool, "-window", "root", str(out)]
            subprocess.run(command, timeout=30, check=True)
    except (OSError, subprocess.SubprocessError) as exc:
        return False, f"screen capture failed: {exc}"
    if out.exists() and out.stat().st_size > 0:
        return True, str(out)
    return False, "no picture was written (on macOS, allow Screen Recording for the terminal)"


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
    """Create the library entry and report whether Lively accepted the request, not display verification."""
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
        result = subprocess.run([info["exe"], "setwp", "--file", str(package)], timeout=30,
                                capture_output=True, text=True, creationflags=env.CREATE_NO_WINDOW)
    except (OSError, subprocess.SubprocessError) as exc:
        return False, f"lively-command-failed: {exc}"
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()[-400:]
        return False, f"lively-command-failed: exit {result.returncode}" + (f": {detail}" if detail else "")
    # A zero exit status acknowledges the command; it does not verify the desktop.
    return True, f"lively-request-accepted: {package}"


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
    # closewp selects monitors, not a particular Orbit instance. Without a verified
    # mapping it could close another wallpaper, so leave host removal to the user.
    # Keep the library files too: they may still belong to an active wallpaper.
    return False, "lively-manual-removal"


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
    """Submit a Plash URL request; success only means the OS accepted that request."""
    if not find_plash():
        return False, "plash-missing"
    query = urllib.parse.urlencode({"url": url, "title": "Orbit Desktop"}, quote_via=urllib.parse.quote)
    try:
        result = subprocess.run(["open", f"plash:add?{query}"], timeout=15,
                                capture_output=True, text=True)
    except (OSError, subprocess.SubprocessError) as exc:
        return False, f"plash-command-failed: {exc}"
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()[-400:]
        return False, f"plash-command-failed: exit {result.returncode}" + (f": {detail}" if detail else "")
    return True, "plash-request-accepted"


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
        except FileNotFoundError:
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
