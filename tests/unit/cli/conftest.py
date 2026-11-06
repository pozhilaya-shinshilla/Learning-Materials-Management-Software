from __future__ import annotations

import pytest

from src.bootstrap import ApplicationContext
from src.domain.enums import Role
from src.notifications.email_sender import EmailSender
from src.services.auth_service import AuthService
from src.services.catalog_service import CatalogService
from src.services.event_log_service import EventLogService
from src.services.favorite_service import FavoriteService
from src.services.material_service import MaterialService
from src.services.search_service import SearchService
from src.services.session_service import SessionService
from src.services.user_management_service import UserManagementService
from src.storage.file_storage import LocalFileStorage
from tests.fakes import PlainPasswordHasher, RecordingEmailSender


@pytest.fixture
def mail() -> EmailSender:
    return RecordingEmailSender()


@pytest.fixture
def app(tmp_path, mail, repository_factory) -> ApplicationContext:
    """Контекст из настоящих сервисов и репозиториев PostgreSQL, но с быстрым хешером."""
    users = repository_factory.create_user_repository()
    disciplines = repository_factory.create_discipline_repository()
    topics = repository_factory.create_topic_repository()
    materials = repository_factory.create_material_repository()
    favorites = repository_factory.create_favorite_repository()
    log = EventLogService(repository_factory.create_event_repository())
    hasher = PlainPasswordHasher()
    storage = LocalFileStorage(tmp_path / "storage")
    auth = AuthService(
        users, repository_factory.create_password_reset_token_repository(), hasher, log, mail
    )
    return ApplicationContext(
        auth_service=auth,
        user_management_service=UserManagementService(users, hasher, log),
        material_service=MaterialService(
            materials,
            disciplines,
            topics,
            repository_factory.create_material_revision_repository(),
            log,
            storage,
        ),
        search_service=SearchService(materials),
        favorite_service=FavoriteService(favorites, materials, log),
        event_log_service=log,
        catalog_service=CatalogService(disciplines, topics, log),
        session_service=SessionService(
            auth, users, repository_factory.create_auth_token_repository()
        ),
    )


@pytest.fixture
def admin(app):
    from src.domain.models import User

    repo = app.user_management_service._user_repository
    return repo.add(User(0, "boss", "boss@example.org", "hashed:Password1!", Role.ADMIN))


@pytest.fixture
def make_account(app, admin):
    def _make(login: str, role: Role = Role.STUDENT):
        return app.user_management_service.create_user(
            admin, login, f"{login}@example.org", "Password1!", role
        )

    return _make


@pytest.fixture
def teacher(make_account):
    return make_account("teacher", Role.TEACHER)


@pytest.fixture
def student(make_account):
    return make_account("student", Role.STUDENT)


@pytest.fixture
def seeded(app, teacher, tmp_path):
    """Каталог с одной дисциплиной, двумя темами и одним материалом."""
    math = app.catalog_service.create_discipline(teacher, "Математика")
    algebra = app.catalog_service.create_topic(teacher, "Алгебра", math.id)
    app.catalog_service.create_topic(teacher, "Геометрия", math.id)
    source = tmp_path / "lecture.pdf"
    source.write_bytes(b"content")
    material = app.material_service.create_material(
        teacher, "Линейные уравнения", "Решение систем", math.id, algebra.id, source
    )
    return math, algebra, material
