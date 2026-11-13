import tempfile
import unittest
from pathlib import Path

from learning_platform.history_notes import HistoryNotes, display_time, query_history


class HistoryNotesTests(unittest.TestCase):
    def test_profile_isolation_and_restart(self):
        with tempfile.TemporaryDirectory() as folder:
            alice = HistoryNotes(Path(folder) / "alice")
            alice.save("session-1", True, "Review fractions")
            self.assertEqual(
                HistoryNotes(Path(folder) / "alice").load()["session-1"]["note"], "Review fractions"
            )
            self.assertEqual(HistoryNotes(Path(folder) / "bob").load(), {})

    def test_combined_filters_and_inclusive_date_range(self):
        records = [
            {"id": "1", "date": "2026-11-13T08:15:10+08:00"},
            {"id": "2", "date": "2026-11-12T18:00:00+08:00"},
        ]
        notes = {"1": {"liked": True, "note": "Example"}}
        self.assertEqual(
            [
                r["id"]
                for r in query_history(records, notes, "2026/11/13", "2026/11/13", "yes", "yes")
            ],
            ["1"],
        )
        self.assertEqual(
            [r["id"] for r in query_history(records, notes, liked="no", commented="no")], ["2"]
        )
        with self.assertRaises(ValueError):
            query_history(records, notes, "2026/11/14", "2026/11/13")

    def test_timestamp_is_local_and_readable(self):
        text = display_time("2026-11-13T08:15:10+08:00")
        self.assertRegex(text, r"^\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2}$")
