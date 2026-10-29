"""Question schema and score calculations, independent of the GUI."""

from dataclasses import dataclass


def option_label(index: int) -> str:
    """Use A..Z, AA..AZ for display without changing persisted answer values."""
    if type(index) is not int or index < 0:
        raise ValueError("Invalid option index")
    label = ""
    index += 1
    while index:
        index, digit = divmod(index - 1, 26)
        label = chr(65 + digit) + label
    return label


@dataclass
class Question:
    id: str
    subject: str
    topic: str
    difficulty: str
    type: str
    question: str
    options: list[str]
    answer: str
    explanation: str
    question_image: str | None = None
    option_images: list[str | None] | None = None

    @classmethod
    def from_dict(cls, data):
        if not isinstance(data, dict):
            raise ValueError("Question must be an object")
        fields = (
            "id",
            "subject",
            "topic",
            "difficulty",
            "type",
            "question",
            "answer",
            "explanation",
        )
        for key in fields:
            if not isinstance(data.get(key), str) or not data[key].strip():
                raise ValueError(f"{key} must be a non-empty string")
        if data["type"] != "single_choice":
            raise ValueError("Only single_choice is supported")
        options = data.get("options")
        if (
            not isinstance(options, list)
            or len(options) < 2
            or any(not isinstance(x, str) or not x.strip() for x in options)
        ):
            raise ValueError("options must contain at least two non-empty strings")
        if len(set(options)) != len(options) or data["answer"] not in options:
            raise ValueError("Options must be unique and answer must exactly match an option")
        images = data.get("option_images")
        if images is not None and (not isinstance(images, list) or len(images) != len(options)):
            raise ValueError("option_images must be null or match the options length")
        for path in [data.get("question_image"), *(images or [])]:
            if path is not None and (not isinstance(path, str) or not path.strip()):
                raise ValueError("Image paths must be non-empty strings or null")
        return cls(
            **{key: data[key] for key in fields},
            options=options,
            question_image=data.get("question_image"),
            option_images=images,
        )


def score(total, correct):
    if type(total) is not int or type(correct) is not int or not 0 <= correct <= total:
        raise ValueError("Invalid score counts")
    return {
        "total": total,
        "correct": correct,
        "incorrect": total - correct,
        "accuracy": round(correct / total * 100, 2) if total else 0.0,
        "score": correct,
        "max_score": total,
    }
