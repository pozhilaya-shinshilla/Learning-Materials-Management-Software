"""Фикстуры тестов БД. Общие (`db_engine`, `db_session`, ...) лежат в `tests/conftest.py`."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.domain.enums import Role


@pytest.fixture
def repository_factory(db_repository_factory):
    """В тестах каталога `db` репозитории настоящие: PostgreSQL."""
    return db_repository_factory


@pytest.fixture
def repos(repository_factory) -> SimpleNamespace:
    """Набор из шести репозиториев PostgreSQL на одной сессии теста."""
    return SimpleNamespace(
        users=repository_factory.create_user_repository(),
        disciplines=repository_factory.create_discipline_repository(),
        topics=repository_factory.create_topic_repository(),
        materials=repository_factory.create_material_repository(),
        favorites=repository_factory.create_favorite_repository(),
        events=repository_factory.create_event_repository(),
    )


@pytest.fixture
def build_app(session_factory, tmp_path):
    """Фабрика «процессов» приложения: каждый вызов — новый контекст со своим менеджером
    транзакций и своим отправщиком писем, но над одной и той же БД (как несколько воркеров
    веб-приложения или перезапуск процесса)."""
    from src.bootstrap import build_application_context
    from src.configs.settings import AdminSettings
    from src.database.transaction import TransactionManager
    from src.repositories.factory import SQLAlchemyRepositoryFactory
    from tests.fakes import RecordingEmailSender

    def build():
        transactions = TransactionManager(session_factory)
        sender = RecordingEmailSender()
        context = build_application_context(
            SQLAlchemyRepositoryFactory(transactions.session),
            email_sender=sender,
            upload_root=tmp_path / "uploads",
            admin=AdminSettings("admin", "admin@example.org", "Admin12345!"),
            transaction_scope=transactions.transaction,
            transaction_hooks=transactions,
        )
        return SimpleNamespace(context=context, mail=sender)

    return build


@pytest.fixture
def apps(build_app):
    """Два независимых «процесса» с администратором, вошедшим в каждом."""
    first, second = build_app(), build_app()
    for app in (first, second):
        app.admin = app.context.auth_service.login("admin", "Admin12345!")
    return first, second


@pytest.fixture
def bob(apps):
    first, _ = apps
    return first.context.user_management_service.create_user(
        first.admin, "bob", "bob@example.org", "Password123!", Role.STUDENT
    )


def make_catalog(app):
    """Дисциплина и тема для материалов."""
    catalog = app.context.catalog_service
    discipline = catalog.create_discipline(app.admin, "Математика")
    return discipline, catalog.create_topic(app.admin, "Алгебра", discipline.id)


def make_material(app, tmp_path, title: str, author=None):
    """Материал с файлом; автор по умолчанию — администратор процесса."""
    discipline, topic = make_catalog(app)
    source = tmp_path / "lecture.pdf"
    source.write_bytes(b"12345")
    return app.context.material_service.create_material(
        author or app.admin, title, "описание", discipline.id, topic.id, source
    )


@pytest.fixture
def material(apps, tmp_path):
    return make_material(apps[0], tmp_path, "A")
