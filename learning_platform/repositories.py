"""Load question banks and validate persisted learning records."""

from datetime import datetime, timedelta
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


class PersonalQuestionRepository:
    """Strict per-account question bank; malformed data is never overwritten."""

    def __init__(self, path):
        self.store = JsonStore(path, [])

    def all(self):
        records = self.store.read()
        if not isinstance(records, list):
            raise DataError(f"个人题库损坏，原文件已保留：{self.store.path}")
        questions, seen = [], set()
        try:
            for index, record in enumerate(records, 1):
                question = Question.from_dict(record)
                if question.id in seen:
                    raise ValueError(f"第 {index} 条题目 ID 重复：{question.id}")
                seen.add(question.id)
                questions.append(question)
        except ValueError as exc:
            raise DataError(f"个人题库损坏，原文件已保留：{self.store.path}；{exc}") from exc
        return questions

    def merge(self, questions, reserved_ids=()):
        existing = self.all()
        seen = {question.id for question in existing} | set(reserved_ids)
        added = []
        for question in questions:
            if question.id not in seen:
                seen.add(question.id)
                added.append(question)
        if added:
            self.store.write([question.to_dict() for question in [*existing, *added]])
        return added

    def save(self, question, original=None, reserved_ids=()):
        questions = self.all()
        ids = {item.id for item in questions} | set(reserved_ids)
        if original is None:
            if question.id in ids:
                raise ValueError("题目 ID 已存在，请使用不同的 ID。")
            questions.append(question)
        else:
            matches = [index for index, item in enumerate(questions) if item.id == original.id]
            if question.id != original.id or len(matches) != 1:
                raise ValueError("题目 ID 不可更改，且必须唯一。请刷新题库后重试。")
            index = matches[0]
            if questions[index] != original:
                raise ValueError("该题已被其他操作修改，请返回列表刷新后重新编辑。")
            questions[index] = question
        self.store.write([item.to_dict() for item in questions])

    def delete(self, original):
        questions = self.all()
        matches = [index for index, item in enumerate(questions) if item.id == original.id]
        if len(matches) != 1 or questions[matches[0]] != original:
            raise ValueError("题目不存在或已被修改，请刷新后重试。")
        del questions[matches[0]]
        self.store.write([item.to_dict() for item in questions])


class LearningPlanRepository:
    DEFAULT_GOAL = 20
    DEFAULT_SETTINGS = {
        "bank_kind": "public",
        "subject": None,
        "difficulty": None,
    }

    def __init__(self, path):
        self.store = JsonStore(
            path,
            {
                "daily_goal": self.DEFAULT_GOAL,
                "answers": [],
                **self.DEFAULT_SETTINGS,
            },
        )

    def load(self):
        data = self.store.read()
        try:
            if not isinstance(data, dict):
                raise ValueError("学习计划必须是对象")
            required = {"daily_goal", "answers"}
            allowed = required | set(self.DEFAULT_SETTINGS)
            if not required.issubset(data) or not set(data).issubset(allowed):
                raise ValueError("学习计划字段无效")
            if type(data["daily_goal"]) is not int or not 1 <= data["daily_goal"] <= 500:
                raise ValueError("daily_goal 必须是 1–500 的整数")
            if not isinstance(data["answers"], list):
                raise ValueError("answers 必须是数组")
            ids = set()
            for event in data["answers"]:
                if not isinstance(event, dict) or set(event) != {"id", "answered_at"}:
                    raise ValueError("答题事件格式无效")
                if not isinstance(event["id"], str) or not event["id"] or event["id"] in ids:
                    raise ValueError("答题事件 ID 无效或重复")
                ids.add(event["id"])
                timestamp = datetime.fromisoformat(event["answered_at"])
                if timestamp.tzinfo is None:
                    raise ValueError("答题时间必须包含时区")
            bank_kind = data.get("bank_kind", "public")
            if bank_kind not in {"public", "personal"}:
                raise ValueError("bank_kind 必须是 public 或 personal")
            for field in ("subject", "difficulty"):
                value = data.get(field)
                if value is not None and (not isinstance(value, str) or not value.strip()):
                    raise ValueError(f"{field} 必须是非空字符串或 null")
        except (TypeError, ValueError) as exc:
            raise DataError(f"学习计划损坏，原文件已保留：{self.store.path}；{exc}") from exc
        return {**self.DEFAULT_SETTINGS, **data}

    def set_goal(self, goal):
        if type(goal) is not int or not 1 <= goal <= 500:
            raise ValueError("每日目标必须是 1–500 之间的整数。")
        data = self.load()
        data["daily_goal"] = goal
        self.store.write(data)

    def set_settings(self, bank_kind, subject, difficulty, goal):
        if bank_kind not in {"public", "personal"}:
            raise ValueError("题库设置无效。")
        if type(goal) is not int or not 1 <= goal <= 500:
            raise ValueError("每日目标必须是 1–500 之间的整数。")
        for value in (subject, difficulty):
            if value is not None and (not isinstance(value, str) or not value.strip()):
                raise ValueError("科目和难度必须是有效文本。")
        data = self.load()
        data.update(
            {
                "bank_kind": bank_kind,
                "subject": subject,
                "difficulty": difficulty,
                "daily_goal": goal,
            }
        )
        self.store.write(data)

    def record_answer(self, event_id, answered_at=None):
        data = self.load()
        if any(event["id"] == event_id for event in data["answers"]):
            return False
        timestamp = answered_at or datetime.now().astimezone()
        if timestamp.tzinfo is None:
            raise ValueError("答题时间必须包含时区")
        data["answers"].append(
            {"id": event_id, "answered_at": timestamp.isoformat(timespec="seconds")}
        )
        self.store.write(data)
        return True

    def summary(self, now=None):
        now = now or datetime.now().astimezone()
        data = self.load()
        counts = {}
        for event in data["answers"]:
            day = datetime.fromisoformat(event["answered_at"]).astimezone(now.tzinfo).date()
            counts[day] = counts.get(day, 0) + 1
        today = now.date()
        weekly = []
        for offset in range(6, -1, -1):
            day = today - timedelta(days=offset)
            weekly.append({"date": day.isoformat(), "count": counts.get(day, 0)})
        streak = 0
        cursor = today if counts.get(today, 0) else today - timedelta(days=1)
        while counts.get(cursor, 0):
            streak += 1
            cursor -= timedelta(days=1)
        answered = counts.get(today, 0)
        return {
            "daily_goal": data["daily_goal"],
            "bank_kind": data["bank_kind"],
            "subject": data["subject"],
            "difficulty": data["difficulty"],
            "today": answered,
            "remaining": max(data["daily_goal"] - answered, 0),
            "percent": min(answered / data["daily_goal"] * 100, 100),
            "streak": streak,
            "weekly": weekly,
        }
