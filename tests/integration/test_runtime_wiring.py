"""Сборка приложения поверх PostgreSQL: сессия как единица работы (Unit of Work)."""

from __future__ import annotations

import pytest
from sqlalchemy import func, select

from src.bootstrap import build_transactional_context
from src.configs.settings import AdminSettings
from src.database.models import UserEntity
from src.database.transaction import TransactionalService
from src.domain.exceptions import AuthenticationError

ADMIN = AdminSettings("admin", "admin@example.org", "Admin12345!")


def test_every_service_runs_in_its_own_transaction(session_factory, tmp_path):
    context = build_transactional_context(session_factory, admin=ADMIN, upload_root=tmp_path)
    for name in (
        "auth_service",
        "user_management_service",
        "material_service",
        "search_service",
        "favorite_service",
        "event_log_service",
        "catalog_service",
        "session_service",
    ):
        assert isinstance(getattr(context, name), TransactionalService), name


def test_seeded_admin_is_committed_by_the_unit_of_work(session_factory, tmp_path):
    build_transactional_context(session_factory, admin=ADMIN, upload_root=tmp_path)
    with session_factory() as session:  # другая сессия видит данные: транзакция зафиксирована
        assert session.scalar(select(func.count()).select_from(UserEntity)) == 1


def test_failed_login_event_survives_the_domain_error(session_factory, tmp_path):
    """`DomainError` не откатывает работу: событие «неудачный вход» остаётся в журнале."""
    context = build_transactional_context(session_factory, admin=ADMIN, upload_root=tmp_path)
    admin = context.auth_service.login("admin", "Admin12345!")
    with pytest.raises(AuthenticationError):
        context.session_service.open_session("admin", "wrong-password")
    events = context.event_log_service.list_events(admin)
    assert "user_login_failed" in {event.event_type.value for event in events}
