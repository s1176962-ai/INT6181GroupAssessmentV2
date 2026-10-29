"""Persistent window preferences, independent of monitor resolution."""

from .storage import DataError, JsonStore

SIZES = {
    "auto": (1040, 720),
    "960x640": (960, 640),
    "1080x720": (1080, 720),
    "1280x800": (1280, 800),
}


class DisplaySettings:
    def __init__(self, folder):
        self.store = JsonStore(folder / "display.json", {"size": "auto", "compact": True})

    def load(self):
        data = self.store.read()
        if (
            not isinstance(data, dict)
            or data.get("size") not in SIZES
            or type(data.get("compact")) is not bool
        ):
            raise DataError("Invalid display.json settings")
        return data

    def save(self, size, compact):
        if size not in SIZES or type(compact) is not bool:
            raise ValueError("Invalid display settings")
        self.load()  # Preserve a corrupt file for diagnosis instead of overwriting it.
        self.store.write({"size": size, "compact": compact})


def window_size(size, screen_width, screen_height):
    """Leave space for the taskbar and native window decoration."""
    width, height = SIZES[size]
    return min(width, max(320, screen_width - 80)), min(height, max(320, screen_height - 120))
