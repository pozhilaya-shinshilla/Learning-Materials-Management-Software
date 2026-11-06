"""Одновременная работа нескольких пользователей над одной БД.

Каждый `build_app()` — отдельный «процесс»: свой менеджер транзакций и свои соединения. Потоки
здесь нужны не ради нагрузки, а чтобы гарантированно получить неудобное чередование операций
(`helpers.py`): в нужное место операции вставляется пауза или барьер: «обе транзакции уже всё
проверили, но ещё ничего не записали». Без блокировок и атомарных операторов эти тесты
падают: гонку воспроизводит сам тест, а не удача.

Правила, которые проверяются:
- одноразовый код восстановления нельзя использовать дважды, и действует только последний;
- проигравший гонку за уникальное значение получает обычную доменную ошибку;
- правки одного материала выполняются по очереди, снимки для отмены не повторяются;
- понижение роли вступает в силу сразу, а не после выхода из системы;
- два параллельных неудачных входа дают одно письмо, а не два;
- удаление пользователя и операции с его материалом не блокируют друг друга намертво.
"""

from __future__ import annotations

import threading

import pytest
from sqlalchemy import func, select

from src.database.models import PasswordResetTokenEntity
from src.domain.enums import Role
from src.domain.exceptions import (
    AccountDeletedError,
    AuthenticationError,
    DuplicateDisciplineError,
    DuplicateEmailError,
    DuplicateFavoriteError,
    DuplicateLoginError,
    DuplicateTopicError,
    InvalidResetTokenError,
    MaterialNotFoundError,
    RoleChangedError,
    UserNotFoundError,
    ValidationError,
)
from src.domain.models import Favorite
from tests.fakes import make_user
from tests.integration.db.conftest import make_material
from tests.integration.db.helpers import (
    Gate,
    Worker,
    after,
    barrier_after,
    real,
    run_in_order_of_blocking,
)


def _code(app) -> str:
    return app.mail.sent[-1][2].split("восстановления пароля: ")[1].split()[0]


def _token_count(session_factory) -> int:
    with session_factory() as session:
        return session.scalar(select(func.count()).select_from(PasswordResetTokenEntity))


class TestResetCode:
    def test_same_code_cannot_be_used_twice_in_parallel(self, apps, bob):
        first, second = apps
        first.context.auth_service.request_password_reset("bob@example.org")
        code = _code(first)
        barrier = threading.Barrier(2)
        for app in apps:  # оба уже убедились, что код действует, и только потом меняют пароль
            barrier_after(real(app.context.auth_service), "check_reset_token", barrier)

        one = Worker(
            lambda: first.context.auth_service.reset_password_with_token(code, "First123!")
        )
        two = Worker(
            lambda: second.context.auth_service.reset_password_with_token(code, "Second123!")
        )
        one.start(), two.start()
        one.wait(), two.wait()

        errors = [w.error for w in (one, two)]
        assert sum(e is None for e in errors) == 1, errors
        assert sum(isinstance(e, InvalidResetTokenError) for e in errors) == 1, errors
        winner_password = "First123!" if one.error is None else "Second123!"
        assert first.context.auth_service.login("bob", winner_password).login == "bob"

    def test_parallel_requests_leave_exactly_one_valid_code(self, apps, bob, session_factory):
        first, second = apps
        gate = Gate()  # первая транзакция держит блокировку строки пользователя до фиксации
        after(real(first.context.auth_service)._event_log_service, "record", gate.hold)

        one = Worker(lambda: first.context.auth_service.request_password_reset("bob@example.org"))
        two = Worker(lambda: second.context.auth_service.request_password_reset("bob@example.org"))
        run_in_order_of_blocking(one, gate, two)

        assert one.error is None and two.error is None
        assert _token_count(session_factory) == 1
        old_code, new_code = _code(first), _code(second)
        with pytest.raises(InvalidResetTokenError):
            first.context.auth_service.check_reset_token(old_code)
        assert first.context.auth_service.check_reset_token(new_code).login == "bob"

    def test_weak_new_password_does_not_burn_the_code(self, apps, bob):
        first, _ = apps
        first.context.auth_service.request_password_reset("bob@example.org")
        code = _code(first)
        with pytest.raises(ValidationError):
            first.context.auth_service.reset_password_with_token(code, "short")
        first.context.auth_service.reset_password_with_token(code, "Strong123!")
        assert first.context.auth_service.login("bob", "Strong123!").login == "bob"


class TestLosingARaceIsADomainError:
    """Оба процесса проверили «свободно» и пишут одновременно: проигравший видит обычную ошибку."""

    def _race(self, apps, gated_service, gated_method, first_action, second_action):
        first, second = apps
        barrier = threading.Barrier(2)
        for app in apps:
            barrier_after(real(getattr(app.context, gated_service)), gated_method, barrier)
        one = Worker(lambda: first_action(first))
        two = Worker(lambda: second_action(second))
        one.start(), two.start()
        one.wait(), two.wait()
        return [one.error, two.error]

    @staticmethod
    def _outcome(errors, expected):
        assert sum(e is None for e in errors) == 1, errors
        assert sum(type(e) is expected for e in errors) == 1, errors

    def test_same_login(self, apps):
        def create(email):
            return lambda app: app.context.user_management_service.create_user(
                app.admin, "newbie", email, "Password123!", Role.STUDENT
            )

        errors = self._race(
            apps, "user_management_service", "ensure_email_available",
            create("one@example.org"), create("two@example.org"),
        )  # fmt: skip
        self._outcome(errors, DuplicateLoginError)
        users = apps[0].context.user_management_service.list_users(apps[0].admin)
        assert [u.login for u in users].count("newbie") == 1

    def test_same_email(self, apps):
        def create(login):
            return lambda app: app.context.user_management_service.create_user(
                app.admin, login, "same@example.org", "Password123!", Role.STUDENT
            )

        errors = self._race(
            apps, "user_management_service", "ensure_email_available",
            create("first"), create("second"),
        )  # fmt: skip
        self._outcome(errors, DuplicateEmailError)

    def test_same_discipline(self, apps):
        def create(app):
            return app.context.catalog_service.create_discipline(app.admin, "Математика")

        errors = self._race(apps, "catalog_service", "ensure_discipline_name_free", create, create)
        self._outcome(errors, DuplicateDisciplineError)

    def test_same_topic(self, apps):
        first, _ = apps
        discipline = first.context.catalog_service.create_discipline(first.admin, "Математика")

        def create(app):
            return app.context.catalog_service.create_topic(app.admin, "Алгебра", discipline.id)

        errors = self._race(apps, "catalog_service", "ensure_topic_name_free", create, create)
        self._outcome(errors, DuplicateTopicError)

    def test_same_favorite(self, apps, tmp_path):
        first, _ = apps
        material = make_material(first, tmp_path, "Лекция")
        barrier = threading.Barrier(2)
        for app in apps:
            repository = real(app.context.favorite_service)._favorite_repository
            barrier_after(repository, "exists", barrier)

        def add(app):
            return lambda: app.context.favorite_service.add_favorite(app.admin, material.id)

        one, two = Worker(add(apps[0])), Worker(add(apps[1]))
        one.start(), two.start()
        one.wait(), two.wait()
        self._outcome([one.error, two.error], DuplicateFavoriteError)

    def test_favorite_of_material_deleted_meanwhile(self, repos, db_session):
        user = repos.users.add(make_user(0, "reader"))
        with pytest.raises(MaterialNotFoundError):
            repos.favorites.add(Favorite(user.id, 999))

    def test_session_stays_usable_after_a_conflict(self, repos):
        repos.users.add(make_user(0, "twin", email="a@example.org"))
        with pytest.raises(DuplicateLoginError):
            repos.users.add(make_user(0, "twin", email="b@example.org"))
        # Неудачная вставка откатила только свой SAVEPOINT: транзакция работает дальше.
        assert [u.login for u in repos.users.list_all()] == ["twin"]


def _title(app, material) -> str:
    return app.context.material_service.get_material(material.id).title


class TestMaterialEditsAreSerialised:
    def _edit(self, app, material, title):
        return lambda: app.context.material_service.edit_material(
            app.admin, material.id, title=title
        )

    def _undo(self, app, material):
        return lambda: app.context.material_service.undo_last_edit(app.admin, material.id)

    def test_second_edit_waits_and_snapshots_follow_the_real_history(self, apps, material):
        first, second = apps
        gate = Gate()
        after(real(first.context.material_service)._event_log_service, "record", gate.hold)

        one = Worker(self._edit(first, material, "B"))
        two = Worker(self._edit(second, material, "C"))
        run_in_order_of_blocking(one, gate, two)

        assert one.error is None and two.error is None
        assert _title(first, material) == "C"
        # Снимки лежат в настоящем порядке: A -> B -> C. Без блокировки оба правщика
        # прочитали бы «A», и вторая отмена вернула бы не «B», а «A».
        first.context.material_service.undo_last_edit(first.admin, material.id)
        assert _title(first, material) == "B"
        first.context.material_service.undo_last_edit(first.admin, material.id)
        assert _title(first, material) == "A"

    def test_parallel_undo_steps_back_twice(self, apps, material):
        first, second = apps
        service = first.context.material_service
        service.edit_material(first.admin, material.id, title="B")
        service.edit_material(first.admin, material.id, title="C")
        gate = Gate()
        after(real(first.context.material_service)._event_log_service, "record", gate.hold)

        one = Worker(self._undo(first, material))
        two = Worker(self._undo(second, material))
        run_in_order_of_blocking(one, gate, two)

        assert one.error is None and two.error is None
        assert _title(first, material) == "A"  # каждый достал свой снимок, а не один и тот же
        assert not first.context.material_service.can_undo(material.id)

    def test_edit_of_material_deleted_in_parallel_is_an_error_not_a_silent_success(
        self, apps, material
    ):
        first, second = apps
        gate = Gate()
        after(real(first.context.material_service)._event_log_service, "record", gate.hold)

        deleter = Worker(
            lambda: first.context.material_service.delete_material(first.admin, material.id)
        )
        editor = Worker(self._edit(second, material, "Поздно"))
        run_in_order_of_blocking(deleter, gate, editor)

        assert deleter.error is None
        assert isinstance(editor.error, MaterialNotFoundError), editor.error


class TestRoleChangeEndsTheSession:
    def test_demoted_teacher_is_signed_out_at_next_step(self, apps):
        first, second = apps
        service = first.context.user_management_service
        teacher = service.create_user(
            first.admin, "teacher1", "t@example.org", "Password123!", Role.TEACHER
        )
        session_user = second.context.auth_service.login("teacher1", "Password123!")
        assert second.context.auth_service.ensure_session_active(session_user).role is Role.TEACHER

        service.change_role(first.admin, teacher.id, Role.STUDENT)

        with pytest.raises(RoleChangedError):
            second.context.auth_service.ensure_session_active(session_user)

    def test_promotion_also_requires_a_new_login(self, apps, bob):
        first, second = apps
        session_user = second.context.auth_service.login("bob", "Password123!")
        first.context.user_management_service.change_role(first.admin, bob.id, Role.TEACHER)
        with pytest.raises(RoleChangedError):
            second.context.auth_service.ensure_session_active(session_user)
        assert second.context.auth_service.login("bob", "Password123!").role is Role.TEACHER


class TestRowLocks:
    def test_lock_reports_whether_the_user_exists(self, repos):
        user = repos.users.add(make_user(0, "locked"))
        assert repos.users.lock(user.id) is True
        assert repos.users.lock(user.id + 1000) is False

    def test_missing_material_cannot_be_locked_for_update(self, repos):
        assert repos.materials.get_by_id_for_update(999) is None
        assert repos.materials.get_by_id_for_update(999, acting_user_id=5) is None

    @pytest.mark.parametrize("exclusive", [False, True])
    def test_lock_many_returns_only_existing_users(self, repos, exclusive):
        one = repos.users.add(make_user(0, "one"))
        two = repos.users.add(make_user(0, "two"))
        found = repos.users.lock_many([two.id, one.id, 9999, one.id], exclusive=exclusive)
        assert found == {one.id, two.id}
        assert repos.users.lock_many([]) == set()


class TestUserDeletedMidOperation:
    def test_event_of_deleted_user_aborts_the_whole_operation(self, apps, tmp_path):
        first, second = apps
        service = first.context.user_management_service
        author = service.create_user(
            first.admin, "teacher1", "t@example.org", "Password123!", Role.TEACHER
        )
        stale_author = second.context.auth_service.login("teacher1", "Password123!")
        service.delete_user(first.admin, author.id)

        with pytest.raises(AccountDeletedError):
            second.context.catalog_service.create_discipline(stale_author, "Физика")
        assert first.context.catalog_service.list_disciplines() == []


class TestFailedLoginCounter:
    def test_parallel_failures_reaching_the_threshold_send_one_alert(self, apps, bob):
        first, second = apps
        for _ in range(2):  # две попытки уже были: следующая достигает порога (3)
            with pytest.raises(AuthenticationError):
                first.context.auth_service.login("bob", "wrong")
        gate = Gate()
        after(real(first.context.auth_service)._event_log_service, "record", gate.hold)

        one = Worker(lambda: first.context.auth_service.login("bob", "wrong"))
        two = Worker(lambda: second.context.auth_service.login("bob", "wrong"))
        run_in_order_of_blocking(one, gate, two)

        assert isinstance(one.error, AuthenticationError) and isinstance(
            two.error, AuthenticationError
        )
        # Без блокировки оба считали бы по три попытки и оба написали бы владельцу.
        assert len(first.mail.sent) + len(second.mail.sent) == 1

    def test_attempt_after_the_alert_starts_a_new_series(self, apps, bob):
        first, second = apps
        for app in (first, second, first):
            with pytest.raises(AuthenticationError):
                app.context.auth_service.login("bob", "wrong")
        assert len(first.mail.sent) == 1
        with pytest.raises(AuthenticationError):
            second.context.auth_service.login("bob", "wrong")
        assert len(first.mail.sent) + len(second.mail.sent) == 1  # серия началась заново


class TestDeletingAnAuthorWhileTheirMaterialIsChanged:
    """Удаление пользователя и операции с его материалом не ждут друг друга по кругу.

    Удаление пользователя блокирует его строку, а затем обнуляет `author_id` у его материалов.
    Правка материала блокирует материал, а затем пишет событие со ссылкой на пользователя.
    Если порядки противоположны, каждая транзакция ждёт строку, занятую другой, и PostgreSQL
    отменяет одну из них как взаимную блокировку. Теперь обе идут в порядке «пользователь,
    затем материал».
    """

    OPERATIONS = ("edit", "undo", "delete")

    @pytest.fixture
    def teacher(self, apps):
        first, _ = apps
        return first.context.user_management_service.create_user(
            first.admin, "teacher1", "t@example.org", "Password123!", Role.TEACHER
        )

    @staticmethod
    def _operation(app, editor, material, name):
        service = app.context.material_service
        return {
            "edit": lambda: service.edit_material(editor, material.id, title="B"),
            "undo": lambda: service.undo_last_edit(editor, material.id),
            "delete": lambda: service.delete_material(editor, material.id),
        }[name]

    @staticmethod
    def _prepare(app, editor, material, name):
        if name == "undo":  # отменять нечего, пока не было правки
            app.context.material_service.edit_material(editor, material.id, title="B")

    @pytest.mark.parametrize("operation", OPERATIONS)
    @pytest.mark.parametrize("editor_is_author", [True, False])
    def test_author_deleted_while_material_is_locked(
        self, apps, teacher, tmp_path, operation, editor_is_author
    ):
        first, second = apps
        material = make_material(first, tmp_path, "A", author=teacher)
        editor = teacher if editor_is_author else first.admin
        self._prepare(first, editor, material, operation)
        gate = Gate()
        after(
            real(first.context.material_service)._material_repository,
            "get_by_id_for_update",
            gate.hold,
        )

        changer = Worker(self._operation(first, editor, material, operation))
        deleter = Worker(
            lambda: second.context.user_management_service.delete_user(second.admin, teacher.id)
        )
        run_in_order_of_blocking(changer, gate, deleter)

        assert changer.error is None and deleter.error is None, (changer.error, deleter.error)
        logins = [u.login for u in first.context.user_management_service.list_users(first.admin)]
        assert "teacher1" not in logins
        service = first.context.material_service
        if operation == "delete":
            with pytest.raises(MaterialNotFoundError):
                service.get_material(material.id)
        else:
            kept = service.get_material(material.id)
            assert kept.author_id is None  # материал остался, автор обнулён базой
            assert kept.title == ("B" if operation == "edit" else "A")

    @pytest.mark.parametrize("operation", OPERATIONS)
    def test_stale_session_of_a_deleted_author_ends_with_a_domain_error(
        self, apps, teacher, tmp_path, operation
    ):
        first, second = apps
        material = make_material(first, tmp_path, "A", author=teacher)
        self._prepare(first, teacher, material, operation)
        gate = Gate()
        after(real(second.context.user_management_service)._user_repository, "delete", gate.hold)

        deleter = Worker(
            lambda: second.context.user_management_service.delete_user(second.admin, teacher.id)
        )
        changer = Worker(self._operation(first, teacher, material, operation))
        run_in_order_of_blocking(deleter, gate, changer)

        assert deleter.error is None
        assert isinstance(changer.error, AccountDeletedError), changer.error
        kept = first.context.material_service.get_material(material.id)
        assert kept.title == ("B" if operation == "undo" else "A")  # операция откатилась целиком

    def test_admins_deleting_each_other_do_not_deadlock(self, apps):
        first, second = apps
        service = first.context.user_management_service
        other = service.create_user(
            first.admin, "admin2", "a2@example.org", "Password123!", Role.ADMIN
        )
        other_session = second.context.auth_service.login("admin2", "Password123!")
        gate = Gate()
        after(real(first.context.user_management_service)._user_repository, "delete", gate.hold)

        one = Worker(
            lambda: first.context.user_management_service.delete_user(first.admin, other.id)
        )
        two = Worker(
            lambda: second.context.user_management_service.delete_user(
                other_session, first.admin.id
            )
        )
        run_in_order_of_blocking(one, gate, two)

        errors = [one.error, two.error]
        assert sum(e is None for e in errors) == 1, errors  # выиграл ровно один
        loser = next(e for e in errors if e is not None)
        assert isinstance(loser, AccountDeletedError), loser

    def test_two_admins_deleting_the_same_user_leave_one_deletion_event(self, apps, bob):
        first, second = apps
        gate = Gate()
        after(real(first.context.user_management_service)._user_repository, "delete", gate.hold)

        one = Worker(lambda: first.context.user_management_service.delete_user(first.admin, bob.id))
        two = Worker(
            lambda: second.context.user_management_service.delete_user(second.admin, bob.id)
        )
        run_in_order_of_blocking(one, gate, two)

        assert one.error is None
        assert isinstance(two.error, UserNotFoundError), two.error  # а не молчаливый «успех»
        events = first.context.event_log_service.list_events(first.admin)
        assert [e.target for e in events].count("deleted:bob") == 1
