"""Наблюдатель, отзывающий токены после смены пароля."""

from __future__ import annotations

import pytest

from src.domain.enums import EventType
from src.domain.models import Event
from src.services.token_revocation import TokenRevocationObserver


class RecordingTokens:
    def __init__(self) -> None:
        self.revoked_users: list[int] = []

    def delete_by_user(self, user_id: int) -> None:
        self.revoked_users.append(user_id)


def test_password_reset_revokes_tokens_of_that_user():
    tokens = RecordingTokens()
    TokenRevocationObserver(tokens).on_event(Event(1, 7, EventType.PASSWORD_RESET, "alice"))
    assert tokens.revoked_users == [7]


@pytest.mark.parametrize(
    "event_type",
    [t for t in EventType if t is not EventType.PASSWORD_RESET],
)
def test_other_events_do_not_touch_tokens(event_type):
    tokens = RecordingTokens()
    TokenRevocationObserver(tokens).on_event(Event(1, 7, event_type, "x"))
    assert tokens.revoked_users == []


def test_event_without_user_is_ignored():
    tokens = RecordingTokens()
    TokenRevocationObserver(tokens).on_event(Event(1, None, EventType.PASSWORD_RESET, "x"))
    assert tokens.revoked_users == []
