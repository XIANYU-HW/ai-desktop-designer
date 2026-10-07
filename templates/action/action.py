"""my-action: describe what it does and the safety rules it keeps.

Contract: started as `action.py <operation>`, request JSON on stdin, progress as JSON lines on
stderr (kit.progress), exactly one JSON result on stdout (returned from the handler).
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, os.environ.get("ORBIT_RUNTIME") or str(Path(__file__).resolve().parents[2] / "runtime"))
from orbitcore import kit  # noqa: E402


def find_work(ctx: kit.Context) -> List[Path]:
    folder = kit.expand_path(ctx.param("folder", "{desktop}"))
    # Decide what this action would act on. Read only: no changes here.
    return []


def op_status(ctx: kit.Context) -> Dict[str, Any]:
    work = find_work(ctx)
    journal = kit.read_jsonl(ctx.state_dir / "journal.jsonl")
    can_undo = any(r.get("type") == "done" for r in journal) and not any(r.get("type") == "undone" for r in journal[-1:])
    return {"ok": True, "message": "", "data": {"pending": len(work), "available": {"run": bool(work), "undo": can_undo}}}


def op_preview(ctx: kit.Context) -> Dict[str, Any]:
    work = find_work(ctx)
    return {"ok": True, "message": ctx.t(f"将处理 {len(work)} 项", f"Would handle {len(work)} items"),
            "data": {"items": [p.name for p in work]}}


def op_run(ctx: kit.Context) -> Dict[str, Any]:
    with kit.file_lock(ctx.state_dir / "run.lock"):
        work = find_work(ctx)
        journal = ctx.state_dir / "journal.jsonl"
        done = 0
        for index, path in enumerate(work, 1):
            kit.append_jsonl(journal, {"type": "intent", "path": str(path), "at": time.time()})
            # ... make the change here; never delete, never force anything ...
            kit.append_jsonl(journal, {"type": "done", "path": str(path)})
            done += 1
            kit.progress(index / len(work), ctx.t(f"完成：{path.name}", f"Done: {path.name}"), item=path.name, status="done")
        return {"ok": True, "message": ctx.t(f"已完成 {done} 项", f"Handled {done} items"), "data": {"done": done}}


def op_undo(ctx: kit.Context) -> Dict[str, Any]:
    with kit.file_lock(ctx.state_dir / "run.lock"):
        journal = ctx.state_dir / "journal.jsonl"
        records = kit.read_jsonl(journal)
        # ... replay "done" records backwards and reverse each change ...
        kit.append_jsonl(journal, {"type": "undone", "at": time.time()})
        return {"ok": True, "message": ctx.t("已撤销", "Undone"), "data": {"undone": sum(r.get("type") == "done" for r in records)}}


if __name__ == "__main__":
    kit.main({"status": op_status, "preview": op_preview, "run": op_run, "undo": op_undo})
