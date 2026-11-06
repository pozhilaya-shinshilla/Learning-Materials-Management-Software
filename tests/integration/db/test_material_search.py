"""Поиск материалов в PostgreSQL: отбор, сортировка и полнотекстовый поиск одним запросом."""

from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import literal_column, select, text
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import to_tsquery

from src.database.models import MaterialEntity, material_search_vector
from src.domain.enums import FileType, SortField, SortOrder
from src.repositories.sorting import (
    DEFAULT_SORT_STRATEGIES,
    SortStrategy,
    TitleSortStrategy,
    UploadDateSortStrategy,
)
from src.repositories.sqlalchemy import build_tsquery
from src.services.search_service import MaterialFilter, SearchService
from tests.fakes import make_material

TZ = ZoneInfo("Europe/Volgograd")


def at(day: int, hour: int = 12) -> datetime:
    return datetime(2026, 3, day, hour, 0, tzinfo=TZ)


@pytest.fixture
def search(material_repo) -> SearchService:
    return SearchService(material_repo, TZ)


def add(repo, **kwargs):
    # Тема k принадлежит дисциплине k (см. `reference_data`).
    kwargs.setdefault("topic_id", kwargs.get("discipline_id", 1))
    return repo.add(make_material(0, **kwargs))


def titles(materials) -> list[str]:
    return [m.title for m in materials]


class TestBuildTsquery:
    @pytest.mark.parametrize("text_", [None, "", "   ", "!!!", "...", "-—"])
    def test_empty_or_symbol_only_gives_none(self, text_):
        assert build_tsquery(text_) is None

    def test_words_become_prefix_terms_joined_with_and(self):
        assert build_tsquery("Лекции по пределам") == "'лекции':* & 'по':* & 'пределам':*"

    def test_query_syntax_characters_cannot_get_in(self):
        assert build_tsquery("a' | !b & (c):*") == "'a':* & 'b':* & 'c':*"

    def test_digits_and_latin_are_kept(self):
        assert build_tsquery("Python 3") == "'python':* & '3':*"

    def test_word_count_is_limited(self):
        assert build_tsquery(" ".join(["слово"] * 100)).count("&") == 19


@pytest.mark.usefixtures("reference_data")
class TestFilters:
    def test_empty_repository(self, search):
        assert search.search() == []
        assert search.search(MaterialFilter(query="x")) == []

    def test_no_criteria_returns_all_newest_first(self, search, material_repo):
        old = add(material_repo, title="old", uploaded_at=at(1))
        new = add(material_repo, title="new", uploaded_at=at(2))
        assert [m.id for m in search.search()] == [new.id, old.id]

    def test_blank_query_does_not_filter(self, search, material_repo):
        add(material_repo)
        assert len(search.search(MaterialFilter(query="   "))) == 1

    def test_filter_by_discipline_and_topic(self, search, material_repo):
        target = add(material_repo, discipline_id=2, topic_id=5)
        add(material_repo, discipline_id=2, topic_id=6)
        add(material_repo, discipline_id=3, topic_id=7)
        found = search.search(MaterialFilter(discipline_id=2, topic_id=5))
        assert [m.id for m in found] == [target.id]

    def test_filter_by_file_type(self, search, material_repo):
        pdf = add(material_repo, file_type=FileType.PDF)
        add(material_repo, file_type=FileType.PNG)
        assert [m.id for m in search.search(MaterialFilter(file_type=FileType.PDF))] == [pdf.id]

    def test_all_conditions_are_combined_with_and(self, search, material_repo):
        add(material_repo, title="Алгебра", discipline_id=1, file_type=FileType.PDF)
        add(material_repo, title="Алгебра", discipline_id=2, file_type=FileType.PDF)
        add(material_repo, title="Алгебра", discipline_id=1, file_type=FileType.PNG)
        criteria = MaterialFilter(query="алгебра", discipline_id=1, file_type=FileType.PDF)
        assert len(search.search(criteria)) == 1

    @pytest.mark.parametrize(
        ("after", "before", "expected_days"),
        [
            (date(2026, 3, 2), date(2026, 3, 2), {2}),
            (date(2026, 3, 2), None, {2, 3}),
            (None, date(2026, 3, 2), {1, 2}),
            (date(2026, 3, 3), date(2026, 3, 1), set()),
            (date(2026, 3, 4), None, set()),
            (None, date(2026, 2, 28), set()),
            (None, None, {1, 2, 3}),
        ],
    )
    def test_date_range_bounds_are_inclusive(
        self, search, material_repo, after, before, expected_days
    ):
        for day in (1, 2, 3):
            add(material_repo, title=f"day{day}", uploaded_at=at(day))
        criteria = MaterialFilter(uploaded_on_or_after=after, uploaded_on_or_before=before)
        found = {int(m.title.removeprefix("day")) for m in search.search(criteria)}
        assert found == expected_days

    def test_day_boundaries_follow_the_application_time_zone(self, material_repo):
        """00:30 3 марта по Волгограду — это 21:30 2 марта по UTC. Сутки определяет часовой
        пояс приложения, а не UTC и не пояс сервера."""
        add(material_repo, title="late", uploaded_at=datetime(2026, 3, 2, 23, 30, tzinfo=TZ))
        add(material_repo, title="early", uploaded_at=datetime(2026, 3, 3, 0, 30, tzinfo=TZ))
        service = SearchService(material_repo, TZ)
        second, third = date(2026, 3, 2), date(2026, 3, 3)
        assert titles(
            service.search(
                MaterialFilter(uploaded_on_or_after=second, uploaded_on_or_before=second)
            )
        ) == ["late"]
        assert titles(
            service.search(MaterialFilter(uploaded_on_or_after=third, uploaded_on_or_before=third))
        ) == ["early"]


@pytest.mark.usefixtures("reference_data")
class TestSorting:
    def test_every_sort_field_has_a_strategy(self):
        assert set(DEFAULT_SORT_STRATEGIES) == set(SortField)
        assert all(isinstance(s, SortStrategy) for s in DEFAULT_SORT_STRATEGIES.values())

    def test_title_ascending_and_descending(self, search, material_repo):
        for title in ("б", "а", "в"):
            add(material_repo, title=title)
        asc = search.search(None, SortField.TITLE, SortOrder.ASCENDING)
        desc = search.search(None, SortField.TITLE, SortOrder.DESCENDING)
        assert titles(asc) == ["а", "б", "в"]
        assert titles(desc) == ["в", "б", "а"]

    def test_title_ignores_case(self, search, material_repo):
        for title in ("б", "А", "В"):
            add(material_repo, title=title)
        result = search.search(None, SortField.TITLE, SortOrder.ASCENDING)
        assert titles(result) == ["А", "б", "В"]

    def test_equal_titles_keep_insertion_order(self, search, material_repo):
        ids = [add(material_repo, title=t).id for t in ("а", "А", "а")]
        for order in SortOrder:
            result = search.search(None, SortField.TITLE, order)
            assert [m.id for m in result] == ids

    def test_date_orders(self, search, material_repo):
        first = add(material_repo, title="1", uploaded_at=at(2))
        second = add(material_repo, title="2", uploaded_at=at(1))
        third = add(material_repo, title="3", uploaded_at=at(3))
        asc = search.search(None, SortField.UPLOAD_DATE, SortOrder.ASCENDING)
        desc = search.search(None, SortField.UPLOAD_DATE, SortOrder.DESCENDING)
        assert [m.id for m in asc] == [second.id, first.id, third.id]
        assert [m.id for m in desc] == [third.id, first.id, second.id]

    def test_microsecond_difference_is_respected(self, search, material_repo):
        base = datetime(2026, 1, 1, tzinfo=TZ)
        later = add(material_repo, uploaded_at=base.replace(microsecond=2))
        earlier = add(material_repo, uploaded_at=base.replace(microsecond=1))
        result = search.search(None, SortField.UPLOAD_DATE, SortOrder.ASCENDING)
        assert [m.id for m in result] == [earlier.id, later.id]

    def test_strategies_produce_order_by_with_id_tiebreaker(self):
        for strategy in (TitleSortStrategy(), UploadDateSortStrategy()):
            clauses = strategy.order_by(SortOrder.DESCENDING)
            assert len(clauses) == 2
            assert str(clauses[1]) == str(MaterialEntity.id.asc())


@pytest.mark.usefixtures("reference_data")
class TestFullTextSearch:
    def test_query_matches_title_or_description(self, search, material_repo):
        by_title = add(material_repo, title="Интегралы")
        by_description = add(material_repo, title="Тема", description="про интегралы")
        add(material_repo, title="Другое")
        found = {m.id for m in search.search(MaterialFilter(query="интеграл"))}
        assert found == {by_title.id, by_description.id}

    @pytest.mark.parametrize(
        ("stored", "query"),
        [
            ("Решение уравнений", "уравнение"),
            ("Линейные уравнения", "уравнения"),
            ("Лекция по пределам", "лекции"),
            ("Практика: производные", "производная"),
            ("МАТЕМАТИКА", "математика"),
            ("Ёлка", "елка"),
            ("Елка", "ёлка"),
            ("Design Patterns", "pattern"),
            ("Studies", "study"),
            ("Лабораторная работа 2024", "2024"),
        ],
    )
    def test_morphology_case_and_yo_are_ignored(self, search, material_repo, stored, query):
        add(material_repo, title=stored)
        assert titles(search.search(MaterialFilter(query=query))) == [stored]

    def test_word_prefix_finds_material(self, search, material_repo):
        add(material_repo, title="Дифференциальные уравнения")
        assert len(search.search(MaterialFilter(query="диффер"))) == 1

    def test_all_words_must_be_present_in_any_order(self, search, material_repo):
        add(material_repo, title="Линейные уравнения")
        assert len(search.search(MaterialFilter(query="уравнения линейные"))) == 1
        assert search.search(MaterialFilter(query="линейные интегралы")) == []

    def test_words_may_come_from_title_and_description(self, search, material_repo):
        add(material_repo, title="Лекция", description="по пределам")
        assert len(search.search(MaterialFilter(query="лекция пределы"))) == 1

    def test_stop_words_are_ignored(self, search, material_repo):
        add(material_repo, title="Лекция по пределам")
        assert len(search.search(MaterialFilter(query="лекции по пределам"))) == 1

    def test_query_of_only_stop_words_does_not_filter(self, search, material_repo):
        add(material_repo, title="Лекция")
        add(material_repo, title="Практика")
        assert len(search.search(MaterialFilter(query="и по на"))) == 2

    def test_unrelated_word_finds_nothing(self, search, material_repo):
        add(material_repo, title="Лекция")
        assert search.search(MaterialFilter(query="география")) == []

    @pytest.mark.parametrize(
        "query", ["'", "a' | b", "лекц:*", "!лекция", "(лекция", "лекция & ", "\\", "%_"]
    )
    def test_special_characters_never_break_the_query(self, search, material_repo, query):
        add(material_repo, title="Лекция")
        search.search(MaterialFilter(query=query))  # главное: нет SQL-ошибки

    def test_query_is_combined_with_other_filters_and_sorting(self, search, material_repo):
        add(material_repo, title="Алгебра б", discipline_id=1)
        add(material_repo, title="Алгебра а", discipline_id=1)
        add(material_repo, title="Алгебра в", discipline_id=2)
        criteria = MaterialFilter(query="алгебра", discipline_id=1)
        result = search.search(criteria, SortField.TITLE, SortOrder.ASCENDING)
        assert titles(result) == ["Алгебра а", "Алгебра б"]

    def test_empty_description_does_not_hide_title(self, search, material_repo):
        add(material_repo, title="Лекция", description="")
        assert len(search.search(MaterialFilter(query="лекция"))) == 1


class TestSearchIndex:
    def test_gin_index_exists_in_the_migrated_database(self, db_engine):
        with db_engine.connect() as connection:
            definition = connection.scalar(
                text(
                    "SELECT indexdef FROM pg_indexes WHERE indexname = 'ix_materials_search_vector'"
                )
            )
        assert definition is not None
        assert "USING gin" in definition and "to_tsvector('russian'::regconfig" in definition

    def test_search_expression_can_use_the_index(self, db_engine):
        """Выражение запроса совпадает с индексом: при выключенном seq scan план берёт индекс."""
        query = to_tsquery(literal_column("'russian'::regconfig"), "'лекц':*")
        statement = (
            select(1).select_from(MaterialEntity).where(material_search_vector().op("@@")(query))
        )
        sql = str(
            statement.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True})
        )
        with db_engine.connect() as connection:
            connection.execute(text("SET enable_seqscan = off"))
            plan = "\n".join(row[0] for row in connection.execute(text(f"EXPLAIN {sql}")))
        assert "ix_materials_search_vector" in plan
