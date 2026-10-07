"""Host boundaries tested with temporary files and mocked system calls only."""
import argparse
import contextlib
import io
import os
import plistlib
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

from helpers import ROOT  # adds the runtime to sys.path
from orbitcore import cli, env, hosts
from orbitcore.config import Workspace


class HostTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="orbit-host-test-")
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name).resolve()
        self.ws = Workspace(self.base / "selected workspace")
        with mock.patch("orbitcore.config.port_is_free", return_value=True):
            self.ws.ensure(language="en")
        # Unexpected external calls must fail, even on a developer's real machine.
        for name in ("run", "Popen"):
            guard = mock.patch.object(hosts.subprocess, name,
                                      side_effect=AssertionError("unexpected process launch"))
            guard.start()
            self.addCleanup(guard.stop)

    def capture(self, function, *args):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            result = function(*args)
        return result, output.getvalue()

    def test_helper_always_keeps_selected_workspace(self):
        # A conflicting environment must not override the supplied workspace.
        for configured in (None, str(self.base / "different-workspace")):
            with self.subTest(environment=configured), mock.patch.dict(os.environ):
                if configured is None:
                    os.environ.pop("ORBIT_WORKSPACE", None)
                else:
                    os.environ["ORBIT_WORKSPACE"] = configured
                ws = Workspace(self.ws.root / ".." / self.ws.root.name)
                command = hosts.helper_command(ws)
                self.assertEqual(command[2:], ["--workspace", str(self.ws.root), "serve", "--quiet"])

    def test_background_launch_receives_selected_workspace(self):
        process = mock.Mock()
        process.poll.return_value = None
        with mock.patch.object(hosts, "ping", side_effect=[None, {"ok": True}]), \
                mock.patch.object(hosts.subprocess, "Popen", return_value=process) as launch:
            self.assertEqual(hosts.start_background(self.ws), (True, "started"))
        self.assertIn(str(self.ws.root), launch.call_args.args[0])
        self.assertEqual(launch.call_args.kwargs["cwd"], str(self.ws.root))
        self.assertTrue(launch.call_args.kwargs["stdout"].closed)

    def test_background_launch_error_returns_failure_and_closes_log(self):
        with mock.patch.object(hosts, "ping", return_value=None), \
                mock.patch.object(hosts.subprocess, "Popen", side_effect=OSError("missing interpreter")) as launch:
            ok, detail = hosts.start_background(self.ws)
        self.assertFalse(ok)
        self.assertIn("missing interpreter", detail)
        self.assertTrue(launch.call_args.kwargs["stdout"].closed)

    def test_mac_autostart_keeps_workspace_in_temporary_plist(self):
        plist = self.base / "LaunchAgents" / "orbit.plist"
        with mock.patch.object(env, "IS_WINDOWS", False), mock.patch.object(env, "IS_MAC", True), \
                mock.patch.object(hosts, "_launch_agent_path", return_value=plist):
            hosts.set_autostart(self.ws, True)
            data = plistlib.loads(plist.read_bytes())
        self.assertEqual(data["ProgramArguments"][2:],
                         ["--workspace", str(self.ws.root), "serve", "--quiet"])

    def test_windows_autostart_keeps_workspace_in_mock_registry(self):
        registry = types.SimpleNamespace(
            HKEY_CURRENT_USER=1, KEY_SET_VALUE=2, REG_SZ=3,
            CreateKeyEx=mock.MagicMock(), SetValueEx=mock.Mock(),
        )
        with mock.patch.object(env, "IS_WINDOWS", True), \
                mock.patch.dict(sys.modules, {"winreg": registry}):
            hosts.set_autostart(self.ws, True)
        command = registry.SetValueEx.call_args.args[-1]
        self.assertIn('--workspace "' + str(self.ws.root) + '"', command)

    def test_windows_autostart_permission_failure_is_not_silenced(self):
        registry = types.SimpleNamespace(HKEY_CURRENT_USER=1, KEY_SET_VALUE=2,
                                         OpenKey=mock.MagicMock(side_effect=PermissionError("denied")))
        with mock.patch.object(env, "IS_WINDOWS", True), \
                mock.patch.dict(sys.modules, {"winreg": registry}), self.assertRaises(PermissionError):
            hosts.set_autostart(self.ws, False)

    def test_plash_checks_exit_status_and_only_acknowledges_request(self):
        for code in (0, 1):
            with self.subTest(code=code), mock.patch.object(hosts, "find_plash", return_value="/fake/Plash.app"), \
                    mock.patch.object(hosts.subprocess, "run", return_value=subprocess.CompletedProcess(
                        [], code, stdout="", stderr="host rejected" if code else "")):
                ok, detail = hosts.install_plash("http://127.0.0.1:47321/")
                self.assertEqual(ok, code == 0)
                self.assertIn("request-accepted" if code == 0 else "exit 1: host rejected", detail)

    def test_plash_launch_exceptions_are_reported(self):
        for error in (OSError("not found"), subprocess.TimeoutExpired("open", 15)):
            with self.subTest(error=type(error).__name__), \
                    mock.patch.object(hosts, "find_plash", return_value="/fake/Plash.app"), \
                    mock.patch.object(hosts.subprocess, "run", side_effect=error):
                ok, detail = hosts.install_plash("http://127.0.0.1:47321/")
            self.assertFalse(ok)
            self.assertIn("plash-command-failed", detail)

    def test_lively_checks_exit_status_and_only_acknowledges_request(self):
        info = {"installed": True, "exe": "mock-Lively.exe"}
        library = self.base / "lively-library"
        for code in (0, 1):
            with self.subTest(code=code), mock.patch.object(hosts, "find_lively", return_value=info), \
                    mock.patch.object(hosts, "lively_library", return_value=library), \
                    mock.patch.object(hosts.subprocess, "run", return_value=subprocess.CompletedProcess(
                        [], code, stdout="", stderr="host rejected" if code else "")):
                ok, detail = hosts.install_lively(self.ws, "http://127.0.0.1:47321/")
                self.assertEqual(ok, code == 0)
                self.assertIn("request-accepted" if code == 0 else "exit 1: host rejected", detail)
        self.assertTrue((library / "wallpapers" / hosts.LIVELY_PACKAGE / "LivelyInfo.json").is_file())

    def test_lively_store_requires_manual_application(self):
        with mock.patch.object(hosts, "find_lively", return_value={"installed": True, "exe": None}), \
                mock.patch.object(hosts, "lively_library", return_value=self.base / "lively-library"):
            self.assertEqual(hosts.install_lively(self.ws, "http://127.0.0.1:47321/"), (False, "lively-store"))

    def test_lively_uninstall_preserves_wallpapers_and_requires_manual_removal(self):
        library = self.base / "lively-library"
        for name in (hosts.LIVELY_PACKAGE, "other-wallpaper"):
            folder = library / "wallpapers" / name
            folder.mkdir(parents=True)
            (folder / "LivelyInfo.json").write_text("{}", encoding="utf-8")
        before = sorted(path.relative_to(library) for path in library.rglob("*"))
        with mock.patch.object(hosts, "find_lively", return_value={"installed": True, "exe": "mock-Lively.exe"}), \
                mock.patch.object(hosts, "lively_library", return_value=library):
            self.assertEqual(hosts.uninstall_lively(), (False, "lively-manual-removal"))
        self.assertEqual(before, sorted(path.relative_to(library) for path in library.rglob("*")))

    def test_install_autostart_requires_explicit_flag_and_accepted_request(self):
        cases = [([], True, False), (["--no-autostart"], True, False),
                 (["--autostart"], False, False), (["--autostart"], True, True)]
        for flags, accepted, startup in cases:
            with self.subTest(flags=flags, accepted=accepted):
                args = cli.build_parser().parse_args(["--workspace", str(self.ws.root), "install"] + flags)
                with mock.patch.object(cli, "_require_helper", return_value=True), \
                        mock.patch.object(cli, "_put_on_desktop", return_value=accepted), \
                        mock.patch.object(hosts, "set_autostart") as autostart:
                    code, output = self.capture(cli.cmd_install, args)
                self.assertEqual(code, 0 if accepted else 3)
                self.assertEqual(autostart.called, startup)
                if startup:
                    self.assertEqual(autostart.call_args.args[0].root, self.ws.root)
                    self.assertTrue(autostart.call_args.args[1])

    def test_failed_helper_does_not_request_host_or_autostart(self):
        args = cli.build_parser().parse_args(["--workspace", str(self.ws.root), "install", "--autostart"])
        with mock.patch.object(cli, "_require_helper", return_value=False), \
                mock.patch.object(cli, "_put_on_desktop") as host, \
                mock.patch.object(hosts, "set_autostart") as autostart:
            self.assertEqual(cli.cmd_install(args), 1)
        host.assert_not_called()
        autostart.assert_not_called()

    def test_install_reports_autostart_error(self):
        args = cli.build_parser().parse_args(["--workspace", str(self.ws.root), "install", "--autostart"])
        with mock.patch.object(cli, "_require_helper", return_value=True), \
                mock.patch.object(cli, "_put_on_desktop", return_value=True), \
                mock.patch.object(hosts, "set_autostart", side_effect=PermissionError("denied")):
            code, output = self.capture(cli.cmd_install, args)
        self.assertEqual(code, 1)
        self.assertIn("start at sign-in failed", output)

    def test_host_output_does_not_claim_verified_desktop(self):
        for windows in (True, False):
            with self.subTest(windows=windows), mock.patch.object(env, "IS_WINDOWS", windows), \
                    mock.patch.object(env, "IS_MAC", not windows), \
                    mock.patch.object(hosts, "install_lively", return_value=(True, "lively-request-accepted")), \
                    mock.patch.object(hosts, "install_plash", return_value=(True, "plash-request-accepted")):
                accepted, output = self.capture(cli._put_on_desktop, self.ws, cli.Out("en"))
            self.assertTrue(accepted)
            self.assertIn("has not been verified", output)

    def test_plash_command_error_is_not_misreported_as_missing_app(self):
        with mock.patch.object(env, "IS_WINDOWS", False), mock.patch.object(env, "IS_MAC", True), \
                mock.patch.object(hosts, "install_plash", return_value=(False, "plash-command-failed: exit 1")):
            accepted, output = self.capture(cli._put_on_desktop, self.ws, cli.Out("en"))
        self.assertFalse(accepted)
        self.assertIn("request failed", output)
        self.assertNotIn("Install the free Plash app first", output)

    def test_uninstall_reports_manual_host_step_and_stop_failure(self):
        for stopped in (True, False):
            with self.subTest(stopped=stopped), mock.patch.object(env, "IS_WINDOWS", True), \
                    mock.patch.object(hosts, "set_autostart"), \
                    mock.patch.object(hosts, "uninstall_lively", return_value=(False, "lively-manual-removal")), \
                    mock.patch.object(hosts, "stop_background", return_value=stopped):
                code, output = self.capture(cli.cmd_uninstall, argparse.Namespace(workspace=str(self.ws.root)))
            self.assertEqual(code, 3 if stopped else 1)
            self.assertIn("manual step", output)
            self.assertIn("Helper stopped." if stopped else "Could not stop the helper.", output)

    def test_quickstart_does_not_enable_autostart_after_failed_host_request(self):
        with mock.patch.object(cli, "interactive", return_value=False), \
                mock.patch.object(cli, "_require_helper", return_value=True), \
                mock.patch.object(cli, "ask", side_effect=["3", "q"]), \
                mock.patch.object(cli, "_put_on_desktop", return_value=False), \
                mock.patch.object(env, "IS_WINDOWS", False), \
                mock.patch.object(hosts, "set_autostart") as autostart:
            code, output = self.capture(cli.cmd_quickstart, argparse.Namespace(workspace=str(self.ws.root)))
        self.assertEqual(code, 0)
        autostart.assert_not_called()

    def test_quickstart_preserves_incomplete_removal_exit_status(self):
        with mock.patch.object(cli, "interactive", return_value=False), \
                mock.patch.object(cli, "_require_helper", return_value=True), \
                mock.patch.object(cli, "ask", return_value="6"), \
                mock.patch.object(cli, "cmd_uninstall", return_value=3):
            code, output = self.capture(cli.cmd_quickstart, argparse.Namespace(workspace=str(self.ws.root)))
        self.assertEqual(code, 3)


if __name__ == "__main__":
    unittest.main()
