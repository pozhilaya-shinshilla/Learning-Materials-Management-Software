"""Метаданные ORM соответствуют ER-диаграмме (`docs/database-er.md`); БД не нужна."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from sqlalchemy import CheckConstraint, ForeignKeyConstraint, UniqueConstraint
from sqlalchemy.orm import configure_mappers

import src.database.models  # noqa: F401
from src.database.base import Base

ROOT = Path(__file__).resolve().parents[3]
TABLES = Base.metadata.tables


def test_all_tables_from_er_diagram_exist():
    assert set(TABLES) == {
        "users",
        "disciplines",
        "topics",
        "materials",
        "favorites",
        "events",
        "password_reset_tokens",
        "auth_tokens",
        "failed_logins",
        "material_revisions",
    }


@pytest.mark.parametrize("table", sorted(TABLES))
def test_every_table_has_primary_key(table):
    assert list(TABLES[table].primary_key.columns)


def test_favorites_has_composite_primary_key():
    assert [c.name for c in TABLES["favorites"].primary_key.columns] == ["user_id", "material_id"]


def test_only_author_and_event_user_are_nullable():
    nullable = {
        f"{table.name}.{column.name}"
        for table in TABLES.values()
        for column in table.columns
        if column.nullable
    }
    assert nullable == {"materials.author_id", "events.user_id"}


def _foreign_keys(table: str) -> dict[tuple[str, ...], tuple[str, str | None]]:
    result = {}
    for constraint in TABLES[table].constraints:
        if isinstance(constraint, ForeignKeyConstraint):
            columns = tuple(c.name for c in constraint.columns)
            result[columns] = (constraint.referred_table.name, constraint.ondelete)
    return result


def test_foreign_keys_and_delete_rules_match_er():
    assert _foreign_keys("topics") == {("discipline_id",): ("disciplines", "RESTRICT")}
    assert _foreign_keys("materials") == {
        ("author_id",): ("users", "SET NULL"),
        ("topic_id", "discipline_id"): ("topics", "RESTRICT"),
    }
    assert _foreign_keys("favorites") == {
        ("user_id",): ("users", "CASCADE"),
        ("material_id",): ("materials", "CASCADE"),
    }
    assert _foreign_keys("events") == {("user_id",): ("users", "SET NULL")}
    assert _foreign_keys("password_reset_tokens") == {("user_id",): ("users", "CASCADE")}
    assert _foreign_keys("auth_tokens") == {("user_id",): ("users", "CASCADE")}
    assert _foreign_keys("material_revisions") == {("material_id",): ("materials", "CASCADE")}
    assert _foreign_keys("failed_logins") == {}


def test_composite_fk_target_is_unique():
    unique = {
        tuple(c.name for c in constraint.columns)
        for constraint in TABLES["topics"].constraints
        if isinstance(constraint, UniqueConstraint)
    }
    assert ("id", "discipline_id") in unique


def test_materials_file_size_check_exists():
    checks = [c for c in TABLES["materials"].constraints if isinstance(c, CheckConstraint)]
    assert [str(c.sqltext) for c in checks] == ["file_size_bytes >= 0"]


def test_indexes_match_er():
    def names(table):
        return {index.name for index in TABLES[table].indexes}

    assert names("materials") == {
        "ix_materials_discipline_id_topic_id",
        "ix_materials_author_id",
        "ix_materials_uploaded_at",
        "ix_materials_title",
        "ix_materials_search_vector",
    }
    assert names("favorites") == {"ix_favorites_material_id"}
    assert names("events") == {"ix_events_occurred_at", "ix_events_user_id"}
    assert names("users") == {"uq_users_lower_email"}
    assert names("disciplines") == {"uq_disciplines_lower_name"}
    assert names("topics") == {"uq_topics_discipline_id_lower_name"}
    assert names("password_reset_tokens") == {
        "ix_password_reset_tokens_user_id",
        "ix_password_reset_tokens_expires_at",
    }
    assert names("auth_tokens") == {"ix_auth_tokens_user_id", "ix_auth_tokens_expires_at"}
    assert names("failed_logins") == {"ix_failed_logins_login"}
    assert names("material_revisions") == {"ix_material_revisions_material_id"}


def test_every_constraint_has_an_explicit_name():
    """Имена нужны, чтобы Alembic мог ссылаться на ограничения в `downgrade`."""
    for table in TABLES.values():
        for constraint in table.constraints:
            assert constraint.name, f"{table.name}: {constraint!r}"


def test_mappers_configure_without_errors_or_warnings():
    configure_mappers()


def test_every_relationship_has_back_populates():
    configure_mappers()
    for mapper in Base.registry.mappers:
        for relationship in mapper.relationships:
            assert relationship.back_populates, f"{mapper.class_.__name__}.{relationship.key}"


FORBIDDEN_CALL = (
    "create" + "_all"
)  # собирается из частей: поиск по тексту проекта не должен находить слово


def test_direct_table_creation_is_never_called():
    """Схему создаёт только Alembic (требование этапа): прямых вызовов создания таблиц нет."""
    for folder in ("src", "migrations", "tests"):
        for path in (ROOT / folder).rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            calls = [
                node
                for node in ast.walk(tree)
                if isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == FORBIDDEN_CALL
            ]
            assert not calls, f"{path}: вызов на строке {calls[0].lineno}"


def test_forbidden_word_is_absent_from_source_text():
    """Проверка из методички: `grep -R` по `src`, `migrations` и `tests` ничего не находит."""
    for folder in ("src", "migrations", "tests"):
        for path in (ROOT / folder).rglob("*.py"):
            assert FORBIDDEN_CALL not in path.read_text(encoding="utf-8"), path
