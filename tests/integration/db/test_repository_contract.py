"""Контракт репозиториев, на который рассчитаны сервисы, проверенный на PostgreSQL."""

from __future__ import annotations

from datetime import UTC, datetime

from src.domain.enums import AccountStatus, EventType, Role
from src.domain.models import Discipline, Event, Favorite, Topic
from tests.conftest import new_material, new_user


class TestUsers:
    def test_add_assigns_id_and_returns_the_same_object(self, repos):
        user = new_user("bob")
        saved = repos.users.add(user)
        assert saved.id > 0
        assert saved is user

    def test_get_by_id_roundtrip(self, repos):
        saved = repos.users.add(new_user("bob", Role.STUDENT))
        found = repos.users.get_by_id(saved.id)
        assert found == saved
        assert found.role is Role.STUDENT and found.status is AccountStatus.ACTIVE

    def test_missing_user_is_none(self, repos):
        assert repos.users.get_by_id(999) is None
        assert repos.users.get_by_login("nobody") is None
        assert repos.users.get_by_email("no@example.org") is None

    def test_login_lookup_is_exact(self, repos):
        repos.users.add(new_user("Bob"))
        assert repos.users.get_by_login("Bob") is not None
        assert repos.users.get_by_login("bob") is None

    def test_email_lookup_ignores_case(self, repos):
        saved = repos.users.add(new_user("bob", email="Bob.Smith@Example.ORG"))
        assert repos.users.get_by_email("bob.smith@example.org") == saved

    def test_list_all_keeps_insertion_order(self, repos):
        first = repos.users.add(new_user("a"))
        second = repos.users.add(new_user("b"))
        assert [u.id for u in repos.users.list_all()] == [first.id, second.id]

    def test_update_persists_changes(self, repos):
        saved = repos.users.add(new_user("bob", Role.STUDENT))
        saved.role = Role.TEACHER
        saved.status = AccountStatus.BLOCKED
        saved.password_hash = "new-hash"
        repos.users.update(saved)
        found = repos.users.get_by_id(saved.id)
        assert (found.role, found.status, found.password_hash) == (
            Role.TEACHER,
            AccountStatus.BLOCKED,
            "new-hash",
        )

    def test_delete_removes_user(self, repos):
        saved = repos.users.add(new_user("bob"))
        repos.users.delete(saved.id)
        assert repos.users.get_by_id(saved.id) is None

    def test_delete_missing_user_is_not_an_error(self, repos):
        repos.users.delete(999)


class TestDisciplinesAndTopics:
    def test_discipline_roundtrip_and_case_insensitive_name(self, repos):
        saved = repos.disciplines.add(Discipline(0, "Математика"))
        assert repos.disciplines.get_by_id(saved.id) == saved
        assert repos.disciplines.get_by_name("МАТЕМАТИКА") == saved
        assert repos.disciplines.get_by_name("Физика") is None

    def test_discipline_rename(self, repos):
        saved = repos.disciplines.add(Discipline(0, "Мат"))
        saved.name = "Математика"
        repos.disciplines.update(saved)
        assert repos.disciplines.get_by_id(saved.id).name == "Математика"

    def test_list_disciplines(self, repos):
        a = repos.disciplines.add(Discipline(0, "А"))
        b = repos.disciplines.add(Discipline(0, "Б"))
        assert repos.disciplines.list_all() == [a, b]

    def test_topic_lookup_is_scoped_to_discipline(self, repos):
        math = repos.disciplines.add(Discipline(0, "Математика"))
        phys = repos.disciplines.add(Discipline(0, "Физика"))
        algebra = repos.topics.add(Topic(0, "Введение", math.id))
        repos.topics.add(Topic(0, "Введение", phys.id))
        assert repos.topics.get_by_name(math.id, "введение") == algebra
        assert repos.topics.get_by_name(math.id, "Оптика") is None
        assert repos.topics.list_by_discipline(math.id) == [algebra]

    def test_topic_rename(self, repos):
        d = repos.disciplines.add(Discipline(0, "Математика"))
        topic = repos.topics.add(Topic(0, "Алг", d.id))
        topic.name = "Алгебра"
        repos.topics.update(topic)
        assert repos.topics.get_by_id(topic.id).name == "Алгебра"


class TestMaterials:
    def test_roundtrip(self, repos, seeded):
        saved = repos.materials.add(new_material(seeded.topic, seeded.teacher.id))
        found = repos.materials.get_by_id(saved.id)
        assert found == saved
        assert found.author_id == seeded.teacher.id

    def test_update_persists_editable_fields(self, repos, seeded):
        saved = repos.materials.add(new_material(seeded.topic, seeded.teacher.id))
        other_topic = repos.topics.add(Topic(0, "Геометрия", seeded.discipline.id))
        saved.title = "Новое название"
        saved.description = "Новое описание"
        saved.topic_id = other_topic.id
        repos.materials.update(saved)
        found = repos.materials.get_by_id(saved.id)
        assert (found.title, found.description, found.topic_id) == (
            "Новое название",
            "Новое описание",
            other_topic.id,
        )

    def test_list_all_and_delete(self, repos, seeded):
        a = repos.materials.add(new_material(seeded.topic, seeded.teacher.id, "А"))
        b = repos.materials.add(new_material(seeded.topic, seeded.teacher.id, "Б"))
        assert [m.id for m in repos.materials.list_all()] == [a.id, b.id]
        repos.materials.delete(a.id)
        assert [m.id for m in repos.materials.list_all()] == [b.id]

    def test_missing_material_is_none(self, repos):
        assert repos.materials.get_by_id(999) is None

    def test_uploaded_at_is_preserved(self, repos, seeded):
        material = new_material(seeded.topic, seeded.teacher.id)
        material.uploaded_at = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)
        saved = repos.materials.add(material)
        assert repos.materials.get_by_id(saved.id).uploaded_at == material.uploaded_at

    def test_material_without_author(self, repos, seeded):
        saved = repos.materials.add(new_material(seeded.topic, None))
        assert repos.materials.get_by_id(saved.id).author_id is None


class TestFavorites:
    def test_add_exists_list_remove(self, repos, seeded):
        material = repos.materials.add(new_material(seeded.topic, seeded.teacher.id))
        student = repos.users.add(new_user("student", Role.STUDENT))
        assert not repos.favorites.exists(student.id, material.id)
        repos.favorites.add(Favorite(student.id, material.id))
        assert repos.favorites.exists(student.id, material.id)
        assert [f.material_id for f in repos.favorites.list_by_user(student.id)] == [material.id]
        repos.favorites.remove(student.id, material.id)
        assert not repos.favorites.exists(student.id, material.id)

    def test_remove_missing_favorite_is_not_an_error(self, repos):
        repos.favorites.remove(1, 1)

    def test_list_is_per_user(self, repos, seeded):
        material = repos.materials.add(new_material(seeded.topic, seeded.teacher.id))
        a = repos.users.add(new_user("a", Role.STUDENT))
        b = repos.users.add(new_user("b", Role.STUDENT))
        repos.favorites.add(Favorite(a.id, material.id))
        assert repos.favorites.list_by_user(b.id) == []


class TestEvents:
    def test_add_assigns_id_and_lists_oldest_first(self, repos, seeded):
        first = repos.events.add(Event(0, seeded.teacher.id, EventType.USER_LOGGED_IN, "teacher"))
        second = repos.events.add(Event(0, seeded.teacher.id, EventType.MATERIAL_CREATED, "T"))
        assert first.id > 0
        assert [e.id for e in repos.events.list_all()] == [first.id, second.id]

    def test_guest_event_has_no_user(self, repos):
        saved = repos.events.add(Event(0, None, EventType.USER_LOGIN_FAILED, "ghost"))
        assert repos.events.list_all()[0].user_id is None
        assert saved.event_type is EventType.USER_LOGIN_FAILED


class TestMissingRowsAndDeleteRules:
    """`update` меняет только существующие строки; удаление пользователя оставляет данные."""

    def test_update_of_missing_rows_changes_nothing(self, repos, seeded):
        ghost_user = new_user("ghost")
        ghost_user.id = 999
        repos.users.update(ghost_user)
        repos.disciplines.update(Discipline(999, "Нет"))
        repos.topics.update(Topic(999, "Нет", seeded.discipline.id))
        ghost_material = new_material(seeded.topic, seeded.teacher.id)
        ghost_material.id = 999
        repos.materials.update(ghost_material)
        assert repos.users.get_by_id(999) is None
        assert repos.disciplines.get_by_id(999) is None
        assert repos.topics.get_by_id(999) is None
        assert repos.materials.get_by_id(999) is None

    def test_delete_of_missing_material_is_not_an_error(self, repos):
        repos.materials.delete(999)

    def test_deleting_user_clears_author_and_event_user_but_keeps_rows(self, repos, seeded):
        material = repos.materials.add(new_material(seeded.topic, seeded.teacher.id))
        repos.events.add(Event(0, seeded.teacher.id, EventType.MATERIAL_CREATED, "T"))
        repos.users.delete(seeded.teacher.id)
        assert repos.materials.get_by_id(material.id).author_id is None
        assert repos.events.list_all()[0].user_id is None
