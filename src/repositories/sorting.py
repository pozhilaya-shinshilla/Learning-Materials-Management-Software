"""Стратегия (Strategy): взаимозаменяемые способы сортировки результатов поиска в SQL.

Каждая стратегия знает, по какому столбцу упорядочить материалы. Сортирует база данных
(`ORDER BY`), а не Python: на большом каталоге это быстрее и не требует загружать в память
все строки. Новый способ сортировки — новый класс и запись в `DEFAULT_SORT_STRATEGIES`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from sqlalchemy import ColumnElement, func

from src.database.models import MaterialEntity
from src.domain.enums import SortField, SortOrder


class SortStrategy(ABC):
    """Контракт сортировки: наследник задаёт ключ, а направление и порядок «при равенстве» общие."""

    @abstractmethod
    def key(self) -> ColumnElement:
        """Вернуть SQL-выражение, по которому сортируют."""

    def order_by(self, order: SortOrder) -> list[ColumnElement]:
        """Вернуть условия `ORDER BY`: ключ в нужном направлении, при равенстве — по возрастанию id.

        Равные значения всегда идут в порядке добавления, поэтому выдача не «скачет» между
        запросами.
        """
        key = self.key()
        ordered = key.desc() if order is SortOrder.DESCENDING else key.asc()
        return [ordered, MaterialEntity.id.asc()]


class TitleSortStrategy(SortStrategy):
    """Сортировка по названию без учёта регистра."""

    def key(self) -> ColumnElement:
        """Название в нижнем регистре."""
        return func.lower(MaterialEntity.title)


class UploadDateSortStrategy(SortStrategy):
    """Сортировка по моменту загрузки."""

    def key(self) -> ColumnElement:
        """Момент загрузки."""
        return MaterialEntity.uploaded_at


DEFAULT_SORT_STRATEGIES: dict[SortField, SortStrategy] = {
    SortField.TITLE: TitleSortStrategy(),
    SortField.UPLOAD_DATE: UploadDateSortStrategy(),
}
