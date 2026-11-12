"""Visual acceptance captures for the modern-light redesign.

Run: py -3 .workbuddy-ai/capture_redesign.py

Uses a temporary profile directory, so the user's data/settings.json and
progress.json are never touched. DPI awareness is enabled before the first
Tk window, matching launcher.py / gui.main().
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
    time.sleep(0.25)
    root.update()
    x, y = root.winfo_rootx(), root.winfo_rooty()
    image = ImageGrab.grab(
        bbox=(x, y, x + root.winfo_width(), y + root.winfo_height()),
        all_screens=True,
    )
    path = OUT / name
    image.save(path)
    print(f"{path.name}: {image.size}")


def capture(page, theme, factor):
    tmp = tempfile.TemporaryDirectory()
    root = None
    try:
        tokens.set_scale(factor)
        root = tk.Tk()
        root.tk.call("tk", "scaling", f"{1.333333 * factor:.4f}")
        app = Application(root, progress_path=Path(tmp.name) / "progress.json")
        app.motion.enabled = False
        width = min(int(1100 * factor), 1700)
        height = min(int(760 * factor), 1000)
        root.geometry(f"{width}x{height}+20+20")
        root.attributes("-topmost", True)
        root.lift()
        app.enter_guest()
        if theme == "light":
            app.apply_theme("light")
        if page == "configure":
            app.configure()
        elif page == "settings":
            app.settings()
        elif page == "home":
            app.home()
        elif page == "quiz":
            app.configure()
            app.start_configured()
        shot(root, f"redesign-{page}-{theme}-{int(factor * 100)}.png")
    except Exception as exc:  # keep the remaining shots even if one page fails
        print(f"FAILED {page}/{theme}/{factor}: {type(exc).__name__}: {exc}")
    finally:
        if root is not None:
            try:
                root.destroy()
            except tk.TclError:
                pass
        tmp.cleanup()


for scale in (1.0, 1.25, 1.5):
    capture("configure", "light", scale)
capture("configure", "dark", 1.0)
capture("settings", "light", 1.0)
capture("home", "light", 1.0)
capture("quiz", "light", 1.0)
