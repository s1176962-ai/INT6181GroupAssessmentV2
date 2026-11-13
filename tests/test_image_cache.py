"""Image reuse and bounded memory for repeated page changes."""

import tempfile
import tkinter as tk
import unittest
from pathlib import Path

from learning_platform.image_cache import portrait_image, source_image


class ImageCacheTests(unittest.TestCase):
    def test_source_and_portrait_reuse_and_bound(self):
        root = tk.Tk()
        root.withdraw()
        self.addCleanup(root.destroy)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "sprite.png"
            image = tk.PhotoImage(master=root, width=6, height=2)
            image.put("blue", to=(0, 0, 6, 2))
            image.write(str(path), format="png")
            self.assertIs(source_image(root, path), source_image(root, path))
            first = portrait_image(root, path, "thinking", 2)
            self.assertIs(first, portrait_image(root, path, "thinking", 2))
            for index in range(18):
                other = Path(folder) / f"{index}.png"
                image.write(str(other), format="png")
                source_image(root, other)
                portrait_image(root, other, "correct", 2)
            self.assertEqual(len(root._source_images), 16)
            self.assertEqual(len(root._portrait_images), 12)
