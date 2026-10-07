"""Read-only system readings for desktop widgets: CPU, memory, disk, battery, uptime.

Every value is a fraction between 0 and 1 (or None when the machine cannot
tell, such as the battery of a desktop PC).
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import threading
import time
from typing import Any, Dict, Optional, Tuple

from . import env

_lock = threading.Lock()
_last_cpu: Optional[Tuple[float, float]] = None  # (busy ticks, total ticks)
_cache: Dict[str, Any] = {}
_cache_time = 0.0


def _clamp(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    return round(max(0.0, min(1.0, value)), 4)


# --------------------------------------------------------------------------- Windows

def _win_cpu_ticks() -> Optional[Tuple[float, float]]:
    import ctypes
    from ctypes import wintypes

    idle, kernel, user = wintypes.FILETIME(), wintypes.FILETIME(), wintypes.FILETIME()
    if not ctypes.windll.kernel32.GetSystemTimes(ctypes.byref(idle), ctypes.byref(kernel), ctypes.byref(user)):
        return None

    def value(ft: Any) -> int:
        return (ft.dwHighDateTime << 32) | ft.dwLowDateTime

    idle_v, kernel_v, user_v = value(idle), value(kernel), value(user)
    total = kernel_v + user_v  # kernel time includes idle time
    return float(total - idle_v), float(total)


def _win_memory() -> Optional[float]:
    import ctypes
    from ctypes import wintypes

    class MEMORYSTATUSEX(ctypes.Structure):
        _fields_ = [
            ("dwLength", wintypes.DWORD),
            ("dwMemoryLoad", wintypes.DWORD),
            ("ullTotalPhys", ctypes.c_ulonglong),
            ("ullAvailPhys", ctypes.c_ulonglong),
            ("ullTotalPageFile", ctypes.c_ulonglong),
            ("ullAvailPageFile", ctypes.c_ulonglong),
            ("ullTotalVirtual", ctypes.c_ulonglong),
            ("ullAvailVirtual", ctypes.c_ulonglong),
            ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
        ]

    status = MEMORYSTATUSEX()
    status.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        return None
    if not status.ullTotalPhys:
        return None
    return 1.0 - status.ullAvailPhys / status.ullTotalPhys


def _win_battery() -> Tuple[Optional[float], Optional[bool]]:
    import ctypes

    class SYSTEM_POWER_STATUS(ctypes.Structure):
        _fields_ = [
            ("ACLineStatus", ctypes.c_ubyte),
            ("BatteryFlag", ctypes.c_ubyte),
            ("BatteryLifePercent", ctypes.c_ubyte),
            ("SystemStatusFlag", ctypes.c_ubyte),
            ("BatteryLifeTime", ctypes.c_ulong),
            ("BatteryFullLifeTime", ctypes.c_ulong),
        ]

    status = SYSTEM_POWER_STATUS()
    if not ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(status)):
        return None, None
    if status.BatteryFlag & 128 or status.BatteryLifePercent == 255:  # no battery / unknown
        return None, None
    return status.BatteryLifePercent / 100.0, status.ACLineStatus == 1


def _win_uptime() -> Optional[float]:
    import ctypes

    ctypes.windll.kernel32.GetTickCount64.restype = ctypes.c_ulonglong
    return ctypes.windll.kernel32.GetTickCount64() / 1000.0


# --------------------------------------------------------------------------- macOS

def _mac_cpu_ticks() -> Optional[Tuple[float, float]]:
    import ctypes

    lib = ctypes.CDLL("/usr/lib/libSystem.dylib")
    lib.mach_host_self.restype = ctypes.c_uint
    ticks = (ctypes.c_uint * 4)()
    count = ctypes.c_uint(4)
    host_cpu_load_info = 3
    lib.host_statistics.argtypes = [ctypes.c_uint, ctypes.c_int, ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint)]
    if lib.host_statistics(lib.mach_host_self(), host_cpu_load_info, ctypes.byref(ticks), ctypes.byref(count)) != 0:
        return None
    user, system, idle, nice = (float(t) for t in ticks)
    total = user + system + idle + nice
    return total - idle, total


def _mac_memory() -> Optional[float]:
    try:
        out = subprocess.run(["vm_stat"], capture_output=True, text=True, timeout=3).stdout
        total = int(subprocess.run(["sysctl", "-n", "hw.memsize"], capture_output=True, text=True, timeout=3).stdout.strip())
    except (OSError, ValueError, subprocess.SubprocessError):
        return None
    page = re.search(r"page size of (\d+) bytes", out)
    page_size = int(page.group(1)) if page else 4096

    def pages(label: str) -> int:
        match = re.search(r"%s:\s+(\d+)" % re.escape(label), out)
        return int(match.group(1)) if match else 0

    used = (pages("Pages active") + pages("Pages wired down") + pages("Pages occupied by compressor")) * page_size
    return used / total if total else None


def _mac_battery() -> Tuple[Optional[float], Optional[bool]]:
    try:
        out = subprocess.run(["pmset", "-g", "batt"], capture_output=True, text=True, timeout=3).stdout
    except (OSError, subprocess.SubprocessError):
        return None, None
    match = re.search(r"(\d+)%;\s*([a-zA-Z ]+);", out)
    if not match:
        return None, None
    state = match.group(2).strip().lower()
    return int(match.group(1)) / 100.0, ("AC Power" in out) or state in ("charging", "charged", "finishing charge")


def _mac_uptime() -> Optional[float]:
    try:
        out = subprocess.run(["sysctl", "-n", "kern.boottime"], capture_output=True, text=True, timeout=3).stdout
        match = re.search(r"sec = (\d+)", out)
        return time.time() - int(match.group(1)) if match else None
    except (OSError, subprocess.SubprocessError):
        return None


# --------------------------------------------------------------------------- Linux

def _linux_cpu_ticks() -> Optional[Tuple[float, float]]:
    try:
        with open("/proc/stat", encoding="ascii") as handle:
            fields = [float(x) for x in handle.readline().split()[1:]]
    except (OSError, ValueError):
        return None
    idle = fields[3] + (fields[4] if len(fields) > 4 else 0)
    total = sum(fields)
    return total - idle, total


def _linux_memory() -> Optional[float]:
    try:
        info = {}
        with open("/proc/meminfo", encoding="ascii") as handle:
            for line in handle:
                key, _, rest = line.partition(":")
                info[key] = float(rest.split()[0])
        return 1.0 - info["MemAvailable"] / info["MemTotal"]
    except (OSError, KeyError, ValueError, ZeroDivisionError):
        return None


def _linux_battery() -> Tuple[Optional[float], Optional[bool]]:
    base = "/sys/class/power_supply"
    try:
        for name in sorted(os.listdir(base)):
            if not name.startswith("BAT"):
                continue
            with open(os.path.join(base, name, "capacity"), encoding="ascii") as handle:
                level = int(handle.read().strip()) / 100.0
            with open(os.path.join(base, name, "status"), encoding="ascii") as handle:
                charging = handle.read().strip().lower() in ("charging", "full")
            return level, charging
    except (OSError, ValueError):
        pass
    return None, None


def _linux_uptime() -> Optional[float]:
    try:
        with open("/proc/uptime", encoding="ascii") as handle:
            return float(handle.read().split()[0])
    except (OSError, ValueError):
        return None


# --------------------------------------------------------------------------- public

def _cpu_ticks() -> Optional[Tuple[float, float]]:
    try:
        if env.IS_WINDOWS:
            return _win_cpu_ticks()
        if env.IS_MAC:
            return _mac_cpu_ticks()
        return _linux_cpu_ticks()
    except Exception:
        return None


def _cpu_fraction() -> Optional[float]:
    global _last_cpu
    now = _cpu_ticks()
    if now is None:
        return None
    previous = _last_cpu
    if previous is None:
        time.sleep(0.25)
        previous, now = now, _cpu_ticks()
        if now is None:
            return None
    _last_cpu = now
    busy = now[0] - previous[0]
    total = now[1] - previous[1]
    return busy / total if total > 0 else None


def _disk_fraction() -> Optional[float]:
    root = os.environ.get("SystemDrive", "C:") + "\\" if env.IS_WINDOWS else "/"
    try:
        usage = shutil.disk_usage(root)
        return usage.used / usage.total if usage.total else None
    except OSError:
        return None


def readings(max_age: float = 2.0) -> Dict[str, Any]:
    """Current readings, cached for a couple of seconds so many widgets can poll cheaply."""
    global _cache, _cache_time
    with _lock:
        if _cache and time.time() - _cache_time < max_age:
            return dict(_cache)
        try:
            if env.IS_WINDOWS:
                memory, battery, uptime = _win_memory(), _win_battery(), _win_uptime()
            elif env.IS_MAC:
                memory, battery, uptime = _mac_memory(), _mac_battery(), _mac_uptime()
            else:
                memory, battery, uptime = _linux_memory(), _linux_battery(), _linux_uptime()
        except Exception:
            memory, battery, uptime = None, (None, None), None
        result = {
            "cpu": _clamp(_cpu_fraction()),
            "memory": _clamp(memory),
            "disk": _clamp(_disk_fraction()),
            "battery": _clamp(battery[0]),
            "charging": battery[1],
            "uptime": round(uptime) if uptime else None,
            "platform": env.PLATFORM,
            "time": time.time(),
        }
        _cache, _cache_time = result, time.time()
        return dict(result)
