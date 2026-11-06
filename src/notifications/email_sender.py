from __future__ import annotations

import logging
from abc import ABC, abstractmethod


class EmailSender(ABC):
    """Контракт отправки писем пользователям."""

    @abstractmethod
    def send(self, to_address: str, subject: str, body: str) -> None:
        """Отправить письмо на указанный адрес."""


class ConsoleEmailSender(EmailSender):
    """Имитация отправки письма выводом в консоль."""

    def send(self, to_address: str, subject: str, body: str) -> None:
        """Показать письмо в консоли так, как его увидел бы получатель."""
        print()
        print(f"[ПОЧТА, имитация отправки] Кому: {to_address}")
        print(f"[ПОЧТА, имитация отправки] Тема: {subject}")
        for line in body.splitlines():
            print(f"[ПОЧТА, имитация отправки] {line}")


class RetryingEmailSender(EmailSender):
    """Декоратор (Decorator): повторяет отправку, если обёрнутый отправщик выбросил ошибку.

    Реализует тот же интерфейс `EmailSender`, поэтому подставляется вместо любого
    отправщика без изменения `AuthService`. После исчерпания попыток исключение
    пробрасывается дальше.
    """

    def __init__(self, inner: EmailSender, attempts: int = 3) -> None:
        """Принять обёрнутого отправщика и общее число попыток (не меньше одной)."""
        self._inner = inner
        self._attempts = max(1, attempts)

    def send(self, to_address: str, subject: str, body: str) -> None:
        """Отправить письмо, повторяя попытку при ошибке."""
        for attempt in range(1, self._attempts + 1):
            try:
                self._inner.send(to_address, subject, body)
            except Exception:
                if attempt == self._attempts:
                    raise
            else:
                return


class LoggingEmailSender(EmailSender):
    """Декоратор (Decorator): пишет в стандартный лог факт отправки, не раскрывая текст письма."""

    def __init__(self, inner: EmailSender, logger: logging.Logger | None = None) -> None:
        """Принять обёрнутого отправщика и логгер (по умолчанию логгер модуля)."""
        self._inner = inner
        self._logger = logger or logging.getLogger(__name__)

    def send(self, to_address: str, subject: str, body: str) -> None:
        """Отправить письмо и записать результат в лог."""
        try:
            self._inner.send(to_address, subject, body)
        except Exception:
            self._logger.exception("Не удалось отправить письмо «%s» на %s", subject, to_address)
            raise
        self._logger.info("Письмо «%s» отправлено на %s", subject, to_address)
