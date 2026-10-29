"""Local login convenience settings with Windows user-bound password protection."""

import base64
import ctypes
import os
import subprocess
import sys
from ctypes import wintypes

from .storage import DataError, JsonStore


class _Blob(ctypes.Structure):
    _fields_ = [("size", wintypes.DWORD), ("data", ctypes.POINTER(ctypes.c_byte))]


def _blob(value: bytes):
    buffer = ctypes.create_string_buffer(value)
    return _Blob(len(value), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_byte))), buffer


SERVICE = "QuizStudio.INT6181"


def _protect(value: str, username: str) -> str:
    if sys.platform == "darwin":
        subprocess.run(
            [
                "security",
                "add-generic-password",
                "-U",
                "-a",
                username,
                "-s",
                SERVICE,
                "-w",
                value,
            ],
            check=True,
            capture_output=True,
        )
        return "keychain"
    if os.name != "nt":
        raise ValueError("当前系统没有可用的安全密码存储。")
    source, source_buffer = _blob(value.encode("utf-8"))
    target = _Blob()
    if not ctypes.windll.crypt32.CryptProtectData(
        ctypes.byref(source), None, None, None, None, 0, ctypes.byref(target)
    ):
        raise OSError("Windows 无法加密登录密码。")
    try:
        return base64.b64encode(ctypes.string_at(target.data, target.size)).decode("ascii")
    finally:
        ctypes.windll.kernel32.LocalFree(target.data)
        del source_buffer


def _unprotect(value: str, username: str) -> str:
    if sys.platform == "darwin" and value == "keychain":
        result = subprocess.run(
            ["security", "find-generic-password", "-a", username, "-s", SERVICE, "-w"],
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout.rstrip("\n")
    if os.name != "nt":
        return ""
    source, source_buffer = _blob(base64.b64decode(value, validate=True))
    target = _Blob()
    if not ctypes.windll.crypt32.CryptUnprotectData(
        ctypes.byref(source), None, None, None, None, 0, ctypes.byref(target)
    ):
        return ""
    try:
        return ctypes.string_at(target.data, target.size).decode("utf-8")
    finally:
        ctypes.windll.kernel32.LocalFree(target.data)
        del source_buffer


class LoginPreferences:
    def __init__(self, data_dir):
        self.store = JsonStore(data_dir / "login_state.json", {"username": "", "password": ""})

    def load(self):
        try:
            data = self.store.read()
            if not isinstance(data, dict) or set(data) != {"username", "password"}:
                raise ValueError("Invalid login state")
            username = data["username"] if isinstance(data["username"], str) else ""
            encrypted = data["password"] if isinstance(data["password"], str) else ""
            password = _unprotect(encrypted, username) if encrypted else ""
            return {"username": username, "password": password, "remember": bool(password)}
        except (DataError, ValueError, OSError, UnicodeError, subprocess.SubprocessError):
            return {"username": "", "password": "", "remember": False}

    def save(self, username, password="", remember=False):
        username = username.strip()
        try:
            encrypted = _protect(password, username) if remember and password else ""
        except subprocess.SubprocessError as exc:
            raise OSError("系统无法保存登录密码。") from exc
        self.store.write({"username": username.strip(), "password": encrypted})
