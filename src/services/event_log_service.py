from __future__ import annotations

from src.domain.enums import EventType, Role
from src.domain.exceptions import EventLogAccessError
from src.domain.models import Event, User
from src.repositories.interfaces import EventRepository


class EventLogService:
    """Записывает действия пользователей и показывает журнал администраторам."""

    def __init__(self, event_repository: EventRepository) -> None:
        self._event_repository = event_repository

    def record(self, user_id: int, event_type: EventType, target: str) -> Event:
        """Добавить запись в журнал событий и вернуть её."""
        event = Event(id=0, user_id=user_id, event_type=event_type, target=target)
        return self._event_repository.add(event)

    def list_events(self, requesting_user: User) -> list[Event]:
        """Вернуть весь журнал событий; доступно только администратору."""
        if requesting_user.role is not Role.ADMIN:
            raise EventLogAccessError()
        return self._event_repository.list_all()
