import json
import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

from helpers import ROOT, TempHome

from orbitcore import env, registry, system
from orbitcore.config import Workspace

ORBIT = [sys.executable, str(ROOT / "runtime" / "orbit.py")]


class RegistryTest(unittest.TestCase):
    def test_bundled_themes_are_valid(self):
        actions = registry.load_actions(Path("/nonexistent-workspace"))
        for theme_id in ("threebody-observatory", "genshin-sumeru", "ink-study", "deep-orbit", "defrag-95"):
            report = registry.validate_theme(ROOT / "themes" / theme_id, actions)
            errors = [m for level, m in report if level == "error"]
            self.assertEqual(errors, [], theme_id)

    def test_template_theme_is_valid(self):
        with TempHome() as h:
            target = h.base / "my-theme"
            shutil.copytree(ROOT / "templates" / "theme", target)
            report = registry.validate_theme(target, registry.load_actions(h.workspace.root))
            self.assertEqual([m for level, m in report if level == "error"], [])

    def test_static_theme_needs_no_animation_loop(self):
        with TempHome() as h:
            target = h.base / "my-theme"
            shutil.copytree(ROOT / "templates" / "theme", target)
            (target / "style.css").write_text("body { color: black; background: white; }", encoding="utf-8")
            (target / "scene.js").write_text("", encoding="utf-8")
            report = registry.validate_theme(target)
            self.assertFalse(any("animations should pause" in message for _, message in report))
            (target / "style.css").write_text("@keyframes drift { to { transform: translateX(3px); } }", encoding="utf-8")
            report = registry.validate_theme(target)
            self.assertTrue(any("animations should pause" in message for _, message in report))

    def test_bundled_and_template_actions_are_valid(self):
        for folder in list((ROOT / "actions").iterdir()) + [ROOT / "templates" / "action"]:
            if (folder / "action.json").exists():
                report = registry.validate_action(folder)
                self.assertEqual([m for level, m in report if level == "error"], [], folder.name)

    def test_summaries_are_localized(self):
        actions = registry.load_actions(Path("/nonexistent-workspace"))
        zh = registry.summarize_action(actions["tidy-files"], "zh-CN")
        en = registry.summarize_action(actions["tidy-files"], "en")
        self.assertEqual(zh["name"], "一键收纳")
        self.assertEqual(en["name"], "Tidy files")
        self.assertEqual(en["operations"]["run"]["effect"], "files")

    def test_pick_and_paths(self):
        self.assertEqual(env.pick({"en": "A", "zh-CN": "甲"}, "zh-CN"), "甲")
        self.assertEqual(env.pick("plain", "en"), "plain")
        self.assertTrue(str(env.expand_path("{documents}/x")).endswith("x"))
        self.assertTrue(env.known_folder("desktop").name)

    def test_system_readings_are_fractions(self):
        readings = system.readings(max_age=0)
        for key in ("cpu", "memory", "disk", "battery"):
            value = readings[key]
            self.assertTrue(value is None or 0.0 <= value <= 1.0, (key, value))
        self.assertIsNotNone(readings["disk"])


class CliTest(unittest.TestCase):
    def orbit(self, *args, home=None, check=True):
        env_vars = dict(os.environ)
        env_vars["PYTHONIOENCODING"] = "utf-8"
        result = subprocess.run(ORBIT + list(args), capture_output=True, text=True, encoding="utf-8", env=env_vars, timeout=120)
        if check:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def test_basic_commands(self):
        with TempHome() as h:
            self.orbit("init", "--lang", "zh-CN")
            self.assertEqual(json.loads((h.workspace.root / "config.json").read_text(encoding="utf-8"))["language"], "zh-CN")
            themes = self.orbit("themes").stdout
            for theme_id in ("threebody-observatory", "genshin-sumeru", "ink-study", "deep-orbit", "defrag-95"):
                self.assertIn(theme_id, themes)
            self.assertIn("tidy-files", self.orbit("actions").stdout)
            self.orbit("validate", "threebody-observatory", "genshin-sumeru", "ink-study", "deep-orbit", "defrag-95")
            self.orbit("doctor")

    def test_new_theme_and_action(self):
        with TempHome() as h:
            self.orbit("new-theme", "rainy-library", "--name", "Rainy Library")
            folder = h.workspace.root / "themes" / "rainy-library"
            self.assertEqual(json.loads((folder / "theme.json").read_text(encoding="utf-8"))["id"], "rainy-library")
            self.orbit("validate", "rainy-library")
            self.orbit("new-theme", "ink-copy", "--from", "ink-study")
            self.orbit("use", "ink-copy")
            self.orbit("new-action", "clean-screens")
            self.orbit("validate-action", "clean-screens")
            preview = self.orbit("run", "clean-screens", "preview", "--json").stdout
            self.assertTrue(json.loads(preview)["ok"])

    def test_state_changing_runs_need_yes(self):
        with TempHome() as h:
            h.file("a.pdf")
            params = json.dumps(h.tidy_params())
            refused = self.orbit("run", "tidy-files", "run", "--params", params, check=False)
            self.assertEqual(refused.returncode, 2)
            self.assertTrue((h.desktop / "a.pdf").exists())
            done = self.orbit("run", "tidy-files", "run", "--params", params, "--yes", "--json")
            self.assertEqual(json.loads(done.stdout)["data"]["moved"], 1)

    def test_params_survive_any_shell(self):
        with TempHome() as h:
            h.file("a.pdf")
            # repeated key=value, the form the docs recommend
            out = self.orbit("run", "tidy-files", "preview", "--param", f"source={h.desktop}",
                             "--param", f"library={h.library}", "--json").stdout
            self.assertEqual(json.loads(out)["data"]["pending"], 1)
            # what Windows PowerShell 5.1 passes for '{"source":"..."}': the inner quotes are gone
            mangled = "{source:%s,library:%s}" % (h.desktop, h.library)
            out = self.orbit("run", "tidy-files", "preview", "--params", mangled, "--json").stdout
            self.assertEqual(json.loads(out)["data"]["pending"], 1)
            bad = self.orbit("run", "tidy-files", "preview", "--param", "nonsense", check=False)
            self.assertEqual(bad.returncode, 1)

    def test_language_choice_is_remembered(self):
        with TempHome() as h:
            fresh = Workspace(h.base / "fresh").ensure()
            self.assertEqual(fresh["language_source"], "detected")
            self.assertEqual(fresh["theme_source"], "default")
            chosen = Workspace(h.base / "chosen").ensure(language="zh-CN")
            self.assertEqual(chosen["language_source"], "user")
            self.assertEqual(chosen["active_theme"], "threebody-observatory")

    def test_export_and_import_theme(self):
        with TempHome() as h:
            archive = h.base / "ink.zip"
            self.orbit("export-theme", "ink-study", "--out", str(archive))
            # importing a theme whose id already exists among the bundled ones goes to the workspace
            self.orbit("import-theme", str(archive))
            self.assertTrue((h.workspace.root / "themes" / "ink-study" / "theme.json").exists())


if __name__ == "__main__":
    unittest.main()
