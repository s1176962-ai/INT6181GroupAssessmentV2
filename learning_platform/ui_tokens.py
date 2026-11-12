"""Runtime-switchable design tokens (compatibility surface).

The values themselves live in :mod:`learning_platform.tokens` -- this module is
only a re-export plus the runtime colour rebind that the existing GUI relies on.
Import it as ``from . import ui_tokens as T`` and read colours as ``T.BG`` at
render time; ``set_theme()`` rebinds every colour in this module's globals.
"""

from . import tokens as _tokens
from .tokens import (
    CARD_PAD,
    CARD_WIDTH,
    CONTENT_MAX,
    CONTENT_MIN,
    CONTROL_H,
    DURATION_FAST_MS,
    FIELD_GAP,
    FOCUS_RING,
    FONT,
    FONT_FALLBACK,
    FONT_MONO,
    GROUP_GAP,
    HAIRLINE,
    HIT,
    ICON,
    LINE_HEIGHT,
    NAV_INDICATOR,
    NAV_W,
    PAGE_PAD,
    PROGRESS_H,
    PX_BODY,
    PX_BODY_LARGE,
    PX_CAPTION,
    PX_TITLE,
    RADIUS_AVATAR,
    RADIUS_CARD,
    RADIUS_CHIP,
    RADIUS_CONTROL,
    RADIUS_LG,
    RADIUS_MD,
    RADIUS_SM,
    ROW_H,
    SHADOW_BLUR_FAR,
    SHADOW_OFFSET_FAR,
    SHADOW_OFFSET_NEAR,
    SHADOW_RGBA_FAR,
    SHADOW_RGBA_NEAR,
    SPACE_1,
    SPACE_2,
    SPACE_3,
    SPACE_4,
    SPACE_5,
    SPACE_6,
    SPACE_7,
    SPACE_LG,
    SPACE_MD,
    SPACE_SM,
    SPACE_XL,
    SPACE_XS,
    SPLIT_WIDE,
    THEMES,
    TOPBAR_H,
    TYPE_BODY,
    TYPE_BODY_LARGE,
    TYPE_BUTTON,
    TYPE_CAPTION,
    TYPE_CARD,
    TYPE_FOOT,
    TYPE_HEADING,
    TYPE_HERO,
    TYPE_HINT,
    TYPE_KICKER,
    TYPE_LABEL,
    TYPE_MARK,
    TYPE_NUM,
    TYPE_QUESTION,
    TYPE_TITLE,
    TYPE_TOOL,
    WINDOW_MIN,
    WINDOW_SIZE,
    font_at,
    mix,
    px,
    scale,
    set_scale,
)


def set_theme(name):
    """Rebind every colour token in this module and return the applied key."""
    applied = _tokens.set_theme(name)
    globals().update(_tokens.palette())
    return applied


def theme_name():
    return _tokens.theme_name()


def palette():
    return _tokens.palette()


set_theme("dark")
