"""Адаптер (Adapter): приводит `smtplib.SMTP` к интерфейсу `EmailSender`."""

from __future__ import annotations

import smtplib
from collections.abc import Callable
from email.message import EmailMessage

from src.configs.settings import SmtpSettings
from src.notifications.email_sender import EmailSender

SmtpFactory = Callable[[str, int], smtplib.SMTP]


class SmtpEmailSender(EmailSender):
    """Отправляет письма через настоящий SMTP-сервер.

    Сервисы по-прежнему вызывают `send(адрес, тема, текст)`; адаптер превращает вызов
    в `EmailMessage` и последовательность команд `smtplib` (STARTTLS, логин, отправка).
    `smtp_factory` позволяет подменить соединение в тестах.
    """

    def __init__(self, settings: SmtpSettings, smtp_factory: SmtpFactory = smtplib.SMTP) -> None:
        """Принять настройки сервера и фабрику SMTP-соединений."""
        self._settings = settings
        self._smtp_factory = smtp_factory

    def send(self, to_address: str, subject: str, body: str) -> None:
        """Собрать письмо и отправить его через SMTP-сервер."""
        message = EmailMessage()
        message["From"] = self._settings.sender
        message["To"] = to_address
        message["Subject"] = subject
        message.set_content(body)
        with self._smtp_factory(self._settings.host, self._settings.port) as smtp:
            if self._settings.use_starttls:
                smtp.starttls()
            if self._settings.username:
                smtp.login(self._settings.username, self._settings.password)
            smtp.send_message(message)
