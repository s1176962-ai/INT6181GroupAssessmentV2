"""Local remembered-login storage behavior."""

import tempfile
import unittest
from pathlib import Path

from learning_platform.login_preferences import LoginPreferences


class LoginPreferenceTests(unittest.TestCase):
    def test_password_is_encrypted_and_corrupt_state_is_ignored(self):
        with tempfile.TemporaryDirectory() as folder:
            preferences = LoginPreferences(Path(folder))
            preferences.save("Student", "Password1", True)
            raw = preferences.store.path.read_text(encoding="utf-8")
            self.assertNotIn("Password1", raw)
            self.assertEqual(
                preferences.load(),
                {"username": "Student", "password": "Password1", "remember": True},
            )
            preferences.store.path.write_text("not-json", encoding="utf-8")
            self.assertEqual(
                preferences.load(), {"username": "", "password": "", "remember": False}
            )
