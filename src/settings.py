from __future__ import annotations

import os
import secrets
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from src.domain.validation import validate_email, validate_login, validate_password

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_ENV_FILE = _PROJECT_ROOT / ".env"

_DEFAULT_ADMIN_LOGIN = "admin"
_DEFAULT_ADMIN_EMAIL = "admin@example.org"
_GENERATED_PASSWORD_BYTES = 12


@dataclass(frozen=True)
class AdminSettings:
    """Учётные данные администратора, который создаётся при запуске."""

    login: str
    email: str
    password: str
    password_generated: bool


def parse_env_file(path: Path) -> dict[str, str]:
    """Прочитать пары КЛЮЧ=ЗНАЧЕНИЕ из .env; пустые строки и строки с «#» пропускаются."""
    if not path.is_file():
        return {}
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        entry = line.strip()
        if not entry or entry.startswith("#") or "=" not in entry:
            continue
        key, _, value = entry.partition("=")
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def load_admin_settings(
    env_file: Path | None = None, environ: Mapping[str, str] | None = None
) -> AdminSettings:
    """Собрать настройки администратора из ADMIN_LOGIN, ADMIN_EMAIL и ADMIN_PASSWORD.

    Переменные окружения важнее файла `.env`. Если пароль не задан, он генерируется
    заново при каждом запуске (`password_generated=True`) и пароля по умолчанию в коде нет.
    Заданные значения проверяются теми же правилами, что и данные обычных пользователей.
    """
    file_values = parse_env_file(env_file or _ENV_FILE)
    source = {**file_values, **(os.environ if environ is None else environ)}
    login = source.get("ADMIN_LOGIN", "").strip() or _DEFAULT_ADMIN_LOGIN
    email = source.get("ADMIN_EMAIL", "").strip() or _DEFAULT_ADMIN_EMAIL
    password = source.get("ADMIN_PASSWORD", "")
    generated = not password
    if generated:
        password = secrets.token_urlsafe(_GENERATED_PASSWORD_BYTES)
    validate_login(login)
    validate_email(email)
    validate_password(password)
    return AdminSettings(login, email, password, generated)
