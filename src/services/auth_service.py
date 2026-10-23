 from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from src.config import RESET_TOKEN_TTL_MINUTES
from src.domain.enums import AccountStatus, EventType
from src.domain.exceptions import (
    AccountBlockedError,
    AccountDeletedError,
    AuthenticationError,
    InvalidResetTokenError,
)
from src.domain.models import User
from src.domain.validation import (
    validate_credentials_present,
    validate_email,
    validate_password,
)
from src.notifications.email_sender import EmailSender
from src.repositories.interfaces import UserRepository
from src.security.password_hasher import PasswordHasher
from src.services.event_log_service import EventLogService


class AuthService:
    """Проверяет учётные данные и записывает события входа и выхода.

    Коды восстановления пароля хранятся в памяти в виде «хеш кода -> (id пользователя,
    момент истечения)».
    """

    def __init__(
        self,
        user_repository: UserRepository,
        password_hasher: PasswordHasher,
        event_log_service: EventLogService,
        email_sender: EmailSender,
        reset_token_ttl: timedelta = timedelta(minutes=RESET_TOKEN_TTL_MINUTES),
    ) -> None:
        self._user_repository = user_repository
        self._password_hasher = password_hasher
        self._event_log_service = event_log_service
        self._email_sender = email_sender
        self._reset_token_ttl = reset_token_ttl
        self._reset_tokens: dict[str, tuple[int, datetime]] = {}

    def login(self, login: str, plain_password: str) -> User:
        """Проверить ввод и учётные данные, вернуть вошедшего пользователя."""
        validate_credentials_present(login, plain_password)
        login = login.strip()
        user = self._user_repository.get_by_login(login)
        if user is None or not self._password_hasher.verify(plain_password, user.password_hash):
            self._event_log_service.record(0, EventType.USER_LOGIN_FAILED, login)
            raise AuthenticationError()
        if user.status is AccountStatus.BLOCKED:
            self._event_log_service.record(user.id, EventType.USER_LOGIN_FAILED, login)
            raise AccountBlockedError()
        self._event_log_service.record(user.id, EventType.USER_LOGGED_IN, user.login)
        return user

    def ensure_session_active(self, user: User) -> User:
        """Проверить по хранилищу, что учётная запись цела и не заблокирована.

        Возвращает актуальную запись пользователя. Если администратор заблокировал
        или удалил учётную запись во время сеанса, выбрасывает ошибку, и сеанс
        нужно завершить.
        """
        current = self._user_repository.get_by_id(user.id)
        if current is None:
            raise AccountDeletedError()
        if current.status is AccountStatus.BLOCKED:
            raise AccountBlockedError()
        return current

    def logout(self, user: User) -> None:
        """Записать в журнал, что пользователь завершил сеанс."""
        self._event_log_service.record(user.id, EventType.USER_LOGGED_OUT, user.login)

    def request_password_reset(self, email: str) -> None:
        """Отправить на email код восстановления пароля.

        Результат одинаков независимо от того, есть ли такая учётная запись:
        так по ответу нельзя узнать, какие адреса зарегистрированы.
        Прежние неиспользованные коды этого пользователя перестают действовать.
        """
        cleaned = email.strip()
        validate_email(cleaned)
        user = self._user_repository.get_by_email(cleaned)
        if user is None:
            return
        self._revoke_reset_tokens(user.id)
        token = secrets.token_hex(6)
        expires_at = datetime.now(UTC) + self._reset_token_ttl
        self._reset_tokens[self._hash_token(token)] = (user.id, expires_at)
        minutes = int(self._reset_token_ttl.total_seconds() // 60)
        self._email_sender.send(
            user.email,
            "Восстановление пароля",
            f"Здравствуйте, {user.login}!\n"
            f"Код для восстановления пароля: {token}\n"
            f"Код действует {minutes} мин. и может быть использован один раз.\n"
            "Если вы не запрашивали восстановление, просто проигнорируйте это письмо.",
        )
        self._event_log_service.record(user.id, EventType.PASSWORD_RESET_REQUESTED, user.login)

    def check_reset_token(self, token: str) -> User:
        """Вернуть владельца кода или выбросить InvalidResetTokenError."""
        key = self._hash_token(token.strip())
        entry = self._reset_tokens.get(key)
        if entry is None:
            raise InvalidResetTokenError()
        user_id, expires_at = entry
        if datetime.now(UTC) > expires_at:
            del self._reset_tokens[key]
            raise InvalidResetTokenError()
        user = self._user_repository.get_by_id(user_id)
        if user is None:
            del self._reset_tokens[key]
            raise InvalidResetTokenError()
        return user

    def reset_password_with_token(self, token: str, new_plain_password: str) -> None:
        """Задать новый пароль по коду из письма; код после этого перестаёт действовать."""
        user = self.check_reset_token(token)
        validate_password(new_plain_password)
        user.password_hash = self._password_hasher.hash(new_plain_password)
        self._user_repository.update(user)
        del self._reset_tokens[self._hash_token(token.strip())]
        self._event_log_service.record(user.id, EventType.PASSWORD_RESET, user.login)

    def _revoke_reset_tokens(self, user_id: int) -> None:
        """Аннулировать все выданные пользователю коды восстановления."""
        self._reset_tokens = {
            key: entry for key, entry in self._reset_tokens.items() if entry[0] != user_id
        }

    @staticmethod
    def _hash_token(token: str) -> str:
        """Хранить коды только в виде хеша, как и пароли."""
        return hashlib.sha256(token.encode("utf-8")).hexdigest()
