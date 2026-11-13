import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from learning_platform.gui import Application
from learning_platform.repositories import ProgressRepository


class HistoryPageTests(unittest.TestCase):
    def test_filtered_journal_includes_notes_and_like(self):
        root = tk.Tk()
        self.addCleanup(root.destroy)
        root.withdraw()
        with tempfile.TemporaryDirectory() as folder:
            app = Application(root, progress_path=Path(folder) / "progress.json")
            app.user = app.auth.register("Journal", "Password1", "Password1")
            app.progress = ProgressRepository(app.auth.progress_path(app.user))
            record = {
                "id": "session-1",
                "date": "2026-11-13T08:15:10+08:00",
                "subject": "English",
                "mode": "quiz",
                "total": 2,
                "correct": 1,
                "incorrect": 1,
                "accuracy": 50.0,
                "score": 1,
                "max_score": 2,
            }
            app.progress.save({"wrong": {}, "history": [record]})
            app.history()
            page = app.history_page
            with patch.object(page, "refresh") as refresh:
                button = Mock()
                page.like(page.matches[0], button)
                refresh.assert_not_called()
                self.assertTrue(page.matches[0]["liked"])
                self.assertEqual(button.configure.call_args.kwargs["text"], "♥")
                page.like(page.matches[0], button)
                self.assertFalse(page.matches[0]["liked"])
            page.like(page.matches[0])
            page.notes.save(record["id"], True, "Remember the irregular plural.")
            page.liked.set(app.tr("是"))
            page.commented.set(app.tr("是"))
            page.refresh()
            root.update_idletasks()
            self.assertEqual(len(page.matches), 1)
            self.assertEqual(page.matches[0]["note"], "Remember the irregular plural.")
