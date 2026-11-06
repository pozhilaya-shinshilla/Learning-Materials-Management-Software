from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from src.configs.config import RESET_TOKEN_TTL_MINUTES
from src.domain.enums import AccountStatus, EventType
from src.domain.exceptions import (
    AccountBlockedError,
    AccountDeletedError,
    AuthenticationError,
    InvalidResetTokenError,
    RoleChangedError,
)
from src.domain.models import PasswordResetToken, User
from src.domain.validation import (
    validate_credentials_present,
    validate_email,
    validate_password,
)
from src.notifications.email_sender import EmailSender
from src.repositories.interfaces import PasswordResetTokenRepository, UserRepository
from src.security.password_hasher import PasswordHasher
from src.services.event_log_service import EventLogService
from src.services.transaction_hooks import ImmediateHooks, TransactionHooks


class AuthService:
    """Проверяет учётные данные и записывает события входа и выхода.

    Коды восстановления пароля хранятся в БД (только SHA-256 кода, момент истечения и владелец),
    поэтому переживают перезапуск и одинаково видны всем процессам приложения.
    """

    def __init__(
        self,
        user_repository: UserRepository,
        reset_token_repository: PasswordResetTokenRepository,
        password_hasher: PasswordHasher,
        event_log_service: EventLogService,
        email_sender: EmailSender,
        reset_token_ttl: timedelta = timedelta(minutes=RESET_TOKEN_TTL_MINUTES),
        transaction_hooks: TransactionHooks | None = None,
    ) -> None:
        """Принять хранилища, хешер паролей, журнал, отправщик писем и срок жизни кода.

        `transaction_hooks` откладывает отправку письма до фиксации транзакции; без него письмо
        уходит сразу (так работает код, которым никто не управляет транзакцией).
        """
        self._user_repository = user_repository
        self._reset_token_repository = reset_token_repository
        self._password_hasher = password_hasher
        self._event_log_service = event_log_service
        self._email_sender = email_sender
        self._reset_token_ttl = reset_token_ttl
        self._hooks = transaction_hooks or ImmediateHooks()

    def login(self, login: str, plain_password: str) -> User:
        """Проверить ввод и учётные данные, вернуть вошедшего пользователя."""
        validate_credentials_present(login, plain_password)
        login = login.strip()
        user = self._user_repository.get_by_login(login)
        if user is None or not self._password_hasher.verify(plain_password, user.password_hash):
            self._event_log_service.record(None, EventType.USER_LOGIN_FAILED, login)
            raise AuthenticationError()
        if user.status is AccountStatus.BLOCKED:
            self._event_log_service.record(user.id, EventType.USER_LOGIN_FAILED, login)
            raise AccountBlockedError()
        self._event_log_service.record(user.id, EventType.USER_LOGGED_IN, user.login)
        return user

    def ensure_session_active(self, user: User) -> User:
        """Проверить по хранилищу, что учётная запись цела и не заблокирована.

        Возвращает актуальную запись пользователя. Если администратор заблокировал
        или удалил учётную запись либо сменил её роль во время сеанса, выбрасывает ошибку,
        и сеанс нужно завершить. Роль проверяется отдельно: права определяет объект
        `User`, полученный при входе, и без этой проверки понижение в должности
        вступило бы в силу только после выхода.
        """
        current = self._user_repository.get_by_id(user.id)
        if current is None:
            raise AccountDeletedError()
        if current.status is AccountStatus.BLOCKED:
            raise AccountBlockedError()
        if current.role is not user.role:
            raise RoleChangedError()
        return current

    def logout(self, user: User) -> None:
        """Записать в журнал, что пользователь завершил сеанс."""
        self._event_log_service.record(user.id, EventType.USER_LOGGED_OUT, user.login)

    def request_password_reset(self, email: str) -> None:
        """Отправить на email код восстановления пароля.

        Результат одинаков независимо от того, есть ли такая учётная запись:
        так по ответу нельзя узнать, какие адреса зарегистрированы.
        Прежние неиспользованные коды этого пользователя перестают действовать.

        Письмо уходит только после фиксации транзакции: при откате код в базе не появится, и
        письмо с несуществующим кодом не должно дойти до пользователя. Заодно соединение с БД
        не занято на время SMTP и его повторов. Если письмо всё же не удалось отправить, код уже
        выдан: пользователь запрашивает его заново, и прежний код перестаёт действовать.

        Строка пользователя блокируется на время операции: два одновременных запроса
        выстраиваются в очередь, и второй отзывает код первого. Без блокировки оба удалили бы
        «старые» коды, не видя друг друга, и остались бы два действующих кода.
        """
        cleaned = email.strip()
        validate_email(cleaned)
        user = self._user_repository.get_by_email(cleaned)
        if user is None or not self._user_repository.lock(user.id):
            return
        now = datetime.now(UTC)
        self._reset_token_repository.delete_expired(now)
        self._reset_token_repository.delete_by_user(user.id)
        token = secrets.token_hex(6)
        self._reset_token_repository.add(
            PasswordResetToken(0, user.id, self._hash_token(token), now + self._reset_token_ttl)
        )
        minutes = int(self._reset_token_ttl.total_seconds() // 60)
        message = (
            f"Здравствуйте, {user.login}!\n"
            f"Код для восстановления пароля: {token}\n"
            f"Код действует {minutes} мин. и может быть использован один раз.\n"
            "Если вы не запрашивали восстановление, просто проигнорируйте это письмо."
        )
        self._hooks.on_commit(
            lambda: self._email_sender.send(user.email, "Восстановление пароля", message)
        )
        self._event_log_service.record(user.id, EventType.PASSWORD_RESET_REQUESTED, user.login)

    def check_reset_token(self, token: str) -> User:
        """Вернуть владельца кода или выбросить InvalidResetTokenError."""
        key = self._hash_token(token.strip())
        entry = self._reset_token_repository.get_by_hash(key)
        if entry is None:
            raise InvalidResetTokenError()
        if datetime.now(UTC) > entry.expires_at:
            self._reset_token_repository.delete_by_hash(key)
            raise InvalidResetTokenError()
        # Владелец кода существует: код удаляется вместе с пользователем (`ON DELETE CASCADE`).
        return self._user_repository.get_by_id(entry.user_id)

    def reset_password_with_token(self, token: str, new_plain_password: str) -> None:
        """Задать новый пароль по коду из письма; код после этого перестаёт действовать.

        `check_reset_token` только отвечает на вопрос «похож ли код на действующий». Использует
        код `consume`: он проверяет срок и удаляет строку одним оператором, поэтому из двух
        одновременных вызовов с одним кодом пароль сменит только один. Пароль проверяется до
        списания: ошибка `DomainError` фиксирует транзакцию, и сгоревший код нельзя было бы
        использовать повторно с исправленным паролем.
        """
        self.check_reset_token(token)
        validate_password(new_plain_password)
        owner_id = self._reset_token_repository.consume(
            self._hash_token(token.strip()), datetime.now(UTC)
        )
        user = None if owner_id is None else self._user_repository.get_by_id(owner_id)
        if user is None:
            raise InvalidResetTokenError()
        user.password_hash = self._password_hasher.hash(new_plain_password)
        self._user_repository.update(user)
        self._event_log_service.record(user.id, EventType.PASSWORD_RESET, user.login)

    @staticmethod
    def _hash_token(token: str) -> str:
        """Хранить коды только в виде хеша, как и пароли."""
        return hashlib.sha256(token.encode("utf-8")).hexdigest()
