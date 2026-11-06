"""Юнит-тесты иерархии исключений предметной области."""

from __future__ import annotations

import inspect
import string

import pytest

from src.domain import exceptions
from src.domain.exceptions import (
    AuthenticationError,
    AuthorizationError,
    DomainError,
    EmptyFieldError,
    EntityNotFoundError,
    ValidationError,
)


def _all_error_classes() -> list[type[DomainError]]:
    return [
        cls
        for _name, cls in inspect.getmembers(exceptions, inspect.isclass)
        if issubclass(cls, DomainError) and cls.__module__ == exceptions.__name__
    ]


def _placeholders(message: str) -> list[str]:
    return [field for _, field, _, _ in string.Formatter().parse(message) if field]


@pytest.mark.parametrize("cls", _all_error_classes(), ids=lambda c: c.__name__)
class TestEveryError:
    def test_message_is_formatted_from_details(self, cls):
        details = {name: f"<{name}>" for name in _placeholders(cls.message)}
        error = cls(**details)
        assert str(error) == cls.message.format(**details)
        assert str(error).strip()

    def test_is_domain_error(self, cls):
        assert issubclass(cls, DomainError)

    def test_details_are_kept(self, cls):
        details = {name: "v" for name in _placeholders(cls.message)}
        assert cls(**details).details == details


def test_error_classes_were_discovered():
    assert len(_all_error_classes()) > 30


def test_missing_placeholder_raises_key_error():
    with pytest.raises(KeyError):
        EmptyFieldError()


def test_extra_details_are_ignored_in_message():
    error = AuthenticationError(extra="x")
    assert str(error) == AuthenticationError.message
    assert error.details == {"extra": "x"}


def test_base_error_has_default_message():
    assert str(DomainError()) == DomainError.message


def test_family_relationships():
    assert issubclass(EmptyFieldError, ValidationError)
    assert issubclass(exceptions.MaterialAccessError, AuthorizationError)
    assert issubclass(exceptions.MaterialNotFoundError, EntityNotFoundError)
    assert issubclass(exceptions.NothingToUndoError, EntityNotFoundError)
    assert issubclass(exceptions.InvalidResetTokenError, AuthenticationError)


def test_all_errors_can_be_caught_as_domain_error():
    with pytest.raises(DomainError):
        raise exceptions.FileTooLargeError(max_mb=100)
