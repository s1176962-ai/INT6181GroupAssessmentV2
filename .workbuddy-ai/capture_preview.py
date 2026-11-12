"""Regenerate login/home previews in both themes at the app's real Tk scaling.

Uses a temporary profile directory, so the user's data/settings.json is untouched.
"""
import ctypes
import sys
import tempfile
import time
import tkinter as tk
import ctypes.wintypes
from pathlib import Path

from PIL import ImageGrab

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from learning_platform.gui import Application
OUT = ROOT / ".workbuddy-ai" / "preview"
OUT.mkdir(parents=True, exist_ok=True)

ctypes.windll.user32.SetProcessDPIAware()
user32 = ctypes.windll.user32


def capture(kind, theme):
    tmp = tempfile.TemporaryDirectory()
    try:
        root = tk.Tk()
        # DPI awareness alone pushes Tk scaling to 2.664; the real app runs at 1.332.
        root.tk.call("tk", "scaling", "1.333")
        app = Application(root, progress_path=Path(tmp.name) / "progress.json")
        app.motion.enabled = False  # avoid the fade-in overlay covering the shot
        root.geometry("1100x760+40+40")
        if kind == "home":
            app.enter_guest()
        else:
            app.login_page()
        if theme == "light":
            app.apply_theme("light")
        root.attributes("-topmost", True)
        root.lift()
        root.update_idletasks()
        root.update()
        time.sleep(0.25)
        root.update()

        # Client area only: avoids the OS title bar and desktop bleeding through
        # the rounded window corners.
        x, y = root.winfo_rootx(), root.winfo_rooty()
        image = ImageGrab.grab(
            bbox=(x, y, x + root.winfo_width(), y + root.winfo_height()),
            all_screens=True,
        )
        path = OUT / f"{kind}-{theme}.png"
        image.save(path)
        print(f"{path.name}: {image.size}")
        root.destroy()
    finally:
        tmp.cleanup()


for page in ("home", "login"):
    for palette in ("dark", "light"):
        capture(page, palette)
