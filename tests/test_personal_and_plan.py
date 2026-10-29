import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from learning_platform.auth import AuthService
from learning_platform.importing import QuestionImportService
from learning_platform.repositories import (
    LearningPlanRepository,
    PersonalQuestionRepository,
    ProgressRepository,
    QuestionRepository,
)
from learning_platform.services import QuizEngine
from learning_platform.storage import DataError

ROOT = Path(__file__).resolve().parents[1]


class PersonalQuestionImportTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.folder = Path(temp.name)
        self.public = QuestionRepository(ROOT / "data/questions").all()
        self.alice = PersonalQuestionRepository(self.folder / "alice/questions.json")
        self.bob = PersonalQuestionRepository(self.folder / "bob/questions.json")

    def record(self, question_id="MINE001", question="My question?"):
        return {
            "id": question_id,
            "subject": "Personal",
            "topic": "Imported",
            "difficulty": "easy",
            "type": "single_choice",
            "question": question,
            "options": ["Yes", "No"],
            "answer": "Yes",
            "explanation": "Yes is correct.",
            "question_image": None,
            "option_images": None,
        }

    def test_json_preview_confirm_duplicates_and_isolation(self):
        path = self.folder / "questions.json"
        path.write_text(
            json.dumps(
                [
                    self.record(),
                    self.record("MINE001", "Different"),
                    self.record("MINE002"),
                    self.record("ENG001", "Public collision"),
                    {**self.record("BAD001"), "answer": "Missing"},
                ]
            ),
            encoding="utf-8",
        )
        service = QuestionImportService(self.alice, self.public)
        preview = service.preview(path)
        self.assertEqual((preview.total, len(preview.valid), preview.duplicates, preview.errors), (5, 1, 3, 1))
        self.assertEqual([q.id for q in service.confirm(preview)], ["MINE001"])
        self.assertEqual([q.id for q in self.alice.all()], ["MINE001"])
        self.assertEqual(self.bob.all(), [])

    def test_csv_keeps_valid_rows_when_another_row_is_bad(self):
        path = self.folder / "questions.csv"
        path.write_text(
            "id,subject,topic,difficulty,type,question,options,answer,explanation\n"
            'CSV001,Math,Addition,easy,single_choice,One plus one?,"[""1"", ""2""]",2,Correct.\n'
            'CSV002,Math,Addition,easy,single_choice,Broken,not-json,2,Broken.\n',
            encoding="utf-8",
        )
        preview = QuestionImportService(self.alice, self.public).preview(path)
        self.assertEqual((len(preview.valid), preview.errors), (1, 1))

    def test_corrupt_personal_bank_is_preserved(self):
        self.alice.store.path.parent.mkdir(parents=True)
        self.alice.store.path.write_text("{bad", encoding="utf-8")
        before = self.alice.store.path.read_bytes()
        source = self.folder / "valid.json"
        source.write_text(json.dumps([self.record()]), encoding="utf-8")
        with self.assertRaises(DataError):
            QuestionImportService(self.alice, self.public).preview(source)
        self.assertEqual(self.alice.store.path.read_bytes(), before)


class LearningPlanTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.folder = Path(temp.name)
        self.plan = LearningPlanRepository(self.folder / "learning_plan.json")
        self.progress = ProgressRepository(self.folder / "progress.json")
        self.questions = QuestionRepository(ROOT / "data/questions").all()
        self.now = datetime(2026, 10, 29, 15, 0, tzinfo=timezone(timedelta(hours=8)))

    def test_default_goal_and_partial_quiz_are_counted(self):
        self.assertEqual(self.plan.summary(self.now)["daily_goal"], 20)
        self.plan.set_goal(25)
        quiz = QuizEngine(
            self.questions[:2], self.progress, learning_plan=self.plan, now=lambda: self.now
        )
        quiz.submit(quiz.current.answer)
        self.assertEqual(self.plan.summary(self.now)["today"], 1)
        self.assertEqual(self.progress.load()["history"], [])

    def test_idempotent_events_streak_and_week(self):
        self.assertTrue(self.plan.record_answer("one", self.now - timedelta(days=2)))
        self.assertFalse(self.plan.record_answer("one", self.now - timedelta(days=2)))
        self.plan.record_answer("two", self.now - timedelta(days=1))
        self.plan.record_answer("three", self.now)
        self.plan.record_answer("four", self.now)
        summary = self.plan.summary(self.now)
        self.assertEqual(summary["streak"], 3)
        self.assertEqual([item["count"] for item in summary["weekly"]][-3:], [1, 1, 2])

    def test_invalid_plan_is_preserved(self):
        self.plan.store.path.parent.mkdir(parents=True, exist_ok=True)
        self.plan.store.path.write_text('{"daily_goal":20,"answers":[{}]}', encoding="utf-8")
        before = self.plan.store.path.read_bytes()
        with self.assertRaises(DataError):
            self.plan.record_answer("new", self.now)
        self.assertEqual(self.plan.store.path.read_bytes(), before)

    def test_account_paths_are_isolated(self):
        auth = AuthService(self.folder / "data")
        alice = auth.register("Alice", "Password1", "Password1")
        bob = auth.register("Bobby", "Password1", "Password1")
        self.assertNotEqual(auth.personal_questions_path(alice), auth.personal_questions_path(bob))
        self.assertNotEqual(auth.learning_plan_path(alice), auth.learning_plan_path(bob))


if __name__ == "__main__":
    unittest.main()
