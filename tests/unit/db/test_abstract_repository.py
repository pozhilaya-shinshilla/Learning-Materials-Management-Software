"""Абстрактный репозиторий — интерфейс, а не готовая реализация (методичка, 12.2)."""

from __future__ import annotations

import pytest

from src.repositories.abstract import AbstractRepository
from src.repositories.sqlalchemy import (
    DisciplineRepository,
    EventRepository,
    MaterialRepository,
    SQLAlchemyRepository,
    TopicRepository,
    UserRepository,
)

CONTRACT = {"add", "get_by_id", "get_all", "update", "delete"}


def test_cannot_instantiate_abstract_repository():
    with pytest.raises(TypeError, match="abstract") as info:
        AbstractRepository()
    for method in CONTRACT:
        assert method in str(info.value)


def test_contract_has_exactly_five_abstract_methods():
    assert set(AbstractRepository.__abstractmethods__) == CONTRACT


def test_common_sqlalchemy_repository_is_complete():
    assert not SQLAlchemyRepository.__abstractmethods__


@pytest.mark.parametrize(
    "repository",
    [UserRepository, DisciplineRepository, TopicRepository, MaterialRepository, EventRepository],
)
def test_concrete_repositories_set_model_and_inherit_common_crud(repository):
    assert issubclass(repository, SQLAlchemyRepository)
    assert repository.model.__tablename__
    assert not repository.__abstractmethods__
