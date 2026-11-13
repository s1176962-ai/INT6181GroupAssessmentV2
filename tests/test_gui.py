"""Real Tk widgets with isolated progress; no user interaction required."""

import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from tkinter import ttk
from unittest.mock import patch

from learning_platform.gui import Application
from learning_platform.repositories import (
    LearningPlanRepository,
    PersonalQuestionRepository,
    ProgressRepository,
)


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
        user = self.app.auth.register("GuiTester", "Password1", "Password1")
        self.app.user = user
        self.app.progress = ProgressRepository(self.app.auth.progress_path(user))
        self.app.personal_bank = PersonalQuestionRepository(
            self.app.auth.personal_questions_path(user)
        )
        self.app.learning_plan = LearningPlanRepository(self.app.auth.learning_plan_path(user))
        self.app.home()
        self.root.update()

    def test_guest_cannot_open_notebook_or_history(self):
        self.app.enter_guest()
        with patch("learning_platform.gui.messagebox.showinfo") as info:
            self.app.notebook()
            self.app.history()
        self.assertEqual(info.call_count, 2)
        self.assertNotIn("notebook", self.app._nav_buttons)
        self.assertNotIn("history", self.app._nav_buttons)

    def test_late_valid_battle_decision_is_void_without_damage(self):
        from learning_platform.battle import OpponentDecision

        self.app.battle_page()
        battle = self.app.battle
        battle.start()
        q = battle.questions[0]
        battle.answer(q.answer)
        decision = OpponentDecision(q.id, q.answer, 10, "A valid answer", "api")
        battle.receive_decision(decision, None, 30.01)
        self.assertIsNone(battle.decision)
        self.assertIsNone(battle.planned)
        battle.finish_round()
        self.assertEqual((battle.player_hp, battle.ai_hp), (battle.max_hp, battle.max_hp))
        self.assertEqual(battle.records, [])
        self.assertEqual(battle.next.cget("text"), self.app.tr("重试本题"))
        self.root.after_cancel(battle.timer_id)

    def test_battle_round_renders_question_portrait_and_options(self):
        self.app.battle_page()
        battle = self.app.battle
        battle.start()
        self.root.update()
        self.assertTrue(battle.active)
        self.assertEqual(len(battle.buttons), len(battle.questions[0].options))
        self.assertTrue(battle.portrait.cget("image"))
        battle.show_decision_stage(1)
        text = battle.thinking_status.get("1.0", "end-1c")
        self.assertIn("2 / 3", text)
        self.assertNotIn("1 / 3", text)
        self.assertNotIn("Decision saved", text)
        battle.answer(battle.questions[0].answer)
        self.assertEqual(battle.player.correct, 100)
        battle.active = False
        battle.generation += 1
        self.root.after_cancel(battle.timer_id)

    def test_battle_api_failure_does_not_damage_or_score(self):
        from learning_platform.battle import grade

        self.app.battle_page()
        battle = self.app.battle
        battle.start()
        battle.answer(battle.questions[0].answer)
        battle.ai = grade(False, 31)
        battle.decision_error = "Invalid JSON response"
        battle.finish_round()
        self.assertEqual((battle.player_hp, battle.ai_hp), (battle.max_hp, battle.max_hp))
        self.assertEqual(battle.records, [])
        self.assertEqual(battle.next.cget("text"), self.app.tr("重试本题"))
        self.assertIn("Invalid JSON response", battle.thinking_status.get("1.0", "end-1c"))
        battle.generation += 1
        self.root.after_cancel(battle.timer_id)

    def test_notebook_overflow_shows_scrollbar(self):
        self.root.deiconify()
        self.root.geometry("960x640")
        data = self.app.progress.load()
        for q in self.app.questions[:5]:
            data["wrong"][q.id] = {
                "count": 1,
                "last_answer": q.options[0],
                "last_seen": "2026-11-13T10:00:00+08:00",
            }
        self.app.progress.save(data)
        self.app.notebook()
        self.root.update()
        self.assertTrue(self.app.scrollbar.winfo_ismapped())
        self.app.canvas.yview_moveto(1)
        self.root.update()
        self.assertGreater(self.app.canvas.yview()[0], 0)

    def test_text_only_question_and_feedback_keep_assistant_geometry(self):
        from dataclasses import replace

        self.root.deiconify()
        self.root.geometry("1080x800")
        self.app.motion.enabled = False
        question = replace(self.app.questions[0], question_image=None, option_images=None)
        self.app.start_quiz([question])
        self.root.update()
        self.assertEqual(self.app.images, [])
        panel = self.app.quiz_ai_panel
        before = (panel.winfo_rooty(), panel.winfo_height())
        self.app.answer.set(question.answer)
        with patch.object(self.app.ai_assistant, "ask") as request:
            self.app.submit()
            request.assert_not_called()
        self.assertNotIn("Keep going", self.app.feedback.cget("text"))
        self.root.update()
        self.assertEqual((panel.winfo_rooty(), panel.winfo_height()), before)

    def test_wrong_feedback_is_local_and_selected_option_has_short_label(self):
        self.app.motion.enabled = False
        question = self.app.questions[0]
        self.app.start_quiz([question])
        chosen = next(option for option in question.options if option != question.answer)
        self.app.answer.set(chosen)
        with patch.object(self.app.ai_assistant, "ask") as request:
            self.app.submit()
            request.assert_not_called()
        self.assertEqual(self.app.option_status[chosen].cget("text"), self.app.tr("你的选择"))
        feedback = self.app.feedback.cget("text")
        self.assertNotIn(self.app.tr("再想一想"), feedback)
        self.assertIn(question.answer, feedback)
        self.assertIn(question.explanation, feedback)
        self.assertTrue(feedback.startswith(self.app.tr("回答错误，已记入错题本。")))

    def test_numeric_controls_accept_direct_editing(self):
        self.app.configure()
        timer = self.app.timer_box
        timer.entry.delete(0, "end")
        timer.entry.insert(0, "120")
        self.assertEqual(self.app.timer_seconds.get(), "120")
        timer._commit_entry()
        self.assertEqual(timer.get(), "120")
        count = self.app.count_box
        count.entry.delete(0, "end")
        count.entry.insert(0, "12")
        self.assertEqual(self.app.count.get(), "12")
        count.entry.insert("end", "abc")
        self.assertEqual(count.get(), "12")
        count._commit_entry()
        self.app.start_configured()
        self.assertEqual(len(self.app.engine.questions), 12)

    def test_subject_cards_and_primary_action_positions(self):
        self.app.home()
        self.assertTrue(self.app.home_ai_button.winfo_exists())
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
        self.assertTrue(self.app.quiz_ai_button.winfo_exists())
        self.assertEqual(self.app.submit_button.pack_info()["side"], "left")
        self.assertFalse(
            any(isinstance(w, ttk.Progressbar) for w in self.app.body.winfo_children())
        )
        self.app.answer.set(self.app.engine.current.answer)
        self.app.submit_button.invoke()
        self.assertEqual(self.app.next_button.pack_info()["side"], "left")

    def test_home_ai_card_uses_primary_tints_and_idle_portrait(self):
        from learning_platform import ui_tokens as T

        self.app.home()
        self.root.update_idletasks()
        self.assertEqual(self.app.home_ai_input.cget("bg"), T.AI_INPUT_BG)
        self.assertEqual(self.app.home_ai_reply.cget("bg"), T.AI_REPLY_BG)
        previous = T.theme_name()
        try:
            for theme in ("light", "dark"):
                T.set_theme(theme)
                self.assertNotEqual(T.AI_INPUT_BG, T.HOVER)
                self.assertNotEqual(T.AI_REPLY_BG, T.HOVER)
                self.assertNotEqual(T.AI_REPLY_BG, T.SURFACE)
        finally:
            T.set_theme(previous)
        self.assertEqual(self.app._home_ai_idle.winfo_manager(), "pack")
        self.assertEqual(self.app._home_ai_answer.winfo_manager(), "")
        self.assertIsNotNone(self.app._home_mascot_base())
        self.assertGreaterEqual(int(self.app._home_mascot.cget("width")), T.px(64))
        self.app.home_ai_reply.configure(text="Hint text")
        self.assertEqual(self.app._home_ai_idle.winfo_manager(), "")
        self.assertEqual(self.app._home_ai_answer.winfo_manager(), "pack")
        self.app.home_ai_reply.configure(text="")
        self.assertEqual(self.app._home_ai_idle.winfo_manager(), "pack")

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

    def test_question_art_fills_the_question_column(self):
        from learning_platform.gui import art_factor

        # Source art is 3x the design grid, so a 720px box needs one halving.
        self.assertEqual(art_factor(1440, 810, 720, 420), 2)
        self.assertEqual(art_factor(480, 270, 720, 420), 1)
        self.root.deiconify()
        self.root.geometry("1200x800")
        self.app.start_quiz(self.app.questions[:1])
        self.root.update()
        column = self.app.question_shell.winfo_width()
        photos = []

        def walk(widget):
            for child in widget.winfo_children():
                photo = getattr(child, "_fit_photo", None)
                if photo is not None:
                    photos.append(photo)
                walk(child)

        walk(self.app.question_shell)
        self.assertTrue(photos)
        self.assertGreaterEqual(photos[0].width(), column * 0.55)
        self.assertLessEqual(photos[0].width(), column)
        # Regression guard: the old fixed 480x220 cap shrank art to half size.
        self.assertGreater(photos[0].width(), 240)

    def test_missing_and_invalid_images_fall_back(self):
        self.app.show_image("assets/missing.png")
        self.app.show_image("data/questions/english.json")
        self.app.show_image("../outside.png")
        labels = [
            w.cget("text") for w in self.app.body.winfo_children() if isinstance(w, ttk.Label)
        ]
        # Assertion stays valid in either locale: derive the lead-in from the catalog.
        marker = self.app.tr("图片无法显示：{0}\n{1}", "", "").splitlines()[0]
        marker = marker.replace("：", ":").split(":")[0]
        self.assertEqual(sum(marker in str(text) for text in labels), 3)

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
        self.app.progress.store.path.parent.mkdir(parents=True, exist_ok=True)
        self.app.progress.store.path.write_text("{bad", encoding="utf-8")
        self.app.home()
        with patch("learning_platform.gui.messagebox.showerror"):
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
        self.assertIn(self.app.tr("请输入用户名"), self.app.login_error.cget("text"))
        self.app.login_page(True)
        self.assertIn(self.app.tr("注册并进入"), self.app.login_button.cget("text"))
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
