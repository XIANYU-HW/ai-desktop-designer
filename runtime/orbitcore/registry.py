"""Find themes and actions, describe them, and check that a theme is well formed."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from . import env

ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{1,47}$")
EFFECTS = ("read", "files", "apps", "open", "network", "system")
CONFIRM_EFFECTS = ("apps", "system")


def _scan(folders: List[Tuple[Path, str]], manifest_name: str) -> Dict[str, Dict[str, Any]]:
    found: Dict[str, Dict[str, Any]] = {}
    for folder, source in folders:
        if not folder.is_dir():
            continue
        for child in sorted(folder.iterdir()):
            manifest_path = child / manifest_name
            if not child.is_dir() or child.name.startswith(".") or not manifest_path.is_file():
                continue
            data = env.read_json(manifest_path)
            if not isinstance(data, dict):
                continue
            item_id = str(data.get("id") or child.name)
            data["id"] = item_id
            data["_dir"] = str(child)
            data["_source"] = source
            found[item_id] = data  # later folders (the workspace) override bundled ones
    return found


def load_actions(workspace_root: Path) -> Dict[str, Dict[str, Any]]:
    return _scan([(env.BUILTIN_ACTIONS, "builtin"), (Path(workspace_root) / "actions", "workspace")], "action.json")


def load_themes(workspace_root: Path) -> Dict[str, Dict[str, Any]]:
    return _scan([(env.BUILTIN_THEMES, "builtin"), (Path(workspace_root) / "themes", "workspace")], "theme.json")


def action_supported(manifest: Dict[str, Any]) -> bool:
    platforms = manifest.get("platforms")
    return not platforms or env.PLATFORM in platforms


def summarize_action(manifest: Dict[str, Any], lang: str) -> Dict[str, Any]:
    operations = {}
    for op, spec in (manifest.get("operations") or {}).items():
        spec = spec if isinstance(spec, dict) else {}
        operations[op] = {
            "effect": spec.get("effect", "read"),
            "label": env.pick(spec.get("label"), lang),
            "description": env.pick(spec.get("description"), lang),
            "undo": spec.get("undo"),
        }
    return {
        "id": manifest["id"],
        "name": env.pick(manifest.get("name"), lang, manifest["id"]),
        "description": env.pick(manifest.get("description"), lang),
        "platforms": manifest.get("platforms") or [],
        "supported": action_supported(manifest),
        "source": manifest.get("_source"),
        "operations": operations,
        "params": {
            key: {k: v for k, v in (spec or {}).items() if k in ("type", "default", "description", "enum")}
            for key, spec in (manifest.get("params") or {}).items()
        },
    }


def summarize_theme(theme: Dict[str, Any], lang: str) -> Dict[str, Any]:
    folder = Path(theme["_dir"])
    return {
        "id": theme["id"],
        "name": env.pick(theme.get("name"), lang, theme["id"]),
        "description": env.pick(theme.get("description"), lang),
        "author": theme.get("author") or "",
        "version": theme.get("version") or "",
        "source": theme.get("_source"),
        "palette": theme.get("palette") or {},
        "has_preview": (folder / "preview.png").exists(),
        "uses": theme.get("uses") or {},
    }


# ---------------------------------------------------------------------------
# Theme validation

_ACTION_REFS = [
    re.compile(r"data-orbit-action\s*=\s*[\"']([a-z0-9-]+)[\"']"),
    re.compile(r"Orbit\.run\(\s*[\"']([a-z0-9-]+)[\"']"),
]
_SDK_REF = re.compile(r"<script[^>]+src\s*=\s*[\"'][^\"']*sdk/orbit\.js[\"']", re.I)
_EXTERNAL_SCRIPT = re.compile(r"<script[^>]+src\s*=\s*[\"']https?://", re.I)
TEXT_SUFFIXES = {".html", ".htm", ".js", ".mjs", ".css", ".json", ".svg"}


def validate_theme(folder: Path, actions: Optional[Dict[str, Dict[str, Any]]] = None) -> List[Tuple[str, str]]:
    """Return a list of (level, message). Level is 'error', 'warning' or 'ok'."""
    folder = Path(folder)
    report: List[Tuple[str, str]] = []
    manifest_path = folder / "theme.json"
    theme = env.read_json(manifest_path)
    if not isinstance(theme, dict):
        return [("error", f"{manifest_path} is missing or is not valid JSON")]

    theme_id = str(theme.get("id") or "")
    if not ID_PATTERN.match(theme_id):
        report.append(("error", "theme.json 'id' must be 2-48 characters of a-z, 0-9 and '-'"))
    elif theme_id != folder.name:
        report.append(("warning", f"theme id '{theme_id}' differs from its folder name '{folder.name}'"))
    if not theme.get("name"):
        report.append(("error", "theme.json needs a 'name'"))
    if not theme.get("concept"):
        report.append(("warning", "theme.json has no 'concept' (the world and the metaphor for each function)"))

    entry = folder / str(theme.get("entry") or "index.html")
    if not entry.is_file():
        report.append(("error", f"entry page {entry.name} does not exist"))
        return report

    texts: Dict[str, str] = {}
    total_size = 0
    for path in folder.rglob("*"):
        if not path.is_file():
            continue
        total_size += path.stat().st_size
        if path.suffix.lower() in TEXT_SUFFIXES:
            try:
                texts[str(path.relative_to(folder))] = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                pass

    html = texts.get(str(entry.relative_to(folder)), "")
    if not _SDK_REF.search(html):
        report.append(("error", 'entry page must load the SDK: <script src="../../sdk/orbit.js"></script>'))
    if _EXTERNAL_SCRIPT.search(html):
        report.append(("warning", "entry page loads scripts from the internet; the desktop will break offline"))
    if any("fonts.googleapis.com" in text or "fonts.gstatic.com" in text for name, text in texts.items() if "fonts" not in Path(name).parts):
        report.append(("warning", "fonts load from Google at run time; offline or where Google is blocked the desktop falls back to "
                                  "system fonts and looks cheap. Bundle them: orbit.py fonts <id> --family \"…\""))

    joined = "\n".join(texts.values())
    if "Orbit.loop" not in joined and "prefers-reduced-motion" not in joined:
        report.append(("warning", "no Orbit.loop() or prefers-reduced-motion handling found; animations should pause and respect reduced motion"))
    if "requestAnimationFrame" in joined and "Orbit.loop" not in joined:
        report.append(("warning", "uses requestAnimationFrame directly; prefer Orbit.loop() so the scene pauses with the wallpaper host"))

    referenced = set()
    for pattern in _ACTION_REFS:
        referenced.update(pattern.findall(joined))
    declared = set(((theme.get("uses") or {}).get("actions")) or [])
    if actions is not None:
        for action_id in sorted(referenced | declared):
            if action_id not in actions:
                report.append(("error", f"theme uses action '{action_id}', which is not installed"))
            elif not action_supported(actions[action_id]):
                report.append(("warning", f"action '{action_id}' does not support {env.PLATFORM}"))
    missing_decl = referenced - declared
    if missing_decl:
        report.append(("warning", "theme.json 'uses.actions' should list: " + ", ".join(sorted(missing_decl))))

    if total_size > 40 * 1024 * 1024:
        report.append(("warning", f"theme is {total_size // (1024 * 1024)} MB; keep it under 40 MB"))
    if not (folder / "preview.png").exists():
        report.append(("warning", "no preview.png yet; create one with: orbit.py snapshot " + (theme_id or folder.name)))

    if not any(level == "error" for level, _ in report):
        report.insert(0, ("ok", f"theme '{theme_id}' is valid"))
    return report


def validate_action(folder: Path) -> List[Tuple[str, str]]:
    folder = Path(folder)
    manifest = env.read_json(folder / "action.json")
    if not isinstance(manifest, dict):
        return [("error", "action.json is missing or is not valid JSON")]
    report: List[Tuple[str, str]] = []
    action_id = str(manifest.get("id") or "")
    if not ID_PATTERN.match(action_id):
        report.append(("error", "action.json 'id' must be 2-48 characters of a-z, 0-9 and '-'"))
    operations = manifest.get("operations")
    if not isinstance(operations, dict) or not operations:
        report.append(("error", "action.json needs 'operations'"))
        operations = {}
    for op, spec in operations.items():
        effect = (spec or {}).get("effect", "read")
        if effect not in EFFECTS:
            report.append(("error", f"operation '{op}' has unknown effect '{effect}' (use one of {', '.join(EFFECTS)})"))
        if effect in ("files", "apps", "system") and "preview" not in operations:
            report.append(("warning", f"operation '{op}' changes things; add a read-only 'preview' operation"))
    command = manifest.get("command")
    if not command:
        report.append(("error", "action.json needs 'command', e.g. {\"default\": [\"{python}\", \"action.py\"]}"))
    if not report:
        report.append(("ok", f"action '{action_id}' looks valid"))
    return report
