from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from src.domain.enums import AccountStatus, EventType, FileType, Role


def _now() -> datetime:
    """Текущий момент времени в UTC (с часовым поясом)."""
    return datetime.now(UTC)


@dataclass
class User:
    """Зарегистрированная учётная запись: студент, преподаватель или администратор."""

    id: int
    login: str
    email: str
    password_hash: str
    role: Role
    status: AccountStatus = AccountStatus.ACTIVE

    def is_active(self) -> bool:
        """Вернуть, может ли учётная запись сейчас входить в систему."""
        return self.status is AccountStatus.ACTIVE


@dataclass
class Discipline:
    """Учебная дисциплина, по которой классифицируются материалы."""

    id: int
    name: str


@dataclass
class Topic:
    """Тема внутри дисциплины, по которой классифицируются материалы."""

    id: int
    name: str
    discipline_id: int


@dataclass
class Material:
    """Учебный материал: описание и ссылка на сохранённый файл."""

    id: int
    title: str
    description: str
    discipline_id: int
    topic_id: int
    file_name: str
    file_type: FileType
    file_size_bytes: int
    author_id: int
    storage_path: str = ""
    uploaded_at: datetime = field(default_factory=_now)


@dataclass
class Favorite:
    """Закладка студента на материал (избранное)."""

    user_id: int
    material_id: int
    added_at: datetime = field(default_factory=_now)


@dataclass
class Event:
    """Запись в журнале событий системы."""

    id: int
    user_id: int
    event_type: EventType
    target: str
    occurred_at: datetime = field(default_factory=_now)

