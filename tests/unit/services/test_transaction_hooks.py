"""Сервисы откладывают письма и операции с файлами до исхода транзакции."""

from __future__ import annotations

import pytest

from src.domain.enums import EventType, Role
from src.domain.exceptions import AuthenticationError
from src.domain.models import Discipline, Topic
from src.notifications.login_alerts import FailedLoginAlertObserver
from src.services.auth_service import AuthService
from src.services.material_service import MaterialService
from src.services.transaction_hooks import ImmediateHooks
from tests.fakes import RecordingHooks, make_event, make_user


class TestImmediateHooks:
    def test_commit_action_runs_at_once(self):
        ran = []
        ImmediateHooks().on_commit(lambda: ran.append("письмо"))
        assert ran == ["письмо"]

    def test_rollback_action_is_dropped(self):
        ran = []
        ImmediateHooks().on_rollback(lambda: ran.append("уборка"))
        assert ran == []


@pytest.fixture
def hooks() -> RecordingHooks:
    return RecordingHooks()


class TestPasswordResetMail:
    @pytest.fixture
    def service(self, user_repo, reset_token_repo, hasher, event_log, email_sender, hooks):
        return AuthService(
            user_repo, reset_token_repo, hasher, event_log, email_sender, transaction_hooks=hooks
        )

    @pytest.fixture(autouse=True)
    def bob(self, user_repo):
        return user_repo.add(make_user(0, "bob", email="bob@example.org"))

    def test_mail_is_held_until_commit(self, service, email_sender, hooks):
        service.request_password_reset("bob@example.org")
        assert email_sender.sent == []
        hooks.commit()
        assert [to for to, _, _ in email_sender.sent] == ["bob@example.org"]

    def test_rollback_sends_nothing(self, service, email_sender, hooks):
        service.request_password_reset("bob@example.org")
        hooks.rollback()
        assert email_sender.sent == []

    def test_unknown_address_registers_nothing(self, service, hooks):
        service.request_password_reset("ghost@example.org")
        assert hooks.commit_actions == []


class TestFailedLoginAlertMail:
    def test_alert_is_held_until_commit(self, user_repo, failed_login_repo, email_sender, hooks):
        user_repo.add(make_user(0, "bob", email="bob@example.org"))
        observer = FailedLoginAlertObserver(
            user_repo, failed_login_repo, email_sender, threshold=1, transaction_hooks=hooks
        )
        observer.on_event(make_event(EventType.USER_LOGIN_FAILED, "bob", None))
        assert email_sender.sent == []
        hooks.commit()
        assert len(email_sender.sent) == 1


class TestMaterialFiles:
    @pytest.fixture
    def service(
        self,
        material_repo,
        discipline_repo,
        topic_repo,
        revision_repo,
        event_log,
        file_storage,
        hooks,
    ):
        return MaterialService(
            material_repo,
            discipline_repo,
            topic_repo,
            revision_repo,
            event_log,
            file_storage,
            transaction_hooks=hooks,
        )

    @pytest.fixture
    def created(self, service, teacher_user, discipline_repo, topic_repo, tmp_path):
        discipline = discipline_repo.add(Discipline(0, "Математика"))
        topic = topic_repo.add(Topic(0, "Алгебра", discipline.id))
        source = tmp_path / "lecture.pdf"
        source.write_bytes(b"12345")
        return service.create_material(teacher_user, "Лекция", "", discipline.id, topic.id, source)

    def test_upload_is_undone_only_by_a_rollback(self, created, file_storage, hooks):
        assert len(file_storage.files) == 1
        hooks.rollback()
        assert file_storage.files == {}  # копия убрана вместе с откатом строки

    def test_committed_upload_keeps_its_file(self, created, file_storage, hooks):
        hooks.commit()
        assert len(file_storage.files) == 1
        assert file_storage.deleted == []

    def test_file_is_deleted_only_after_commit(
        self, service, created, teacher_user, file_storage, hooks
    ):
        hooks.commit()  # закончилась загрузка
        service.delete_material(teacher_user, created.id)
        assert file_storage.deleted == []  # строка удалена, но файл ещё на месте
        hooks.commit()
        assert file_storage.deleted == [created.storage_path]

    def test_rolled_back_delete_keeps_the_file(
        self, service, created, teacher_user, file_storage, hooks
    ):
        hooks.commit()
        service.delete_material(teacher_user, created.id)
        hooks.rollback()
        assert file_storage.deleted == []
        assert len(file_storage.files) == 1


def test_rejected_login_still_raises_after_mail_is_deferred(
    user_repo, reset_token_repo, hasher, event_log, email_sender, hooks
):
    """Отложенное письмо не меняет, что именно видит пользователь при неверном пароле."""
    service = AuthService(
        user_repo, reset_token_repo, hasher, event_log, email_sender, transaction_hooks=hooks
    )
    user_repo.add(make_user(0, "bob", role=Role.STUDENT))
    with pytest.raises(AuthenticationError):
        service.login("bob", "Wrong-password1")
