from __future__ import annotations

from src.domain.enums import EventType
from src.domain.exceptions import (
    DuplicateFavoriteError,
    FavoriteNotFoundError,
    MaterialNotFoundError,
)
from src.domain.models import Favorite, Material, User
from src.repositories.interfaces import FavoriteRepository, MaterialRepository
from src.services.event_log_service import EventLogService


class FavoriteService:
    """Позволяет любому пользователю добавлять материалы в избранное и убирать их оттуда."""

    def __init__(
        self,
        favorite_repository: FavoriteRepository,
        material_repository: MaterialRepository,
        event_log_service: EventLogService,
    ) -> None:
        """Принять хранилища избранного и материалов и сервис журнала событий."""
        self._favorite_repository = favorite_repository
        self._material_repository = material_repository
        self._event_log_service = event_log_service

    def add_favorite(self, user: User, material_id: int) -> Favorite:
        """Добавить материал в избранное пользователя."""
        material = self._material_repository.get_by_id(material_id)
        if material is None:
            raise MaterialNotFoundError(material_id=material_id)
        if self._favorite_repository.exists(user.id, material_id):
            raise DuplicateFavoriteError(title=material.title)
        favorite = self._favorite_repository.add(Favorite(user_id=user.id, material_id=material_id))
        self._event_log_service.record(user.id, EventType.FAVORITE_ADDED, material.title)
        return favorite

    def remove_favorite(self, user: User, material_id: int) -> None:
        """Убрать материал из избранного; ошибка, если его там нет."""
        if not self._favorite_repository.exists(user.id, material_id):
            raise FavoriteNotFoundError(material_id=material_id)
        self._favorite_repository.remove(user.id, material_id)
        # Закладка была, значит был и материал (`ON DELETE CASCADE`), но его могли удалить
        # между проверкой и этим чтением: тогда закладки уже нет, как и материала.
        material = self._material_repository.get_by_id(material_id)
        if material is None:
            raise FavoriteNotFoundError(material_id=material_id)
        self._event_log_service.record(user.id, EventType.FAVORITE_REMOVED, material.title)

    def list_favorites(self, user: User) -> list[Material]:
        """Вернуть материалы, добавленные пользователем в избранное."""
        favorites = self._favorite_repository.list_by_user(user.id)
        # Материал каждой закладки существует: при его удалении БД удаляет и закладки.
        return [self._material_repository.get_by_id(f.material_id) for f in favorites]
