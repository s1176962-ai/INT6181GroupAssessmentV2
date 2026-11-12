"""Single source of truth for the Quiz Studio visual language.

Every colour, radius, spacing step, type ramp, shadow and control dimension used
by the interface is declared here. Nothing else in the codebase may hard-code a
style value. :func:`set_theme` rebinds the whole colour palette at runtime, so
colours must always be read as ``T.<TOKEN>`` at render time, never imported by
value and never captured in a function default.

Tkinter limitations (documented here so the rest of the code stays honest):
  * Tk has no alpha compositing, so the requested CSS shadows are stored both as
    their original rgba tuples and as pre-blended opaque colours that Canvas can
    paint. Two offset rounded layers approximate the two CSS shadow bands.
  * Tk font sizes are points, not pixels. ``font_at`` converts the design px
    scale to points at a 96 dpi baseline (1px = 0.75pt); Tk's own ``tk scaling``
    then handles the physical dpi scaling after DPI awareness is enabled.
  * ttk cannot draw real rounded corners; ``modern.py`` paints them on Canvas.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Typography
# ---------------------------------------------------------------------------
FONT = "Microsoft YaHei UI"
FONT_FALLBACK = "Segoe UI"
FONT_MONO = "Consolas"

PX_TITLE = 15          # 15px / 500
PX_BODY = 13           # 13px / 400
PX_BODY_LARGE = 14     # 14px / 400
PX_CAPTION = 12        # 12px / 400
LINE_HEIGHT = 1.5

# 8pt grid. Only these steps may be used for spacing.
SPACE_1 = 4
SPACE_2 = 8
SPACE_3 = 12
SPACE_4 = 16
SPACE_5 = 24
SPACE_6 = 32
SPACE_XS = SPACE_1
SPACE_SM = SPACE_2
SPACE_MD = SPACE_4
SPACE_LG = SPACE_5
SPACE_XL = SPACE_6

# Legacy alias kept for older modules; new code must not use it.
SPACE_7 = 48

# Radii (px)
RADIUS_CARD = 12
RADIUS_CONTROL = 9
RADIUS_CHIP = 8
RADIUS_AVATAR = 0.5     # 50% of the avatar diameter
RADIUS_SM = RADIUS_CHIP
RADIUS_MD = RADIUS_CONTROL
RADIUS_LG = RADIUS_CARD

# Geometry (px) -- all consumed through px() so high-dpi layouts stay aligned.
CONTROL_H = 36
ICON = 16
TOPBAR_H = 54
NAV_W = 224
NAV_INDICATOR = 3
CARD_PAD = 24
FOCUS_RING = 3
FIELD_GAP = 8          # label -> control
GROUP_GAP = 24         # between field groups
HAIRLINE = 1
PROGRESS_H = 3
CARD_WIDTH = 460
SPLIT_WIDE = 900
HIT = 44
ROW_H = 32
# A maximized 2K/4K window should be used, not surrounded by dead margins.
# content_w is still clamped by the viewport width, so small windows are unchanged.
CONTENT_MAX = 1600
CONTENT_MIN = 520
PAGE_PAD = 24
WINDOW_MIN = (720, 560)
WINDOW_SIZE = "1180x760"
DURATION_FAST_MS = 120

# Shadows: original CSS specification + opaque equivalents for Canvas painting.
SHADOW_RGBA_NEAR = (16, 24, 40, 0.04)   # 0 1px 2px
SHADOW_RGBA_FAR = (16, 24, 40, 0.06)    # 0 8px 24px
SHADOW_OFFSET_NEAR = 1
SHADOW_OFFSET_FAR = 8
SHADOW_BLUR_FAR = 24


def _hex(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))


def _rgb(value: tuple[int, int, int]) -> str:
    return "#%02X%02X%02X" % value


def mix(left: str, right: str, amount: float) -> str:
    """Blend two colours; ``amount`` is the weight of ``right`` (0..1)."""
    a, b = _hex(left), _hex(right)
    return _rgb(tuple(round(x + (y - x) * amount) for x, y in zip(a, b)))


def _shadow(page: str, rgba: tuple[int, int, int, float]) -> str:
    """Pre-blend a CSS rgba shadow onto the page colour (Tk has no alpha)."""
    return mix(page, _rgb(rgba[:3]), rgba[3])


# ---------------------------------------------------------------------------
# Palettes. Only the values below are authored; every other colour token is
# derived from them so there is exactly one place to change the theme.
# ---------------------------------------------------------------------------
_LIGHT_BASE = {
    "PAGE": "#F7F8FA",
    "SURFACE": "#FFFFFF",
    "NAV": "#F8F9FC",
    "BORDER_LIGHT": "#E9ECF1",
    "BORDER_CONTROL": "#DFE4EC",
    "PRIMARY": "#2F6BFF",
    "PRIMARY_SOFT": "#EEF3FF",
    "TEXT": "#1B2430",
    "TEXT_SECONDARY": "#6B7688",
    "TEXT_MUTED": "#9AA5B5",
}

_DARK_BASE = {
    "PAGE": "#14171C",
    "SURFACE": "#1C2027",
    "NAV": "#191D23",
    "BORDER_LIGHT": "#2C323C",
    "BORDER_CONTROL": "#2C323C",
    "PRIMARY": "#5B83FF",
    "PRIMARY_SOFT": "#1E2A45",
    "TEXT": "#E8ECF2",
    "TEXT_SECONDARY": "#9AA5B5",
    "TEXT_MUTED": "#77828F",
}


def _expand(base: dict[str, str]) -> dict[str, str]:
    """Derive the complete token surface from the authored base colours."""
    page = base["PAGE"]
    surface = base["SURFACE"]
    text = base["TEXT"]
    primary = base["PRIMARY"]
    p = dict(base)
    p.update(
        {
            "ON_PRIMARY": "#FFFFFF",
            "PRIMARY_HOVER": mix(primary, "#000000", 0.12),
            "PRIMARY_ACTIVE": mix(primary, "#000000", 0.22),
            "PRIMARY_DISABLED": mix(primary, surface, 0.62),
            "RAISED": mix(surface, text, 0.045),
            "HOVER": mix(surface, text, 0.05),
            "PRESSED": mix(surface, text, 0.09),
            "TRACK": mix(page, text, 0.10),
            "SELECTED_BG": base["PRIMARY_SOFT"],
            "SKY": mix(page, surface, 0.55),
            "NAV_BG": base["NAV"],
            "NAV_SELECTED": base["PRIMARY_SOFT"],
            "SEGMENT_TRACK": mix(page, text, 0.055),
            # The selected capsule must read as "raised": white in light mode,
            # a lighter surface in dark mode (SURFACE alone is darker than the
            # dark track and would make the selection invisible).
            "SEGMENT_SELECTED": (
                surface if page == _LIGHT_BASE["PAGE"] else mix(surface, text, 0.10)
            ),
            "FOCUS_GLOW": mix(surface, primary, 0.22),
            # Ask AI surfaces: the old layout used neutral grey (HOVER), which
            # read as a foreign colour next to the blue accent. The composer is
            # the primary tint itself; the reply area is a half-step tint so the
            # two blocks separate without another grey.
            "AI_INPUT_BG": base["PRIMARY_SOFT"],
            "AI_INPUT_EDGE": mix(base["PRIMARY_SOFT"], primary, 0.18),
            # Light: a half-step blue tint on white. Dark: PRIMARY_SOFT is close
            # to SURFACE, so mix in the accent instead or the panel disappears.
            "AI_REPLY_BG": (
                mix(surface, base["PRIMARY_SOFT"], 0.72)
                if page == _LIGHT_BASE["PAGE"]
                else mix(surface, primary, 0.10)
            ),
            "AI_REPLY_EDGE": mix(
                mix(surface, base["PRIMARY_SOFT"], 0.72)
                if page == _LIGHT_BASE["PAGE"]
                else mix(surface, primary, 0.10),
                primary,
                0.16,
            ),
            "SHADOW_NEAR": _shadow(page, SHADOW_RGBA_NEAR),
            "SHADOW_FAR": _shadow(page, SHADOW_RGBA_FAR),
            "ERROR": "#DC2626" if page == _LIGHT_BASE["PAGE"] else "#F4212E",
            "WARNING": "#B45309" if page == _LIGHT_BASE["PAGE"] else "#C4A36A",
            "SUCCESS_FG": "#047857" if page == _LIGHT_BASE["PAGE"] else "#00BA7C",
        }
    )
    p["ERROR_BG"] = mix(p["ERROR"], page, 0.90)
    p["WARNING_BG"] = mix(p["WARNING"], page, 0.90)
    p["SUCCESS_BG"] = mix(p["SUCCESS_FG"], page, 0.90)
    p["INFO"] = primary
    p["INFO_BG"] = base["PRIMARY_SOFT"]
    p["SCROLL_THUMB"] = mix(text, page, 0.72)
    p["SCROLL_HOVER"] = mix(text, page, 0.60)
    p["SCROLL_ACTIVE"] = mix(text, page, 0.48)
    p["CHECK_BORDER"] = base["BORDER_CONTROL"]
    p["CHECK_MARK"] = primary
    p["DISABLED_INK"] = base["TEXT_MUTED"]
    p["DISABLED_FILL"] = mix(surface, text, 0.045)

    # Compatibility aliases used by the pre-existing 4k-line GUI module.
    p.update(
        {
            "COLOR_PAGE": page,
            "COLOR_SURFACE": surface,
            "COLOR_RAISED": p["RAISED"],
            "COLOR_TEXT": text,
            "COLOR_MUTED": base["TEXT_SECONDARY"],
            "COLOR_BORDER": base["BORDER_LIGHT"],
            "COLOR_ACCENT": primary,
            "COLOR_BUTTON": primary,
            "COLOR_BUTTON_INK": p["ON_PRIMARY"],
            "COLOR_PRIMARY": primary,
            "COLOR_PRIMARY_DARK": p["PRIMARY_ACTIVE"],
            "BG": page,
            "TEXT": text,
            "MUTED": base["TEXT_SECONDARY"],
            "BORDER": base["BORDER_LIGHT"],
            "SURFACE": surface,
            "RAISED": p["RAISED"],
            "ACCENT": primary,
            "BUTTON_FILL": primary,
            "BUTTON_INK": p["ON_PRIMARY"],
            "SHADOW": base["BORDER_LIGHT"],
            "SHADOW_CARD": base["BORDER_LIGHT"],
        }
    )
    return p


THEMES = {"light": _expand(_LIGHT_BASE), "dark": _expand(_DARK_BASE)}
_current_theme = "dark"

# DPI scale is set once by dpi.enable(), before any window is created.
_scale = 1.0


def set_scale(scale: float) -> float:
    """Record the physical dpi scale used by px()."""
    global _scale
    _scale = max(1.0, min(float(scale), 3.0))
    return _scale


def scale() -> float:
    return _scale


def px(value: float) -> int:
    """Convert a design-space pixel value to a physical pixel value."""
    return max(1, round(value * _scale))


def font_at(px_size: int, weight: str = "normal") -> tuple:
    """Design px -> Tk point size (96 dpi baseline)."""
    points = max(1, round(px_size * 0.75))
    return (FONT, points, weight) if weight != "normal" else (FONT, points)


# Type ramp. Legacy names are preserved so existing pages keep working, but all
# of them now live in this one file.
TYPE_HEADING = font_at(PX_TITLE, "bold")       # 15px / 500 (Tk has no 500 -> bold)
TYPE_BODY = font_at(PX_BODY)                   # 13px / 400
TYPE_BODY_LARGE = font_at(PX_BODY_LARGE)       # 14px / 400
TYPE_CAPTION = font_at(PX_CAPTION)             # 12px / 400
TYPE_MARK = (FONT, 11, "bold")
TYPE_TITLE = (FONT, 22, "bold")                # legacy display headline
TYPE_HERO = font_at(38, "bold")                # login brand headline (38px design)
TYPE_KICKER = font_at(16, "bold")              # small caps wordmark / eyebrow
TYPE_CARD = (FONT, 15, "bold")
TYPE_LABEL = TYPE_BODY_LARGE
TYPE_HINT = TYPE_CAPTION
TYPE_FOOT = (FONT, 9)
TYPE_BUTTON = (FONT, 11, "bold")
TYPE_TOOL = (FONT, 10)
TYPE_NUM = (FONT_MONO, 11)
TYPE_QUESTION = (FONT, 15)


def theme_name() -> str:
    return _current_theme


def set_theme(name: str) -> str:
    """Rebind the active palette; callers must re-read tokens afterwards."""
    global _current_theme
    if name not in THEMES:
        raise ValueError(f"Unknown theme: {name}")
    _current_theme = name
    return name


def palette() -> dict[str, str]:
    """Return every colour token of the active theme (for runtime rebinding)."""
    return dict(THEMES[_current_theme])


set_theme("dark")
