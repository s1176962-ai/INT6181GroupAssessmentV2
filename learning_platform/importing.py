"""Preview-first JSON/CSV import for isolated personal question banks."""

import csv
import json
from dataclasses import dataclass
from pathlib import Path

from .models import Question
from .storage import DataError


@dataclass
class ImportPreview:
    path: Path
    rows: list[dict]
    valid: list[Question]

    @property
    def total(self):
        return len(self.rows)

    @property
    def errors(self):
        return sum(row["status"] == "error" for row in self.rows)

    @property
    def duplicates(self):
        return sum(row["status"] == "duplicate" for row in self.rows)


class QuestionImportService:
    MAX_BYTES = 5 * 1024 * 1024
    MAX_RECORDS = 1000

    def __init__(self, personal_repository, public_questions):
        self.personal_repository = personal_repository
        self.public_questions = list(public_questions)

    @staticmethod
    def _fingerprint(question):
        data = question.to_dict()
        data.pop("id", None)
        return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    @staticmethod
    def _csv_record(record):
        converted = {
            key: (value.strip() if isinstance(value, str) else value)
            for key, value in record.items()
        }
        try:
            converted["options"] = json.loads(converted.get("options", ""))
        except (TypeError, json.JSONDecodeError) as exc:
            raise ValueError('options 必须是 JSON 数组，例如 ["A", "B"]') from exc
        option_images = converted.get("option_images", "")
        if option_images:
            try:
                converted["option_images"] = json.loads(option_images)
            except json.JSONDecodeError as exc:
                raise ValueError("option_images 必须留空、为 null 或 JSON 数组") from exc
        else:
            converted["option_images"] = None
        converted["question_image"] = converted.get("question_image") or None
        return converted

    def _records(self, path):
        try:
            if path.suffix.lower() == ".json":
                records = json.loads(path.read_text(encoding="utf-8-sig"))
                if not isinstance(records, list):
                    raise ValueError("JSON 最外层必须是题目数组")
                return records
            if path.suffix.lower() == ".csv":
                with path.open("r", encoding="utf-8-sig", newline="") as handle:
                    reader = csv.DictReader(handle)
                    if not reader.fieldnames:
                        raise ValueError("CSV 必须有标题行")
                    return list(reader)
            raise ValueError("仅支持 .json 和 .csv 文件")
        except (OSError, UnicodeError, json.JSONDecodeError, csv.Error) as exc:
            raise DataError(f"无法读取导入文件 {path}：{exc}") from exc

    def preview(self, source):
        path = Path(source)
        if not path.is_file():
            raise ValueError("请选择存在的 JSON 或 CSV 文件。")
        if path.stat().st_size > self.MAX_BYTES:
            raise ValueError("导入文件不能超过 5 MB。")
        records = self._records(path)
        if not records:
            raise ValueError("导入文件中没有题目。")
        if len(records) > self.MAX_RECORDS:
            raise ValueError("一次最多导入 1000 道题。")
        existing = [*self.public_questions, *self.personal_repository.all()]
        ids = {question.id for question in existing}
        fingerprints = {self._fingerprint(question) for question in existing}
        rows, valid = [], []
        for index, record in enumerate(records, 1):
            try:
                if path.suffix.lower() == ".csv":
                    record = self._csv_record(record)
                question = Question.from_dict(record)
                fingerprint = self._fingerprint(question)
                if question.id in ids:
                    status, message = "duplicate", "题目 ID 已存在，已安全跳过。"
                elif fingerprint in fingerprints:
                    status, message = "duplicate", "题目内容已存在，已安全跳过。"
                else:
                    ids.add(question.id)
                    fingerprints.add(fingerprint)
                    valid.append(question)
                    status, message = "valid", "校验通过"
                rows.append(
                    {
                        "row": index,
                        "id": question.id,
                        "status": status,
                        "message": message,
                        "subject": question.subject,
                        "topic": question.topic,
                        "difficulty": question.difficulty,
                        "question": question.question,
                    }
                )
            except (TypeError, ValueError) as exc:
                item_id = record.get("id", "") if isinstance(record, dict) else ""
                rows.append(
                    {
                        "row": index,
                        "id": str(item_id),
                        "status": "error",
                        "message": str(exc),
                        "subject": "",
                        "topic": "",
                        "difficulty": "",
                        "question": "",
                    }
                )
        return ImportPreview(path, rows, valid)

    def confirm(self, preview):
        if not isinstance(preview, ImportPreview):
            raise ValueError("请先预览并校验导入文件。")
        reserved = {question.id for question in self.public_questions}
        return self.personal_repository.merge(preview.valid, reserved_ids=reserved)
