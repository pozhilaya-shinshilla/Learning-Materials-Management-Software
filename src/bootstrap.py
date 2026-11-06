from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager, nullcontext
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.orm import Session, sessionmaker

from src.configs.settings import (
    AdminSettings,
    load_admin_settings,
    load_app_timezone,
    load_smtp_settings,
)
from src.database.transaction import TransactionalService, TransactionManager
from src.domain.enums import Role
from src.domain.models import User
from src.notifications.email_sender import (
    ConsoleEmailSender,
    EmailSender,
    LoggingEmailSender,
    RetryingEmailSender,
)
from src.notifications.login_alerts import FailedLoginAlertObserver
from src.notifications.smtp_sender import SmtpEmailSender
from src.repositories.factory import RepositoryFactory, SQLAlchemyRepositoryFactory
from src.repositories.interfaces import UserRepository
from src.security.password_hasher import PasswordHasher, Pbkdf2PasswordHasher
from src.services.auth_service import AuthService
from src.services.catalog_service import CatalogService
from src.services.event_log_service import EventLogService
from src.services.favorite_service import FavoriteService
from src.services.material_service import MaterialService
from src.services.search_service import SearchService
from src.services.session_service import SessionService
from src.services.token_revocation import TokenRevocationObserver
from src.services.transaction_hooks import TransactionHooks
from src.services.user_management_service import UserManagementService
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
    session_service: SessionService


def build_application_context(
    repository_factory: RepositoryFactory,
    email_sender: EmailSender | None = None,
    upload_root: Path | None = None,
    admin: AdminSettings | None = None,
    transaction_scope: Callable[[], AbstractContextManager[None]] | None = None,
    transaction_hooks: TransactionHooks | None = None,
) -> ApplicationContext:
    """Создать репозитории и сервисы, затем добавить учётную запись администратора.

    `repository_factory` обязателен: данные всегда лежат в PostgreSQL (в `main.py` передаётся
    `SQLAlchemyRepositoryFactory`). `transaction_scope` — контекстный менеджер транзакции: каждая
    операция сервиса выполняется внутри него, а фиксирует транзакцию владелец сессии, а не
    репозиторий. Без него транзакцией управляет вызывающий код (так собираются тесты).
    `transaction_hooks` — тот же владелец транзакции (`TransactionManager`) в роли «по исходу»:
    письма и удаление файлов откладываются до фиксации, а копия файла убирается при откате.
    Область транзакции и хуки задаются вместе: письмо, отправленное из открытой транзакции,
    держало бы соединение с БД и могло уйти, хотя транзакция откатится.
    `email_sender`, `upload_root` и `admin` можно подменить: без подмены письма выводятся в консоль,
    файлы сохраняются в `data/uploads`, а данные администратора берутся из переменных окружения
    или `.env` (см. `load_admin_settings`).

    Применяемые паттерны: «Абстрактная фабрика» (семейство репозиториев), «Заместитель»
    (транзакция на операцию сервиса), «Декоратор» (повтор и лог отправки писем), «Адаптер»
    (SMTP), «Наблюдатель» (письмо о неудачных входах, отзыв токенов после смены пароля),
    «Хранитель» (история правок в БД), «Фасад» (`SessionService`: вход по токену для REST API).
    """
    if (transaction_scope is None) != (transaction_hooks is None):
        raise ValueError("transaction_scope и transaction_hooks задаются только вместе")
    factory = repository_factory
    user_repository = factory.create_user_repository()
    discipline_repository = factory.create_discipline_repository()
    topic_repository = factory.create_topic_repository()
    material_repository = factory.create_material_repository()
    favorite_repository = factory.create_favorite_repository()
    event_repository = factory.create_event_repository()

    password_hasher = Pbkdf2PasswordHasher()
    file_storage = LocalFileStorage(upload_root or _UPLOAD_STORAGE_ROOT)
    mail = LoggingEmailSender(RetryingEmailSender(email_sender or _default_email_sender()))
    event_log_service = EventLogService(event_repository)
    event_log_service.subscribe(
        FailedLoginAlertObserver(
            user_repository,
            factory.create_failed_login_repository(),
            mail,
            transaction_hooks=transaction_hooks,
        )
    )
    auth_token_repository = factory.create_auth_token_repository()
    event_log_service.subscribe(TokenRevocationObserver(auth_token_repository))
    auth_service = AuthService(
        user_repository,
        factory.create_password_reset_token_repository(),
        password_hasher,
        event_log_service,
        mail,
        transaction_hooks=transaction_hooks,
    )
    user_management_service = UserManagementService(
        user_repository, password_hasher, event_log_service, auth_token_repository
    )
    material_service = MaterialService(
        material_repository,
        discipline_repository,
        topic_repository,
        factory.create_material_revision_repository(),
        event_log_service,
        file_storage,
        transaction_hooks=transaction_hooks,
    )
    search_service = SearchService(material_repository, load_app_timezone())
    favorite_service = FavoriteService(favorite_repository, material_repository, event_log_service)
    catalog_service = CatalogService(discipline_repository, topic_repository, event_log_service)
    session_service = SessionService(auth_service, user_repository, auth_token_repository)

    with (transaction_scope or nullcontext)():
        _seed_admin(user_repository, password_hasher, admin or load_admin_settings())

    def wrap[ServiceT](service: ServiceT) -> ServiceT:
        """Подставить заместителя с транзакцией, если хранилище её требует."""
        if transaction_scope is None:
            return service
        return TransactionalService(service, transaction_scope)  # type: ignore[return-value]

    return ApplicationContext(
        auth_service=wrap(auth_service),
        user_management_service=wrap(user_management_service),
        material_service=wrap(material_service),
        search_service=wrap(search_service),
        favorite_service=wrap(favorite_service),
        event_log_service=wrap(event_log_service),
        catalog_service=wrap(catalog_service),
        session_service=wrap(session_service),
    )


def _default_email_sender() -> EmailSender:
    """Выбрать отправщика писем: SMTP, если он настроен, иначе имитация в консоли."""
    smtp_settings = load_smtp_settings()
    if smtp_settings is None:
        return ConsoleEmailSender()
    return SmtpEmailSender(smtp_settings)


def _seed_admin(
    user_repository: UserRepository,
    password_hasher: PasswordHasher,
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


def build_transactional_context(
    session_factory: sessionmaker[Session],
    *,
    admin: AdminSettings | None = None,
    email_sender: EmailSender | None = None,
    upload_root: Path | None = None,
) -> ApplicationContext:
    """Собрать приложение поверх PostgreSQL: сессия — единица работы (Unit of Work).

    Единственное место, где `TransactionManager` соединяется с репозиториями и сервисами.
    Им пользуются все точки входа (консоль, REST API, тесты), поэтому правила транзакций,
    блокировок и отложенных писем у них одинаковые.
    """
    transactions = TransactionManager(session_factory)
    return build_application_context(
        repository_factory=SQLAlchemyRepositoryFactory(transactions.session),
        email_sender=email_sender,
        upload_root=upload_root,
        admin=admin,
        transaction_scope=transactions.transaction,
        transaction_hooks=transactions,
    )
