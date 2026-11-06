"""Фасад (Facade) входа в систему для REST API: вход, проверка токена и выход одним вызовом.

Для CLI хватало `AuthService.login`: пользователь вошёл, и объект `User` живёт в памяти
процесса. У HTTP нет «процесса пользователя»: каждый запрос приходит отдельно, поэтому после
входа выдаётся токен, а на каждый запрос по токену восстанавливается пользователь.

`SessionService` скрывает от роутеров три вещи сразу: проверку пароля и запись в журнал
(`AuthService`), выпуск и отзыв токенов (`AuthTokenRepository`) и повторную проверку учётной
записи (удалена, заблокирована). Роутеру достаточно трёх методов, а сервисы под фасадом
остаются прежними и по-прежнему работают в CLI.

Токен хранится в БД только в виде SHA-256 (как коды восстановления пароля), поэтому выход
действительно отзывает токен, а состояние общее для всех процессов сервера.
"""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from src.configs.config import AUTH_TOKEN_TTL_HOURS
from src.domain.exceptions import AccountBlockedError, AccountDeletedError, InvalidTokenError
from src.domain.models import AuthToken, User
from src.repositories.interfaces import AuthTokenRepository, UserRepository
from src.services.auth_service import AuthService


@dataclass(frozen=True)
class OpenedSession:
    """Результат входа: пользователь и выданный токен (открытый вид показывается один раз)."""

    user: User
    token: str
    expires_at: datetime


class SessionService:
    """Фасад над `AuthService` и хранилищем токенов доступа."""

    def __init__(
        self,
        auth_service: AuthService,
        user_repository: UserRepository,
        token_repository: AuthTokenRepository,
        token_ttl: timedelta = timedelta(hours=AUTH_TOKEN_TTL_HOURS),
    ) -> None:
        """Принять сервис аутентификации, хранилища пользователей и токенов, срок жизни токена."""
        self._auth_service = auth_service
        self._user_repository = user_repository
        self._token_repository = token_repository
        self._token_ttl = token_ttl

    def open_session(self, login: str, plain_password: str) -> OpenedSession:
        """Проверить логин и пароль, выдать токен и записать вход в журнал."""
        user = self._auth_service.login(login, plain_password)
        now = datetime.now(UTC)
        self._token_repository.delete_expired(now)
        token = secrets.token_urlsafe(32)
        expires_at = now + self._token_ttl
        self._token_repository.add(AuthToken(0, user.id, self._hash(token), expires_at))
        return OpenedSession(user, token, expires_at)

    def authenticate(self, token: str) -> User:
        """Вернуть актуального пользователя по токену или выбросить ошибку.

        Пользователь читается из БД при каждом вызове, поэтому смена роли и блокировка
        действуют сразу, а не после повторного входа.
        """
        token_hash = self._hash(token)
        stored = self._token_repository.get_by_hash(token_hash)
        if stored is None:
            raise InvalidTokenError()
        if stored.expires_at <= datetime.now(UTC):
            self._token_repository.delete_by_hash(token_hash)
            raise InvalidTokenError()
        user = self._user_repository.get_by_id(stored.user_id)
        if user is None:
            raise AccountDeletedError()
        if not user.is_active():
            raise AccountBlockedError()
        return user

    def close_session(self, token: str) -> None:
        """Отозвать токен и записать выход в журнал."""
        user = self.authenticate(token)
        self._token_repository.delete_by_hash(self._hash(token))
        self._auth_service.logout(user)

    @staticmethod
    def _hash(token: str) -> str:
        """Вернуть SHA-256 токена в шестнадцатеричном виде."""
        return hashlib.sha256(token.encode("utf-8")).hexdigest()
