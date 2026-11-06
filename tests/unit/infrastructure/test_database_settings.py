"""Юнит-тесты настроек подключения к БД и проверки локали."""

from __future__ import annotations

from contextlib import contextmanager

import pytest

from src.configs.settings import (
    DEFAULT_DATABASE_URL,
    DEFAULT_TEST_DATABASE_URL,
    Settings,
    normalize_database_url,
    settings,
)
from src.database.health import ensure_unicode_case_folding
from src.domain.exceptions import DatabaseSchemaError, DatabaseSettingsError


class TestNormalizeDatabaseUrl:
    def test_short_scheme_is_switched_to_psycopg(self):
        assert (
            normalize_database_url("postgresql://u:p@h:5432/db")
            == "postgresql+psycopg://u:p@h:5432/db"
        )

    def test_psycopg_scheme_is_kept(self):
        url = "postgresql+psycopg://u:p@h/db"
        assert normalize_database_url(f"  {url}  ") == url

    @pytest.mark.parametrize(
        "url", ["sqlite:///x.db", "mysql://u@h/db", "postgres://u@h/db", "", "localhost/db"]
    )
    def test_other_databases_are_rejected(self, url):
        with pytest.raises(DatabaseSettingsError, match="postgresql"):
            normalize_database_url(url)


class TestSettings:
    def test_reads_environment(self, tmp_path):
        loaded = Settings(tmp_path / "none.env", {"DATABASE_URL": "postgresql://u:p@h/db"})
        assert loaded.database_url == "postgresql+psycopg://u:p@h/db"

    def test_reads_env_file(self, tmp_path):
        env = tmp_path / ".env"
        env.write_text("DATABASE_URL='postgresql+psycopg://u:p@h/db'\n", encoding="utf-8")
        assert Settings(env, {}).database_url == "postgresql+psycopg://u:p@h/db"

    def test_environment_beats_file(self, tmp_path):
        env = tmp_path / ".env"
        env.write_text("DATABASE_URL=postgresql://u:p@file/db\n", encoding="utf-8")
        loaded = Settings(env, {"DATABASE_URL": "postgresql://u:p@env/db"})
        assert "@env/" in loaded.database_url

    @pytest.mark.parametrize("environ", [{}, {"DATABASE_URL": ""}, {"DATABASE_URL": "   "}])
    def test_default_url_is_used_when_not_set(self, tmp_path, environ):
        assert Settings(tmp_path / "none.env", environ).database_url == DEFAULT_DATABASE_URL

    def test_default_url_uses_psycopg_driver(self):
        assert DEFAULT_DATABASE_URL.startswith("postgresql+psycopg://")

    def test_invalid_url_is_rejected(self, tmp_path):
        with pytest.raises(DatabaseSettingsError, match="postgresql"):
            Settings(tmp_path / "none.env", {"DATABASE_URL": "sqlite:///x.db"})

    def test_test_database_url_has_default_and_can_be_set(self, tmp_path):
        assert Settings(tmp_path / "none.env", {}).test_database_url == DEFAULT_TEST_DATABASE_URL
        loaded = Settings(tmp_path / "none.env", {"TEST_DATABASE_URL": "postgresql://u:p@h/t"})
        assert loaded.test_database_url == "postgresql+psycopg://u:p@h/t"

    def test_module_singleton_exists(self):
        assert settings.database_url.startswith("postgresql+psycopg://")


class _FakeEngine:
    """Движок, у которого `lower('Д')` возвращает заданную строку."""

    def __init__(self, lowered: str) -> None:
        self._lowered = lowered

    @contextmanager
    def connect(self):
        lowered = self._lowered

        class Connection:
            def scalar(self, _statement):
                return lowered

        yield Connection()


class TestUnicodeCaseFolding:
    def test_utf8_locale_is_accepted(self):
        ensure_unicode_case_folding(_FakeEngine("д"))

    def test_c_locale_is_rejected_with_hint(self):
        with pytest.raises(DatabaseSchemaError, match="UTF-8"):
            ensure_unicode_case_folding(_FakeEngine("Д"))
