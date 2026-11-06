"""Юнит-тесты редких ветвей контроллеров: пустые состояния и ошибки файловой системы."""

from __future__ import annotations

import pytest

from src.bootstrap import _seed_admin
from src.cli.auth_controller import RESET_COMMAND, AuthController
from src.cli.picker import Picker
from src.cli.student_controller import StudentController
from src.cli.teacher_controller import TeacherController
from src.configs.settings import AdminSettings
from src.domain.enums import Role
from src.domain.exceptions import TopicNameRequiredError
from tests.fakes import PlainPasswordHasher, ScriptedIO


def _student(app, student, answers=()):
    return StudentController(app, ScriptedIO(answers), student)


def _teacher(app, teacher, answers=()):
    return TeacherController(app, ScriptedIO(answers), teacher)


class TestEmptyCatalogMessages:
    @pytest.mark.parametrize(
        "flow", ["_download_flow", "_add_favorite_flow", "_material_details_flow", "_search_flow"]
    )
    def test_student_sees_hint_for_empty_catalog(self, app, student, capsys, flow):
        getattr(_student(app, student), flow)()
        assert "Каталог материалов пока пуст" in capsys.readouterr().out

    def test_teacher_edit_and_delete_in_empty_catalog(self, app, teacher, capsys):
        controller = _teacher(app, teacher)
        controller._edit_material_flow()
        controller._delete_material_flow()
        assert capsys.readouterr().out.count("Каталог материалов пуст") == 2

    def test_teacher_delete_when_only_foreign_materials(self, app, make_account, seeded, capsys):
        other = make_account("other", Role.TEACHER)
        _teacher(app, other)._delete_material_flow()
        assert "можно удалять только свои" in capsys.readouterr().out


class TestSearchWithEmptyDiscipline:
    def test_student_hint(self, app, student, teacher, seeded, capsys):
        app.catalog_service.create_discipline(teacher, "Физика")
        answers = ["", "физика", "", "", "", ""]
        _student(app, student, answers)._search_flow()
        assert "В дисциплине «Физика» пока нет тем." in capsys.readouterr().out

    def test_teacher_hint_suggests_adding_topic(self, app, teacher, seeded, capsys):
        app.catalog_service.create_discipline(teacher, "Физика")
        answers = ["", "физика", "", "", "", ""]
        _teacher(app, teacher, answers)._search_flow()
        assert "Сначала добавьте тему" in capsys.readouterr().out


class TestFileSystemFailures:
    def test_copy_failure_is_reported(self, app, student, seeded, tmp_path, capsys):
        _, _, material = seeded
        target = tmp_path / "d"
        (target / "lecture.pdf").mkdir(parents=True)
        controller = _student(app, student, [str(material.id), str(target), "y"])
        controller._download_flow()
        assert "Не удалось сохранить файл" in capsys.readouterr().out

    def test_failed_download_is_not_logged(self, app, student, admin, seeded, tmp_path):
        _, _, material = seeded
        target = tmp_path / "d"
        (target / "lecture.pdf").mkdir(parents=True)
        _student(app, student, [str(material.id), str(target), "y"])._download_flow()
        types = [e.event_type.value for e in app.event_log_service.list_events(admin)]
        assert "material_downloaded" not in types

    def test_unavailable_destination_is_reasked(self, app, student, seeded, tmp_path, capsys):
        _, _, material = seeded
        blocker = tmp_path / "file.txt"
        blocker.write_text("x")
        answers = [str(material.id), str(blocker / "sub"), str(tmp_path / "ok")]
        _student(app, student, answers)._download_flow()
        assert "✗" in capsys.readouterr().out
        assert (tmp_path / "ok" / "lecture.pdf").exists()

    def test_empty_destination_means_current_directory(
        self, app, student, seeded, tmp_path, monkeypatch
    ):
        _, _, material = seeded
        workdir = tmp_path / "work"
        workdir.mkdir()
        monkeypatch.chdir(workdir)
        _student(app, student, [str(material.id), ""])._download_flow()
        assert (workdir / "lecture.pdf").read_bytes() == b"content"


class TestTeacherEditBranches:
    def test_change_discipline_with_topic(self, app, teacher, seeded):
        _, _, material = seeded
        physics = app.catalog_service.create_discipline(teacher, "Физика")
        mechanics = app.catalog_service.create_topic(teacher, "Механика", physics.id)
        answers = [str(material.id), "", "", "физика", "механика"]
        _teacher(app, teacher, answers)._edit_material_flow()
        edited = app.material_service.get_material(material.id)
        assert (edited.discipline_id, edited.topic_id) == (physics.id, mechanics.id)

    def test_existing_topics_are_listed_when_adding_topic(self, app, teacher, seeded, capsys):
        answers = ["математика", "Тригонометрия"]
        _teacher(app, teacher, answers)._create_topic_flow()
        assert "Уже есть темы: Алгебра, Геометрия" in capsys.readouterr().out

    def test_existing_disciplines_are_listed(self, app, teacher, seeded, capsys):
        _teacher(app, teacher, ["Физика"])._create_discipline_flow()
        assert "Уже существуют: Математика" in capsys.readouterr().out


class TestResetFlowDomainError:
    def test_error_after_prompts_is_reported(self, app, student, mail, admin, capsys):
        class Io(ScriptedIO):
            def read_line(self, prompt):
                if prompt.startswith("Код из письма"):
                    return mail.sent[-1][2].split("восстановления пароля: ")[1].split()[0]
                if prompt.startswith("Повторите пароль"):
                    app.user_management_service.delete_user(admin, student.id)
                return super().read_line(prompt)

        io = Io([RESET_COMMAND, "student@example.org", "NewPassword1!", "NewPassword1!", "exit"])
        AuthController(app, io).sign_in()
        assert "Ошибка:" in capsys.readouterr().out


def test_picker_blank_topic_name():
    with pytest.raises(TopicNameRequiredError):
        Picker._parse_topic("   ", {})


class TestSeedAdmin:
    def test_does_not_overwrite_existing_admin(self, user_repo):
        repo = user_repo
        hasher = PlainPasswordHasher()
        settings = AdminSettings("admin", "admin@example.org", "FirstPass1!")
        _seed_admin(repo, hasher, settings)
        _seed_admin(repo, hasher, AdminSettings("admin", "other@example.org", "SecondPass1!"))
        users = repo.list_all()
        assert len(users) == 1
        assert users[0].password_hash == hasher.hash("FirstPass1!")

    def test_seeded_user_is_admin(self, user_repo):
        repo = user_repo
        _seed_admin(
            repo, PlainPasswordHasher(), AdminSettings("root", "r@example.org", "Password1!")
        )
        assert repo.get_by_login("root").role is Role.ADMIN
