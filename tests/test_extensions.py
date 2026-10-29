"""Account isolation, reversible maintenance and real image/form integration."""

import shutil
import tempfile
import tkinter as tk
import unittest
from dataclasses import asdict, replace
from pathlib import Path
from unittest.mock import patch

from learning_platform.auth import AuthService
from learning_platform.gui import ROOT, Application
from learning_platform.maintenance import QuestionEditor, import_image
from learning_platform.repositories import ProgressRepository, QuestionRepository
from learning_platform.services import QuizEngine
from learning_platform.storage import DataError, JsonStore


class ExtensionTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.folder = Path(temp.name)
        self.auth = AuthService(self.folder / "data")
        self.bank_folder = self.folder / "data/questions"
        shutil.copytree(ROOT / "data/questions", self.bank_folder)
        self.question = QuestionRepository(self.bank_folder).all()[0]
        self.editor = QuestionEditor(self.bank_folder)

    def test_register_login_and_hash_storage(self):
        user = self.auth.register("Alice", "Password1", "Password1")
        self.assertEqual(self.auth.login(" alice ", "Password1"), user)
        self.assertNotIn("Password1", self.auth.store.path.read_text())
        self.auth.register("Bob", "Password1", "Password1")
        users = self.auth.store.read()
        self.assertNotEqual(users["alice"]["salt"], users["bob"]["salt"])
        self.assertNotEqual(users["alice"]["password_hash"], users["bob"]["password_hash"])
        with self.assertRaises(ValueError):
            self.auth.login("Alice", "wrong")
        with self.assertRaises(ValueError):
            self.auth.login("missing", "Password1")

    def test_account_validation_and_duplicates(self):
        for name, password, confirm in [
            ("ab", "Password1", "Password1"),
            ("../Alice", "Password1", "Password1"),
            ("Alice", "short", "short"),
            ("Alice", "Password1", "different"),
        ]:
            with self.subTest(name=name, password=password), self.assertRaises(ValueError):
                self.auth.register(name, password, confirm)
        self.auth.register("Alice", "Password1", "Password1")
        with self.assertRaises(ValueError):
            self.auth.register("ALICE", "Password1", "Password1")

    def test_user_progress_isolation_and_restart(self):
        alice = self.auth.register("Alice", "Password1", "Password1")
        bob = self.auth.register("Bob", "Password1", "Password1")
        repository = ProgressRepository(self.auth.progress_path(alice))
        QuizEngine([self.question], repository).submit(self.question.answer)
        self.assertEqual(
            len(ProgressRepository(self.auth.progress_path(alice)).load()["history"]), 1
        )
        self.assertEqual(ProgressRepository(self.auth.progress_path(bob)).load()["history"], [])
        self.assertEqual(AuthService(self.folder / "data").login("Alice", "Password1"), alice)

    def test_corrupt_account_data_preserved(self):
        for bad in ([], {"x": {}}, {"x": {"name": 1}}):
            self.auth.store.write(bad)
            before = self.auth.store.path.read_bytes()
            with self.assertRaises(DataError):
                self.auth.register("Alice", "Password1", "Password1")
            self.assertEqual(self.auth.store.path.read_bytes(), before)

    def test_crud_backup_and_stale_edit(self):
        new = replace(self.question, id="CUSTOM001", subject="New Subject")
        self.editor.save(new)
        self.assertIn(new, QuestionRepository(self.bank_folder).all())
        changed = replace(new, explanation="Updated explanation")
        self.editor.save(changed, new)
        backups = list((self.folder / "data/backups").glob("*.json"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(JsonStore(backups[0], []).read()[0]["explanation"], new.explanation)
        with self.assertRaises(ValueError):
            self.editor.save(replace(new, explanation="Stale"), new)
        self.editor.delete(changed)
        self.assertNotIn(changed.id, {q.id for q in QuestionRepository(self.bank_folder).all()})
        self.assertEqual(len(list((self.folder / "data/backups").glob("*.json"))), 2)

    def test_duplicate_and_invalid_source_preserved(self):
        with self.assertRaises(ValueError):
            self.editor.save(self.question)
        path = self.bank_folder / "broken.json"
        path.write_text("{bad", encoding="utf-8")
        with self.assertRaises(DataError):
            self.editor.save(replace(self.question, id="NEW001"))
        self.assertEqual(path.read_text(), "{bad")

    def test_edit_retains_unknown_fields_and_other_bad_records(self):
        path = self.bank_folder / "english.json"
        original = {**asdict(self.question), "teacher_note": "keep me"}
        JsonStore(path, []).write([original, {"bad_record": True}])
        self.editor.save(replace(self.question, explanation="Edited"), self.question)
        records = JsonStore(path, []).read()
        self.assertEqual(records[0]["teacher_note"], "keep me")
        self.assertEqual(records[1], {"bad_record": True})

    def test_backup_failure_does_not_modify_bank(self):
        before = (self.bank_folder / "english.json").read_bytes()
        with patch("learning_platform.maintenance.shutil.copy2", side_effect=OSError("denied")):
            with self.assertRaises(DataError):
                self.editor.delete(self.question)
        self.assertEqual((self.bank_folder / "english.json").read_bytes(), before)


class ExtensionGuiTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.folder = Path(temp.name)
        shutil.copytree(ROOT / "data/questions", self.folder / "data/questions")
        shutil.copytree(ROOT / "assets", self.folder / "assets")
        try:
            self.root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(str(exc))
        self.root.withdraw()
        self.addCleanup(self.root.destroy)
        self.app = Application(self.root, project_root=self.folder)

    def register(self, admin=False):
        self.app.login_page(True)
        self.app.login_name.set("Student")
        self.app.login_password.set("Password1")
        self.app.login_confirm.set("Password1")
        self.app.login_button.invoke()
        self.assertTrue(self.app.wait_login())
        if admin:
            users = self.app.auth.store.read()
            users["student"]["role"] = "admin"
            self.app.auth.store.write(users)
            self.app.user = self.app.auth.require_session(self.app.user)

    def test_login_register_logout_and_guest_preservation(self):
        guest = ProgressRepository(self.folder / "data/progress.json")
        q = self.app.questions[0]
        QuizEngine([q], guest).submit(q.answer)
        self.register()
        self.assertEqual(self.app.user["name"], "Student")
        self.assertEqual(self.app.progress.load()["history"], [])
        self.app.logout()
        self.app.login_name.set("Student")
        self.app.login_password.set("bad")
        self.app.login_button.invoke()
        self.assertTrue(self.app.wait_login())
        self.assertTrue(self.app.login_error.cget("text"))
        self.app.login_password.set("Password1")
        self.app.login_button.invoke()
        self.assertTrue(self.app.wait_login())
        self.assertEqual(self.app.user["name"], "Student")
        self.app.logout()
        self.app.enter_guest()
        self.assertEqual(len(self.app.progress.load()["history"]), 1)
        with patch("learning_platform.gui.messagebox.showinfo") as info:
            self.app.manage_questions()
            info.assert_called_once()

    def test_upload_save_preview_and_quiz_image(self):
        self.register(admin=True)
        self.app.manage_questions()
        editor = self.app.editor
        editor.edit()
        for field, value in {"subject": "Art", "topic": "Shapes", "difficulty": "easy"}.items():
            editor.fields[field].set(value)
        editor.question_text.insert("1.0", "Which shape is shown?")
        editor.explanation.insert("1.0", "The picture shows a circle.")
        editor.remove_option()
        editor.remove_option()
        editor.rows[0][1].set("Circle")
        editor.rows[1][1].set("Square")
        source = ROOT / "assets/circle.png"
        with patch(
            "learning_platform.editor_ui.filedialog.askopenfilename", return_value=str(source)
        ):
            editor.upload(editor.question_image)
            editor.upload(editor.rows[0][2])
        self.assertTrue((self.folder / editor.question_image.get()).exists())
        editor.preview()
        q = editor.build_question()
        with patch("learning_platform.editor_ui.messagebox.showinfo"):
            editor.save()
        self.assertIn(q.id, self.app.by_id)
        editor.search.set(q.id)
        editor.refresh_list()
        self.assertEqual(editor.table.get_children(), (q.id,))
        self.app.start_quiz([self.app.by_id[q.id]])
        self.assertEqual(len(self.app.images), 2)
        self.app.answer.set("Circle")
        self.app.submit()
        self.assertEqual(self.app.engine.result()["score"], 1)

    def test_cancel_unsaved_and_confirm_delete(self):
        self.register(admin=True)
        self.app.manage_questions()
        editor = self.app.editor
        q = self.app.questions[0]
        editor.edit(q)
        editor.fields["topic"].set("Changed")
        with patch("learning_platform.editor_ui.messagebox.askyesno", return_value=False):
            editor.cancel()
        self.assertTrue(editor.editing)
        with patch("learning_platform.editor_ui.messagebox.askyesno", return_value=True):
            editor.cancel()
        editor.table.selection_set(q.id)
        with patch("learning_platform.editor_ui.messagebox.askyesno", return_value=True):
            editor.delete_selected()
        self.assertNotIn(q.id, self.app.by_id)

    def test_invalid_upload_and_unique_paths(self):
        with self.assertRaises(ValueError):
            import_image(self.folder, ROOT / "main.py", self.root)
        bad = self.folder / "bad.png"
        bad.write_text("invalid", encoding="utf-8")
        with self.assertRaises(ValueError):
            import_image(self.folder, bad, self.root)
        source = ROOT / "assets/circle.png"
        first = import_image(self.folder, source, self.root)
        second = import_image(self.folder, source, self.root)
        self.assertNotEqual(first, second)
        self.assertEqual((self.folder / first).read_bytes(), source.read_bytes())


if __name__ == "__main__":
    unittest.main()
