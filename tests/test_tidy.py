import importlib.util
import errno
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from helpers import ROOT, TempHome
from orbitcore import kit

spec = importlib.util.spec_from_file_location("tidy", ROOT / "actions" / "tidy-files" / "tidy.py")
tidy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tidy)


def context(h, **params):
    return kit.Context({"action": "tidy-files", "op": "run", "params": h.tidy_params(**params),
                        "lang": "en", "state_dir": str(h.workspace.state_dir / "tidy-files")})


class TidyFilesTest(unittest.TestCase):
    def test_preview_moves_files_and_keeps_the_rest(self):
        with TempHome() as h:
            h.file("report.pdf")
            h.file("photo.jpg")
            h.file("notes.unknownext")
            h.file("shortcut.lnk")
            h.file("movie.mp4.crdownload")
            h.file(".hidden")
            h.file("fresh.docx", age=None)  # just written
            (h.desktop / "Project").mkdir()
            result = h.run("tidy-files", "preview", h.tidy_params())
            self.assertTrue(result["ok"], result)
            data = result["data"]
            moving = {i["name"]: i for i in data["items"] if i["status"] == "move"}
            keeping = {i["name"]: i for i in data["items"] if i["status"] == "keep"}
            self.assertEqual(set(moving), {"report.pdf", "photo.jpg", "notes.unknownext"})
            self.assertEqual(moving["report.pdf"]["category"], "Documents")
            self.assertEqual(moving["photo.jpg"]["category"], "Images")
            self.assertEqual(moving["notes.unknownext"]["category"], "Other")
            self.assertIn("shortcut.lnk", keeping)
            self.assertIn("movie.mp4.crdownload", keeping)
            self.assertIn("fresh.docx", keeping)
            self.assertIn("Project", keeping)
            self.assertNotIn(".hidden", moving)
            self.assertNotIn(".hidden", keeping)
            self.assertTrue((h.desktop / "report.pdf").exists(), "preview must not move anything")

    def test_run_then_undo_restores_everything(self):
        with TempHome() as h:
            names = ["a.pdf", "b.xlsx", "c.png", "季度报价单.xlsx", "with space.txt"]
            for name in names:
                h.file(name)
            events = []
            result = h.run("tidy-files", "run", h.tidy_params(), events)
            self.assertTrue(result["ok"], result)
            self.assertEqual(result["data"]["moved"], len(names))
            self.assertEqual([n for n in names if (h.desktop / n).exists()], [])
            self.assertTrue((h.library / "Spreadsheets" / "季度报价单.xlsx").exists())
            self.assertEqual(len([e for e in events if e.get("status") == "moved"]), len(names))

            status = h.run("tidy-files", "status", h.tidy_params())
            self.assertEqual(status["data"]["pending"], 0)
            self.assertTrue(status["data"]["available"]["undo"])

            undone = h.run("tidy-files", "undo", h.tidy_params())
            self.assertTrue(undone["ok"], undone)
            self.assertEqual(undone["data"]["restored"], len(names))
            for name in names:
                self.assertTrue((h.desktop / name).exists(), name)
            self.assertFalse(h.library.exists(), "folders created by the run are removed again")
            again = h.run("tidy-files", "status", h.tidy_params())
            self.assertFalse(again["data"]["available"]["undo"])

    def test_never_overwrites_existing_files(self):
        with TempHome() as h:
            h.file("report.pdf", "new")
            h.file("report.pdf", "old", folder=h.library / "Documents")
            result = h.run("tidy-files", "run", h.tidy_params())
            self.assertTrue(result["ok"], result)
            self.assertEqual((h.library / "Documents" / "report.pdf").read_text(encoding="utf-8"), "old")
            self.assertEqual((h.library / "Documents" / "report (2).pdf").read_text(encoding="utf-8"), "new")

    def test_undo_keeps_a_new_file_that_took_the_old_name(self):
        with TempHome() as h:
            h.file("plan.txt", "first")
            h.run("tidy-files", "run", h.tidy_params())
            h.file("plan.txt", "second")
            h.run("tidy-files", "undo", h.tidy_params())
            self.assertEqual((h.desktop / "plan.txt").read_text(encoding="utf-8"), "second")
            restored = [p for p in h.desktop.iterdir() if p.name.startswith("plan") and p.name != "plan.txt"]
            self.assertEqual(len(restored), 1)
            self.assertEqual(restored[0].read_text(encoding="utf-8"), "first")

    def test_custom_categories_use_keywords_first(self):
        with TempHome() as h:
            h.file("invoice-2026-10.pdf")
            h.file("manual.pdf")
            categories = [{"name": "Invoices", "keywords": ["invoice"]}, {"name": "PDFs", "extensions": ["pdf"]}]
            result = h.run("tidy-files", "preview", h.tidy_params(categories=categories))
            moving = {i["name"]: i["category"] for i in result["data"]["items"] if i["status"] == "move"}
            self.assertEqual(moving, {"invoice-2026-10.pdf": "Invoices", "manual.pdf": "PDFs"})

    def test_group_by_month(self):
        with TempHome() as h:
            h.file("a.pdf")
            result = h.run("tidy-files", "run", h.tidy_params(group_by_month=True))
            self.assertTrue(result["ok"])
            months = list((h.library / "Documents").iterdir())
            self.assertEqual(len(months), 1)
            self.assertRegex(months[0].name, r"^\d{4}-\d{2}$")

    def test_refuses_folders_outside_home(self):
        with TempHome() as h:
            outside = Path(tempfile.mkdtemp(prefix="orbit-outside-"))
            try:
                (outside / "x.pdf").write_text("x", encoding="utf-8")
                result = h.run("tidy-files", "run", h.tidy_params(source=str(outside)))
                self.assertFalse(result["ok"])
                self.assertTrue((outside / "x.pdf").exists())
                home = h.run("tidy-files", "preview", h.tidy_params(source=str(h.home)))
                self.assertFalse(home["ok"])
            finally:
                for p in outside.iterdir():
                    p.unlink()
                outside.rmdir()

    def test_nothing_to_do(self):
        with TempHome() as h:
            result = h.run("tidy-files", "run", h.tidy_params())
            self.assertTrue(result["ok"])
            self.assertEqual(result["data"]["moved"], 0)
            undo = h.run("tidy-files", "undo", h.tidy_params())
            self.assertTrue(undo["ok"])
            self.assertEqual(undo["data"]["restored"], 0)

    def test_custom_categories_cannot_be_paths_on_either_platform(self):
        with TempHome() as h:
            h.file("a.pdf")
            for category in (str(h.base / "outside"), "../outside", "nested/folder", "nested\\folder",
                             "C:\\outside", "C:outside", "..", "CON", "NUL.txt"):
                with self.subTest(category=category):
                    result = h.run("tidy-files", "run", h.tidy_params(categories=[{"name": category, "extensions": ["pdf"]}]))
                    self.assertFalse(result["ok"], result)
                    self.assertTrue((h.desktop / "a.pdf").exists())

    def test_archive_category_symlink_is_left_untouched(self):
        with TempHome() as h:
            h.file("a.pdf")
            outside = h.base / "outside"
            outside.mkdir()
            h.library.mkdir()
            try:
                (h.library / "Documents").symlink_to(outside, target_is_directory=True)
            except OSError:
                self.skipTest("Creating directory links requires permission on this platform")
            result = h.run("tidy-files", "run", h.tidy_params())
            self.assertEqual(result["data"]["moved"], 0)
            self.assertTrue((h.desktop / "a.pdf").exists())
            self.assertEqual(list(outside.iterdir()), [])

    def test_source_changed_after_scan_stays(self):
        with TempHome() as h:
            src = h.file("a.pdf", "first")
            def change_after_scan(_paths):
                src.write_text("new content", encoding="utf-8")
                return set()
            with patch.object(tidy, "open_files_mac", side_effect=change_after_scan):
                result = tidy.op_run(context(h))
            self.assertEqual(result["data"]["moved"], 0)
            self.assertEqual(src.read_text(encoding="utf-8"), "new content")

    def test_source_replaced_immediately_before_move_stays(self):
        with TempHome() as h:
            src = h.file("a.pdf", "first")
            move = tidy.move_to
            def replace_before_move(source, destination, expected=None):
                replacement = h.file("replacement.pdf", "replacement")
                os.replace(replacement, source)
                return move(source, destination, expected)
            with patch.object(tidy, "open_files_mac", return_value=set()), patch.object(tidy, "move_to", side_effect=replace_before_move):
                result = tidy.op_run(context(h))
            self.assertEqual(result["data"]["moved"], 0)
            self.assertEqual(src.read_text(encoding="utf-8"), "replacement")

    def test_undo_refuses_replaced_file_even_with_same_contents(self):
        with TempHome() as h:
            h.file("a.pdf", "first")
            h.run("tidy-files", "run", h.tidy_params())
            archived = h.library / "Documents" / "a.pdf"
            replacement = h.base / "replacement.pdf"
            shutil.copy2(archived, replacement)
            os.replace(replacement, archived)
            result = h.run("tidy-files", "undo", h.tidy_params())
            self.assertFalse(result["ok"])
            self.assertEqual(result["data"]["restored"], 0)
            self.assertTrue(archived.exists())
            self.assertFalse((h.desktop / "a.pdf").exists())

    def test_undo_hash_detects_content_change_with_restored_size_and_mtime(self):
        with TempHome() as h:
            h.file("a.pdf", "first")
            h.run("tidy-files", "run", h.tidy_params())
            archived = h.library / "Documents" / "a.pdf"
            before = archived.stat()
            archived.write_text("other", encoding="utf-8")
            os.utime(archived, ns=(before.st_atime_ns, before.st_mtime_ns))
            result = h.run("tidy-files", "undo", h.tidy_params())
            self.assertFalse(result["ok"])
            self.assertEqual(result["data"]["restored"], 0)
            self.assertEqual(archived.read_text(encoding="utf-8"), "other")

    def test_partial_undo_retries_only_failed_items(self):
        with TempHome() as h:
            h.file("a.pdf"); h.file("b.pdf")
            h.run("tidy-files", "run", h.tidy_params())
            move = tidy.move_to
            def locked_file(source, destination, expected=None):
                if source.name == "b.pdf":
                    raise PermissionError("temporary file lock")
                return move(source, destination, expected)
            with patch.object(tidy, "move_to", side_effect=locked_file):
                first = tidy.op_undo(context(h))
            self.assertFalse(first["ok"])
            self.assertEqual(first["data"]["restored"], 1)
            self.assertEqual(first["data"]["remaining"], 1)
            self.assertTrue(first["data"]["can_undo"])
            second = tidy.op_undo(context(h))
            self.assertTrue(second["ok"], second)
            self.assertEqual(second["data"]["restored"], 1)
            self.assertEqual(sorted(p.name for p in h.desktop.iterdir()), ["a.pdf", "b.pdf"])
            self.assertFalse(h.library.exists())

    def test_legacy_journal_requires_manual_review_and_is_preserved(self):
        with TempHome() as h:
            archived = h.file("a.pdf", folder=h.library / "Documents")
            c = context(h)
            journal = tidy.runs_dir(c) / "legacy.jsonl"
            kit.append_jsonl(journal, {"type": "done", "src": str(h.desktop / "a.pdf"), "dst": str(archived)})
            original = journal.read_bytes()
            result = tidy.op_undo(c)
            self.assertFalse(result["ok"])
            self.assertEqual(result["data"]["manual_review"], 1)
            self.assertFalse(result["data"]["can_undo"])
            self.assertIn("manual review", result["message"])
            self.assertEqual(journal.read_bytes(), original)
            self.assertTrue(archived.exists())

    def test_cross_volume_moves_do_not_copy_or_delete(self):
        with TempHome() as h:
            src = h.file("a.pdf", "original")
            with patch.object(tidy, "exclusive_move", side_effect=OSError(errno.EXDEV, "different volume")), patch.object(tidy.shutil, "copy2") as copy:
                with self.assertRaises(OSError):
                    tidy.move_to(src, h.library / "Documents" / src.name, tidy.fingerprint(src))
            copy.assert_not_called()
            self.assertEqual(src.read_text(encoding="utf-8"), "original")

    def test_detected_cloud_placeholders_are_not_opened(self):
        for flag in (0x400, 0x1000, 0x40000, 0x400000):
            self.assertTrue(tidy.unavailable(SimpleNamespace(st_file_attributes=flag, st_flags=0)))
        self.assertTrue(tidy.unavailable(SimpleNamespace(st_file_attributes=0, st_flags=tidy.DATALESS_FLAG)))
        with TempHome() as h:
            h.file("remote.icloud")
            result = h.run("tidy-files", "preview", h.tidy_params())
            self.assertEqual(result["data"]["pending"], 0)
            self.assertEqual(result["data"]["items"][0]["status"], "keep")
            c = context(h)
            with patch.object(tidy, "unavailable", return_value=True), patch.object(tidy.os, "open") as opened:
                with self.assertRaises(OSError):
                    tidy.fingerprint(h.desktop / "remote.icloud")
            opened.assert_not_called()

    def test_changed_folder_descendant_prevents_undo(self):
        with TempHome() as h:
            h.file("child.txt", "before", folder=h.desktop / "Project")
            result = h.run("tidy-files", "run", h.tidy_params(include_folders=True))
            self.assertEqual(result["data"]["moved"], 1, result)
            archived = h.library / "Folders" / "Project"
            (archived / "child.txt").write_text("after", encoding="utf-8")
            result = h.run("tidy-files", "undo", h.tidy_params())
            self.assertFalse(result["ok"])
            self.assertTrue(archived.exists())

    def test_completed_move_with_missing_done_record_can_be_recovered(self):
        with TempHome() as h:
            src = h.file("a.pdf", "first")
            c = context(h)
            destination = h.library / "Documents" / src.name
            destination.parent.mkdir(parents=True)
            journal = tidy.runs_dir(c) / "interrupted.jsonl"
            evidence = tidy.fingerprint(src)
            kit.append_jsonl(journal, {"type": "intent", "src": str(src), "dst": str(destination),
                                      "fingerprint": evidence, "source_parent": tidy.parent_identity(src.parent),
                                      "archive_parent": tidy.parent_identity(destination.parent)})
            tidy.move_to(src, destination, evidence)
            result = tidy.op_undo(c)
            self.assertTrue(result["ok"], result)
            self.assertEqual(src.read_text(encoding="utf-8"), "first")

    def test_undo_refuses_replaced_parent_directory(self):
        with TempHome() as h:
            h.file("a.pdf")
            h.run("tidy-files", "run", h.tidy_params())
            original_desktop = h.home / "Old Desktop"
            h.desktop.rename(original_desktop)
            outside = h.base / "outside"
            outside.mkdir()
            try:
                h.desktop.symlink_to(outside, target_is_directory=True)
            except OSError:
                self.skipTest("Creating directory links requires permission on this platform")
            result = h.run("tidy-files", "undo", h.tidy_params())
            self.assertFalse(result["ok"])
            self.assertEqual(list(outside.iterdir()), [])
            self.assertTrue((h.library / "Documents" / "a.pdf").exists())

    def test_interrupted_restore_is_not_attempted_twice(self):
        with TempHome() as h:
            h.file("a.pdf")
            h.run("tidy-files", "run", h.tidy_params())
            c = context(h)
            journal, records = tidy.last_undoable(c)
            record = tidy.moves_of(records)[0]
            archived, original = Path(record["dst"]), Path(record["src"])
            kit.append_jsonl(journal, {"type": "restore_intent", "src": str(archived), "dst": str(original),
                                      "move_src": record["src"], "move_dst": record["dst"],
                                      "fingerprint": record["fingerprint"]})
            tidy.move_to(archived, original, record["fingerprint"])
            self.assertIsNone(tidy.last_undoable(c))
            self.assertTrue(original.exists())


if __name__ == "__main__":
    unittest.main()
