"""Заглушки и подставные объекты для юнит-тестов: никаких диска, почты и консоли."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path

from src.cli.console_io import ConsoleIO
from src.domain.enums import AccountStatus, EventType, FileType, Role
from src.domain.models import Event, Material, User
from src.notifications.email_sender import EmailSender
from src.security.password_hasher import PasswordHasher
from src.services.transaction_hooks import Action, TransactionHooks
from src.storage.file_storage import FileStorage, StoredFile


class RecordingEmailSender(EmailSender):
    """Запоминает письма вместо отправки."""

    def __init__(self) -> None:
        self.sent: list[tuple[str, str, str]] = []

    def send(self, to_address: str, subject: str, body: str) -> None:
        self.sent.append((to_address, subject, body))


class RecordingHooks(TransactionHooks):
    """Копит действия, пока тест не решит, чем закончилась «транзакция»."""

    def __init__(self) -> None:
        self.commit_actions: list[Action] = []
        self.rollback_actions: list[Action] = []

    def on_commit(self, action: Action) -> None:
        self.commit_actions.append(action)

    def on_rollback(self, action: Action) -> None:
        self.rollback_actions.append(action)

    def commit(self) -> None:
        """Фиксация: действия «после» выполняются, действия отката отбрасываются."""
        for action in self.commit_actions:
            action()
        self.commit_actions, self.rollback_actions = [], []

    def rollback(self) -> None:
        """Откат: выполняются действия отката, действия «после» отбрасываются."""
        for action in self.rollback_actions:
            action()
        self.commit_actions, self.rollback_actions = [], []


class PlainPasswordHasher(PasswordHasher):
    """Быстрый обратимый «хешер» для тестов сервисов (настоящий проверяется отдельно)."""

    def hash(self, plain_password: str) -> str:
        return f"hashed:{plain_password}"

    def verify(self, plain_password: str, password_hash: str) -> bool:
        return password_hash == f"hashed:{plain_password}"


class FakeFileStorage(FileStorage):
    """Файловое хранилище в словаре: ничего не пишет на диск."""

    def __init__(self) -> None:
        self.files: dict[str, StoredFile] = {}
        self.deleted: list[str] = []

    def store(self, source_path: Path) -> StoredFile:
        stored = StoredFile(
            storage_path=f"mem://{len(self.files) + 1}/{source_path.name}",
            file_name=source_path.name,
            size_bytes=source_path.stat().st_size,
        )
        self.files[stored.storage_path] = stored
        return stored

    def resolve(self, storage_path: str) -> Path:
        return Path(storage_path)

    def delete(self, storage_path: str) -> None:
        self.files.pop(storage_path, None)
        self.deleted.append(storage_path)


class ScriptedIO(ConsoleIO):
    """Консоль, которая отвечает заранее заданными строками и запоминает вопросы."""

    def __init__(self, answers: Iterable[str] = ()) -> None:
        self._answers = iter(answers)
        self.prompts: list[str] = []
        self.pauses = 0

    def read_line(self, prompt: str) -> str:
        self.prompts.append(prompt)
        try:
            return next(self._answers)
        except StopIteration:
            raise EOFError from None

    def read_secret(self, prompt: str) -> str:
        return self.read_line(prompt)

    def clear_screen(self) -> None:
        return None

    def pause(self) -> None:
        self.pauses += 1


def make_user(
    user_id: int = 1,
    login: str = "user1",
    role: Role = Role.STUDENT,
    status: AccountStatus = AccountStatus.ACTIVE,
    email: str | None = None,
) -> User:
    """Создать пользователя без обращения к хранилищу."""
    return User(
        id=user_id,
        login=login,
        email=email or f"{login}@example.org",
        password_hash="hashed:Password1!",
        role=role,
        status=status,
    )


def make_material(
    material_id: int = 1,
    title: str = "Лекция",
    description: str = "",
    discipline_id: int = 1,
    topic_id: int = 1,
    file_type: FileType = FileType.PDF,
    author_id: int = 1,
    uploaded_at: datetime | None = None,
) -> Material:
    """Создать материал без обращения к хранилищу."""
    return Material(
        id=material_id,
        title=title,
        description=description,
        discipline_id=discipline_id,
        topic_id=topic_id,
        file_name=f"{title}.{file_type.value}",
        file_type=file_type,
        file_size_bytes=10,
        author_id=author_id,
        storage_path=f"mem://{material_id}",
        uploaded_at=uploaded_at or datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
    )


def make_event(
    event_type: EventType = EventType.USER_LOGGED_IN, target: str = "x", user_id: int | None = 1
) -> Event:
    """Создать событие журнала."""
    return Event(id=1, user_id=user_id, event_type=event_type, target=target)
