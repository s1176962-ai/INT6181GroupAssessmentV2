"""Display preference persistence and monitor-boundary calculations."""

import tempfile
import unittest
from pathlib import Path

from learning_platform.display import DisplaySettings, window_size
from learning_platform.storage import DataError


class DisplayTests(unittest.TestCase):
    def test_default_and_saved_settings_include_wheel_control_preference(self):
        with tempfile.TemporaryDirectory() as folder:
            settings = DisplaySettings(Path(folder))
            self.assertEqual(settings.load(), {"size": "auto", "compact": True})

            settings.save("960x640", False, True)

            self.assertEqual(
                settings.load(),
                {"size": "960x640", "compact": False, "wheel_controls": True},
            )

    def test_invalid_settings_are_rejected_without_overwriting_existing_data(self):
        with tempfile.TemporaryDirectory() as folder:
            settings = DisplaySettings(Path(folder))
            settings.store.write({"size": "bad", "compact": True})
            before = settings.store.path.read_bytes()

            with self.assertRaises(DataError):
                settings.load()
            with self.assertRaises(ValueError):
                settings.save("bad", True)

            self.assertEqual(settings.store.path.read_bytes(), before)

    def test_window_size_respects_monitor_minimum_and_maximum(self):
        self.assertEqual(window_size("1280x800", 1920, 1080), (1280, 800))
        self.assertEqual(window_size("1280x800", 800, 600), (720, 480))
        self.assertEqual(window_size("960x640", 200, 200), (320, 320))


if __name__ == "__main__":
    unittest.main()
