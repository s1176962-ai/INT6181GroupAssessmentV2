"""JSON storage, adapted from the original project's atomic JsonStore."""

import copy
import json
import os
import tempfile
from pathlib import Path


class DataError(ValueError):
    """An actionable file or data-format error."""


class JsonStore:
    def __init__(self, path, default):
        self.path = Path(path)
        self.default = default

    def read(self):
        if not self.path.exists():
            return copy.deepcopy(self.default)
        try:
            return json.loads(self.path.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError) as exc:
            raise DataError(
                f"Cannot read {self.path}: {exc}. Repair the file or move it aside to start fresh."
            ) from exc

    def write(self, value):
        name = None
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            fd, name = tempfile.mkstemp(dir=self.path.parent, prefix=".tmp-")
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(value, handle, ensure_ascii=False, indent=2, allow_nan=False)
                handle.flush()
                os.fsync(handle.fileno())
            Path(name).replace(self.path)
        except (OSError, ValueError) as exc:
            raise DataError(f"Cannot save {self.path}: {exc}") from exc
        finally:
            if name and os.path.exists(name):
                os.unlink(name)
