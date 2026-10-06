from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from src.domain.enums import AccountStatus, EventType, FileType, Role


def _now() -> datetime:
    """Текущий момент времени в UTC (с часовым поясом)."""
    return datetime.now(UTC)


@dataclass
class User:
    """A registered account: student, teacher, or administrator."""

    id: int
    login: str
    email: str
    password_hash: str
    role: Role
    status: AccountStatus = AccountStatus.ACTIVE

    def is_active(self) -> bool:
        """Return whether the account may currently authenticate."""
        return self.status is AccountStatus.ACTIVE


@dataclass
class Discipline:
    """An academic discipline used to classify materials."""

    id: int
    name: str


@dataclass
class Topic:
    """A topic within a discipline used to classify materials."""

    id: int
    name: str
    discipline_id: int


@dataclass
class Material:
    """A teaching material: metadata plus a reference to its stored file."""

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
    """A student's bookmark of a material."""

    user_id: int
    material_id: int
    added_at: datetime = field(default_factory=_now)


@dataclass
class Event:
    """An entry in the system event log."""

    id: int
    user_id: int
    event_type: EventType
    target: str
    occurred_at: datetime = field(default_factory=_now)
