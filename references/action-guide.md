# Writing a new action

An action is a folder with a manifest and a program. The helper starts the program for every call:

```
~/OrbitDesktop/actions/<id>/
  action.json
  action.py          (or any program: a PowerShell or shell script, an executable)
```

Create one from the template with `orbit.py new-action <id>`, then:

```
orbit.py validate-action <id>
orbit.py run <id> preview --param folder=downloads   # read-only operations need no flag
orbit.py run <id> run --yes               # only with the user's explicit OK, on their real machine
```

## The contract

- The program is started as `<command…> <operation>` with the working directory set to the action folder.
- The request arrives as JSON on **stdin**:
  `{"action", "op", "params", "lang", "platform", "workspace", "state_dir"}`. `params` already merges the
  manifest defaults, the user's config and what the theme button passed.
- Progress goes to **stderr** as JSON lines: `{"orbit": "progress", "progress": 0.4, "message": "…", …}`.
  Extra fields (for example `item`, `status`) reach the theme in its `action` events.
- The result is **one JSON line on stdout**: `{"ok": true, "message": "…", "data": {…}}`.
  `message` is shown on the desktop, in the user's language, short and concrete.
- Other stderr lines go to the log. The default timeout is 90 s (`timeout` in the manifest).
- Store anything you need to remember (journals, last session) in `state_dir`.

With Python, `orbitcore.kit` does the plumbing (the runtime folder is on `PYTHONPATH`):

```python
import os, sys
from pathlib import Path
sys.path.insert(0, os.environ.get("ORBIT_RUNTIME") or str(Path(__file__).resolve().parents[2] / "runtime"))
from orbitcore import kit

def preview(ctx):
    return {"ok": True, "message": ctx.t("将处理 3 项", "Would handle 3 items"), "data": {"count": 3}}

def run(ctx):
    for i, item in enumerate(items, 1):
        ...                                                   # do the work, journal it first
        kit.progress(i / len(items), ctx.t(f"完成：{item}", f"Done: {item}"), item=item, status="done")
    return {"ok": True, "message": ctx.t("已完成", "Done"), "data": {"done": len(items)}}

kit.main({"preview": preview, "run": run})
```

`ctx.params`, `ctx.param(name, default)`, `ctx.t(zh, en)`, `ctx.lang`, `ctx.state_dir`, and helpers
`kit.known_folder("desktop")` (OneDrive-aware on Windows), `kit.expand_path("{documents}/x")`,
`kit.open_path(p)`, `kit.read_json`, `kit.write_json` (atomic), `kit.append_jsonl` (fsync'd journal),
`kit.read_jsonl`, `kit.file_lock(path)` (raises `kit.Busy`), `kit.IS_WINDOWS`, `kit.IS_MAC`.

## action.json

```json
{
  "id": "clean-screenshots",
  "name": { "en": "File screenshots", "zh-CN": "整理截图" },
  "description": { "en": "…", "zh-CN": "…" },
  "version": "1.0.0",
  "platforms": ["windows", "macos"],
  "command": { "default": ["{python}", "action.py"],
               "windows": ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "action.ps1"] },
  "timeout": 90,
  "operations": {
    "status":  { "effect": "read" },
    "preview": { "effect": "read" },
    "run":     { "effect": "files", "undo": "undo", "label": { "en": "File", "zh-CN": "整理" } },
    "undo":    { "effect": "files" }
  },
  "params": {
    "folder": { "type": "string", "default": "{desktop}", "description": "…" }
  }
}
```

`{python}` becomes the helper's own Python. `effect` is one of `read`, `files`, `apps`, `open`,
`network`, `system`; the SDK asks for confirmation before `apps` and `system`, and the CLI refuses
`files`, `apps` and `system` without `--yes`.

## Safety rules (required)

1. **Offer `preview`** for anything that changes state, and a `status` with
   `{"available": {"run": bool, "undo": bool}}` so themes can show or hide buttons.
2. **Never delete.** Move to a folder the user can see, or to the system trash, and journal it first.
3. **Make it undoable** where possible: write an intent line before each change and a done line after;
   `undo` replays the journal backwards and tolerates missing or renamed files.
4. **Never force-kill** processes and never answer an app's "save changes?" prompt.
5. **Stay inside the user's space.** Refuse system folders, other users' folders and the whole home folder.
6. **No system settings, no privilege prompts, no network uploads** unless that is the action's stated purpose and the user asked for it.
7. **Be quick and quiet:** finish within the timeout, never open windows unless the operation is `open`,
   and keep `status` cheap because themes poll it every minute.
8. **Say what happened** in the user's language, including what was skipped and why.

## Cross-platform notes

- Use `kit.known_folder()` rather than `~/Desktop`: Windows often redirects Desktop and Documents to OneDrive.
- Windows APIs are reachable from Python through `ctypes` (see `actions/quit-apps/quit_apps.py`);
  macOS app automation through `osascript -l JavaScript` with the ObjC bridge (same file).
- On Windows `os.rename` fails when a file is open in another program; treat that as "skipped, in use".
- Paths may contain spaces and Chinese characters; never build shell strings, pass argument lists.
- Child processes on Windows should use `creationflags=0x08000000` (no console window).
