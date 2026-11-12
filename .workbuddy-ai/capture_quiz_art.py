"""Capture the quiz page to inspect the illustration size.

Run: py -3 .workbuddy-ai/capture_quiz_art.py [tag]

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
TAG = sys.argv[1] if len(sys.argv) > 1 else "quiz"
IDS = ("ENG007", "MAT013", "SCI001")


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
        for qid in IDS:
            question = next((q for q in app.questions if q.id == qid), None)
            if question is None:
                print("missing", qid)
                continue
            app.start_quiz([question])
            root.update()
            app.answer.set(question.answer)
            app.submit()
            root.update()
            root.update_idletasks()
            art = []

            def walk(widget):
                for child in widget.winfo_children():
                    photo = getattr(child, "_fit_photo", None)
                    if photo is not None:
                        art.append((photo.width(), photo.height()))
                    walk(child)

            walk(app.question_shell)
            print("art", qid, art, "column", app.question_shell.winfo_width())
            shot(root, f"{TAG}-{theme}-{int(factor * 100)}-{suffix}-{qid}.png")
            app.leave_quiz()
            root.update()
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
capture(1.5, "dark", geometry="1600x920")
capture(1.0, "light", geometry="1180x760")
