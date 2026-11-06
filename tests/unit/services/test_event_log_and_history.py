"""Юнит-тесты журнала событий, наблюдателей, истории правок и оповещения о входах."""

from __future__ import annotations

import pytest

from src.domain.enums import EventType
from src.domain.exceptions import EventLogAccessError
from src.domain.models import Event
from src.notifications.login_alerts import FailedLoginAlertObserver
from src.services.event_log_service import EventObserver
from tests.fakes import RecordingEmailSender, make_event, make_user

pytestmark = pytest.mark.usefixtures("reference_data")


class Collector(EventObserver):
    def __init__(self) -> None:
        self.events: list[Event] = []

    def on_event(self, event: Event) -> None:
        self.events.append(event)


class TestEventLogService:
    def test_record_returns_saved_event_with_id(self, event_log, student_user):
        event = event_log.record(student_user.id, EventType.USER_LOGGED_IN, "bob")
        assert (event.id, event.user_id, event.target) == (1, student_user.id, "bob")
        assert event.event_type is EventType.USER_LOGGED_IN

    def test_admin_sees_all_events_in_order(self, event_log, admin_user):
        event_log.record(1, EventType.USER_LOGGED_IN, "a")
        event_log.record(1, EventType.USER_LOGGED_OUT, "b")
        assert [e.target for e in event_log.list_events(admin_user)] == ["a", "b"]

    def test_empty_log(self, event_log, admin_user):
        assert event_log.list_events(admin_user) == []

    @pytest.mark.parametrize("fixture", ["teacher_user", "student_user"])
    def test_non_admin_cannot_read(self, event_log, request, fixture):
        with pytest.raises(EventLogAccessError):
            event_log.list_events(request.getfixturevalue(fixture))

    def test_guest_event_has_no_user_id(self, event_log):
        assert event_log.record(None, EventType.USER_LOGIN_FAILED, "ghost").user_id is None

    def test_empty_target_is_allowed(self, event_log):
        assert event_log.record(1, EventType.USER_LOGGED_IN, "").target == ""


class TestObservers:
    def test_observer_receives_saved_event(self, event_log):
        collector = Collector()
        event_log.subscribe(collector)
        saved = event_log.record(1, EventType.USER_LOGGED_IN, "a")
        assert collector.events == [saved]
        assert saved.id == 1

    def test_no_observers_is_fine(self, event_log):
        event_log.record(1, EventType.USER_LOGGED_IN, "a")

    def test_double_subscription_notifies_once(self, event_log):
        collector = Collector()
        event_log.subscribe(collector)
        event_log.subscribe(collector)
        event_log.record(1, EventType.USER_LOGGED_IN, "a")
        assert len(collector.events) == 1

    def test_unsubscribe_stops_notifications(self, event_log):
        collector = Collector()
        event_log.subscribe(collector)
        event_log.unsubscribe(collector)
        event_log.record(1, EventType.USER_LOGGED_IN, "a")
        assert collector.events == []

    def test_unsubscribe_unknown_observer_is_silent(self, event_log):
        event_log.unsubscribe(Collector())

    def test_all_observers_are_notified(self, event_log):
        first, second = Collector(), Collector()
        event_log.subscribe(first)
        event_log.subscribe(second)
        event_log.record(1, EventType.USER_LOGGED_IN, "a")
        assert len(first.events) == len(second.events) == 1

    def test_observer_may_unsubscribe_itself_while_notified(self, event_log):
        class OneShot(EventObserver):
            def __init__(self, log):
                self.log, self.calls = log, 0

            def on_event(self, event):
                self.calls += 1
                self.log.unsubscribe(self)

        one_shot = OneShot(event_log)
        other = Collector()
        event_log.subscribe(one_shot)
        event_log.subscribe(other)
        event_log.record(1, EventType.USER_LOGGED_IN, "a")
        event_log.record(1, EventType.USER_LOGGED_IN, "b")
        assert one_shot.calls == 1
        assert len(other.events) == 2

    def test_event_is_stored_before_observers_run(self, event_log, event_repo):
        seen = []

        class Peek(EventObserver):
            def on_event(self, event):
                seen.append(len(event_repo.list_all()))

        event_log.subscribe(Peek())
        event_log.record(1, EventType.USER_LOGGED_IN, "a")
        assert seen == [1]


class TestFailedLoginAlertObserver:
    @pytest.fixture
    def users(self, user_repo):
        user_repo.add(make_user(0, "bob", email="bob@example.org"))
        return user_repo

    @pytest.fixture
    def mail(self):
        return RecordingEmailSender()

    def _fail(self, observer, login="bob"):
        observer.on_event(make_event(EventType.USER_LOGIN_FAILED, login, None))

    def test_no_alert_below_threshold(self, users, failed_login_repo, mail):
        observer = FailedLoginAlertObserver(users, failed_login_repo, mail, threshold=3)
        for _ in range(2):
            self._fail(observer)
        assert mail.sent == []

    def test_alert_exactly_at_threshold(self, users, failed_login_repo, mail):
        observer = FailedLoginAlertObserver(users, failed_login_repo, mail, threshold=3)
        for _ in range(3):
            self._fail(observer)
        assert len(mail.sent) == 1
        assert mail.sent[0][0] == "bob@example.org"

    def test_counter_resets_after_alert(self, users, failed_login_repo, mail):
        observer = FailedLoginAlertObserver(users, failed_login_repo, mail, threshold=2)
        for _ in range(3):
            self._fail(observer)
        assert len(mail.sent) == 1
        self._fail(observer)
        assert len(mail.sent) == 2

    def test_successful_login_resets_counter(self, users, failed_login_repo, mail):
        observer = FailedLoginAlertObserver(users, failed_login_repo, mail, threshold=3)
        self._fail(observer)
        self._fail(observer)
        observer.on_event(make_event(EventType.USER_LOGGED_IN, "bob"))
        self._fail(observer)
        assert mail.sent == []

    def test_threshold_one_alerts_immediately(self, users, failed_login_repo, mail):
        self._fail(FailedLoginAlertObserver(users, failed_login_repo, mail, threshold=1))
        assert len(mail.sent) == 1

    def test_unknown_login_sends_nothing(self, users, failed_login_repo, mail):
        observer = FailedLoginAlertObserver(users, failed_login_repo, mail, threshold=1)
        self._fail(observer, "ghost")
        assert mail.sent == []

    def test_logins_are_case_sensitive_like_authentication(self, users, failed_login_repo, mail):
        observer = FailedLoginAlertObserver(users, failed_login_repo, mail, threshold=2)
        self._fail(observer, "bob")
        self._fail(observer, "BOB")
        assert mail.sent == []
        self._fail(observer, "bob")
        assert len(mail.sent) == 1

    def test_other_events_are_ignored(self, users, failed_login_repo, mail):
        observer = FailedLoginAlertObserver(users, failed_login_repo, mail, threshold=1)
        observer.on_event(make_event(EventType.MATERIAL_CREATED, "bob"))
        assert mail.sent == []

    def test_counters_are_independent_per_login(self, users, failed_login_repo, mail):
        users.add(make_user(0, "alice", email="alice@example.org"))
        observer = FailedLoginAlertObserver(users, failed_login_repo, mail, threshold=2)
        self._fail(observer, "bob")
        self._fail(observer, "alice")
        assert mail.sent == []
        self._fail(observer, "bob")
        assert [m[0] for m in mail.sent] == ["bob@example.org"]
