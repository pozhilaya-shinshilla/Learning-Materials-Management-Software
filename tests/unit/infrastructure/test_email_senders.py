"""Юнит-тесты отправщиков писем: консольный, декораторы и SMTP-адаптер."""

from __future__ import annotations

import logging

import pytest

from src.configs.settings import SmtpSettings
from src.notifications.email_sender import (
    ConsoleEmailSender,
    EmailSender,
    LoggingEmailSender,
    RetryingEmailSender,
)
from src.notifications.smtp_sender import SmtpEmailSender
from tests.fakes import RecordingEmailSender


class FlakySender(EmailSender):
    def __init__(self, failures: int) -> None:
        self.failures = failures
        self.calls = 0

    def send(self, to_address: str, subject: str, body: str) -> None:
        self.calls += 1
        if self.calls <= self.failures:
            raise ConnectionError("down")


class TestConsoleEmailSender:
    def test_prints_recipient_subject_and_every_line(self, capsys):
        ConsoleEmailSender().send("a@b.c", "Тема", "строка 1\nстрока 2")
        out = capsys.readouterr().out
        assert "Кому: a@b.c" in out
        assert "Тема: Тема" in out
        assert "строка 1" in out
        assert "строка 2" in out

    def test_empty_body(self, capsys):
        ConsoleEmailSender().send("a@b.c", "Тема", "")
        assert "Кому: a@b.c" in capsys.readouterr().out


class TestRetryingEmailSender:
    def test_success_on_first_attempt_calls_once(self):
        inner = FlakySender(0)
        RetryingEmailSender(inner, attempts=3).send("a@b.c", "s", "b")
        assert inner.calls == 1

    def test_succeeds_on_last_allowed_attempt(self):
        inner = FlakySender(2)
        RetryingEmailSender(inner, attempts=3).send("a@b.c", "s", "b")
        assert inner.calls == 3

    def test_fails_when_one_attempt_short(self):
        inner = FlakySender(3)
        with pytest.raises(ConnectionError):
            RetryingEmailSender(inner, attempts=3).send("a@b.c", "s", "b")
        assert inner.calls == 3

    @pytest.mark.parametrize("attempts", [0, -1, -100])
    def test_non_positive_attempts_still_try_once(self, attempts):
        inner = FlakySender(0)
        RetryingEmailSender(inner, attempts=attempts).send("a@b.c", "s", "b")
        assert inner.calls == 1

    def test_single_attempt_does_not_retry(self):
        inner = FlakySender(1)
        with pytest.raises(ConnectionError):
            RetryingEmailSender(inner, attempts=1).send("a@b.c", "s", "b")
        assert inner.calls == 1

    def test_delivery_arguments_are_passed_through(self):
        inner = RecordingEmailSender()
        RetryingEmailSender(inner).send("a@b.c", "s", "b")
        assert inner.sent == [("a@b.c", "s", "b")]


class TestLoggingEmailSender:
    def test_logs_success_without_body(self, caplog):
        with caplog.at_level(logging.INFO):
            LoggingEmailSender(RecordingEmailSender()).send("a@b.c", "Тема", "секрет")
        assert "Тема" in caplog.text
        assert "a@b.c" in caplog.text
        assert "секрет" not in caplog.text

    def test_logs_failure_and_reraises(self, caplog):
        with caplog.at_level(logging.ERROR), pytest.raises(ConnectionError):
            LoggingEmailSender(FlakySender(1)).send("a@b.c", "Тема", "секрет")
        assert "Не удалось отправить" in caplog.text
        assert "секрет" not in caplog.text.replace("Traceback", "")

    def test_message_is_delivered(self):
        inner = RecordingEmailSender()
        LoggingEmailSender(inner).send("a@b.c", "s", "b")
        assert inner.sent == [("a@b.c", "s", "b")]


class FakeSmtp:
    created: list[FakeSmtp] = []

    def __init__(self, host, port):
        self.host, self.port = host, port
        self.calls: list[object] = []
        self.message = None
        FakeSmtp.created.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.calls.append("closed")
        return False

    def starttls(self):
        self.calls.append("starttls")

    def login(self, user, password):
        self.calls.append(("login", user, password))

    def send_message(self, message):
        self.calls.append("send")
        self.message = message


@pytest.fixture(autouse=True)
def _reset_fake_smtp():
    FakeSmtp.created.clear()


class TestSmtpEmailSender:
    def _send(self, **overrides):
        settings = SmtpSettings(
            **{
                "host": "smtp.test",
                "port": 2525,
                "sender": "noreply@test.org",
                "username": "user",
                "password": "pw",
                "use_starttls": True,
                **overrides,
            }
        )
        SmtpEmailSender(settings, FakeSmtp).send("to@test.org", "Тема", "Текст письма")
        return FakeSmtp.created[0]

    def test_connects_to_configured_host_and_port(self):
        smtp = self._send()
        assert (smtp.host, smtp.port) == ("smtp.test", 2525)

    def test_full_sequence_with_tls_and_login(self):
        assert self._send().calls == ["starttls", ("login", "user", "pw"), "send", "closed"]

    def test_without_tls(self):
        assert "starttls" not in self._send(use_starttls=False).calls

    def test_without_username_no_login(self):
        calls = self._send(username="", password="").calls
        assert not any(isinstance(call, tuple) for call in calls)

    def test_message_headers_and_body(self):
        message = self._send().message
        assert message["From"] == "noreply@test.org"
        assert message["To"] == "to@test.org"
        assert message["Subject"] == "Тема"
        assert "Текст письма" in message.get_content()

    def test_connection_is_closed_even_if_send_fails(self):
        class Failing(FakeSmtp):
            def send_message(self, message):
                raise OSError("boom")

        settings = SmtpSettings("h", 25, "a@b.org")
        with pytest.raises(OSError):
            SmtpEmailSender(settings, Failing).send("to@test.org", "s", "b")
        assert "closed" in FakeSmtp.created[0].calls
