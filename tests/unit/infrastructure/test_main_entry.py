"""Единая точка входа `src/main.py`: команды, параметры и обработка ошибок."""

from __future__ import annotations

import pytest
from sqlalchemy.exc import OperationalError

from src import main as entry
from src.configs.settings import ServerSettings
from src.domain.exceptions import AdminPasswordNotSetError, DatabaseUnavailableError


@pytest.fixture
def calls(monkeypatch) -> list[tuple]:
    """Подменяет всё, что трогает БД и сеть, и записывает вызовы по порядку."""
    log: list[tuple] = []
    monkeypatch.setattr(entry, "load_server_settings", lambda: ServerSettings())
    monkeypatch.setattr(entry, "check_configuration", lambda: log.append(("check",)))
    monkeypatch.setattr(
        entry,
        "prepare_database",
        lambda settings, migrate=None: log.append(("prepare", settings, migrate)),
    )
    monkeypatch.setattr(entry, "create_app", lambda: "APP")
    monkeypatch.setattr(entry.uvicorn, "run", lambda app, **kw: log.append(("uvicorn", app, kw)))
    monkeypatch.setattr(entry.engine, "dispose", lambda: log.append(("dispose",)))
    return log


class TestServe:
    def test_no_arguments_start_the_server(self, calls):
        entry.main([])
        assert [c[0] for c in calls] == ["check", "prepare", "uvicorn"]
        _, app, options = calls[2]
        assert app == "APP"
        assert (options["host"], options["port"]) == ("127.0.0.1", 8000)

    def test_configuration_is_checked_before_the_database_is_touched(self, calls):
        entry.main([])
        assert calls[0] == ("check",)

    def test_serve_command_is_the_same_as_default(self, calls):
        entry.main(["serve"])
        assert [c[0] for c in calls] == ["check", "prepare", "uvicorn"]

    def test_host_and_port_can_be_overridden(self, calls):
        entry.main(["serve", "--host", "0.0.0.0", "--port", "9000"])
        assert (calls[2][2]["host"], calls[2][2]["port"]) == ("0.0.0.0", 9000)
        assert calls[1][1].host == "0.0.0.0"

    def test_environment_settings_are_used_when_no_flags(self, calls, monkeypatch):
        monkeypatch.setattr(entry, "load_server_settings", lambda: ServerSettings("::1", 8123))
        entry.main([])
        assert (calls[2][2]["host"], calls[2][2]["port"]) == ("::1", 8123)

    def test_no_migrate_flag_turns_migrations_off(self, calls):
        entry.main(["serve", "--no-migrate"])
        assert calls[1][1].auto_migrate is False

    def test_migrations_are_on_by_default(self, calls):
        entry.main([])
        assert calls[1][1].auto_migrate is True


class TestMigrateCommand:
    def test_forces_migrations_and_exits(self, calls, capsys):
        entry.main(["migrate"])
        assert [c[0] for c in calls] == ["prepare", "dispose"]
        assert calls[0][2] is True
        assert "Миграции применены" in capsys.readouterr().out

    def test_migrate_works_even_if_auto_migrate_is_off(self, calls, monkeypatch):
        monkeypatch.setattr(
            entry, "load_server_settings", lambda: ServerSettings(auto_migrate=False)
        )
        entry.main(["migrate"])
        assert calls[0][2] is True


class TestCliCommand:
    @pytest.fixture
    def cli(self, calls, monkeypatch):
        class FakeApplication:
            def __init__(self, context, io):
                calls.append(("cli-init", context))

            def run(self):
                calls.append(("cli-run",))

        monkeypatch.setattr(entry, "CliApplication", FakeApplication)
        monkeypatch.setattr(entry, "ConsoleIO", lambda: "IO")
        monkeypatch.setattr(entry, "load_admin_settings", lambda: "ADMIN")
        monkeypatch.setattr(
            entry,
            "build_transactional_context",
            lambda session_factory, *, admin: ("CONTEXT", session_factory, admin),
        )
        return calls

    def test_prepares_database_then_runs_console(self, cli):
        entry.main(["cli"])
        names = [c[0] for c in cli]
        assert names == ["check", "prepare", "cli-init", "cli-run", "dispose"]
        assert cli[2][1] == ("CONTEXT", entry.SessionFactory, "ADMIN")

    def test_connections_are_closed_even_if_console_fails(self, cli, monkeypatch):
        def boom(self):
            raise RuntimeError("сбой")

        monkeypatch.setattr(entry.CliApplication, "run", boom)
        with pytest.raises(RuntimeError):
            entry.main(["cli"])
        assert ("dispose",) in cli


class TestErrors:
    def test_configuration_error_exits_with_readable_text(self, calls, monkeypatch):
        def fail():
            raise AdminPasswordNotSetError()

        monkeypatch.setattr(entry, "check_configuration", fail)
        with pytest.raises(SystemExit) as info:
            entry.main([])
        assert "Ошибка настройки приложения" in str(info.value)
        assert "uvicorn" not in [c[0] for c in calls]

    def test_unavailable_database_exits_with_readable_text(self, calls, monkeypatch):
        def fail(settings, migrate=None):
            raise DatabaseUnavailableError(seconds=30, reason="connection refused")

        monkeypatch.setattr(entry, "prepare_database", fail)
        with pytest.raises(SystemExit) as info:
            entry.main([])
        assert "30 с" in str(info.value) and "connection refused" in str(info.value)

    def test_sqlalchemy_error_exits_without_traceback(self, calls, monkeypatch):
        def fail(settings, migrate=None):
            raise OperationalError("SELECT 1", None, Exception("плохо"))

        monkeypatch.setattr(entry, "prepare_database", fail)
        with pytest.raises(SystemExit) as info:
            entry.main([])
        assert "базой данных" in str(info.value)

    def test_unknown_command_is_rejected_by_argparse(self, calls):
        with pytest.raises(SystemExit) as info:
            entry.main(["frobnicate"])
        assert info.value.code == 2

    def test_bad_port_flag_is_rejected_by_argparse(self, calls):
        with pytest.raises(SystemExit):
            entry.main(["serve", "--port", "abc"])
