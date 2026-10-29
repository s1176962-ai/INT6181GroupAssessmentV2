"""Explicit UI catalogs; question-bank content is never machine-translated."""

import json
from pathlib import Path

from .storage import DataError, JsonStore


class Translator:
    def __init__(self, data_dir: Path):
        self.store = JsonStore(Path(data_dir) / "settings.json", {"language": "zh"})
        self.warning = ""
        try:
            self.language = self._settings()["language"]
        except DataError as exc:
            self.language = "zh"
            self.warning = str(exc)
        catalog = Path(__file__).with_name("locales") / "en.json"
        self.english = json.loads(catalog.read_text(encoding="utf-8"))

    def _settings(self):
        data = self.store.read()
        if not isinstance(data, dict) or data.get("language") not in {"zh", "en"}:
            raise DataError("语言设置文件损坏，请修复或备份后移走 settings.json。")
        return data

    def motion_enabled(self) -> bool:
        # Default off so scoring/navigation stay snappy; users can enable in Settings.
        try:
            return self._settings().get("motion", False) is True
        except DataError:
            return False

    def set_motion(self, enabled: bool):
        data = self._settings()
        data["motion"] = bool(enabled)
        self.store.write(data)

    def set_language(self, language: str):
        if language not in {"zh", "en"}:
            raise ValueError("Unsupported language")
        data = self._settings()
        data["language"] = language
        self.store.write(data)
        self.language = language

    def __call__(self, text: str, *values) -> str:
        template = self.english.get(text, text) if self.language == "en" else text
        if self.language == "en" and template == text and not values:
            # Translate known diagnostic prefixes while leaving paths and user data intact.
            for source, target in self.english.items():
                if source.endswith("：") and text.startswith(source):
                    return target + text[len(source) :]
        values = tuple(
            self(str(value)) if isinstance(value, Exception) else value for value in values
        )
        return template.format(*values) if values else template
