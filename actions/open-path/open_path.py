"""open-path: open a folder, document or web address.

Programs and scripts are refused, so a theme button can never start software.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Dict

sys.path.insert(0, os.environ.get("ORBIT_RUNTIME") or str(Path(__file__).resolve().parents[2] / "runtime"))
from orbitcore import kit  # noqa: E402

BLOCKED_SUFFIXES = {
    ".exe", ".com", ".bat", ".cmd", ".ps1", ".psm1", ".vbs", ".vbe", ".js", ".jse", ".wsf", ".wsh", ".msi", ".msix",
    ".scr", ".pif", ".cpl", ".hta", ".lnk", ".reg", ".jar", ".app", ".command", ".sh", ".scpt", ".applescript",
    ".workflow", ".pkg", ".dmg", ".appimage", ".run", ".desktop",
}


def op_run(ctx: kit.Context) -> Dict[str, Any]:
    target = str(ctx.param("path", "{documents}") or "").strip()
    if not target:
        return {"ok": False, "message": ctx.t("没有指定要打开什么。", "Nothing to open."), "data": {}}
    if kit.is_url(target):
        if not target.lower().startswith("https://") and not target.lower().startswith("http://"):
            return {"ok": False, "message": ctx.t("只能打开网页地址。", "Only web addresses can be opened."), "data": {}}
        kit.open_path(target)
        return {"ok": True, "message": ctx.t("已在浏览器中打开", "Opened in the browser"), "data": {"url": target}}
    path = kit.expand_path(target)
    if path.suffix.lower() in BLOCKED_SUFFIXES:
        return {"ok": False, "message": ctx.t("为了安全，主题按钮不能启动程序或脚本。", "For safety, theme buttons cannot start programs or scripts."), "data": {}}
    if not path.exists():
        if ctx.param("create", False) and not path.suffix:
            path.mkdir(parents=True, exist_ok=True)
        else:
            return {"ok": False, "message": ctx.t(f"找不到：{path}", f"Not found: {path}"), "data": {}}
    kit.open_path(path)
    return {"ok": True, "message": ctx.t(f"已打开「{path.name or path}」", f"Opened '{path.name or path}'"), "data": {"path": str(path)}}


if __name__ == "__main__":
    kit.main({"run": op_run})
