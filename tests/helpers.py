"""Shared test helpers: an isolated fake home folder and workspace for every test."""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, Optional

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "runtime"
if str(RUNTIME) not in sys.path:
    sys.path.insert(0, str(RUNTIME))

from orbitcore import registry  # noqa: E402
from orbitcore.config import Workspace  # noqa: E402
from orbitcore.runner import merge_params, run_action  # noqa: E402

OLD = time.time() - 3600  # files older than the "changed moments ago" window


class TempHome:
    """A throwaway home folder with Desktop and Documents; HOME and USERPROFILE point at it."""

    def __enter__(self) -> "TempHome":
        self.base = Path(tempfile.mkdtemp(prefix="orbit-test-")).resolve()
        self.home = self.base / "home"
        self.desktop = self.home / "Desktop"
        self.documents = self.home / "Documents"
        self.library = self.documents / "Archive"
        for folder in (self.desktop, self.documents):
            folder.mkdir(parents=True)
        self.saved = {k: os.environ.get(k) for k in ("HOME", "USERPROFILE", "ORBIT_WORKSPACE", "ORBIT_LANG")}
        os.environ["HOME"] = str(self.home)
        os.environ["USERPROFILE"] = str(self.home)
        os.environ["ORBIT_WORKSPACE"] = str(self.home / "OrbitDesktop")
        os.environ["ORBIT_LANG"] = "en"
        self.workspace = Workspace(self.home / "OrbitDesktop")
        self.workspace.ensure(language="en")
        return self

    def __exit__(self, *exc: Any) -> None:
        for key, value in self.saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        shutil.rmtree(self.base, ignore_errors=True)

    def file(self, name: str, text: str = "x", folder: Optional[Path] = None, age: Optional[float] = OLD) -> Path:
        path = (folder or self.desktop) / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        if age is not None:
            os.utime(path, (age, age))
        return path

    def tidy_params(self, **extra: Any) -> Dict[str, Any]:
        params = {"source": str(self.desktop), "library": str(self.library), "preset": "en"}
        params.update(extra)
        return params

    def run(self, action_id: str, op: str, params: Optional[Dict[str, Any]] = None, events: Optional[list] = None) -> Dict[str, Any]:
        actions = registry.load_actions(self.workspace.root)
        manifest = actions[action_id]
        merged = merge_params(manifest, {}, params or {})
        return run_action(manifest, op, merged, lang="en", workspace_root=self.workspace.root,
                          on_progress=(events.append if events is not None else None))
