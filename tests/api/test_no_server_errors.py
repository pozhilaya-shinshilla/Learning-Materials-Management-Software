"""Ни один запрос не должен давать 500: враждебные и бессмысленные запросы ко всем методам API.

Тест обходит все маршруты приложения и подставляет в пути, тела, параметры и файлы значения,
на которых обычно «падают» серверы: огромные числа, нулевые символы, слишком длинные строки,
неверные типы, битый JSON, странные имена файлов. Допустим любой код, кроме 5xx, и любой
ответ-ошибка обязан быть JSON вида `{"detail": "текст"}`.
"""

from __future__ import annotations

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from src.api.app import create_app
from src.services.session_service import SessionService

BAD_IDS = ["0", "-1", "99999999999999999999", "2147483648", "abc", "1.5", "%00", "1%20OR%201=1"]
BAD_STRINGS = [
    "",
    " ",
    "\x00",
    "a\x00b",
    "x" * 100_000,
    "я" * 5_000,
    "'; DROP TABLE users; --",
    "\U0001f600" * 300,
    "‮\u0000",
]
BAD_BODIES = [
    {},
    [],
    "text",
    None,
    123,
    {"login": None, "password": None},
    {"name": "\x00"},
    {"name": "x" * 5000},
    {"title": "\x00", "discipline_id": 2**40, "topic_id": -1},
    {"discipline_id": 2**200, "name": "n"},
    {"role": "root", "status": "gone"},
    {"login": "a" * 10_000, "email": "e", "password": "p"},
    {"email": "\x00@x"},
    {"token": "\x00", "new_password": "\x00"},
    {"unknown": 1},
]


@pytest.fixture
def lenient(api_context) -> TestClient:
    """Клиент, который возвращает 500 как ответ, а не пробрасывает исключение в тест."""
    return TestClient(create_app(api_context), raise_server_exceptions=False)


def assert_fine(response, label: str) -> None:
    assert response.status_code < 500, f"{label}: {response.status_code} {response.text[:300]}"
    if response.status_code >= 400:
        body = response.json()
        assert isinstance(body.get("detail"), str) and body["detail"], f"{label}: {body}"


def routes(app) -> list[tuple[str, str]]:
    found = []
    for route in app.routes:
        if isinstance(route, APIRoute) and route.path.startswith("/api"):
            for method in route.methods - {"HEAD", "OPTIONS"}:
                found.append((method, route.path))
    return found


def fill(path: str, value: str) -> str:
    import re

    return re.sub(r"\{[^}]+\}", value, path)


def test_bad_path_ids_never_cause_500(lenient, admin):
    for method, path in routes(lenient.app):
        if "{" not in path:
            continue
        for bad in BAD_IDS:
            response = lenient.request(method, fill(path, bad), headers=admin.headers, json={})
            assert_fine(response, f"{method} {path} id={bad!r}")


def test_bad_json_bodies_never_cause_500(lenient, admin, catalog):
    for method, path in routes(lenient.app):
        if method not in {"POST", "PATCH", "PUT"} or path == "/api/materials":
            continue
        target = fill(path, str(catalog["discipline_id"]))
        for body in BAD_BODIES:
            response = lenient.request(method, target, headers=admin.headers, json=body)
            assert_fine(response, f"{method} {path} body={str(body)[:40]!r}")
        for raw in (b"{not json", b"\xff\xfe\x00", b"", b'{"a":' + b"[" * 10_000):
            response = lenient.request(
                method,
                target,
                headers={**admin.headers, "Content-Type": "application/json"},
                content=raw,
            )
            assert_fine(response, f"{method} {path} raw={raw[:10]!r}")


def test_bad_query_parameters_never_cause_500(lenient, admin):
    params = [
        {"q": s} for s in BAD_STRINGS + ["!!!", "&|:*()", "а:*", "'", "\\", "<->", "a b c d " * 50]
    ]
    params += [{"discipline_id": v} for v in BAD_IDS] + [{"topic_id": v} for v in BAD_IDS]
    params += [
        {"uploaded_from": "9999-12-31", "uploaded_to": "9999-12-31"},
        {"uploaded_from": "0001-01-01"},
        {"uploaded_from": "2026-02-30"},
        {"limit": "99999999999999999999"},
        {"offset": "99999999999999999999"},
        {"offset": str(2**63)},
        {"limit": "1", "offset": str(2**31)},
        {"sort_by": "'", "order": "up"},
        {"file_type": "exe"},
        {"unknown": "1"},
    ]
    for item in params:
        if any(len(str(v)) > 20_000 for v in item.values()):  # клиент httpx не отправит такой адрес
            continue
        for path in ("/api/materials", "/api/topics", "/api/favorites", "/api/events"):
            assert_fine(lenient.get(path, headers=admin.headers, params=item), f"{path} {item}")


def test_bad_uploads_never_cause_500(lenient, teacher, catalog):
    fields = {k: str(v) for k, v in catalog.items()}
    cases = [
        ({"title": "t", **fields}, {"file": ("a" * 400 + ".pdf", b"%PDF", "application/pdf")}),
        ({"title": "t", **fields}, {"file": ("a\x00b.pdf", b"%PDF", "application/pdf")}),
        ({"title": "t", **fields}, {"file": ("..", b"%PDF", "application/pdf")}),
        ({"title": "t", **fields}, {"file": ("..\\..\\x.pdf", b"%PDF", "application/pdf")}),
        ({"title": "t", **fields}, {"file": (".pdf", b"%PDF", "application/pdf")}),
        ({"title": "t", **fields}, {"file": ("x.pdf", b"", "application/pdf")}),
        ({"title": "t", **fields}, {"file": ("x", b"%PDF", "application/pdf")}),
        ({"title": "\x00", **fields}, {"file": ("x.pdf", b"%PDF", "application/pdf")}),
        ({"title": "t" * 5000, **fields}, {"file": ("x.pdf", b"%PDF", "application/pdf")}),
        (
            {"title": "t", "discipline_id": "99999999999", "topic_id": "1"},
            {"file": ("x.pdf", b"%", "a/b")},
        ),
        ({"title": "t", "discipline_id": "x", "topic_id": "1"}, {"file": ("x.pdf", b"%", "a/b")}),
        ({"title": "t", **fields, "description": "\x00"}, {"file": ("x.pdf", b"%PDF", "a/b")}),
        ({"title": "t", **fields}, {}),
        ({}, {}),
        ({"title": "t", **fields, "file": "not-a-file"}, {}),
    ]
    for data, files in cases:
        response = lenient.post(
            "/api/materials", headers=teacher.headers, data=data, files=files or None
        )
        assert_fine(response, f"upload {str(data)[:50]} {list(files)}")
    response = lenient.post(
        "/api/materials",
        headers={**teacher.headers, "Content-Type": "multipart/form-data; boundary=x"},
        content=b"--x\r\nbroken",
    )
    assert_fine(response, "broken multipart")


def test_bad_headers_and_methods_never_cause_500(lenient, admin):
    for headers in (
        {"Authorization": "Bearer"},
        {"Authorization": "Bearer \x00"},
        {"Authorization": "Basic abc"},
        {"Authorization": "Bearer " + "a" * 100_000},
        {"Authorization": "Bearer ñ"},
    ):
        try:
            response = lenient.get("/api/materials", headers=headers)
        except UnicodeEncodeError:  # клиент не умеет отправить такой заголовок
            continue
        assert_fine(response, f"headers {str(headers)[:40]}")
    for method, path in (
        ("PUT", "/api/materials"),
        ("DELETE", "/api/auth/login"),
        ("POST", "/api/health"),
    ):
        assert_fine(lenient.request(method, path, headers=admin.headers), f"{method} {path}")
    assert_fine(lenient.get("/api/нет/такого", headers=admin.headers), "unknown path")
    assert_fine(lenient.get("/api/materials/%ff", headers=admin.headers), "bad percent-encoding")


def test_login_and_recovery_with_hostile_values(lenient):
    for value in BAD_STRINGS:
        assert_fine(
            lenient.post("/api/auth/login", json={"login": value, "password": value}), "login"
        )
        assert_fine(lenient.post("/api/auth/password/recovery", json={"email": value}), "recovery")
        assert_fine(
            lenient.post("/api/auth/password/reset", json={"token": value, "new_password": value}),
            "reset",
        )


def test_unexpected_exception_is_a_json_500_without_traceback(api_context, monkeypatch):
    app = create_app(api_context)
    client = TestClient(app, raise_server_exceptions=False)

    def boom(*_args, **_kwargs):
        raise RuntimeError("секрет внутри")

    monkeypatch.setattr(SessionService, "authenticate", boom)
    response = client.get("/api/materials", headers={"Authorization": "Bearer x"})
    assert response.status_code == 500
    assert response.json()["code"] == "InternalError"
    assert "секрет" not in response.text and "Traceback" not in response.text


@pytest.mark.parametrize("bad_id", ["0", "-5", "2147483648", "99999999999999999999"])
def test_out_of_range_id_is_422_with_readable_text(lenient, admin, bad_id):
    response = lenient.get(f"/api/materials/{bad_id}", headers=admin.headers)
    assert response.status_code == 422
    assert "material_id" in response.json()["detail"]
