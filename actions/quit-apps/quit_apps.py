"""quit-apps: politely ask open apps to quit ("wind down"), and reopen them later.

Safety rules this action keeps:
  * it only sends the normal close request (WM_CLOSE on Windows, the standard
    quit request on macOS), exactly like clicking the close button
  * it never force-kills; an app that asks "save changes?" is left waiting for you
  * the system shell, terminals, AI tools, password managers, sync, VPN/proxy,
    security, remote-desktop and virtualization apps are always left open
  * the process tree that runs this helper or your AI agent is left open
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

sys.path.insert(0, os.environ.get("ORBIT_RUNTIME") or str(Path(__file__).resolve().parents[2] / "runtime"))
from orbitcore import kit  # noqa: E402

# --------------------------------------------------------------------------- protection lists

WIN_SYSTEM = {
    "explorer.exe", "dwm.exe", "sihost.exe", "shellexperiencehost.exe", "startmenuexperiencehost.exe",
    "searchhost.exe", "searchapp.exe", "searchui.exe", "textinputhost.exe", "lockapp.exe", "ctfmon.exe",
    "taskmgr.exe", "systemsettingsbroker.exe", "runtimebroker.exe", "securityhealthsystray.exe",
    "widgets.exe", "phoneexperiencehost.exe", "gamebar.exe", "nvidia share.exe", "rundll32.exe",
}
WIN_PROTECTED = {
    # terminals and shells
    "windowsterminal.exe", "wt.exe", "cmd.exe", "powershell.exe", "pwsh.exe", "conhost.exe", "openconsole.exe",
    "mintty.exe", "alacritty.exe", "wezterm-gui.exe", "hyper.exe", "tabby.exe", "putty.exe", "mobaxterm.exe",
    "git-bash.exe", "bash.exe", "wsl.exe", "wslhost.exe",
    # AI tools and this helper
    "claude.exe", "codex.exe", "chatgpt.exe", "python.exe", "pythonw.exe", "py.exe", "pyw.exe",
    # wallpaper hosts
    "lively.exe", "livelywpf.exe", "wallpaper32.exe", "wallpaper64.exe",
    # password managers
    "1password.exe", "bitwarden.exe", "keepass.exe", "keepassxc.exe", "dashlane.exe", "enpass.exe", "lastpass.exe",
    # sync and backup
    "onedrive.exe", "dropbox.exe", "googledrivefs.exe", "box.exe", "iclouddrive.exe", "icloudservices.exe",
    "baidunetdisk.exe", "nutstore.exe", "synologydrive.exe", "backblaze.exe",
    # remote desktop and virtualization
    "teamviewer.exe", "anydesk.exe", "mstsc.exe", "rustdesk.exe", "todesk.exe", "sunloginclient.exe",
    "vmware.exe", "vmware-vmx.exe", "virtualbox.exe", "virtualboxvm.exe", "docker desktop.exe", "vmconnect.exe",
}
MAC_SYSTEM = {
    "com.apple.finder", "com.apple.dock", "com.apple.systemuiserver", "com.apple.controlcenter",
    "com.apple.notificationcenterui", "com.apple.loginwindow", "com.apple.wallpaper.agent",
}
MAC_PROTECTED = {
    "com.apple.terminal", "com.googlecode.iterm2", "dev.warp.warp-stable", "com.mitchellh.ghostty",
    "net.kovidgoyal.kitty", "io.alacritty", "com.github.wez.wezterm", "co.zeit.hyper",
    "com.anthropic.claudefordesktop", "com.openai.chat", "com.openai.codex",
    "com.sindresorhus.plash", "com.apple.keychainaccess", "com.apple.activitymonitor",
    "com.1password.1password", "com.agilebits.onepassword7", "com.bitwarden.desktop",
    "com.microsoft.onedrive", "com.getdropbox.dropbox", "com.google.drivefs",
    "com.parallels.desktop.console", "com.vmware.fusion", "com.docker.docker", "dev.orbstack.orbstack", "com.utmapp.utm",
    "com.teamviewer.teamviewer", "com.anydesk.anydeskmacos",
}
MUSIC = {
    "spotify.exe", "cloudmusic.exe", "qqmusic.exe", "kugou.exe", "kwmusic.exe", "itunes.exe", "applemusic.exe",
    "foobar2000.exe", "aimp.exe", "musicbee.exe",
    "com.spotify.client", "com.apple.music", "com.netease.163music", "com.tencent.qqmusicmac", "com.kugou.mac",
}
AI_NAMES = ("chatgpt", "claude", "codex")  # also catches web-app wrappers such as a ChatGPT Safari web app
PROTECTED_TOKENS = (
    "vpn", "clash", "v2ray", "shadowsocks", "trojan", "sing-box", "nekoray", "hiddify", "surge", "quantumult",
    "password", "keychain", "antivirus", "defender", "kaspersky", "avast", "bitdefender", "eset", "malwarebytes",
    "huorong", "360safe", "360tray", "hipsmain", "hipstray", "wireguard", "tailscale", "zerotier", "openvpn",
    "terminal", "backup", "timemachine",
)


def ancestors() -> Set[int]:
    """Process ids of this action, the helper and whoever started them (e.g. the AI agent's terminal)."""
    chain: Set[int] = set()
    pid = os.getpid()
    if kit.IS_WINDOWS:
        parents = win_parent_map()
        while pid and pid not in chain:
            chain.add(pid)
            pid = parents.get(pid, 0)
        return chain
    while pid > 1 and pid not in chain:
        chain.add(pid)
        try:
            out = subprocess.run(["ps", "-o", "ppid=", "-p", str(pid)], capture_output=True, text=True, timeout=3).stdout.strip()
            pid = int(out or 0)
        except (OSError, ValueError, subprocess.SubprocessError):
            break
    return chain


def clean_name(text: str) -> str:
    """Drop invisible formatting characters some apps put in their names (e.g. U+200E)."""
    return "".join(ch for ch in str(text or "") if unicodedata.category(ch) != "Cf").strip()


def _match_any(values: List[str], app: Dict[str, Any]) -> bool:
    keys = {str(app.get(k) or "").lower() for k in ("name", "exe", "bundle", "id")}
    keys |= {k[:-4] for k in keys if k.endswith(".exe")}
    keys.discard("")
    return any(str(v).strip().lower() in keys for v in values if str(v).strip())


def protection(ctx: kit.Context, app: Dict[str, Any], tree: Set[int]) -> Optional[str]:
    ident = str(app.get("exe") or app.get("bundle") or "").lower()
    name = str(app.get("name") or "").lower()
    if app.get("pid") in tree and app.get("kind") == "app":
        return ctx.t("正在运行这个助手或你的 AI", "runs this helper or your AI agent")
    if _match_any(list(ctx.param("keep", []) or []), app):
        return ctx.t("你设置了保留", "you chose to keep it")
    only = list(ctx.param("only", []) or [])
    if only and not _match_any(only, app):
        return ctx.t("不在这次的范围内", "not in this run's list")
    if ident in WIN_SYSTEM or ident in MAC_SYSTEM:
        return ctx.t("系统组件", "part of the system")
    if ident in WIN_PROTECTED or ident in MAC_PROTECTED:
        return ctx.t("终端、AI、同步、安全等工具保持运行", "terminals, AI, sync and security tools stay open")
    if any(token in name for token in AI_NAMES):
        return ctx.t("AI 工具保持运行", "AI tools stay open")
    if any(token in ident or token in name for token in PROTECTED_TOKENS):
        return ctx.t("网络、安全或备份类工具保持运行", "network, security and backup tools stay open")
    if ctx.param("keep_music", True) and ident in MUSIC:
        return ctx.t("音乐继续播放", "music keeps playing")
    if app.get("kind") == "folders" and not ctx.param("close_folders", True):
        return ctx.t("你设置了保留文件夹窗口", "you chose to keep folder windows")
    return None


# --------------------------------------------------------------------------- Windows

if kit.IS_WINDOWS:
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    version_dll = ctypes.WinDLL("version")
    try:
        dwmapi = ctypes.WinDLL("dwmapi")
        dwmapi.DwmGetWindowAttribute.argtypes = [wintypes.HWND, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD]
        dwmapi.DwmGetWindowAttribute.restype = ctypes.c_long
    except OSError:
        dwmapi = None

    WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    user32.EnumWindows.argtypes = [WNDENUMPROC, wintypes.LPARAM]
    user32.EnumWindows.restype = wintypes.BOOL
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.IsWindowVisible.restype = wintypes.BOOL
    user32.IsWindow.argtypes = [wintypes.HWND]
    user32.IsWindow.restype = wintypes.BOOL
    user32.GetWindow.argtypes = [wintypes.HWND, wintypes.UINT]
    user32.GetWindow.restype = wintypes.HWND
    user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
    user32.GetWindowTextLengthW.restype = ctypes.c_int
    user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.GetWindowTextW.restype = ctypes.c_int
    user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.GetClassNameW.restype = ctypes.c_int
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    user32.PostMessageW.restype = wintypes.BOOL
    _get_window_long = getattr(user32, "GetWindowLongPtrW", None) or user32.GetWindowLongW
    _get_window_long.argtypes = [wintypes.HWND, ctypes.c_int]
    _get_window_long.restype = ctypes.c_ssize_t

    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    kernel32.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
    kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
    kernel32.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
    kernel32.GetProcessTimes.restype = wintypes.BOOL
    kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel32.WaitForSingleObject.restype = wintypes.DWORD

    class PROCESSENTRY32W(ctypes.Structure):
        _fields_ = [
            ("dwSize", wintypes.DWORD),
            ("cntUsage", wintypes.DWORD),
            ("th32ProcessID", wintypes.DWORD),
            ("th32DefaultHeapID", ctypes.c_size_t),
            ("th32ModuleID", wintypes.DWORD),
            ("cntThreads", wintypes.DWORD),
            ("th32ParentProcessID", wintypes.DWORD),
            ("pcPriClassBase", ctypes.c_long),
            ("dwFlags", wintypes.DWORD),
            ("szExeFile", ctypes.c_wchar * 260),
        ]

    kernel32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    kernel32.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
    kernel32.Process32FirstW.restype = wintypes.BOOL
    kernel32.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
    kernel32.Process32NextW.restype = wintypes.BOOL

    version_dll.GetFileVersionInfoSizeW.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(wintypes.DWORD)]
    version_dll.GetFileVersionInfoSizeW.restype = wintypes.DWORD
    version_dll.GetFileVersionInfoW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p]
    version_dll.GetFileVersionInfoW.restype = wintypes.BOOL
    version_dll.VerQueryValueW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR, ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(wintypes.UINT)]
    version_dll.VerQueryValueW.restype = wintypes.BOOL

WM_CLOSE = 0x0010
GW_OWNER = 4
GWL_EXSTYLE = -20
WS_EX_TOOLWINDOW = 0x00000080
DWMWA_CLOAKED = 14
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
SYNCHRONIZE = 0x00100000
WAIT_OBJECT_0 = 0
TH32CS_SNAPPROCESS = 0x2
IGNORED_CLASSES = {"Progman", "WorkerW", "Shell_TrayWnd", "Shell_SecondaryTrayWnd", "Windows.UI.Core.CoreWindow", "NotifyIconOverflowWindow"}


def win_parent_map() -> Dict[int, int]:
    parents: Dict[int, int] = {}
    snapshot = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if not snapshot or snapshot == ctypes.c_void_p(-1).value:
        return parents
    try:
        entry = PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(PROCESSENTRY32W)
        ok = kernel32.Process32FirstW(snapshot, ctypes.byref(entry))
        while ok:
            parents[int(entry.th32ProcessID)] = int(entry.th32ParentProcessID)
            ok = kernel32.Process32NextW(snapshot, ctypes.byref(entry))
    finally:
        kernel32.CloseHandle(snapshot)
    return parents


def win_running_exes() -> Set[str]:
    names: Set[str] = set()
    snapshot = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if not snapshot or snapshot == ctypes.c_void_p(-1).value:
        return names
    try:
        entry = PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(PROCESSENTRY32W)
        ok = kernel32.Process32FirstW(snapshot, ctypes.byref(entry))
        while ok:
            names.add(entry.szExeFile.lower())
            ok = kernel32.Process32NextW(snapshot, ctypes.byref(entry))
    finally:
        kernel32.CloseHandle(snapshot)
    return names


def _window_text(hwnd: int) -> str:
    length = user32.GetWindowTextLengthW(hwnd)
    buffer = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buffer, length + 1)
    return buffer.value


def _class_name(hwnd: int) -> str:
    buffer = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, buffer, 256)
    return buffer.value


def _cloaked(hwnd: int) -> bool:
    if dwmapi is None:
        return False
    value = wintypes.DWORD(0)
    if dwmapi.DwmGetWindowAttribute(hwnd, DWMWA_CLOAKED, ctypes.byref(value), ctypes.sizeof(value)) != 0:
        return False
    return value.value != 0


def _is_app_window(hwnd: int) -> bool:
    if not user32.IsWindowVisible(hwnd):
        return False
    if user32.GetWindow(hwnd, GW_OWNER):
        return False
    if _get_window_long(hwnd, GWL_EXSTYLE) & WS_EX_TOOLWINDOW:
        return False
    if user32.GetWindowTextLengthW(hwnd) == 0:
        return False
    if _class_name(hwnd) in IGNORED_CLASSES:
        return False
    return not _cloaked(hwnd)


def _all_windows() -> List[int]:
    found: List[int] = []

    def collect(hwnd: int, _lparam: int) -> bool:
        found.append(hwnd)
        return True

    callback = WNDENUMPROC(collect)
    user32.EnumWindows(callback, 0)
    return found


def _process_path(pid: int) -> str:
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return ""
    try:
        size = wintypes.DWORD(32768)
        buffer = ctypes.create_unicode_buffer(size.value)
        if kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
            return buffer.value
        return ""
    finally:
        kernel32.CloseHandle(handle)


def _created(handle: int) -> Optional[int]:
    times = [wintypes.FILETIME() for _ in range(4)]
    if not kernel32.GetProcessTimes(handle, *[ctypes.byref(t) for t in times]):
        return None
    return (times[0].dwHighDateTime << 32) | times[0].dwLowDateTime


def _process_created(pid: int) -> Optional[int]:
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return None
    try:
        return _created(handle)
    finally:
        kernel32.CloseHandle(handle)


def _alive(pid: int, created: Optional[int]) -> bool:
    handle = kernel32.OpenProcess(SYNCHRONIZE | PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return False
    try:
        if kernel32.WaitForSingleObject(handle, 0) == WAIT_OBJECT_0:
            return False
        return created is None or _created(handle) == created
    finally:
        kernel32.CloseHandle(handle)


_descriptions: Dict[str, str] = {}


def _file_description(path: str) -> str:
    """The friendly app name stored in the .exe, e.g. 'Google Chrome'."""
    if not path:
        return ""
    if path in _descriptions:
        return _descriptions[path]
    description = ""
    try:
        size = version_dll.GetFileVersionInfoSizeW(path, None)
        if size:
            data = ctypes.create_string_buffer(size)
            if version_dll.GetFileVersionInfoW(path, 0, size, data):
                pointer, length = ctypes.c_void_p(), wintypes.UINT()
                pairs = []
                if version_dll.VerQueryValueW(data, "\\VarFileInfo\\Translation", ctypes.byref(pointer), ctypes.byref(length)) and length.value >= 4:
                    words = ctypes.cast(pointer, ctypes.POINTER(wintypes.WORD * (length.value // 2))).contents
                    pairs = [(words[i], words[i + 1]) for i in range(0, len(words) - 1, 2)]
                for lang, codepage in pairs + [(0x0409, 0x04B0), (0x0409, 0x04E4), (0x0804, 0x04B0)]:
                    key = "\\StringFileInfo\\%04x%04x\\FileDescription" % (lang, codepage)
                    if version_dll.VerQueryValueW(data, key, ctypes.byref(pointer), ctypes.byref(length)) and length.value:
                        text = ctypes.wstring_at(pointer, length.value).rstrip("\x00").strip()
                        if text:
                            description = text
                            break
    except (OSError, ValueError):
        description = ""
    _descriptions[path] = description
    return description


def win_list(ctx: kit.Context) -> List[Dict[str, Any]]:
    apps: Dict[str, Dict[str, Any]] = {}
    folder_windows: List[int] = []
    explorer_pid = 0
    for hwnd in _all_windows():
        try:
            if not _is_app_window(hwnd):
                continue
            pid_value = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid_value))
            pid = int(pid_value.value)
            path = _process_path(pid)
            exe = os.path.basename(path).lower()
            if exe == "explorer.exe":
                if _class_name(hwnd) == "CabinetWClass":
                    folder_windows.append(hwnd)
                    explorer_pid = pid
                continue
            if exe == "applicationframehost.exe":  # Store apps share one host process
                title = clean_name(_window_text(hwnd))
                key = f"uwp:{hwnd}"
                apps[key] = {"id": f"uwp:{title}", "name": title, "exe": "", "path": "", "pid": pid, "kind": "uwp", "windows": [hwnd]}
                continue
            key = f"pid:{pid}"
            if key not in apps:
                name = clean_name(_file_description(path) or (os.path.splitext(exe)[0] if exe else "") or _window_text(hwnd))
                apps[key] = {
                    "id": exe or name, "name": name, "exe": exe, "path": path, "pid": pid,
                    "created": _process_created(pid), "kind": "app" if path else "unknown", "windows": [],
                }
            apps[key]["windows"].append(hwnd)
        except OSError:
            continue
    result = list(apps.values())
    if folder_windows:
        result.append({
            "id": "explorer-windows", "name": ctx.t(f"文件夹窗口 ×{len(folder_windows)}", f"Folder windows ×{len(folder_windows)}"),
            "exe": "explorer-windows", "path": "", "pid": explorer_pid, "kind": "folders", "windows": folder_windows,
        })
    return sorted(result, key=lambda a: a["name"].lower())


def win_request_quit(app: Dict[str, Any]) -> str:
    sent = False
    denied = False
    for hwnd in app["windows"]:
        if user32.PostMessageW(hwnd, WM_CLOSE, 0, 0):
            sent = True
        elif ctypes.get_last_error() == 5:  # access denied: the app runs as administrator
            denied = True
    if sent:
        return "sent"
    return "denied" if denied else "failed"


def win_state(app: Dict[str, Any], current: List[Dict[str, Any]]) -> str:
    """closed, hidden (still running without windows) or open."""
    if app["kind"] in ("uwp", "folders"):
        still = [h for h in app["windows"] if user32.IsWindow(h) and user32.IsWindowVisible(h)]
        return "open" if still else "closed"
    if not _alive(app["pid"], app.get("created")):
        return "closed"
    has_windows = any(c.get("pid") == app["pid"] and c["kind"] == "app" for c in current)
    return "open" if has_windows else "hidden"


# --------------------------------------------------------------------------- macOS

JXA_LIST = r"""
ObjC.import('AppKit');
var apps = $.NSWorkspace.sharedWorkspace.runningApplications;
var out = [];
for (var i = 0; i < apps.count; i++) {
  var a = apps.objectAtIndex(i);
  if (a.activationPolicy != 0) continue;
  var url = a.bundleURL;
  var launched = a.launchDate;
  out.push({
    name: ObjC.unwrap(a.localizedName) || '',
    bundle: ObjC.unwrap(a.bundleIdentifier) || '',
    pid: a.processIdentifier,
    path: (url && !url.isNil()) ? ObjC.unwrap(url.path) : '',
    launched: (launched && !launched.isNil()) ? launched.timeIntervalSince1970 : 0
  });
}
JSON.stringify(out);
"""

JXA_QUIT = r"""
ObjC.import('AppKit');
function run(argv) {
  var a = $.NSRunningApplication.runningApplicationWithProcessIdentifier(parseInt(argv[0], 10));
  if (!a || a.isNil()) return 'gone';
  if ((ObjC.unwrap(a.bundleIdentifier) || '') !== argv[1]) return 'changed';
  return a.terminate ? 'sent' : 'failed';
}
"""


def _osascript(script: str, *args: str) -> str:
    out = subprocess.run(["osascript", "-l", "JavaScript", "-e", script, *args], capture_output=True, text=True, timeout=15)
    if out.returncode != 0:
        raise OSError(out.stderr.strip() or "osascript failed")
    return out.stdout.strip()


def mac_list(ctx: kit.Context) -> List[Dict[str, Any]]:
    raw = json.loads(_osascript(JXA_LIST) or "[]")
    apps = []
    for item in raw:
        bundle = str(item.get("bundle") or "")
        apps.append({
            "id": bundle or item.get("name"), "name": clean_name(item.get("name") or bundle), "bundle": bundle.lower(),
            "bundle_id": bundle, "path": item.get("path") or "", "pid": int(item.get("pid") or 0),
            "launched": item.get("launched"), "kind": "app",
        })
    return sorted(apps, key=lambda a: a["name"].lower())


def mac_request_quit(app: Dict[str, Any]) -> str:
    try:
        return _osascript(JXA_QUIT, str(app["pid"]), app["bundle_id"]) or "failed"
    except (OSError, subprocess.SubprocessError):
        return "failed"


def mac_state(app: Dict[str, Any], current: List[Dict[str, Any]]) -> str:
    for other in current:
        if other["pid"] == app["pid"] and other["bundle"] == app["bundle"]:
            return "open"
    return "closed"


# --------------------------------------------------------------------------- shared flow

def list_apps(ctx: kit.Context) -> List[Dict[str, Any]]:
    if kit.IS_WINDOWS:
        return win_list(ctx)
    if kit.IS_MAC:
        return mac_list(ctx)
    raise RuntimeError(ctx.t("这个功能目前支持 Windows 和 macOS。", "This action supports Windows and macOS."))


def plan(ctx: kit.Context) -> Dict[str, List[Dict[str, Any]]]:
    tree = ancestors()
    close, keep = [], []
    for app in list_apps(ctx):
        reason = protection(ctx, app, tree)
        if reason is None and app.get("kind") == "unknown":
            reason = ctx.t("无法确认是什么程序（可能以管理员身份运行）", "could not identify it (it may run as administrator)")
        (keep if reason else close).append(dict(app, reason=reason) if reason else app)
    return {"close": close, "keep": keep}


def _public(app: Dict[str, Any]) -> Dict[str, Any]:
    return {k: app.get(k) for k in ("id", "name", "kind", "reason", "status") if app.get(k) is not None}


def _names(apps: List[Dict[str, Any]], limit: int = 4) -> str:
    names = [a["name"] for a in apps[:limit]]
    more = len(apps) - limit
    joined = "、".join(names) if any("一" <= ch <= "鿿" for ch in "".join(names)) else ", ".join(names)
    return joined + (f" +{more}" if more > 0 else "")


def session_path(ctx: kit.Context) -> Path:
    return ctx.state_dir / "last-session.json"


def reopenable(ctx: kit.Context) -> List[Dict[str, Any]]:
    session = kit.read_json(session_path(ctx), {}) or {}
    if session.get("reopened"):
        return []
    return [a for a in session.get("apps", []) if a.get("path")]


def op_status(ctx: kit.Context) -> Dict[str, Any]:
    steps = plan(ctx)
    count = len(steps["close"])
    again = reopenable(ctx)
    return {"ok": True, "message": ctx.t(f"{count} 个应用开着", f"{count} apps open"), "data": {
        "open": count, "kept": len(steps["keep"]), "reopenable": len(again),
        "available": {"run": count > 0, "reopen": bool(again), "preview": True},
    }}


def op_preview(ctx: kit.Context) -> Dict[str, Any]:
    steps = plan(ctx)
    close, keep = steps["close"], steps["keep"]
    if close:
        message = ctx.t(f"将请 {len(close)} 个应用退出：{_names(close)}", f"Will ask {len(close)} apps to quit: {_names(close)}")
    else:
        message = ctx.t("没有需要关闭的应用。", "No apps to close.")
    return {"ok": True, "message": message, "data": {
        "apps": [_public(a) for a in close], "kept": [_public(a) for a in keep], "count": len(close),
    }}


def op_run(ctx: kit.Context) -> Dict[str, Any]:
    with kit.file_lock(ctx.state_dir / "quit.lock"):
        steps = plan(ctx)
        targets = steps["close"]
        if not targets:
            return {"ok": True, "message": ctx.t("没有需要关闭的应用。", "No apps to close."), "data": {"closed": 0}}
        total = len(targets)
        request = win_request_quit if kit.IS_WINDOWS else mac_request_quit
        state_of = win_state if kit.IS_WINDOWS else mac_state
        for app in targets:
            app["request"] = request(app)
            if app["request"] in ("denied", "failed", "changed", "gone"):
                app["status"] = {"gone": "closed"}.get(app["request"], "skipped")
        pending = [a for a in targets if "status" not in a]
        finished = total - len(pending)
        deadline = time.time() + float(ctx.param("wait_seconds", 12) or 12)
        hidden_since: Dict[int, float] = {}
        while pending and time.time() < deadline:
            time.sleep(0.4)
            current = list_apps(ctx)
            for app in list(pending):
                state = state_of(app, current)
                if state == "hidden":
                    first = hidden_since.setdefault(id(app), time.time())
                    if time.time() - first < 3:
                        continue  # give it a moment to finish quitting
                if state in ("closed", "hidden"):
                    app["status"] = state
                    pending.remove(app)
                    finished += 1
                    kit.progress(finished / total, ctx.t(f"已关闭：{app['name']}", f"Closed: {app['name']}"), app=app["name"], status=state)
        for app in pending:
            app["status"] = "waiting"
            kit.progress(None, ctx.t(f"等你处理：{app['name']}", f"Waiting for you: {app['name']}"), app=app["name"], status="waiting")

        closed = [a for a in targets if a.get("status") in ("closed", "hidden")]
        waiting = [a for a in targets if a.get("status") == "waiting"]
        skipped = [a for a in targets if a.get("status") == "skipped"]
        kit.write_json(session_path(ctx), {
            "at": time.time(),
            "apps": [{"name": a["name"], "path": a.get("path"), "exe": a.get("exe"), "bundle": a.get("bundle_id")}
                     for a in closed if a.get("kind") == "app" and a.get("path")],
        })
        parts = [ctx.t(f"已关闭 {len(closed)} 个应用", f"Closed {len(closed)} apps")]
        if waiting:
            parts.append(ctx.t(f"{_names(waiting)} 有未保存的内容，等你处理", f"{_names(waiting)} need you (unsaved work?)"))
        if skipped:
            parts.append(ctx.t(f"{len(skipped)} 个无法关闭（可能需要管理员权限）", f"{len(skipped)} could not be asked (admin apps?)"))
        return {"ok": True, "message": ctx.t("；", "; ").join(parts), "data": {
            "closed": len(closed), "waiting": len(waiting), "skipped": len(skipped),
            "apps": [_public(a) for a in targets], "can_reopen": bool(closed),
        }}


def op_reopen(ctx: kit.Context) -> Dict[str, Any]:
    with kit.file_lock(ctx.state_dir / "quit.lock"):
        apps = reopenable(ctx)
        if not apps:
            return {"ok": True, "message": ctx.t("没有可以重新打开的应用。", "Nothing to reopen."), "data": {"opened": 0}}
        running = win_running_exes() if kit.IS_WINDOWS else {a["bundle"] for a in mac_list(ctx)}
        opened = 0
        for index, app in enumerate(apps, 1):
            try:
                if kit.IS_WINDOWS:
                    if (app.get("exe") or "").lower() in running or not os.path.exists(app["path"]):
                        continue
                    os.startfile(app["path"])  # type: ignore[attr-defined]
                else:
                    if (app.get("bundle") or "").lower() in running:
                        continue
                    target = ["-b", app["bundle"]] if app.get("bundle") else [app["path"]]
                    subprocess.run(["open", "-g", *target], check=True, timeout=20)
                opened += 1
                kit.progress(index / len(apps), ctx.t(f"已打开：{app['name']}", f"Opened: {app['name']}"), app=app["name"], status="opened")
            except (OSError, subprocess.SubprocessError):
                continue
        session = kit.read_json(session_path(ctx), {}) or {}
        session["reopened"] = time.time()
        kit.write_json(session_path(ctx), session)
        return {"ok": True, "message": ctx.t(f"已重新打开 {opened} 个应用", f"Reopened {opened} apps"), "data": {"opened": opened}}


if __name__ == "__main__":
    kit.main({"status": op_status, "preview": op_preview, "run": op_run, "reopen": op_reopen})
