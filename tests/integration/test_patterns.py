"""Интеграционные проверки: паттерны работают вместе в собранном приложении."""

from __future__ import annotations

import pytest

from src.cli.controller_factory import CONTROLLER_FACTORIES
from src.domain.enums import EventType, Role
from src.domain.exceptions import AuthenticationError, DomainError, ForeignMaterialAccessError
from src.services.event_log_service import EventLogService
from tests.integration.conftest import _register


@pytest.fixture
def editable_material(context, teacher, tmp_path):
    discipline = context.catalog_service.create_discipline(teacher, "Физика")
    topic = context.catalog_service.create_topic(teacher, "Механика", discipline.id)
    source = tmp_path / "f.pdf"
    source.write_bytes(b"x")
    return context.material_service.create_material(
        teacher, "Исходное", "описание", discipline.id, topic.id, source
    )


def test_controller_factories_work_with_real_context(context, admin):
    for factory in CONTROLLER_FACTORIES.values():
        assert factory.create_controller(context, None, admin).menu_items()
    assert set(CONTROLLER_FACTORIES) == set(Role)


def test_event_log_is_the_subject_of_the_application(context):
    assert isinstance(context.event_log_service, EventLogService)


def test_failed_login_alert_after_three_failures(context, email_sender):
    for _ in range(3):
        with pytest.raises(AuthenticationError):
            context.auth_service.login("admin", "bad-password")
    alerts = [m for m in email_sender.sent if m[1] == "Подозрительные попытки входа"]
    assert len(alerts) == 1
    assert alerts[0][0] == "admin@example.org"


def test_successful_login_resets_failure_counter(context, email_sender):
    for _ in range(2):
        with pytest.raises(AuthenticationError):
            context.auth_service.login("admin", "bad-password")
    context.auth_service.login("admin", "Admin12345!")
    with pytest.raises(AuthenticationError):
        context.auth_service.login("admin", "bad-password")
    assert not [m for m in email_sender.sent if m[1] == "Подозрительные попытки входа"]


def test_undo_restores_state_through_cache(context, teacher, admin, editable_material):
    service = context.material_service
    service.edit_material(teacher, editable_material.id, title="Новое")
    assert service.list_materials()[0].title == "Новое"
    service.undo_last_edit(teacher, editable_material.id)
    assert service.list_materials()[0].title == "Исходное"
    assert context.event_log_service.list_events(admin)[-1].event_type is (
        EventType.MATERIAL_EDIT_UNDONE
    )


def test_undo_steps_back_one_edit_at_a_time(context, teacher, editable_material):
    service = context.material_service
    service.edit_material(teacher, editable_material.id, title="Первое")
    service.edit_material(teacher, editable_material.id, title="Второе")
    service.undo_last_edit(teacher, editable_material.id)
    assert service.get_material(editable_material.id).title == "Первое"
    service.undo_last_edit(teacher, editable_material.id)
    assert service.get_material(editable_material.id).title == "Исходное"


def test_other_teacher_cannot_undo(context, admin, teacher, editable_material):
    other = _register(context, admin, "teacher2", Role.TEACHER)
    context.material_service.edit_material(teacher, editable_material.id, title="X")
    with pytest.raises(ForeignMaterialAccessError):
        context.material_service.undo_last_edit(other, editable_material.id)


def test_failed_edit_is_not_undoable(context, teacher, editable_material):
    with pytest.raises(DomainError):
        context.material_service.edit_material(teacher, editable_material.id, title="   ")
    assert not context.material_service.can_undo(editable_material.id)
