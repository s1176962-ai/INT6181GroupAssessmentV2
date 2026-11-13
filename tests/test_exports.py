"""CSV and PDF export behavior for isolated learning records."""

import csv
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from learning_platform.exports import export_progress
from learning_platform.history_notes import display_time
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
    def test_full_width_punctuation_uses_unicode_fallback_without_changing_latin_font(self):
        from reportlab.platypus import Paragraph

        data = {
            "history": [
                {
                    "date": "2026-11-13T14:45:58+08:00",
                    "subject": "English",
                    "mode": "quiz",
                    "total": 1,
                    "correct": 1,
                    "incorrect": 0,
                    "accuracy": 100.0,
                    "score": 1,
                    "max_score": 1,
                    "note": "well done！ Great!",
                }
            ],
            "wrong": {},
        }
        with patch("reportlab.platypus.Paragraph", wraps=Paragraph) as paragraph:
            build_report("history", data, {})
        note_call = next(
            call for call in paragraph.call_args_list if str(call.args[0]).startswith("Note:")
        )
        self.assertIn("well done<font", note_call.args[0])
        self.assertIn("！</font> Great!", note_call.args[0])
        self.assertEqual(note_call.args[1].fontName, "Helvetica")

    def test_reports_have_english_labels_and_formatted_wrong_timestamp(self):
        from reportlab.platypus import Paragraph

        q = sample_question()
        stamp = "2026-11-13T06:45:58+00:00"
        wrong = {
            "history": [],
            "wrong": {
                q.id: {
                    "last_answer": "Flower",
                    "count": 1,
                    "last_seen": stamp,
                }
            },
        }
        with patch("reportlab.platypus.Paragraph", wraps=Paragraph) as paragraph:
            build_report("wrong", wrong, {q.id: q})
        texts = [str(call.args[0]) for call in paragraph.call_args_list]
        self.assertIn("Wrong-Question Review Report", texts)
        self.assertIn("Last attempted: " + display_time(stamp), texts)
        self.assertFalse(any(any("\u3400" <= c <= "\u9fff" for c in text) for text in texts))
        self.assertFalse(any(stamp in text for text in texts))
        with patch("reportlab.platypus.Paragraph", wraps=Paragraph) as paragraph:
            build_report("history", {"history": [], "wrong": {}}, {})
        self.assertIn(
            "Learning Progress Report", [call.args[0] for call in paragraph.call_args_list]
        )

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
        self.assertEqual(rows[0]["date"], "2026/11/05 00:00:00")
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
        self.assertEqual(exported[0]["last_seen"], "2026/11/05 00:00:00")
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
