"""Абстрактная фабрика (Abstract Factory): целое семейство репозиториев создаётся вместе.

Сервисы и корень сборки работают с `RepositoryFactory`, не зная, где лежат данные.
`SQLAlchemyRepositoryFactory` возвращает согласованный набор репозиториев PostgreSQL;
сервисы и `bootstrap.py` при этом не меняются.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.repositories.domain_adapters import (
    SqlAuthTokenRepository,
    SqlDisciplineRepository,
    SqlEventRepository,
    SqlFailedLoginRepository,
    SqlFavoriteRepository,
    SqlMaterialRepository,
    SqlMaterialRevisionRepository,
    SqlPasswordResetTokenRepository,
    SqlTopicRepository,
    SqlUserRepository,
)
from src.repositories.interfaces import (
    AuthTokenRepository,
    DisciplineRepository,
    EventRepository,
    FailedLoginRepository,
    FavoriteRepository,
    MaterialRepository,
    MaterialRevisionRepository,
    PasswordResetTokenRepository,
    TopicRepository,
    UserRepository,
)
from src.repositories.sqlalchemy import SessionLike


class RepositoryFactory(ABC):
    """Контракт семейства репозиториев: все они принадлежат одному виду хранилища."""

    @abstractmethod
    def create_user_repository(self) -> UserRepository:
        """Создать хранилище пользователей."""

    @abstractmethod
    def create_discipline_repository(self) -> DisciplineRepository:
        """Создать хранилище дисциплин."""

    @abstractmethod
    def create_topic_repository(self) -> TopicRepository:
        """Создать хранилище тем."""

    @abstractmethod
    def create_material_repository(self) -> MaterialRepository:
        """Создать хранилище материалов."""

    @abstractmethod
    def create_favorite_repository(self) -> FavoriteRepository:
        """Создать хранилище избранного."""

    @abstractmethod
    def create_event_repository(self) -> EventRepository:
        """Создать хранилище журнала событий."""

    @abstractmethod
    def create_password_reset_token_repository(self) -> PasswordResetTokenRepository:
        """Создать хранилище кодов восстановления пароля."""

    @abstractmethod
    def create_auth_token_repository(self) -> AuthTokenRepository:
        """Создать хранилище токенов доступа к API."""

    @abstractmethod
    def create_failed_login_repository(self) -> FailedLoginRepository:
        """Создать хранилище неудачных попыток входа."""

    @abstractmethod
    def create_material_revision_repository(self) -> MaterialRevisionRepository:
        """Создать хранилище снимков материалов для отмены правок."""


class SQLAlchemyRepositoryFactory(RepositoryFactory):
    """Семейство репозиториев, хранящих данные в PostgreSQL через SQLAlchemy."""

    def __init__(self, session: SessionLike) -> None:
        """Принять сессию, общую для всех репозиториев семейства (одна транзакция)."""
        self._session = session

    def create_user_repository(self) -> UserRepository:
        """Создать хранилище пользователей в PostgreSQL."""
        return SqlUserRepository(self._session)

    def create_discipline_repository(self) -> DisciplineRepository:
        """Создать хранилище дисциплин в PostgreSQL."""
        return SqlDisciplineRepository(self._session)

    def create_topic_repository(self) -> TopicRepository:
        """Создать хранилище тем в PostgreSQL."""
        return SqlTopicRepository(self._session)

    def create_material_repository(self) -> MaterialRepository:
        """Создать хранилище материалов в PostgreSQL."""
        return SqlMaterialRepository(self._session)

    def create_favorite_repository(self) -> FavoriteRepository:
        """Создать хранилище избранного в PostgreSQL."""
        return SqlFavoriteRepository(self._session)

    def create_event_repository(self) -> EventRepository:
        """Создать журнал событий в PostgreSQL."""
        return SqlEventRepository(self._session)

    def create_password_reset_token_repository(self) -> PasswordResetTokenRepository:
        """Создать хранилище кодов восстановления пароля в PostgreSQL."""
        return SqlPasswordResetTokenRepository(self._session)

    def create_auth_token_repository(self) -> AuthTokenRepository:
        """Создать хранилище токенов доступа к API в PostgreSQL."""
        return SqlAuthTokenRepository(self._session)

    def create_failed_login_repository(self) -> FailedLoginRepository:
        """Создать хранилище неудачных попыток входа в PostgreSQL."""
        return SqlFailedLoginRepository(self._session)

    def create_material_revision_repository(self) -> MaterialRevisionRepository:
        """Создать хранилище снимков материалов в PostgreSQL."""
        return SqlMaterialRevisionRepository(self._session)
