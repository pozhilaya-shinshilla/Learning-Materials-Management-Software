"""Базовый класс ORM-моделей и соглашение об именах ограничений.

`Base` один на весь проект: все модели наследуются от него, иначе у них была бы
разная `metadata`, и Alembic увидел бы только часть таблиц.

Соглашение нужно Alembic: он удаляет ограничения в `downgrade` по имени, поэтому имена
должны быть предсказуемыми. CHECK-ограничения в моделях называются коротко
(`name="file_size_non_negative"`), полное имя `ck_materials_file_size_non_negative`
собирает соглашение; в миграции его оборачивают в `op.f(...)`.
"""

from __future__ import annotations

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Базовый класс для всех моделей проекта."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)
