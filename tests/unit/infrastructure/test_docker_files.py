"""Файлы развёртывания: защита от случайных поломок (Docker в тестах не запускается)."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8")


def test_dockerfile_starts_the_single_entry_point_as_non_root():
    dockerfile = read("Dockerfile")
    assert 'CMD ["python", "-m", "src.main"]' in dockerfile
    assert "USER app" in dockerfile
    assert "HEALTHCHECK" in dockerfile and "/api/health" in dockerfile
    assert "--frozen" in dockerfile  # версии зависимостей строго из uv.lock


def test_dockerfile_copies_what_the_app_needs():
    dockerfile = read("Dockerfile")
    for required in ("alembic.ini", "migrations", "src"):
        assert f"COPY {required}" in dockerfile


def test_secrets_and_junk_stay_out_of_the_image():
    ignored = set(read(".dockerignore").split())
    assert {".env", ".venv", ".git", "data"} <= ignored
    assert "!.env.example" in ignored


def test_compose_runs_app_after_a_healthy_database():
    compose = read("docker-compose.yaml")
    assert "  app:" in compose and "  db:" in compose
    assert "condition: service_healthy" in compose
    assert "@db:5432" in compose  # внутри сети compose база доступна по имени сервиса
    assert "lms_uploads:/app/data" in compose  # загрузки переживают пересоздание контейнера
    assert "restart: unless-stopped" in compose


def test_every_server_setting_is_documented_in_env_example():
    example = read(".env.example")
    for name in ("APP_HOST", "APP_PORT", "DB_WAIT_SECONDS", "AUTO_MIGRATE", "APP_TIMEZONE"):
        assert name in example


def test_env_example_has_no_real_secrets():
    for line in read(".env.example").splitlines():
        if line.startswith("SMTP_PASSWORD="):
            assert line == "SMTP_PASSWORD="


def test_web_container_serves_frontend_and_proxies_api_to_app():
    compose = read("docker-compose.yaml")
    assert "  web:" in compose and "build: ./frontend" in compose
    assert '"8000:80"' in compose  # интерфейс и API на одном адресе
    nginx = read("frontend/nginx.conf")
    assert "proxy_pass http://app:8000" in nginx
    for prefix in ("api", "docs", "redoc", "openapi"):
        assert prefix in nginx
    assert "try_files $uri /index.html" in nginx  # маршруты SPA
    assert "client_max_body_size" in nginx  # загрузка файлов до 100 МБ


def test_app_image_has_no_frontend_stage_and_fastapi_does_not_serve_static():
    assert "node:" not in read("Dockerfile")
    assert "node:22" in read("frontend/Dockerfile") and "nginx" in read("frontend/Dockerfile")
    assert not (ROOT / "src" / "api" / "web.py").exists()
