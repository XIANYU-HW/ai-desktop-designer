"""Tests for the craft tools: bundled fonts, the review report and quiet browser windows (no network)."""
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

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

    def _render(self, theme=None, *, snapshot=None, dump=None, quick=False):
        def good_snapshot(url, target, width, height, wait):
            target.write_bytes(b"test-image")
            return True, str(target)

        def good_dom(url, width, height, wait):
            data = self.sample(viewport=[width, height])
            return True, '<script id="orbit-review">' + json.dumps(data) + '</script>'

        with tempfile.TemporaryDirectory(prefix="orbit-review-test-") as folder, \
                mock.patch.object(hosts, "snapshot", side_effect=snapshot or good_snapshot) as shots, \
                mock.patch.object(hosts, "dump_dom", side_effect=dump or good_dom) as doms:
            level, report = review.run(ROOT / "templates" / "theme", theme or {"id": "test"},
                                       1, Path(folder), quick=quick, log=lambda _: None)
            return level, json.loads(report.with_suffix(".json").read_text()), report.read_text(), shots.call_args_list, doms.call_args_list

    def test_full_review_measures_every_size_and_state(self):
        level, data, text, shots, doms = self._render()
        self.assertEqual(level, 0)
        self.assertEqual(data["coverage"], {"planned": 20, "captured": 20, "measured": 20, "mode": "full"})
        self.assertEqual(len(shots), len(doms))
        for shot, dom in zip(shots, doms):
            self.assertEqual(shot.args[0] + "&review=3500", dom.args[0])
            self.assertEqual(shot.args[2:4], dom.args[1:3])
        self.assertEqual(data["evidence"]["automatic"], "passed")
        self.assertEqual(data["evidence"]["visual"], "pending")
        self.assertEqual(data["evidence"]["real_host"], "pending")
        self.assertIn("unverified", text)

    def test_snapshot_failure_cannot_pass(self):
        level, data, _, _, _ = self._render(snapshot=lambda *args: (False, "browser missing"), quick=True)
        self.assertEqual(level, 2)
        self.assertEqual(data["coverage"]["captured"], 0)
        self.assertEqual(data["coverage"]["measured"], 8)
        self.assertEqual(sum("Snapshot failed" in message for _, message in data["findings"]), 8)

    def test_success_without_image_is_failure(self):
        level, data, _, _, _ = self._render(snapshot=lambda *args: (True, "ok"), quick=True)
        self.assertEqual(level, 2)
        self.assertEqual(data["coverage"]["captured"], 0)

    def test_renderer_exception_still_writes_failure_report(self):
        def fail(*args):
            raise OSError("cannot start browser")
        level, data, _, _, _ = self._render(snapshot=fail, dump=fail, quick=True)
        self.assertEqual(level, 2)
        self.assertEqual(data["coverage"]["measured"], 0)

    def test_custom_state_is_measured_and_must_be_implemented(self):
        theme = {"id": "test", "review": {"states": {"empty": "review-state=empty"}}}
        level, data, _, _, _ = self._render(theme, quick=True)
        self.assertEqual(level, 2)
        self.assertEqual(data["coverage"]["planned"], 10)
        self.assertEqual(sum("did not confirm" in message for _, message in data["findings"]), 2)

    def test_duplicate_state_names_do_not_overwrite_evidence(self):
        theme = {"id": "test", "review": {"states": {"DAY": "x=1", "day!": "x=2"}}}
        _, data, _, _, _ = self._render(theme, quick=True)
        self.assertEqual(len(data["pictures"]), len(set(data["pictures"])))

    def test_non_object_and_empty_measurements_cannot_pass(self):
        self.assertIsNone(review.parse_report('<script id="orbit-review">[]</script>'))
        self.assertEqual(review.assess({}, ROOT)[0][0], "error")

    def test_malformed_measurement_keeps_failure_evidence(self):
        data = self.sample(text=[{"size": "invalid"}])
        dump = lambda *args: (True, '<script id="orbit-review">' + json.dumps(data) + '</script>')
        level, report, _, _, _ = self._render(dump=dump, quick=True)
        self.assertEqual(level, 2)
        self.assertEqual(report["evidence"]["automatic"], "failed")
        errors = [message for severity, message in report["findings"] if severity == "error"]
        self.assertEqual(len(errors), 8)
        self.assertTrue(all("malformed" in message for message in errors))


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
