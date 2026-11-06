"""Состояние приложения лежит в БД, а не в памяти процесса.

Каждый `build_app()` — отдельный «процесс»: свой контекст, свои сервисы, свой менеджер
транзакций, но общая БД. Так работают несколько воркеров веб-приложения и так выглядит
перезапуск: код, счётчик и история правок не должны пропадать.
"""

from __future__ import annotations

import pytest

from src.domain.enums import Role
from src.domain.exceptions import AuthenticationError, InvalidResetTokenError


def _code(mail) -> str:
    return mail.sent[-1][2].split("восстановления пароля: ")[1].split()[0]


@pytest.fixture
def admin_of(build_app):
    """Администратор, созданный первым «процессом» (его же засевает bootstrap)."""
    first = build_app()
    admin = first.context.auth_service.login("admin", "Admin12345!")
    return first, admin


class TestPasswordResetAcrossProcesses:
    def test_code_requested_in_one_process_works_in_another(self, build_app, admin_of):
        first, admin = admin_of
        first.context.user_management_service.create_user(
            admin, "bob", "bob@example.org", "Password123!", Role.STUDENT
        )
        first.context.auth_service.request_password_reset("bob@example.org")
        code = _code(first.mail)

        second = build_app()  # другой воркер / после перезапуска
        second.context.auth_service.reset_password_with_token(code, "NewPassword1!")
        assert second.context.auth_service.login("bob", "NewPassword1!").login == "bob"

    def test_code_is_single_use_across_processes(self, build_app, admin_of):
        first, admin = admin_of
        first.context.user_management_service.create_user(
            admin, "bob", "bob@example.org", "Password123!", Role.STUDENT
        )
        first.context.auth_service.request_password_reset("bob@example.org")
        code = _code(first.mail)
        build_app().context.auth_service.reset_password_with_token(code, "NewPassword1!")
        with pytest.raises(InvalidResetTokenError):
            first.context.auth_service.check_reset_token(code)

    def test_new_request_in_other_process_revokes_old_code(self, build_app, admin_of):
        first, admin = admin_of
        first.context.user_management_service.create_user(
            admin, "bob", "bob@example.org", "Password123!", Role.STUDENT
        )
        first.context.auth_service.request_password_reset("bob@example.org")
        old_code = _code(first.mail)
        second = build_app()
        second.context.auth_service.request_password_reset("bob@example.org")
        with pytest.raises(InvalidResetTokenError):
            second.context.auth_service.check_reset_token(old_code)
        assert second.context.auth_service.check_reset_token(_code(second.mail)).login == "bob"


class TestFailedLoginsAcrossProcesses:
    def test_attempts_are_counted_across_processes(self, build_app, admin_of):
        first, admin = admin_of
        first.context.user_management_service.create_user(
            admin, "bob", "bob@example.org", "Password123!", Role.STUDENT
        )
        second, third = build_app(), build_app()
        for process in (first, second):
            with pytest.raises(AuthenticationError):
                process.context.auth_service.login("bob", "wrong")
        assert first.mail.sent == [] and second.mail.sent == []
        with pytest.raises(AuthenticationError):
            third.context.auth_service.login("bob", "wrong")  # третья попытка подряд
        assert [m[0] for m in third.mail.sent] == ["bob@example.org"]

    def test_success_in_one_process_resets_counter_for_all(self, build_app, admin_of):
        first, admin = admin_of
        first.context.user_management_service.create_user(
            admin, "bob", "bob@example.org", "Password123!", Role.STUDENT
        )
        second = build_app()
        for _ in range(2):
            with pytest.raises(AuthenticationError):
                first.context.auth_service.login("bob", "wrong")
        second.context.auth_service.login("bob", "Password123!")
        with pytest.raises(AuthenticationError):
            first.context.auth_service.login("bob", "wrong")
        assert first.mail.sent == []  # счётчик начал с нуля

    def test_attempts_survive_restart(self, build_app, admin_of):
        first, admin = admin_of
        first.context.user_management_service.create_user(
            admin, "bob", "bob@example.org", "Password123!", Role.STUDENT
        )
        for _ in range(2):
            with pytest.raises(AuthenticationError):
                first.context.auth_service.login("bob", "wrong")
        restarted = build_app()
        with pytest.raises(AuthenticationError):
            restarted.context.auth_service.login("bob", "wrong")
        assert len(restarted.mail.sent) == 1


class TestEditHistoryAcrossProcesses:
    @pytest.fixture
    def material(self, admin_of, tmp_path):
        first, admin = admin_of
        service = first.context.catalog_service
        discipline = service.create_discipline(admin, "Математика")
        topic = service.create_topic(admin, "Алгебра", discipline.id)
        source = tmp_path / "a.pdf"
        source.write_bytes(b"x")
        created = first.context.material_service.create_material(
            admin, "Лекция", "описание", discipline.id, topic.id, source
        )
        return first, admin, created

    def test_edit_made_in_one_process_is_undone_in_another(self, build_app, material):
        first, admin, created = material
        first.context.material_service.edit_material(admin, created.id, title="Новая")
        second = build_app()
        assert second.context.material_service.can_undo(created.id)
        second.context.material_service.undo_last_edit(admin, created.id)
        assert first.context.material_service.get_material(created.id).title == "Лекция"

    def test_history_survives_restart_and_is_consumed_once(self, build_app, material):
        first, admin, created = material
        first.context.material_service.edit_material(admin, created.id, title="Новая")
        restarted = build_app()
        restarted.context.material_service.undo_last_edit(admin, created.id)
        assert not build_app().context.material_service.can_undo(created.id)

    def test_deleting_material_removes_its_history(self, build_app, material, session_factory):
        from sqlalchemy import func, select

        from src.database.models import MaterialRevisionEntity

        first, admin, created = material
        first.context.material_service.edit_material(admin, created.id, title="Новая")
        first.context.material_service.delete_material(admin, created.id)
        with session_factory() as session:
            count = session.scalar(select(func.count()).select_from(MaterialRevisionEntity))
        assert count == 0
