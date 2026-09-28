from __future__ import annotations

from src.domain.enums import EventType, Role
from src.domain.exceptions import AuthorizationError
from src.domain.models import Event, User
from src.repositories.interfaces import EventRepository


class EventLogService:
    """Records user actions and exposes the log to administrators."""

    def __init__(self, event_repository: EventRepository) -> None:
        self._event_repository = event_repository

    def record(self, user_id: int, event_type: EventType, target: str) -> Event:
        """Append a new entry to the event log and return it."""
        event = Event(id=0, user_id=user_id, event_type=event_type, target=target)
        return self._event_repository.add(event)

    def list_events(self, requesting_user: User) -> list[Event]:
        """Return the full event log; only administrators may view it."""
        if requesting_user.role is not Role.ADMIN:
            raise AuthorizationError("Only administrators may view the event log.")
        return self._event_repository.list_all()
