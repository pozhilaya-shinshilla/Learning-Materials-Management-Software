"""Проверки готовности БД при запуске приложения."""

from __future__ import annotations

from sqlalchemy import Engine, text

from src.database.migrations import ensure_schema_is_current
from src.domain.exceptions import DatabaseSchemaError


def ensure_unicode_case_folding(engine: Engine) -> None:
    """Убедиться, что `lower()` в БД понижает регистр кириллицы.

    Уникальность email, названий дисциплин и тем держится на индексах по `lower(...)`.
    В базе с локалью `C` (`LC_CTYPE=C`) `lower('Д')` не меняет букву, и «Математика»
    с «математика» стали бы разными дисциплинами. Базу нужно создавать с UTF-8 локалью
    (например, `C.UTF-8`, `en_US.UTF-8` или `ru_RU.UTF-8`).
    """
    with engine.connect() as connection:
        lowered = connection.scalar(text("SELECT lower('Д')"))
    if lowered != "д":
        raise DatabaseSchemaError(
            reason=(
                "локаль базы данных не поддерживает регистр кириллицы (LC_CTYPE=C). "
                "Создайте базу с UTF-8 локалью, например "
                "`CREATE DATABASE lms LC_COLLATE 'C.UTF-8' LC_CTYPE 'C.UTF-8' TEMPLATE template0`."
            )
        )


def ensure_database_ready(engine: Engine) -> None:
    """Проверить локаль и применённые миграции; при проблеме выбросить `DatabaseSchemaError`."""
    ensure_unicode_case_folding(engine)
    ensure_schema_is_current(engine)
