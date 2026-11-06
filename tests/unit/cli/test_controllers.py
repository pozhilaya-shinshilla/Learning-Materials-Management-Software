"""Юнит-тесты контроллеров CLI: сценарии студента, преподавателя, администратора и входа."""

from __future__ import annotations

import pytest

from src.cli.admin_controller import AdminController
from src.cli.console_io import Cancelled
from src.cli.controller_factory import CONTROLLER_FACTORIES
from src.cli.student_controller import StudentController
from src.cli.teacher_controller import TeacherController
from src.domain.enums import AccountStatus, EventType, Role
from tests.fakes import ScriptedIO


def _labels(controller):
    return [label for label, _ in controller.menu_items()]


class TestMenus:
    def test_student_menu_is_prefix_of_teacher_menu(self, app, student, teacher):
        student_menu = _labels(StudentController(app, ScriptedIO(), student))
        teacher_menu = _labels(TeacherController(app, ScriptedIO(), teacher))
        assert teacher_menu[: len(student_menu)] == student_menu
        assert len(teacher_menu) > len(student_menu)

    def test_teacher_menu_is_prefix_of_admin_menu(self, app, teacher, admin):
        teacher_menu = _labels(TeacherController(app, ScriptedIO(), teacher))
        admin_menu = _labels(AdminController(app, ScriptedIO(), admin))
        assert admin_menu[: len(teacher_menu)] == teacher_menu
        assert "Просмотреть журнал событий" in admin_menu

    def test_student_has_no_management_items(self, app, student):
        menu = _labels(StudentController(app, ScriptedIO(), student))
        assert "Добавить материал" not in menu
        assert "Удалить материал" not in menu
        assert not any("пользовател" in item.lower() for item in menu)

    def test_undo_item_is_available_to_teacher(self, app, teacher):
        assert "Отменить последнее изменение материала" in _labels(
            TeacherController(app, ScriptedIO(), teacher)
        )

    @pytest.mark.parametrize(
        ("role", "controller_type"),
        [
            (Role.STUDENT, StudentController),
            (Role.TEACHER, TeacherController),
            (Role.ADMIN, AdminController),
        ],
    )
    def test_factory_creates_exact_type(self, app, admin, role, controller_type):
        controller = CONTROLLER_FACTORIES[role].create_controller(app, ScriptedIO(), admin)
        assert type(controller) is controller_type

    def test_every_role_has_a_factory(self):
        assert set(CONTROLLER_FACTORIES) == set(Role)


class TestStudentFlows:
    def _controller(self, app, student, answers=()):
        io = ScriptedIO(answers)
        return StudentController(app, io, student), io

    def test_empty_catalog_message_for_student(self, app, student, capsys):
        controller, _ = self._controller(app, student)
        controller._show_materials_flow()
        assert "Материалы добавляют преподаватели" in capsys.readouterr().out

    def test_empty_catalog_message_for_teacher_differs(self, app, teacher, capsys):
        TeacherController(app, ScriptedIO(), teacher)._show_materials_flow()
        assert "Добавить материал" in capsys.readouterr().out

    def test_show_materials(self, app, student, seeded, capsys):
        controller, _ = self._controller(app, student)
        controller._show_materials_flow()
        assert "Линейные уравнения" in capsys.readouterr().out

    def test_details_show_author_and_favorite(self, app, student, seeded, capsys):
        _, _, material = seeded
        controller, _ = self._controller(app, student, [str(material.id)])
        controller._material_details_flow()
        out = capsys.readouterr().out
        assert "Автор:       teacher" in out
        assert "В избранном: нет" in out

    def test_details_of_empty_catalog(self, app, student, capsys):
        controller, _ = self._controller(app, student)
        controller._material_details_flow()
        assert "пока пуст" in capsys.readouterr().out

    @pytest.mark.db  # морфологию русского языка выполняет PostgreSQL
    def test_search_by_morphology(self, app, student, seeded, capsys):
        answers = ["уравнение", "", "", "", "", "", ""]
        controller, _ = self._controller(app, student, answers)
        controller._search_flow()
        out = capsys.readouterr().out
        assert "Найдено материалов: 1" in out

    def test_search_without_results(self, app, student, seeded, capsys):
        answers = ["химия", "", "", "", "", "", ""]
        controller, _ = self._controller(app, student, answers)
        controller._search_flow()
        assert "ничего не найдено" in capsys.readouterr().out

    def test_search_with_discipline_and_topic_filters(self, app, student, seeded, capsys):
        answers = ["", "математика", "геометрия", "", "", "", ""]
        controller, _ = self._controller(app, student, answers)
        controller._search_flow()
        assert "ничего не найдено" in capsys.readouterr().out

    def test_search_rejects_reversed_date_range_then_accepts(self, app, student, seeded, capsys):
        answers = ["", "", "", "10.01.2026", "01.01.2026", "11.01.2026", ""]
        controller, _ = self._controller(app, student, answers)
        controller._search_flow()
        out = capsys.readouterr().out
        assert "✗" in out

    def test_search_in_empty_catalog(self, app, student, capsys):
        controller, _ = self._controller(app, student)
        controller._search_flow()
        assert "пока пуст" in capsys.readouterr().out

    def test_search_can_be_cancelled(self, app, student, seeded):
        controller, _ = self._controller(app, student, ["0"])
        with pytest.raises(Cancelled):
            controller._search_flow()

    def test_favorites_lifecycle(self, app, student, seeded, capsys):
        _, _, material = seeded
        controller, _ = self._controller(app, student, [str(material.id), str(material.id)])
        controller._list_favorites_flow()
        assert "ничего нет" in capsys.readouterr().out
        controller._add_favorite_flow()
        assert "добавлен в избранное" in capsys.readouterr().out
        controller._list_favorites_flow()
        assert "Линейные уравнения" in capsys.readouterr().out
        controller._add_favorite_flow()
        assert "уже в вашем избранном" in capsys.readouterr().out
        controller._remove_favorite_flow()
        assert "убран из избранного" in capsys.readouterr().out
        controller._remove_favorite_flow()
        assert "ничего нет" in capsys.readouterr().out

    def test_download_copies_file(self, app, student, seeded, tmp_path, capsys):
        _, _, material = seeded
        target = tmp_path / "downloads"
        controller, _ = self._controller(app, student, [str(material.id), str(target)])
        controller._download_flow()
        assert (target / "lecture.pdf").read_bytes() == b"content"
        assert "Файл сохранен" in capsys.readouterr().out

    def test_download_is_logged(self, app, student, seeded, tmp_path, admin):
        _, _, material = seeded
        controller, _ = self._controller(app, student, [str(material.id), str(tmp_path / "d")])
        controller._download_flow()
        types = [e.event_type for e in app.event_log_service.list_events(admin)]
        assert EventType.MATERIAL_DOWNLOADED in types

    def test_download_declined_overwrite(self, app, student, seeded, tmp_path, capsys):
        _, _, material = seeded
        target = tmp_path / "d"
        target.mkdir()
        (target / "lecture.pdf").write_bytes(b"old")
        controller, _ = self._controller(app, student, [str(material.id), str(target), "n"])
        controller._download_flow()
        assert (target / "lecture.pdf").read_bytes() == b"old"
        assert "Скачивание отменено" in capsys.readouterr().out

    def test_download_confirmed_overwrite(self, app, student, seeded, tmp_path):
        _, _, material = seeded
        target = tmp_path / "d"
        target.mkdir()
        (target / "lecture.pdf").write_bytes(b"old")
        controller, _ = self._controller(app, student, [str(material.id), str(target), "y"])
        controller._download_flow()
        assert (target / "lecture.pdf").read_bytes() == b"content"

    def test_download_when_storage_file_vanished(self, app, student, seeded, capsys):
        _, _, material = seeded
        app.material_service.resolve_file_path(material.id).unlink()
        controller, _ = self._controller(app, student, [str(material.id)])
        controller._download_flow()
        assert "не найден в хранилище" in capsys.readouterr().out

    def test_destination_that_is_a_file_is_rejected(self, app, student, seeded, tmp_path, capsys):
        _, _, material = seeded
        not_dir = tmp_path / "file.txt"
        not_dir.write_text("x")
        controller, _ = self._controller(
            app, student, [str(material.id), str(not_dir), str(tmp_path / "ok")]
        )
        controller._download_flow()
        assert "✗" in capsys.readouterr().out

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [("  /tmp/x  ", "/tmp/x"), ('"/tmp/x"', "/tmp/x"), ("'/tmp/x'", "/tmp/x"), ('" a "', "a")],
    )
    def test_clean_path_strips_quotes_and_spaces(self, raw, expected):
        assert StudentController._clean_path(raw) == expected

    def test_print_catalog(self, app, student, seeded, capsys):
        controller, _ = self._controller(app, student)
        controller._print_catalog()
        out = capsys.readouterr().out
        assert "• Математика" in out and "Алгебра" in out and "Геометрия" in out

    def test_print_catalog_marks_empty_discipline(self, app, student, teacher, capsys):
        app.catalog_service.create_discipline(teacher, "Физика")
        controller, _ = self._controller(app, student)
        controller._print_catalog()
        assert "тем пока нет" in capsys.readouterr().out

    def test_print_empty_catalog(self, app, student, capsys):
        controller, _ = self._controller(app, student)
        controller._print_catalog()
        assert "Дисциплин пока нет" in capsys.readouterr().out


class TestTeacherFlows:
    def _controller(self, app, teacher, answers=()):
        io = ScriptedIO(answers)
        return TeacherController(app, io, teacher), io

    def test_create_discipline_and_topic(self, app, teacher, capsys):
        controller, _ = self._controller(app, teacher, ["Физика", "физика", "Механика"])
        controller._create_discipline_flow()
        controller._create_topic_flow()
        out = capsys.readouterr().out
        assert "Дисциплина «Физика» создана" in out
        assert "Тема «Механика» добавлена" in out

    def test_duplicate_discipline_name_is_reasked(self, app, teacher, seeded, capsys):
        controller, io = self._controller(app, teacher, ["математика", "Физика"])
        controller._create_discipline_flow()
        assert len(io.prompts) == 2
        assert "✗" in capsys.readouterr().out

    def test_create_topic_without_disciplines(self, app, teacher, capsys):
        controller, _ = self._controller(app, teacher)
        controller._create_topic_flow()
        assert "Сначала добавьте дисциплину" in capsys.readouterr().out

    def test_create_material_without_catalog(self, app, teacher, capsys):
        controller, _ = self._controller(app, teacher)
        controller._create_material_flow()
        assert "Сначала добавьте дисциплину" in capsys.readouterr().out

    def test_create_material_without_topics(self, app, teacher, capsys):
        app.catalog_service.create_discipline(teacher, "Физика")
        controller, _ = self._controller(app, teacher)
        controller._create_material_flow()
        assert "нет тем" in capsys.readouterr().out

    def test_create_material(self, app, teacher, seeded, tmp_path, capsys):
        source = tmp_path / "new.docx"
        source.write_bytes(b"abc")
        answers = ["Новый", "Описание", "математика", "алгебра", str(source)]
        controller, _ = self._controller(app, teacher, answers)
        controller._create_material_flow()
        assert "Материал создан" in capsys.readouterr().out
        assert len(app.material_service.list_materials()) == 2

    def test_create_material_reasks_for_bad_file_path(self, app, teacher, seeded, tmp_path, capsys):
        good = tmp_path / "ok.png"
        good.write_bytes(b"x")
        bad = tmp_path / "bad.exe"
        bad.write_bytes(b"x")
        answers = [
            "Т",
            "",
            "математика",
            "алгебра",
            "",
            str(bad),
            str(tmp_path / "none.pdf"),
            str(good),
        ]
        controller, io = self._controller(app, teacher, answers)
        controller._create_material_flow()
        assert capsys.readouterr().out.count("✗") == 3
        assert len(app.material_service.list_materials()) == 2

    def test_path_in_quotes_is_accepted(self, app, teacher, seeded, tmp_path):
        good = tmp_path / "ok.png"
        good.write_bytes(b"x")
        controller, _ = self._controller(
            app, teacher, ["Т", "", "математика", "алгебра", f'"{good}"']
        )
        controller._create_material_flow()
        assert len(app.material_service.list_materials()) == 2

    def test_my_materials(self, app, teacher, seeded, capsys):
        controller, _ = self._controller(app, teacher)
        controller._my_materials_flow()
        assert "Линейные уравнения" in capsys.readouterr().out

    def test_my_materials_empty(self, app, teacher, capsys):
        controller, _ = self._controller(app, teacher)
        controller._my_materials_flow()
        assert "не добавили" in capsys.readouterr().out

    def test_edit_title_then_undo(self, app, teacher, seeded, capsys):
        _, _, material = seeded
        answers = [str(material.id), "Новое название", "", "", ""]
        controller, _ = self._controller(app, teacher, answers)
        controller._edit_material_flow()
        assert app.material_service.get_material(material.id).title == "Новое название"
        controller2, _ = self._controller(app, teacher, [str(material.id)])
        controller2._undo_edit_flow()
        assert app.material_service.get_material(material.id).title == "Линейные уравнения"
        assert "Изменение отменено" in capsys.readouterr().out

    def test_edit_with_nothing_entered(self, app, teacher, seeded, capsys):
        _, _, material = seeded
        controller, _ = self._controller(app, teacher, [str(material.id), "", "", "", ""])
        controller._edit_material_flow()
        assert "Ничего не изменено" in capsys.readouterr().out
        assert app.material_service.can_undo(material.id) is False

    def test_edit_topic_only(self, app, teacher, seeded):
        _, _, material = seeded
        answers = [str(material.id), "", "", "", "геометрия"]
        controller, _ = self._controller(app, teacher, answers)
        controller._edit_material_flow()
        geometry = app.catalog_service.list_topics(material.discipline_id)[1]
        assert app.material_service.get_material(material.id).topic_id == geometry.id

    def test_undo_with_nothing_to_undo(self, app, teacher, seeded, capsys):
        controller, _ = self._controller(app, teacher)
        controller._undo_edit_flow()
        assert "Нет материалов" in capsys.readouterr().out

    def test_edit_when_user_has_no_own_materials(self, app, make_account, seeded, capsys):
        other = make_account("other", Role.TEACHER)
        controller, _ = self._controller(app, other)
        controller._edit_material_flow()
        assert "только свои" in capsys.readouterr().out

    def test_delete_requires_confirmation(self, app, teacher, seeded, capsys):
        _, _, material = seeded
        controller, _ = self._controller(app, teacher, [str(material.id), "n"])
        controller._delete_material_flow()
        assert "Удаление отменено" in capsys.readouterr().out
        assert len(app.material_service.list_materials()) == 1

    def test_delete_confirmed(self, app, teacher, seeded, capsys):
        _, _, material = seeded
        controller, _ = self._controller(app, teacher, [str(material.id), "y"])
        controller._delete_material_flow()
        assert app.material_service.list_materials() == []
        assert "Материал удален" in capsys.readouterr().out

    def test_rename_discipline_and_topic(self, app, teacher, seeded, capsys):
        answers = ["математика", "Матан", "матан", "алгебра", "Линал"]
        controller, _ = self._controller(app, teacher, answers)
        controller._rename_discipline_flow()
        controller._rename_topic_flow()
        out = capsys.readouterr().out
        assert "переименована в «Матан»" in out
        assert "переименована в «Линал»" in out

    def test_rename_rejects_unchanged_name_then_accepts(self, app, teacher, seeded, capsys):
        controller, io = self._controller(app, teacher, ["математика", "Математика", "Алгебра2"])
        controller._rename_discipline_flow()
        assert "✗" in capsys.readouterr().out

    def test_rename_topic_when_no_topics(self, app, teacher, capsys):
        app.catalog_service.create_discipline(teacher, "Физика")
        controller, _ = self._controller(app, teacher)
        controller._rename_topic_flow()
        assert "переименовывать нечего" in capsys.readouterr().out

    def test_rename_without_disciplines(self, app, teacher, capsys):
        controller, _ = self._controller(app, teacher)
        controller._rename_discipline_flow()
        controller._rename_topic_flow()
        assert capsys.readouterr().out.count("Дисциплин пока нет") == 2


class TestAdminFlows:
    def _controller(self, app, admin, answers=()):
        io = ScriptedIO(answers)
        return AdminController(app, io, admin), io

    def test_list_users(self, app, admin, student, capsys):
        controller, _ = self._controller(app, admin)
        controller._list_users_flow()
        out = capsys.readouterr().out
        assert "boss" in out and "student" in out

    def test_create_user(self, app, admin, capsys):
        answers = ["newbie", "newbie@example.org", "Password1!", "t"]
        controller, _ = self._controller(app, admin, answers)
        controller._create_user_flow()
        assert "Пользователь newbie создан" in capsys.readouterr().out
        assert app.user_management_service.list_users(admin)[-1].role is Role.TEACHER

    def test_create_user_reasks_taken_login_and_short_password(self, app, admin, student, capsys):
        answers = ["student", "free", "x@y.org", "short", "alllowercase1", "Password1!", "s"]
        controller, io = self._controller(app, admin, answers)
        controller._create_user_flow()
        assert capsys.readouterr().out.count("✗") == 3

    def test_create_user_prompt_states_password_rules(self, app, admin):
        controller, io = self._controller(
            app, admin, ["newbie", "newbie@example.org", "Password1!", "s"]
        )
        controller._create_user_flow()
        assert any("заглавной буквой" in prompt for prompt in io.prompts)

    def test_create_user_reasks_taken_email(self, app, admin, student, capsys):
        answers = ["fresh", "student@example.org", "fresh@example.org", "Password1!", "s"]
        controller, _ = self._controller(app, admin, answers)
        controller._create_user_flow()
        assert capsys.readouterr().out.count("✗") == 1

    def test_change_role(self, app, admin, student, capsys, user_repo):
        controller, _ = self._controller(app, admin, [str(student.id), "t"])
        controller._change_role_flow()
        assert user_repo.get_by_id(student.id).role is Role.TEACHER
        assert "изменена" in capsys.readouterr().out

    def test_change_role_to_same_is_reasked(self, app, admin, student, capsys, user_repo):
        controller, _ = self._controller(app, admin, [str(student.id), "s", "a"])
        controller._change_role_flow()
        assert user_repo.get_by_id(student.id).role is Role.ADMIN
        assert "✗" in capsys.readouterr().out

    def test_change_role_without_other_users(self, app, admin, capsys):
        controller, _ = self._controller(app, admin)
        controller._change_role_flow()
        assert "менять роль некому" in capsys.readouterr().out

    def test_admin_cannot_pick_self(self, app, admin, student, capsys):
        controller, _ = self._controller(app, admin, [str(admin.id), str(student.id), "t"])
        controller._change_role_flow()
        assert "✗" in capsys.readouterr().out

    def test_block_and_unblock(self, app, admin, student, capsys, user_repo):
        controller, _ = self._controller(app, admin, [str(student.id), "y", str(student.id), "y"])
        controller._toggle_block_flow()
        assert user_repo.get_by_id(student.id).status is AccountStatus.BLOCKED
        controller._toggle_block_flow()
        assert user_repo.get_by_id(student.id).status is AccountStatus.ACTIVE
        out = capsys.readouterr().out
        assert "заблокирован" in out and "разблокирован" in out

    def test_block_declined(self, app, admin, student, capsys, user_repo):
        controller, _ = self._controller(app, admin, [str(student.id), "n"])
        controller._toggle_block_flow()
        assert user_repo.get_by_id(student.id).status is AccountStatus.ACTIVE
        assert "Действие отменено" in capsys.readouterr().out

    def test_delete_user_declined_then_confirmed(self, app, admin, student, capsys):
        controller, _ = self._controller(app, admin, [str(student.id), "n", str(student.id), "y"])
        controller._delete_user_flow()
        assert "Удаление отменено" in capsys.readouterr().out
        controller._delete_user_flow()
        assert app.user_management_service.list_users(admin) == [admin]

    def test_delete_without_other_users(self, app, admin, capsys):
        controller, _ = self._controller(app, admin)
        controller._delete_user_flow()
        assert "удалять некого" in capsys.readouterr().out

    def test_block_without_other_users(self, app, admin, capsys):
        controller, _ = self._controller(app, admin)
        controller._toggle_block_flow()
        assert "блокировать некого" in capsys.readouterr().out

    def test_events_flow_shows_actions(self, app, admin, student, capsys):
        app.auth_service.logout(student)
        controller, _ = self._controller(app, admin)
        controller._print_events_flow()
        out = capsys.readouterr().out
        assert "student: выход из системы" in out

    def test_events_flow_for_empty_log(self, app, admin, capsys):
        controller, _ = self._controller(app, admin)
        controller._print_events_flow()
        assert "Журнал событий пуст" in capsys.readouterr().out
