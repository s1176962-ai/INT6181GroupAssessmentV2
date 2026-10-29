"""Real Tk widgets with isolated progress; no user interaction required."""

import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from tkinter import ttk
from unittest.mock import patch

from learning_platform.gui import Application


class GuiTests(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f"Tk display unavailable: {exc}")
        self.root.withdraw()
        self.addCleanup(self.root.destroy)
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.app = Application(self.root, progress_path=Path(temp.name) / "progress.json")
        self.app.enter_guest()
        self.root.update()

    def test_full_quiz_review_and_history_flow(self):
        self.app.configure()
        self.app.subject.set("Mathematics")
        self.app.refresh_filters()
        self.app.topic.set("Geometry")
        self.app.refresh_difficulties()
        self.app.count.set("2")
        self.app.start_configured()
        self.assertEqual(len(self.app.engine.questions), 2)
        self.assertTrue(self.app.images)
        question = self.app.engine.current
        self.app.answer.set(next(x for x in question.options if x != question.answer))
        self.app.submit_button.invoke()
        self.assertTrue(self.app.submit_button.instate(["disabled"]))
        self.assertTrue(all(button.instate(["disabled"]) for button in self.app.option_buttons))
        self.app.submit_button.invoke()
        self.assertEqual(len(self.app.engine.answers), 1)
        self.app.next_button.invoke()
        self.app.answer.set(self.app.engine.current.answer)
        self.app.submit_button.invoke()
        self.app.next_button.invoke()
        self.assertIsNone(self.app.engine)
        self.app.notebook()
        self.app.start_quiz([question], review=True)
        self.app.answer.set(question.answer)
        self.app.submit_button.invoke()
        self.app.next_button.invoke()
        self.assertEqual(self.app.progress.load()["wrong"], {})
        self.app.history()
        self.assertEqual(len(self.app.progress.load()["history"]), 2)
        self.root.update()

    def test_missing_and_invalid_images_fall_back(self):
        self.app.show_image("assets/missing.png")
        self.app.show_image("data/questions/english.json")
        self.app.show_image("../outside.png")
        labels = [
            w.cget("text") for w in self.app.body.winfo_children() if isinstance(w, ttk.Label)
        ]
        self.assertEqual(sum("图片无法显示" in str(text) for text in labels), 3)

    def test_missing_question_in_notebook(self):
        q = self.app.questions[0]
        self.app.start_quiz([q])
        self.app.answer.set(next(x for x in q.options if x != q.answer))
        self.app.submit()
        del self.app.by_id[q.id]
        self.app.notebook()
        self.assertIn(q.id, self.app.progress.load()["wrong"])

    def test_invalid_input_and_empty_notebook(self):
        self.app.notebook()
        self.app.history()
        self.app.configure()
        self.app.count.set("abc")
        with patch("learning_platform.gui.messagebox.showerror") as error:
            self.app.start_configured()
            error.assert_called_once()
        self.app.start_quiz([self.app.questions[0]])
        with patch("learning_platform.gui.messagebox.showerror") as error:
            self.app.submit()
            error.assert_called_once()
        self.assertFalse(self.app.engine.submitted)

    def test_empty_bank_and_corrupt_progress(self):
        self.app.questions = []
        self.app.configure()
        self.app.progress.store.path.write_text("{bad", encoding="utf-8")
        self.app.home()
        self.app.history()
        self.app.notebook()
        with patch("learning_platform.gui.messagebox.showerror") as error:
            self.app.start_quiz([self.app.questions[0]])
            error.assert_called_once()

    def test_login_password_toggle_error_and_narrow_layout(self):
        self.app.logout()
        self.app.login_page()
        self.assertEqual(self.app.password_entries[0].cget("show"), "•")
        self.app.password_toggle.invoke()
        self.assertEqual(self.app.password_entries[0].cget("show"), "")
        self.app.password_toggle.invoke()
        self.assertEqual(self.app.password_entries[0].cget("show"), "•")
        self.app.login_button.invoke()
        self.assertIn("请输入用户名", self.app.login_error.cget("text"))
        self.app.login_page(True)
        self.assertIn("注册并进入", self.app.login_button.cget("text"))
        self.root.geometry("700x620")
        self.root.update()
        self.app._layout_login()
        self.root.geometry("1100x720")
        self.root.update()
        self.app._layout_login()
        self.app.enter_guest()
        self.assertTrue(self.app.signed_in)


if __name__ == "__main__":
    unittest.main()
