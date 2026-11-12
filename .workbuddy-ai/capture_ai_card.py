"""Capture the home page to inspect the Ask AI card layout.

Run: py -3 .workbuddy-ai/capture_ai_card.py [tag]

Uses a temporary profile so real settings/progress are untouched.
"""
import ctypes
import shutil
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
TAG = sys.argv[1] if len(sys.argv) > 1 else "cur"

HINT = (
    "Hint: look at whether the subject is singular or plural, then at the "
    "present continuous form \"be + doing\".\n\n"
    "They is plural, so the present continuous needs \"are\". A. is only "
    "matches a third-person singular subject; C. am is used only with I. "
    "That leaves B. are as the correct completion: \"They are playing now\"."
)


def shot(root, name):
    root.update_idletasks()
    root.update()
    time.sleep(0.35)
    root.update()
    x, y = root.winfo_rootx(), root.winfo_rooty()
    image = ImageGrab.grab(
        bbox=(x, y, x + root.winfo_width(), y + root.winfo_height()),
        all_screens=True,
    )
    image.save(OUT / name)
    print(f"{name}: {image.size}")


def capture(factor, theme, maximize=True, geometry=None):
    tmp = tempfile.TemporaryDirectory()
    folder = Path(tmp.name)
    root = None
    try:
        shutil.copytree(ROOT / "data/questions", folder / "data/questions")
        shutil.copytree(ROOT / "assets", folder / "assets")
        shutil.copy2(ROOT / "AI-assistant-icon.png", folder / "AI-assistant-icon.png")
        tokens.set_scale(factor)
        root = tk.Tk()
        root.tk.call("tk", "scaling", f"{1.333333 * factor:.4f}")
        app = Application(root, project_root=folder)
        app.motion.enabled = False
        app.tr.set_language("en")
        app.apply_theme(theme)
        if geometry:
            root.geometry(geometry)
        elif maximize:
            root.state("zoomed")
        else:
            root.geometry("1180x760")
        root.attributes("-topmost", True)
        root.lift()
        root.update()
        app.enter_guest()
        root.update()
        suffix = geometry.replace("x", "_") if geometry else ("max" if maximize else "win")
        shot(root, f"{TAG}-home-{theme}-{int(factor * 100)}-{suffix}.png")
        from learning_platform import ui_tokens as T

        app.home_ai_input.focus_set()
        root.update()
        shot(root, f"{TAG}-home-{theme}-{int(factor * 100)}-{suffix}-focus.png")
        app.home_ai_reply.configure(text=HINT, fg=T.TEXT)
        root.update()
        shot(root, f"{TAG}-home-{theme}-{int(factor * 100)}-{suffix}-answered.png")
    except Exception as exc:
        print(f"FAILED {theme}/{factor}: {type(exc).__name__}: {exc}")
    finally:
        if root is not None:
            try:
                root.destroy()
            except tk.TclError:
                pass
        tmp.cleanup()


for scale in (1.0, 1.5):
    capture(scale, "light", True)
    capture(scale, "dark", True)
capture(1.0, "light", False)
capture(1.5, "light", geometry="1600x920")
capture(1.5, "dark", geometry="1600x920")
