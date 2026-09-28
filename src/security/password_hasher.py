from __future__ import annotations

import hashlib
import hmac
import os
from abc import ABC, abstractmethod

_ALGORITHM = "sha256"
_ITERATIONS = 200_000
_SALT_BYTES = 16


class PasswordHasher(ABC):
    """Contract for hashing and verifying user passwords."""

    @abstractmethod
    def hash(self, plain_password: str) -> str:
        """Return a salted hash of the given plaintext password."""

    @abstractmethod
    def verify(self, plain_password: str, password_hash: str) -> bool:
        """Return whether the plaintext password matches the given hash."""


class Pbkdf2PasswordHasher(PasswordHasher):
    """Hashes passwords with PBKDF2-HMAC-SHA256, as required by the spec."""

    def hash(self, plain_password: str) -> str:
        """Return a salted hash of the given plaintext password."""
        salt = os.urandom(_SALT_BYTES)
        digest = hashlib.pbkdf2_hmac(_ALGORITHM, plain_password.encode("utf-8"), salt, _ITERATIONS)
        return f"{_ALGORITHM}${_ITERATIONS}${salt.hex()}${digest.hex()}"

    def verify(self, plain_password: str, password_hash: str) -> bool:
        """Return whether the plaintext password matches the given hash."""
        try:
            algorithm, iterations_text, salt_hex, digest_hex = password_hash.split("$")
            iterations = int(iterations_text)
            salt = bytes.fromhex(salt_hex)
        except (ValueError, AttributeError):
            return False
        candidate = hashlib.pbkdf2_hmac(algorithm, plain_password.encode("utf-8"), salt, iterations)
        return hmac.compare_digest(candidate.hex(), digest_hex)
