"""Файлы и письма следуют за исходом транзакции, а не опережают его.

Откат не должен оставлять письмо, которое уже ушло, или файл, которого уже нет, а открытая
транзакция не должна держать соединение с БД на время отправки письма.
"""

from __future__ import annotations

import logging

import pytest
from sqlalchemy import func, select, text

from src.database.models import PasswordResetTokenEntity
from src.domain.exceptions import AuthenticationError
from tests.integration.db.conftest import make_catalog
from tests.integration.db.helpers import Gate, Worker, after, real


def _stored_files(tmp_path) -> list[str]:
    return sorted(path.name for path in (tmp_path / "uploads").iterdir())


def _boom() -> None:
    raise RuntimeError("сбой после записи в БД")


def _token_count(session_factory) -> int:
    with session_factory() as session:
        return session.scalar(select(func.count()).select_from(PasswordResetTokenEntity))


def _hold_before_commit(app, service_name: str) -> Gate:
    """Удержать операцию сервиса после записи в журнал, то есть перед самой фиксацией."""
    gate = Gate()
    after(real(getattr(app.context, service_name))._event_log_service, "record", gate.hold)
    return gate


class TestFilesFollowTheTransaction:
    def test_deleted_file_stays_until_the_commit(self, apps, material, tmp_path):
        first, _ = apps
        gate = _hold_before_commit(first, "material_service")
        deleter = Worker(
            lambda: first.context.material_service.delete_material(first.admin, material.id)
        )
        deleter.start()
        assert gate.entered.wait(15)
        assert len(_stored_files(tmp_path)) == 1  # строка удалена, но не зафиксирована
        gate.release()
        deleter.wait()
        assert deleter.error is None
        assert _stored_files(tmp_path) == []

    def test_rolled_back_delete_keeps_the_file(self, apps, material, tmp_path):
        first, _ = apps
        after(real(first.context.material_service)._event_log_service, "record", _boom)
        with pytest.raises(RuntimeError):
            first.context.material_service.delete_material(first.admin, material.id)
        assert first.context.material_service.get_material(material.id).title == "A"
        assert len(_stored_files(tmp_path)) == 1  # строка на месте, значит, на месте и файл

    def test_copy_of_a_rolled_back_upload_is_removed(self, apps, tmp_path):
        first, _ = apps
        discipline, topic = make_catalog(first)
        source = tmp_path / "lecture.pdf"
        source.write_bytes(b"12345")
        after(real(first.context.material_service)._event_log_service, "record", _boom)
        with pytest.raises(RuntimeError):
            first.context.material_service.create_material(
                first.admin, "A", "описание", discipline.id, topic.id, source
            )
        assert first.context.material_service.list_materials() == []
        assert _stored_files(tmp_path) == []  # без строки в БД файл-«сирота» не остался

    def test_committed_upload_keeps_its_copy(self, apps, material, tmp_path):
        assert len(_stored_files(tmp_path)) == 1

    def test_upload_of_a_deleted_account_leaves_no_copy(self, apps, tmp_path):
        """Автора удалили посреди загрузки: операция откатывается, копия убирается."""
        from src.domain.enums import Role
        from src.domain.exceptions import AccountDeletedError

        first, second = apps
        teacher = first.context.user_management_service.create_user(
            first.admin, "teacher1", "t@example.org", "Password123!", Role.TEACHER
        )
        discipline, topic = make_catalog(first)
        source = tmp_path / "lecture.pdf"
        source.write_bytes(b"12345")
        second.context.user_management_service.delete_user(second.admin, teacher.id)
        with pytest.raises(AccountDeletedError):
            first.context.material_service.create_material(
                teacher, "A", "описание", discipline.id, topic.id, source
            )
        assert _stored_files(tmp_path) == []


class TestMailFollowsTheTransaction:
    def test_reset_code_mail_waits_for_the_commit(self, apps, bob):
        first, _ = apps
        gate = _hold_before_commit(first, "auth_service")
        request = Worker(lambda: first.context.auth_service.request_password_reset(bob.email))
        request.start()
        assert gate.entered.wait(15)
        assert first.mail.sent == []  # код ещё не зафиксирован, письмо с ним рано
        gate.release()
        request.wait()
        assert request.error is None
        assert [to for to, _, _ in first.mail.sent] == [bob.email]

    def test_rolled_back_request_sends_no_mail(self, apps, bob, session_factory):
        first, _ = apps
        after(real(first.context.auth_service)._event_log_service, "record", _boom)
        with pytest.raises(RuntimeError):
            first.context.auth_service.request_password_reset(bob.email)
        assert first.mail.sent == []
        assert _token_count(session_factory) == 0

    def test_alert_mail_waits_for_the_commit(self, apps, bob):
        first, _ = apps
        for _ in range(2):
            with pytest.raises(AuthenticationError):
                first.context.auth_service.login("bob", "wrong")
        gate = _hold_before_commit(first, "auth_service")
        attempt = Worker(lambda: first.context.auth_service.login("bob", "wrong"))
        attempt.start()
        assert gate.entered.wait(15)
        assert first.mail.sent == []
        gate.release()
        attempt.wait()
        assert isinstance(attempt.error, AuthenticationError)
        assert [subject for _, subject, _ in first.mail.sent] == ["Подозрительные попытки входа"]

    def test_connection_is_not_held_open_while_the_mail_is_sent(self, apps, bob, session_factory):
        first, _ = apps
        idle_in_transaction: list[int] = []

        class Probe:
            def send(self, *args):
                with session_factory() as session:
                    idle_in_transaction.append(
                        session.scalar(
                            text(
                                "SELECT count(*) FROM pg_stat_activity "
                                "WHERE datname = current_database() "
                                "AND state LIKE 'idle in transaction%'"
                            )
                        )
                    )

        real(first.context.auth_service)._email_sender = Probe()
        first.context.auth_service.request_password_reset(bob.email)
        assert idle_in_transaction == [0]

    def test_failed_delivery_does_not_undo_the_operation(self, apps, bob, session_factory, caplog):
        first, _ = apps

        class Broken:
            def send(self, *args):
                raise ConnectionError("SMTP недоступен")

        real(first.context.auth_service)._email_sender = Broken()
        with caplog.at_level(logging.ERROR, logger="src.database.transaction"):
            first.context.auth_service.request_password_reset(bob.email)  # без ошибки
        assert _token_count(session_factory) == 1  # код выдан, транзакция зафиксирована
        assert "SMTP недоступен" in caplog.text  # сбой не потерян: он в журнале
