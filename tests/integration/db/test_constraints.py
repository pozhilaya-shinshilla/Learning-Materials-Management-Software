"""Ограничения из ER-диаграммы действуют на уровне СУБД, а не только в коде сервисов."""

from __future__ import annotations

import pytest
from sqlalchemy import func, insert, select, text
from sqlalchemy.exc import DataError, IntegrityError

from src.database.models import (
    DisciplineEntity,
    EventEntity,
    MaterialEntity,
    TopicEntity,
    UserEntity,
    favorites,
)
from src.domain.enums import EventType, FileType, Role


def _favorite(session, user_id: int, material_id: int) -> None:
    session.execute(insert(favorites).values(user_id=user_id, material_id=material_id))


def _favorites_count(session) -> int:
    return session.scalar(select(func.count()).select_from(favorites))


def _user(login="alice", email=None, role=Role.TEACHER) -> UserEntity:
    return UserEntity(
        login=login, email=email or f"{login}@example.org", password_hash="h", role=role
    )


def _material(topic: TopicEntity, discipline_id: int | None = None, **kwargs) -> MaterialEntity:
    values = {
        "title": "Лекция",
        "description": "",
        "discipline_id": topic.discipline_id if discipline_id is None else discipline_id,
        "topic_id": topic.id,
        "file_name": "a.pdf",
        "file_type": FileType.PDF,
        "file_size_bytes": 1,
        "storage_path": "uploads/a.pdf",
    }
    values.update(kwargs)
    return MaterialEntity(**values)


@pytest.fixture
def session(session_factory):
    with session_factory() as session:
        yield session


@pytest.fixture
def catalog(session):
    """Две дисциплины, в каждой по теме."""
    math, phys = DisciplineEntity(name="Математика"), DisciplineEntity(name="Физика")
    session.add_all([math, phys])
    session.flush()
    algebra = TopicEntity(name="Алгебра", discipline_id=math.id)
    optics = TopicEntity(name="Оптика", discipline_id=phys.id)
    session.add_all([algebra, optics])
    session.commit()
    return math, phys, algebra, optics


class TestUniqueness:
    def test_login_is_unique(self, session):
        session.add_all([_user("bob", "a@x.org"), _user("bob", "b@x.org")])
        with pytest.raises(IntegrityError, match="uq_users_login"):
            session.commit()

    def test_email_is_unique_ignoring_case(self, session):
        session.add_all([_user("a", "Same@Example.org"), _user("b", "same@example.ORG")])
        with pytest.raises(IntegrityError, match="uq_users_lower_email"):
            session.commit()

    def test_discipline_name_is_unique_ignoring_case(self, session):
        session.add_all([DisciplineEntity(name="Математика"), DisciplineEntity(name="МАТЕМАТИКА")])
        with pytest.raises(IntegrityError, match="uq_disciplines_lower_name"):
            session.commit()

    def test_topic_name_is_unique_within_discipline_only(self, session, catalog):
        math, phys, *_ = catalog
        session.add(TopicEntity(name="Введение", discipline_id=math.id))
        session.add(TopicEntity(name="введение", discipline_id=phys.id))  # другая дисциплина
        session.commit()
        session.add(TopicEntity(name="ВВЕДЕНИЕ", discipline_id=math.id))
        with pytest.raises(IntegrityError, match="uq_topics_discipline_id_lower_name"):
            session.commit()


class TestMaterialClassification:
    def test_topic_must_belong_to_materials_discipline(self, session, catalog):
        math, phys, algebra, optics = catalog
        # Тема «Оптика» относится к физике, а дисциплина материала — математика.
        session.add(_material(optics, discipline_id=math.id))
        with pytest.raises(IntegrityError, match="fk_materials_topic_id_discipline_id_topics"):
            session.commit()

    def test_consistent_classification_is_accepted(self, session, catalog):
        _, _, algebra, _ = catalog
        session.add(_material(algebra))
        session.commit()

    def test_discipline_with_topics_cannot_be_deleted(self, session, catalog):
        math, *_ = catalog
        session.delete(session.get(DisciplineEntity, math.id))
        with pytest.raises(IntegrityError, match="fk_topics_discipline_id_disciplines"):
            session.commit()

    def test_topic_with_materials_cannot_be_deleted(self, session, catalog):
        _, _, algebra, _ = catalog
        session.add(_material(algebra))
        session.commit()
        session.delete(session.get(TopicEntity, algebra.id))
        with pytest.raises(IntegrityError, match="fk_materials_topic_id_discipline_id_topics"):
            session.commit()


class TestCheckAndTypes:
    def test_negative_file_size_is_rejected(self, session, catalog):
        _, _, algebra, _ = catalog
        session.add(_material(algebra, file_size_bytes=-1))
        with pytest.raises(IntegrityError, match="ck_materials_file_size_non_negative"):
            session.commit()

    def test_zero_size_and_large_size_are_accepted(self, session, catalog):
        _, _, algebra, _ = catalog
        session.add_all(
            [_material(algebra, file_size_bytes=0), _material(algebra, file_size_bytes=2**40)]
        )
        session.commit()

    def test_enum_rejects_unknown_value_in_database(self, session):
        with pytest.raises(DataError):
            session.execute(
                text(
                    "INSERT INTO users (login, email, password_hash, role) "
                    "VALUES ('x', 'x@x.org', 'h', 'superuser')"
                )
            )

    def test_enum_values_are_stored_as_lowercase_strings(self, session):
        session.add(_user("bob"))
        session.commit()
        assert session.scalar(text("SELECT role::text FROM users")) == "teacher"
        assert session.scalar(text("SELECT status::text FROM users")) == "active"

    def test_not_null_columns_are_enforced(self, session):
        session.add(UserEntity(login="x", email="x@x.org", role=Role.STUDENT))
        with pytest.raises(IntegrityError, match="password_hash"):
            session.commit()

    def test_string_length_limits_are_enforced(self, session):
        session.add(_user("x" * 51))
        with pytest.raises(DataError):
            session.commit()

    def test_timestamps_default_to_now(self, session):
        user = _user()
        session.add(user)
        session.commit()
        assert user.created_at is not None and user.created_at.tzinfo is not None


class TestDeleteRules:
    @pytest.fixture
    def populated(self, session, catalog):
        _, _, algebra, _ = catalog
        author, reader = _user("author"), _user("reader", role=Role.STUDENT)
        session.add_all([author, reader])
        session.flush()
        material = _material(algebra, author_id=author.id)
        session.add(material)
        session.flush()
        _favorite(session, reader.id, material.id)
        session.add(EventEntity(user_id=author.id, event_type=EventType.USER_LOGGED_IN, target="a"))
        session.commit()
        return author.id, reader.id, material.id

    def test_deleting_author_keeps_material_and_clears_author(self, session, populated):
        author_id, _, material_id = populated
        session.delete(session.get(UserEntity, author_id))
        session.commit()
        session.expire_all()
        material = session.get(MaterialEntity, material_id)
        assert material is not None and material.author_id is None

    def test_deleting_user_keeps_events_and_clears_user(self, session, populated):
        author_id, *_ = populated
        session.delete(session.get(UserEntity, author_id))
        session.commit()
        events = session.query(EventEntity).all()
        assert len(events) == 1 and events[0].user_id is None

    def test_deleting_user_removes_their_favorites(self, session, populated):
        _, reader_id, _ = populated
        session.delete(session.get(UserEntity, reader_id))
        session.commit()
        assert _favorites_count(session) == 0

    def test_deleting_material_removes_its_favorites(self, session, populated):
        *_, material_id = populated
        session.delete(session.get(MaterialEntity, material_id))
        session.commit()
        assert _favorites_count(session) == 0

    def test_favorite_is_unique_per_user_and_material(self, session, populated):
        _, reader_id, material_id = populated
        with pytest.raises(IntegrityError, match="pk_favorites"):
            _favorite(session, reader_id, material_id)

    def test_favorite_requires_existing_material(self, session, populated):
        _, reader_id, _ = populated
        with pytest.raises(IntegrityError, match="fk_favorites_material_id_materials"):
            _favorite(session, reader_id, 9999)


class TestUpdatedAt:
    def test_updated_at_changes_on_update(self, session, catalog):
        _, _, algebra, _ = catalog
        material = _material(algebra)
        session.add(material)
        session.commit()
        created = material.updated_at
        session.execute(text("SELECT pg_sleep(0.01)"))
        material.title = "Другое название"
        session.commit()
        session.refresh(material)
        assert material.updated_at > created
