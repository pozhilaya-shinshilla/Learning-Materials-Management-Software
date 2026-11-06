"""Связка приложения с Alembic: конфигурация и проверка, что схема БД актуальна.

Схему создаёт и меняет только Alembic (`alembic upgrade head`): метод `metadata` для
прямого создания таблиц в проекте не вызывается. Приложение при старте лишь проверяет,
что миграции применены.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import Engine, text
from sqlalchemy.exc import OperationalError

from src.domain.exceptions import DatabaseSchemaError, DatabaseUnavailableError

logger = logging.getLogger(__name__)

_ALEMBIC_INI = Path(__file__).resolve().parent.parent.parent / "alembic.ini"


def make_alembic_config(url: str | None = None) -> Config:
    """Конфигурация Alembic из `alembic.ini`; `url` (если задан) важнее DATABASE_URL."""
    config = Config(str(_ALEMBIC_INI))
    if url is not None:
        # Конфигурация читается через configparser: знак «%» в пароле нужно удвоить.
        config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    return config


# Индексы по выражениям, которые Alembic не умеет сравнивать: он счёл бы их «лишними» в БД и
# предлагал удалить. Они описаны в моделях и создаются вручную в миграции; что индекс на месте
# и что запрос им пользуется, проверяют тесты.
MANUALLY_MANAGED_INDEXES = frozenset({"ix_materials_search_vector"})


def include_in_autogenerate(object_, name, type_, reflected, compare_to) -> bool:
    """Решить, сравнивает ли Alembic объект (`include_object`): ручные индексы пропускаются."""
    return not (type_ == "index" and name in MANUALLY_MANAGED_INDEXES)


def ensure_schema_is_current(engine: Engine) -> None:
    """Выбросить `DatabaseSchemaError`, если применены не все миграции Alembic."""
    head = ScriptDirectory.from_config(make_alembic_config()).get_current_head()
    with engine.connect() as connection:
        current = MigrationContext.configure(connection).get_current_revision()
    if current != head:
        state = current or "миграции не применялись"
        raise DatabaseSchemaError(
            reason=f"текущая ревизия: {state}, нужна: {head}. Выполните `alembic upgrade head`."
        )


# Ключ консультативной блокировки на время миграций: блокировки PostgreSQL общие на всю базу.
MIGRATION_LOCK_KEY = 7002


def wait_for_database(
    engine: Engine,
    timeout_seconds: float,
    *,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
    interval_seconds: float = 1.0,
) -> None:
    """Дождаться, пока база начнёт принимать подключения (при запуске рядом с контейнером БД).

    Подключение проверяется раз в `interval_seconds`. Если за `timeout_seconds` база так и не
    ответила, выбрасывает `DatabaseUnavailableError` с последней ошибкой подключения.
    """
    deadline = clock() + timeout_seconds
    waiting_logged = False
    while True:
        try:
            engine.connect().close()
            return
        except OperationalError as error:
            if clock() >= deadline:
                reason = str(error.orig or error).strip().splitlines()[0]
                raise DatabaseUnavailableError(
                    seconds=int(timeout_seconds), reason=reason
                ) from error
            if not waiting_logged:
                logger.info("Жду запуска базы данных (до %s с)...", int(timeout_seconds))
                waiting_logged = True
            sleep(interval_seconds)


def upgrade_to_head(engine: Engine) -> None:
    """Применить все миграции (`alembic upgrade head`); безопасно запускать повторно.

    На время миграций берётся консультативная блокировка: если несколько копий приложения
    стартуют одновременно, схему обновляет одна, остальные ждут и затем видят, что всё уже
    применено. Блокировку держит отдельное соединение, а сами миграции идут через Alembic.
    """
    config = make_alembic_config(engine.url.render_as_string(hide_password=False))
    config.attributes["configure_logging"] = False  # логирование уже настроено приложением
    with engine.connect() as lock_connection:
        lock_connection.execute(text("SELECT pg_advisory_lock(:key)"), {"key": MIGRATION_LOCK_KEY})
        try:
            command.upgrade(config, "head")
        finally:
            lock_connection.rollback()
            lock_connection.execute(
                text("SELECT pg_advisory_unlock(:key)"), {"key": MIGRATION_LOCK_KEY}
            )
            lock_connection.commit()
