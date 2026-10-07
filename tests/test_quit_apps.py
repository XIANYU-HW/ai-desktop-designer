import importlib.util
import tempfile
from pathlib import Path
import unittest

from helpers import ROOT, TempHome

from orbitcore import env, kit

spec = importlib.util.spec_from_file_location("quit_apps", ROOT / "actions" / "quit-apps" / "quit_apps.py")
quit_apps = importlib.util.module_from_spec(spec)
spec.loader.exec_module(quit_apps)


def ctx(**params):
    return kit.Context({"action": "quit-apps", "op": "preview", "params": params, "lang": "en", "state_dir": str(Path(tempfile.gettempdir()) / "orbit-test-state")})


class ProtectionTest(unittest.TestCase):
    def reason(self, app, **params):
        return quit_apps.protection(ctx(**params), dict({"kind": "app", "pid": 99999}, **app), tree={1, 2})

    def test_ordinary_apps_can_close(self):
        self.assertIsNone(self.reason({"name": "Google Chrome", "exe": "chrome.exe"}))
        self.assertIsNone(self.reason({"name": "Microsoft Excel", "bundle": "com.microsoft.excel"}))

    def test_system_terminals_ai_and_network_tools_stay(self):
        for app in (
            {"name": "Windows Explorer", "exe": "explorer.exe"},
            {"name": "Finder", "bundle": "com.apple.finder"},
            {"name": "Windows Terminal", "exe": "windowsterminal.exe"},
            {"name": "Claude", "exe": "claude.exe"},
            {"name": "ChatGPT", "bundle": "com.apple.safari.webapp.123"},
            {"name": "Clash Verge", "exe": "clash-verge.exe"},
            {"name": "1Password", "exe": "1password.exe"},
            {"name": "Lively Wallpaper", "exe": "lively.exe"},
        ):
            self.assertIsNotNone(self.reason(app), app)

    def test_music_keep_only_and_own_process_tree(self):
        self.assertIsNotNone(self.reason({"name": "Spotify", "exe": "spotify.exe"}))
        self.assertIsNone(self.reason({"name": "Spotify", "exe": "spotify.exe"}, keep_music=False))
        self.assertIsNotNone(self.reason({"name": "WeChat", "exe": "wechat.exe"}, keep=["WeChat"]))
        self.assertIsNotNone(self.reason({"name": "Excel", "exe": "excel.exe"}, only=["chrome.exe"]))
        self.assertIsNone(self.reason({"name": "Google Chrome", "exe": "chrome.exe"}, only=["chrome"]))
        self.assertIsNotNone(self.reason({"name": "Code", "exe": "code.exe", "pid": 2}))

    def test_clean_name_drops_invisible_marks(self):
        self.assertEqual(quit_apps.clean_name("‎WhatsApp"), "WhatsApp")


@unittest.skipUnless(env.IS_WINDOWS or env.IS_MAC, "quit-apps supports Windows and macOS")
class LiveListingTest(unittest.TestCase):
    def test_preview_and_status_are_read_only_and_work(self):
        with TempHome() as h:
            preview = h.run("quit-apps", "preview")
            self.assertTrue(preview["ok"], preview)
            self.assertIn("apps", preview["data"])
            status = h.run("quit-apps", "status")
            self.assertTrue(status["ok"], status)
            self.assertIn("available", status["data"])


if __name__ == "__main__":
    unittest.main()
