import copy
import json
import random
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from learning_platform.models import Question, score
from learning_platform.repositories import ProgressRepository, QuestionRepository
from learning_platform.services import QuizEngine, image_path, select_questions
from learning_platform.storage import DataError, JsonStore

ROOT = Path(__file__).resolve().parents[1]


class CoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.progress = ProgressRepository(self.folder / "progress.json")
        self.bank = QuestionRepository(ROOT / "data/questions")
        self.questions = self.bank.all()
        self.q = self.questions[0]

    def wrong_answer(self, q):
        return next(answer for answer in q.options if answer != q.answer)

    def test_sample_banks(self):
        self.assertEqual(len(self.questions), 60)
        self.assertEqual({q.subject for q in self.questions}, {"English", "Mathematics", "Science"})
        self.assertEqual(self.bank.warnings, [])
        self.assertIn("苹果", self.q.options)

    def test_required_fields(self):
        for field in (
            "id",
            "subject",
            "topic",
            "difficulty",
            "type",
            "question",
            "options",
            "answer",
            "explanation",
        ):
            record = copy.deepcopy(self.q.__dict__)
            del record[field]
            with self.subTest(field=field), self.assertRaises(ValueError):
                Question.from_dict(record)

    def test_bad_question_shapes(self):
        for update in (
            {"options": ["same", "same"]},
            {"answer": "missing"},
            {"type": "essay"},
            {"option_images": [None]},
            {"options": [1, 2]},
            {"question_image": 42},
            {"option_images": [None, None, {}]},
        ):
            with self.subTest(update=update), self.assertRaises(ValueError):
                Question.from_dict({**self.q.__dict__, **update})
        with self.assertRaises(ValueError):
            Question.from_dict(None)

    def test_invalid_and_duplicate_records_are_skipped(self):
        JsonStore(self.folder / "a.json", []).write([self.q.__dict__, {}, self.q.__dict__])
        bank = QuestionRepository(self.folder)
        self.assertEqual(len(bank.all()), 1)
        self.assertEqual(len(bank.warnings), 2)

    def test_empty_missing_and_malformed_banks(self):
        bank = QuestionRepository(self.folder)
        self.assertEqual(bank.all(), [])
        self.assertTrue(bank.warnings)
        (self.folder / "bad.json").write_text("{bad", encoding="utf-8")
        (self.folder / "object.json").write_text("{}", encoding="utf-8")
        self.assertEqual(bank.all(), [])
        self.assertEqual(len(bank.warnings), 2)

    def test_filtering(self):
        result = select_questions(self.questions, "Mathematics", "Geometry", "easy", 10)
        self.assertEqual({q.id for q in result}, {"MAT003", "MAT004"})

    def test_random_selection_and_limits(self):
        result = select_questions(self.questions, count=4, rng=random.Random(8))
        self.assertEqual(len(result), 4)
        self.assertEqual(len({q.id for q in result}), 4)
        self.assertEqual(result, select_questions(self.questions, count=4, rng=random.Random(8)))
        self.assertNotEqual(result, select_questions(self.questions, count=4, rng=random.Random(9)))
        self.assertEqual(len(select_questions(self.questions, count=100)), 60)

    def test_invalid_settings(self):
        for count in (0, -1, 2.5, True, "3"):
            with self.subTest(count=count), self.assertRaises(ValueError):
                select_questions(self.questions, count=count)
        with self.assertRaises(ValueError):
            select_questions(self.questions, subject="Missing")
        with self.assertRaises(ValueError):
            select_questions([], count=1)

    def test_correct_incorrect_and_duplicate_submission(self):
        quiz = QuizEngine(self.questions[:2], self.progress)
        with self.assertRaises(ValueError):
            quiz.next_question()
        with self.assertRaises(ValueError):
            quiz.submit("")
        self.assertTrue(quiz.submit(quiz.current.answer))
        with self.assertRaises(ValueError):
            quiz.submit(quiz.current.answer)
        quiz.next_question()
        self.assertFalse(quiz.submit(self.wrong_answer(quiz.current)))
        self.assertTrue(quiz.complete)
        self.assertEqual(quiz.result()["accuracy"], 50)
        with self.assertRaises(ValueError):
            quiz.next_question()

    def test_scoring_edges(self):
        self.assertEqual(score(0, 0)["accuracy"], 0)
        self.assertEqual(score(3, 1)["accuracy"], 33.33)
        self.assertEqual(score(3, 3)["score"], 3)
        self.assertEqual(score(3, 0)["incorrect"], 3)
        for counts in ((-1, 0), (1, 2), (1, -1), (True, 1)):
            with self.assertRaises(ValueError):
                score(*counts)
        with self.assertRaises(ValueError):
            QuizEngine([], self.progress)

    def test_wrong_dedup_and_review_rule(self):
        for _ in range(2):
            QuizEngine([self.q], self.progress).submit(self.wrong_answer(self.q))
        data = self.progress.load()
        self.assertEqual(len(data["wrong"]), 1)
        self.assertEqual(data["wrong"][self.q.id]["count"], 2)
        QuizEngine([self.q], self.progress).submit(self.q.answer)
        self.assertIn(self.q.id, self.progress.load()["wrong"])
        QuizEngine([self.q], self.progress, review=True).submit(self.wrong_answer(self.q))
        self.assertEqual(self.progress.load()["wrong"][self.q.id]["count"], 3)
        QuizEngine([self.q], self.progress, review=True).submit(self.q.answer)
        self.assertEqual(self.progress.load()["wrong"], {})

    def test_history_survives_restart(self):
        QuizEngine([self.q], self.progress).submit(self.q.answer)
        new_repo = ProgressRepository(self.progress.store.path)
        record = new_repo.load()["history"][0]
        self.assertEqual(record["subject"], "English")
        self.assertEqual(record["score"], 1)
        self.assertTrue(record["date"])

    def test_partial_quiz_saves_wrong_but_not_history(self):
        QuizEngine(self.questions[:2], self.progress).submit(self.wrong_answer(self.q))
        self.assertIn(self.q.id, self.progress.load()["wrong"])
        self.assertEqual(self.progress.load()["history"], [])

    def test_missing_progress_and_independent_defaults(self):
        self.assertEqual(self.progress.load(), {"wrong": {}, "history": []})
        data = self.progress.load()
        data["history"].append(1)
        self.assertEqual(self.progress.load()["history"], [])

    def test_malformed_progress_is_never_overwritten(self):
        for content in (
            "{bad",
            "[]",
            '{"wrong":[],"history":[]}',
            '{"wrong":{},"history":[{}]}',
            '{"wrong":{"x":{"count":false}},"history":[]}',
        ):
            self.progress.store.path.write_text(content, encoding="utf-8")
            with self.assertRaises(DataError):
                QuizEngine([self.q], self.progress).submit(self.q.answer)
            self.assertEqual(self.progress.store.path.read_text(encoding="utf-8"), content)

    def test_inconsistent_history_rejected(self):
        QuizEngine([self.q], self.progress).submit(self.q.answer)
        data = self.progress.load()
        data["history"][0]["accuracy"] = 50
        self.progress.save(data)
        with self.assertRaises(DataError):
            self.progress.load()

    def test_failed_write_is_atomic_and_can_retry(self):
        self.progress.save({"wrong": {}, "history": []})
        before = self.progress.store.path.read_bytes()
        quiz = QuizEngine([self.q], self.progress)
        with patch("pathlib.Path.replace", side_effect=OSError("Disk unavailable")):
            with self.assertRaises(DataError):
                quiz.submit(self.wrong_answer(self.q))
        self.assertFalse(quiz.submitted)
        self.assertEqual(self.progress.store.path.read_bytes(), before)
        self.assertEqual(list(self.folder.glob(".tmp-*")), [])
        quiz.submit(self.wrong_answer(self.q))
        self.assertEqual(len(self.progress.load()["history"]), 1)

    def test_image_paths(self):
        for q in self.questions:
            for image in [q.question_image, *(q.option_images or [])]:
                if image:
                    self.assertTrue(image_path(ROOT, image).is_file())
        self.assertFalse(image_path(ROOT, "assets/missing.png").exists())
        with self.assertRaises(ValueError):
            image_path(ROOT, "../outside.png")

    def test_utf8_bom(self):
        path = self.folder / "bom.json"
        path.write_text(json.dumps([self.q.__dict__]), encoding="utf-8-sig")
        self.assertEqual(len(QuestionRepository(self.folder).all()), 1)


if __name__ == "__main__":
    unittest.main()
