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


@dataclass(frozen=True)
class MaterialMemento:
    """Снимок редактируемых полей материала (паттерн «Хранитель»).

    Неизменяем и ничего не умеет, кроме хранения: читает его только сам `Material`.
    Файл, автор и дата загрузки при редактировании не меняются, поэтому в снимок не входят.
    """

    title: str
    description: str
    discipline_id: int
    topic_id: int


@dataclass
class Material:
    """Учебный материал: описание и ссылка на сохранённый файл.

    `author_id` равен None, если автора удалили: материал остаётся в каталоге,
    а менять и удалять его может только администратор.
    """

    id: int
    title: str
    description: str
    discipline_id: int
    topic_id: int
    file_name: str
    file_type: FileType
    file_size_bytes: int
    author_id: int | None
    storage_path: str = ""
    uploaded_at: datetime = field(default_factory=_now)

    def create_memento(self) -> MaterialMemento:
        """Сохранить текущие редактируемые поля в снимок."""
        return MaterialMemento(self.title, self.description, self.discipline_id, self.topic_id)

    def restore(self, memento: MaterialMemento) -> None:
        """Вернуть редактируемые поля к значениям из снимка."""
        self.title = memento.title
        self.description = memento.description
        self.discipline_id = memento.discipline_id
        self.topic_id = memento.topic_id


@dataclass
class Favorite:
    """Закладка студента на материал (избранное)."""

    user_id: int
    material_id: int
    added_at: datetime = field(default_factory=_now)


@dataclass
class Event:
    """Запись в журнале событий системы.

    `user_id` равен None, если действие совершил гость (например, неудачный вход
    под несуществующим логином) или пользователя позже удалили.
    """

    id: int
    user_id: int | None
    event_type: EventType
    target: str
    occurred_at: datetime = field(default_factory=_now)


@dataclass
class PasswordResetToken:
    """Выданный код восстановления пароля. Сам код не хранится, только его SHA-256."""

    id: int
    user_id: int
    token_hash: str
    expires_at: datetime


@dataclass
class AuthToken:
    """Токен доступа к API, выданный при входе. Сам токен не хранится, только его SHA-256."""

    id: int
    user_id: int
    token_hash: str
    expires_at: datetime
