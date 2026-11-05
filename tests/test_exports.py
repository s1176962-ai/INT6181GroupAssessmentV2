"""CSV and PDF export behavior for isolated learning records."""

import csv
import tempfile
import unittest
from pathlib import Path

from learning_platform.exports import export_progress
from learning_platform.models import Question
from learning_platform.pdf_report import build_report


def sample_question():
    return Question.from_dict(
        {
            "id": "EXP001",
            "subject": "Science",
            "topic": "Plants",
            "difficulty": "easy",
            "type": "single_choice",
            "question": "@Which part absorbs water?",
            "options": ["=Root", "Flower"],
            "answer": "=Root",
            "explanation": "Roots absorb water.",
        }
    )


class ExportTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.folder = Path(temp.name)

    def test_csv_export_uses_bom_and_neutralizes_spreadsheet_formulas(self):
        history_path = self.folder / "history.csv"
        history = {
            "history": [
                {
                    "date": "2026-11-05",
                    "subject": "=1+1",
                    "mode": "quiz",
                    "total": 1,
                    "correct": 1,
                    "incorrect": 0,
                    "accuracy": 100.0,
                    "score": 1,
                    "timed_out": False,
                    "unanswered": 0,
                }
            ],
            "wrong": {},
        }
        export_progress(history_path, "history", "csv", history, {})

        payload = history_path.read_bytes()
        self.assertTrue(payload.startswith(b"\xef\xbb\xbf"))
        with history_path.open(encoding="utf-8-sig", newline="") as stream:
            rows = list(csv.DictReader(stream))
        self.assertEqual(rows[0]["subject"], "'=1+1")
        self.assertEqual(list(self.folder.glob("*.tmp")), [])

        wrong_path = self.folder / "wrong.csv"
        question = sample_question()
        wrong = {
            "history": [],
            "wrong": {
                question.id: {"last_answer": "=Root", "count": 2, "last_seen": "2026-11-05"},
                "DELETED001": {"last_answer": "+answer", "count": 1, "last_seen": "2026-11-05"},
            },
        }
        export_progress(wrong_path, "wrong", "csv", wrong, {question.id: question})
        with wrong_path.open(encoding="utf-8-sig", newline="") as stream:
            exported = list(csv.DictReader(stream))
        self.assertEqual(exported[0]["question"], "'@Which part absorbs water?")
        self.assertEqual(exported[0]["answer"], "'=Root")
        self.assertEqual(exported[1]["question"], "[Deleted question]")
        self.assertEqual(exported[1]["last_answer"], "'+answer")

    def test_pdf_export_builds_reports_for_history_and_deleted_questions(self):
        history = {
            "history": [
                {
                    "id": "attempt-1",
                    "date": "2026-11-05T12:00:00+08:00",
                    "subject": "Science",
                    "mode": "quiz",
                    "total": 1,
                    "correct": 1,
                    "incorrect": 0,
                    "accuracy": 100.0,
                    "score": 1,
                    "max_score": 1,
                }
            ],
            "wrong": {},
        }
        history_pdf = build_report("history", history, {})
        self.assertTrue(history_pdf.startswith(b"%PDF-"))
        self.assertTrue(history_pdf.endswith(b"%%EOF\n"))

        wrong = {
            "history": [],
            "wrong": {
                "DELETED001": {
                    "count": 2,
                    "last_answer": "Unknown",
                    "last_seen": "2026-11-05T12:00:00+08:00",
                }
            },
        }
        wrong_pdf = build_report("wrong", wrong, {})
        self.assertTrue(wrong_pdf.startswith(b"%PDF-"))
        self.assertTrue(wrong_pdf.endswith(b"%%EOF\n"))


if __name__ == "__main__":
    unittest.main()
