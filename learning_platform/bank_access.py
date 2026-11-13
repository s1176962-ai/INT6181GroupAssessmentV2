"""Account-scoped personal bank access with fresh permission checks."""

import shutil
from datetime import datetime

from .repositories import PersonalQuestionRepository


class ManagedPersonalBank:
    def __init__(self, auth, actor, owner_id):
        self.auth = auth
        self.actor = actor
        self.owner_id = owner_id

    def _repository(self):
        actor = self.auth.require_session(self.actor())
        if actor["id"] == self.owner_id:
            owner = actor
        else:
            users = self.auth.list_users(actor)
            owner = next((u for u in users if u["id"] == self.owner_id), None)
            if owner is None:
                raise ValueError("账户不存在，请刷新列表。")
        return PersonalQuestionRepository(self.auth.personal_questions_path(owner))

    def all(self):
        return self._repository().all()

    def _write(self, operation, *args, **kwargs):
        repository = self._repository()
        repository.all()
        path = repository.store.path
        if path.exists():
            stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
            shutil.copy2(path, path.with_name(f"questions.{stamp}.bak.json"))
        return getattr(repository, operation)(*args, **kwargs)

    def save(self, question, original=None, reserved_ids=()):
        return self._write("save", question, original, reserved_ids=reserved_ids)

    def delete(self, original):
        return self._write("delete", original)
