"""Юнит-тесты UserManagementService."""

from __future__ import annotations

import pytest

from src.domain.enums import AccountStatus, EventType, Role
from src.domain.exceptions import (
    DuplicateEmailError,
    DuplicateLoginError,
    InvalidEmailError,
    InvalidLoginError,
    PasswordTooShortError,
    PasswordTooWeakError,
    SameRoleError,
    SelfBlockError,
    SelfDeleteError,
    SelfRoleChangeError,
    UserAlreadyBlockedError,
    UserManagementAccessError,
    UserNotBlockedError,
    UserNotFoundError,
)
from src.services.user_management_service import UserManagementService
from tests.fakes import make_user


@pytest.fixture
def service(user_repo, hasher, event_log) -> UserManagementService:
    return UserManagementService(user_repo, hasher, event_log)


@pytest.fixture
def admin(service, user_repo):
    return user_repo.add(make_user(0, "boss", Role.ADMIN))


def _last_event(event_log, admin):
    event = event_log.list_events(admin)[-1]
    return event.event_type, event.target


class TestCreateUser:
    def test_creates_hashed_user_with_role(self, service, admin, hasher):
        user = service.create_user(admin, "newbie", "n@example.org", "Password1!", Role.TEACHER)
        assert user.id > 0
        assert user.role is Role.TEACHER
        assert user.password_hash == hasher.hash("Password1!")
        assert user.status is AccountStatus.ACTIVE

    def test_logged_as_account_change(self, service, admin, event_log):
        service.create_user(admin, "newbie", "n@example.org", "Password1!", Role.STUDENT)
        assert _last_event(event_log, admin) == (EventType.USER_ACCOUNT_CHANGED, "created:newbie")

    @pytest.mark.parametrize("fixture", ["teacher_user", "student_user"])
    def test_only_admin_can_create(self, service, request, fixture):
        with pytest.raises(UserManagementAccessError):
            service.create_user(
                request.getfixturevalue(fixture), "x1x", "x@example.org", "Password1!", Role.STUDENT
            )

    def test_duplicate_login(self, service, admin):
        with pytest.raises(DuplicateLoginError):
            service.create_user(admin, "boss", "other@example.org", "Password1!", Role.STUDENT)

    def test_duplicate_email_ignoring_case(self, service, admin):
        service.create_user(admin, "first", "Same@Example.org", "Password1!", Role.STUDENT)
        with pytest.raises(DuplicateEmailError):
            service.create_user(admin, "second", "same@example.org", "Password1!", Role.STUDENT)

    def test_logins_differing_in_case_are_distinct(self, service, admin):
        service.create_user(admin, "Alice", "a1@example.org", "Password1!", Role.STUDENT)
        service.create_user(admin, "alice", "a2@example.org", "Password1!", Role.STUDENT)

    @pytest.mark.parametrize("login", ["ab", "a" * 33, "bad login", ""])
    def test_invalid_login(self, service, admin, login):
        with pytest.raises(InvalidLoginError):
            service.create_user(admin, login, "x@example.org", "Password1!", Role.STUDENT)

    def test_invalid_email(self, service, admin):
        with pytest.raises(InvalidEmailError):
            service.create_user(admin, "abc", "nope", "Password1!", Role.STUDENT)

    def test_password_boundary(self, service, admin):
        service.create_user(admin, "abc", "a@example.org", "Abcdef1!", Role.STUDENT)
        with pytest.raises(PasswordTooShortError):
            service.create_user(admin, "abd", "b@example.org", "Abcde1!", Role.STUDENT)

    @pytest.mark.parametrize("weak", ["password1!", "PASSWORD!!", "Password12", "12345678"])
    def test_weak_password_is_rejected_and_nothing_saved(self, service, admin, user_repo, weak):
        with pytest.raises(PasswordTooWeakError):
            service.create_user(admin, "abc", "a@example.org", weak, Role.STUDENT)
        assert user_repo.get_by_login("abc") is None

    def test_failed_creation_is_not_logged_or_saved(self, service, admin, event_log, user_repo):
        with pytest.raises(PasswordTooShortError):
            service.create_user(admin, "abc", "a@example.org", "short", Role.STUDENT)
        assert event_log.list_events(admin) == []
        assert user_repo.get_by_login("abc") is None


class TestEnsureAvailable:
    def test_free_login_and_email(self, service, admin):
        service.ensure_login_available("free")
        service.ensure_email_available("free@example.org")

    def test_taken_login_and_email(self, service, admin):
        with pytest.raises(DuplicateLoginError):
            service.ensure_login_available("boss")
        with pytest.raises(DuplicateEmailError):
            service.ensure_email_available("BOSS@example.org")


class TestListUsers:
    def test_admin_lists_all(self, service, admin):
        assert service.list_users(admin) == [admin]

    @pytest.mark.parametrize("fixture", ["teacher_user", "student_user"])
    def test_non_admin_forbidden(self, service, request, fixture):
        with pytest.raises(UserManagementAccessError):
            service.list_users(request.getfixturevalue(fixture))


class TestGetAuthorLogin:
    def test_existing(self, service, admin):
        assert service.get_author_login(admin.id) == "boss"

    @pytest.mark.parametrize("user_id", [0, -1, 9999])
    def test_missing_user_is_marked_deleted(self, service, user_id):
        assert service.get_author_login(user_id) == "удалённый пользователь"

    def test_author_login_of_material_without_author(self, service):
        assert service.get_author_login(None) == "автор удалён"


class TestChangeRole:
    @pytest.fixture
    def target(self, user_repo):
        return user_repo.add(make_user(0, "target", Role.STUDENT))

    def test_changes_and_logs(self, service, admin, target, event_log, user_repo):
        service.change_role(admin, target.id, Role.TEACHER)
        assert user_repo.get_by_id(target.id).role is Role.TEACHER
        assert _last_event(event_log, admin) == (EventType.USER_ROLE_CHANGED, "target")

    def test_same_role_rejected(self, service, admin, target):
        with pytest.raises(SameRoleError):
            service.change_role(admin, target.id, Role.STUDENT)

    def test_cannot_change_own_role(self, service, admin):
        with pytest.raises(SelfRoleChangeError):
            service.change_role(admin, admin.id, Role.STUDENT)

    def test_unknown_user(self, service, admin):
        with pytest.raises(UserNotFoundError):
            service.change_role(admin, 9999, Role.TEACHER)

    def test_only_admin(self, service, teacher_user, target):
        with pytest.raises(UserManagementAccessError):
            service.change_role(teacher_user, target.id, Role.ADMIN)

    def test_failed_change_keeps_role_and_log_empty(self, service, admin, target, event_log):
        with pytest.raises(SameRoleError):
            service.change_role(admin, target.id, Role.STUDENT)
        assert event_log.list_events(admin) == []


class TestSetBlocked:
    @pytest.fixture
    def target(self, user_repo):
        return user_repo.add(make_user(0, "target", Role.STUDENT))

    def test_block_then_unblock(self, service, admin, target, event_log, user_repo):
        service.set_blocked(admin, target.id, True)
        assert user_repo.get_by_id(target.id).status is AccountStatus.BLOCKED
        assert _last_event(event_log, admin) == (EventType.USER_BLOCKED, "target")
        service.set_blocked(admin, target.id, False)
        assert user_repo.get_by_id(target.id).status is AccountStatus.ACTIVE
        assert _last_event(event_log, admin) == (EventType.USER_UNBLOCKED, "target")

    def test_double_block(self, service, admin, target):
        service.set_blocked(admin, target.id, True)
        with pytest.raises(UserAlreadyBlockedError):
            service.set_blocked(admin, target.id, True)

    def test_unblock_active(self, service, admin, target):
        with pytest.raises(UserNotBlockedError):
            service.set_blocked(admin, target.id, False)

    def test_cannot_block_self(self, service, admin):
        with pytest.raises(SelfBlockError):
            service.set_blocked(admin, admin.id, True)

    def test_unknown_user(self, service, admin):
        with pytest.raises(UserNotFoundError):
            service.set_blocked(admin, 0, True)

    def test_only_admin(self, service, student_user, target):
        with pytest.raises(UserManagementAccessError):
            service.set_blocked(student_user, target.id, True)


class TestDeleteUser:
    def test_deletes_and_logs(self, service, admin, user_repo, event_log):
        target = user_repo.add(make_user(0, "target"))
        service.delete_user(admin, target.id)
        assert user_repo.get_by_id(target.id) is None
        assert _last_event(event_log, admin) == (EventType.USER_ACCOUNT_CHANGED, "deleted:target")

    def test_cannot_delete_self(self, service, admin, user_repo):
        with pytest.raises(SelfDeleteError):
            service.delete_user(admin, admin.id)
        assert user_repo.get_by_id(admin.id) is not None

    def test_unknown_user(self, service, admin):
        with pytest.raises(UserNotFoundError):
            service.delete_user(admin, 9999)

    def test_only_admin(self, service, teacher_user, user_repo):
        target = user_repo.add(make_user(0, "target"))
        with pytest.raises(UserManagementAccessError):
            service.delete_user(teacher_user, target.id)
        assert user_repo.get_by_id(target.id) is not None

    def test_deleting_twice(self, service, admin, user_repo):
        target = user_repo.add(make_user(0, "target"))
        service.delete_user(admin, target.id)
        with pytest.raises(UserNotFoundError):
            service.delete_user(admin, target.id)
