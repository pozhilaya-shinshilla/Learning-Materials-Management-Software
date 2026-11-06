"""Ожидание базы данных при старте: повторные попытки с понятной ошибкой в конце."""

from __future__ import annotations

import pytest
from sqlalchemy.exc import OperationalError

from src.database.migrations import wait_for_database
from src.domain.exceptions import DatabaseUnavailableError


class FakeConnection:
    closed = False

    def close(self) -> None:
        self.closed = True


class FakeEngine:
    """Первые `failures` подключений не удаются, потом база «просыпается»."""

    def __init__(self, failures: int) -> None:
        self.failures = failures
        self.attempts = 0
        self.last: FakeConnection | None = None

    def connect(self) -> FakeConnection:
        self.attempts += 1
        if self.attempts <= self.failures:
            raise OperationalError("connect", None, Exception("connection refused\nsecond line"))
        self.last = FakeConnection()
        return self.last


class FakeClock:
    """Время идёт только когда «спим»: тест не ждёт по-настоящему."""

    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


def test_ready_database_is_not_waited_for():
    engine, clock = FakeEngine(0), FakeClock()
    wait_for_database(engine, 30, sleep=clock.sleep, clock=clock)
    assert engine.attempts == 1 and clock.sleeps == []
    assert engine.last.closed


def test_retries_until_database_comes_up():
    engine, clock = FakeEngine(3), FakeClock()
    wait_for_database(engine, 30, sleep=clock.sleep, clock=clock)
    assert engine.attempts == 4
    assert clock.sleeps == [1.0, 1.0, 1.0]


def test_gives_up_after_timeout_with_readable_error():
    engine, clock = FakeEngine(10_000), FakeClock()
    with pytest.raises(DatabaseUnavailableError) as info:
        wait_for_database(engine, 5, sleep=clock.sleep, clock=clock)
    assert "5 с" in str(info.value)
    assert "connection refused" in str(info.value)
    assert "second line" not in str(info.value)  # только первая строка ошибки драйвера
    assert clock.now == 5


def test_zero_timeout_means_a_single_attempt():
    engine, clock = FakeEngine(10_000), FakeClock()
    with pytest.raises(DatabaseUnavailableError):
        wait_for_database(engine, 0, sleep=clock.sleep, clock=clock)
    assert engine.attempts == 1 and clock.sleeps == []


def test_other_errors_are_not_swallowed():
    class Broken:
        def connect(self):
            raise RuntimeError("не ошибка подключения")

    with pytest.raises(RuntimeError):
        wait_for_database(Broken(), 5, sleep=lambda s: None)


def test_custom_interval_is_used():
    engine, clock = FakeEngine(2), FakeClock()
    wait_for_database(engine, 30, sleep=clock.sleep, clock=clock, interval_seconds=0.25)
    assert clock.sleeps == [0.25, 0.25]
