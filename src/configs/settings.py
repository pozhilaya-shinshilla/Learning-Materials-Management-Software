from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from src.domain.exceptions import (
    AdminPasswordNotSetError,
    DatabaseSettingsError,
    ServerSettingsError,
    SmtpSettingsError,
    TimezoneSettingsError,
)
from src.domain.validation import validate_email, validate_login, validate_password

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_ENV_FILE = _PROJECT_ROOT / ".env"

_DEFAULT_ADMIN_LOGIN = "admin"
_DEFAULT_ADMIN_EMAIL = "admin@example.org"


@dataclass(frozen=True)
class AdminSettings:
    """Учётные данные администратора, который создаётся при запуске."""

    login: str
    email: str
    password: str


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

    Переменные окружения важнее файла `.env`. Пароль обязателен: пароля по умолчанию
    в коде нет, а при его отсутствии выбрасывается `AdminPasswordNotSetError`.
    Заданные значения проверяются теми же правилами, что и данные обычных пользователей.
    """
    file_values = parse_env_file(env_file or _ENV_FILE)
    source = {**file_values, **(os.environ if environ is None else environ)}
    login = source.get("ADMIN_LOGIN", "").strip() or _DEFAULT_ADMIN_LOGIN
    email = source.get("ADMIN_EMAIL", "").strip() or _DEFAULT_ADMIN_EMAIL
    password = source.get("ADMIN_PASSWORD", "")
    if not password:
        raise AdminPasswordNotSetError()
    validate_login(login)
    validate_email(email)
    validate_password(password)
    return AdminSettings(login, email, password)


@dataclass(frozen=True)
class SmtpSettings:
    """Параметры подключения к SMTP-серверу для отправки писем."""

    host: str
    port: int
    sender: str
    username: str = ""
    password: str = ""
    use_starttls: bool = True


def load_smtp_settings(
    env_file: Path | None = None, environ: Mapping[str, str] | None = None
) -> SmtpSettings | None:
    """Собрать настройки SMTP из SMTP_HOST, SMTP_PORT, SMTP_FROM, SMTP_USER, SMTP_PASSWORD.

    Если SMTP_HOST не задан, возвращает None: письма тогда имитируются выводом в консоль.
    SMTP_STARTTLS=0 отключает шифрование (по умолчанию включено).
    """
    file_values = parse_env_file(env_file or _ENV_FILE)
    source = {**file_values, **(os.environ if environ is None else environ)}
    host = source.get("SMTP_HOST", "").strip()
    if not host:
        return None
    raw_port = source.get("SMTP_PORT", "").strip() or "587"
    if not raw_port.isdecimal() or not 0 < int(raw_port) < 65536:
        raise SmtpSettingsError(reason=f"SMTP_PORT «{raw_port}» не является номером порта")
    username = source.get("SMTP_USER", "").strip()
    sender = source.get("SMTP_FROM", "").strip() or username
    if not sender:
        raise SmtpSettingsError(reason="задайте SMTP_FROM или SMTP_USER")
    validate_email(sender)
    starttls = source.get("SMTP_STARTTLS", "1").strip().lower() not in {"0", "false", "no", "нет"}
    return SmtpSettings(
        host=host,
        port=int(raw_port),
        sender=sender,
        username=username,
        password=source.get("SMTP_PASSWORD", ""),
        use_starttls=starttls,
    )


DEFAULT_TIMEZONE = "Europe/Volgograd"


def load_app_timezone(
    env_file: Path | None = None, environ: Mapping[str, str] | None = None
) -> ZoneInfo:
    """Прочитать часовой пояс приложения из `APP_TIMEZONE` (по умолчанию Europe/Volgograd).

    В нём понимаются даты фильтра «загружен с … по …»: «2 марта» — это сутки по местному времени
    вуза, а не по времени сервера, который может стоять в другом поясе или в UTC (Docker).
    """
    file_values = parse_env_file(env_file or _ENV_FILE)
    source = {**file_values, **(os.environ if environ is None else environ)}
    name = source.get("APP_TIMEZONE", "").strip() or DEFAULT_TIMEZONE
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError) as error:
        raise TimezoneSettingsError(name=name) from error


@dataclass(frozen=True)
class ServerSettings:
    """Как запускать сервер: адрес, порт, ожидание БД и автоматическое применение миграций."""

    host: str = "127.0.0.1"
    port: int = 8000
    db_wait_seconds: int = 30
    auto_migrate: bool = True


_FALSE_WORDS = {"0", "false", "no", "нет", "off"}


def load_server_settings(
    env_file: Path | None = None, environ: Mapping[str, str] | None = None
) -> ServerSettings:
    """Прочитать `APP_HOST`, `APP_PORT`, `DB_WAIT_SECONDS` и `AUTO_MIGRATE`.

    По умолчанию сервер слушает только `127.0.0.1` (доступен с этого компьютера); в контейнере
    `APP_HOST=0.0.0.0` задаёт `docker-compose.yaml`. `AUTO_MIGRATE=0` отключает применение
    миграций при старте (тогда схему обновляют вручную: `alembic upgrade head`).
    """
    file_values = parse_env_file(env_file or _ENV_FILE)
    source = {**file_values, **(os.environ if environ is None else environ)}
    defaults = ServerSettings()
    host = source.get("APP_HOST", "").strip() or defaults.host
    raw_port = source.get("APP_PORT", "").strip() or str(defaults.port)
    if not raw_port.isdecimal() or not 0 < int(raw_port) < 65536:
        raise ServerSettingsError(reason=f"APP_PORT «{raw_port}» не является номером порта")
    raw_wait = source.get("DB_WAIT_SECONDS", "").strip() or str(defaults.db_wait_seconds)
    if not raw_wait.isdecimal() or int(raw_wait) > 3600:
        raise ServerSettingsError(
            reason=f"DB_WAIT_SECONDS «{raw_wait}» должно быть целым числом секунд от 0 до 3600"
        )
    auto_migrate = source.get("AUTO_MIGRATE", "1").strip().lower() not in _FALSE_WORDS
    return ServerSettings(host, int(raw_port), int(raw_wait), auto_migrate)


DEFAULT_DATABASE_URL = "postgresql+psycopg://lms:lms@localhost:5432/lms"
DEFAULT_TEST_DATABASE_URL = "postgresql+psycopg://lms:lms@localhost:5432/lms_test"
_DATABASE_URL_PREFIXES = ("postgresql://", "postgresql+psycopg://")


def normalize_database_url(url: str) -> str:
    """Привести URL PostgreSQL к виду `postgresql+psycopg://...` (драйвер psycopg 3).

    Принимает и короткую форму `postgresql://`, которую выдают облачные сервисы
    (без `+psycopg` SQLAlchemy искал бы драйвер psycopg2, которого в проекте нет).
    Другие СУБД отклоняются: схема и миграции рассчитаны на PostgreSQL.
    """
    cleaned = url.strip()
    if not cleaned.startswith(_DATABASE_URL_PREFIXES):
        raise DatabaseSettingsError(
            reason="DATABASE_URL должен начинаться с postgresql:// или postgresql+psycopg://"
        )
    if cleaned.startswith("postgresql://"):
        cleaned = "postgresql+psycopg://" + cleaned.removeprefix("postgresql://")
    return cleaned


class Settings:
    """Настройки приложения: переменные окружения важнее файла `.env`, затем значения по умолчанию.

    Приложение и Alembic читают один и тот же `settings.database_url`.
    """

    def __init__(
        self, env_file: Path | None = None, environ: Mapping[str, str] | None = None
    ) -> None:
        """Прочитать настройки; `env_file` и `environ` можно подменить (в тестах)."""
        file_values = parse_env_file(env_file or _ENV_FILE)
        source = {**file_values, **(os.environ if environ is None else environ)}
        raw_url = source.get("DATABASE_URL", "").strip() or DEFAULT_DATABASE_URL
        self.database_url: str = normalize_database_url(raw_url)
        raw_test_url = source.get("TEST_DATABASE_URL", "").strip() or DEFAULT_TEST_DATABASE_URL
        self.test_database_url: str = normalize_database_url(raw_test_url)


settings = Settings()
