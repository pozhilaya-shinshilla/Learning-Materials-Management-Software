from __future__ import annotations

from src.domain.enums import AccountStatus, EventType, Role
from src.domain.exceptions import (
    DuplicateEmailError,
    DuplicateLoginError,
    SameRoleError,
    SelfBlockError,
    SelfDeleteError,
    SelfRoleChangeError,
    UserAlreadyBlockedError,
    UserManagementAccessError,
    UserNotBlockedError,
    UserNotFoundError,
)
from src.domain.models import User
from src.domain.validation import validate_email, validate_login, validate_password
from src.repositories.interfaces import UserRepository
from src.security.password_hasher import PasswordHasher
from src.services.event_log_service import EventLogService


class UserManagementService:
    """Позволяет администраторам создавать, изменять и удалять учётные записи."""

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
        """Вернуть всех зарегистрированных пользователей."""
        self._require_admin(requesting_user)
        return self._user_repository.list_all()

    def get_author_login(self, user_id: int) -> str:
        """Вернуть логин пользователя для показа (доступно всем ролям); удалённого помечает."""
        user = self._user_repository.get_by_id(user_id)
        return user.login if user is not None else "удалённый пользователь"

    def create_user(
        self,
        requesting_user: User,
        login: str,
        email: str,
        plain_password: str,
        role: Role,
    ) -> User:
        """Создать учётную запись; доступно только администраторам."""
        self._require_admin(requesting_user)
        self.ensure_login_available(login)
        self.ensure_email_available(email)
        validate_password(plain_password)
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

    def ensure_login_available(self, login: str) -> None:
        """Выбросить ошибку, если логин неверного формата или уже занят."""
        validate_login(login)
        if self._user_repository.get_by_login(login) is not None:
            raise DuplicateLoginError(login=login)

    def ensure_email_available(self, email: str) -> None:
        """Выбросить ошибку, если email неверного формата или уже используется."""
        validate_email(email)
        if self._find_by_email(email) is not None:
            raise DuplicateEmailError(email=email)

    def change_role(self, requesting_user: User, target_user_id: int, new_role: Role) -> User:
        """Изменить роль другого пользователя; доступно только администраторам."""
        self._require_admin(requesting_user)
        target = self._get_existing_user(target_user_id)
        if target.id == requesting_user.id:
            raise SelfRoleChangeError()
        if target.role is new_role:
            raise SameRoleError(login=target.login, role=new_role.label)
        target.role = new_role
        self._user_repository.update(target)
        self._event_log_service.record(
            requesting_user.id, EventType.USER_ROLE_CHANGED, target.login
        )
        return target

    def set_blocked(self, requesting_user: User, target_user_id: int, blocked: bool) -> User:
        """Заблокировать или разблокировать учётную запись; доступно только администраторам."""
        self._require_admin(requesting_user)
        target = self._get_existing_user(target_user_id)
        if blocked and target.id == requesting_user.id:
            raise SelfBlockError()
        if blocked == (target.status is AccountStatus.BLOCKED):
            if blocked:
                raise UserAlreadyBlockedError(login=target.login)
            raise UserNotBlockedError(login=target.login)
        target.status = AccountStatus.BLOCKED if blocked else AccountStatus.ACTIVE
        self._user_repository.update(target)
        event_type = EventType.USER_BLOCKED if blocked else EventType.USER_UNBLOCKED
        self._event_log_service.record(requesting_user.id, event_type, target.login)
        return target

    def delete_user(self, requesting_user: User, target_user_id: int) -> None:
        """Удалить учётную запись; доступно только администраторам."""
        self._require_admin(requesting_user)
        target = self._get_existing_user(target_user_id)
        if target.id == requesting_user.id:
            raise SelfDeleteError()
        self._user_repository.delete(target.id)
        self._event_log_service.record(
            requesting_user.id, EventType.USER_ACCOUNT_CHANGED, f"deleted:{target.login}"
        )

    def _find_by_email(self, email: str) -> User | None:
        """Найти пользователя по email (без учёта регистра)."""
        for user in self._user_repository.list_all():
            if user.email.casefold() == email.casefold():
                return user
        return None

    def _get_existing_user(self, user_id: int) -> User:
        """Вернуть пользователя или выбросить ошибку, если его нет."""
        user = self._user_repository.get_by_id(user_id)
        if user is None:
            raise UserNotFoundError(user_id=user_id)
        return user

    def _require_admin(self, requesting_user: User) -> None:
        """Пропустить только администратора."""
        if requesting_user.role is not Role.ADMIN:
            raise UserManagementAccessError()
