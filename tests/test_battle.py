import json
import random
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock

from learning_platform.battle import PROFILES, ApiOpponent, apply_damage, grade, opponent_answer
from learning_platform.models import Question


class BattleTests(unittest.TestCase):
    def test_images_keep_stem_and_option_identity_and_reject_path_escape(self):
        q = Question(
            "q",
            "Math",
            "a",
            "easy",
            "single_choice",
            "Shape?",
            ["Circle", "Square"],
            "Circle",
            "Round",
        )
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "shape.png").write_bytes(b"image")
            q = replace(q, question_image="shape.png", option_images=[None, "shape.png"])
            opponent = ApiOpponent(Mock(), "en", root)
            self.assertEqual(
                [label for label, _ in opponent.images_for(q)], ["Question image", "Option B image"]
            )
            with self.assertRaises(ValueError):
                opponent.images_for(replace(q, question_image="../outside.png"))

    def test_api_decision_is_bound_to_question_and_preserves_choice_summary(self):
        q = Question("q", "Math", "a", "easy", "single_choice", "2+2?", ["4", "5"], "4", "Four")
        client = Mock()
        client.ask.return_value = json.dumps(
            {
                "question_id": "q",
                "option_index": 1,
                "thinking_seconds": 10,
                "decision_basis": "I choose 5 because I counted one extra unit.",
            }
        )
        decision = ApiOpponent(client, "en").answer(q, "普通级")
        self.assertEqual(decision.option, "5")
        self.assertIn("5", decision.basis)
        self.assertEqual(tuple(decision), ("5", 10.0))
        self.assertEqual(client.ask.call_count, 1)
        payload = json.loads(client.ask.call_args.args[0].split("\n")[-1])
        self.assertNotIn("answer", payload)
        self.assertNotIn("explanation", payload)

    def test_api_preserves_three_concise_stage_summaries(self):
        q = Question("q", "Math", "a", "easy", "single_choice", "2+2?", ["4", "5"], "4", "Four")
        client = Mock()
        stages = [
            "Add two pairs.",
            "4 matches; 5 adds one extra.",
            "I select 4; no extra unit is requested.",
        ]
        client.ask.return_value = json.dumps(
            {
                "question_id": "q",
                "option_index": 0,
                "thinking_seconds": 10,
                "decision_basis": "I select 4: two pairs make four.",
                "stage_summaries": stages,
            }
        )
        self.assertEqual(ApiOpponent(client, "en").answer(q, "普通级").stages, tuple(stages))

    def test_api_rejects_mismatched_or_unsubstantiated_decisions(self):
        q = Question("q", "Math", "a", "easy", "single_choice", "2+2?", ["4", "5"], "4", "Four")
        valid = {
            "question_id": "q",
            "option_index": 0,
            "thinking_seconds": 10,
            "decision_basis": "I select 4: adding two pairs makes four.",
        }
        for patch in (
            {"question_id": "other"},
            {"option_index": 9},
            {"decision_basis": "I pick something."},
            {"thinking_seconds": float("nan")},
        ):
            client = Mock()
            client.ask.return_value = json.dumps({**valid, **patch})
            with self.subTest(patch=patch), self.assertRaises(ValueError):
                ApiOpponent(client).answer(q, "普通级")

    def test_damage(self):
        self.assertEqual(apply_damage(100, 100, 150, 140), (100, 90))
        self.assertEqual(apply_damage(100, 100, 0, 150), (0, 100))
        self.assertEqual(apply_damage(40, 60, 120, 120), (40, 60))

    def test_wrong_and_timeout_have_no_speed_points(self):
        self.assertEqual(grade(False, 1).total, 0)
        self.assertEqual(grade(True, 31).total, 0)
        self.assertEqual(grade(True, 5).total, 150)
        self.assertEqual(grade(True, 10).total, 140)
        self.assertEqual(grade(True, 30, 7).total, 117)

    def test_profiles_produce_valid_answers_and_delays(self):
        q = Question("q", "Math", "a", "easy", "single_choice", "2+2?", ["4", "5"], "4", "Four")
        for level, (_, low, high) in PROFILES.items():
            answer, delay = opponent_answer(q, level, random.Random(42))
            self.assertIn(answer, q.options)
            self.assertLessEqual(low, delay)
            self.assertLessEqual(delay, high)
