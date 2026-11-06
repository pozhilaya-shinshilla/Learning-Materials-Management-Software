"""Фикстуры тестов REST API.

Приложение собирается теми же функциями, что и в бою, но поверх хранилища в памяти: настоящие
сервисы и роутеры, без базы данных; письма пишутся в `RecordingEmailSender`, файлы — во временную
папку. Тест с меткой `db` (или использующий фикстуры БД) получает приложение на PostgreSQL:
`build_transactional_context` с настоящими транзакциями.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest
from fastapi.testclient import TestClient

from src.api.app import create_app
from src.bootstrap import (
    ApplicationContext,
    build_application_context,
    build_transactional_context,
)
from src.configs.settings import AdminSettings
from src.domain.enums import Role
from tests.memory import InMemoryRepositoryFactory

ADMIN = AdminSettings("admin", "admin@example.org", "Admin12345!")
PASSWORD = "Password123!"
PDF = b"%PDF-1.4\n% test file\n"


@dataclass
class Account:
    """Вошедший пользователь: заголовки для запросов, id и логин."""

    id: int
    login: str
    headers: dict[str, str]


@pytest.fixture
def api_context(request, tmp_path, email_sender) -> ApplicationContext:
    if request.node.get_closest_marker("db") is not None:
        return build_transactional_context(
            request.getfixturevalue("session_factory"),
            admin=ADMIN,
            email_sender=email_sender,
            upload_root=tmp_path / "uploads",
        )
    return build_application_context(
        InMemoryRepositoryFactory(),
        email_sender=email_sender,
        upload_root=tmp_path / "uploads",
        admin=ADMIN,
    )


@pytest.fixture
def client(api_context) -> TestClient:
    return TestClient(create_app(api_context))


def sign_in(client: TestClient, login: str, password: str) -> dict:
    response = client.post("/api/auth/login", json={"login": login, "password": password})
    assert response.status_code == 200, response.text
    return response.json()


def headers_of(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin(client) -> Account:
    data = sign_in(client, ADMIN.login, ADMIN.password)
    return Account(data["user"]["id"], ADMIN.login, headers_of(data["access_token"]))


@pytest.fixture
def make_account(client, admin):
    """Создать пользователя через API администратором и войти под ним."""

    def make(login: str, role: Role) -> Account:
        created = client.post(
            "/api/users",
            headers=admin.headers,
            json={
                "login": login,
                "email": f"{login}@example.org",
                "password": PASSWORD,
                "role": role,
            },
        )
        assert created.status_code == 201, created.text
        data = sign_in(client, login, PASSWORD)
        return Account(created.json()["id"], login, headers_of(data["access_token"]))

    return make


@pytest.fixture
def teacher(make_account) -> Account:
    return make_account("teacher1", Role.TEACHER)


@pytest.fixture
def student(make_account) -> Account:
    return make_account("student1", Role.STUDENT)


@pytest.fixture
def catalog(client, teacher) -> dict[str, int]:
    """Дисциплина «Математика» и тема «Пределы», созданные преподавателем."""
    discipline = client.post(
        "/api/disciplines", headers=teacher.headers, json={"name": "Математика"}
    )
    topic = client.post(
        "/api/topics",
        headers=teacher.headers,
        json={"name": "Пределы", "discipline_id": discipline.json()["id"]},
    )
    return {"discipline_id": discipline.json()["id"], "topic_id": topic.json()["id"]}


@pytest.fixture
def upload(client, catalog):
    """Загрузить материал от имени `account`; вернуть ответ сервера."""

    def do(
        account: Account, title: str = "Лекция по пределам", name: str = "lecture.pdf", body=PDF
    ):
        return client.post(
            "/api/materials",
            headers=account.headers,
            data={
                "title": title,
                "description": "Введение",
                **{k: str(v) for k, v in catalog.items()},
            },
            files={"file": (name, body, "application/octet-stream")},
        )

    return do
