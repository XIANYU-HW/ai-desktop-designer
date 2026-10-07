"""Headless-render timeout regressions: no real browser or screen capture runs."""
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from helpers import ROOT  # puts the runtime on sys.path
from orbitcore import env, hosts


class BrowserRenderTest(unittest.TestCase):
    def process(self, waits, stdout=b"", stderr=b"", image=False):
        process = Mock(pid=246810)
        process.wait.side_effect = waits

        def launch(args, **kwargs):
            # Real file handles let the browser and any child write without
            # leaving Python blocked on an inherited stdout/stderr pipe.
            self.assertNotEqual(kwargs["stdout"], subprocess.PIPE)
            self.assertNotEqual(kwargs["stderr"], subprocess.PIPE)
            kwargs["stdout"].write(stdout)
            kwargs["stderr"].write(stderr)
            if image:
                target = next(a.split("=", 1)[1] for a in args if a.startswith("--screenshot="))
                Path(target).write_bytes(b"test image")
            return process

        return process, launch

    def test_posix_timeout_kills_only_isolated_render_group_and_has_bounded_waits(self):
        process, launch = self.process([subprocess.TimeoutExpired("fake-browser", 60), -9], stderr=b"renderer stalled")
        with tempfile.TemporaryDirectory(prefix="orbit-render-test-") as directory:
            with patch.object(hosts, "find_browser", return_value="fake-browser"), \
                 patch.object(env, "IS_WINDOWS", False), \
                 patch.object(hosts.subprocess, "Popen", side_effect=launch) as started, \
                 patch.object(hosts.os, "killpg") as kill_group:
                ok, detail = hosts.snapshot("http://example.invalid/", Path(directory) / "preview.png")
        self.assertFalse(ok)
        self.assertIn("took too long", detail)
        self.assertIn("renderer stalled", detail)
        self.assertTrue(started.call_args.kwargs["start_new_session"])
        kill_group.assert_called_once_with(process.pid, hosts.signal.SIGKILL)
        self.assertEqual([c.kwargs["timeout"] for c in process.wait.call_args_list], [60, hosts._BROWSER_CLEANUP_SECONDS])
        process.communicate.assert_not_called()

    def test_timeout_retains_already_written_snapshot_after_cleanup(self):
        process, launch = self.process([subprocess.TimeoutExpired("fake-browser", 60), -9], image=True)
        with tempfile.TemporaryDirectory(prefix="orbit-render-test-") as directory:
            target = Path(directory) / "preview.png"
            with patch.object(hosts, "find_browser", return_value="fake-browser"), \
                 patch.object(env, "IS_WINDOWS", False), \
                 patch.object(hosts.subprocess, "Popen", side_effect=launch), patch.object(hosts.os, "killpg"):
                ok, detail = hosts.snapshot("http://example.invalid/", target)
            self.assertTrue(ok)
            self.assertEqual(detail, str(target.resolve()))
        process.communicate.assert_not_called()

    def test_dom_timeout_does_not_accept_partial_output(self):
        process, launch = self.process([subprocess.TimeoutExpired("fake-browser", 60), -9],
                                       stdout=b"<html><body>unfinished", stderr=b"renderer crash")
        with patch.object(hosts, "find_browser", return_value="fake-browser"), \
             patch.object(env, "IS_WINDOWS", False), \
             patch.object(hosts.subprocess, "Popen", side_effect=launch), patch.object(hosts.os, "killpg"):
            ok, detail = hosts.dump_dom("http://example.invalid/")
        self.assertFalse(ok)
        self.assertIn("took too long", detail)
        self.assertIn("renderer crash", detail)
        process.communicate.assert_not_called()

    def test_dom_success_reads_output_without_pipe_cleanup(self):
        process, launch = self.process([0], stdout=b"<html>complete</html>")
        with patch.object(hosts, "find_browser", return_value="fake-browser"), \
             patch.object(hosts.subprocess, "Popen", side_effect=launch), patch.object(hosts, "_stop_headless") as stop:
            self.assertEqual(hosts.dump_dom("http://example.invalid/"), (True, "<html>complete</html>"))
        stop.assert_not_called()
        process.communicate.assert_not_called()

    def test_windows_timeout_targets_pid_tree_and_has_bounded_taskkill(self):
        process, launch = self.process([subprocess.TimeoutExpired("fake-browser", 1), 1])
        with patch.object(env, "IS_WINDOWS", True), \
             patch.object(hosts.subprocess, "Popen", side_effect=launch) as started, \
             patch.object(hosts.subprocess, "run", return_value=Mock(returncode=0)) as taskkill:
            _, _, timed_out, error = hosts._run_headless(["fake-browser"], timeout=1)
        self.assertTrue(timed_out)
        self.assertEqual(error, "")
        self.assertEqual(started.call_args.kwargs["creationflags"], env.CREATE_NO_WINDOW | env.CREATE_NEW_PROCESS_GROUP)
        self.assertEqual(taskkill.call_args.args[0], ["taskkill", "/PID", str(process.pid), "/T", "/F"])
        self.assertEqual(taskkill.call_args.kwargs["timeout"], hosts._BROWSER_CLEANUP_SECONDS)
        process.kill.assert_not_called()

    def test_windows_taskkill_timeout_still_reaps_only_our_parent_with_a_deadline(self):
        process, launch = self.process([subprocess.TimeoutExpired("fake-browser", 1), 1])
        with patch.object(env, "IS_WINDOWS", True), \
             patch.object(hosts.subprocess, "Popen", side_effect=launch), \
             patch.object(hosts.subprocess, "run", side_effect=subprocess.TimeoutExpired("taskkill", 5)):
            _, _, timed_out, error = hosts._run_headless(["fake-browser"], timeout=1)
        self.assertTrue(timed_out)
        self.assertIn("tree cleanup failed", error)
        process.kill.assert_called_once_with()
        self.assertEqual(process.wait.call_args.kwargs["timeout"], hosts._BROWSER_CLEANUP_SECONDS)

    def test_keyboard_interrupt_cleans_up_new_session_before_propagating(self):
        process, launch = self.process([KeyboardInterrupt(), -9])
        with patch.object(env, "IS_WINDOWS", False), \
             patch.object(hosts.subprocess, "Popen", side_effect=launch), patch.object(hosts.os, "killpg") as kill_group:
            with self.assertRaises(KeyboardInterrupt):
                hosts._run_headless(["fake-browser"], timeout=60)
        kill_group.assert_called_once_with(process.pid, hosts.signal.SIGKILL)
        self.assertEqual(process.wait.call_args.kwargs["timeout"], hosts._BROWSER_CLEANUP_SECONDS)

    def test_cleanup_timeout_is_reported_even_if_snapshot_was_written(self):
        process, launch = self.process([subprocess.TimeoutExpired("fake-browser", 60), subprocess.TimeoutExpired("fake-browser", 5)], image=True)
        with tempfile.TemporaryDirectory(prefix="orbit-render-test-") as directory:
            with patch.object(hosts, "find_browser", return_value="fake-browser"), \
                 patch.object(env, "IS_WINDOWS", False), \
                 patch.object(hosts.subprocess, "Popen", side_effect=launch), patch.object(hosts.os, "killpg"):
                ok, detail = hosts.snapshot("http://example.invalid/", Path(directory) / "preview.png")
        self.assertFalse(ok)
        self.assertIn("cleanup deadline", detail)
        process.communicate.assert_not_called()

    def test_browser_launch_failure_is_a_useful_result(self):
        with patch.object(hosts, "find_browser", return_value="fake-browser"), \
             patch.object(hosts.subprocess, "Popen", side_effect=OSError("browser unavailable")):
            ok, detail = hosts.dump_dom("http://example.invalid/")
        self.assertFalse(ok)
        self.assertIn("could not start", detail)
        self.assertIn("browser unavailable", detail)

    def test_excessive_dom_output_fails_explicitly(self):
        _, launch = self.process([0], stdout=b"0123456789")
        with patch.object(hosts, "find_browser", return_value="fake-browser"), \
             patch.object(hosts, "_BROWSER_STDOUT_LIMIT", 8), \
             patch.object(hosts.subprocess, "Popen", side_effect=launch):
            ok, detail = hosts.dump_dom("http://example.invalid/")
        self.assertFalse(ok)
        self.assertIn("size limit", detail)


if __name__ == "__main__":
    unittest.main()
