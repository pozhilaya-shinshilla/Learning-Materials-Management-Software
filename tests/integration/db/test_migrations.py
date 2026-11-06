"""Схему создают миграции Alembic: проверяем их на живом PostgreSQL."""

from __future__ import annotations

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text

import src.database.models  # noqa: F401
from src.database.base import Base
from src.database.health import ensure_database_ready, ensure_unicode_case_folding
from src.database.migrations import (
    MIGRATION_LOCK_KEY,
    ensure_schema_is_current,
    include_in_autogenerate,
    upgrade_to_head,
    wait_for_database,
)
from src.domain.enums import EventType
from src.domain.exceptions import DatabaseSchemaError

FIRST_TABLES = {"users", "disciplines", "topics", "materials", "favorites", "events"}
STATE_TABLES = {"password_reset_tokens", "failed_logins", "material_revisions", "auth_tokens"}
EXPECTED_TABLES = FIRST_TABLES | STATE_TABLES


@pytest.fixture
def pristine(db_engine, alembic_config):
    """Отдать тестам БД без схемы и вернуть актуальную схему после теста."""
    command.downgrade(alembic_config, "base")
    yield db_engine
    command.upgrade(alembic_config, "head")


def _tables(engine) -> set[str]:
    return set(inspect(engine).get_table_names()) - {"alembic_version"}


def _enum_types(engine) -> set[str]:
    with engine.connect() as connection:
        return set(connection.scalars(text("SELECT typname FROM pg_type WHERE typtype = 'e'")))


class TestUpgradeAndDowngrade:
    def test_upgrade_creates_all_tables_and_enums(self, pristine, alembic_config):
        assert _tables(pristine) == set()
        command.upgrade(alembic_config, "head")
        assert _tables(pristine) == EXPECTED_TABLES
        assert _enum_types(pristine) == {"user_role", "account_status", "file_type", "event_type"}

    def test_downgrade_removes_tables_and_enum_types(self, pristine, alembic_config):
        command.upgrade(alembic_config, "head")
        command.downgrade(alembic_config, "base")
        assert _tables(pristine) == set()
        assert _enum_types(pristine) == set()

    def test_upgrade_after_downgrade_works(self, pristine, alembic_config):
        command.upgrade(alembic_config, "head")
        command.downgrade(alembic_config, "base")
        command.upgrade(alembic_config, "head")
        assert _tables(pristine) == EXPECTED_TABLES

    def test_upgrade_is_idempotent(self, pristine, alembic_config):
        command.upgrade(alembic_config, "head")
        command.upgrade(alembic_config, "head")
        assert _tables(pristine) == EXPECTED_TABLES

    def test_offline_mode_renders_sql(self, alembic_config, capsys):
        command.upgrade(alembic_config, "head", sql=True)
        out = capsys.readouterr().out
        assert "CREATE TABLE materials" in out and "CREATE TYPE user_role" in out


def _index_exists(engine, name: str) -> bool:
    with engine.connect() as connection:
        query = text("SELECT count(*) FROM pg_indexes WHERE indexname = :name")
        return bool(connection.scalar(query, {"name": name}))


def _event_labels(engine) -> set[str]:
    with engine.connect() as connection:
        return set(
            connection.scalars(
                text(
                    "SELECT e.enumlabel FROM pg_enum e JOIN pg_type t ON t.oid = e.enumtypid "
                    "WHERE t.typname = 'event_type'"
                )
            )
        )


class TestLaterRevisions:
    def test_last_revision_adds_event_types_and_downgrade_keeps_them(
        self, pristine, alembic_config
    ):
        command.upgrade(alembic_config, "head")
        assert {"discipline_deleted", "topic_deleted"} <= _event_labels(pristine)
        command.downgrade(alembic_config, "-1")
        assert _index_exists(pristine, "ix_materials_search_vector")
        command.upgrade(alembic_config, "head")
        assert _index_exists(pristine, "ix_materials_search_vector")

    def test_downgrade_two_steps_removes_only_the_search_index(self, pristine, alembic_config):
        command.upgrade(alembic_config, "head")
        assert _index_exists(pristine, "ix_materials_search_vector")
        command.downgrade(alembic_config, "-2")
        assert not _index_exists(pristine, "ix_materials_search_vector")
        assert _tables(pristine) == EXPECTED_TABLES
        command.upgrade(alembic_config, "head")
        assert _index_exists(pristine, "ix_materials_search_vector")

    def test_downgrade_three_steps_removes_auth_tokens(self, pristine, alembic_config):
        command.upgrade(alembic_config, "head")
        command.downgrade(alembic_config, "-3")
        assert _tables(pristine) == EXPECTED_TABLES - {"auth_tokens"}
        command.upgrade(alembic_config, "head")
        assert _tables(pristine) == EXPECTED_TABLES

    def test_downgrade_four_steps_removes_all_state_tables(self, pristine, alembic_config):
        command.upgrade(alembic_config, "head")
        command.downgrade(alembic_config, "-4")
        assert _tables(pristine) == FIRST_TABLES
        assert _enum_types(pristine) == {"user_role", "account_status", "file_type", "event_type"}
        command.upgrade(alembic_config, "head")
        assert _tables(pristine) == EXPECTED_TABLES


class TestUpgradeToHead:
    """`upgrade_to_head` — то, что вызывает приложение при старте («включил и забыл»)."""

    def test_creates_schema_from_scratch(self, pristine):
        upgrade_to_head(pristine)
        assert _tables(pristine) == EXPECTED_TABLES
        ensure_schema_is_current(pristine)

    def test_repeated_call_changes_nothing(self, pristine):
        upgrade_to_head(pristine)
        upgrade_to_head(pristine)
        assert _tables(pristine) == EXPECTED_TABLES

    def test_simultaneous_starts_do_not_conflict(self, pristine):
        """Две копии приложения стартуют вместе: блокировка не даёт им мешать друг другу."""
        from concurrent.futures import ThreadPoolExecutor

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(upgrade_to_head, pristine) for _ in range(2)]
            for future in futures:
                future.result(timeout=60)
        assert _tables(pristine) == EXPECTED_TABLES
        ensure_schema_is_current(pristine)

    def test_lock_is_released_afterwards(self, pristine):
        upgrade_to_head(pristine)
        with pristine.connect() as connection:
            assert connection.scalar(
                text("SELECT pg_try_advisory_lock(:key)"), {"key": MIGRATION_LOCK_KEY}
            )
            connection.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": MIGRATION_LOCK_KEY})

    def test_wait_for_database_returns_at_once_when_ready(self, db_engine):
        wait_for_database(db_engine, 0)


class TestSchemaMatchesModels:
    def test_no_difference_between_models_and_migrated_schema(self, db_engine):
        """То же самое проверяет `alembic check`: модели и миграции не расходятся."""
        with db_engine.connect() as connection:
            context = MigrationContext.configure(
                connection,
                opts={
                    "compare_type": True,
                    "compare_server_default": True,
                    "include_object": include_in_autogenerate,
                },
            )
            assert compare_metadata(context, Base.metadata) == []

    def test_enum_labels_match_python_enums(self, db_engine):
        with db_engine.connect() as connection:
            labels = set(
                connection.scalars(
                    text(
                        "SELECT e.enumlabel FROM pg_enum e JOIN pg_type t ON t.oid = e.enumtypid "
                        "WHERE t.typname = 'event_type'"
                    )
                )
            )
        assert labels == {event.value for event in EventType}
        assert len(labels) == 23

    def test_single_linear_history(self, alembic_config):
        script = ScriptDirectory.from_config(alembic_config)
        assert len(script.get_heads()) == 1


class TestSchemaGuards:
    def test_current_schema_passes_the_check(self, db_engine):
        ensure_schema_is_current(db_engine)
        ensure_database_ready(db_engine)

    def test_unmigrated_database_is_rejected_with_hint(self, pristine):
        with pytest.raises(DatabaseSchemaError, match="alembic upgrade head"):
            ensure_schema_is_current(pristine)

    def test_database_locale_handles_cyrillic_case(self, db_engine):
        ensure_unicode_case_folding(db_engine)
