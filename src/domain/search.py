"""Запрос на поиск материалов: что искать и в каком порядке вернуть.

Сервис поиска собирает его из пользовательского фильтра, а хранилище выполняет, не зная,
откуда он взялся. Даты уже переведены в моменты времени с часовым поясом, поэтому
хранилищу не нужно знать часовой пояс приложения.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from src.domain.enums import FileType, SortField, SortOrder


@dataclass(frozen=True)
class MaterialSearchQuery:
    """Условия отбора и порядок сортировки; `None` означает «условие не задано».

    `text` ищется по названию и описанию с учётом морфологии (полнотекстовый поиск).
    `uploaded_from` входит в период, `uploaded_before` не входит. `limit` и `offset` выбирают
    страницу результата; без `limit` возвращается всё.
    """

    text: str | None = None
    discipline_id: int | None = None
    topic_id: int | None = None
    file_type: FileType | None = None
    uploaded_from: datetime | None = None
    uploaded_before: datetime | None = None
    sort_field: SortField = SortField.UPLOAD_DATE
    sort_order: SortOrder = SortOrder.DESCENDING
    limit: int | None = None
    offset: int = 0
