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

    def test_subject_cards_and_primary_action_positions(self):
        self.app.configure()
        self.assertEqual(self.app.chrome.pack_slaves()[0], self.app.chrome_back)
        self.assertEqual(self.app.chrome_back.winfo_manager(), "pack")
        self.assertEqual(
            {name for _, name in self.app._subject_cards}, {q.subject for q in self.app.questions}
        )
        self.app._select_subject("Science")
        self.assertEqual(self.app.subject.get(), "Science")
        self.assertEqual(self.app.start_button.pack_info()["side"], "left")
        self.app.start_quiz(self.app.questions[:2])
        self.assertEqual(self.app.submit_button.pack_info()["side"], "left")
        self.assertFalse(
            any(isinstance(w, ttk.Progressbar) for w in self.app.body.winfo_children())
        )
        self.app.answer.set(self.app.engine.current.answer)
        self.app.submit_button.invoke()
        self.assertEqual(self.app.next_button.pack_info()["side"], "left")

    def test_count_changes_update_start_label_immediately(self):
        self.app.configure()
        self.app.count.set("2")
        self.assertIn("2", self.app.start_button.cget("text"))
        self.app.count_box.set("1")
        self.assertIn("1", self.app.start_button.cget("text"))
        self.app.start_button.invoke()
        self.assertEqual(len(self.app.engine.questions), 1)

    def test_daily_practice_starts_directly_from_saved_filters(self):
        self.app.learning_plan.set_settings("public", "English", "easy", 3)
        self.app.start_daily_practice()
        self.assertEqual(len(self.app.engine.questions), 3)
        self.assertEqual(self.app._practice_bank_kind, "public")
        self.assertEqual(self.app._last_filters["subject"], "English")
        self.assertEqual(self.app._last_filters["difficulty"], "easy")

    def test_wheel_control_setting_and_persistence(self):
        from types import SimpleNamespace

        self.app.configure()
        box = self.app.topic_box
        box.current(0)
        event = SimpleNamespace(widget=box, delta=-120)
        self.assertEqual(self.app._control_wheel(event), "break")
        self.assertEqual(box.current(), 0)
        self.app.display["wheel_controls"] = True
        self.app._control_wheel(event)
        self.assertEqual(box.current(), 1)
        self.app.settings()
        self.app.wheel_choice.set(True)
        self.app.save_display()
        self.assertTrue(self.app.display_store.load()["wheel_controls"])

    def test_quiz_actions_remain_visible_when_content_scrolls(self):
        self.root.deiconify()
        self.root.geometry("960x640")
        self.app.start_quiz(self.app.questions[:2])
        self.root.update()
        self.assertEqual(self.app.submit_button.master, self.app.action_dock)
        self.assertTrue(self.app.submit_button.winfo_ismapped())
        position = self.app.action_dock.winfo_rooty()
        header = self.app.quiz_progress_header
        header_position = header.winfo_rooty()
        self.assertIs(header.master, self.app.outer)
        self.assertFalse(any(isinstance(w, tk.Canvas) for w in self.app.body.winfo_children()))
        self.app.canvas.yview_moveto(1)
        self.root.update()
        self.assertEqual(self.app.action_dock.winfo_rooty(), position)
        self.assertEqual(header.winfo_rooty(), header_position)
        self.assertTrue(header.winfo_ismapped())
        q = self.app.engine.current
        self.assertEqual(self.app.option_buttons[0].cget("text"), q.options[0])
        self.app.answer.set(q.answer)
        self.app.submit_button.invoke()
        self.root.update()
        self.assertFalse(self.app.submit_button.winfo_ismapped())
        self.assertTrue(self.app.next_button.winfo_ismapped())
        self.app.next_button.invoke()
        self.assertEqual(self.app.engine.index, 1)

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
