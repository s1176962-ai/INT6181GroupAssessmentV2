"""Safe question maintenance; preserve original records and create backups."""

import shutil
import tkinter as tk
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from .models import Question
from .repositories import QuestionRepository
from .storage import DataError, JsonStore


class QuestionEditor:
    """Mutations target one source file and reject ambiguous or stale records."""

    def __init__(self, folder: Path, authorize=None):
        self.folder = Path(folder)
        self.authorize = authorize

    def _records(self) -> dict:
        if self.authorize:
            self.authorize()
        files = {}
        for path in sorted(self.folder.glob("*.json")):
            records = JsonStore(path, []).read()
            if not isinstance(records, list):
                raise DataError(f"请先修复题库文件：{path}")
            files[path] = records
        return files

    def _find(self, files: dict, question_id: str) -> list:
        return [
            (path, index)
            for path, records in files.items()
            for index, record in enumerate(records)
            if isinstance(record, dict) and record.get("id") == question_id
        ]

    def all(self):
        if self.authorize:
            self.authorize()
        return QuestionRepository(self.folder).all()

    def merge(self, questions, reserved_ids=()):
        files = self._records()
        existing_ids = {
            record.get("id")
            for records in files.values()
            for record in records
            if isinstance(record, dict)
        } | set(reserved_ids)
        added = []
        for question in questions:
            if question.id not in existing_ids:
                existing_ids.add(question.id)
                added.append(question)
        if added:
            path = self.folder / "custom.json"
            records = files.get(path, []) + [question.to_dict() for question in added]
            self._commit(path, records)
        return added

    def _commit(self, path: Path, records: list) -> None:
        # Backups live outside the scanned *.json directory to avoid duplicate IDs.
        if path.exists():
            backup = self.folder.parent / "backups"
            try:
                backup.mkdir(parents=True, exist_ok=True)
                stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
                shutil.copy2(path, backup / f"{path.stem}-{stamp}-{uuid4().hex}.json")
            except OSError as exc:
                raise DataError(f"备份失败，未修改题库：{exc}") from exc
        JsonStore(path, []).write(records)

    def save(self, question: Question, original: Question | None = None) -> None:
        Question.from_dict(asdict(question))
        files = self._records()
        matches = self._find(files, question.id)
        if original is None:
            if matches:
                raise ValueError("题目 ID 已存在，请使用不同的 ID。")
            path = self.folder / "custom.json"
            records = files.get(path, []) + [asdict(question)]
        else:
            if question.id != original.id or len(matches) != 1:
                raise ValueError("题目 ID 不可更改，且必须唯一。请刷新题库后重试。")
            path, index = matches[0]
            records = files[path]
            if Question.from_dict(records[index]) != original:
                raise ValueError("该题已被其他操作修改，请返回列表刷新后重新编辑。")
            # Retain extension fields not represented in the current form.
            records[index] = {**records[index], **asdict(question)}
        self._commit(path, records)

    def delete(self, original: Question) -> None:
        files = self._records()
        matches = self._find(files, original.id)
        if len(matches) != 1:
            raise ValueError("题目不存在或 ID 重复，请刷新后重试。")
        path, index = matches[0]
        if Question.from_dict(files[path][index]) != original:
            raise ValueError("题目已被修改，请刷新后重试。")
        del files[path][index]
        self._commit(path, files[path])


def import_image(root: Path, source: Path, master: tk.Misc) -> str:
    """Validate a local image with Tk, then copy it under a unique asset name."""
    source = Path(source)
    try:
        if source.suffix.lower() not in {".png", ".gif", ".ppm", ".pgm"}:
            raise ValueError("请选择 PNG、GIF、PPM 或 PGM 图片。JPEG 请先转换成 PNG。")
        if source.stat().st_size > 10 * 1024 * 1024:
            raise ValueError("图片不能超过 10 MB。")
        photo = tk.PhotoImage(master=master, file=str(source))
        if photo.width() * photo.height() > 16_000_000:
            raise ValueError("图片不能超过 1600 万像素。")
        target = Path(root) / "assets" / "uploads" / f"{uuid4().hex}{source.suffix.lower()}"
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        return target.relative_to(root).as_posix()
    except (OSError, tk.TclError) as exc:
        raise ValueError(f"无法导入图片：{exc}") from exc
