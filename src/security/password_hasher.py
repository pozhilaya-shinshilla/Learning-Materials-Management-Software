from __future__ import annotations

import hashlib
import hmac
import os
from abc import ABC, abstractmethod

_ALGORITHM = "sha256"
_ITERATIONS = 200_000
_SALT_BYTES = 16


class PasswordHasher(ABC):
    """Контракт хеширования и проверки паролей пользователей."""

    @abstractmethod
    def hash(self, plain_password: str) -> str:
        """Вернуть хеш пароля, посоленный случайной солью."""

    @abstractmethod
    def verify(self, plain_password: str, password_hash: str) -> bool:
        """Вернуть, соответствует ли введённый пароль хешу."""


class Pbkdf2PasswordHasher(PasswordHasher):
    """Хеширует пароли алгоритмом PBKDF2-HMAC-SHA256, как требует задание."""

    def hash(self, plain_password: str) -> str:
        """Вернуть хеш пароля, посоленный случайной солью."""
        salt = os.urandom(_SALT_BYTES)
        digest = hashlib.pbkdf2_hmac(_ALGORITHM, plain_password.encode("utf-8"), salt, _ITERATIONS)
        return f"{_ALGORITHM}${_ITERATIONS}${salt.hex()}${digest.hex()}"

    def verify(self, plain_password: str, password_hash: str) -> bool:
        """Вернуть, соответствует ли введённый пароль хешу."""
        try:
            algorithm, iterations_text, salt_hex, digest_hex = password_hash.split("$")
            iterations = int(iterations_text)
            salt = bytes.fromhex(salt_hex)
        except (ValueError, AttributeError):
            return False
        candidate = hashlib.pbkdf2_hmac(algorithm, plain_password.encode("utf-8"), salt, iterations)
        return hmac.compare_digest(candidate.hex(), digest_hex)
