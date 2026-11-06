"""Транзакцией владеет тот, кто создал сессию, а не репозиторий (методичка, 12.8)."""

from __future__ import annotations

import pytest
from sqlalchemy.orm import sessionmaker

from src.database.transaction import TransactionalService, TransactionManager
from src.domain.exceptions import DomainError
from src.domain.models import Discipline
from src.repositories.factory import SQLAlchemyRepositoryFactory


@pytest.fixture
def manager(clean_db, session_factory) -> TransactionManager:
    return TransactionManager(session_factory)


@pytest.fixture
def disciplines(manager):
    return SQLAlchemyRepositoryFactory(manager.session).create_discipline_repository()


def _names(session_factory: sessionmaker) -> list[str]:
    """Что видит другое соединение, то есть что реально зафиксировано."""
    with session_factory() as other:
        from sqlalchemy import select

        from src.database.models import DisciplineEntity

        return list(other.scalars(select(DisciplineEntity.name)))


class TestRepositoryDoesNotCommit:
    def test_flushed_row_is_visible_only_inside_transaction(self, db_session, session_factory):
        repo = SQLAlchemyRepositoryFactory(db_session).create_discipline_repository()
        saved = repo.add(Discipline(0, "Математика"))
        assert saved.id > 0  # flush выдал id
        assert repo.get_by_id(saved.id) is not None
        assert _names(session_factory) == []  # другое соединение ничего не видит

    def test_rollback_discards_repository_writes(self, db_session, session_factory):
        repo = SQLAlchemyRepositoryFactory(db_session).create_discipline_repository()
        repo.add(Discipline(0, "Математика"))
        db_session.rollback()
        assert repo.list_all() == []

    def test_repositories_share_one_transaction(self, db_session):
        factory = SQLAlchemyRepositoryFactory(db_session)
        discipline = factory.create_discipline_repository().add(Discipline(0, "Физика"))
        assert factory.create_discipline_repository().get_by_id(discipline.id) is not None


class TestTransactionManager:
    def test_commit_on_success(self, manager, disciplines, session_factory):
        with manager.transaction():
            disciplines.add(Discipline(0, "Математика"))
        assert _names(session_factory) == ["Математика"]

    def test_rollback_on_unexpected_error(self, manager, disciplines, session_factory):
        with pytest.raises(RuntimeError), manager.transaction():
            disciplines.add(Discipline(0, "Математика"))
            raise RuntimeError("сбой")
        assert _names(session_factory) == []

    def test_domain_error_still_commits(self, manager, disciplines, session_factory):
        """Нарушение бизнес-правила не откатывает уже сделанные записи (журнал входа)."""
        with pytest.raises(DomainError), manager.transaction():
            disciplines.add(Discipline(0, "Математика"))
            raise DomainError()
        assert _names(session_factory) == ["Математика"]

    def test_domain_error_marked_as_rolling_back_discards_writes(
        self, manager, disciplines, session_factory
    ):
        """Ошибка гонки (`rolls_back_transaction`) отменяет операцию целиком, а не фиксирует её."""

        class LostRace(DomainError):
            rolls_back_transaction = True

        with pytest.raises(LostRace), manager.transaction():
            disciplines.add(Discipline(0, "Математика"))
            raise LostRace()
        assert _names(session_factory) == []

    def test_nested_transaction_joins_outer_one(self, manager, disciplines, session_factory):
        with pytest.raises(RuntimeError), manager.transaction():
            with manager.transaction():
                disciplines.add(Discipline(0, "Математика"))
            assert _names(session_factory) == []  # внутренний блок не коммитил
            raise RuntimeError("сбой")
        assert _names(session_factory) == []

    def test_next_transaction_starts_clean_after_error(self, manager, disciplines):
        with pytest.raises(RuntimeError), manager.transaction():
            disciplines.add(Discipline(0, "Математика"))
            raise RuntimeError("сбой")
        with manager.transaction():
            disciplines.add(Discipline(0, "Физика"))
            assert [d.name for d in disciplines.list_all()] == ["Физика"]

    def test_data_survives_between_transactions(self, manager, disciplines):
        with manager.transaction():
            disciplines.add(Discipline(0, "Математика"))
        with manager.transaction():
            assert disciplines.get_by_name("математика") is not None


class _Service:
    def __init__(self, disciplines) -> None:
        self.disciplines = disciplines
        self.label = "service"

    def create(self, name: str) -> Discipline:
        return self.disciplines.add(Discipline(0, name))

    def fail(self) -> None:
        self.disciplines.add(Discipline(0, "Лишняя"))
        raise RuntimeError("сбой")

    def _private(self) -> str:
        return "private"


class TestTransactionalProxy:
    def test_each_public_call_is_one_transaction(self, manager, disciplines, session_factory):
        service = TransactionalService(_Service(disciplines), manager.transaction)
        service.create("Математика")
        assert _names(session_factory) == ["Математика"]

    def test_failure_rolls_back_whole_call(self, manager, disciplines, session_factory):
        service = TransactionalService(_Service(disciplines), manager.transaction)
        with pytest.raises(RuntimeError):
            service.fail()
        assert _names(session_factory) == []

    def test_attributes_and_private_members_pass_through(self, manager, disciplines):
        service = TransactionalService(_Service(disciplines), manager.transaction)
        assert service.label == "service"
        assert service._private() == "private"

    def test_missing_attribute_raises(self, manager, disciplines):
        service = TransactionalService(_Service(disciplines), manager.transaction)
        with pytest.raises(AttributeError):
            _ = service.nothing


class TestTransactionHooks:
    """`on_commit` / `on_rollback`: внешние действия выполняются по исходу транзакции."""

    def test_on_commit_runs_after_the_commit(self, manager, disciplines, session_factory):
        seen: list[list[str]] = []
        with manager.transaction():
            disciplines.add(Discipline(0, "Математика"))
            manager.on_commit(lambda: seen.append(_names(session_factory)))
            assert seen == []  # внутри транзакции действие не выполняется
        assert seen == [["Математика"]]  # а когда выполнилось, запись уже зафиксирована

    def test_on_commit_runs_after_a_committed_domain_error(self, manager):
        ran: list[str] = []
        with pytest.raises(DomainError), manager.transaction():
            manager.on_commit(lambda: ran.append("письмо"))
            raise DomainError()
        assert ran == ["письмо"]  # событие «неудачный вход» зафиксировано, письмо уходит

    @pytest.mark.parametrize("failure", ["unexpected", "race"])
    def test_rollback_discards_commit_actions_and_runs_rollback_actions(self, manager, failure):
        class LostRace(DomainError):
            rolls_back_transaction = True

        error = RuntimeError("сбой") if failure == "unexpected" else LostRace()
        ran: list[str] = []
        with pytest.raises(type(error)), manager.transaction():
            manager.on_commit(lambda: ran.append("письмо"))
            manager.on_rollback(lambda: ran.append("уборка"))
            raise error
        assert ran == ["уборка"]

    def test_commit_discards_rollback_actions(self, manager):
        ran: list[str] = []
        with manager.transaction():
            manager.on_rollback(lambda: ran.append("уборка"))
        assert ran == []

    def test_failed_commit_counts_as_a_rollback(self, manager, monkeypatch):
        ran: list[str] = []

        def failing_commit() -> None:
            raise RuntimeError("соединение потеряно при фиксации")

        monkeypatch.setattr(manager.session, "commit", failing_commit)
        with pytest.raises(RuntimeError), manager.transaction():
            manager.on_commit(lambda: ran.append("письмо"))
            manager.on_rollback(lambda: ran.append("уборка"))
        assert ran == ["уборка"]

    def test_actions_run_in_order_and_one_failure_does_not_stop_the_rest(self, manager, caplog):
        ran: list[str] = []

        def failing() -> None:
            raise OSError("диск недоступен")

        with manager.transaction():
            manager.on_commit(lambda: ran.append("первое"))
            manager.on_commit(failing)
            manager.on_commit(lambda: ran.append("третье"))
        assert ran == ["первое", "третье"]
        assert "диск недоступен" in caplog.text

    def test_failing_action_does_not_hide_the_domain_error(self, manager):
        def failing() -> None:
            raise OSError("письмо не ушло")

        with pytest.raises(DomainError), manager.transaction():
            manager.on_commit(failing)
            raise DomainError()

    def test_nested_transaction_leaves_actions_to_the_outer_one(self, manager):
        ran: list[str] = []
        with manager.transaction():
            with manager.transaction():
                manager.on_commit(lambda: ran.append("письмо"))
            assert ran == []  # внутренний блок не фиксировал
        assert ran == ["письмо"]

    def test_outside_a_transaction_commit_action_runs_at_once_and_rollback_action_is_dropped(
        self, manager
    ):
        ran: list[str] = []
        manager.on_commit(lambda: ran.append("сразу"))
        manager.on_rollback(lambda: ran.append("не нужно"))
        assert ran == ["сразу"]

    def test_actions_do_not_leak_into_the_next_transaction(self, manager):
        ran: list[str] = []
        with pytest.raises(RuntimeError), manager.transaction():
            manager.on_commit(lambda: ran.append("отброшено"))
            raise RuntimeError("сбой")
        with manager.transaction():
            pass
        assert ran == []

    def test_action_may_open_its_own_transaction(self, manager, disciplines, session_factory):
        def follow_up() -> None:
            with manager.transaction():
                disciplines.add(Discipline(0, "Физика"))

        with manager.transaction():
            manager.on_commit(follow_up)
        assert _names(session_factory) == ["Физика"]
