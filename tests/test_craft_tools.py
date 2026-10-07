"""Tests for the craft tools: bundled fonts, the review report and quiet browser windows (no network)."""
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from helpers import ROOT  # noqa: F401  (puts runtime/ on sys.path)

from orbitcore import env, fonts, hosts, review


class FontsTest(unittest.TestCase):
    def test_common_chinese_is_gb2312_level_one(self):
        chars = fonts.common_zh()
        self.assertEqual(len(chars), 3755 + len(fonts.CJK_PUNCTUATION))
        self.assertIn("的", chars)
        self.assertIn("言", chars)

    def test_ranges_collapse_consecutive_code_points(self):
        self.assertEqual(fonts._ranges("abcx"), "U+61-63, U+78")
        self.assertEqual(fonts._ranges("z"), "U+7A")

    def test_theme_text_reads_the_theme_but_not_its_fonts(self):
        folder = Path(tempfile.mkdtemp(prefix="orbit-fonts-"))
        try:
            (folder / "index.html").write_text("<p>神谕</p>", encoding="utf-8")
            (folder / "assets" / "fonts").mkdir(parents=True)
            (folder / "assets" / "fonts" / "fonts.css").write_text("/* 不该收录 */", encoding="utf-8")
            text = fonts.theme_text(folder)
            self.assertIn("神", text)
            self.assertNotIn("录", text)
        finally:
            shutil.rmtree(folder, ignore_errors=True)


class ReviewTest(unittest.TestCase):
    def sample(self, **changes):
        report = {"viewport": [1920, 1080], "platform": "windows", "errors": [], "fonts": [{"family": "My Serif", "weight": "400", "style": "normal", "status": "loaded"}],
                  "families": {"My Serif": True}, "text": [{"el": ".clock \"12:00\"", "size": 64, "family": "My Serif", "rect": [1500, 60, 200, 70]}],
                  "overlaps": [], "zones": [], "offscreen": [], "network": [], "translate": True}
        report.update(changes)
        return report

    def test_parse_report_from_dumped_dom(self):
        data = self.sample()
        dom = '<html><body><script type="application/json" id="orbit-review">' + json.dumps(data).replace("<", "\\u003c") + "</script></body></html>"
        self.assertEqual(review.parse_report(dom)["viewport"], [1920, 1080])
        self.assertIsNone(review.parse_report("<html></html>"))

    def test_clean_report_passes(self):
        findings = review.assess(self.sample(), ROOT / "templates" / "theme")
        self.assertEqual([level for level, _ in findings], ["ok"])

    def test_fallback_font_overlap_and_errors_are_errors(self):
        findings = review.assess(self.sample(families={"Missing Serif": False}, overlaps=[[".a", ".b"]], errors=["boom"]), ROOT / "templates" / "theme")
        levels = [level for level, _ in findings]
        self.assertEqual(levels.count("error"), 3)

    def test_network_and_tiny_text_are_warnings(self):
        report = self.sample(network=["https://fonts.googleapis.com/css2?family=X"],
                             text=[{"el": ".note \"hi\"", "size": 9, "family": "My Serif", "rect": [900, 500, 20, 10]}])
        findings = review.assess(report, ROOT / "templates" / "theme")
        self.assertTrue(all(level == "warning" for level, _ in findings))
        self.assertEqual(len(findings), 2)

    def test_theme_states_from_manifest(self):
        states = review.theme_states({"review": {"states": {"Praying now": "pray=hi", "bad": 3}}})
        self.assertEqual(states, [("praying-now", "pray=hi")])


class QuietBrowserTest(unittest.TestCase):
    def test_quiet_profile_turns_translation_off(self):
        profile = Path(tempfile.mkdtemp(prefix="orbit-profile-"))
        try:
            hosts.quiet_profile(profile, "zh-CN")
            prefs = env.read_json(profile / "Default" / "Preferences", {})
            self.assertIs(prefs["translate"]["enabled"], False)
            self.assertIn("zh", prefs["intl"]["accept_languages"])
            hosts.quiet_profile(profile, "zh-CN")       # idempotent
            prefs = env.read_json(profile / "Default" / "Preferences", {})
            self.assertEqual(prefs["translate_blocked_languages"].count("zh"), 1)
        finally:
            shutil.rmtree(profile, ignore_errors=True)

    def test_window_args_set_language_and_app_mode(self):
        args = hosts.browser_window_args("edge", "http://127.0.0.1:1/", Path("p"), "zh-CN", True)
        self.assertIn("--app=http://127.0.0.1:1/", args)
        self.assertIn("--lang=zh-CN", args)
        self.assertIn("--start-fullscreen", args)


if __name__ == "__main__":
    unittest.main()
