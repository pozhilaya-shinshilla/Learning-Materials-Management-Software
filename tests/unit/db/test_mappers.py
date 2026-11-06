"""Мапперы работают без БД: переводят доменные dataclass-ы и ORM-сущности туда и обратно."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from src.database.mappers import (
    AuthTokenMapper,
    DisciplineMapper,
    EventMapper,
    FavoriteMapper,
    MaterialMapper,
    MaterialRevisionMapper,
    PasswordResetTokenMapper,
    TopicMapper,
    UserMapper,
)
from src.database.models import (
    AuthTokenEntity,
    DisciplineEntity,
    EventEntity,
    MaterialEntity,
    MaterialRevisionEntity,
    PasswordResetTokenEntity,
    TopicEntity,
    UserEntity,
)
from src.domain.enums import AccountStatus, EventType, FileType, Role
from src.domain.models import (
    AuthToken,
    Discipline,
    Event,
    Favorite,
    Material,
    MaterialMemento,
    PasswordResetToken,
    Topic,
    User,
)
from tests.fakes import make_material, make_user

MOMENT = datetime(2026, 5, 6, 7, 8, 9, tzinfo=UTC)


def _roundtrip(mapper, model, entity_type):
    entity = mapper.to_entity(model)
    assert isinstance(entity, entity_type)
    return entity, mapper.to_domain(entity)


class TestUserMapper:
    def test_roundtrip(self):
        user = make_user(5, "bob", Role.TEACHER, AccountStatus.BLOCKED)
        entity, back = _roundtrip(UserMapper(), user, UserEntity)
        assert entity.id == 5 and back == user

    def test_unsaved_user_leaves_id_to_database(self):
        entity = UserMapper().to_entity(make_user(0, "bob"))
        assert entity.id is None

    def test_apply_copies_every_editable_field(self):
        entity = UserMapper().to_entity(make_user(1, "old"))
        changed = User(1, "new", "n@x.org", "h2", Role.ADMIN, AccountStatus.BLOCKED)
        UserMapper().apply(entity, changed)
        assert UserMapper().to_domain(entity) == changed


class TestCatalogMappers:
    def test_discipline_roundtrip_and_apply(self):
        mapper = DisciplineMapper()
        entity, back = _roundtrip(mapper, Discipline(3, "Математика"), DisciplineEntity)
        assert back == Discipline(3, "Математика")
        mapper.apply(entity, Discipline(3, "Физика"))
        assert entity.name == "Физика"

    def test_topic_roundtrip_and_apply(self):
        mapper = TopicMapper()
        entity, back = _roundtrip(mapper, Topic(4, "Алгебра", 3), TopicEntity)
        assert back == Topic(4, "Алгебра", 3)
        mapper.apply(entity, Topic(4, "Геометрия", 9))
        assert (entity.name, entity.discipline_id) == ("Геометрия", 9)

    def test_unsaved_catalog_items_leave_id_to_database(self):
        assert DisciplineMapper().to_entity(Discipline(0, "X")).id is None
        assert TopicMapper().to_entity(Topic(0, "X", 1)).id is None


class TestMaterialMapper:
    def test_roundtrip(self):
        material = make_material(7, "Лекция", author_id=2, uploaded_at=MOMENT)
        entity, back = _roundtrip(MaterialMapper(), material, MaterialEntity)
        assert back == material
        assert entity.file_type is FileType.PDF

    def test_material_without_author(self):
        material = make_material(7, uploaded_at=MOMENT)
        material.author_id = None
        _, back = _roundtrip(MaterialMapper(), material, MaterialEntity)
        assert back.author_id is None

    def test_apply_copies_editable_fields(self):
        mapper = MaterialMapper()
        entity = mapper.to_entity(make_material(1, "Старое", uploaded_at=MOMENT))
        edited = make_material(1, "Новое", description="d", discipline_id=2, topic_id=3)
        edited.uploaded_at = MOMENT
        mapper.apply(entity, edited)
        assert (entity.title, entity.description, entity.discipline_id, entity.topic_id) == (
            "Новое",
            "d",
            2,
            3,
        )

    def test_unsaved_material_leaves_id_to_database(self):
        assert MaterialMapper().to_entity(make_material(0)).id is None

    def test_domain_memento_still_works_on_mapped_material(self):
        _, back = _roundtrip(MaterialMapper(), make_material(1, "A"), MaterialEntity)
        snapshot = back.create_memento()
        back.title = "B"
        back.restore(snapshot)
        assert back.title == "A"


class TestFavoriteAndEventMappers:
    def test_favorite_row_to_domain(self):
        row = SimpleNamespace(user_id=1, material_id=2, added_at=MOMENT)
        assert FavoriteMapper().to_domain(row) == Favorite(1, 2, MOMENT)

    @pytest.mark.parametrize("user_id", [4, None])
    def test_event_roundtrip_including_guest(self, user_id):
        event = Event(8, user_id, EventType.USER_LOGIN_FAILED, "ghost", MOMENT)
        entity, back = _roundtrip(EventMapper(), event, EventEntity)
        assert back == event and entity.user_id == user_id

    def test_event_apply_is_a_noop(self):
        entity = EventMapper().to_entity(Event(1, 1, EventType.USER_LOGGED_IN, "a", MOMENT))
        EventMapper().apply(entity, Event(1, 2, EventType.USER_LOGGED_OUT, "b", MOMENT))
        assert (entity.user_id, entity.target) == (1, "a")


def test_material_type_is_unchanged_dataclass():
    """Домен остаётся чистым: никакого SQLAlchemy в `Material`."""
    assert not hasattr(Material, "__table__") and not hasattr(Material, "_sa_instance_state")


class TestStateMappers:
    def test_reset_token_roundtrip(self):
        token = PasswordResetToken(4, 2, "a" * 64, MOMENT)
        entity, back = _roundtrip(PasswordResetTokenMapper(), token, PasswordResetTokenEntity)
        assert back == token and entity.id == 4

    def test_unsaved_reset_token_leaves_id_to_database(self):
        entity = PasswordResetTokenMapper().to_entity(PasswordResetToken(0, 2, "b" * 64, MOMENT))
        assert entity.id is None

    def test_reset_token_apply_is_a_noop(self):
        mapper = PasswordResetTokenMapper()
        entity = mapper.to_entity(PasswordResetToken(1, 2, "a" * 64, MOMENT))
        mapper.apply(entity, PasswordResetToken(1, 9, "z" * 64, MOMENT))
        assert (entity.user_id, entity.token_hash) == (2, "a" * 64)

    def test_auth_token_roundtrip(self):
        token = AuthToken(5, 2, "c" * 64, MOMENT)
        entity, back = _roundtrip(AuthTokenMapper(), token, AuthTokenEntity)
        assert back == token and entity.id == 5

    def test_unsaved_auth_token_leaves_id_to_database(self):
        entity = AuthTokenMapper().to_entity(AuthToken(0, 2, "d" * 64, MOMENT))
        assert entity.id is None

    def test_auth_token_apply_is_a_noop(self):
        mapper = AuthTokenMapper()
        entity = mapper.to_entity(AuthToken(1, 2, "a" * 64, MOMENT))
        mapper.apply(entity, AuthToken(1, 9, "z" * 64, MOMENT))
        assert (entity.user_id, entity.token_hash) == (2, "a" * 64)

    def test_revision_roundtrip(self):
        mapper = MaterialRevisionMapper()
        memento = MaterialMemento("Название", "Описание", 3, 4)
        entity = mapper.to_entity(7, memento)
        assert isinstance(entity, MaterialRevisionEntity) and entity.material_id == 7
        assert mapper.to_domain(entity) == memento
