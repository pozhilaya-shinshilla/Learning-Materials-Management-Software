"""Связи `relationship` + `back_populates`: «один ко многим» и «многие ко многим»."""

from __future__ import annotations

import pytest
from sqlalchemy import func, select

from src.database.models import (
    DisciplineEntity,
    EventEntity,
    MaterialEntity,
    TopicEntity,
    UserEntity,
    favorites,
)
from src.domain.enums import EventType, FileType, Role


@pytest.fixture
def session(session_factory):
    with session_factory() as session:
        yield session


def _graph(session):
    """Преподаватель, два студента, дисциплина, тема, два материала, закладки."""
    teacher = UserEntity(login="t", email="t@x.org", password_hash="h", role=Role.TEACHER)
    s1 = UserEntity(login="s1", email="s1@x.org", password_hash="h", role=Role.STUDENT)
    s2 = UserEntity(login="s2", email="s2@x.org", password_hash="h", role=Role.STUDENT)
    discipline = DisciplineEntity(name="Математика")
    topic = TopicEntity(name="Алгебра", discipline=discipline)
    materials = [
        MaterialEntity(
            title=f"M{i}",
            description="",
            topic=topic,
            discipline_id=0,  # будет синхронизирован связью `topic`
            author=teacher,
            file_name="a.pdf",
            file_type=FileType.PDF,
            file_size_bytes=1,
            storage_path="p",
        )
        for i in (1, 2)
    ]
    session.add_all([teacher, s1, s2, discipline, topic, *materials])
    session.flush()
    # Многие ко многим пишется прямо через relationship: ORM сама вставит строки в `favorites`.
    s1.favorite_materials.extend(materials)
    materials[0].favorited_by.append(s2)
    session.commit()
    return teacher, s1, s2, discipline, topic, materials


class TestOneToMany:
    def test_discipline_has_topics_and_topic_points_back(self, session):
        _, _, _, discipline, topic, _ = _graph(session)
        session.expire_all()
        assert [t.name for t in session.get(DisciplineEntity, discipline.id).topics] == ["Алгебра"]
        assert session.get(TopicEntity, topic.id).discipline.name == "Математика"

    def test_topic_has_materials_and_material_points_back(self, session):
        _, _, _, _, topic, materials = _graph(session)
        session.expire_all()
        assert len(session.get(TopicEntity, topic.id).materials) == 2
        assert session.get(MaterialEntity, materials[0].id).topic.name == "Алгебра"

    def test_assigning_topic_synchronizes_composite_foreign_key(self, session):
        _, _, _, discipline, topic, materials = _graph(session)
        session.expire_all()
        material = session.get(MaterialEntity, materials[0].id)
        assert (material.topic_id, material.discipline_id) == (topic.id, discipline.id)

    def test_material_discipline_and_disciplines_materials_are_readable(self, session):
        _, _, _, discipline, _, materials = _graph(session)
        session.expire_all()
        assert session.get(MaterialEntity, materials[0].id).discipline.name == "Математика"
        assert len(session.get(DisciplineEntity, discipline.id).materials) == 2

    def test_author_and_user_materials(self, session):
        teacher, *_, materials = _graph(session)
        session.expire_all()
        assert len(session.get(UserEntity, teacher.id).materials) == 2
        assert session.get(MaterialEntity, materials[0].id).author.login == "t"

    def test_events_relationship(self, session):
        teacher, *_ = _graph(session)
        session.add(EventEntity(user=teacher, event_type=EventType.USER_LOGGED_IN, target="t"))
        session.commit()
        session.expire_all()
        user = session.get(UserEntity, teacher.id)
        assert [e.target for e in user.events] == ["t"]
        assert user.events[0].user is user


def _favorites_count(session) -> int:
    return session.scalar(select(func.count()).select_from(favorites))


class TestManyToMany:
    def test_user_favorite_materials_and_material_favorited_by(self, session):
        _, s1, s2, _, _, materials = _graph(session)
        session.expire_all()
        assert {m.title for m in session.get(UserEntity, s1.id).favorite_materials} == {"M1", "M2"}
        assert {u.login for u in session.get(MaterialEntity, materials[0].id).favorited_by} == {
            "s1",
            "s2",
        }
        assert {u.login for u in session.get(MaterialEntity, materials[1].id).favorited_by} == {
            "s1"
        }

    def test_both_sides_are_kept_in_sync_in_session(self, session):
        _, s1, _, _, _, materials = _graph(session)
        assert s1 in materials[1].favorited_by  # back_populates обновил обратную сторону

    def test_association_table_rows_are_created_by_relationships(self, session):
        _graph(session)
        assert _favorites_count(session) == 3

    def test_added_at_is_filled_by_database(self, session):
        _graph(session)
        assert session.scalar(select(func.count()).where(favorites.c.added_at.is_(None))) == 0

    def test_removing_from_collection_deletes_row(self, session):
        _, s1, *_ = _graph(session)
        user = session.get(UserEntity, s1.id)
        user.favorite_materials.remove(user.favorite_materials[0])
        session.commit()
        assert _favorites_count(session) == 2

    def test_same_pair_twice_is_rejected_by_primary_key(self, session):
        from sqlalchemy.exc import IntegrityError

        _, s1, _, _, _, materials = _graph(session)
        with pytest.raises(IntegrityError, match="pk_favorites"):
            session.execute(favorites.insert().values(user_id=s1.id, material_id=materials[0].id))


class TestCascadesThroughOrm:
    def test_deleting_user_via_orm_does_not_load_children(self, session):
        _, s1, *_ = _graph(session)
        session.expire_all()
        session.delete(session.get(UserEntity, s1.id))
        session.commit()
        assert _favorites_count(session) == 1

    def test_deleting_author_via_orm_nulls_author_in_database(self, session):
        teacher, *_, materials = _graph(session)
        session.expire_all()
        session.delete(session.get(UserEntity, teacher.id))
        session.commit()
        session.expire_all()
        assert session.get(MaterialEntity, materials[0].id).author is None
