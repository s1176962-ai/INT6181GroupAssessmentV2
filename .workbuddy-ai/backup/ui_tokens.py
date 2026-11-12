"""Runtime-switchable design tokens. This module is the single source of truth.

Import the module (``from . import ui_tokens as T``) and read colour tokens as
``T.BG`` at render time. Colours are rebound by :func:`set_theme`, so importing
values directly (``from .ui_tokens import BG``) would freeze one palette.
Typography and geometry tokens never change with the theme.
"""

FONT = "Microsoft YaHei UI"

TYPE_MARK = (FONT, 11, "bold")
TYPE_TITLE = (FONT, 22, "bold")
TYPE_CARD = (FONT, 16, "bold")
TYPE_LABEL = (FONT, 10)
TYPE_BODY = (FONT, 11)
TYPE_HINT = (FONT, 10)
TYPE_FOOT = (FONT, 9)
TYPE_BUTTON = (FONT, 12, "bold")
TYPE_TOOL = (FONT, 10)
TYPE_NUM = ("Consolas", 11)
TYPE_QUESTION = (FONT, 15)

RADIUS_SM = 8
RADIUS_MD = 10
RADIUS_LG = 12

SPACE_1 = 4
SPACE_2 = 8
SPACE_3 = 12
SPACE_4 = 16
SPACE_5 = 24
SPACE_6 = 32
SPACE_7 = 48

SPACE_XS = SPACE_1
SPACE_SM = SPACE_2
SPACE_MD = SPACE_4
SPACE_LG = SPACE_5
SPACE_XL = SPACE_6

PROGRESS_H = 3
CARD_WIDTH = 420
SPLIT_WIDE = 900
HIT = 44
ROW_H = 32
DURATION_FAST_MS = 120
CONTENT_MAX = 1080
PAGE_PAD = 28
WINDOW_MIN = (720, 560)
WINDOW_SIZE = "1180x760"


def _palette(**colors):
    """Expand a small colour set into every public token name."""
    p = dict(colors)
    p["COLOR_PRIMARY"] = p["PRIMARY"]
    p["COLOR_PRIMARY_DARK"] = p["PRIMARY_ACTIVE"]
    p["TEXT"] = p["COLOR_TEXT"]
    p["MUTED"] = p["COLOR_MUTED"]
    p["BORDER"] = p["COLOR_BORDER"]
    p["SURFACE"] = p["COLOR_SURFACE"]
    p["BG"] = p["COLOR_PAGE"]
    p["ACCENT"] = p["COLOR_ACCENT"]
    p["BUTTON_FILL"] = p["COLOR_BUTTON"]
    p["BUTTON_INK"] = p["COLOR_BUTTON_INK"]
    p["SHADOW"] = p["SHADOW_CARD"]
    return p


# X "Lights Out" — near-black instead of pure black to reduce glare.
_DARK = _palette(
    COLOR_PAGE="#0C0E11",
    COLOR_SURFACE="#16181C",
    COLOR_RAISED="#1D1F23",
    COLOR_TEXT="#E7E9EA",
    COLOR_MUTED="#8B949E",
    COLOR_BORDER="#2F3336",
    COLOR_ACCENT="#1D9BF0",
    COLOR_BUTTON="#1D9BF0",
    COLOR_BUTTON_INK="#FFFFFF",
    PRIMARY="#1D9BF0",
    PRIMARY_HOVER="#1A8CD8",
    PRIMARY_ACTIVE="#1878B8",
    PRIMARY_DISABLED="#2F3336",
    ON_PRIMARY="#FFFFFF",
    HOVER="#1D1F23",
    TRACK="#161616",
    ERROR="#F4212E",
    ERROR_BG="#2A1216",
    WARNING="#C4A36A",
    WARNING_BG="#241E14",
    INFO="#1D9BF0",
    INFO_BG="#14181C",
    SUCCESS_BG="#122018",
    SUCCESS_FG="#00BA7C",
    SELECTED_BG="#141A1E",
    SKY="#0C0E11",
    SHADOW_CARD="#2F3336",
    NAV_BG="#0A0C0F",
    SCROLL_THUMB="#44484F",
    SCROLL_HOVER="#656B75",
    SCROLL_ACTIVE="#7A808A",
    CHECK_BORDER="#526675",
    CHECK_MARK="#137C72",
)

# Daylight — white cards on a soft grey canvas, one restrained blue accent.
_LIGHT = _palette(
    COLOR_PAGE="#F6F7F9",
    COLOR_SURFACE="#FFFFFF",
    COLOR_RAISED="#F0F2F5",
    COLOR_TEXT="#1B2028",
    COLOR_MUTED="#6B7280",
    COLOR_BORDER="#E2E6EB",
    COLOR_ACCENT="#2563EB",
    COLOR_BUTTON="#2563EB",
    COLOR_BUTTON_INK="#FFFFFF",
    PRIMARY="#2563EB",
    PRIMARY_HOVER="#1D4ED8",
    PRIMARY_ACTIVE="#1E40AF",
    PRIMARY_DISABLED="#C9D4E5",
    ON_PRIMARY="#FFFFFF",
    HOVER="#F0F2F5",
    TRACK="#E7EAEF",
    ERROR="#DC2626",
    ERROR_BG="#FEF2F2",
    WARNING="#B45309",
    WARNING_BG="#FFFBEB",
    INFO="#2563EB",
    INFO_BG="#EFF6FF",
    SUCCESS_BG="#ECFDF5",
    SUCCESS_FG="#047857",
    SELECTED_BG="#DBEAFE",
    SKY="#EEF3FA",
    SHADOW_CARD="#E2E6EB",
    NAV_BG="#FFFFFF",
    SCROLL_THUMB="#CBD2DB",
    SCROLL_HOVER="#AEB7C2",
    SCROLL_ACTIVE="#94A0AD",
    CHECK_BORDER="#9AA7B4",
    CHECK_MARK="#0F766E",
)

THEMES = {"dark": _DARK, "light": _LIGHT}
_current_theme = "dark"


def theme_name():
    """Return the active theme key."""
    return _current_theme


def set_theme(name):
    """Rebind every colour token in this module and return the applied key."""
    global _current_theme
    if name not in THEMES:
        raise ValueError(f"Unknown theme: {name}")
    globals().update(THEMES[name])
    _current_theme = name
    return name


set_theme("dark")
