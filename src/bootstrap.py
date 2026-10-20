from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.domain.enums import Role
from src.domain.models import User
from src.notifications.email_sender import ConsoleEmailSender, EmailSender
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
from src.settings import AdminSettings, load_admin_settings
from src.storage.file_storage import LocalFileStorage

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_UPLOAD_STORAGE_ROOT = _PROJECT_ROOT / "data" / "uploads"


@dataclass
class ApplicationContext:
    """Объединяет все готовые к работе сервисы, от которых зависит интерфейс."""

    auth_service: AuthService
    user_management_service: UserManagementService
    material_service: MaterialService
    search_service: SearchService
    favorite_service: FavoriteService
    event_log_service: EventLogService
    catalog_service: CatalogService


def build_application_context(
    email_sender: EmailSender | None = None,
    upload_root: Path | None = None,
    admin: AdminSettings | None = None,
) -> ApplicationContext:
    """Создать репозитории в памяти и сервисы, затем добавить учётную запись администратора.

    `email_sender`, `upload_root` и `admin` можно подменить (в тестах); по умолчанию письма
    выводятся в консоль, файлы сохраняются в `data/uploads`, а данные администратора
    берутся из переменных окружения или `.env` (см. `load_admin_settings`).
    """
    user_repository = InMemoryUserRepository()
    discipline_repository = InMemoryDisciplineRepository()
    topic_repository = InMemoryTopicRepository()
    material_repository = InMemoryMaterialRepository()
    favorite_repository = InMemoryFavoriteRepository()
    event_repository = InMemoryEventRepository()

    password_hasher = Pbkdf2PasswordHasher()
    file_storage = LocalFileStorage(upload_root or _UPLOAD_STORAGE_ROOT)
    event_log_service = EventLogService(event_repository)
    auth_service = AuthService(
        user_repository, password_hasher, event_log_service, email_sender or ConsoleEmailSender()
    )
    user_management_service = UserManagementService(
        user_repository, password_hasher, event_log_service
    )
    material_service = MaterialService(
        material_repository,
        discipline_repository,
        topic_repository,
        event_log_service,
        file_storage,
    )
    search_service = SearchService(material_repository)
    favorite_service = FavoriteService(favorite_repository, material_repository, event_log_service)
    catalog_service = CatalogService(discipline_repository, topic_repository, event_log_service)

    _seed_admin(user_repository, password_hasher, admin or load_admin_settings())

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
    user_repository: InMemoryUserRepository,
    password_hasher: Pbkdf2PasswordHasher,
    admin: AdminSettings,
) -> None:
    """Создать администратора с заданными учётными данными, если его ещё нет."""
    if user_repository.get_by_login(admin.login) is not None:
        return
    user_repository.add(
        User(
            id=0,
            login=admin.login,
            email=admin.email,
            password_hash=password_hasher.hash(admin.password),
            role=Role.ADMIN,
        )
    )
