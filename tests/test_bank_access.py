"""Personal bank moderation permissions and account isolation."""

import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from learning_platform.auth import AuthService
from learning_platform.bank_access import ManagedPersonalBank
from learning_platform.repositories import PersonalQuestionRepository, QuestionRepository


class BankAccessTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.auth = AuthService(Path(temp.name))
        self.admin = self.auth.register("wutaicheng", "secret123", "secret123")
        records = self.auth.store.read()
        records["wutaicheng"]["role"] = "admin"
        self.auth.store.write(records)
        self.admin = self.auth.login("wutaicheng", "secret123")
        self.student = self.auth.register("student", "secret123", "secret123")
        self.other = self.auth.register("other", "secret123", "secret123")
        root = Path(__file__).resolve().parents[1]
        self.question = QuestionRepository(root / "data/questions").all()[0]
        for user in (self.student, self.other):
            PersonalQuestionRepository(self.auth.personal_questions_path(user)).save(self.question)

    def test_admin_edits_and_deletes_target_without_changing_other_bank(self):
        bank = ManagedPersonalBank(self.auth, lambda: self.admin, self.student["id"])
        changed = replace(self.question, explanation="Updated explanation")
        bank.save(changed, self.question)
        self.assertEqual(bank.all(), [changed])
        bank.delete(changed)
        self.assertEqual(bank.all(), [])
        other = PersonalQuestionRepository(self.auth.personal_questions_path(self.other))
        self.assertEqual(other.all(), [self.question])
        self.assertEqual(
            len(
                list(
                    self.auth.personal_questions_path(self.student).parent.glob(
                        "questions.*.bak.json"
                    )
                )
            ),
            2,
        )

    def test_student_and_guest_cannot_access_another_owner(self):
        for actor in (self.student, None):
            bank = ManagedPersonalBank(self.auth, lambda: actor, self.other["id"])
            with self.assertRaises(ValueError):
                bank.all()
            with self.assertRaises(ValueError):
                bank.delete(self.question)

    def test_disabled_owner_cannot_save_or_delete_from_existing_service(self):
        bank = ManagedPersonalBank(self.auth, lambda: self.student, self.student["id"])
        self.assertEqual(bank.all(), [self.question])
        self.auth.update_user(self.admin, self.student["id"], "student", "student", False)
        with self.assertRaises(ValueError):
            bank.save(replace(self.question, explanation="Denied"), self.question)
        with self.assertRaises(ValueError):
            bank.delete(self.question)
        self.assertEqual(
            PersonalQuestionRepository(self.auth.personal_questions_path(self.student)).all(),
            [self.question],
        )

    def test_cached_admin_role_does_not_survive_demotion(self):
        bank = ManagedPersonalBank(self.auth, lambda: self.admin, self.student["id"])
        admin2 = self.auth.create_user(self.admin, "admin2", "secret123", role="admin")
        self.auth.update_user(admin2, self.admin["id"], "wutaicheng", "student", True)
        with self.assertRaises(ValueError):
            bank.save(replace(self.question, explanation="Denied"), self.question)
        self.assertEqual(
            PersonalQuestionRepository(self.auth.personal_questions_path(self.student)).all(),
            [self.question],
        )
