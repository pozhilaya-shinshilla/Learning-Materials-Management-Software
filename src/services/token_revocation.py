"""Наблюдатель (Observer): после смены пароля по коду отзывает токены доступа к API.

Если пароль меняют потому, что его узнал посторонний, выданные до этого токены не должны
продолжать работать: иначе злоумышленник остался бы в системе, а смена пароля ничего не дала.
Наблюдатель подписан на журнал событий, поэтому `AuthService` о токенах ничего не знает, а
отзыв выполняется в той же транзакции, что и смена пароля: либо оба действия, либо ни одно.
"""

from __future__ import annotations

from src.domain.enums import EventType
from src.domain.models import Event
from src.repositories.interfaces import AuthTokenRepository
from src.services.event_log_service import EventObserver


class TokenRevocationObserver(EventObserver):
    """Удаляет все токены пользователя, когда он сменил пароль по коду восстановления."""

    def __init__(self, token_repository: AuthTokenRepository) -> None:
        """Принять хранилище токенов."""
        self._token_repository = token_repository

    def on_event(self, event: Event) -> None:
        """Отозвать токены при событии «пароль изменён»; остальные события не интересны."""
        if event.event_type is EventType.PASSWORD_RESET and event.user_id is not None:
            self._token_repository.delete_by_user(event.user_id)
