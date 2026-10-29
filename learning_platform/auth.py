"""Local accounts with salted password hashes and separate progress paths."""

import hashlib
import hmac
import re
import secrets
from pathlib import Path
from uuid import UUID, uuid4

from .repositories import ProgressRepository
from .storage import DataError, JsonStore

ITERATIONS = 600_000


class AuthService:
    """Account names are case-insensitive; passwords are never stored as text."""

    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self.store = JsonStore(self.data_dir / "users.json", {})

    def _load(self) -> dict:
        users = self.store.read()
        try:
            if not isinstance(users, dict):
                raise ValueError("Expected an account object")
            ids = set()
            for key, user in users.items():
                if not isinstance(user, dict) or key != user["name"].casefold():
                    raise ValueError("Invalid account name")
                if str(UUID(user["id"])) != user["id"] or user["id"] in ids:
                    raise ValueError("Invalid or duplicate account ID")
                ids.add(user["id"])
                if len(bytes.fromhex(user["salt"])) != 16:
                    raise ValueError("Invalid salt")
                if len(bytes.fromhex(user["password_hash"])) != 32:
                    raise ValueError("Invalid password hash")
                if user["iterations"] != ITERATIONS:
                    raise ValueError("Unsupported password format")
                # Older records retain their UUID and hash; missing roles are students.
                user.setdefault("role", "student")
                user.setdefault("enabled", True)
                if user["role"] not in {"admin", "student"} or type(user["enabled"]) is not bool:
                    raise ValueError("Invalid account role or status")
        except (KeyError, TypeError, ValueError, AttributeError) as exc:
            raise DataError(f"账户文件损坏，原文件已保留：{self.store.path}") from exc
        return users

    @staticmethod
    def _hash(password: str, salt: str) -> str:
        return hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), bytes.fromhex(salt), ITERATIONS
        ).hex()

    @staticmethod
    def _validate_name(name: str) -> str:
        name = name.strip()
        if not re.fullmatch(r"[\w-]{3,32}", name):
            raise ValueError("用户名需为 3–32 位文字、数字、下划线或短横线。")
        return name

    @staticmethod
    def _validate_password(password: str) -> None:
        if not 6 <= len(password) <= 16 or not password.strip():
            raise ValueError("密码需为 6–16 位，不能全部为空格。")

    @staticmethod
    def _public(user: dict) -> dict:
        return {key: user[key] for key in ("id", "name", "role", "enabled")}

    def _new_user(self, name: str, password: str, role="student", enabled=True) -> dict:
        name = self._validate_name(name)
        self._validate_password(password)
        if role not in {"admin", "student"} or type(enabled) is not bool:
            raise ValueError("无效的角色或账户状态。")
        salt = secrets.token_hex(16)
        return {
            "id": str(uuid4()),
            "name": name,
            "salt": salt,
            "password_hash": self._hash(password, salt),
            "iterations": ITERATIONS,
            "role": role,
            "enabled": enabled,
        }

    def register(self, name: str, password: str, confirmation: str) -> dict:
        name = self._validate_name(name)
        self._validate_password(password)
        if password != confirmation:
            raise ValueError("两次密码不一致。")
        users = self._load()
        if name.casefold() in users:
            raise ValueError("此用户名已注册。")
        user = self._new_user(name, password)
        users[name.casefold()] = user
        self.store.write(users)
        return self._public(user)

    def login(self, name: str, password: str) -> dict:
        user = self._load().get(name.strip().casefold())
        if (
            # Accept legacy passwords at login; the new limit applies to new/reset passwords.
            len(password) > 128
            or not user
            or not hmac.compare_digest(self._hash(password, user["salt"]), user["password_hash"])
        ):
            raise ValueError("用户名或密码错误。")
        if not user["enabled"]:
            raise ValueError("此账户已停用，请联系管理员。")
        return self._public(user)

    def require_session(self, actor: dict | None) -> dict:
        user = next(
            (u for u in self._load().values() if actor and u["id"] == actor.get("id")), None
        )
        if user is None or not user["enabled"]:
            raise ValueError("账户已停用或不存在，请重新登录。")
        return self._public(user)

    def require_admin(self, actor: dict | None) -> dict:
        # Never trust a cached role from the UI; re-read before privileged operations.
        user = self.require_session(actor)
        if user["role"] != "admin":
            raise ValueError("此操作仅限管理员。")
        return user

    def list_users(self, actor: dict) -> list[dict]:
        self.require_admin(actor)
        return sorted(
            (self._public(u) for u in self._load().values()), key=lambda u: u["name"].casefold()
        )

    def create_user(
        self, actor: dict, name: str, password: str, role="student", enabled=True
    ) -> dict:
        self.require_admin(actor)
        user = self._new_user(name, password, role, enabled)
        users = self._load()
        if user["name"].casefold() in users:
            raise ValueError("此用户名已注册。")
        users[user["name"].casefold()] = user
        self.store.write(users)
        return self._public(user)

    def update_user(
        self, actor: dict, user_id: str, name: str, role: str, enabled: bool, password: str = ""
    ) -> dict:
        self.require_admin(actor)
        name = self._validate_name(name)
        if role not in {"admin", "student"} or type(enabled) is not bool:
            raise ValueError("无效的角色或账户状态。")
        if password:
            self._validate_password(password)
        users = self._load()
        old_key = next((key for key, u in users.items() if u["id"] == user_id), None)
        if old_key is None:
            raise ValueError("账户不存在，请刷新列表。")
        if name.casefold() in users and name.casefold() != old_key:
            raise ValueError("此用户名已注册。")
        user = users.pop(old_key)
        user.update(name=name, role=role, enabled=enabled)
        if password:
            user["salt"] = secrets.token_hex(16)
            user["password_hash"] = self._hash(password, user["salt"])
        users[name.casefold()] = user
        if not any(u["role"] == "admin" and u["enabled"] for u in users.values()):
            raise ValueError("必须保留至少一个启用的管理员账户。")
        # UUID remains unchanged so renaming never detaches learning records.
        self.store.write(users)
        return self._public(user)

    def user_progress(self, actor: dict, user_id: str) -> dict:
        users = self.list_users(actor)
        user = next((u for u in users if u["id"] == user_id), None)
        if user is None:
            raise ValueError("账户不存在，请刷新列表。")
        return ProgressRepository(self.progress_path(user)).load()

    def progress_path(self, user: dict) -> Path:
        # A generated UUID, never the username, is used as a directory name.
        account_id = str(UUID(user["id"]))
        return self.data_dir / "profiles" / account_id / "progress.json"
