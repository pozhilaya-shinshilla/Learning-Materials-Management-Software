"""Юнит-тесты AuthService: вход, блокировка, сеанс, восстановление пароля."""

from __future__ import annotations

import hashlib
from datetime import timedelta

import pytest

from src.domain.enums import AccountStatus, EventType, Role
from src.domain.exceptions import (
    AccountBlockedError,
    AccountDeletedError,
    AuthenticationError,
    InvalidEmailError,
    InvalidLoginError,
    InvalidResetTokenError,
    LoginRequiredError,
    PasswordRequiredError,
    PasswordTooShortError,
    PasswordTooWeakError,
)
from src.domain.models import User
from src.services.auth_service import AuthService


@pytest.fixture
def service(user_repo, reset_token_repo, hasher, event_log, email_sender) -> AuthService:
    return AuthService(user_repo, reset_token_repo, hasher, event_log, email_sender)


@pytest.fixture
def bob(user_repo, hasher) -> User:
    return user_repo.add(User(0, "bob", "bob@example.org", hasher.hash("Password1!"), Role.STUDENT))


def _events(event_log, admin_user):
    return [(e.event_type, e.target) for e in event_log.list_events(admin_user)]


class TestLogin:
    def test_success_returns_user_and_logs(self, service, bob, event_log, admin_user):
        assert service.login("bob", "Password1!") == bob
        assert _events(event_log, admin_user) == [(EventType.USER_LOGGED_IN, "bob")]

    def test_login_is_stripped(self, service, bob):
        assert service.login("  bob  ", "Password1!") == bob

    def test_wrong_password(self, service, bob, event_log, admin_user):
        with pytest.raises(AuthenticationError):
            service.login("bob", "wrong")
        assert _events(event_log, admin_user) == [(EventType.USER_LOGIN_FAILED, "bob")]

    def test_unknown_user_gives_same_error_as_wrong_password(self, service, bob):
        with pytest.raises(AuthenticationError) as unknown:
            service.login("nobody", "Password1!")
        with pytest.raises(AuthenticationError) as wrong:
            service.login("bob", "bad")
        assert str(unknown.value) == str(wrong.value)

    def test_password_is_case_sensitive(self, service, bob):
        with pytest.raises(AuthenticationError):
            service.login("bob", "PASSWORD1")

    def test_login_is_case_sensitive(self, service, bob):
        with pytest.raises(AuthenticationError):
            service.login("BOB", "Password1!")

    @pytest.mark.parametrize("login", ["", "   "])
    def test_blank_login(self, service, login):
        with pytest.raises(LoginRequiredError):
            service.login(login, "Password1!")

    def test_blank_password(self, service, bob):
        with pytest.raises(PasswordRequiredError):
            service.login("bob", "")

    def test_malformed_login_is_rejected_before_lookup(self, service, event_log, admin_user):
        with pytest.raises(InvalidLoginError):
            service.login("bad login!", "x")
        assert _events(event_log, admin_user) == []

    def test_blocked_account_with_correct_password(self, service, bob, user_repo):
        bob.status = AccountStatus.BLOCKED
        user_repo.update(bob)
        user_repo.update(bob)
        with pytest.raises(AccountBlockedError):
            service.login("bob", "Password1!")

    def test_blocked_account_with_wrong_password_hides_status(self, service, bob, user_repo):
        bob.status = AccountStatus.BLOCKED
        user_repo.update(bob)
        with pytest.raises(AuthenticationError):
            service.login("bob", "wrong")

    def test_blocked_login_attempt_is_logged_as_failure(
        self, service, bob, event_log, admin_user, user_repo
    ):
        bob.status = AccountStatus.BLOCKED
        user_repo.update(bob)
        with pytest.raises(AccountBlockedError):
            service.login("bob", "Password1!")
        assert _events(event_log, admin_user) == [(EventType.USER_LOGIN_FAILED, "bob")]

    def test_failed_login_of_unknown_user_is_logged_without_user_id(
        self, service, event_log, admin_user
    ):
        with pytest.raises(AuthenticationError):
            service.login("ghost", "x")
        assert event_log.list_events(admin_user)[0].user_id is None


class TestSession:
    def test_active_user_session_is_valid(self, service, bob):
        assert service.ensure_session_active(bob) == bob

    def test_returns_fresh_record(self, service, bob, user_repo):
        stale = User(bob.id, "bob", "x@x.org", "h", Role.STUDENT)
        assert service.ensure_session_active(stale) == bob

    def test_deleted_user(self, service, bob, user_repo):
        user_repo.delete(bob.id)
        with pytest.raises(AccountDeletedError):
            service.ensure_session_active(bob)

    def test_blocked_during_session(self, service, bob, user_repo):
        bob.status = AccountStatus.BLOCKED
        user_repo.update(bob)
        with pytest.raises(AccountBlockedError):
            service.ensure_session_active(bob)

    def test_logout_is_logged(self, service, bob, event_log, admin_user):
        service.logout(bob)
        assert _events(event_log, admin_user) == [(EventType.USER_LOGGED_OUT, "bob")]


class TestPasswordResetRequest:
    def _code(self, email_sender) -> str:
        return email_sender.sent[-1][2].split("восстановления пароля: ")[1].split()[0]

    def test_sends_email_with_code(self, service, bob, email_sender):
        service.request_password_reset("bob@example.org")
        to, subject, body = email_sender.sent[0]
        assert to == "bob@example.org"
        assert subject == "Восстановление пароля"
        assert len(self._code(email_sender)) == 12
        assert "30 мин" in body

    def test_unknown_email_is_silent(self, service, bob, email_sender):
        service.request_password_reset("nobody@example.org")
        assert email_sender.sent == []

    def test_unknown_and_known_email_are_indistinguishable_to_caller(self, service, bob):
        assert service.request_password_reset("nobody@example.org") is None
        assert service.request_password_reset("bob@example.org") is None

    def test_email_is_stripped_and_case_insensitive(self, service, bob, email_sender):
        service.request_password_reset("  BOB@example.org ")
        assert len(email_sender.sent) == 1

    @pytest.mark.parametrize("email", ["", "bad", "a@b", "a@b.c d"])
    def test_invalid_email_format(self, service, email):
        with pytest.raises(InvalidEmailError):
            service.request_password_reset(email)

    def test_request_is_logged(self, service, bob, event_log, admin_user):
        service.request_password_reset("bob@example.org")
        assert _events(event_log, admin_user) == [(EventType.PASSWORD_RESET_REQUESTED, "bob")]

    def test_new_request_revokes_previous_code(self, service, bob, email_sender):
        service.request_password_reset("bob@example.org")
        first = self._code(email_sender)
        service.request_password_reset("bob@example.org")
        second = self._code(email_sender)
        assert first != second
        with pytest.raises(InvalidResetTokenError):
            service.check_reset_token(first)
        assert service.check_reset_token(second) == bob

    def test_codes_of_other_users_are_not_revoked(
        self, service, bob, user_repo, hasher, email_sender
    ):
        user_repo.add(User(0, "amy", "amy@example.org", hasher.hash("Password1!"), Role.STUDENT))
        service.request_password_reset("bob@example.org")
        bob_code = self._code(email_sender)
        service.request_password_reset("amy@example.org")
        assert service.check_reset_token(bob_code) == bob

    def test_code_is_not_stored_in_plain_text(self, service, bob, email_sender, reset_token_repo):
        service.request_password_reset("bob@example.org")
        code = self._code(email_sender)
        assert reset_token_repo.get_by_hash(code) is None
        assert reset_token_repo.get_by_hash(hashlib.sha256(code.encode()).hexdigest()) is not None


class TestResetTokenValidity:
    def _service(self, user_repo, reset_token_repo, hasher, event_log, email_sender, ttl):
        return AuthService(
            user_repo, reset_token_repo, hasher, event_log, email_sender, reset_token_ttl=ttl
        )

    def _code(self, email_sender):
        return email_sender.sent[-1][2].split("восстановления пароля: ")[1].split()[0]

    def test_garbage_token(self, service, bob):
        with pytest.raises(InvalidResetTokenError):
            service.check_reset_token("garbage")

    def test_empty_token(self, service, bob):
        with pytest.raises(InvalidResetTokenError):
            service.check_reset_token("")

    def test_token_with_spaces_is_accepted(self, service, bob, email_sender):
        service.request_password_reset("bob@example.org")
        assert service.check_reset_token(f"  {self._code(email_sender)}  ") == bob

    def test_expired_token(self, user_repo, reset_token_repo, hasher, event_log, email_sender, bob):
        service = self._service(
            user_repo, reset_token_repo, hasher, event_log, email_sender, timedelta(seconds=-1)
        )
        service.request_password_reset("bob@example.org")
        with pytest.raises(InvalidResetTokenError):
            service.check_reset_token(self._code(email_sender))

    def test_expired_token_is_forgotten(
        self, user_repo, reset_token_repo, hasher, event_log, email_sender, bob
    ):
        service = self._service(
            user_repo, reset_token_repo, hasher, event_log, email_sender, timedelta(seconds=-1)
        )
        service.request_password_reset("bob@example.org")
        code = self._code(email_sender)
        with pytest.raises(InvalidResetTokenError):
            service.check_reset_token(code)
        assert reset_token_repo.get_by_hash(hashlib.sha256(code.encode()).hexdigest()) is None

    def test_token_of_deleted_user(self, service, bob, user_repo, email_sender):
        service.request_password_reset("bob@example.org")
        code = self._code(email_sender)
        user_repo.delete(bob.id)
        with pytest.raises(InvalidResetTokenError):
            service.check_reset_token(code)

    def test_ttl_in_email_uses_minutes(
        self, user_repo, reset_token_repo, hasher, event_log, email_sender, bob
    ):
        service = self._service(
            user_repo, reset_token_repo, hasher, event_log, email_sender, timedelta(minutes=5)
        )
        service.request_password_reset("bob@example.org")
        assert "5 мин" in email_sender.sent[0][2]


class TestResetPassword:
    def _code(self, email_sender):
        return email_sender.sent[-1][2].split("восстановления пароля: ")[1].split()[0]

    def _request(self, service, email_sender):
        service.request_password_reset("bob@example.org")
        return self._code(email_sender)

    def test_new_password_works_and_old_does_not(self, service, bob, email_sender):
        code = self._request(service, email_sender)
        service.reset_password_with_token(code, "NewPassword1!")
        assert service.login("bob", "NewPassword1!").id == bob.id
        with pytest.raises(AuthenticationError):
            service.login("bob", "Password1!")

    def test_token_is_single_use(self, service, bob, email_sender):
        code = self._request(service, email_sender)
        service.reset_password_with_token(code, "NewPassword1!")
        with pytest.raises(InvalidResetTokenError):
            service.reset_password_with_token(code, "Another-Pass1")

    def test_short_password_rejected_and_token_still_valid(self, service, bob, email_sender):
        code = self._request(service, email_sender)
        with pytest.raises(PasswordTooShortError):
            service.reset_password_with_token(code, "short")
        service.reset_password_with_token(code, "LongEnough1!")

    def test_password_of_exactly_minimum_length(self, service, bob, email_sender):
        code = self._request(service, email_sender)
        service.reset_password_with_token(code, "Abcdef1!")
        assert service.login("bob", "Abcdef1!").id == bob.id

    @pytest.mark.parametrize("weak", ["alllowercase1!", "NoDigits!!!", "NoSymbol123"])
    def test_weak_password_rejected_and_token_still_valid(self, service, bob, email_sender, weak):
        code = self._request(service, email_sender)
        with pytest.raises(PasswordTooWeakError):
            service.reset_password_with_token(code, weak)
        service.reset_password_with_token(code, "LongEnough1!")

    def test_invalid_token(self, service, bob):
        with pytest.raises(InvalidResetTokenError):
            service.reset_password_with_token("nope", "NewPassword1!")

    def test_reset_is_logged(self, service, bob, email_sender, event_log, admin_user):
        code = self._request(service, email_sender)
        service.reset_password_with_token(code, "NewPassword1!")
        assert (EventType.PASSWORD_RESET, "bob") in _events(event_log, admin_user)

    def test_blocked_user_can_reset_but_not_login(self, service, bob, email_sender, user_repo):
        bob.status = AccountStatus.BLOCKED
        user_repo.update(bob)
        code = self._request(service, email_sender)
        service.reset_password_with_token(code, "NewPassword1!")
        with pytest.raises(AccountBlockedError):
            service.login("bob", "NewPassword1!")
