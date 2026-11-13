import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from unittest.mock import patch

from learning_platform.gui import Application
from learning_platform.repositories import PersonalQuestionRepository

ROOT = Path(__file__).resolve().parents[1]


class ImportUiTests(unittest.TestCase):
    def test_personal_preview_confirm_and_failed_replacement(self):
        root = tk.Tk()
        self.addCleanup(root.destroy)
        root.withdraw()
        with tempfile.TemporaryDirectory() as folder:
            app = Application(root, progress_path=Path(folder) / "progress.json")
            app.user = app.auth.register("Importer", "Password1", "Password1")
            app.personal_bank = PersonalQuestionRepository(
                app.auth.personal_questions_path(app.user)
            )
            app.personal_bank_page()
            with patch(
                "learning_platform.gui.filedialog.askopenfilename",
                return_value=str(ROOT / "examples/import_test_json.json"),
            ):
                app.choose_import_file()
            self.assertEqual(len(app.import_preview.valid), 3)
            for item in app.import_table.get_children():
                self.assertEqual(app.import_table.item(item, "values")[-1], "Validation passed")
            self.assertNotIn("disabled", app.import_confirm.state())
            with (
                patch("learning_platform.gui.messagebox.askyesno", return_value=True),
                patch("learning_platform.gui.messagebox.showinfo"),
            ):
                app.confirm_personal_import()
            self.assertEqual(len(app.personal_bank.all()), 3)
            app.configure()
            app.practice_bank_picker.select(1)
            self.assertEqual(app._practice_bank_kind, "personal")
            self.assertEqual(app.subject.get(), "Import Lab")
            self.assertEqual({q.subject for q in app.questions}, {"Import Lab"})
            app.start_configured()
            self.assertEqual(len(app.engine.questions), 3)
            self.assertTrue(all(q.id.startswith("DEMO-J-") for q in app.engine.questions))
            app.engine = None
            app.personal_bank_page()
            with patch(
                "learning_platform.gui.filedialog.askopenfilename",
                return_value=str(ROOT / "examples/import_test_csv.csv"),
            ):
                app.choose_import_file()
            with (
                patch(
                    "learning_platform.gui.filedialog.askopenfilename",
                    return_value=str(Path(folder) / "missing.csv"),
                ),
                patch("learning_platform.gui.messagebox.showerror"),
            ):
                app.choose_import_file()
            self.assertIsNone(app.import_preview)
            self.assertIn("disabled", app.import_confirm.state())
            self.assertEqual(app.import_table.get_children(), ())
