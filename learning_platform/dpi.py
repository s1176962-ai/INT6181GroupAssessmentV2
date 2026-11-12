"""Windows high-DPI bootstrap.

``enable()`` must run before ``tk.Tk()`` is created: without process DPI
awareness Windows renders the whole Tk window at 96 dpi and bitmap-stretches it
to the physical resolution, which is what makes text and 1px rules look blurry
at 125% / 150%. After enabling, Tk uses the real dpi for font rasterisation and
``apply_to()`` keeps Tk's point-to-pixel conversion in step with it.

All geometry in the redesigned widgets goes through ``tokens.px()``, which uses
the same scale, so controls and type grow together instead of overflowing.
"""

import ctypes
import sys

from . import tokens

_enabled = False


def _system_dpi() -> int:
    if sys.platform != "win32":
        return 96
    try:
        get_dpi = ctypes.windll.user32.GetDpiForSystem
        get_dpi.restype = ctypes.c_uint
        return int(get_dpi()) or 96
    except (AttributeError, OSError):
        pass
    try:
        hdc = ctypes.windll.user32.GetDC(0)
        dpi = ctypes.windll.gdi32.GetDeviceCaps(hdc, 88)  # LOGPIXELSX
        ctypes.windll.user32.ReleaseDC(0, hdc)
        return int(dpi) or 96
    except (AttributeError, OSError):
        return 96


def enable() -> float:
    """Set process DPI awareness once and publish the scale to tokens."""
    global _enabled
    if _enabled:
        return tokens.scale()
    if sys.platform == "win32":
        try:
            # PROCESS_SYSTEM_DPI_AWARE = 1. Falls back for older Windows builds.
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except (AttributeError, OSError):
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except (AttributeError, OSError):
                pass
    scale = tokens.set_scale(_system_dpi() / 96.0)
    _enabled = True
    return scale


def apply_to(root) -> None:
    """Align Tk scaling with the real dpi after the root window exists."""
    if sys.platform != "win32" or not _enabled:
        return
    try:
        # 96 dpi -> Tk's native 1.3333; 125% -> 1.6667; 150% -> 2.0.
        root.tk.call("tk", "scaling", f"{1.333333 * tokens.scale():.4f}")
    except Exception:
        pass
