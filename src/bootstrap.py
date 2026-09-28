from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.domain.enums import Role
from src.domain.models import User
from src.repositories.in_memory import (
    InMemoryDisciplineRepository,
    InMemoryEventRepository,
    InMemoryFavoriteRepository,
    InMemoryMaterialRepository,
    InMemoryTopicRepository,
    InMemoryUserRepository,
)
from src.security.password_hasher import Pbkdf2PasswordHasher
from src.services.auth_service import AuthService
from src.services.catalog_service import CatalogService
from src.services.event_log_service import EventLogService
from src.services.favorite_service import FavoriteService
from src.services.material_service import MaterialService
from src.services.search_service import SearchService
from src.services.user_management_service import UserManagementService
from src.storage.file_storage import LocalFileStorage

DEFAULT_ADMIN_LOGIN = "admin"
DEFAULT_ADMIN_PASSWORD = "admin123"
DEFAULT_ADMIN_EMAIL = "admin@example.org"

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_UPLOAD_STORAGE_ROOT = _PROJECT_ROOT / "data" / "uploads"


@dataclass
class ApplicationContext:
    """Bundles every fully-wired service the CLI layer depends on."""

    auth_service: AuthService
    user_management_service: UserManagementService
    material_service: MaterialService
    search_service: SearchService
    favorite_service: FavoriteService
    event_log_service: EventLogService
    catalog_service: CatalogService


def build_application_context() -> ApplicationContext:
    """Construct in-memory repositories and services, then seed an admin account."""
    user_repository = InMemoryUserRepository()
    discipline_repository = InMemoryDisciplineRepository()
    topic_repository = InMemoryTopicRepository()
    material_repository = InMemoryMaterialRepository()
    favorite_repository = InMemoryFavoriteRepository()
    event_repository = InMemoryEventRepository()

    password_hasher = Pbkdf2PasswordHasher()
    file_storage = LocalFileStorage(_UPLOAD_STORAGE_ROOT)
    event_log_service = EventLogService(event_repository)
    auth_service = AuthService(user_repository, password_hasher, event_log_service)
    user_management_service = UserManagementService(
        user_repository, password_hasher, event_log_service
    )
    material_service = MaterialService(material_repository, event_log_service, file_storage)
    search_service = SearchService(material_repository)
    favorite_service = FavoriteService(favorite_repository, material_repository, event_log_service)
    catalog_service = CatalogService(discipline_repository, topic_repository, event_log_service)

    _seed_admin(user_repository, password_hasher)

    return ApplicationContext(
        auth_service=auth_service,
        user_management_service=user_management_service,
        material_service=material_service,
        search_service=search_service,
        favorite_service=favorite_service,
        event_log_service=event_log_service,
        catalog_service=catalog_service,
    )


def _seed_admin(
    user_repository: InMemoryUserRepository, password_hasher: Pbkdf2PasswordHasher
) -> None:
    if user_repository.get_by_login(DEFAULT_ADMIN_LOGIN) is not None:
        return
    admin = User(
        id=0,
        login=DEFAULT_ADMIN_LOGIN,
        email=DEFAULT_ADMIN_EMAIL,
        password_hash=password_hasher.hash(DEFAULT_ADMIN_PASSWORD),
        role=Role.ADMIN,
    )
    user_repository.add(admin)
