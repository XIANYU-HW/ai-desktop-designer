"""Start an action as a child process and collect its progress and result."""
from __future__ import annotations

import json
import logging
import os
import subprocess
import threading
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from . import env
from .registry import action_supported

log = logging.getLogger("orbit.runner")

ProgressCallback = Callable[[Dict[str, Any]], None]


def resolve_command(manifest: Dict[str, Any]) -> List[str]:
    command = manifest.get("command") or {}
    if isinstance(command, list):
        chosen = command
    else:
        chosen = command.get(env.PLATFORM) or command.get("default") or []
    console_python, _ = env.python_executables()
    resolved = []
    for part in chosen:
        part = str(part)
        if part == "{python}":
            resolved.append(str(console_python))
        else:
            resolved.append(part.replace("{action_dir}", manifest["_dir"]))
    return resolved


def merge_params(manifest: Dict[str, Any], configured: Dict[str, Any], requested: Dict[str, Any]) -> Dict[str, Any]:
    """Defaults from action.json, then the user's config, then what the theme asked for.

    A theme may only set parameters the action declares, so a theme cannot
    smuggle in options the action author never planned for.
    """
    declared = manifest.get("params") or {}
    params: Dict[str, Any] = {}
    for key, spec in declared.items():
        if isinstance(spec, dict) and "default" in spec:
            params[key] = spec["default"]
    params.update(configured or {})
    for key, value in (requested or {}).items():
        if key in declared:
            params[key] = value
    return params


def _parse_result(stdout: str) -> Optional[Dict[str, Any]]:
    for line in reversed(stdout.strip().splitlines()):
        line = line.strip()
        if line.startswith("{"):
            try:
                value = json.loads(line)
            except ValueError:
                continue
            if isinstance(value, dict):
                return value
    return None


def run_action(
    manifest: Dict[str, Any],
    op: str,
    params: Dict[str, Any],
    *,
    lang: str,
    workspace_root: Path,
    on_progress: Optional[ProgressCallback] = None,
    timeout: Optional[float] = None,
) -> Dict[str, Any]:
    zh = lang.lower().startswith("zh")
    say = (lambda a, b: a if zh else b)
    operations = manifest.get("operations") or {}
    if op not in operations:
        return {"ok": False, "message": say(f"这个功能没有“{op}”操作。", f"This action has no '{op}' operation."), "data": {}, "error": "unknown-op"}
    if not action_supported(manifest):
        return {"ok": False, "message": say("这个功能还不支持当前系统。", "This action does not support this system yet."), "data": {}, "error": "unsupported-platform"}
    command = resolve_command(manifest)
    if not command:
        return {"ok": False, "message": say("功能缺少启动命令。", "The action has no command."), "data": {}, "error": "no-command"}

    action_id = manifest["id"]
    state_dir = Path(workspace_root) / "state" / action_id
    state_dir.mkdir(parents=True, exist_ok=True)
    request = {
        "action": action_id,
        "op": op,
        "params": params,
        "lang": lang,
        "platform": env.PLATFORM,
        "workspace": str(workspace_root),
        "state_dir": str(state_dir),
    }
    child_env = dict(os.environ)
    child_env["PYTHONPATH"] = os.pathsep.join(filter(None, [str(env.RUNTIME_DIR), child_env.get("PYTHONPATH", "")]))
    child_env["PYTHONIOENCODING"] = "utf-8"
    child_env["PYTHONUTF8"] = "1"
    child_env["ORBIT_WORKSPACE"] = str(workspace_root)
    child_env["ORBIT_LANG"] = lang
    child_env["ORBIT_ACTION"] = action_id
    child_env["ORBIT_RUNTIME"] = str(env.RUNTIME_DIR)

    limit = float(timeout or manifest.get("timeout") or 90)
    started = time.time()
    kwargs: Dict[str, Any] = {}
    if env.IS_WINDOWS:
        kwargs["creationflags"] = env.CREATE_NO_WINDOW
    try:
        proc = subprocess.Popen(
            command + [op],
            cwd=manifest["_dir"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=child_env,
            **kwargs,
        )
    except OSError as exc:
        log.warning("could not start %s: %s", action_id, exc)
        return {"ok": False, "message": say("功能无法启动：", "The action could not start: ") + str(exc), "data": {}, "error": "start-failed"}

    stdout_chunks: List[bytes] = []
    stderr_lines: List[str] = []

    def read_stdout() -> None:
        assert proc.stdout is not None
        stdout_chunks.append(proc.stdout.read())

    def read_stderr() -> None:
        assert proc.stderr is not None
        for raw in iter(proc.stderr.readline, b""):
            line = raw.decode("utf-8", errors="replace").rstrip()
            if not line:
                continue
            if line.startswith("{"):
                try:
                    event = json.loads(line)
                except ValueError:
                    event = None
                if isinstance(event, dict) and event.get("orbit") == "progress":
                    event.pop("orbit", None)
                    if on_progress:
                        try:
                            on_progress(event)
                        except Exception:  # a broken listener must not stop the action
                            log.exception("progress listener failed")
                    continue
            stderr_lines.append(line)

    readers = [threading.Thread(target=read_stdout, daemon=True), threading.Thread(target=read_stderr, daemon=True)]
    for reader in readers:
        reader.start()
    try:
        assert proc.stdin is not None
        proc.stdin.write(json.dumps(request, ensure_ascii=False).encode("utf-8"))
        proc.stdin.close()
    except OSError:
        pass

    timed_out = False
    try:
        proc.wait(timeout=limit)
    except subprocess.TimeoutExpired:
        timed_out = True
        proc.kill()  # our own child process, never a user application
        proc.wait()
    for reader in readers:
        reader.join(timeout=5)
    for stream in (proc.stdout, proc.stderr):
        try:
            if stream is not None:
                stream.close()
        except OSError:
            pass

    stdout = b"".join(stdout_chunks).decode("utf-8", errors="replace")
    if stderr_lines:
        log.info("[%s %s] %s", action_id, op, "\n".join(stderr_lines[-40:]))
    if timed_out:
        return {"ok": False, "message": say("功能运行超时，已停止。", "The action took too long and was stopped."), "data": {}, "error": "timeout"}
    result = _parse_result(stdout)
    if result is None:
        detail = stderr_lines[-1] if stderr_lines else ""
        return {"ok": False, "message": say("功能没有返回结果。", "The action returned no result.") + (" " + detail if detail else ""), "data": {}, "error": "no-result"}
    result.setdefault("ok", proc.returncode == 0)
    result.setdefault("message", "")
    if not isinstance(result.get("data"), dict):
        result["data"] = {}
    result["elapsed"] = round(time.time() - started, 3)
    return result
