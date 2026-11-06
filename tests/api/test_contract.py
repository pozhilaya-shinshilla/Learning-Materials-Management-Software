"""Контракт API: набор методов из ТЗ, `response_model`, DTO и перевод ошибок в статусы."""

from __future__ import annotations

import re

import pytest
from pydantic import ValidationError as PydanticValidationError

from src.api.app import create_app
from src.api.errors import status_for
from src.domain import exceptions as exc
from src.dtos.requests import LoginRequest, MaterialListQuery, MaterialUpdateRequest
from src.dtos.responses import UserResponse

# 24 метода из раздела 5.8 технического задания.
REQUIRED_METHODS = {
    ("POST", "/api/auth/login"),
    ("POST", "/api/auth/logout"),
    ("POST", "/api/auth/password/recovery"),
    ("GET", "/api/materials"),
    ("GET", "/api/materials/{id}"),
    ("POST", "/api/materials"),
    ("PATCH", "/api/materials/{id}"),
    ("DELETE", "/api/materials/{id}"),
    ("GET", "/api/materials/{id}/download"),
    ("GET", "/api/disciplines"),
    ("GET", "/api/disciplines/{id}"),
    ("POST", "/api/disciplines"),
    ("PATCH", "/api/disciplines/{id}"),
    ("GET", "/api/topics"),
    ("GET", "/api/topics/{id}"),
    ("POST", "/api/topics"),
    ("PATCH", "/api/topics/{id}"),
    ("GET", "/api/favorites"),
    ("POST", "/api/favorites/{id}"),
    ("DELETE", "/api/favorites/{id}"),
    ("GET", "/api/users"),
    ("POST", "/api/users"),
    ("PATCH", "/api/users/{id}"),
    ("DELETE", "/api/users/{id}"),
}


@pytest.fixture(scope="module")
def paths() -> dict[str, dict]:
    """Описание всех методов в формате OpenAPI: {путь: {метод: описание}}."""
    return create_app(object()).openapi()["paths"]  # type: ignore[arg-type]


def test_all_methods_from_the_spec_exist(paths):
    present = {
        (method.upper(), re.sub(r"\{[^}]+\}", "{id}", path))
        for path, methods in paths.items()
        for method in methods
    }
    assert present >= REQUIRED_METHODS


def test_every_method_documents_a_json_response_model(paths):
    """Каждый метод с телом ответа описывает схему ответа (`response_model`)."""
    for path, methods in paths.items():
        for method, description in methods.items():
            ok = next(code for code in description["responses"] if code.startswith("2"))
            if ok == "204" or path.endswith("/download"):
                continue
            content = description["responses"][ok]["content"]["application/json"]
            assert content["schema"], f"{method.upper()} {path}"


def test_protected_methods_declare_error_responses(paths):
    assert "401" in paths["/api/materials"]["get"]["responses"]
    assert "403" in paths["/api/users"]["get"]["responses"]


def test_swagger_ui_and_openapi_are_available(client):
    assert client.get("/docs").status_code == 200
    schema = client.get("/openapi.json").json()
    assert "TokenResponse" in schema["components"]["schemas"]
    assert "ErrorResponse" in schema["components"]["schemas"]


def test_health_needs_no_login(client):
    assert client.get("/api/health").json() == {"detail": "ok"}


def test_user_response_has_no_password_fields():
    assert not {"password", "password_hash"} & set(UserResponse.model_fields)


def test_requests_forbid_unknown_fields_and_strip_spaces():
    assert LoginRequest(login="  admin ", password="x").login == "admin"
    with pytest.raises(PydanticValidationError):
        MaterialUpdateRequest(title="Т", author_id=1)


def test_query_rejects_reversed_dates():
    with pytest.raises(PydanticValidationError):
        MaterialListQuery(uploaded_from="2026-10-10", uploaded_to="2026-10-01")


@pytest.mark.parametrize(
    ("error", "status"),
    [
        (exc.AuthenticationError(), 401),
        (exc.InvalidTokenError(), 401),
        (exc.AccountBlockedError(), 403),
        (exc.CatalogAccessError(), 403),
        (exc.SelfDeleteError(), 403),
        (exc.MaterialNotFoundError(material_id=1), 404),
        (exc.UnknownTopicError(), 404),
        (exc.DuplicateLoginError(login="a"), 409),
        (exc.PasswordTooShortError(min_length=8), 422),
        (exc.FileTooLargeError(max_mb=100), 413),
        (exc.UnsupportedFileTypeError(shown=".exe", allowed="pdf"), 415),
        (exc.DatabaseSchemaError(reason="x"), 500),
        (exc.DomainError(), 400),
    ],
)
def test_domain_errors_map_to_http_statuses(error, status):
    assert status_for(error) == status
