"""TransactionManager без базы данных: сессия SQLAlchemy заменена `MagicMock`.

Заменяется только внешняя зависимость (соединение с БД). Логика выбора «commit или rollback»
и порядок отложенных действий — настоящие, их мы и проверяем.
"""

from __future__ import annotations

from unittest.mock import MagicMock, call

import pytest

from src.database.transaction import TransactionManager
from src.domain.exceptions import AccountDeletedError, AuthenticationError, DomainError


@pytest.fixture
def session() -> MagicMock:
    return MagicMock(name="Session")


@pytest.fixture
def manager(session) -> TransactionManager:
    # scoped_session вызывает фабрику, а та возвращает наш двойник.
    return TransactionManager(MagicMock(return_value=session))


def test_clean_block_is_committed(manager, session):
    with manager.transaction():
        pass
    session.commit.assert_called_once_with()
    session.rollback.assert_not_called()


def test_domain_error_still_commits_and_is_reraised(manager, session):
    """Нарушение бизнес-правила — не сбой: записи до него (например, журнал) сохраняются."""
    assert not AuthenticationError.rolls_back_transaction
    with pytest.raises(AuthenticationError), manager.transaction():
        raise AuthenticationError()
    session.commit.assert_called_once_with()
    session.rollback.assert_not_called()


def test_domain_error_marked_as_race_rolls_back(manager, session):
    assert AccountDeletedError.rolls_back_transaction
    with pytest.raises(AccountDeletedError), manager.transaction():
        raise AccountDeletedError()
    session.rollback.assert_called_once_with()
    session.commit.assert_not_called()


@pytest.mark.parametrize("error", [RuntimeError("сбой"), KeyboardInterrupt(), ValueError("баг")])
def test_any_other_error_rolls_back(manager, session, error):
    with pytest.raises(type(error)), manager.transaction():
        raise error
    session.rollback.assert_called_once_with()
    session.commit.assert_not_called()


def test_failed_commit_turns_into_rollback(manager, session):
    session.commit.side_effect = RuntimeError("БД пропала при commit")
    with pytest.raises(RuntimeError), manager.transaction():
        pass
    session.rollback.assert_called_once_with()


def test_session_is_always_released(manager, session):
    with manager.transaction():
        pass
    with pytest.raises(RuntimeError), manager.transaction():
        raise RuntimeError
    assert session.close.call_count == 2  # scoped_session.remove() закрывает сессию


def test_nested_transaction_uses_the_outer_one(manager, session):
    with manager.transaction():
        with manager.transaction():
            pass
        session.commit.assert_not_called()  # внутренний блок ничего не фиксирует
    session.commit.assert_called_once_with()


def test_commit_actions_run_only_after_commit(manager, session):
    order = MagicMock()
    session.commit.side_effect = lambda: order.commit()
    with manager.transaction():
        manager.on_commit(lambda: order.mail())
        manager.on_rollback(lambda: order.cleanup())
        order.mail.assert_not_called()
    assert order.mock_calls == [call.commit(), call.mail()]


def test_rollback_actions_run_only_after_rollback(manager):
    mail, cleanup = MagicMock(), MagicMock()
    with pytest.raises(DomainError), manager.transaction():
        manager.on_commit(mail)
        manager.on_rollback(cleanup)
        raise AccountDeletedError()
    mail.assert_not_called()
    cleanup.assert_called_once_with()


def test_failing_action_does_not_block_the_next_one_or_hide_the_outcome(manager, caplog):
    second = MagicMock()
    with manager.transaction():
        manager.on_commit(MagicMock(side_effect=OSError("SMTP недоступен")))
        manager.on_commit(second)
    second.assert_called_once_with()
    assert "Не удалось выполнить действие" in caplog.text


def test_outside_a_transaction_commit_action_runs_immediately_and_rollback_action_is_dropped(
    manager,
):
    now, never = MagicMock(), MagicMock()
    manager.on_commit(now)
    manager.on_rollback(never)
    now.assert_called_once_with()
    never.assert_not_called()


def test_state_does_not_leak_into_the_next_transaction(manager):
    leftover = MagicMock()
    with manager.transaction():
        manager.on_commit(leftover)
    leftover.reset_mock()
    with manager.transaction():
        pass
    leftover.assert_not_called()
