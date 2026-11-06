"""Документация API (Swagger UI / OpenAPI) и единый вид ошибок. База данных не нужна."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.api.app import create_app


@pytest.fixture(scope="module")
def app():
    return create_app(object())  # type: ignore[arg-type]


@pytest.fixture(scope="module")
def schema(app) -> dict:
    return app.openapi()


@pytest.fixture(scope="module")
def client(app) -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


def operations(schema: dict):
    for path, methods in schema["paths"].items():
        for method, operation in methods.items():
            yield method.upper(), path, operation


def test_every_operation_has_summary_description_and_tag(schema):
    for method, path, operation in operations(schema):
        label = f"{method} {path}"
        assert operation.get("summary"), label
        assert len(operation.get("description", "")) >= 10, label  # из docstring функции
        assert operation.get("tags"), label


def test_every_operation_is_grouped_by_a_declared_tag(schema):
    declared = {tag["name"] for tag in schema["tags"]}
    for method, path, operation in operations(schema):
        assert set(operation["tags"]) <= declared, f"{method} {path}"
    assert all(tag.get("description") for tag in schema["tags"])


def test_every_success_response_has_a_schema_or_is_empty(schema):
    for method, path, operation in operations(schema):
        ok = [code for code in operation["responses"] if code.startswith("2")]
        assert ok, f"{method} {path}"
        for code in ok:
            response = operation["responses"][code]
            assert response.get("description"), f"{method} {path} {code}"
            if code == "204" or path.endswith("/download"):
                continue
            assert response["content"]["application/json"]["schema"], f"{method} {path}"


def test_every_operation_documents_validation_and_server_errors(schema):
    for method, path, operation in operations(schema):
        codes = set(operation["responses"])
        assert {"422", "500"} <= codes, f"{method} {path}: {sorted(codes)}"
        for code in codes:
            if code.startswith(("4", "5")):
                body = operation["responses"][code]["content"]["application/json"]["schema"]
                assert "ErrorResponse" in str(body) or "ValidationErrorResponse" in str(body), (
                    f"{method} {path} {code}"
                )


def test_protected_operations_document_401_and_403(schema):
    public = {
        ("POST", "/api/auth/login"),
        ("POST", "/api/auth/password/recovery"),
        ("POST", "/api/auth/password/reset"),
        ("GET", "/api/health"),
    }
    for method, path, operation in operations(schema):
        if (method, path) not in public:
            assert {"401", "403"} <= set(operation["responses"]), f"{method} {path}"


def test_conflicts_and_missing_objects_are_documented(schema):
    paths = schema["paths"]
    assert "409" in paths["/api/disciplines"]["post"]["responses"]
    assert "409" in paths["/api/topics/{topic_id}"]["delete"]["responses"]
    assert "409" in paths["/api/users"]["post"]["responses"]
    assert "404" in paths["/api/materials/{material_id}"]["get"]["responses"]
    assert {"413", "415"} <= set(paths["/api/materials"]["post"]["responses"])


def test_every_schema_field_has_description_and_example(schema):
    for name, definition in schema["components"]["schemas"].items():
        if name in {"HTTPValidationError", "ValidationError"}:  # стандартные схемы FastAPI
            continue
        for field, spec in definition.get("properties", {}).items():
            variants = [spec, *spec.get("anyOf", [])]
            assert any("description" in v for v in variants), f"{name}.{field}: нет description"
            assert any("examples" in v or "example" in v for v in variants), (
                f"{name}.{field}: нет examples"
            )


def test_constraints_are_visible_in_the_schema(schema):
    schemas = schema["components"]["schemas"]
    title = schemas["MaterialUpdateRequest"]["properties"]["title"]["anyOf"][0]
    assert title["minLength"] == 1 and title["maxLength"] == 200
    login = schemas["LoginRequest"]["properties"]["login"]
    assert login["minLength"] == 1 and login["maxLength"] == 50
    assert schemas["MaterialUpdateRequest"]["additionalProperties"] is False
    path_id = next(
        p
        for p in schema["paths"]["/api/materials/{material_id}"]["get"]["parameters"]
        if p["name"] == "material_id"
    )
    assert path_id["schema"]["minimum"] == 1 and path_id["schema"]["maximum"] == 2**31 - 1
    query = {p["name"]: p for p in schema["paths"]["/api/materials"]["get"]["parameters"]}
    assert query["limit"]["schema"]["anyOf"][0]["maximum"] == 100
    assert "description" in query["q"] and query["q"].get("examples") or query["q"]["schema"]


def test_swagger_ui_and_openapi_json_are_served(client):
    assert client.get("/docs").status_code == 200
    assert client.get("/redoc").status_code == 200
    body = client.get("/openapi.json").json()
    assert body["openapi"].startswith("3.") and body["info"]["title"]


def test_validation_error_is_a_human_readable_detail_string(client):
    response = client.post("/api/auth/login", json={"login": "", "extra": 1})
    assert response.status_code == 422
    body = response.json()
    assert isinstance(body["detail"], str) and "login" in body["detail"]
    assert body["code"] == "RequestValidationError"
    fields = {item["field"]: item for item in body["errors"]}
    assert "слишком короткое" in fields["login"]["message"]
    assert "обязательное" in fields["password"]["message"]
    assert "такого поля нет" in fields["extra"]["message"]


def test_custom_validator_messages_are_passed_through(client):
    response = client.post("/api/auth/login", json={"login": "a\x00b", "password": "x"})
    assert response.status_code == 422
    assert "управляющие символы" in response.json()["detail"]


def test_unknown_route_and_wrong_method_are_json_errors(client):
    missing = client.get("/api/nothing-here")
    assert missing.status_code == 404 and missing.json()["detail"] == "Такого адреса нет."
    wrong = client.put("/api/materials")
    assert wrong.status_code == 405 and "не поддерживается" in wrong.json()["detail"]
    assert "allow" in {key.lower() for key in wrong.headers}


def test_malformed_json_is_422_not_500(client):
    response = client.post(
        "/api/auth/login", content=b"{oops", headers={"Content-Type": "application/json"}
    )
    assert response.status_code == 422
    assert "JSON" in response.json()["detail"]
