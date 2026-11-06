from __future__ import annotations

import pytest

from src.bootstrap import ApplicationContext, build_application_context
from src.configs.settings import AdminSettings
from src.domain.enums import Role
from src.domain.models import User
from src.notifications.email_sender import EmailSender


class RecordingEmailSender(EmailSender):
    """Запоминает отправленные письма вместо вывода в консоль."""

    def __init__(self) -> None:
        self.sent: list[tuple[str, str, str]] = []

    def send(self, to_address: str, subject: str, body: str) -> None:
        self.sent.append((to_address, subject, body))


@pytest.fixture
def email_sender() -> RecordingEmailSender:
    return RecordingEmailSender()


@pytest.fixture
def context(tmp_path, email_sender, repository_factory) -> ApplicationContext:
    admin = AdminSettings("admin", "admin@example.org", "Admin12345!")
    return build_application_context(
        repository_factory,
        email_sender=email_sender,
        upload_root=tmp_path / "uploads",
        admin=admin,
    )


@pytest.fixture
def admin(context) -> User:
    return context.auth_service.login("admin", "Admin12345!")


@pytest.fixture
def teacher(context, admin) -> User:
    return _register(context, admin, "teacher1", Role.TEACHER)


def _register(context, admin, login, role) -> User:
    service = context.user_management_service
    name = next(m for m in dir(service) if m.startswith(("create", "register", "add")))
    return getattr(service, name)(admin, login, f"{login}@example.org", "Password123!", role)
