"""Глобальные обработчики ошибок и запуск приложения: БД и окружение заменены двойниками."""

from __future__ import annotations

from unittest.mock import MagicMock

import psycopg
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.exc import DBAPIError, IntegrityError, OperationalError

import src.api.app as app_module
from src.api.app import create_app
from src.api.errors import register_exception_handlers
from src.domain.exceptions import AuthenticationError


def _failing_app(error: BaseException) -> TestClient:
    """Маленькое приложение с одной ручкой, которая всегда падает заданной ошибкой."""
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/boom")
    def boom():
        raise error

    return TestClient(app, raise_server_exceptions=False)


def _db_error(kind: type[DBAPIError], orig: Exception) -> DBAPIError:
    return kind("SELECT 1", {}, orig)


@pytest.mark.parametrize(
    ("error", "status", "code"),
    [
        (
            _db_error(OperationalError, psycopg.OperationalError("нет связи")),
            503,
            "DatabaseUnavailable",
        ),
        (_db_error(IntegrityError, psycopg.errors.UniqueViolation("дубль")), 409, "IntegrityError"),
        (
            _db_error(DBAPIError, psycopg.errors.StringDataRightTruncation("длинно")),
            422,
            "DataError",
        ),
        (RuntimeError("баг"), 500, "InternalError"),
        (KeyError("нет ключа"), 500, "InternalError"),
    ],
)
def test_internal_failures_become_json_without_traceback(error, status, code):
    response = _failing_app(error).get("/boom")
    assert response.status_code == status
    assert response.json()["code"] == code
    assert "Traceback" not in response.text and "нет связи" not in response.text


def test_unavailable_database_asks_the_client_to_retry():
    error = _db_error(OperationalError, psycopg.OperationalError("нет связи"))
    assert _failing_app(error).get("/boom").headers["Retry-After"] == "5"


def test_http_error_keeps_its_status_and_headers():
    error = HTTPException(status_code=418, detail="чайник", headers={"X-Tea": "1"})
    response = _failing_app(error).get("/boom")
    assert (response.status_code, response.json()["detail"], response.headers["X-Tea"]) == (
        418,
        "чайник",
        "1",
    )


def test_domain_error_uses_its_message():
    response = _failing_app(AuthenticationError()).get("/boom")
    assert response.status_code == 401
    assert response.json()["detail"] == AuthenticationError.message


class TestLifespan:
    def test_runtime_is_built_on_start_and_shut_down_on_stop(self, monkeypatch):
        context, shutdown = MagicMock(name="context"), MagicMock(name="shutdown")
        monkeypatch.setattr(app_module, "build_runtime_context", MagicMock(return_value=context))
        monkeypatch.setattr(app_module, "shutdown_runtime", shutdown)
        app = create_app()
        with TestClient(app):
            assert app.state.context is context
            shutdown.assert_not_called()
        shutdown.assert_called_once_with()

    def test_startup_failure_is_reported_in_plain_words(self, monkeypatch):
        failing = MagicMock(
            side_effect=OperationalError("SELECT 1", {}, psycopg.OperationalError("нет БД"))
        )
        monkeypatch.setattr(app_module, "build_runtime_context", failing)
        shutdown = MagicMock()
        monkeypatch.setattr(app_module, "shutdown_runtime", shutdown)
        with (
            pytest.raises(RuntimeError, match="Не удалось запустить приложение"),
            TestClient(create_app()),
        ):
            pass
        shutdown.assert_not_called()  # раз ничего не запустилось, останавливать нечего

    def test_ready_made_context_skips_the_runtime(self, monkeypatch):
        build = MagicMock()
        monkeypatch.setattr(app_module, "build_runtime_context", build)
        with TestClient(create_app(MagicMock(name="context"))):
            pass
        build.assert_not_called()
