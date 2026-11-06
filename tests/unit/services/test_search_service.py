"""Строитель фильтра и сервис поиска: перевод фильтра в запрос к хранилищу."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from src.domain.enums import FileType, SortField, SortOrder
from src.domain.search import MaterialSearchQuery
from src.services.search_service import MaterialFilter, MaterialFilterBuilder, SearchService


class TestMaterialFilterBuilder:
    def test_empty_builder_gives_empty_filter(self):
        assert MaterialFilterBuilder().build() == MaterialFilter()

    def test_all_fields(self):
        start, end = date(2026, 1, 1), date(2026, 2, 1)
        built = (
            MaterialFilterBuilder()
            .with_query("q")
            .in_discipline(2)
            .in_topic(3)
            .of_type(FileType.PDF)
            .uploaded_between(start, end)
            .build()
        )
        assert built == MaterialFilter("q", 2, 3, FileType.PDF, start, end)

    def test_none_means_not_set(self):
        built = (
            MaterialFilterBuilder()
            .with_query(None)
            .in_discipline(None)
            .in_topic(None)
            .of_type(None)
            .uploaded_between(None, None)
            .build()
        )
        assert built == MaterialFilter()

    def test_methods_return_same_builder(self):
        builder = MaterialFilterBuilder()
        assert builder.with_query("x") is builder
        assert builder.in_discipline(1) is builder

    def test_later_call_overrides_earlier(self):
        built = MaterialFilterBuilder().with_query("a").with_query("b").build()
        assert built.query == "b"

    def test_discipline_id_zero_is_kept(self):
        assert MaterialFilterBuilder().in_discipline(0).build().discipline_id == 0

    def test_builders_do_not_share_state(self):
        first = MaterialFilterBuilder().with_query("a")
        second = MaterialFilterBuilder()
        assert first.build() is not second.build()
        assert second.build().query is None


class RecordingRepository:
    """Запоминает запрос, который сервис передал хранилищу."""

    def __init__(self) -> None:
        self.queries: list[MaterialSearchQuery] = []

    def search(self, query: MaterialSearchQuery) -> list:
        self.queries.append(query)
        return []


@pytest.fixture
def repo() -> RecordingRepository:
    return RecordingRepository()


class TestSearchServiceBuildsQuery:
    def test_no_criteria_gives_default_query(self, repo):
        SearchService(repo).search()
        assert repo.queries == [MaterialSearchQuery()]

    def test_fields_are_passed_through(self, repo):
        criteria = MaterialFilter("лекция", 2, 5, FileType.DOCX)
        SearchService(repo).search(criteria, SortField.TITLE, SortOrder.ASCENDING)
        query = repo.queries[0]
        assert (query.text, query.discipline_id, query.topic_id, query.file_type) == (
            "лекция",
            2,
            5,
            FileType.DOCX,
        )
        assert (query.sort_field, query.sort_order) == (SortField.TITLE, SortOrder.ASCENDING)

    def test_dates_become_day_boundaries_in_the_app_time_zone(self, repo):
        volgograd = ZoneInfo("Europe/Volgograd")
        criteria = MaterialFilter(
            uploaded_on_or_after=date(2026, 3, 2), uploaded_on_or_before=date(2026, 3, 4)
        )
        SearchService(repo, volgograd).search(criteria)
        query = repo.queries[0]
        assert query.uploaded_from == datetime(2026, 3, 2, tzinfo=volgograd)
        assert query.uploaded_before == datetime(2026, 3, 5, tzinfo=volgograd)

    def test_end_date_is_inclusive(self, repo):
        """Конец периода — начало следующих суток, не включая его."""
        criteria = MaterialFilter(uploaded_on_or_before=date(2026, 3, 2))
        SearchService(repo, UTC).search(criteria)
        assert repo.queries[0].uploaded_before == datetime(2026, 3, 3, tzinfo=UTC)

    def test_same_instant_falls_on_different_days_in_different_zones(self, repo):
        criteria = MaterialFilter(uploaded_on_or_after=date(2026, 3, 2))
        SearchService(repo, UTC).search(criteria)
        SearchService(repo, timezone(timedelta(hours=3))).search(criteria)
        utc_query, plus3_query = repo.queries
        assert plus3_query.uploaded_from < utc_query.uploaded_from  # 00:00 +03:00 раньше 00:00 UTC

    def test_missing_dates_stay_none(self, repo):
        SearchService(repo).search(MaterialFilter())
        assert repo.queries[0].uploaded_from is None
        assert repo.queries[0].uploaded_before is None

    def test_last_possible_date_does_not_overflow(self, repo):
        SearchService(repo).search(MaterialFilter(uploaded_on_or_before=date.max))
        assert repo.queries[0].uploaded_before is None

    def test_returns_what_the_repository_returned(self):
        class Fixed(RecordingRepository):
            def search(self, query):
                return ["a", "b"]

        assert SearchService(Fixed()).search() == ["a", "b"]
