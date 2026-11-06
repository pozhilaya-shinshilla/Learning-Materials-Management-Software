"""Запуск приложения «по-настоящему»: проверка настроек, подготовка БД, сборка сервисов.

Общий для консоли и REST API код старта (`src/main.py`, `src/api/app.py`): обе точки входа
одинаково проверяют настройки, готовят базу и собирают `ApplicationContext`.
"""

from __future__ import annotations

import logging

from src.bootstrap import ApplicationContext, build_transactional_context
from src.configs.settings import (
    ServerSettings,
    load_admin_settings,
    load_app_timezone,
    load_smtp_settings,
)
from src.database.health import ensure_database_ready
from src.database.migrations import upgrade_to_head, wait_for_database
from src.database.session import SessionFactory, engine

logger = logging.getLogger(__name__)


def check_configuration() -> None:
    """Проверить все настройки до запуска: ошибка в `.env` видна сразу, а не после старта.

    Выбрасывает `DomainError` с понятным текстом (нет `ADMIN_PASSWORD`, плохой `SMTP_PORT`...).
    """
    load_admin_settings()
    load_smtp_settings()
    load_app_timezone()


def prepare_database(server: ServerSettings, *, migrate: bool | None = None) -> None:
    """Дождаться базы данных и (если не отключено) применить миграции.

    `migrate=None` берёт значение из настроек (`AUTO_MIGRATE`). После этого схема актуальна, и
    приложение стартует без ручного `alembic upgrade head`.
    """
    wait_for_database(engine, server.db_wait_seconds)
    if server.auto_migrate if migrate is None else migrate:
        logger.info("Применяю миграции базы данных...")
        upgrade_to_head(engine)


def build_runtime_context() -> ApplicationContext:
    """Проверить базу и собрать приложение с настройками из окружения и `.env`.

    Выбрасывает `DomainError` (некорректные настройки, не применены миграции) или
    `SQLAlchemyError` (база недоступна): вызывающий код решает, как о них сообщить.
    """
    admin = load_admin_settings()
    ensure_database_ready(engine)
    return build_transactional_context(SessionFactory, admin=admin)


def shutdown_runtime() -> None:
    """Закрыть соединения с базой данных."""
    engine.dispose()
