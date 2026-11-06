"""Перебор по схеме OpenAPI (Schemathesis): тысячи сгенерированных запросов к каждому методу.

Схема приложения сама описывает, какие запросы допустимы, а библиотека строит по ней и корректные,
и пограничные, и заведомо неверные запросы (пустые и огромные строки, нулевые символы, числа
вне диапазона, неверные типы). Проверяем две вещи:

* ответ никогда не бывает 5xx;
* код ответа описан в `responses` метода, а тело ошибки — JSON `{"detail": "текст"}`.

Тест медленный, поэтому помечен `fuzz`: `pytest -m "not fuzz"` пропускает его.
Число примеров на метод задаёт `FUZZ_EXAMPLES` (по умолчанию 40; для глубокой проверки — 500).
"""

from __future__ import annotations

import os

import pytest
import schemathesis
from hypothesis import HealthCheck, settings
from starlette.testclient import TestClient

from src.api.app import create_app

pytestmark = pytest.mark.fuzz

SCHEMA = schemathesis.openapi.from_dict(
    create_app(object()).openapi()  # type: ignore[arg-type]
)
# Скачивание файла и загрузка проверяются отдельными тестами; здесь важны JSON-методы и параметры.
schema = SCHEMA


@pytest.fixture
def lenient(api_context) -> TestClient:
    return TestClient(create_app(api_context), raise_server_exceptions=False)


@schema.parametrize()
@settings(
    max_examples=int(os.environ.get("FUZZ_EXAMPLES", "40")),
    deadline=None,
    suppress_health_check=list(HealthCheck),
)
def test_no_server_errors_and_documented_responses(case, lenient, admin):
    kwargs = case.as_transport_kwargs(base_url="http://testserver")
    headers = {**(kwargs.get("headers") or {}), **admin.headers}
    kwargs["headers"] = headers
    response = lenient.request(**{k: v for k, v in kwargs.items() if k != "verify"})
    label = f"{case.method} {case.path}"
    assert response.status_code < 500, f"{label}: {response.status_code} {response.text[:300]}"
    declared = set(case.operation.definition.raw["responses"])
    # Схемата специально шлёт и методы, которых у адреса нет (TRACE и т. п.): 405 — верный ответ.
    served = {m.upper() for m in SCHEMA.raw_schema["paths"][case.operation.path]}
    if case.method.upper() not in served and response.status_code == 405:
        return
    assert str(response.status_code) in declared or "default" in declared, (
        f"{label}: код {response.status_code} не описан в responses {sorted(declared)}"
    )
    if response.status_code >= 400:
        body = response.json()
        assert isinstance(body.get("detail"), str) and body["detail"], f"{label}: {body}"
