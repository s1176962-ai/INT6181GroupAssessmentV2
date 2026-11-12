"""Restore the pre-refactor V2 home() from the backup, dual-theme tokenised.

Keeps the login-page redesign, theme switching and default English untouched.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKUP = ROOT / ".workbuddy-ai" / "backup" / "gui.py"
CURRENT = ROOT / "learning_platform" / "gui.py"

COLOUR_MAP = {
    "BG": "T.BG",
    "BORDER": "T.BORDER",
    "BUTTON_FILL": "T.BUTTON_FILL",
    "BUTTON_INK": "T.BUTTON_INK",
    "COLOR_PRIMARY_DARK": "T.COLOR_PRIMARY_DARK",
    "ERROR": "T.ERROR",
    "ERROR_BG": "T.ERROR_BG",
    "HOVER": "T.HOVER",
    "INFO_BG": "T.INFO_BG",
    "MUTED": "T.MUTED",
    "ON_PRIMARY": "T.ON_PRIMARY",
    "PRIMARY": "T.PRIMARY",
    "PRIMARY_DISABLED": "T.PRIMARY_DISABLED",
    "PRIMARY_HOVER": "T.PRIMARY_HOVER",
    "SELECTED_BG": "T.SELECTED_BG",
    "SHADOW_CARD": "T.SHADOW_CARD",
    "SKY": "T.SKY",
    "SUCCESS_BG": "T.SUCCESS_BG",
    "SUCCESS_FG": "T.SUCCESS_FG",
    "SURFACE": "T.SURFACE",
    "TEXT": "T.TEXT",
    "TRACK": "T.TRACK",
    "WARNING": "T.WARNING",
    "WARNING_BG": "T.WARNING_BG",
    "CARD": "T.SURFACE",
    "RAISED": "T.HOVER",
    "NAVY": "T.TEXT",
    "PRIMARY_DARK": "T.COLOR_PRIMARY_DARK",
    "PRIMARY_INK": "T.ON_PRIMARY",
    "ERROR_FG": "T.ERROR",
    "ACCENT": "T.ACCENT",
    "SHADOW": "T.SHADOW_CARD",
}

PATTERN = re.compile(
    r"(?<![\w.])\b(" + "|".join(sorted(COLOUR_MAP, key=len, reverse=True)) + r")\b(?!\w)"
)


def method_span(lines, name):
    start = next(i for i, line in enumerate(lines) if line.startswith(f"    def {name}("))
    end = next(i for i in range(start + 1, len(lines)) if lines[i].startswith("    def "))
    return start, end


# 1. Extract the original home() and adapt it to the live token module.
backup_lines = BACKUP.read_text(encoding="utf-8").splitlines(keepends=True)
start, end = method_span(backup_lines, "home")
home = "".join(backup_lines[start:end]).rstrip("\n") + "\n"
home = PATTERN.sub(lambda m: COLOUR_MAP[m.group(1)], home)
home = home.replace('"#363A40"', "T.TRACK")

# Only deviation from the original: a locale-aware comma, because the default
# language is now English (the original hard-coded a full-width comma).
old_greeting = '        tk.Label(\n            self.body,\n            text=f"{greeting}，{name}",\n'
new_greeting = (
    '        separator = ", " if self.tr.language == "en" else "，"\n'
    '        tk.Label(\n            self.body,\n            text=f"{greeting}{separator}{name}",\n'
)
if old_greeting not in home:
    raise SystemExit("greeting block not found in backup home()")
home = home.replace(old_greeting, new_greeting, 1)

# 2. Swap it into the current file.
lines = CURRENT.read_text(encoding="utf-8").splitlines(keepends=True)
start, end = method_span(lines, "home")
lines[start:end] = [home]
text = "".join(lines)

# 3. Drop the helper that existed only for the minimal dashboard.
lines = text.splitlines(keepends=True)
start, end = method_span(lines, "_soft_card")
del lines[start:end]

CURRENT.write_text("".join(lines), encoding="utf-8")
print("restored original home(); removed _soft_card()")
