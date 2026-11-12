import random
import unittest

from learning_platform.battle import PROFILES, apply_damage, grade, opponent_answer
from learning_platform.models import Question


class BattleTests(unittest.TestCase):
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
