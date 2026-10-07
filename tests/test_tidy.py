import os
import tempfile
import unittest
from pathlib import Path

from helpers import TempHome


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


if __name__ == "__main__":
    unittest.main()
