"""Изоляция: без метки `db` база недоступна, а состояние не переходит между тестами."""

from __future__ import annotations

import psycopg
import pytest
from sqlalchemy import create_engine, text

from src.domain.models import Discipline


def test_direct_database_connection_is_refused_in_a_plain_test():
    with pytest.raises(AssertionError, match="настоящей базе данных"):
        psycopg.connect("postgresql://lms:lms@localhost:5432/lms")


def test_sqlalchemy_engine_cannot_reach_the_database_either():
    engine = create_engine("postgresql+psycopg://lms:lms@localhost:5432/lms")
    with pytest.raises(AssertionError, match="настоящей базе данных"), engine.connect() as conn:
        conn.execute(text("SELECT 1"))


@pytest.mark.parametrize("round_number", [1, 2, 3])
def test_every_test_gets_an_empty_store(repository_factory, round_number):
    """Хранилище создаётся заново для каждого теста: прошлые записи не видны, порядок не важен."""
    disciplines = repository_factory.create_discipline_repository()
    assert disciplines.list_all() == []
    disciplines.add(Discipline(0, f"Дисциплина {round_number}"))
    assert [d.id for d in disciplines.list_all()] == [1]
