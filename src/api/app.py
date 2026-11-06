"""Фабрика приложения FastAPI.

`create_app()` без аргументов собирает сервисы при старте сервера из переменных окружения;
`create_app(context)` принимает готовый `ApplicationContext` — так приложение поднимается
в тестах на тестовой БД. Запуск: `uvicorn src.api.app:create_app --factory`.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy.exc import SQLAlchemyError

from src.api.errors import COMMON_RESPONSES, register_exception_handlers
from src.api.routers import ALL_ROUTERS
from src.bootstrap import ApplicationContext
from src.domain.exceptions import DomainError
from src.dtos.responses import MessageResponse
from src.runtime import build_runtime_context, shutdown_runtime

API_DESCRIPTION = """
REST API веб-приложения для управления учебными материалами (ВолгГТУ).

**Как работать:** выполните `POST /api/auth/login`, скопируйте `access_token` и нажмите
**Authorize** — дальше Swagger UI будет подставлять токен в заголовок
`Authorization: Bearer <токен>`. Права зависят от роли: студент, преподаватель, администратор.

Ошибки бизнес-правил возвращаются в виде `{"detail": "<текст>", "code": "<ИмяОшибки>"}`.
"""

OPENAPI_TAGS = [
    {"name": "Аутентификация", "description": "Вход, выход, восстановление пароля."},
    {"name": "Учебные материалы", "description": "Каталог, поиск, загрузка и скачивание."},
    {"name": "Дисциплины", "description": "Учебные дисциплины."},
    {"name": "Темы", "description": "Темы внутри дисциплин."},
    {"name": "Избранное", "description": "Закладки текущего пользователя."},
    {"name": "Пользователи", "description": "Управление учётными записями (администратор)."},
    {"name": "Журнал событий", "description": "Системный журнал (администратор)."},
    {"name": "Служебное", "description": "Проверка работоспособности."},
]


def create_app(context: ApplicationContext | None = None) -> FastAPI:
    """Создать приложение; без `context` сервисы собираются при старте из окружения."""

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        if context is not None:
            yield
            return
        try:
            app.state.context = build_runtime_context()
        except (DomainError, SQLAlchemyError) as error:
            raise RuntimeError(f"Не удалось запустить приложение: {error}") from error
        try:
            yield
        finally:
            shutdown_runtime()

    app = FastAPI(
        title="Учебные материалы: REST API",
        version="1.0.0",
        description=API_DESCRIPTION,
        openapi_tags=OPENAPI_TAGS,
        lifespan=lifespan,
        responses=COMMON_RESPONSES,
    )
    if context is not None:
        app.state.context = context
    register_exception_handlers(app)
    for router in ALL_ROUTERS:
        app.include_router(router)

    @app.get(
        "/api/health",
        response_model=MessageResponse,
        tags=["Служебное"],
        summary="Проверка работоспособности",
    )
    def health() -> MessageResponse:
        """Вернуть `ok`, если сервер запущен."""
        return MessageResponse(detail="ok")

    return app
