"""Владелец транзакции: тот, кто создаёт `Session`, тот её и фиксирует.

Репозитории только делают `flush()` (см. `src/repositories/sqlalchemy.py`). Сервисы в проекте
живут всё время работы программы (в них хранятся коды восстановления пароля, история правок,
счётчики неудачных входов), поэтому сессия на каждую операцию выдаётся через `scoped_session`:
репозитории получают один объект-посредник, а настоящая `Session` создаётся при первом
обращении внутри `TransactionManager.transaction()` и закрывается при выходе из неё.

Правило фиксации (`TransactionManager.transaction`):
- без ошибок — `commit`;
- `DomainError` — тоже `commit`: это нарушение бизнес-правила, а не сбой, и записи, сделанные
  до него, должны остаться (например, событие «неудачный вход» пишется до `AuthenticationError`;
  оно должно сохраниться);
- `DomainError` с `rolls_back_transaction = True` — `rollback`: так помечены ошибки, вызванные
  гонкой с другим пользователем (например, учётную запись удалили посреди операции). Частично
  выполненная операция не должна остаться в базе;
- любая другая ошибка (сбой БД, баг) — `rollback`: транзакция откатывается целиком.

Внешние действия (письма, файлы) регистрируются через `on_commit` / `on_rollback` и выполняются
уже по исходу: после `commit` соединение возвращено в пул, а откат не оставляет следов вне БД
(см. `src/services/transaction_hooks.py`).
"""

from __future__ import annotations

import functools
import logging
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any

from sqlalchemy.orm import Session, scoped_session, sessionmaker

from src.domain.exceptions import DomainError
from src.services.transaction_hooks import Action, TransactionHooks

logger = logging.getLogger(__name__)


class TransactionManager(TransactionHooks):
    """Создаёт сессию на операцию и фиксирует или откатывает её транзакцию."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        """Принять фабрику сессий; `session` отдаётся репозиториям."""
        self.session: scoped_session[Session] = scoped_session(session_factory)
        self._state = threading.local()

    def on_commit(self, action: Action) -> None:
        """Отложить действие до фиксации внешней транзакции; вне транзакции выполнить сразу."""
        if getattr(self._state, "depth", 0):
            self._state.commit_actions.append(action)
        else:
            action()

    def on_rollback(self, action: Action) -> None:
        """Отложить действие до отката внешней транзакции; вне транзакции оно не нужно."""
        if getattr(self._state, "depth", 0):
            self._state.rollback_actions.append(action)

    @contextmanager
    def transaction(self) -> Iterator[None]:
        """Выполнить блок в одной транзакции; вложенный вызов использует внешнюю."""
        depth = getattr(self._state, "depth", 0)
        if depth:
            yield
            return
        self._state.depth = 1
        self._state.commit_actions = []
        self._state.rollback_actions = []
        committed = False
        try:
            yield
            self.session.commit()
            committed = True
        except DomainError as error:
            if error.rolls_back_transaction:
                self.session.rollback()
            else:
                self.session.commit()
                committed = True
            raise
        except BaseException:
            self.session.rollback()
            raise
        finally:
            actions = self._state.commit_actions if committed else self._state.rollback_actions
            self._state.depth = 0
            self._state.commit_actions = []
            self._state.rollback_actions = []
            self.session.remove()
            self._run(actions)

    @staticmethod
    def _run(actions: list[Action]) -> None:
        """Выполнить отложенные действия; сбой одного не мешает остальным и не прячет исход."""
        for action in actions:
            try:
                action()
            except Exception:
                logger.exception("Не удалось выполнить действие по исходу транзакции")


class TransactionalService[ServiceT]:
    """Заместитель (Proxy): каждый публичный метод сервиса выполняется в своей транзакции.

    Сервис остаётся обычным объектом и о БД ничего не знает. Заместитель подставляется
    в корне сборки (`bootstrap.py`) и только для хранилища в PostgreSQL. Внутренние
    вызовы между методами сервиса идут к самому сервису, а не к заместителю, поэтому
    вся бизнес-операция остаётся в одной транзакции.
    """

    def __init__(self, service: ServiceT, scope: Callable[[], Any]) -> None:
        """Принять сервис и фабрику контекстного менеджера транзакции."""
        self._service = service
        self._scope = scope

    def __getattr__(self, name: str) -> Any:
        """Обернуть вызываемые публичные атрибуты сервиса транзакцией."""
        attribute = getattr(self._service, name)
        if name.startswith("_") or not callable(attribute):
            return attribute

        @functools.wraps(attribute)
        def run_in_transaction(*args: Any, **kwargs: Any) -> Any:
            with self._scope():
                return attribute(*args, **kwargs)

        return run_in_transaction
