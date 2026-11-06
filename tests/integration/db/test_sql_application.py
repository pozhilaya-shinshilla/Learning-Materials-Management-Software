"""Всё приложение целиком (сервисы + репозитории) поверх PostgreSQL."""

from __future__ import annotations

import pytest

from src.bootstrap import ApplicationContext, build_application_context
from src.configs.settings import AdminSettings
from src.database.transaction import TransactionManager
from src.domain.enums import EventType, Role, SortField, SortOrder
from src.domain.exceptions import (
    AuthenticationError,
    DuplicateDisciplineError,
    DuplicateEmailError,
    DuplicateLoginError,
    DuplicateTopicError,
    ForeignMaterialAccessError,
)
from src.domain.models import User
from src.repositories.factory import SQLAlchemyRepositoryFactory
from src.services.search_service import MaterialFilter
from tests.integration.conftest import RecordingEmailSender


def _build(session_factory, tmp_path) -> ApplicationContext:
    """Собрать приложение так же, как `main.py`: сессии и коммиты ведёт TransactionManager."""
    transactions = TransactionManager(session_factory)
    return build_application_context(
        email_sender=RecordingEmailSender(),
        upload_root=tmp_path / "uploads",
        admin=AdminSettings("admin", "admin@example.org", "Admin12345!"),
        repository_factory=SQLAlchemyRepositoryFactory(transactions.session),
        transaction_scope=transactions.transaction,
        transaction_hooks=transactions,
    )


@pytest.fixture
def context(clean_db, session_factory, tmp_path) -> ApplicationContext:
    return _build(session_factory, tmp_path)


@pytest.fixture
def admin(context) -> User:
    return context.auth_service.login("admin", "Admin12345!")


def _register(context, admin, login, role=Role.TEACHER) -> User:
    return context.user_management_service.create_user(
        admin, login, f"{login}@example.org", "Password123!", role
    )


def _file(tmp_path, name="a.pdf"):
    path = tmp_path / name
    path.write_bytes(b"x")
    return path


@pytest.fixture
def teacher(context, admin):
    return _register(context, admin, "teacher1")


@pytest.fixture
def topic(context, teacher):
    discipline = context.catalog_service.create_discipline(teacher, "Математика")
    return context.catalog_service.create_topic(teacher, "Алгебра", discipline.id)


def _material(context, teacher, topic, tmp_path, title="Лекция", name="a.pdf"):
    return context.material_service.create_material(
        teacher, title, "описание", topic.discipline_id, topic.id, _file(tmp_path, name)
    )


class TestStartup:
    def test_admin_is_seeded_once(self, context, session_factory, tmp_path):
        again = _build(session_factory, tmp_path)
        admins = [
            u
            for u in again.user_management_service.list_users(
                again.auth_service.login("admin", "Admin12345!")
            )
        ]
        assert len(admins) == 1 and admins[0].role is Role.ADMIN

    def test_wrong_password_is_logged_as_guest(self, context, admin):
        with pytest.raises(AuthenticationError):
            context.auth_service.login("ghost", "Whatever123!")
        failed = [
            e
            for e in context.event_log_service.list_events(admin)
            if e.event_type is EventType.USER_LOGIN_FAILED
        ]
        assert [(e.user_id, e.target) for e in failed] == [(None, "ghost")]


class TestUsersAndCatalog:
    def test_duplicates_are_detected_ignoring_case(self, context, admin, teacher):
        with pytest.raises(DuplicateLoginError):
            _register(context, admin, "teacher1")
        with pytest.raises(DuplicateEmailError):
            context.user_management_service.create_user(
                admin, "other", "TEACHER1@example.org", "Password123!", Role.STUDENT
            )

    def test_duplicate_catalog_names_are_detected_ignoring_case(self, context, teacher, topic):
        with pytest.raises(DuplicateDisciplineError):
            context.catalog_service.create_discipline(teacher, "МАТЕМАТИКА")
        with pytest.raises(DuplicateTopicError):
            context.catalog_service.create_topic(teacher, "алгебра", topic.discipline_id)

    def test_rename_discipline_is_persisted(self, context, teacher, topic):
        context.catalog_service.rename_discipline(
            teacher, topic.discipline_id, "Алгебра и геометрия"
        )
        names = [d.name for d in context.catalog_service.list_disciplines()]
        assert names == ["Алгебра и геометрия"]

    def test_role_and_block_changes_are_persisted(self, context, admin, teacher):
        context.user_management_service.change_role(admin, teacher.id, Role.STUDENT)
        context.user_management_service.set_blocked(admin, teacher.id, True)
        stored = context.auth_service.ensure_session_active  # noqa: F841
        users = {u.login: u for u in context.user_management_service.list_users(admin)}
        assert users["teacher1"].role is Role.STUDENT
        assert users["teacher1"].is_active() is False


class TestMaterials:
    def test_create_edit_undo_delete(self, context, teacher, topic, tmp_path):
        material = _material(context, teacher, topic, tmp_path)
        edited = context.material_service.edit_material(teacher, material.id, title="Новая")
        assert context.material_service.get_material(material.id).title == "Новая"
        context.material_service.undo_last_edit(teacher, material.id)
        assert context.material_service.get_material(material.id).title == "Лекция"
        context.material_service.delete_material(teacher, material.id)
        assert context.material_service.list_materials() == []
        assert edited.id == material.id

    def test_search_and_sort(self, context, teacher, topic, tmp_path):
        _material(context, teacher, topic, tmp_path, "Бета", "b.pdf")
        _material(context, teacher, topic, tmp_path, "Линейные уравнения", "a.pdf")
        by_title = context.search_service.search(
            None, sort_field=SortField.TITLE, sort_order=SortOrder.ASCENDING
        )
        assert [m.title for m in by_title] == ["Бета", "Линейные уравнения"]
        found = context.search_service.search(MaterialFilter(query="уравнение"))
        assert [m.title for m in found] == ["Линейные уравнения"]

    def test_newest_first_by_default(self, context, teacher, topic, tmp_path):
        first = _material(context, teacher, topic, tmp_path, "Первый", "a.pdf")
        second = _material(context, teacher, topic, tmp_path, "Второй", "b.pdf")
        assert [m.id for m in context.search_service.search()] == [second.id, first.id]

    def test_journal_records_the_flow(self, context, admin, teacher, topic, tmp_path):
        _material(context, teacher, topic, tmp_path)
        types = [e.event_type for e in context.event_log_service.list_events(admin)]
        assert EventType.MATERIAL_CREATED in types and EventType.FILE_UPLOADED in types


class TestFavorites:
    def test_add_list_remove(self, context, admin, teacher, topic, tmp_path):
        student = _register(context, admin, "student1", Role.STUDENT)
        material = _material(context, teacher, topic, tmp_path)
        context.favorite_service.add_favorite(student, material.id)
        assert [m.id for m in context.favorite_service.list_favorites(student)] == [material.id]
        context.favorite_service.remove_favorite(student, material.id)
        assert context.favorite_service.list_favorites(student) == []

    def test_deleting_material_removes_favorites_in_database(
        self, context, admin, teacher, topic, tmp_path
    ):
        student = _register(context, admin, "student1", Role.STUDENT)
        material = _material(context, teacher, topic, tmp_path)
        context.favorite_service.add_favorite(student, material.id)
        context.material_service.delete_material(teacher, material.id)
        assert context.favorite_service.list_favorites(student) == []


class TestAuthorDeletion:
    """Решение из ER: автора можно удалить, материал остаётся, править его может админ."""

    def test_material_survives_and_has_no_author(self, context, admin, teacher, topic, tmp_path):
        material = _material(context, teacher, topic, tmp_path)
        context.material_service.list_materials()  # прогреть кеш материалов
        context.user_management_service.delete_user(admin, teacher.id)
        survivor = context.material_service.get_material(material.id)
        assert survivor.author_id is None
        assert context.material_service.list_materials()[0].author_id is None  # кеш сброшен

    def test_author_is_shown_as_deleted(self, context, admin, teacher, topic, tmp_path):
        material = _material(context, teacher, topic, tmp_path)
        context.user_management_service.delete_user(admin, teacher.id)
        author_id = context.material_service.get_material(material.id).author_id
        assert context.user_management_service.get_author_login(author_id) == "автор удалён"

    def test_other_teacher_cannot_edit_orphaned_material(
        self, context, admin, teacher, topic, tmp_path
    ):
        material = _material(context, teacher, topic, tmp_path)
        other = _register(context, admin, "teacher2")
        context.user_management_service.delete_user(admin, teacher.id)
        with pytest.raises(ForeignMaterialAccessError):
            context.material_service.edit_material(other, material.id, title="Чужое")

    def test_admin_can_edit_and_delete_orphaned_material(
        self, context, admin, teacher, topic, tmp_path
    ):
        material = _material(context, teacher, topic, tmp_path)
        context.user_management_service.delete_user(admin, teacher.id)
        context.material_service.edit_material(admin, material.id, title="Правка админа")
        assert context.material_service.list_editable(admin)[0].title == "Правка админа"
        context.material_service.delete_material(admin, material.id)
        assert context.material_service.list_materials() == []

    def test_journal_keeps_events_of_deleted_user(self, context, admin, teacher, topic, tmp_path):
        _material(context, teacher, topic, tmp_path)
        context.user_management_service.delete_user(admin, teacher.id)
        created = [
            e
            for e in context.event_log_service.list_events(admin)
            if e.event_type is EventType.MATERIAL_CREATED
        ]
        assert len(created) == 1 and created[0].user_id is None
