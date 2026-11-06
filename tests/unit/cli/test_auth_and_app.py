"""Юнит-тесты AuthController, CliApplication, сборки приложения и точки входа."""

from __future__ import annotations

import pytest

from src.bootstrap import ApplicationContext, build_application_context
from src.cli.app import CliApplication
from src.cli.auth_controller import RESET_COMMAND, AuthController
from src.configs.settings import AdminSettings
from src.domain.enums import AccountStatus, EventType, Role
from tests.fakes import ScriptedIO


def _code(mail) -> str:
    return mail.sent[-1][2].split("восстановления пароля: ")[1].split()[0]


class TestSignIn:
    def test_success(self, app, student, capsys):
        io = ScriptedIO(["student", "Password1!"])
        assert AuthController(app, io).sign_in() == student
        assert "Добро пожаловать, student" in capsys.readouterr().out
        assert io.pauses == 1

    def test_exit_returns_none(self, app):
        assert AuthController(app, ScriptedIO(["exit"])).sign_in() is None

    def test_exit_is_case_insensitive(self, app):
        assert AuthController(app, ScriptedIO(["EXIT"])).sign_in() is None

    @pytest.mark.parametrize("bad_login", ["", "  ", "ab", "bad login", "a" * 33])
    def test_bad_login_format_is_reasked(self, app, student, capsys, bad_login):
        io = ScriptedIO([bad_login, "student", "Password1!"])
        assert AuthController(app, io).sign_in() == student
        assert "Ошибка" in capsys.readouterr().out

    def test_empty_password_is_reasked(self, app, student, capsys):
        io = ScriptedIO(["student", "", "Password1!"])
        assert AuthController(app, io).sign_in() == student
        assert "введите пароль" in capsys.readouterr().out

    def test_wrong_password_returns_to_login_prompt(self, app, student, capsys):
        io = ScriptedIO(["student", "wrong", "student", "Password1!"])
        assert AuthController(app, io).sign_in() == student
        assert "Ошибка входа" in capsys.readouterr().out

    def test_blocked_user_sees_reason(self, app, student, capsys, user_repo):
        student.status = AccountStatus.BLOCKED
        user_repo.update(student)
        io = ScriptedIO(["student", "Password1!", "exit"])
        assert AuthController(app, io).sign_in() is None
        assert "заблокирована" in capsys.readouterr().out

    def test_sign_out_logs(self, app, student, admin):
        AuthController(app, ScriptedIO()).sign_out(student)
        events = app.event_log_service.list_events(admin)
        assert events[-1].event_type is EventType.USER_LOGGED_OUT


class TestPasswordResetFlow:
    def test_full_flow(self, app, student, mail, capsys):
        class Io(ScriptedIO):
            def read_line(self, prompt):
                if prompt.startswith("Код из письма"):
                    return _code(mail)
                return super().read_line(prompt)

        io = Io(
            [
                RESET_COMMAND,
                "student@example.org",
                "NewPassword1!",
                "NewPassword1!",
                "student",
                "NewPassword1!",
            ]
        )
        assert AuthController(app, io).sign_in().id == student.id
        assert "Пароль изменен" in capsys.readouterr().out

    def test_unknown_email_gives_same_message_and_then_invalid_code(self, app, mail, capsys):
        io = ScriptedIO([RESET_COMMAND, "ghost@example.org", "0", "exit"])
        AuthController(app, io).sign_in()
        out = capsys.readouterr().out
        assert "Если учетная запись с таким email существует" in out
        assert mail.sent == []

    def test_invalid_email_is_reasked(self, app, capsys):
        io = ScriptedIO([RESET_COMMAND, "bad", "0", "exit"])
        AuthController(app, io).sign_in()
        assert "✗" in capsys.readouterr().out

    def test_password_mismatch_is_reasked(self, app, student, mail, capsys):
        class Io(ScriptedIO):
            def read_line(self, prompt):
                if prompt.startswith("Код из письма"):
                    return _code(mail)
                return super().read_line(prompt)

        io = Io(
            [
                RESET_COMMAND,
                "student@example.org",
                "NewPassword1!",
                "different1",
                "NewPassword1!",
                "exit",
            ]
        )
        AuthController(app, io).sign_in()
        out = capsys.readouterr().out
        assert "✗" in out
        assert "Пароль изменен" in out

    def test_weak_new_password_is_reasked_with_reason(self, app, student, mail, capsys):
        class Io(ScriptedIO):
            def read_line(self, prompt):
                if prompt.startswith("Код из письма"):
                    return _code(mail)
                return super().read_line(prompt)

        answers = [RESET_COMMAND, "student@example.org", "alllowercase1", "NewPassword1!"]
        io = Io([*answers, "NewPassword1!", "student", "NewPassword1!"])
        assert AuthController(app, io).sign_in().id == student.id
        out = capsys.readouterr().out
        assert "слишком простой" in out
        assert "заглавной буквой" in "".join(io.prompts)

    def test_cancel_in_middle(self, app, capsys):
        io = ScriptedIO([RESET_COMMAND, "0", "exit"])
        assert AuthController(app, io).sign_in() is None
        assert "отменено" in capsys.readouterr().out

    def test_reset_command_is_case_insensitive(self, app, capsys):
        io = ScriptedIO(["/RESET", "0", "exit"])
        AuthController(app, io).sign_in()
        assert "Восстановление пароля" in capsys.readouterr().out


class TestCliApplication:
    def test_exit_immediately(self, app, capsys):
        CliApplication(app, ScriptedIO(["exit"])).run()

    def test_login_logout_cycle_logs_events(self, app, student, admin):
        io = ScriptedIO(["student", "Password1!", "0", "exit"])
        CliApplication(app, io).run()
        types = [e.event_type for e in app.event_log_service.list_events(admin)]
        assert types[-2:] == [EventType.USER_LOGGED_IN, EventType.USER_LOGGED_OUT]

    def test_menu_action_runs_and_pauses(self, app, student, seeded, capsys):
        io = ScriptedIO(["student", "Password1!", "1", "0", "exit"])
        CliApplication(app, io).run()
        assert "Линейные уравнения" in capsys.readouterr().out
        assert io.pauses >= 2

    def test_domain_errors_are_reported_not_raised(self, app, student, capsys, monkeypatch):
        from src.cli.student_controller import StudentController
        from src.domain.exceptions import MaterialNotFoundError

        def fail(self):
            raise MaterialNotFoundError(material_id=1)

        monkeypatch.setattr(StudentController, "_show_materials_flow", fail)
        io = ScriptedIO(["student", "Password1!", "1", "0", "exit"])
        CliApplication(app, io).run()
        assert "Ошибка: Материал с ID 1 не найден." in capsys.readouterr().out

    def test_cancelled_action_prints_message(self, app, student, seeded, capsys):
        io = ScriptedIO(["student", "Password1!", "3", "0", "0", "exit"])
        CliApplication(app, io).run()
        assert "Действие отменено" in capsys.readouterr().out

    def test_blocked_during_session_ends_session(self, app, student, admin, capsys):
        class Io(ScriptedIO):
            def read_line(self, prompt):
                if prompt.startswith("Выберите действие"):
                    app.user_management_service.set_blocked(admin, student.id, True)
                return super().read_line(prompt)

        io = Io(["student", "Password1!", "1", "exit"])
        CliApplication(app, io).run()
        assert "заблокирована" in capsys.readouterr().out

    def test_end_of_input_stops_gracefully(self, app, capsys):
        CliApplication(app, ScriptedIO([])).run()
        assert "Завершение работы" in capsys.readouterr().out

    def test_teacher_gets_teacher_menu(self, app, teacher, capsys):
        io = ScriptedIO(["teacher", "Password1!", "0", "exit"])
        CliApplication(app, io).run()
        assert "Меню преподавателя (teacher)" in capsys.readouterr().out

    def test_admin_gets_admin_menu(self, app, admin, capsys):
        admin.password_hash = "hashed:Password1!"
        io = ScriptedIO(["boss", "Password1!", "0", "exit"])
        CliApplication(app, io).run()
        assert "Меню администратора (boss)" in capsys.readouterr().out


class TestBootstrap:
    @pytest.fixture
    def settings(self):
        return AdminSettings("admin", "admin@example.org", "Admin12345!")

    def test_builds_all_services(self, tmp_path, settings, repository_factory):
        context = build_application_context(
            repository_factory, upload_root=tmp_path, admin=settings
        )
        assert isinstance(context, ApplicationContext)
        for name in ApplicationContext.__dataclass_fields__:
            assert getattr(context, name) is not None

    def test_admin_is_seeded_and_can_login(self, tmp_path, settings, repository_factory):
        context = build_application_context(
            repository_factory, upload_root=tmp_path, admin=settings
        )
        user = context.auth_service.login("admin", "Admin12345!")
        assert user.role is Role.ADMIN

    def test_admin_is_seeded_only_once(self, tmp_path, settings, repository_factory):
        first = build_application_context(repository_factory, upload_root=tmp_path, admin=settings)
        second = build_application_context(repository_factory, upload_root=tmp_path, admin=settings)
        admin = first.auth_service.login("admin", "Admin12345!")
        assert len(second.user_management_service.list_users(admin)) == 1

    def test_failed_login_alert_is_wired(self, tmp_path, settings, mail, repository_factory):
        from src.domain.exceptions import AuthenticationError

        context = build_application_context(
            repository_factory, email_sender=mail, upload_root=tmp_path, admin=settings
        )
        for _ in range(3):
            with pytest.raises(AuthenticationError):
                context.auth_service.login("admin", "bad-password")
        assert any(m[1] == "Подозрительные попытки входа" for m in mail.sent)

    @pytest.mark.parametrize("given", ["scope_only", "hooks_only"])
    def test_transaction_scope_and_hooks_come_together(
        self, tmp_path, settings, repository_factory, given
    ):
        """Письмо из открытой транзакции или транзакция без хуков — ошибка сборки, а не молчание."""
        from contextlib import nullcontext

        from src.services.transaction_hooks import ImmediateHooks

        arguments = (
            {"transaction_scope": nullcontext}
            if given == "scope_only"
            else {"transaction_hooks": ImmediateHooks()}
        )
        with pytest.raises(ValueError, match="только вместе"):
            build_application_context(
                repository_factory, upload_root=tmp_path, admin=settings, **arguments
            )

    def test_upload_root_is_created(self, tmp_path, settings, repository_factory):
        build_application_context(
            repository_factory, upload_root=tmp_path / "new" / "dir", admin=settings
        )
        assert (tmp_path / "new" / "dir").is_dir()

    def test_custom_repository_factory_is_used(self, tmp_path, settings, db_session):
        from src.repositories.factory import SQLAlchemyRepositoryFactory

        class Counting(SQLAlchemyRepositoryFactory):
            created = 0

            def create_user_repository(self):
                Counting.created += 1
                return super().create_user_repository()

        build_application_context(Counting(db_session), upload_root=tmp_path, admin=settings)
        assert Counting.created == 1

    def test_smtp_sender_is_chosen_when_configured(self, tmp_path, settings, monkeypatch):
        from src.bootstrap import _default_email_sender
        from src.configs.settings import SmtpSettings
        from src.notifications.smtp_sender import SmtpEmailSender

        monkeypatch.setattr(
            "src.bootstrap.load_smtp_settings", lambda: SmtpSettings("h", 25, "a@b.org")
        )
        assert isinstance(_default_email_sender(), SmtpEmailSender)

    def test_console_sender_is_default(self, monkeypatch):
        from src.bootstrap import _default_email_sender
        from src.notifications.email_sender import ConsoleEmailSender

        monkeypatch.setattr("src.bootstrap.load_smtp_settings", lambda: None)
        assert isinstance(_default_email_sender(), ConsoleEmailSender)
