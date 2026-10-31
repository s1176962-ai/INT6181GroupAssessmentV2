import csv
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from learning_platform.auth import AuthService
from learning_platform.exports import rows_for
from learning_platform.importing import QuestionImportService
from learning_platform.maintenance import QuestionEditor
from learning_platform.models import Question
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
        self.assertEqual(
            (preview.total, len(preview.valid), preview.duplicates, preview.errors), (5, 1, 3, 1)
        )
        self.assertEqual([q.id for q in service.confirm(preview)], ["MINE001"])
        self.assertEqual([q.id for q in self.alice.all()], ["MINE001"])
        self.assertEqual(self.bob.all(), [])

    def test_csv_keeps_valid_rows_when_another_row_is_bad(self):
        path = self.folder / "questions.csv"
        path.write_text(
            "id,subject,topic,difficulty,type,question,options,answer,explanation\n"
            'CSV001,Math,Addition,easy,single_choice,One plus one?,"[""1"", ""2""]",2,Correct.\n'
            "CSV002,Math,Addition,easy,single_choice,Broken,not-json,2,Broken.\n",
            encoding="utf-8",
        )
        preview = QuestionImportService(self.alice, self.public).preview(path)
        self.assertEqual((len(preview.valid), preview.errors), (1, 1))

    def test_official_json_and_csv_templates_are_importable(self):
        json_preview = QuestionImportService(self.alice, self.public).preview(
            ROOT / "examples/personal_questions_template.json"
        )
        csv_preview = QuestionImportService(self.bob, self.public).preview(
            ROOT / "examples/personal_questions_template.csv"
        )
        self.assertEqual((len(json_preview.valid), json_preview.errors), (1, 0))
        self.assertEqual((len(csv_preview.valid), csv_preview.errors), (1, 0))

    def test_admin_public_bank_import_uses_the_same_validated_template(self):
        for suffix in ("json", "csv"):
            public_folder = self.folder / f"public-{suffix}"
            public_folder.mkdir()
            editor = QuestionEditor(public_folder)
            service = QuestionImportService(editor, [])
            preview = service.preview(ROOT / f"examples/personal_questions_template.{suffix}")
            added = service.confirm(preview)
            self.assertEqual(len(added), 1)
            self.assertEqual(QuestionRepository(public_folder).all(), added)

    def test_corrupt_personal_bank_is_preserved(self):
        self.alice.store.path.parent.mkdir(parents=True)
        self.alice.store.path.write_text("{bad", encoding="utf-8")
        before = self.alice.store.path.read_bytes()
        source = self.folder / "valid.json"
        source.write_text(json.dumps([self.record()]), encoding="utf-8")
        with self.assertRaises(DataError):
            QuestionImportService(self.alice, self.public).preview(source)
        self.assertEqual(self.alice.store.path.read_bytes(), before)

    def test_personal_crud_and_public_id_protection(self):
        question = Question.from_dict(self.record())
        self.alice.save(question, reserved_ids={"PUBLIC001"})
        changed = Question.from_dict({**question.to_dict(), "question": "Changed?"})
        self.alice.save(changed, question, reserved_ids={"PUBLIC001"})
        self.assertEqual(self.alice.all(), [changed])
        self.alice.delete(changed)
        self.assertEqual(self.alice.all(), [])
        with self.assertRaises(ValueError):
            self.alice.save(
                Question.from_dict(self.record("PUBLIC001")), reserved_ids={"PUBLIC001"}
            )

    def test_wrong_question_csv_is_a_valid_import_source(self):
        question = self.public[0]
        data = {
            "wrong": {
                question.id: {
                    "last_answer": next(x for x in question.options if x != question.answer),
                    "count": 1,
                    "last_seen": "2026-10-31T10:00:00+08:00",
                }
            },
            "history": [],
        }
        keys, rows = rows_for("wrong", data, {question.id: question})
        source = self.folder / "wrong.csv"
        with source.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(keys)
            writer.writerows(rows)
        preview = QuestionImportService(self.alice, self.public).preview(source)
        self.assertEqual(len(preview.valid), 1)
        self.assertEqual(preview.valid[0].id, f"WRONG-{question.id}")


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

    def test_daily_filters_are_saved_and_old_files_are_upgraded_in_memory(self):
        self.plan.store.path.parent.mkdir(parents=True, exist_ok=True)
        self.plan.store.path.write_text(
            json.dumps({"daily_goal": 8, "answers": []}), encoding="utf-8"
        )
        old = self.plan.load()
        self.assertEqual(
            (old["bank_kind"], old["subject"], old["difficulty"]),
            ("public", None, None),
        )
        self.plan.set_settings("personal", "English", "easy", 6)
        saved = self.plan.load()
        self.assertEqual(
            (
                saved["bank_kind"],
                saved["subject"],
                saved["difficulty"],
                saved["daily_goal"],
            ),
            ("personal", "English", "easy", 6),
        )

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
