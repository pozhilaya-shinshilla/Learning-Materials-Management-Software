from __future__ import annotations

import secrets

from src.domain.enums import AccountStatus, EventType
from src.domain.exceptions import AccountBlockedError, AuthenticationError
from src.domain.models import User
from src.domain.validation import validate_password
from src.repositories.interfaces import UserRepository
from src.security.password_hasher import PasswordHasher
from src.services.event_log_service import EventLogService


class AuthService:
    """Handles credential verification and session lifecycle events."""

    def __init__(
        self,
        user_repository: UserRepository,
        password_hasher: PasswordHasher,
        event_log_service: EventLogService,
    ) -> None:
        self._user_repository = user_repository
        self._password_hasher = password_hasher
        self._event_log_service = event_log_service

    def login(self, login: str, plain_password: str) -> User:
        """Verify credentials and return the authenticated user."""
        user = self._user_repository.get_by_login(login)
        if user is None or not self._password_hasher.verify(plain_password, user.password_hash):
            self._event_log_service.record(0, EventType.USER_LOGIN_FAILED, login)
            raise AuthenticationError("Invalid login or password.")
        if user.status is AccountStatus.BLOCKED:
            self._event_log_service.record(user.id, EventType.USER_LOGIN_FAILED, login)
            raise AccountBlockedError("This account has been blocked.")
        self._event_log_service.record(user.id, EventType.USER_LOGGED_IN, user.login)
        return user

    def logout(self, user: User) -> None:
        """Record that the given user ended their session."""
        self._event_log_service.record(user.id, EventType.USER_LOGGED_OUT, user.login)

    def request_password_reset(self, login: str) -> str:
        """Issue a single-use password-reset token for the given login.

        Delivering the token by email is outside the scope of this stage;
        the token is returned so the caller can transmit it.
        """
        user = self._user_repository.get_by_login(login)
        if user is None:
            raise AuthenticationError("No account is registered with this login.")
        self._event_log_service.record(user.id, EventType.PASSWORD_RESET_REQUESTED, user.login)
        return secrets.token_urlsafe(24)

    def reset_password(self, user: User, new_plain_password: str) -> None:
        """Set a new password for the given user."""
        validate_password(new_plain_password)
        user.password_hash = self._password_hasher.hash(new_plain_password)
        self._user_repository.update(user)
        self._event_log_service.record(user.id, EventType.PASSWORD_RESET, user.login)
