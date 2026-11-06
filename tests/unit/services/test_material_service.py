"""Юнит-тесты MaterialService с подставным файловым хранилищем."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.domain.enums import EventType, FileType, Role
from src.domain.exceptions import (
    DisciplineDoesNotExistError,
    EmptyFieldError,
    FieldTooLongError,
    ForeignMaterialAccessError,
    MaterialAccessError,
    MaterialFileNotStoredError,
    MaterialNotFoundError,
    NothingToUndoError,
    SourceFileNotFoundError,
    TopicDisciplineMismatchError,
    TopicDoesNotExistError,
    UnsupportedFileTypeError,
)
from src.domain.models import Discipline, Topic
from src.domain.validation import MAX_TITLE_LENGTH
from src.services.file_validation import build_file_validation_chain
from src.services.material_service import MaterialService
from tests.fakes import make_material

pytestmark = pytest.mark.usefixtures("reference_data")


@pytest.fixture
def service(material_repo, discipline_repo, topic_repo, revision_repo, event_log, file_storage):
    return MaterialService(
        material_repo, discipline_repo, topic_repo, revision_repo, event_log, file_storage
    )


@pytest.fixture
def catalog(discipline_repo, topic_repo):
    math = discipline_repo.add(Discipline(0, "Математика"))
    physics = discipline_repo.add(Discipline(0, "Физика"))
    algebra = topic_repo.add(Topic(0, "Алгебра", math.id))
    algebra2 = topic_repo.add(Topic(0, "Геометрия", math.id))
    mechanics = topic_repo.add(Topic(0, "Механика", physics.id))
    return math, physics, algebra, algebra2, mechanics


@pytest.fixture
def source(tmp_path):
    path = tmp_path / "lecture.pdf"
    path.write_bytes(b"12345")
    return path


@pytest.fixture
def created(service, teacher_user, catalog, source):
    math, _, algebra, *_ = catalog
    return service.create_material(teacher_user, "Лекция", "Описание", math.id, algebra.id, source)


def _events(event_log, admin_user):
    return [(e.event_type, e.target) for e in event_log.list_events(admin_user)]


class TestCreate:
    def test_stores_file_and_metadata(self, created, file_storage, teacher_user):
        assert created.id == 1
        assert created.file_type is FileType.PDF
        assert created.file_size_bytes == 5
        assert created.author_id == teacher_user.id
        assert created.storage_path in file_storage.files

    def test_title_and_description_are_trimmed(self, service, teacher_user, catalog, source):
        math, _, algebra, *_ = catalog
        material = service.create_material(
            teacher_user, "  Лекция  ", "  текст  ", math.id, algebra.id, source
        )
        assert (material.title, material.description) == ("Лекция", "текст")

    def test_logs_creation_and_upload(self, created, event_log, admin_user):
        assert _events(event_log, admin_user) == [
            (EventType.MATERIAL_CREATED, "Лекция"),
            (EventType.FILE_UPLOADED, "lecture.pdf"),
        ]

    def test_admin_may_create(self, service, admin_user, catalog, source):
        math, _, algebra, *_ = catalog
        service.create_material(admin_user, "T", "", math.id, algebra.id, source)

    def test_student_forbidden(self, service, student_user, catalog, source):
        math, _, algebra, *_ = catalog
        with pytest.raises(MaterialAccessError):
            service.create_material(student_user, "T", "", math.id, algebra.id, source)

    def test_empty_description_is_allowed(self, service, teacher_user, catalog, source):
        math, _, algebra, *_ = catalog
        assert (
            service.create_material(
                teacher_user, "T", "   ", math.id, algebra.id, source
            ).description
            == ""
        )

    @pytest.mark.parametrize("title", ["", "   "])
    def test_blank_title(self, service, teacher_user, catalog, source, title):
        math, _, algebra, *_ = catalog
        with pytest.raises(EmptyFieldError):
            service.create_material(teacher_user, title, "", math.id, algebra.id, source)

    def test_title_length_boundary(self, service, teacher_user, catalog, source):
        math, _, algebra, *_ = catalog
        service.create_material(
            teacher_user, "a" * MAX_TITLE_LENGTH, "", math.id, algebra.id, source
        )
        with pytest.raises(FieldTooLongError):
            service.create_material(
                teacher_user, "a" * (MAX_TITLE_LENGTH + 1), "", math.id, algebra.id, source
            )

    def test_unknown_discipline(self, service, teacher_user, catalog, source):
        _, _, algebra, *_ = catalog
        with pytest.raises(DisciplineDoesNotExistError):
            service.create_material(teacher_user, "T", "", 999, algebra.id, source)

    def test_unknown_topic(self, service, teacher_user, catalog, source):
        math, *_ = catalog
        with pytest.raises(TopicDoesNotExistError):
            service.create_material(teacher_user, "T", "", math.id, 999, source)

    def test_topic_from_other_discipline(self, service, teacher_user, catalog, source):
        math, _, _, _, mechanics = catalog
        with pytest.raises(TopicDisciplineMismatchError):
            service.create_material(teacher_user, "T", "", math.id, mechanics.id, source)

    def test_nothing_is_stored_when_validation_fails(
        self, service, teacher_user, catalog, tmp_path, file_storage, material_repo
    ):
        math, _, algebra, *_ = catalog
        bad = tmp_path / "bad.exe"
        bad.write_bytes(b"x")
        with pytest.raises(UnsupportedFileTypeError):
            service.create_material(teacher_user, "T", "", math.id, algebra.id, bad)
        assert file_storage.files == {}
        assert material_repo.list_all() == []

    def test_missing_source_file(self, service, teacher_user, catalog, tmp_path):
        math, _, algebra, *_ = catalog
        with pytest.raises(SourceFileNotFoundError):
            service.create_material(
                teacher_user, "T", "", math.id, algebra.id, tmp_path / "ghost.pdf"
            )

    def test_custom_validation_chain_is_used(
        self,
        material_repo,
        discipline_repo,
        topic_repo,
        revision_repo,
        event_log,
        file_storage,
        teacher_user,
        catalog,
        source,
    ):
        strict = build_file_validation_chain({FileType.PNG}, 10)
        service = MaterialService(
            material_repo,
            discipline_repo,
            topic_repo,
            revision_repo,
            event_log,
            file_storage,
            strict,
        )
        math, _, algebra, *_ = catalog
        with pytest.raises(UnsupportedFileTypeError):
            service.create_material(teacher_user, "T", "", math.id, algebra.id, source)


class TestValidateSourceFile:
    @pytest.mark.parametrize("name", ["a.pdf", "a.DOCX", "a.pptx", "a.xlsx", "a.jpg", "a.png"])
    def test_allowed(self, service, tmp_path, name):
        path = tmp_path / name
        path.write_bytes(b"x")
        assert service.validate_source_file(path).value == name.rsplit(".", 1)[1].lower()

    def test_not_allowed(self, service, tmp_path):
        path = tmp_path / "a.gif"
        path.write_bytes(b"x")
        with pytest.raises(UnsupportedFileTypeError):
            service.validate_source_file(path)


class TestEdit:
    def test_partial_edit_changes_only_given_fields(self, service, teacher_user, created):
        edited = service.edit_material(teacher_user, created.id, title="Новое")
        assert edited.title == "Новое"
        assert edited.description == "Описание"

    def test_empty_description_clears_it(self, service, teacher_user, created):
        assert service.edit_material(teacher_user, created.id, description="  ").description == ""

    def test_none_means_unchanged(self, service, teacher_user, created):
        edited = service.edit_material(teacher_user, created.id)
        assert edited.title == "Лекция"

    def test_logs_edit(self, service, teacher_user, created, event_log, admin_user):
        service.edit_material(teacher_user, created.id, title="Новое")
        assert _events(event_log, admin_user)[-1] == (EventType.MATERIAL_EDITED, "Новое")

    def test_change_topic_within_discipline(self, service, teacher_user, created, catalog):
        *_, algebra2, _ = catalog
        assert (
            service.edit_material(teacher_user, created.id, topic_id=algebra2.id).topic_id
            == algebra2.id
        )

    def test_change_discipline_and_topic_together(self, service, teacher_user, created, catalog):
        _, physics, _, _, mechanics = catalog
        edited = service.edit_material(
            teacher_user, created.id, discipline_id=physics.id, topic_id=mechanics.id
        )
        assert (edited.discipline_id, edited.topic_id) == (physics.id, mechanics.id)

    def test_change_discipline_alone_fails_on_mismatch(
        self, service, teacher_user, created, catalog
    ):
        _, physics, *_ = catalog
        with pytest.raises(TopicDisciplineMismatchError):
            service.edit_material(teacher_user, created.id, discipline_id=physics.id)

    def test_failed_edit_leaves_material_untouched(self, service, teacher_user, created):
        with pytest.raises(EmptyFieldError):
            service.edit_material(teacher_user, created.id, title=" ", description="X")
        current = service.get_material(created.id)
        assert (current.title, current.description) == ("Лекция", "Описание")

    def test_other_teacher_forbidden(self, service, other_teacher, created):
        with pytest.raises(ForeignMaterialAccessError):
            service.edit_material(other_teacher, created.id, title="X")

    def test_admin_may_edit_foreign(self, service, admin_user, created):
        assert service.edit_material(admin_user, created.id, title="X").title == "X"

    def test_student_forbidden(self, service, student_user, created):
        with pytest.raises(MaterialAccessError):
            service.edit_material(student_user, created.id, title="X")

    def test_unknown_material(self, service, teacher_user):
        with pytest.raises(MaterialNotFoundError):
            service.edit_material(teacher_user, 999, title="X")

    def test_file_is_not_replaced(self, service, teacher_user, created, file_storage):
        before = dict(file_storage.files)
        service.edit_material(teacher_user, created.id, title="X")
        assert file_storage.files == before


class TestUndo:
    def test_restores_previous_values(self, service, teacher_user, created):
        service.edit_material(teacher_user, created.id, title="Новое", description="Другое")
        restored = service.undo_last_edit(teacher_user, created.id)
        assert (restored.title, restored.description) == ("Лекция", "Описание")

    def test_undo_is_logged(self, service, teacher_user, created, event_log, admin_user):
        service.edit_material(teacher_user, created.id, title="Новое")
        service.undo_last_edit(teacher_user, created.id)
        assert _events(event_log, admin_user)[-1] == (EventType.MATERIAL_EDIT_UNDONE, "Лекция")

    def test_nothing_to_undo(self, service, teacher_user, created):
        with pytest.raises(NothingToUndoError):
            service.undo_last_edit(teacher_user, created.id)

    def test_cannot_undo_twice_after_single_edit(self, service, teacher_user, created):
        service.edit_material(teacher_user, created.id, title="Новое")
        service.undo_last_edit(teacher_user, created.id)
        with pytest.raises(NothingToUndoError):
            service.undo_last_edit(teacher_user, created.id)

    def test_can_undo_flag(self, service, teacher_user, created):
        assert service.can_undo(created.id) is False
        service.edit_material(teacher_user, created.id, title="Новое")
        assert service.can_undo(created.id) is True

    def test_failed_edit_creates_no_snapshot(self, service, teacher_user, created):
        with pytest.raises(EmptyFieldError):
            service.edit_material(teacher_user, created.id, title="")
        assert service.can_undo(created.id) is False

    def test_foreign_teacher_forbidden(self, service, teacher_user, other_teacher, created):
        service.edit_material(teacher_user, created.id, title="Новое")
        with pytest.raises(ForeignMaterialAccessError):
            service.undo_last_edit(other_teacher, created.id)

    def test_unknown_material(self, service, teacher_user):
        with pytest.raises(MaterialNotFoundError):
            service.undo_last_edit(teacher_user, 404)

    def test_history_is_cleared_on_delete(self, service, teacher_user, created):
        service.edit_material(teacher_user, created.id, title="Новое")
        service.delete_material(teacher_user, created.id)
        assert service.can_undo(created.id) is False


class TestDelete:
    def test_deletes_record_and_file(self, service, teacher_user, created, file_storage):
        service.delete_material(teacher_user, created.id)
        assert service.list_materials() == []
        assert created.storage_path in file_storage.deleted

    def test_logs_deletion(self, service, teacher_user, created, event_log, admin_user):
        service.delete_material(teacher_user, created.id)
        assert _events(event_log, admin_user)[-1] == (EventType.MATERIAL_DELETED, "Лекция")

    def test_other_teacher_forbidden_and_nothing_deleted(
        self, service, other_teacher, created, file_storage
    ):
        with pytest.raises(ForeignMaterialAccessError):
            service.delete_material(other_teacher, created.id)
        assert service.get_material(created.id)
        assert file_storage.deleted == []

    def test_admin_may_delete_foreign(self, service, admin_user, created):
        service.delete_material(admin_user, created.id)
        assert service.list_materials() == []

    def test_unknown(self, service, teacher_user):
        with pytest.raises(MaterialNotFoundError):
            service.delete_material(teacher_user, 1)

    def test_material_without_stored_file_does_not_call_storage(
        self, service, teacher_user, material_repo, file_storage
    ):
        material = make_material(0, author_id=teacher_user.id)
        material.storage_path = ""
        material_repo.add(material)
        service.delete_material(teacher_user, material.id)
        assert file_storage.deleted == []


class TestListing:
    def test_list_materials_empty(self, service):
        assert service.list_materials() == []

    def test_list_by_author(self, service, material_repo, teacher_user, other_teacher):
        mine = material_repo.add(make_material(0, author_id=teacher_user.id))
        material_repo.add(make_material(0, author_id=other_teacher.id))
        assert [m.id for m in service.list_by_author(teacher_user)] == [mine.id]

    @pytest.mark.parametrize(
        ("role_fixture", "expected"), [("admin_user", 2), ("teacher_user", 1), ("student_user", 0)]
    )
    def test_list_editable_by_role(
        self, service, material_repo, teacher_user, other_teacher, request, role_fixture, expected
    ):
        material_repo.add(make_material(0, author_id=teacher_user.id))
        material_repo.add(make_material(0, author_id=other_teacher.id))
        user = request.getfixturevalue(role_fixture)
        assert len(service.list_editable(user)) == expected

    def test_get_unknown(self, service):
        with pytest.raises(MaterialNotFoundError):
            service.get_material(1)


class TestFileAccess:
    def test_resolve_path(self, service, created):
        assert service.resolve_file_path(created.id) == Path(created.storage_path)

    def test_resolve_without_stored_file(self, service, material_repo):
        material = make_material(0)
        material.storage_path = ""
        material_repo.add(material)
        with pytest.raises(MaterialFileNotStoredError):
            service.resolve_file_path(material.id)

    def test_resolve_unknown(self, service):
        with pytest.raises(MaterialNotFoundError):
            service.resolve_file_path(5)

    def test_record_download_logs_by_downloader(
        self, service, created, student_user, event_log, admin_user
    ):
        service.record_download(student_user, created.id)
        event = event_log.list_events(admin_user)[-1]
        assert (event.user_id, event.event_type, event.target) == (
            student_user.id,
            EventType.MATERIAL_DOWNLOADED,
            "Лекция",
        )

    def test_record_download_unknown(self, service, student_user):
        with pytest.raises(MaterialNotFoundError):
            service.record_download(student_user, 5)


def test_roles_used_in_fixtures_are_consistent(admin_user, teacher_user, student_user):
    assert (admin_user.role, teacher_user.role, student_user.role) == (
        Role.ADMIN,
        Role.TEACHER,
        Role.STUDENT,
    )
