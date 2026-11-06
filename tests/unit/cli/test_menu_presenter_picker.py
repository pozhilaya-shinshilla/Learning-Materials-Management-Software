"""Юнит-тесты MenuRenderer, Presenter и Picker."""

from __future__ import annotations

from datetime import datetime

import pytest

from src.cli.menu import MenuRenderer
from src.cli.picker import Picker
from src.cli.presenter import Presenter
from src.domain.enums import AccountStatus, EventType, Role
from src.domain.exceptions import (
    DisciplineNameRequiredError,
    DisciplineNotInListError,
    MaterialNotInListError,
    NotPositiveIntegerError,
    TopicNotInListError,
    UserNotInListError,
)
from src.domain.models import Discipline, Event, Topic
from src.services.catalog_service import CatalogService
from tests.fakes import ScriptedIO, make_material, make_user


class TestMenuRenderer:
    def _items(self, log):
        return [("Первый", lambda: log.append(1)), ("Второй", lambda: log.append(2))]

    def test_selects_handler_by_number(self):
        log = []
        handler = MenuRenderer(ScriptedIO(["2"])).choose("Меню", self._items(log))
        handler()
        assert log == [2]

    def test_zero_means_exit(self):
        assert MenuRenderer(ScriptedIO(["0"])).choose("Меню", self._items([])) is None

    @pytest.mark.parametrize("bad", ["", "3", "-1", "abc", "1.5", "00x", "99"])
    def test_invalid_numbers_are_reasked(self, bad, capsys):
        io = ScriptedIO([bad, "1"])
        assert MenuRenderer(io).choose("Меню", self._items([])) is not None
        assert "Нет такого пункта" in capsys.readouterr().out

    def test_boundaries_first_and_last(self):
        log = []
        MenuRenderer(ScriptedIO(["1"])).choose("М", self._items(log))()
        MenuRenderer(ScriptedIO(["2"])).choose("М", self._items(log))()
        assert log == [1, 2]

    def test_prints_title_and_all_items(self, capsys):
        MenuRenderer(ScriptedIO(["0"])).choose("Заголовок", self._items([]))
        out = capsys.readouterr().out
        assert "Заголовок" in out
        assert "1) Первый" in out and "2) Второй" in out
        assert "0) Выйти" in out

    def test_empty_menu_only_allows_exit(self):
        io = ScriptedIO(["1", "0"])
        assert MenuRenderer(io).choose("М", []) is None


class TestFormatSize:
    @pytest.mark.parametrize(
        ("size", "expected"),
        [
            (0, "0 Б"),
            (1, "1 Б"),
            (1023, "1023 Б"),
            (1024, "1.0 КБ"),
            (1536, "1.5 КБ"),
            (1024 * 1024 - 1, "1024.0 КБ"),
            (1024 * 1024, "1.0 МБ"),
            (100 * 1024 * 1024, "100.0 МБ"),
        ],
    )
    def test_boundaries(self, size, expected):
        assert Presenter.format_size(size) == expected


@pytest.fixture
def catalog(discipline_repo, topic_repo, event_log):
    service = CatalogService(discipline_repo, topic_repo, event_log)
    math = discipline_repo.add(Discipline(0, "Математика"))
    topic_repo.add(Topic(0, "Алгебра", math.id))
    return service


class TestPresenter:
    def test_print_materials_with_description(self, catalog, capsys):
        Presenter(catalog).print_materials([make_material(1, "Лекция", "Описание")])
        out = capsys.readouterr().out
        assert "[1] Лекция" in out
        assert "Математика / Алгебра" in out
        assert "Описание" in out
        assert "pdf" in out

    def test_print_materials_without_description_has_no_extra_line(self, catalog, capsys):
        Presenter(catalog).print_materials([make_material(1, "Лекция", "")])
        assert len(capsys.readouterr().out.strip().splitlines()) == 1

    def test_print_empty_list(self, catalog, capsys):
        Presenter(catalog).print_materials([])
        assert capsys.readouterr().out == ""

    def test_unknown_classification_shown_as_question_marks(self, catalog, capsys):
        Presenter(catalog).print_materials([make_material(1, discipline_id=99, topic_id=99)])
        assert "? / ?" in capsys.readouterr().out

    @pytest.mark.parametrize(("favorite", "word"), [(True, "да"), (False, "нет")])
    def test_details_favorite_flag(self, catalog, capsys, favorite, word):
        Presenter(catalog).print_material_details(make_material(1), "bob", favorite)
        out = capsys.readouterr().out
        assert f"В избранном: {word}" in out
        assert "Автор:       bob" in out

    def test_details_empty_description_dash(self, catalog, capsys):
        Presenter(catalog).print_material_details(make_material(1, description=""), "bob", False)
        assert "Описание:    —" in capsys.readouterr().out

    def test_print_users(self, catalog, capsys):
        users = [
            make_user(1, "bob", Role.TEACHER),
            make_user(2, "amy", Role.STUDENT, AccountStatus.BLOCKED),
        ]
        Presenter(catalog).print_users(users)
        out = capsys.readouterr().out
        assert "[1] bob" in out and Role.TEACHER.label in out
        assert AccountStatus.BLOCKED.label in out

    def test_print_events_known_guest_and_deleted_users(self, catalog, capsys):
        events = [
            Event(1, 1, EventType.USER_LOGGED_IN, "bob"),
            Event(2, None, EventType.USER_LOGIN_FAILED, "ghost"),
            Event(3, 7, EventType.MATERIAL_CREATED, "T"),
        ]
        Presenter(catalog).print_events(events, {1: "bob"})
        out = capsys.readouterr().out
        assert "bob: вход в систему — bob" in out
        assert "гость или удалённый пользователь: неудачная попытка входа — ghost" in out
        assert "ID 7 (удален): материал создан — T" in out

    def test_event_time_is_formatted(self, catalog, capsys):
        event = Event(1, 1, EventType.USER_LOGGED_IN, "x")
        event.occurred_at = datetime(2026, 3, 4, 5, 6, 7).astimezone()
        Presenter(catalog).print_events([event], {1: "bob"})
        assert "04.03.2026 05:06:07" in capsys.readouterr().out


class TestPicker:
    @pytest.fixture
    def disciplines(self):
        return [Discipline(1, "Математика"), Discipline(2, "Физика")]

    def _picker(self, answers, catalog):
        io = ScriptedIO(answers)
        return Picker(io, Presenter(catalog)), io

    def test_pick_discipline_ignoring_case(self, catalog, disciplines):
        picker, _ = self._picker(["  физика "], catalog)
        assert picker.pick_discipline("Д: ", disciplines).id == 2

    def test_unknown_discipline_is_reasked(self, catalog, disciplines, capsys):
        picker, io = self._picker(["химия", "математика"], catalog)
        assert picker.pick_discipline("Д: ", disciplines).id == 1
        assert "химия" in capsys.readouterr().out

    def test_blank_discipline_is_reasked(self, catalog, disciplines):
        picker, io = self._picker(["", "физика"], catalog)
        picker.pick_discipline("Д: ", disciplines)
        assert len(io.prompts) == 2

    def test_optional_discipline_blank_gives_none(self, catalog, disciplines):
        picker, _ = self._picker([""], catalog)
        assert picker.pick_optional_discipline("Д: ", disciplines) is None

    def test_optional_discipline_still_validates(self, catalog, disciplines):
        picker, io = self._picker(["химия", ""], catalog)
        assert picker.pick_optional_discipline("Д: ", disciplines) is None
        assert len(io.prompts) == 2

    def test_pick_topic_and_optional(self, catalog):
        topics = [Topic(1, "Алгебра", 1), Topic(2, "Геометрия", 1)]
        picker, _ = self._picker(["ГЕОМЕТРИЯ", ""], catalog)
        assert picker.pick_topic("Т: ", topics).id == 2
        assert picker.pick_optional_topic("Т: ", topics) is None

    def test_pick_material_by_id(self, catalog):
        materials = [make_material(3), make_material(5)]
        picker, _ = self._picker(["5"], catalog)
        assert picker.pick_material("ID: ", materials).id == 5

    @pytest.mark.parametrize("bad", ["4", "-3", "x", "", "03x"])
    def test_pick_material_reasks_on_bad_id(self, catalog, bad):
        materials = [make_material(3), make_material(5)]
        picker, io = self._picker([bad, "3"], catalog)
        assert picker.pick_material("ID: ", materials).id == 3
        assert len(io.prompts) == 2

    def test_zero_cancels_the_selection(self, catalog):
        from src.cli.console_io import Cancelled

        picker, _ = self._picker(["0"], catalog)
        with pytest.raises(Cancelled):
            picker.pick_material("ID: ", [make_material(3)])

    def test_pick_user(self, catalog):
        users = [make_user(2, "bob"), make_user(9, "amy")]
        picker, _ = self._picker(["9"], catalog)
        assert picker.pick_user("ID: ", users).login == "amy"

    def test_lists_are_printed_before_asking(self, catalog, disciplines, capsys):
        picker, _ = self._picker(["математика"], catalog)
        picker.pick_discipline("Д: ", disciplines)
        out = capsys.readouterr().out
        assert "• Математика" in out and "• Физика" in out

    def test_static_parsers_raise_specific_errors(self):
        with pytest.raises(DisciplineNameRequiredError):
            Picker._parse_discipline("  ", {})
        with pytest.raises(DisciplineNotInListError):
            Picker._parse_discipline("x", {})
        with pytest.raises(TopicNotInListError):
            Picker._parse_topic("x", {})
        with pytest.raises(MaterialNotInListError):
            Picker._parse_material("1", {})
        with pytest.raises(UserNotInListError):
            Picker._parse_user("1", {})
        with pytest.raises(NotPositiveIntegerError):
            Picker._parse_user("0", {})
