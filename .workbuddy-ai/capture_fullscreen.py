"""Reproduce the user's environment: maximized window at 125% / 150% DPI.

Run: py -3 .workbuddy-ai/capture_fullscreen.py
Uses a temporary profile so the user's settings/progress are untouched.
"""
import ctypes
import sys
import tempfile
import time
import tkinter as tk
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

from PIL import ImageGrab

from learning_platform import tokens
from learning_platform.gui import Application

OUT = ROOT / ".workbuddy-ai" / "preview"
OUT.mkdir(parents=True, exist_ok=True)


def shot(root, name):
    root.update_idletasks()
    root.update()
    time.sleep(0.3)
    root.update()
    x, y = root.winfo_rootx(), root.winfo_rooty()
    image = ImageGrab.grab(
        bbox=(x, y, x + root.winfo_width(), y + root.winfo_height()),
        all_screens=True,
    )
    image.save(OUT / name)
    print(f"{name}: {image.size} (root {root.winfo_width()}x{root.winfo_height()})")


def capture(factor, tag):
    tmp = tempfile.TemporaryDirectory()
    root = None
    try:
        tokens.set_scale(factor)
        root = tk.Tk()
        root.tk.call("tk", "scaling", f"{1.333333 * factor:.4f}")
        app = Application(root, progress_path=Path(tmp.name) / "progress.json")
        app.motion.enabled = False
        root.state("zoomed")
        root.attributes("-topmost", True)
        root.lift()
        root.update()
        shot(root, f"full-{tag}-login-{int(factor * 100)}.png")
        app.enter_guest()
        root.update()
        shot(root, f"full-{tag}-home-{int(factor * 100)}.png")
        app.settings()
        root.update()
        shot(root, f"full-{tag}-settings-{int(factor * 100)}.png")
    except Exception as exc:
        print(f"FAILED {tag}/{factor}: {type(exc).__name__}: {exc}")
    finally:
        if root is not None:
            try:
                root.destroy()
            except tk.TclError:
                pass
        tmp.cleanup()


for value in (1.25, 1.5):
    capture(value, "dark")
