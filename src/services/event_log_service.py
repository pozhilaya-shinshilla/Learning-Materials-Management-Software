from __future__ import annotations

from abc import ABC, abstractmethod

from src.domain.enums import EventType, Role
from src.domain.exceptions import EventLogAccessError
from src.domain.models import Event, User
from src.repositories.interfaces import EventRepository


class EventObserver(ABC):
    """Наблюдатель (Observer): получает уведомление о каждом новом событии журнала."""

    @abstractmethod
    def on_event(self, event: Event) -> None:
        """Отреагировать на только что записанное событие."""


class EventLogService:
    """Записывает действия пользователей и показывает журнал администраторам.

    Одновременно служит субъектом паттерна «Наблюдатель»: подписчики узнают о каждом
    событии, а сервисы, которые его создают, ничего о подписчиках не знают.
    """

    def __init__(self, event_repository: EventRepository) -> None:
        """Принять хранилище событий."""
        self._event_repository = event_repository
        self._observers: list[EventObserver] = []

    def subscribe(self, observer: EventObserver) -> None:
        """Подписать наблюдателя на новые события."""
        if observer not in self._observers:
            self._observers.append(observer)

    def unsubscribe(self, observer: EventObserver) -> None:
        """Отписать наблюдателя; отсутствие подписки не считается ошибкой."""
        if observer in self._observers:
            self._observers.remove(observer)

    def record(self, user_id: int | None, event_type: EventType, target: str) -> Event:
        """Добавить запись в журнал, оповестить наблюдателей и вернуть запись.

        `user_id=None` — действие совершил гость (пользователь не опознан).
        """
        event = Event(id=0, user_id=user_id, event_type=event_type, target=target)
        saved = self._event_repository.add(event)
        for observer in list(self._observers):
            observer.on_event(saved)
        return saved

    def list_events(self, requesting_user: User) -> list[Event]:
        """Вернуть весь журнал событий; доступно только администратору."""
        if requesting_user.role is not Role.ADMIN:
            raise EventLogAccessError()
        return self._event_repository.list_all()
