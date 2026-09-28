from __future__ import annotations

from src.domain.enums import EventType
from src.domain.exceptions import EntityNotFoundError
from src.domain.models import Favorite, Material, User
from src.repositories.interfaces import FavoriteRepository, MaterialRepository
from src.services.event_log_service import EventLogService


class FavoriteService:
    """Lets any user bookmark and unbookmark materials for quick access."""

    def __init__(
        self,
        favorite_repository: FavoriteRepository,
        material_repository: MaterialRepository,
        event_log_service: EventLogService,
    ) -> None:
        self._favorite_repository = favorite_repository
        self._material_repository = material_repository
        self._event_log_service = event_log_service

    def add_favorite(self, user: User, material_id: int) -> Favorite:
        """Bookmark a material for the given user."""
        material = self._material_repository.get_by_id(material_id)
        if material is None:
            raise EntityNotFoundError(f"Материал с id {material_id} не найден.")
        if self._favorite_repository.exists(user.id, material_id):
            return Favorite(user_id=user.id, material_id=material_id)
        favorite = self._favorite_repository.add(Favorite(user_id=user.id, material_id=material_id))
        self._event_log_service.record(user.id, EventType.FAVORITE_ADDED, material.title)
        return favorite

    def remove_favorite(self, user: User, material_id: int) -> None:
        """Remove a bookmark for the given user, if it exists."""
        self._favorite_repository.remove(user.id, material_id)
        material = self._material_repository.get_by_id(material_id)
        target = material.title if material is not None else str(material_id)
        self._event_log_service.record(user.id, EventType.FAVORITE_REMOVED, target)

    def list_favorites(self, user: User) -> list[Material]:
        """Return the materials the given user has bookmarked."""
        favorites = self._favorite_repository.list_by_user(user.id)
        materials = []
        for favorite in favorites:
            material = self._material_repository.get_by_id(favorite.material_id)
            if material is not None:
                materials.append(material)
        return materials
