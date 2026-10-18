from __future__ import annotations

from abc import ABC, abstractmethod


class EmailSender(ABC):
    """Контракт отправки писем пользователям."""

    @abstractmethod
    def send(self, to_address: str, subject: str, body: str) -> None:
        """Отправить письмо на указанный адрес."""


class ConsoleEmailSender(EmailSender):

    def send(self, to_address: str, subject: str, body: str) -> None:
        """Показать письмо в консоли так, как его увидел бы получатель."""
        print()
        print(f"[ПОЧТА, имитация отправки] Кому: {to_address}")
        print(f"[ПОЧТА, имитация отправки] Тема: {subject}")
        for line in body.splitlines():
            print(f"[ПОЧТА, имитация отправки] {line}")
