from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, date, datetime, time, timedelta, tzinfo

from src.domain.enums import FileType, SortField, SortOrder
from src.domain.models import Material
from src.domain.search import MaterialSearchQuery
from src.repositories.interfaces import MaterialRepository


@dataclass
class MaterialFilter:
    """Необязательные условия для сужения поиска материалов."""

    query: str | None = None
    discipline_id: int | None = None
    topic_id: int | None = None
    file_type: FileType | None = None
    uploaded_on_or_after: date | None = None
    uploaded_on_or_before: date | None = None


class MaterialFilterBuilder:
    """Строитель (Builder): пошагово собирает `MaterialFilter` цепочкой вызовов.

    Каждый метод принимает необязательное значение и возвращает самого строителя;
    значение `None` означает «условие не задано», поэтому интерфейсу не нужно
    проверять каждый ответ пользователя перед вызовом.
    """

    def __init__(self) -> None:
        """Начать с пустого фильтра."""
        self._filter = MaterialFilter()

    def with_query(self, query: str | None) -> MaterialFilterBuilder:
        """Задать текстовый запрос."""
        self._filter.query = query
        return self

    def in_discipline(self, discipline_id: int | None) -> MaterialFilterBuilder:
        """Ограничить поиск дисциплиной."""
        self._filter.discipline_id = discipline_id
        return self

    def in_topic(self, topic_id: int | None) -> MaterialFilterBuilder:
        """Ограничить поиск темой."""
        self._filter.topic_id = topic_id
        return self

    def of_type(self, file_type: FileType | None) -> MaterialFilterBuilder:
        """Ограничить поиск форматом файла."""
        self._filter.file_type = file_type
        return self

    def uploaded_between(self, start: date | None, end: date | None) -> MaterialFilterBuilder:
        """Ограничить поиск периодом загрузки (границы включаются)."""
        self._filter.uploaded_on_or_after = start
        self._filter.uploaded_on_or_before = end
        return self

    def build(self) -> MaterialFilter:
        """Вернуть готовый фильтр."""
        return self._filter


class SearchService:
    """Поиск материалов с учётом морфологии русского языка, фильтрация и сортировка.

    Сервис только переводит пользовательский фильтр в `MaterialSearchQuery`: даты становятся
    границами суток в часовом поясе приложения. Отбор, полнотекстовый поиск и сортировку
    выполняет хранилище (в PostgreSQL это один запрос с индексами).
    """

    def __init__(self, material_repository: MaterialRepository, time_zone: tzinfo = UTC) -> None:
        """Принять хранилище материалов и часовой пояс, в котором понимаются даты фильтра."""
        self._material_repository = material_repository
        self._time_zone = time_zone

    def search(
        self,
        criteria: MaterialFilter | None = None,
        sort_field: SortField = SortField.UPLOAD_DATE,
        sort_order: SortOrder = SortOrder.DESCENDING,
    ) -> list[Material]:
        """Вернуть материалы, подходящие под фильтр, в запрошенном порядке."""
        query = self._build_query(criteria, sort_field, sort_order)
        return self._material_repository.search(query)

    def search_page(
        self,
        criteria: MaterialFilter | None = None,
        sort_field: SortField = SortField.UPLOAD_DATE,
        sort_order: SortOrder = SortOrder.DESCENDING,
        *,
        limit: int,
        offset: int = 0,
    ) -> tuple[list[Material], int]:
        """Вернуть страницу результатов и общее число подходящих материалов."""
        query = self._build_query(criteria, sort_field, sort_order)
        total = self._material_repository.count(query)
        page = replace(query, limit=limit, offset=offset)
        return self._material_repository.search(page), total

    def _build_query(
        self, criteria: MaterialFilter | None, sort_field: SortField, sort_order: SortOrder
    ) -> MaterialSearchQuery:
        """Перевести пользовательский фильтр в запрос к хранилищу."""
        criteria = criteria or MaterialFilter()
        return MaterialSearchQuery(
            text=criteria.query,
            discipline_id=criteria.discipline_id,
            topic_id=criteria.topic_id,
            file_type=criteria.file_type,
            uploaded_from=self._start_of_day(criteria.uploaded_on_or_after),
            uploaded_before=self._start_of_next_day(criteria.uploaded_on_or_before),
            sort_field=sort_field,
            sort_order=sort_order,
        )

    def _start_of_day(self, day: date | None) -> datetime | None:
        """Начало суток `day` в часовом поясе приложения (включая границу)."""
        if day is None:
            return None
        return datetime.combine(day, time.min, tzinfo=self._time_zone)

    def _start_of_next_day(self, day: date | None) -> datetime | None:
        """Начало суток после `day`: конец периода, в который `day` входит целиком."""
        if day is None or day == date.max:
            return None
        return datetime.combine(day + timedelta(days=1), time.min, tzinfo=self._time_zone)
