"""Workspace layout and the user's config.json."""
from __future__ import annotations

import copy
import secrets
from pathlib import Path
from typing import Any, Dict, Optional

from . import env

DEFAULT_PORT = 47321

DEFAULT_CONFIG: Dict[str, Any] = {
    "version": 1,
    "port": DEFAULT_PORT,
    "language": None,          # "zh-CN" or "en"; detected on first run
    "active_theme": None,      # theme id
    "location": None,          # {"name", "latitude", "longitude", "timezone"}
    "units": "metric",         # "metric" or "imperial"
    "actions": {},             # per-action overrides: {"tidy-files": {"params": {...}}}
}

WORKSPACE_README = """Orbit Desktop workspace / Orbit Desktop 工作区

config.json   your settings (port, language, active theme, location, action options)
themes/       your own themes; a theme here overrides a bundled theme with the same id
actions/      your own functions (actions); same rule as themes
state/        what actions remember, such as the undo journal of tidy-files
logs/         helper and action logs

config.json   设置（端口、语言、当前主题、城市、各功能的选项）
themes/       你自己的主题；与内置主题同名时以这里为准
actions/      你自己的功能（动作）；规则同上
state/        功能的记录，例如一键收纳的撤销日志
logs/         运行日志
"""


class Workspace:
    def __init__(self, root: Optional[Path] = None):
        self.root = Path(root) if root else env.workspace_dir()

    @property
    def config_path(self) -> Path:
        return self.root / "config.json"

    @property
    def themes_dir(self) -> Path:
        return self.root / "themes"

    @property
    def actions_dir(self) -> Path:
        return self.root / "actions"

    @property
    def state_dir(self) -> Path:
        return self.root / "state"

    @property
    def logs_dir(self) -> Path:
        return self.root / "logs"

    @property
    def server_file(self) -> Path:
        return self.state_dir / "server.json"

    def exists(self) -> bool:
        return self.config_path.exists()

    def ensure(self, language: Optional[str] = None, theme: Optional[str] = None) -> Dict[str, Any]:
        """Create the workspace if needed and return the config."""
        for folder in (self.root, self.themes_dir, self.actions_dir, self.state_dir, self.logs_dir):
            folder.mkdir(parents=True, exist_ok=True)
        readme = self.root / "README.txt"
        if not readme.exists():
            readme.write_text(WORKSPACE_README, encoding="utf-8")
        config = self.load()
        changed = not self.config_path.exists()
        if language:
            config["language"] = language
            changed = True
        if not config.get("language"):
            config["language"] = env.detect_language()
            changed = True
        if theme:
            config["active_theme"] = theme
            changed = True
        if not config.get("active_theme"):
            config["active_theme"] = "ink-study" if config["language"].startswith("zh") else "deep-orbit"
            changed = True
        if not config.get("token"):
            config["token"] = secrets.token_urlsafe(24)
            changed = True
        if changed:
            self.save(config)
        return config

    def load(self) -> Dict[str, Any]:
        stored = env.read_json(self.config_path, {}) or {}
        config = copy.deepcopy(DEFAULT_CONFIG)
        if isinstance(stored, dict):
            config.update(stored)
        if not isinstance(config.get("actions"), dict):
            config["actions"] = {}
        try:
            config["port"] = int(config.get("port") or DEFAULT_PORT)
        except (TypeError, ValueError):
            config["port"] = DEFAULT_PORT
        return config

    def save(self, config: Dict[str, Any]) -> None:
        env.write_json(self.config_path, config, private=True)

    def update(self, **changes: Any) -> Dict[str, Any]:
        config = self.load()
        config.update(changes)
        self.save(config)
        return config

    def action_params(self, config: Dict[str, Any], action_id: str) -> Dict[str, Any]:
        entry = (config.get("actions") or {}).get(action_id) or {}
        params = entry.get("params") if isinstance(entry, dict) else None
        return dict(params) if isinstance(params, dict) else {}

    def lang(self, config: Optional[Dict[str, Any]] = None) -> str:
        config = config or self.load()
        return config.get("language") or env.detect_language()
