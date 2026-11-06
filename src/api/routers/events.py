"""Журнал событий (только администратор)."""

from __future__ import annotations

from fastapi import APIRouter

from src.api.dependencies import AdminUser, ContextDep
from src.api.errors import ERROR_RESPONSES
from src.dtos.responses import EventResponse

router = APIRouter(
    prefix="/api/events",
    tags=["Журнал событий"],
    responses={401: ERROR_RESPONSES[401], 403: ERROR_RESPONSES[403]},
)


@router.get("", response_model=list[EventResponse], summary="Журнал событий системы")
def list_events(admin: AdminUser, context: ContextDep) -> list[EventResponse]:
    """Вернуть записи журнала событий."""
    return [EventResponse.from_domain(e) for e in context.event_log_service.list_events(admin)]
