from __future__ import annotations

from src.domain.enums import AccountStatus, EventType, Role
from src.domain.exceptions import AuthorizationError, DuplicateLoginError, ValidationError
from src.domain.models import User
from src.domain.validation import validate_email, validate_login, validate_password
from src.repositories.interfaces import UserRepository
from src.security.password_hasher import PasswordHasher
from src.services.event_log_service import EventLogService


class UserManagementService:
    """Lets administrators register, modify and remove user accounts."""

    def __init__(
        self,
        user_repository: UserRepository,
        password_hasher: PasswordHasher,
        event_log_service: EventLogService,
    ) -> None:
        self._user_repository = user_repository
        self._password_hasher = password_hasher
        self._event_log_service = event_log_service

    def list_users(self, requesting_user: User) -> list[User]:
        """Return every registered user."""
        self._require_admin(requesting_user)
        return self._user_repository.list_all()

    def create_user(
        self,
        requesting_user: User,
        login: str,
        email: str,
        plain_password: str,
        role: Role,
    ) -> User:
        """Register a new account; only administrators may do this."""
        self._require_admin(requesting_user)
        validate_login(login)
        validate_email(email)
        validate_password(plain_password)
        if self._user_repository.get_by_login(login) is not None:
            raise DuplicateLoginError(f"Логин '{login}' уже занят.")
        if self._find_by_email(email) is not None:
            raise DuplicateLoginError(f"Email '{email}' уже используется другой учетной записью.")
        user = User(
            id=0,
            login=login,
            email=email,
            password_hash=self._password_hasher.hash(plain_password),
            role=role,
        )
        created = self._user_repository.add(user)
        self._event_log_service.record(
            requesting_user.id, EventType.USER_ACCOUNT_CHANGED, f"created:{login}"
        )
        return created

    def change_role(self, requesting_user: User, target_user_id: int, new_role: Role) -> User:
        """Change another user's role; only administrators may do this."""
        self._require_admin(requesting_user)
        target = self._get_existing_user(target_user_id)
        target.role = new_role
        self._user_repository.update(target)
        self._event_log_service.record(
            requesting_user.id, EventType.USER_ROLE_CHANGED, target.login
        )
        return target

    def set_blocked(self, requesting_user: User, target_user_id: int, blocked: bool) -> User:
        """Block or unblock an account; only administrators may do this."""
        self._require_admin(requesting_user)
        target = self._get_existing_user(target_user_id)
        if blocked and target.id == requesting_user.id:
            raise AuthorizationError("Нельзя заблокировать собственную учетную запись.")
        target.status = AccountStatus.BLOCKED if blocked else AccountStatus.ACTIVE
        self._user_repository.update(target)
        event_type = EventType.USER_BLOCKED if blocked else EventType.USER_UNBLOCKED
        self._event_log_service.record(requesting_user.id, event_type, target.login)
        return target

    def delete_user(self, requesting_user: User, target_user_id: int) -> None:
        """Delete an account; only administrators may do this."""
        self._require_admin(requesting_user)
        target = self._get_existing_user(target_user_id)
        if target.id == requesting_user.id:
            raise AuthorizationError("Нельзя удалить собственную учетную запись.")
        self._user_repository.delete(target.id)
        self._event_log_service.record(
            requesting_user.id, EventType.USER_ACCOUNT_CHANGED, f"deleted:{target.login}"
        )

    def _find_by_email(self, email: str) -> User | None:
        for user in self._user_repository.list_all():
            if user.email.casefold() == email.casefold():
                return user
        return None

    def _get_existing_user(self, user_id: int) -> User:
        user = self._user_repository.get_by_id(user_id)
        if user is None:
            raise ValidationError(f"Пользователь с id {user_id} не найден.")
        return user

    def _require_admin(self, requesting_user: User) -> None:
        if requesting_user.role is not Role.ADMIN:
            raise AuthorizationError("Только администратор может управлять учетными записями.")
