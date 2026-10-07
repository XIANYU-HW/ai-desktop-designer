"""Tests that change the machine they run on. They only run on throwaway CI machines (CI=true)."""
import os
import subprocess
import time
import unittest

from helpers import TempHome

from orbitcore import env, hosts

ON_CI = os.environ.get("CI") == "true"


@unittest.skipUnless(ON_CI, "changes the machine; runs only on CI")
class AutostartTest(unittest.TestCase):
    def test_turn_on_and_off(self):
        with TempHome() as h:
            hosts.set_autostart(h.workspace, True)
            try:
                self.assertTrue(hosts.autostart_enabled())
            finally:
                hosts.set_autostart(h.workspace, False)
            self.assertFalse(hosts.autostart_enabled())


@unittest.skipUnless(ON_CI and (env.IS_WINDOWS or env.IS_MAC), "closes an app; runs only on CI")
class WindDownForRealTest(unittest.TestCase):
    """Open a harmless app, wind it down, reopen it, wind it down again."""

    def setUp(self):
        if env.IS_WINDOWS:
            self.only = ["notepad.exe"]
            self.proc = subprocess.Popen(["notepad.exe"])
            self.addCleanup(self.stop_test_app)
        else:
            self.only = ["com.apple.calculator"]
            subprocess.run(["open", "-g", "-a", "Calculator"], check=True)

    def stop_test_app(self):
        if self.proc.poll() is None:  # only the Notepad this test started, if the test was skipped
            self.proc.kill()
        self.proc.wait(10)

    def wait_listed(self, h, present, seconds=15):
        deadline = time.time() + seconds
        while time.time() < deadline:
            preview = h.run("quit-apps", "preview", {"only": self.only})
            if (preview["data"]["count"] > 0) == present:
                return True
            time.sleep(0.5)
        return False

    def test_close_and_reopen(self):
        with TempHome() as h:
            if not self.wait_listed(h, True):
                self.skipTest("the test app did not show a window on this runner (no interactive desktop)")
            events = []
            result = h.run("quit-apps", "run", {"only": self.only, "wait_seconds": 15}, events)
            self.assertTrue(result["ok"], result)
            self.assertEqual(result["data"]["closed"], 1, result)
            self.assertTrue(any(e.get("status") in ("closed", "hidden") for e in events))
            self.assertTrue(self.wait_listed(h, False, 5))
            reopened = h.run("quit-apps", "reopen")
            self.assertTrue(reopened["ok"], reopened)
            self.assertEqual(reopened["data"]["opened"], 1, reopened)
            self.assertTrue(self.wait_listed(h, True))
            again = h.run("quit-apps", "run", {"only": self.only, "wait_seconds": 15})
            self.assertEqual(again["data"]["closed"], 1, again)


if __name__ == "__main__":
    unittest.main()
