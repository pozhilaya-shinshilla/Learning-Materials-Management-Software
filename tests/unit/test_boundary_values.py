"""Граничные значения: минимум и максимум диапазона, пустые коллекции, момент истечения срока.

Приём (анализ граничных значений): для каждого ограничения проверяются три точки — последнее
допустимое значение, первое недопустимое и значение «по другую сторону» (минимум − 1, максимум + 1).
Ошибка почти всегда прячется на границе (`<` вместо `<=`), а не посередине диапазона.

Внешняя зависимость «время» заменена часами `clock`, база данных — хранилищем в памяти.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest
from pydantic import ValidationError as PydanticValidationError

from src.bootstrap import build_application_context
from src.configs.config import (
    AUTH_TOKEN_TTL_HOURS,
    MAX_FILE_SIZE_BYTES,
    MAX_REVISIONS_PER_MATERIAL,
    RESET_TOKEN_TTL_MINUTES,
)
from src.configs.settings import AdminSettings
from src.domain.enums import FileType, Role, SortField, SortOrder
from src.domain.exceptions import (
    EmptyFieldError,
    FieldTooLongError,
    FileTooLargeError,
    InvalidEmailError,
    InvalidLoginError,
    InvalidResetTokenError,
    InvalidTokenError,
    PasswordTooShortError,
)
from src.domain.models import Discipline, Topic
from src.domain.search import MaterialSearchQuery
from src.domain.validation import (
    MAX_NAME_LENGTH,
    MAX_TITLE_LENGTH,
    MIN_PASSWORD_LENGTH,
    require_text,
    validate_email,
    validate_login,
    validate_password,
)
from src.dtos.requests import (
    MAX_ID,
    DisciplineCreateRequest,
    LoginRequest,
    MaterialCreateRequest,
    MaterialListQuery,
)
from src.services.file_validation import FileCheck, FileSizeHandler
from src.services.search_service import MaterialFilter, SearchService
from tests.fakes import RecordingEmailSender, make_material, make_user


@pytest.fixture
def mailbox():
    return RecordingEmailSender()


@pytest.fixture
def author(repository_factory):
    """Автор материалов: хранилище не принимает материал без существующего пользователя."""
    return repository_factory.create_user_repository().add(make_user(0, "author"))


@pytest.fixture
def app(repository_factory, tmp_path, mailbox):
    return build_application_context(
        repository_factory,
        email_sender=mailbox,
        upload_root=tmp_path / "uploads",
        admin=AdminSettings("admin", "admin@example.org", "Admin12345!"),
    )


# --- Длины текстов -----------------------------------------------------------------------------


class TestTextLengths:
    @pytest.mark.parametrize("length", [1, MAX_NAME_LENGTH])
    def test_name_at_the_limits_is_accepted(self, length):
        assert require_text("я" * length, "Название") == "я" * length

    @pytest.mark.parametrize("raw", ["", " ", "\t\n  "])
    def test_empty_or_blank_name_is_rejected(self, raw):
        with pytest.raises(EmptyFieldError):
            require_text(raw, "Название")

    def test_one_character_over_the_limit_is_rejected(self):
        with pytest.raises(FieldTooLongError) as error:
            require_text("я" * (MAX_NAME_LENGTH + 1), "Название")
        assert str(MAX_NAME_LENGTH) in str(error.value)

    def test_padding_spaces_do_not_count_towards_the_limit(self):
        padded = " " * 50 + "я" * MAX_NAME_LENGTH + " " * 50
        assert len(require_text(padded, "Название")) == MAX_NAME_LENGTH

    @pytest.mark.parametrize(
        ("length", "valid"),
        [(0, False), (1, True), (MAX_TITLE_LENGTH, True), (MAX_TITLE_LENGTH + 1, False)],
    )
    def test_material_title_dto(self, length, valid):
        build = lambda: MaterialCreateRequest(  # noqa: E731
            title="т" * length, discipline_id=1, topic_id=1
        )
        if valid:
            assert len(build().title) == length
        else:
            with pytest.raises(PydanticValidationError):
                build()

    @pytest.mark.parametrize(
        ("length", "valid"),
        [(0, False), (1, True), (MAX_NAME_LENGTH, True), (MAX_NAME_LENGTH + 1, False)],
    )
    def test_discipline_name_dto(self, length, valid):
        if valid:
            assert DisciplineCreateRequest(name="д" * length)
        else:
            with pytest.raises(PydanticValidationError):
                DisciplineCreateRequest(name="д" * length)

    @pytest.mark.parametrize(
        ("login_length", "password_length", "valid"),
        [
            (1, 1, True),
            (50, 128, True),
            (0, 1, False),
            (51, 1, False),
            (1, 0, False),
            (1, 129, False),
        ],
    )
    def test_login_request_limits(self, login_length, password_length, valid):
        def build():
            return LoginRequest(login="a" * login_length, password="p" * password_length)

        if valid:
            build()
        else:
            with pytest.raises(PydanticValidationError):
                build()


class TestLoginEmailPassword:
    @pytest.mark.parametrize("length", [3, 32])
    def test_login_length_inside_range(self, length):
        validate_login("a" * length)

    @pytest.mark.parametrize("length", [0, 1, 2, 33, 100])
    def test_login_length_outside_range(self, length):
        with pytest.raises(InvalidLoginError):
            validate_login("a" * length)

    @pytest.mark.parametrize("email", ["a@b.c", "x@y.zz"])
    def test_shortest_valid_emails(self, email):
        validate_email(email)

    @pytest.mark.parametrize("email", ["", "@", "a@b", "a@.c", "@b.c", "a b@c.d"])
    def test_malformed_emails_just_outside_the_format(self, email):
        with pytest.raises(InvalidEmailError):
            validate_email(email)

    def test_password_of_minimum_length_is_accepted(self):
        password = "Aa1!" + "x" * (MIN_PASSWORD_LENGTH - 4)
        assert len(password) == MIN_PASSWORD_LENGTH
        validate_password(password)

    def test_password_one_character_shorter_is_rejected(self):
        password = "Aa1!" + "x" * (MIN_PASSWORD_LENGTH - 5)
        assert len(password) == MIN_PASSWORD_LENGTH - 1
        with pytest.raises(PasswordTooShortError):
            validate_password(password)


# --- Страницы и номера -------------------------------------------------------------------------


class TestPaging:
    @pytest.mark.parametrize("limit", [1, 50, 100])
    def test_limit_inside_range(self, limit):
        assert MaterialListQuery(limit=limit).limit == limit

    @pytest.mark.parametrize("limit", [0, -1, 101])
    def test_limit_outside_range(self, limit):
        with pytest.raises(PydanticValidationError):
            MaterialListQuery(limit=limit)

    @pytest.mark.parametrize("offset", [0, MAX_ID])
    def test_offset_inside_range(self, offset):
        assert MaterialListQuery(offset=offset).offset == offset

    @pytest.mark.parametrize("offset", [-1, MAX_ID + 1])
    def test_offset_outside_range(self, offset):
        with pytest.raises(PydanticValidationError):
            MaterialListQuery(offset=offset)

    @pytest.mark.parametrize("value", [1, MAX_ID])
    def test_ids_at_the_limits(self, value):
        assert MaterialCreateRequest(title="т", discipline_id=value, topic_id=value)

    @pytest.mark.parametrize("value", [0, -1, MAX_ID + 1])
    def test_ids_outside_the_limits(self, value):
        with pytest.raises(PydanticValidationError):
            MaterialCreateRequest(title="т", discipline_id=value, topic_id=1)

    def test_date_range_of_a_single_day_is_allowed_and_reversed_is_not(self):
        assert MaterialListQuery(uploaded_from=date(2026, 5, 1), uploaded_to=date(2026, 5, 1))
        with pytest.raises(PydanticValidationError):
            MaterialListQuery(uploaded_from=date(2026, 5, 2), uploaded_to=date(2026, 5, 1))

    @pytest.fixture
    def seven_materials(self, repository_factory, author):
        repo = repository_factory.create_material_repository()
        for number in range(7):
            repo.add(make_material(0, title=f"Материал {number}"))
        return repo

    @pytest.mark.parametrize(
        ("limit", "offset", "expected"),
        [
            (3, 0, 3),  # первая страница
            (3, 6, 1),  # последняя неполная страница: остался один материал
            (3, 7, 0),  # ровно за концом списка
            (7, 0, 7),  # лимит равен общему числу
            (8, 0, 7),  # лимит больше общего числа
            (1, 0, 1),  # минимальная страница
            (3, 10_000, 0),  # далеко за концом
        ],
    )
    def test_page_sizes_at_the_edges(self, seven_materials, limit, offset, expected):
        query = MaterialSearchQuery(limit=limit, offset=offset)
        assert len(seven_materials.search(query)) == expected
        assert seven_materials.count(MaterialSearchQuery(limit=limit, offset=offset)) == 7


# --- Пустые коллекции --------------------------------------------------------------------------


class TestEmptyCollections:
    def test_search_in_an_empty_catalog(self, app):
        assert app.search_service.search(MaterialFilter()) == []
        items, total = app.search_service.search_page(MaterialFilter(), limit=10)
        assert (items, total) == ([], 0)

    def test_catalog_without_disciplines_and_topics(self, app):
        assert app.catalog_service.list_disciplines() == []
        assert app.catalog_service.list_all_topics() == []
        assert app.catalog_service.list_topics(1) == []

    def test_discipline_without_topics_has_an_empty_topic_list(self, app, repository_factory):
        discipline = repository_factory.create_discipline_repository().add(Discipline(0, "Физика"))
        assert app.catalog_service.list_topics(discipline.id) == []

    def test_new_user_has_no_favorites(self, app):
        admin = app.auth_service.login("admin", "Admin12345!")
        assert app.favorite_service.list_favorites(admin) == []

    def test_user_list_never_empty_because_of_the_seeded_admin(self, app):
        admin = app.auth_service.login("admin", "Admin12345!")
        assert [u.login for u in app.user_management_service.list_users(admin)] == ["admin"]

    def test_admin_login_is_the_only_event_in_a_fresh_system(self, app):
        admin = app.auth_service.login("admin", "Admin12345!")
        events = app.event_log_service.list_events(admin)
        assert len(events) == 1 and events[0].event_type.value == "user_logged_in"

    def test_filter_that_matches_nothing_returns_an_empty_list(self, app, repository_factory):
        repository_factory.create_material_repository().add(make_material(0, title="Лекция"))
        assert app.search_service.search(MaterialFilter(query="несуществующееслово")) == []


# --- Поиск по датам ----------------------------------------------------------------------------


class TestDateRangeEdges:
    """Период «с … по …» включает обе даты целиком, границы сутки — в часовом поясе приложения."""

    MSK = timezone(timedelta(hours=3))

    @pytest.fixture
    def service(self, repository_factory):
        return SearchService(repository_factory.create_material_repository(), self.MSK)

    @pytest.fixture
    def stamped(self, repository_factory, author):
        repo = repository_factory.create_material_repository()

        def add(title: str, moment: datetime) -> None:
            material = make_material(0, title=title)
            material.uploaded_at = moment
            repo.add(material)

        add("до полуночи", datetime(2026, 5, 1, 23, 59, 59, 999999, tzinfo=self.MSK))
        add("ровно в полночь", datetime(2026, 5, 2, 0, 0, 0, tzinfo=self.MSK))
        add("конец дня", datetime(2026, 5, 2, 23, 59, 59, 999999, tzinfo=self.MSK))
        add("следующий день", datetime(2026, 5, 3, 0, 0, 0, tzinfo=self.MSK))

    def titles(self, service, **period):
        found = service.search(MaterialFilter(**period), SortField.UPLOAD_DATE, SortOrder.ASCENDING)
        return [m.title for m in found]

    def test_single_day_includes_both_edges_and_nothing_else(self, service, stamped):
        day = date(2026, 5, 2)
        found = self.titles(service, uploaded_on_or_after=day, uploaded_on_or_before=day)
        assert found == ["ровно в полночь", "конец дня"]

    def test_only_lower_bound(self, service, stamped):
        assert self.titles(service, uploaded_on_or_after=date(2026, 5, 3)) == ["следующий день"]

    def test_only_upper_bound(self, service, stamped):
        assert self.titles(service, uploaded_on_or_before=date(2026, 5, 1)) == ["до полуночи"]

    def test_maximum_date_does_not_overflow(self, service, stamped):
        assert len(self.titles(service, uploaded_on_or_before=date.max)) == 4


# --- Размер файла ------------------------------------------------------------------------------


class TestFileSizeEdges:
    @pytest.mark.parametrize(("size", "accepted"), [(0, True), (9, True), (10, True), (11, False)])
    def test_handler_accepts_exactly_the_maximum(self, tmp_path, size, accepted):
        file = tmp_path / "f.pdf"
        file.write_bytes(b"x" * size)
        handler = FileSizeHandler(max_size_bytes=10)
        if accepted:
            handler.handle(FileCheck(file, FileType.PDF))
        else:
            with pytest.raises(FileTooLargeError):
                handler.handle(FileCheck(file, FileType.PDF))

    def test_the_real_limit_is_one_hundred_megabytes(self):
        assert MAX_FILE_SIZE_BYTES == 100 * 1024 * 1024


# --- Время: сроки токенов и кодов --------------------------------------------------------------


class TestExpiryEdges:
    @pytest.fixture
    def opened(self, app, clock):
        return app.session_service.open_session("admin", "Admin12345!")

    def test_token_is_valid_a_second_before_expiry(self, app, clock, opened):
        clock.advance(hours=AUTH_TOKEN_TTL_HOURS, seconds=-1)
        assert app.session_service.authenticate(opened.token).login == "admin"

    def test_token_is_rejected_at_the_exact_moment_of_expiry(self, app, clock, opened):
        clock.advance(hours=AUTH_TOKEN_TTL_HOURS)
        with pytest.raises(InvalidTokenError):
            app.session_service.authenticate(opened.token)

    def test_expired_token_is_gone_for_good(self, app, clock, opened):
        clock.advance(hours=AUTH_TOKEN_TTL_HOURS, seconds=1)
        with pytest.raises(InvalidTokenError):
            app.session_service.authenticate(opened.token)
        clock.current -= timedelta(hours=1)  # время «откатилось», но токен уже удалён
        with pytest.raises(InvalidTokenError):
            app.session_service.authenticate(opened.token)

    @pytest.fixture
    def reset_code(self, app, mailbox):
        admin = app.auth_service.login("admin", "Admin12345!")
        app.auth_service.request_password_reset(admin.email)
        body = mailbox.sent[-1][2]
        return body.split("Код для восстановления пароля: ")[1].split("\n")[0]

    def test_reset_code_works_a_second_before_expiry(self, app, clock, reset_code):
        clock.advance(minutes=RESET_TOKEN_TTL_MINUTES, seconds=-1)
        assert app.auth_service.check_reset_token(reset_code).login == "admin"

    def test_reset_code_still_works_at_the_exact_moment_of_expiry(self, app, clock, reset_code):
        clock.advance(minutes=RESET_TOKEN_TTL_MINUTES)
        assert app.auth_service.check_reset_token(reset_code).login == "admin"

    def test_reset_code_fails_one_microsecond_later(self, app, clock, reset_code):
        clock.advance(minutes=RESET_TOKEN_TTL_MINUTES, microseconds=1)
        with pytest.raises(InvalidResetTokenError):
            app.auth_service.check_reset_token(reset_code)


# --- Правки материала: предел истории ----------------------------------------------------------


class TestRevisionHistoryLimit:
    def test_history_keeps_exactly_the_maximum_number_of_edits(self, repository_factory):
        from src.domain.models import MaterialMemento

        revisions = repository_factory.create_material_revision_repository()
        for index in range(MAX_REVISIONS_PER_MATERIAL + 1):
            revisions.push(1, MaterialMemento(f"версия {index}", "", 1, 1))
        popped = []
        while (memento := revisions.pop(1)) is not None:
            popped.append(memento.title)
        assert len(popped) == MAX_REVISIONS_PER_MATERIAL
        assert popped[0] == f"версия {MAX_REVISIONS_PER_MATERIAL}"  # самая свежая
        assert popped[-1] == "версия 1"  # самая старая («версия 0» вытеснена)

    def test_history_of_a_material_without_edits_is_empty(self, repository_factory):
        revisions = repository_factory.create_material_revision_repository()
        assert revisions.pop(1) is None
        assert revisions.has_history(1) is False


def test_topic_and_material_models_accept_minimal_values():
    assert Topic(id=1, name="а", discipline_id=1).name == "а"
    assert Role.STUDENT.label == "студент"
    assert make_material(1).file_size_bytes >= 0
