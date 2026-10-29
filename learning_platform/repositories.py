"""Load question banks and validate persisted learning records."""

from datetime import datetime
from pathlib import Path

from .models import Question, score
from .storage import DataError, JsonStore


class QuestionRepository:
    def __init__(self, folder):
        self.folder = Path(folder)
        self.warnings = []

    def all(self):
        questions, seen = [], set()
        self.warnings = []
        files = sorted(self.folder.glob("*.json"))
        if not files:
            self.warnings.append(f"No question files in {self.folder}")
        for path in files:
            try:
                records = JsonStore(path, []).read()
                if not isinstance(records, list):
                    raise DataError(f"{path.name}: expected a JSON array")
            except DataError as exc:
                self.warnings.append(str(exc))
                continue
            for index, record in enumerate(records, 1):
                try:
                    question = Question.from_dict(record)
                    if question.id in seen:
                        raise ValueError(f"Duplicate question ID: {question.id}")
                    seen.add(question.id)
                    questions.append(question)
                except ValueError as exc:
                    self.warnings.append(f"{path.name}, record {index}: {exc}")
        return questions


class ProgressRepository:
    def __init__(self, path):
        self.store = JsonStore(path, {"wrong": {}, "history": []})

    def load(self):
        data = self.store.read()
        try:
            if not isinstance(data, dict) or set(data) != {"wrong", "history"}:
                raise ValueError("Expected wrong and history fields")
            if not isinstance(data["wrong"], dict) or not isinstance(data["history"], list):
                raise ValueError("wrong must be an object; history must be an array")
            for key, record in data["wrong"].items():
                if (
                    not isinstance(key, str)
                    or not key
                    or not isinstance(record, dict)
                    or type(record.get("count")) is not int
                    or record["count"] < 1
                    or not isinstance(record.get("last_answer"), str)
                ):
                    raise ValueError("Invalid wrong-question record")
                datetime.fromisoformat(record["last_seen"])
            ids = set()
            for record in data["history"]:
                if not isinstance(record, dict):
                    raise ValueError("Invalid history record")
                if not isinstance(record["id"], str) or not record["id"] or record["id"] in ids:
                    raise ValueError("Invalid or duplicate history ID")
                ids.add(record["id"])
                datetime.fromisoformat(record["date"])
                if not isinstance(record["subject"], str) or record["mode"] not in (
                    "quiz",
                    "review",
                ):
                    raise ValueError("Invalid history subject or mode")
                expected = score(record["total"], record["correct"])
                if any(record.get(key) != value for key, value in expected.items()):
                    raise ValueError("Inconsistent history score")
        except (KeyError, TypeError, ValueError) as exc:
            raise DataError(
                f"Invalid progress file {self.store.path}: {exc}. Original data is preserved; repair or move the file aside."
            ) from exc
        return data

    def save(self, data):
        self.store.write(data)
