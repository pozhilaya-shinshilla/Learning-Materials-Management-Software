"""Фабрика репозиториев: одно семейство репозиториев на общей сессии."""

from __future__ import annotations

import pytest

from src.repositories.factory import RepositoryFactory, SQLAlchemyRepositoryFactory
from src.repositories.interfaces import (
    AuthTokenRepository,
    DisciplineRepository,
    EventRepository,
    FailedLoginRepository,
    FavoriteRepository,
    MaterialRepository,
    MaterialRevisionRepository,
    PasswordResetTokenRepository,
    TopicRepository,
    UserRepository,
)
from tests.conftest import new_material


@pytest.fixture
def make_material(seeded):
    """Новый материал сидированной темы и автора (внешние ключи БД должны существовать)."""
    return lambda _id=0: new_material(seeded.topic, seeded.teacher.id)


class TestSQLAlchemyRepositoryFactory:
    @pytest.fixture
    def factory(self, db_session) -> RepositoryFactory:
        return SQLAlchemyRepositoryFactory(db_session)

    @pytest.mark.parametrize(
        ("method", "interface"),
        [
            ("create_user_repository", UserRepository),
            ("create_discipline_repository", DisciplineRepository),
            ("create_topic_repository", TopicRepository),
            ("create_material_repository", MaterialRepository),
            ("create_favorite_repository", FavoriteRepository),
            ("create_event_repository", EventRepository),
            ("create_password_reset_token_repository", PasswordResetTokenRepository),
            ("create_auth_token_repository", AuthTokenRepository),
            ("create_failed_login_repository", FailedLoginRepository),
            ("create_material_revision_repository", MaterialRevisionRepository),
        ],
    )
    def test_creates_repository_of_expected_interface(self, factory, method, interface):
        assert isinstance(getattr(factory, method)(), interface)

    def test_each_call_returns_new_repository_on_the_same_session(self, factory, make_material):
        first = factory.create_material_repository()
        first.add(make_material())
        second = factory.create_material_repository()
        assert second is not first
        assert len(second.list_all()) == 1  # одна сессия: репозитории видят общую транзакцию

    def test_abstract_factory_cannot_be_instantiated(self):
        with pytest.raises(TypeError):
            RepositoryFactory()
