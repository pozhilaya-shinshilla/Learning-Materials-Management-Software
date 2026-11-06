"""Репозитории методички на ORM-моделях: тот же код, что в разделе 12, для моделей LMS."""

from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError

from src.database.models import (
    DisciplineEntity,
    EventEntity,
    MaterialEntity,
    TopicEntity,
    UserEntity,
)
from src.domain.enums import EventType, FileType, Role
from src.repositories.sqlalchemy import (
    DisciplineRepository,
    EventRepository,
    MaterialRepository,
    TopicRepository,
    UserRepository,
)


def _user(login: str, email: str | None = None) -> UserEntity:
    return UserEntity(
        login=login, email=email or f"{login}@x.org", password_hash="h", role=Role.TEACHER
    )


@pytest.fixture
def users(db_session) -> UserRepository:
    return UserRepository(db_session)


@pytest.fixture
def catalog(db_session):
    disciplines = DisciplineRepository(db_session)
    topics = TopicRepository(db_session)
    discipline = disciplines.add(DisciplineEntity(name="Математика"))
    topic = topics.add(TopicEntity(name="Алгебра", discipline_id=discipline.id))
    return disciplines, topics, discipline, topic


def _material(topic: TopicEntity, author: UserEntity | None, title: str = "Лекция"):
    return MaterialEntity(
        title=title,
        description="",
        discipline_id=topic.discipline_id,
        topic_id=topic.id,
        author_id=author.id if author else None,
        file_name="a.pdf",
        file_type=FileType.PDF,
        file_size_bytes=1,
        storage_path="p",
    )


class TestCrud:
    def test_add_flushes_and_assigns_id(self, users):
        user = users.add(_user("bob"))
        assert user.id is not None

    def test_get_by_id_and_missing(self, users):
        user = users.add(_user("bob"))
        assert users.get_by_id(user.id) is user
        assert users.get_by_id(999) is None

    def test_get_all_is_ordered_by_id(self, users):
        first, second = users.add(_user("a")), users.add(_user("b"))
        assert users.get_all() == [first, second]

    def test_update_flushes_changes(self, users, db_session):
        user = users.add(_user("bob"))
        user.login = "robert"
        users.update(user)
        db_session.expire_all()
        assert users.get_by_id(user.id).login == "robert"

    def test_delete_removes_row(self, users):
        user = users.add(_user("bob"))
        users.delete(user)
        assert users.get_by_id(user.id) is None

    def test_flush_raises_integrity_error_inside_add(self, users):
        users.add(_user("bob", "a@x.org"))
        with pytest.raises(IntegrityError, match="uq_users_login"):
            users.add(_user("bob", "b@x.org"))


class TestSpecificQueries:
    def test_user_lookups(self, users):
        user = users.add(_user("Bob", "Bob@Example.org"))
        assert users.get_by_login("Bob") is user and users.get_by_login("bob") is None
        assert users.get_by_email("BOB@example.ORG") is user

    def test_catalog_lookups_ignore_case(self, catalog):
        disciplines, topics, discipline, topic = catalog
        assert disciplines.get_by_name("МАТЕМАТИКА") is discipline
        assert topics.get_by_name(discipline.id, "алгебра") is topic
        assert topics.get_by_discipline(discipline.id) == [topic]

    def test_common_get_all_works_for_repository_without_override(self, catalog):
        _, topics, _, topic = catalog
        assert topics.get_all() == [topic]

    def test_materials_by_author(self, db_session, users, catalog):
        _, _, _, topic = catalog
        author = users.add(_user("t"))
        materials = MaterialRepository(db_session)
        mine = materials.add(_material(topic, author))
        materials.add(_material(topic, None, "Без автора"))
        assert materials.get_by_author(author.id) == [mine]

    def test_events_are_ordered_by_time_then_id(self, db_session):
        events = EventRepository(db_session)
        first = events.add(EventEntity(event_type=EventType.USER_LOGGED_IN, target="a"))
        second = events.add(EventEntity(event_type=EventType.USER_LOGGED_OUT, target="b"))
        assert events.get_all() == [first, second]


class TestFavoritesThroughRelationship:
    def test_add_has_remove(self, db_session, users, catalog):
        _, _, _, topic = catalog
        student = users.add(_user("s"))
        material = MaterialRepository(db_session).add(_material(topic, None))
        assert not users.has_favorite(student.id, material.id)
        users.add_favorite(student, material)
        assert users.has_favorite(student.id, material.id)
        assert material in student.favorite_materials and student in material.favorited_by
        rows = users.get_favorite_rows(student.id)
        assert [r.material_id for r in rows] == [material.id] and rows[0].added_at
        users.remove_favorite(student, material)
        assert not users.has_favorite(student.id, material.id)

    def test_duplicate_favorite_is_rejected_by_primary_key(self, db_session, users, catalog):
        _, _, _, topic = catalog
        student = users.add(_user("s"))
        material = MaterialRepository(db_session).add(_material(topic, None))
        users.add_favorite(student, material)
        with pytest.raises(IntegrityError, match="pk_favorites"):
            users.add_favorite(student, material)


class TestDeleteRules:
    def test_discipline_with_topics_cannot_be_deleted(self, catalog):
        disciplines, _, discipline, _ = catalog
        with pytest.raises(IntegrityError, match="fk_topics_discipline_id_disciplines"):
            disciplines.delete(discipline)
