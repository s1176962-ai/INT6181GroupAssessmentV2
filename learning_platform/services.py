"""Filtering, quiz state, answer checking and transactional progress updates."""

import random
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from .models import score


def select_questions(questions, subject=None, topic=None, difficulty=None, count=5, rng=None):
    if type(count) is not int or count < 1:
        raise ValueError("Question count must be a positive integer")
    matches = [
        q
        for q in questions
        if (subject is None or q.subject == subject)
        and (topic is None or q.topic == topic)
        and (difficulty is None or q.difficulty == difficulty)
    ]
    if not matches:
        raise ValueError("No questions match these settings")
    return (rng or random).sample(matches, min(count, len(matches)))


def image_path(root, value):
    """Only local assets under the project root are supported."""
    root = Path(root).resolve()
    path = (root / value).resolve()
    if not path.is_relative_to(root):
        raise ValueError("Image must be inside the project folder")
    return path


def subject_image(root, subject):
    """Soft colour-block art for a subject when a question has no image."""
    key = (subject or "").strip().lower()
    name = "english"
    if "math" in key:
        name = "mathematics"
    elif "sci" in key:
        name = "science"
    path = image_path(root, f"assets/images/subjects/{name}.png")
    if path.is_file():
        return path
    return image_path(root, "assets/images/placeholder.png")


class QuizEngine:
    def __init__(self, questions, repository, review=False, learning_plan=None, now=None):
        if not questions:
            raise ValueError("Cannot start an empty quiz")
        if len({q.id for q in questions}) != len(questions):
            raise ValueError("Duplicate question IDs in quiz")
        self.questions = list(questions)
        self.repository = repository
        self.review = review
        self.index = 0
        self.answers = []
        self.id = str(uuid4())
        self.learning_plan = learning_plan
        self.now = now or (lambda: datetime.now().astimezone())
        self.activity_warning = None

    @property
    def current(self):
        return self.questions[self.index]

    @property
    def submitted(self):
        return len(self.answers) > self.index

    @property
    def complete(self):
        return len(self.answers) == len(self.questions)

    def submit(self, answer):
        if self.submitted:
            raise ValueError("This question has already been submitted")
        q = self.current
        if answer not in q.options:
            raise ValueError("Select an answer before submitting")
        correct = answer == q.answer
        data = self.repository.load()
        submitted_at = self.now()
        now = submitted_at.isoformat(timespec="seconds")
        if not correct:
            previous = data["wrong"].get(q.id, {}).get("count", 0)
            data["wrong"][q.id] = {"count": previous + 1, "last_answer": answer, "last_seen": now}
        elif self.review:
            data["wrong"].pop(q.id, None)
        answers = self.answers + [correct]
        if len(answers) == len(self.questions):
            data["history"].append(
                {
                    "id": self.id,
                    "date": now,
                    "subject": ", ".join(sorted({q.subject for q in self.questions})),
                    "mode": "review" if self.review else "quiz",
                    **score(len(answers), sum(answers)),
                }
            )
        # Commit first: on a write error the same answer can safely be retried.
        self.repository.save(data)
        self.answers = answers
        if self.learning_plan is not None:
            try:
                self.learning_plan.record_answer(f"{self.id}:{self.index}", submitted_at)
            except ValueError as exc:
                self.activity_warning = str(exc)
        return correct

    def finish_timeout(self):
        """Persist one complete timed result; unanswered items do not create wrong entries."""
        if self.complete:
            return
        total = len(self.questions)
        unanswered = total - len(self.answers)
        data = self.repository.load()
        data["history"].append(
            {
                "id": self.id,
                "date": datetime.now().astimezone().isoformat(timespec="seconds"),
                "subject": ", ".join(sorted({q.subject for q in self.questions})),
                "mode": "review" if self.review else "quiz",
                **score(total, sum(self.answers)),
                "timed_out": True,
                "unanswered": unanswered,
            }
        )
        self.repository.save(data)
        self.answers += [False] * unanswered
        self.timed_out = True
        self.unanswered = unanswered

    def next_question(self):
        if not self.submitted or self.complete:
            raise ValueError("Submit this question first, or view the final result")
        self.index += 1

    def result(self):
        return score(len(self.answers), sum(self.answers))
