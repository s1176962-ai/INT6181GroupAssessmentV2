"""Visual acceptance captures for the v2.5 layout / i18n pass.

Run: py -3 .workbuddy-ai/capture_v25.py

Uses a temporary profile (questions + assets copied, admin seeded), so the
user's real settings/progress/users are never touched. DPI awareness is enabled
before the first Tk window, matching launcher.py / gui.main().
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

from learning_platform import tokens, ui_tokens as T
from learning_platform.auth import AuthService
from learning_platform.gui import Application

OUT = ROOT / ".workbuddy-ai" / "preview"
OUT.mkdir(parents=True, exist_ok=True)

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
    time.sleep(0.3)
    root.update()
    x, y = root.winfo_rootx(), root.winfo_rooty()
    image = ImageGrab.grab(
        bbox=(x, y, x + root.winfo_width(), y + root.winfo_height()),
        all_screens=True,
    )
    image.save(OUT / name)
    print(f"{name}: {image.size}")


def seed_admin(auth):
    user = auth.register("Admin", "Secret1", "Secret1")
    records = auth.store.read()
    records["admin"]["role"] = "admin"
    auth.store.write(records)
    return auth.require_admin(user)


def capture(page, factor, tag):
    tmp = tempfile.TemporaryDirectory()
    folder = Path(tmp.name)
    root = None
    try:
        shutil.copytree(ROOT / "data/questions", folder / "data/questions")
        shutil.copytree(ROOT / "assets", folder / "assets")
        tokens.set_scale(factor)
        root = tk.Tk()
        root.tk.call("tk", "scaling", f"{1.333333 * factor:.4f}")
        app = Application(root, project_root=folder)
        app.motion.enabled = False
        app.tr.set_language("en")
        app.apply_theme("light")
        root.state("zoomed")
        root.attributes("-topmost", True)
        root.lift()
        root.update()

        admin = seed_admin(AuthService(folder / "data"))
        app.user = admin
        app.signed_in = True
        app.progress = __import__(
            "learning_platform.repositories", fromlist=["ProgressRepository"]
        ).ProgressRepository(app.auth.progress_path(admin))

        if page == "configure":
            app.configure()
        elif page in ("quiz-ai-empty", "quiz-ai-filled"):
            app.configure()
            root.update()
            app.start_quiz(app.questions[:5])
            root.update()
            if page == "quiz-ai-filled":
                app.quiz_ai_reply.configure(text=HINT, fg=T.TEXT)
                app.quiz_ai_button.configure(text="Asked for this question")
                app.quiz_ai_button.state(["disabled"])
        elif page == "questions":
            app.manage_questions()
        elif page == "users":
            app.manage_users()
        shot(root, f"v25-{page}-{tag}-{int(factor * 100)}.png")
    except Exception as exc:
        print(f"FAILED {page}/{tag}/{factor}: {type(exc).__name__}: {exc}")
    finally:
        if root is not None:
            try:
                root.destroy()
            except tk.TclError:
                pass
        tmp.cleanup()


for scale, tag in ((1.0, "max"), (1.5, "max")):
    for page in ("configure", "quiz-ai-empty", "quiz-ai-filled", "questions", "users"):
        capture(page, scale, tag)
