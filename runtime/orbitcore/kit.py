"""Helpers for action scripts.

An action is a small program the runtime starts for every call:

    python action.py <operation>        (request JSON arrives on stdin)

It reports progress as JSON lines on stderr and prints exactly one JSON
result on stdout. This module hides that protocol:

    from orbitcore import kit

    def preview(ctx):
        return {"ok": True, "message": ctx.t("没有要处理的内容", "Nothing to do"), "data": {}}

    kit.main({"preview": preview})
"""
from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from . import env
from .env import (  # re-exported for action authors
    IS_LINUX,
    IS_MAC,
    IS_WINDOWS,
    PLATFORM,
    Busy,
    append_jsonl,
    expand_path,
    file_lock,
    is_url,
    known_folder,
    open_path,
    read_json,
    read_jsonl,
    write_json,
)

__all__ = [
    "Context", "context", "progress", "finish", "fail", "main",
    "IS_WINDOWS", "IS_MAC", "IS_LINUX", "PLATFORM", "Busy",
    "append_jsonl", "read_jsonl", "expand_path", "file_lock", "is_url", "known_folder",
    "open_path", "read_json", "write_json",
]


class Context:
    """Everything an action needs to know about the current call."""

    def __init__(self, data: Dict[str, Any]):
        self.raw = data
        self.action: str = data.get("action") or Path(sys.argv[0]).resolve().parent.name
        self.op: str = data.get("op") or "run"
        self.params: Dict[str, Any] = data.get("params") or {}
        self.lang: str = data.get("lang") or env.detect_language()
        self.platform: str = data.get("platform") or env.PLATFORM
        self.workspace = Path(data.get("workspace") or env.workspace_dir())
        self.state_dir = Path(data.get("state_dir") or (self.workspace / "state" / self.action))
        self.state_dir.mkdir(parents=True, exist_ok=True)

    @property
    def zh(self) -> bool:
        return self.lang.lower().startswith("zh")

    def t(self, zh: str, en: str) -> str:
        """Choose the Chinese or English text for the user's language."""
        return zh if self.zh else en

    def param(self, name: str, default: Any = None) -> Any:
        value = self.params.get(name, default)
        return default if value is None else value


def context() -> Context:
    env.ensure_utf8_stdio()
    raw = ""
    try:
        if sys.stdin is not None and not sys.stdin.isatty():
            raw = sys.stdin.read()
    except (OSError, ValueError):
        raw = ""
    try:
        data = json.loads(raw) if raw.strip() else {}
    except ValueError:
        data = {}
    if not isinstance(data, dict):
        data = {}
    if len(sys.argv) > 1 and not data.get("op"):
        data["op"] = sys.argv[1]
    return Context(data)


def progress(fraction: Optional[float] = None, message: Optional[str] = None, **data: Any) -> None:
    """Tell the desktop how far along we are. Themes animate with these events."""
    payload: Dict[str, Any] = {"orbit": "progress"}
    if fraction is not None:
        payload["progress"] = max(0.0, min(1.0, float(fraction)))
    if message:
        payload["message"] = message
    payload.update(data)
    if sys.stderr is not None:
        sys.stderr.write(json.dumps(payload, ensure_ascii=False) + "\n")
        sys.stderr.flush()


def finish(ok: bool = True, message: str = "", data: Optional[Dict[str, Any]] = None, **extra: Any) -> None:
    result: Dict[str, Any] = {"ok": bool(ok), "message": message, "data": data or {}}
    result.update(extra)
    sys.stdout.write(json.dumps(result, ensure_ascii=False) + "\n")
    sys.stdout.flush()
    raise SystemExit(0)


def fail(message: str, **extra: Any) -> None:
    finish(False, message, **extra)


Handler = Callable[[Context], Dict[str, Any]]


def main(handlers: Dict[str, Handler]) -> None:
    """Dispatch the requested operation to a handler and print its result."""
    ctx = context()
    handler = handlers.get(ctx.op)
    if handler is None:
        fail(ctx.t("不支持的操作：", "Unsupported operation: ") + ctx.op)
    try:
        result = handler(ctx)
    except Busy:
        fail(ctx.t("上一次操作还没结束，请稍后再试。", "The previous run has not finished yet. Try again shortly."))
    except Exception as exc:  # report, never crash silently
        if sys.stderr is not None:
            traceback.print_exc()
        fail(ctx.t("出错了：", "Something went wrong: ") + str(exc)[:300])
    if not isinstance(result, dict):
        result = {"ok": True, "message": "", "data": {}}
    finish(result.get("ok", True), result.get("message", ""), result.get("data"))
