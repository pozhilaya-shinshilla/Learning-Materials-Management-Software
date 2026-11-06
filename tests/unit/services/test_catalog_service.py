"""Юнит-тесты CatalogService: дисциплины и темы."""

from __future__ import annotations

import pytest

from src.domain.enums import EventType
from src.domain.exceptions import (
    CatalogAccessError,
    DisciplineNotFoundError,
    DuplicateDisciplineError,
    DuplicateTopicError,
    EmptyFieldError,
    FieldTooLongError,
    NameUnchangedError,
    TopicNotFoundError,
    UnknownDisciplineError,
    UnknownTopicError,
)
from src.domain.validation import MAX_NAME_LENGTH
from src.services.catalog_service import CatalogService


@pytest.fixture
def service(discipline_repo, topic_repo, event_log) -> CatalogService:
    return CatalogService(discipline_repo, topic_repo, event_log)


def _events(event_log, admin_user):
    return [(e.event_type, e.target) for e in event_log.list_events(admin_user)]


class TestCreateDiscipline:
    def test_creates_trimmed_and_logs(self, service, teacher_user, event_log, admin_user):
        created = service.create_discipline(teacher_user, "  Математика  ")
        assert (created.id, created.name) == (1, "Математика")
        assert _events(event_log, admin_user) == [(EventType.DISCIPLINE_CREATED, "Математика")]

    def test_admin_can_create(self, service, admin_user):
        service.create_discipline(admin_user, "Физика")

    def test_student_cannot_create(self, service, student_user):
        with pytest.raises(CatalogAccessError):
            service.create_discipline(student_user, "Физика")

    @pytest.mark.parametrize("name", ["", "  ", "\t"])
    def test_blank_name(self, service, teacher_user, name):
        with pytest.raises(EmptyFieldError):
            service.create_discipline(teacher_user, name)

    def test_name_length_boundary(self, service, teacher_user):
        service.create_discipline(teacher_user, "a" * MAX_NAME_LENGTH)
        with pytest.raises(FieldTooLongError):
            service.create_discipline(teacher_user, "b" * (MAX_NAME_LENGTH + 1))

    def test_duplicate_ignoring_case_and_spaces(self, service, teacher_user):
        service.create_discipline(teacher_user, "Математика")
        with pytest.raises(DuplicateDisciplineError):
            service.create_discipline(teacher_user, "  МАТЕМАТИКА ")

    def test_rejected_creation_is_not_logged(self, service, teacher_user, event_log, admin_user):
        with pytest.raises(EmptyFieldError):
            service.create_discipline(teacher_user, "")
        assert event_log.list_events(admin_user) == []


class TestCreateTopic:
    @pytest.fixture
    def discipline(self, service, teacher_user):
        return service.create_discipline(teacher_user, "Математика")

    def test_creates_and_logs(self, service, teacher_user, discipline, event_log, admin_user):
        topic = service.create_topic(teacher_user, " Алгебра ", discipline.id)
        assert (topic.name, topic.discipline_id) == ("Алгебра", discipline.id)
        assert (EventType.TOPIC_CREATED, "Алгебра") in _events(event_log, admin_user)

    def test_unknown_discipline(self, service, teacher_user):
        with pytest.raises(UnknownDisciplineError):
            service.create_topic(teacher_user, "Алгебра", 999)

    def test_student_forbidden_before_lookup(self, service, student_user):
        with pytest.raises(CatalogAccessError):
            service.create_topic(student_user, "Алгебра", 999)

    def test_same_name_in_different_disciplines_is_allowed(self, service, teacher_user, discipline):
        other = service.create_discipline(teacher_user, "Физика")
        service.create_topic(teacher_user, "Введение", discipline.id)
        service.create_topic(teacher_user, "Введение", other.id)

    def test_duplicate_in_same_discipline(self, service, teacher_user, discipline):
        service.create_topic(teacher_user, "Введение", discipline.id)
        with pytest.raises(DuplicateTopicError):
            service.create_topic(teacher_user, "введение", discipline.id)

    def test_blank_name(self, service, teacher_user, discipline):
        with pytest.raises(EmptyFieldError):
            service.create_topic(teacher_user, " ", discipline.id)


class TestRename:
    @pytest.fixture
    def setup(self, service, teacher_user):
        discipline = service.create_discipline(teacher_user, "Математика")
        other = service.create_discipline(teacher_user, "Физика")
        topic = service.create_topic(teacher_user, "Алгебра", discipline.id)
        service.create_topic(teacher_user, "Геометрия", discipline.id)
        return discipline, other, topic

    def test_rename_discipline_and_log(self, service, teacher_user, setup, event_log, admin_user):
        discipline, _, _ = setup
        renamed = service.rename_discipline(teacher_user, discipline.id, "Матан")
        assert renamed.name == "Матан"
        assert (EventType.DISCIPLINE_RENAMED, "Математика -> Матан") in _events(
            event_log, admin_user
        )

    def test_rename_to_same_name(self, service, teacher_user, setup):
        discipline, _, _ = setup
        with pytest.raises(NameUnchangedError):
            service.rename_discipline(teacher_user, discipline.id, "Математика")

    def test_rename_changing_only_case_is_allowed(self, service, teacher_user, setup):
        discipline, _, _ = setup
        assert (
            service.rename_discipline(teacher_user, discipline.id, "МАТЕМАТИКА").name
            == "МАТЕМАТИКА"
        )

    def test_rename_to_other_existing_name(self, service, teacher_user, setup):
        discipline, _, _ = setup
        with pytest.raises(DuplicateDisciplineError):
            service.rename_discipline(teacher_user, discipline.id, "Физика")

    def test_rename_unknown_discipline(self, service, teacher_user):
        with pytest.raises(UnknownDisciplineError):
            service.rename_discipline(teacher_user, 999, "X")

    def test_rename_topic_and_log(self, service, teacher_user, setup, event_log, admin_user):
        _, _, topic = setup
        service.rename_topic(teacher_user, topic.id, "Линал")
        assert (EventType.TOPIC_RENAMED, "Алгебра -> Линал") in _events(event_log, admin_user)

    def test_rename_topic_to_same(self, service, teacher_user, setup):
        _, _, topic = setup
        with pytest.raises(NameUnchangedError):
            service.rename_topic(teacher_user, topic.id, "Алгебра")

    def test_rename_topic_duplicate_in_discipline(self, service, teacher_user, setup):
        _, _, topic = setup
        with pytest.raises(DuplicateTopicError):
            service.rename_topic(teacher_user, topic.id, "Геометрия")

    def test_rename_unknown_topic(self, service, teacher_user):
        with pytest.raises(UnknownTopicError):
            service.rename_topic(teacher_user, 999, "X")

    def test_student_cannot_rename(self, service, student_user, setup):
        discipline, _, topic = setup
        with pytest.raises(CatalogAccessError):
            service.rename_discipline(student_user, discipline.id, "X")
        with pytest.raises(CatalogAccessError):
            service.rename_topic(student_user, topic.id, "X")

    def test_failed_rename_keeps_old_name(self, service, teacher_user, setup):
        discipline, _, _ = setup
        with pytest.raises(DuplicateDisciplineError):
            service.rename_discipline(teacher_user, discipline.id, "Физика")
        assert service.get_discipline_by_name("Математика").id == discipline.id


class TestLookups:
    def test_get_discipline_by_name_ignores_case_and_spaces(self, service, teacher_user):
        created = service.create_discipline(teacher_user, "Математика")
        assert service.get_discipline_by_name("  математика ").id == created.id

    def test_missing_discipline_lists_available(self, service, teacher_user):
        service.create_discipline(teacher_user, "Математика")
        with pytest.raises(DisciplineNotFoundError, match="Математика"):
            service.get_discipline_by_name("Химия")

    def test_missing_discipline_when_catalog_empty(self, service):
        with pytest.raises(DisciplineNotFoundError, match="список пуст"):
            service.get_discipline_by_name("X")

    def test_get_topic_by_name(self, service, teacher_user):
        discipline = service.create_discipline(teacher_user, "Математика")
        created = service.create_topic(teacher_user, "Алгебра", discipline.id)
        assert service.get_topic_by_name(discipline.id, " алгебра ").id == created.id

    def test_missing_topic(self, service, teacher_user):
        discipline = service.create_discipline(teacher_user, "Математика")
        with pytest.raises(TopicNotFoundError, match="список пуст"):
            service.get_topic_by_name(discipline.id, "X")

    def test_list_topics_only_of_discipline(self, service, teacher_user):
        first = service.create_discipline(teacher_user, "A1")
        second = service.create_discipline(teacher_user, "B1")
        service.create_topic(teacher_user, "t1", first.id)
        service.create_topic(teacher_user, "t2", second.id)
        assert [t.name for t in service.list_topics(first.id)] == ["t1"]
        assert service.list_topics(999) == []

    def test_empty_catalog(self, service):
        assert service.list_disciplines() == []

    def test_describe_known_and_unknown(self, service, teacher_user):
        discipline = service.create_discipline(teacher_user, "Математика")
        topic = service.create_topic(teacher_user, "Алгебра", discipline.id)
        assert service.describe(discipline.id, topic.id) == "Математика / Алгебра"
        assert service.describe(999, 999) == "? / ?"
        assert service.describe(discipline.id, 999) == "Математика / ?"
