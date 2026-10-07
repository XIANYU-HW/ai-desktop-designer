"""Opener safety checks; every OS opening call is mocked."""
import importlib.util
import os
import unittest
from unittest.mock import patch

from helpers import ROOT, TempHome
from orbitcore import kit

spec = importlib.util.spec_from_file_location("open_path_action", ROOT / "actions" / "open-path" / "open_path.py")
opener = importlib.util.module_from_spec(spec)
spec.loader.exec_module(opener)


class OpenPathTest(unittest.TestCase):
    def run_opener(self, h, path):
        ctx = kit.Context({"action": "open-path", "op": "run", "params": {"path": str(path)},
                           "lang": "en", "state_dir": str(h.workspace.state_dir / "open-path")})
        with patch.object(opener.kit, "open_path") as opened:
            result = opener.op_run(ctx)
        return result, opened

    def test_document_and_web_address_can_open(self):
        with TempHome() as h:
            document = h.file("manual.pdf")
            for path in (document, "https://example.com/"):
                result, opened = self.run_opener(h, path)
                self.assertTrue(result["ok"], result)
                opened.assert_called_once()

    def test_program_and_script_types_are_refused(self):
        with TempHome() as h:
            for name in ("tool.py", "tool.exe", "tool.command", "tool.ps1", "tool.webloc", "tool.lnk"):
                path = h.file(name)
                result, opened = self.run_opener(h, path)
                self.assertFalse(result["ok"], name)
                opened.assert_not_called()

    def test_document_named_symlink_cannot_launch_a_program(self):
        with TempHome() as h:
            program = h.file("tool.py")
            link = h.desktop / "manual.pdf"
            try:
                link.symlink_to(program)
            except OSError:
                self.skipTest("Creating links requires permission on this platform")
            result, opened = self.run_opener(h, link)
            self.assertFalse(result["ok"])
            opened.assert_not_called()

    @unittest.skipIf(os.name == "nt", "POSIX executable permission")
    def test_extensionless_executable_is_refused(self):
        with TempHome() as h:
            executable = h.file("tool", "#!/bin/sh\nexit 0\n")
            executable.chmod(0o755)
            result, opened = self.run_opener(h, executable)
            self.assertFalse(result["ok"])
            opened.assert_not_called()

    def test_program_inside_an_app_bundle_is_refused(self):
        with TempHome() as h:
            executable = h.file("tool", folder=h.desktop / "Tool.app" / "Contents" / "MacOS")
            result, opened = self.run_opener(h, executable)
            self.assertFalse(result["ok"])
            opened.assert_not_called()


if __name__ == "__main__":
    unittest.main()
