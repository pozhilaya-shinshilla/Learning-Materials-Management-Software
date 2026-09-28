from __future__ import annotations

import re

from src.domain.exceptions import ValidationError

_LOGIN_PATTERN = re.compile(r"^[A-Za-z0-9_-]{3,32}$")
_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MIN_PASSWORD_LENGTH = 8


def validate_login(login: str) -> None:
    """Raise ValidationError unless login is 3-32 chars of letters/digits/_/-."""
    if not _LOGIN_PATTERN.match(login):
        raise ValidationError(
            "Логин должен быть 3-32 символа: латинские буквы, цифры, '_' или '-'."
        )


def validate_email(email: str) -> None:
    """Raise ValidationError unless email looks like local@domain.tld."""
    if not _EMAIL_PATTERN.match(email):
        raise ValidationError("Некорректный формат email.")


def validate_password(plain_password: str) -> None:
    """Raise ValidationError unless the password meets the minimum length."""
    if len(plain_password) < MIN_PASSWORD_LENGTH:
        raise ValidationError(f"Пароль должен быть не короче {MIN_PASSWORD_LENGTH} символов.")
