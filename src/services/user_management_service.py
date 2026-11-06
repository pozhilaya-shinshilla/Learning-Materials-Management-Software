from __future__ import annotations

from src.domain.enums import AccountStatus, EventType, Role
from src.domain.exceptions import (
    AccountDeletedError,
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
from src.repositories.interfaces import AuthTokenRepository, UserRepository
from src.security.password_hasher import PasswordHasher
from src.services.event_log_service import EventLogService


class UserManagementService:
    """Позволяет администраторам создавать, изменять и удалять учётные записи."""

    def __init__(
        self,
        user_repository: UserRepository,
        password_hasher: PasswordHasher,
        event_log_service: EventLogService,
        token_repository: AuthTokenRepository | None = None,
    ) -> None:
        """Принять хранилище пользователей, хешер паролей, сервис журнала и хранилище токенов.

        Хранилище токенов нужно REST API: после смены роли выданные токены отзываются, и
        пользователь входит заново уже с новой ролью. В CLI токенов нет, и оно не передаётся.
        """
        self._user_repository = user_repository
        self._password_hasher = password_hasher
        self._event_log_service = event_log_service
        self._token_repository = token_repository

    def list_users(self, requesting_user: User) -> list[User]:
        """Вернуть всех зарегистрированных пользователей."""
        self._require_admin(requesting_user)
        return self._user_repository.list_all()

    def get_author_login(self, user_id: int | None) -> str:
        """Вернуть логин автора для показа (доступно всем ролям); удалённого помечает.

        `None` — автора удалили, а материал остался (`ON DELETE SET NULL` в БД).
        """
        if user_id is None:
            return "автор удалён"
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
        if self._user_repository.get_by_email(email) is not None:
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
        if self._token_repository is not None:
            self._token_repository.delete_by_user(target.id)
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

    def update_user(
        self,
        requesting_user: User,
        target_user_id: int,
        role: Role | None = None,
        blocked: bool | None = None,
    ) -> User:
        """Изменить роль и/или блокировку учётной записи одной транзакцией.

        Значения, совпадающие с текущими, пропускаются: повторный запрос с теми же данными
        ничего не меняет и не считается ошибкой (так ведёт себя `PATCH`). Запреты на изменение
        себя проверяются *до* первой записи: `DomainError` не откатывает транзакцию, и иначе
        при отказе во второй части первая осталась бы применённой.
        """
        self._require_admin(requesting_user)
        target = self._get_existing_user(target_user_id)
        change_role = role is not None and role is not target.role
        change_block = blocked is not None and blocked != (target.status is AccountStatus.BLOCKED)
        if target.id == requesting_user.id:
            if change_role:
                raise SelfRoleChangeError()
            if change_block and blocked:
                raise SelfBlockError()
        if change_role and role is not None:
            target = self.change_role(requesting_user, target_user_id, role)
        if change_block and blocked is not None:
            target = self.set_blocked(requesting_user, target_user_id, blocked)
        return target

    def delete_user(self, requesting_user: User, target_user_id: int) -> None:
        """Удалить учётную запись; доступно только администраторам.

        Строки удаляемого и удаляющего блокируются вместе, по возрастанию id. Удаление берёт
        строку жертвы, а запись события в журнал ссылается на строку администратора; два
        администратора, удаляющие друг друга, брали бы эти строки в противоположном порядке и
        ждали бы друг друга по кругу. Проигравший получает обычную ошибку.
        """
        self._require_admin(requesting_user)
        target = self._get_existing_user(target_user_id)
        if target.id == requesting_user.id:
            raise SelfDeleteError()
        locked = self._user_repository.lock_many([requesting_user.id, target.id], exclusive=True)
        if requesting_user.id not in locked:
            raise AccountDeletedError()
        if target.id not in locked:
            raise UserNotFoundError(user_id=target.id)
        self._user_repository.delete(target.id)
        self._event_log_service.record(
            requesting_user.id, EventType.USER_ACCOUNT_CHANGED, f"deleted:{target.login}"
        )

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
