"""One-off mechanical retrofit: replace frozen colour names with live tokens.

Run once with the project Python. Keeps every widget/method name untouched.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PKG = ROOT / "learning_platform"

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
    # Old module-level aliases in gui.py.
    "CARD": "T.SURFACE",
    "RAISED": "T.HOVER",
    "NAVY": "T.TEXT",
    "PRIMARY_DARK": "T.COLOR_PRIMARY_DARK",
    "PRIMARY_INK": "T.ON_PRIMARY",
    "ERROR_FG": "T.ERROR",
    "ACCENT": "T.ACCENT",
    "SHADOW": "T.SHADOW_CARD",
}

HEX_MAP = {
    "#0D1014": "T.NAV_BG",
    "#363A40": "T.TRACK",
    "#2F3336": "T.PRIMARY_DISABLED",
    "#1A8CD8": "T.PRIMARY_HOVER",
    "#1878B8": "T.PRIMARY_ACTIVE",
    "#44484F": "T.SCROLL_THUMB",
    "#7A808A": "T.SCROLL_ACTIVE",
    "#656B75": "T.SCROLL_HOVER",
    "#526675": "T.CHECK_BORDER",
    "#137C72": "T.CHECK_MARK",
    "#272A30": "T.HOVER",
    "#168BDD": "T.PRIMARY_HOVER",
    "#183C70": "T.SELECTED_BG",
    "#F5C542": "T.WARNING",
    "#666666": "T.MUTED",
}

NEW_IMPORT = """from . import ui_tokens as T
from .ui_tokens import (
    CARD_WIDTH,
    CONTENT_MAX,
    FONT,
    HIT,
    PAGE_PAD,
    PROGRESS_H,
    ROW_H,
    SPACE_1,
    SPACE_2,
    SPACE_3,
    SPACE_4,
    SPACE_5,
    SPACE_6,
    SPACE_LG,
    SPACE_MD,
    SPACE_SM,
    SPACE_XL,
    SPACE_XS,
    SPLIT_WIDE,
    TYPE_BODY,
    TYPE_BUTTON,
    TYPE_CARD,
    TYPE_FOOT,
    TYPE_HINT,
    TYPE_LABEL,
    TYPE_MARK,
    TYPE_NUM,
    TYPE_TITLE,
    TYPE_TOOL,
)
"""

ALIAS_BLOCK = """CARD = SURFACE
RAISED = HOVER
NAVY = TEXT
PRIMARY_DARK = COLOR_PRIMARY_DARK
PRIMARY_INK = ON_PRIMARY
ERROR_FG = ERROR
ACCENT = PRIMARY
SHADOW = SHADOW_CARD
SPACE_XS = SPACE_1
SPACE_SM = SPACE_2
SPACE_MD = SPACE_4
SPACE_LG = SPACE_5
SPACE_XL = SPACE_6
"""

PATTERN = re.compile(r"(?<![\w.])\b(" + "|".join(sorted(COLOUR_MAP, key=len, reverse=True)) + r")\b(?!\w)")


def retrofit(path, import_old, import_new, alias_block=None, hex_map=None):
    text = path.read_text(encoding="utf-8")
    if import_old not in text:
        raise SystemExit(f"import block not found in {path.name}")
    text = text.replace(import_old, import_new, 1)
    if alias_block:
        if alias_block not in text:
            raise SystemExit(f"alias block not found in {path.name}")
        text = text.replace(alias_block, "", 1)
    text = PATTERN.sub(lambda m: COLOUR_MAP[m.group(1)], text)
    for hex_value, token in (hex_map or {}).items():
        text = text.replace(f'"{hex_value}"', token)
    path.write_text(text, encoding="utf-8")
    print(f"retrofitted {path.name}")


# gui.py: swap the long value import for a live module reference.
gui = PKG / "gui.py"
gui_text = gui.read_text(encoding="utf-8")
start = gui_text.index("from .ui_tokens import (")
end = gui_text.index("\n)\n", start) + len("\n)\n")
gui_text = gui_text[:start] + NEW_IMPORT + gui_text[end:]
if ALIAS_BLOCK not in gui_text:
    raise SystemExit("gui.py alias block not found")
gui_text = gui_text.replace(ALIAS_BLOCK, "", 1)
gui_text = PATTERN.sub(lambda m: COLOUR_MAP[m.group(1)], gui_text)
for hex_value, token in HEX_MAP.items():
    gui_text = gui_text.replace(f'"{hex_value}"', token)
gui.write_text(gui_text, encoding="utf-8")
print("retrofitted gui.py")

# widgets.py
widgets = PKG / "widgets.py"
w = widgets.read_text(encoding="utf-8")
w = w.replace("from .ui_tokens import BORDER, FONT, PRIMARY, SURFACE", "from . import ui_tokens as T\nfrom .ui_tokens import FONT")
w = w.replace("def subject_icon(parent, subject, size=40, bg=SURFACE):", "def subject_icon(parent, subject, size=40, bg=None):\n    bg = bg or T.SURFACE")
w = w.replace("def card_frame(parent, bg=SURFACE, pad=16):", "def card_frame(parent, bg=None, pad=16):\n    bg = bg or T.SURFACE")
w = PATTERN.sub(lambda m: COLOUR_MAP[m.group(1)], w)
widgets.write_text(w, encoding="utf-8")
print("retrofitted widgets.py")

# editor_ui.py
editor = PKG / "editor_ui.py"
e = editor.read_text(encoding="utf-8")
e = e.replace("from .ui_tokens import BG, FONT, TEXT", "from . import ui_tokens as T\nfrom .ui_tokens import FONT")
e = PATTERN.sub(lambda m: COLOUR_MAP[m.group(1)], e)
editor.write_text(e, encoding="utf-8")
print("retrofitted editor_ui.py")

# motion.py
motion = PKG / "motion.py"
m = motion.read_text(encoding="utf-8")
m = m.replace(
    "from .ui_tokens import BG, ERROR, PRIMARY, SUCCESS_BG, SUCCESS_FG, SURFACE",
    "from . import ui_tokens as T",
)
m = m.replace(
    "def circle_transition(self, host, callback, x=None, y=None, color=SUCCESS_BG):",
    "def circle_transition(self, host, callback, x=None, y=None, color=None):\n        color = color or T.SUCCESS_BG",
)
m = m.replace('"#D8D2C6"', "T.BORDER")
m = PATTERN.sub(lambda m: COLOUR_MAP[m.group(1)], m)
motion.write_text(m, encoding="utf-8")
print("retrofitted motion.py")
