"""Regression tests for authorization, user management and bilingual screens."""

import ast
import shutil
import string
import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from unittest.mock import patch

from learning_platform.auth import AuthService
from learning_platform.gui import ROOT, Application
from learning_platform.i18n import Translator
from learning_platform.maintenance import QuestionEditor
from learning_platform.models import option_label
from learning_platform.repositories import ProgressRepository, QuestionRepository
from learning_platform.services import QuizEngine
from learning_platform.storage import DataError


def seed_admin(auth):
    """Trusted fixture setup mirrors the one-time local upgrade, not registration."""
    user = auth.register("Admin", "Secret1", "Secret1")
    records = auth.store.read()
    records["admin"]["role"] = "admin"
    auth.store.write(records)
    return auth.require_admin(user)


class RoleTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.folder = Path(temp.name)
        self.auth = AuthService(self.folder)
        self.admin = seed_admin(self.auth)
        self.student = self.auth.register("Student", "Secret2", "Secret2")

    def test_registration_cannot_choose_admin_even_with_owner_name(self):
        owner_name = self.auth.register("wutaicheng", "Secret3", "Secret3")
        self.assertEqual(owner_name["role"], "student")
        with self.assertRaises(ValueError):
            self.auth.require_admin(owner_name)

    def test_admin_apis_reject_student_and_forged_cached_role(self):
        forged = {**self.student, "role": "admin"}
        before = self.auth.store.path.read_bytes()
        for actor in (self.student, forged, None):
            actions = [
                lambda: self.auth.list_users(actor),
                lambda: self.auth.create_user(actor, "NewUser", "Secret3"),
                lambda: self.auth.update_user(actor, self.student["id"], "Student", "admin", True),
                lambda: self.auth.user_progress(actor, self.admin["id"]),
            ]
            for action in actions:
                with self.assertRaises(ValueError):
                    action()
        self.assertEqual(self.auth.store.path.read_bytes(), before)

    def test_disabled_login_session_and_reenable(self):
        self.auth.update_user(self.admin, self.student["id"], "Student", "student", False)
        with self.assertRaises(ValueError):
            self.auth.login("Student", "Secret2")
        with self.assertRaises(ValueError):
            self.auth.require_session(self.student)
        self.auth.update_user(self.admin, self.student["id"], "Student", "student", True)
        self.assertEqual(self.auth.login("Student", "Secret2")["id"], self.student["id"])

    def test_admin_create_promote_and_demote(self):
        other = self.auth.create_user(self.admin, "Other", "Secret3", "admin")
        self.assertEqual(self.auth.require_admin(other)["role"], "admin")
        self.auth.update_user(self.admin, other["id"], "Other", "student", True)
        with self.assertRaises(ValueError):
            self.auth.require_admin(other)
        self.auth.update_user(self.admin, self.student["id"], "Student", "admin", True)
        self.assertEqual(self.auth.require_admin(self.student)["role"], "admin")

    def test_last_enabled_admin_protection_is_atomic(self):
        self.auth.create_user(self.admin, "DisabledAdmin", "Secret3", "admin", False)
        before = self.auth.store.path.read_bytes()
        for role, enabled in [("student", True), ("admin", False), ("student", False)]:
            with self.assertRaises(ValueError):
                self.auth.update_user(self.admin, self.admin["id"], "Admin", role, enabled)
            self.assertEqual(self.auth.store.path.read_bytes(), before)

    def test_rename_reset_and_learning_data_keep_uuid(self):
        q = QuestionRepository(ROOT / "data/questions").all()[0]
        progress = ProgressRepository(self.auth.progress_path(self.student))
        QuizEngine([q], progress).submit(next(o for o in q.options if o != q.answer))
        before = progress.store.path.read_bytes()
        renamed = self.auth.update_user(
            self.admin, self.student["id"], "Renamed", "student", True, "New123"
        )
        self.assertEqual(renamed["id"], self.student["id"])
        self.assertEqual(progress.store.path.read_bytes(), before)
        with self.assertRaises(ValueError):
            self.auth.login("Student", "Secret2")
        with self.assertRaises(ValueError):
            self.auth.login("Renamed", "Secret2")
        self.assertEqual(self.auth.login("Renamed", "New123")["id"], renamed["id"])
        data = self.auth.user_progress(self.admin, renamed["id"])
        self.assertIn(q.id, data["wrong"])
        self.assertEqual(len(data["history"]), 1)
        for user in self.auth.list_users(self.admin):
            self.assertNotIn("password_hash", user)
            self.assertNotIn("salt", user)

    def test_password_boundaries_and_duplicate_rename(self):
        for size in (6, 16):
            self.auth.register(f"User{size}", "x" * size, "x" * size)
            self.auth.update_user(
                self.admin, self.student["id"], "Student", "student", True, "x" * size
            )
        before = self.auth.store.path.read_bytes()
        for size in (0, 5, 17, 128):
            with self.assertRaises(ValueError):
                self.auth.register(f"Bad{size}", "x" * size, "x" * size)
            if size:
                with self.assertRaises(ValueError):
                    self.auth.update_user(
                        self.admin, self.student["id"], "Student", "student", True, "x" * size
                    )
        with self.assertRaises(ValueError):
            self.auth.update_user(self.admin, self.student["id"], "ADMIN", "student", True)
        self.assertEqual(self.auth.store.path.read_bytes(), before)

    def test_legacy_account_and_password_compatibility(self):
        data = self.auth.store.read()
        record = data["student"]
        record.pop("role")
        record.pop("enabled")
        record["password_hash"] = self.auth._hash("x" * 30, record["salt"])
        self.auth.store.write(data)
        before = self.auth.store.path.read_bytes()
        user = self.auth.login("Student", "x" * 30)
        self.assertEqual(user["role"], "student")
        self.assertTrue(user["enabled"])
        self.assertEqual(self.auth.store.path.read_bytes(), before)

    def test_question_repository_rechecks_revoked_admin(self):
        bank = self.folder / "questions"
        shutil.copytree(ROOT / "data/questions", bank)
        other = self.auth.create_user(self.admin, "Other", "Secret3", "admin")
        editor = QuestionEditor(bank, lambda: self.auth.require_admin(other))
        q = QuestionRepository(bank).all()[0]
        self.auth.update_user(self.admin, other["id"], "Other", "student", True)
        before = (bank / "english.json").read_bytes()
        with self.assertRaises(ValueError):
            editor.delete(q)
        self.assertEqual((bank / "english.json").read_bytes(), before)


class LanguageTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.folder = Path(temp.name)
        self.tr = Translator(self.folder)

    def test_new_profile_starts_in_english(self):
        """The initial language is English; do not silently switch to Chinese."""
        self.assertEqual(self.tr.language, "en")
        self.assertEqual(self.tr.store.read()["language"], "en")
        self.assertEqual(self.tr("开始练习"), "Start a quiz")
        self.assertEqual(Translator(Path(tempfile.mkdtemp())).language, "en")

    def test_save_reload_and_preserve_question_text(self):
        self.tr.set_language("en")
        tr = Translator(self.folder)
        self.assertEqual(tr("开始练习"), "Start a quiz")
        self.assertEqual(tr("你好，{0}。", "中文用户名"), "Hello, 中文用户名.")
        tr.set_language("zh")
        self.assertEqual(tr("开始练习"), "开始练习")

    def test_catalog_coverage_and_placeholders(self):
        for filename in ("gui.py", "editor_ui.py", "user_ui.py"):
            tree = ast.parse((ROOT / "learning_platform" / filename).read_text(encoding="utf-8"))
            for call in ast.walk(tree):
                if (
                    isinstance(call, ast.Call)
                    and isinstance(call.func, ast.Attribute)
                    and call.func.attr == "tr"
                    and call.args
                    and isinstance(call.args[0], ast.Constant)
                ):
                    self.assertIn(call.args[0].value, self.tr.english)
        formatter = string.Formatter()
        for source, target in self.tr.english.items():
            with self.subTest(message=source):
                self.assertEqual(
                    {f for _, f, _, _ in formatter.parse(source) if f is not None},
                    {f for _, f, _, _ in formatter.parse(target) if f is not None},
                )
                if source != "简体中文":
                    self.assertFalse(any("\u4e00" <= c <= "\u9fff" for c in target))

    def test_invalid_settings_do_not_get_overwritten(self):
        self.tr.store.write({"language": "bad"})
        tr = Translator(self.folder)
        self.assertEqual(tr.language, "zh")
        self.assertTrue(tr.warning)
        with self.assertRaises(DataError):
            tr.set_language("en")
        self.assertEqual(tr.store.read(), {"language": "bad"})

    def test_option_labels(self):
        self.assertEqual([option_label(i) for i in range(4)], list("ABCD"))
        self.assertEqual(option_label(25), "Z")
        self.assertEqual(option_label(26), "AA")
        with self.assertRaises(ValueError):
            option_label(-1)


class RoleGuiTests(unittest.TestCase):
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
        self.admin = seed_admin(self.app.auth)
        self.student = self.app.auth.register("Student", "Secret2", "Secret2")

    def texts(self, parent=None):
        values = []
        if parent is None:
            roots = [self.app.body]
            host = getattr(self.app, "login_host", None)
            if host is not None and str(host) and host.winfo_exists():
                roots.append(host)
        else:
            roots = [parent]
        for root in roots:
            for widget in root.winfo_children():
                try:
                    values.append(str(widget.cget("text")))
                except tk.TclError:
                    pass
                values.extend(self.texts(widget))
        return values

    def enter(self, user):
        self.app.user = user
        self.app.progress = ProgressRepository(self.app.auth.progress_path(user))
        self.app.home()

    def test_admin_only_navigation_and_disabled_session(self):
        self.app.enter_guest()
        self.assertNotIn("users", self.app._nav_buttons)
        self.assertNotIn("questions", self.app._nav_buttons)
        self.enter(self.student)
        self.assertNotIn("users", self.app._nav_buttons)
        self.assertIn("questions", self.app._nav_buttons)
        self.app.manage_questions()
        self.assertEqual(self.app.editor.mode, "personal")
        self.enter(self.admin)
        self.assertIn("users", self.app._nav_buttons)
        self.assertIn("questions", self.app._nav_buttons)
        self.enter(self.student)
        self.app.start_quiz([self.app.questions[0]])
        self.app.answer.set(self.app.questions[0].answer)
        self.app.auth.update_user(self.admin, self.student["id"], "Student", "student", False)
        with patch("learning_platform.gui.messagebox.showinfo"):
            self.app.submit()
        self.assertIsNone(self.app.user)
        self.assertFalse(self.app.auth.progress_path(self.student).exists())

    def test_user_form_create_modify_disable_and_details(self):
        self.enter(self.admin)
        self.app.manage_users()
        page = self.app.users_page
        page.edit()
        page.name.set("Created")
        page.password.set("Secret3")
        page.confirmation.set("Secret3")
        page.save()
        created = self.app.auth.login("Created", "Secret3")
        q = self.app.questions[0]
        QuizEngine([q], ProgressRepository(self.app.auth.progress_path(created))).submit(q.answer)
        page.table.selection_set(created["id"])
        page.details()
        summary = self.app.tr("完成练习：{0} 次；待复习错题：{1} 道。", 1, 0)
        self.assertTrue(any(summary in text for text in self.texts()))
        page.show_list()
        page.table.selection_set(created["id"])
        page.edit_selected()
        page.name.set("Renamed")
        page.role.set("admin")
        page.enabled.set(False)
        page.save()
        with self.assertRaises(ValueError):
            self.app.auth.login("Renamed", "Secret3")
        updated = next(u for u in self.app.auth.list_users(self.admin) if u["id"] == created["id"])
        page.edit(updated)
        page.enabled.set(True)
        page.save()
        self.assertEqual(self.app.auth.login("Renamed", "Secret3")["role"], "admin")

    def test_english_settings_and_quiz_notebook_labels(self):
        self.app.settings()
        self.app.language.set("en")
        self.app.save_language()
        self.assertIn("Interface language", self.texts())
        self.app.login_page(True)
        self.assertIn("Register and continue", self.texts())
        self.assertEqual(Translator(self.folder / "data").language, "en")
        self.app.enter_guest()
        self.app.configure()
        self.assertEqual(self.app.topic.get(), "All")
        q = self.app.questions[0]
        self.app.start_quiz([q])
        self.assertEqual(self.app.option_buttons[0].cget("text"), q.options[0])
        self.app.answer.set(next(o for o in q.options if o != q.answer))
        self.app.submit()
        self.assertIn("Correct answer:", self.app.feedback.cget("text"))
        self.app.results()
        self.app.notebook()
        self.assertIn(f"A: {q.options[0]}", self.texts())
        self.assertIn("Export CSV", self.texts())
        self.app.settings()
        self.app.language.set("zh")
        self.app.save_language()
        self.assertIn("界面语言", self.texts())

    def test_english_admin_and_question_preview(self):
        self.app.tr.set_language("en")
        self.enter(self.admin)
        self.app.manage_users()
        self.assertEqual(self.app.users_page.table.heading("name")["text"], "Username")
        self.app.users_page.edit()
        self.assertIn("Save account", self.texts())
        self.app.home()
        self.app.manage_questions()
        page = self.app.editor
        self.assertEqual(page.table.heading("subject")["text"], "Subject")
        q = self.app.questions[0]
        page.edit(q)
        self.assertEqual(page.rows[0][0].cget("text"), "Option A")
        page.preview()
        windows = [w for w in self.root.winfo_children() if isinstance(w, tk.Toplevel)]
        self.assertIn(f"A: {q.options[0]}", self.texts(windows[-1]))

    def all_texts(self, root):
        """Include Canvas-drawn labels (segmented control, soft buttons, cards)."""
        values = []
        for widget in root.winfo_children():
            try:
                text = str(widget.cget("text"))
                if text.strip():
                    values.append(text)
            except tk.TclError:
                pass
            if isinstance(widget, tk.Canvas):
                for item in widget.find_all():
                    if widget.type(item) == "text":
                        values.append(str(widget.itemcget(item, "text")))
            values.extend(self.all_texts(widget))
        return values

    def assert_no_chinese(self, root):
        for text in self.all_texts(root):
            for char in text:
                self.assertFalse("\u4e00" <= char <= "\u9fff", f"Chinese leaked: {text!r}")

    def test_english_configure_and_quiz_assistant_have_no_chinese(self):
        self.app.tr.set_language("en")
        self.app.enter_guest()
        self.app.configure()
        self.root.update()
        self.assertEqual(self.app.tr.language, "en")
        self.assertEqual(self.app._difficulty_label("easy"), "Easy")
        self.assertEqual(self.app._difficulty_label("medium"), "Medium")
        self.assertEqual(self.app._difficulty_label("hard"), "Hard")
        self.assertEqual(self.app._difficulty_label(self.app.tr("全部")), "All")
        self.assert_no_chinese(self.app.body)

        self.app.start_quiz(self.app.questions[:1])
        self.root.update()
        self.assertTrue(self.app.quiz_ai_button.winfo_exists())
        self.assertTrue(self.app.quiz_ai_reply.winfo_exists())
        # Vertical stack: the reply row is weighted, so it grows with the window.
        self.assertEqual(
            self.app.quiz_ai_panel.grid_rowconfigure(1)["weight"], 1
        )
        self.assert_no_chinese(self.app.quiz_ai_panel)

    def test_quiz_ai_request_follows_the_ui_language(self):
        """An English screen must send an English prompt and ask for English."""
        self.app.tr.set_language("en")
        self.app.enter_guest()
        self.app.configure()
        self.root.update()
        self.app.start_quiz(self.app.questions[:1])
        self.root.update()

        class SyncThread:
            def __init__(self, target=None, daemon=None):
                self.target = target

            def start(self):
                self.target()

        with (
            patch("learning_platform.gui.threading.Thread", SyncThread),
            patch.object(self.app.ai_assistant, "ask", return_value="English hint") as mocked,
        ):
            self.app.ask_current_question_ai()
            self.root.update()
        args, kwargs = mocked.call_args
        self.assertEqual(args[1] if len(args) > 1 else kwargs["language"], "en")
        # Framing instructions are English; the stem/options are question-bank
        # content and may legitimately contain Chinese (ENG001 does).
        lines = args[0].splitlines()
        self.assertEqual(lines[0], "Help me understand this multiple-choice question.")
        self.assertTrue(lines[1].startswith("Question: "))
        self.assertIn("Options:", lines)
        self.assertEqual(
            lines[-1],
            "Give a short hint first, then briefly analyse each option. Answer in English.",
        )
        for line in (lines[0], lines[1].split(": ", 1)[0], lines[-1]):
            self.assertFalse(any("\u4e00" <= char <= "\u9fff" for char in line))

    def test_question_bank_and_user_tables_grow_with_viewport(self):
        self.app.tr.set_language("en")
        self.enter(self.admin)
        self.app.manage_questions()
        self.root.update()
        self.assertEqual(self.app.editor.table.master.grid_rowconfigure(0)["weight"], 1)
        self.app.manage_users()
        self.root.update()
        self.assertEqual(self.app.users_page.table.winfo_manager(), "pack")
        self.assertEqual(self.app.users_page.table.pack_info()["fill"], "both")


if __name__ == "__main__":
    unittest.main()
