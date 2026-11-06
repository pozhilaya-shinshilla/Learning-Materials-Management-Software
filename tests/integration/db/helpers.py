"""Общие приёмы тестов на одновременную работу: потоки, барьеры и точки удержания.

Потоки нужны не ради нагрузки, а чтобы гарантированно получить неудобное чередование операций:
в нужное место операции вставляется пауза или барьер.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from typing import Any

TIMEOUT = 15
# Сколько ждём, чтобы убедиться, что вторая операция действительно застряла на блокировке.
BLOCKED_PROBE = 0.5


class Worker(threading.Thread):
    """Поток, который запоминает результат или исключение вместо падения."""

    def __init__(self, action: Callable[[], Any]) -> None:
        super().__init__(daemon=True)
        self._action = action
        self.result: Any = None
        self.error: BaseException | None = None
        self.finished = threading.Event()

    def run(self) -> None:
        try:
            self.result = self._action()
        except BaseException as error:  # тест разбирает любые исключения
            self.error = error
        finally:
            self.finished.set()

    def wait(self) -> Worker:
        self.join(TIMEOUT)
        assert not self.is_alive(), "операция не завершилась: взаимная блокировка?"
        return self


class Gate:
    """Удерживает операцию в нужной точке, пока тест не разрешит продолжить."""

    def __init__(self) -> None:
        self.entered = threading.Event()
        self._release = threading.Event()

    def hold(self) -> None:
        self.entered.set()
        assert self._release.wait(TIMEOUT), "тест не отпустил операцию"

    def release(self) -> None:
        self._release.set()


def after(target: object, name: str, hook: Callable[[], None]) -> None:
    """Вызвать `hook` сразу после метода `target.name` (подмена на экземпляре)."""
    original = getattr(target, name)

    def wrapper(*args: Any, **kwargs: Any) -> Any:
        result = original(*args, **kwargs)
        hook()
        return result

    setattr(target, name, wrapper)


def real(service: Any) -> Any:
    """Настоящий сервис за заместителем транзакций: подменять методы нужно у него."""
    return service._service


def barrier_after(target: object, name: str, barrier: threading.Barrier) -> None:
    after(target, name, lambda: barrier.wait(TIMEOUT))


def run_in_order_of_blocking(first: Worker, gate: Gate, second: Worker) -> None:
    """Запустить `first`, дождаться, что он держит блокировку, и убедиться, что `second` ждёт."""
    first.start()
    assert gate.entered.wait(TIMEOUT), "первая операция не дошла до точки удержания"
    second.start()
    time.sleep(BLOCKED_PROBE)
    assert not second.finished.is_set(), "вторая операция не ждала первую: блокировки нет"
    gate.release()
    first.wait()
    second.wait()
