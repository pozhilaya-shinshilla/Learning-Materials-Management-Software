"""Юнит-тесты FavoriteService."""

from __future__ import annotations

import pytest

from src.domain.enums import EventType
from src.domain.exceptions import (
    DuplicateFavoriteError,
    FavoriteNotFoundError,
    MaterialNotFoundError,
)
from src.services.favorite_service import FavoriteService
from tests.fakes import make_material

pytestmark = pytest.mark.usefixtures("reference_data")


@pytest.fixture
def service(favorite_repo, material_repo, event_log) -> FavoriteService:
    return FavoriteService(favorite_repo, material_repo, event_log)


@pytest.fixture
def material(material_repo):
    return material_repo.add(make_material(0, title="Лекция"))


def _events(event_log, admin_user):
    return [(e.event_type, e.target) for e in event_log.list_events(admin_user)]


def test_add_and_list(service, student_user, material):
    favorite = service.add_favorite(student_user, material.id)
    assert (favorite.user_id, favorite.material_id) == (student_user.id, material.id)
    assert service.list_favorites(student_user) == [material]


def test_add_logs(service, student_user, material, event_log, admin_user):
    service.add_favorite(student_user, material.id)
    assert _events(event_log, admin_user) == [(EventType.FAVORITE_ADDED, "Лекция")]


def test_add_unknown_material(service, student_user):
    with pytest.raises(MaterialNotFoundError):
        service.add_favorite(student_user, 999)


def test_add_duplicate(service, student_user, material):
    service.add_favorite(student_user, material.id)
    with pytest.raises(DuplicateFavoriteError):
        service.add_favorite(student_user, material.id)


def test_two_users_may_favorite_same_material(service, student_user, teacher_user, material):
    service.add_favorite(student_user, material.id)
    service.add_favorite(teacher_user, material.id)


def test_lists_are_per_user(service, student_user, teacher_user, material):
    service.add_favorite(student_user, material.id)
    assert service.list_favorites(teacher_user) == []


def test_remove_and_log(service, student_user, material, event_log, admin_user):
    service.add_favorite(student_user, material.id)
    service.remove_favorite(student_user, material.id)
    assert service.list_favorites(student_user) == []
    assert _events(event_log, admin_user)[-1] == (EventType.FAVORITE_REMOVED, "Лекция")


def test_remove_not_favorite(service, student_user, material):
    with pytest.raises(FavoriteNotFoundError):
        service.remove_favorite(student_user, material.id)


def test_remove_does_not_affect_other_users(service, student_user, teacher_user, material):
    service.add_favorite(student_user, material.id)
    service.add_favorite(teacher_user, material.id)
    service.remove_favorite(student_user, material.id)
    assert service.list_favorites(teacher_user) == [material]


def test_can_add_again_after_remove(service, student_user, material):
    service.add_favorite(student_user, material.id)
    service.remove_favorite(student_user, material.id)
    service.add_favorite(student_user, material.id)


def test_deleted_material_is_skipped_in_list(service, student_user, material, material_repo):
    service.add_favorite(student_user, material.id)
    material_repo.delete(material.id)
    assert service.list_favorites(student_user) == []


def test_deleting_material_removes_favorites_in_database(
    service, student_user, material, material_repo, favorite_repo
):
    """БД удаляет закладки вместе с материалом (`ON DELETE CASCADE`), осиротевших нет."""
    service.add_favorite(student_user, material.id)
    material_repo.delete(material.id)
    assert not favorite_repo.exists(student_user.id, material.id)
    with pytest.raises(FavoriteNotFoundError):
        service.remove_favorite(student_user, material.id)


def test_empty_list(service, student_user):
    assert service.list_favorites(student_user) == []
