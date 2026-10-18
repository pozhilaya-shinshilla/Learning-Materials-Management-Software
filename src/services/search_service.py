from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from src.domain.enums import FileType, SortField, SortOrder
from src.domain.models import Material
from src.repositories.interfaces import MaterialRepository
from src.services.morphology import text_matches_query


@dataclass
class MaterialFilter:
    """Необязательные условия для сужения поиска материалов."""

    query: str | None = None
    discipline_id: int | None = None
    topic_id: int | None = None
    file_type: FileType | None = None
    uploaded_on_or_after: date | None = None
    uploaded_on_or_before: date | None = None


class SearchService:
    """Поиск с учётом морфологии русского языка, фильтрация и сортировка материалов."""

    def __init__(self, material_repository: MaterialRepository) -> None:
        self._material_repository = material_repository

    def search(
        self,
        criteria: MaterialFilter | None = None,
        sort_field: SortField = SortField.UPLOAD_DATE,
        sort_order: SortOrder = SortOrder.DESCENDING,
    ) -> list[Material]:
        """Вернуть материалы, подходящие под фильтр, в запрошенном порядке."""
        materials = self._material_repository.list_all()
        if criteria is not None:
            materials = [m for m in materials if self._matches(m, criteria)]
        return self._sort(materials, sort_field, sort_order)

    def _matches(self, material: Material, criteria: MaterialFilter) -> bool:
        """Проверить, подходит ли материал под все заданные условия."""
        if criteria.query and not text_matches_query(
            f"{material.title} {material.description}", criteria.query
        ):
            return False
        if criteria.discipline_id is not None and material.discipline_id != criteria.discipline_id:
            return False
        if criteria.topic_id is not None and material.topic_id != criteria.topic_id:
            return False
        if criteria.file_type is not None and material.file_type != criteria.file_type:
            return False
        uploaded_date = material.uploaded_at.astimezone().date()
        after = criteria.uploaded_on_or_after
        before = criteria.uploaded_on_or_before
        if after is not None and uploaded_date < after:
            return False
        return not (before is not None and uploaded_date > before)

    def _sort(
        self, materials: list[Material], sort_field: SortField, sort_order: SortOrder
    ) -> list[Material]:
        """Отсортировать материалы по выбранному полю и в выбранном направлении."""
        reverse = sort_order is SortOrder.DESCENDING
        if sort_field is SortField.TITLE:
            return sorted(materials, key=self._title_key, reverse=reverse)
        return sorted(materials, key=self._upload_date_key, reverse=reverse)

    def _title_key(self, material: Material) -> str:
        """Ключ сортировки по названию (без учёта регистра)."""
        return material.title.casefold()

    def _upload_date_key(self, material: Material) -> datetime:
        """Ключ сортировки по дате загрузки."""
        return material.uploaded_at
