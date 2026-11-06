"""Наблюдатель (Observer): письмо владельцу учётной записи после серии неудачных входов."""

from __future__ import annotations

from src.domain.enums import EventType
from src.domain.models import Event
from src.notifications.email_sender import EmailSender
from src.repositories.interfaces import FailedLoginRepository, UserRepository
from src.services.event_log_service import EventObserver
from src.services.transaction_hooks import ImmediateHooks, TransactionHooks

DEFAULT_FAILED_LOGIN_THRESHOLD = 3


class FailedLoginAlertObserver(EventObserver):
    """Считает подряд неудачные попытки входа и предупреждает владельца по email.

    Успешный вход обнуляет счётчик. Для несуществующих логинов письмо не отправляется.
    Счётчик хранится в БД, а не в памяти процесса: подбор пароля, распределённый между
    несколькими процессами или прерванный перезапуском, всё равно будет замечен.
    """

    def __init__(
        self,
        user_repository: UserRepository,
        failed_login_repository: FailedLoginRepository,
        email_sender: EmailSender,
        threshold: int = DEFAULT_FAILED_LOGIN_THRESHOLD,
        transaction_hooks: TransactionHooks | None = None,
    ) -> None:
        """Принять хранилища, отправщик писем и число попыток до оповещения.

        `transaction_hooks` откладывает отправку письма до фиксации транзакции входа.
        """
        self._user_repository = user_repository
        self._failed_login_repository = failed_login_repository
        self._email_sender = email_sender
        self._threshold = threshold
        self._hooks = transaction_hooks or ImmediateHooks()

    def on_event(self, event: Event) -> None:
        """Обработать события входа; остальные игнорировать."""
        key = event.target
        if event.event_type is EventType.USER_LOGGED_IN:
            self._failed_login_repository.reset(key)
        elif (
            event.event_type is EventType.USER_LOGIN_FAILED
            and self._failed_login_repository.register(key) >= self._threshold
        ):
            self._failed_login_repository.reset(key)
            self._send_alert(event.target)

    def _send_alert(self, login: str) -> None:
        """Отправить предупреждение владельцу логина, если такой пользователь есть."""
        user = self._user_repository.get_by_login(login)
        if user is None:
            return
        message = (
            f"Здравствуйте, {user.login}!\n"
            f"В вашу учётную запись {self._threshold} раза подряд не удалось войти.\n"
            "Если это были не вы, смените пароль."
        )
        # Письмо уходит после фиксации: запись о попытках и счётчик уже в базе, а откат
        # транзакции не оставит письма о событии, которого «не было».
        self._hooks.on_commit(
            lambda: self._email_sender.send(user.email, "Подозрительные попытки входа", message)
        )
