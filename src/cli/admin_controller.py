from __future__ import annotations

from functools import partial

from src.bootstrap import ApplicationContext
from src.cli.console_io import ConsoleIO
from src.cli.menu import MenuItem
from src.cli.teacher_controller import TeacherController
from src.domain.enums import Role
from src.domain.exceptions import SameRoleError
from src.domain.models import User
from src.domain.validation import parse_role, role_hint, validate_password


class AdminController(TeacherController):
    """Сценарии администратора: пользователи и журнал событий поверх возможностей преподавателя."""

    menu_title = "Меню администратора"

    def __init__(self, context: ApplicationContext, io: ConsoleIO, user: User) -> None:
        super().__init__(context, io, user)
        self._event_log_service = context.event_log_service

    def menu_items(self) -> list[MenuItem]:
        """Пункты меню администратора: действия преподавателя плюс управление системой."""
        return super().menu_items() + [
            ("Список пользователей", self._list_users_flow),
            ("Создать пользователя", self._create_user_flow),
            ("Изменить роль пользователя", self._change_role_flow),
            ("Заблокировать/разблокировать пользователя", self._toggle_block_flow),
            ("Удалить пользователя", self._delete_user_flow),
            ("Просмотреть журнал событий", self._print_events_flow),
        ]

    def _other_users(self) -> list[User]:
        """Вернуть всех пользователей, кроме текущего."""
        users = self._user_management_service.list_users(self._user)
        return [u for u in users if u.id != self._user.id]

    def _list_users_flow(self) -> None:
        """Показать список пользователей."""
        self._presenter.print_users(self._user_management_service.list_users(self._user))

    def _create_user_flow(self) -> None:
        """Создать пользователя."""
        self._io.header("Создание пользователя")
        login = self._io.ask("Логин (3-32: латиница, цифры, _ и -): ", self._parse_new_login)
        email = self._io.ask("Email: ", self._parse_new_email)
        password = self._io.ask("Пароль (не короче 8 символов): ", self._parse_new_password)
        role = self._io.ask(f"Роль ({role_hint()}): ", parse_role)
        user = self._user_management_service.create_user(self._user, login, email, password, role)
        print(f"Пользователь {user.login} создан, ID: {user.id}, роль: {user.role.label}.")

    def _parse_new_login(self, raw: str) -> str:
        """Разобрать логин нового пользователя и проверить, что он свободен."""
        login = raw.strip()
        self._user_management_service.ensure_login_available(login)
        return login

    def _parse_new_email(self, raw: str) -> str:
        """Разобрать email нового пользователя и проверить, что он свободен."""
        email = raw.strip()
        self._user_management_service.ensure_email_available(email)
        return email

    @staticmethod
    def _parse_new_password(raw: str) -> str:
        """Проверить пароль нового пользователя на допустимую длину."""
        validate_password(raw)
        return raw

    def _change_role_flow(self) -> None:
        """Изменить роль пользователя."""
        others = self._other_users()
        if not others:
            print("Других пользователей пока нет — менять роль некому.")
            return
        self._io.header("Изменение роли")
        target = self._picker.pick_user("ID пользователя: ", others)
        role = self._io.ask(
            f"Новая роль ({role_hint()}): ", partial(self._parse_changed_role, target=target)
        )
        self._user_management_service.change_role(self._user, target.id, role)
        print(f"Роль пользователя {target.login} изменена на «{role.label}».")

    @staticmethod
    def _parse_changed_role(raw: str, target: User) -> Role:
        """Разобрать новую роль; она должна отличаться от текущей роли пользователя."""
        role = parse_role(raw)
        if role is target.role:
            raise SameRoleError(login=target.login, role=role.label)
        return role

    def _toggle_block_flow(self) -> None:
        """Заблокировать или разблокировать пользователя."""
        others = self._other_users()
        if not others:
            print("Других пользователей пока нет — блокировать некого.")
            return
        self._io.header("Блокировка / разблокировка")
        target = self._picker.pick_user("ID пользователя: ", others)
        should_block = target.is_active()
        action = "Заблокировать" if should_block else "Разблокировать"
        if not self._io.confirm(f"{action} пользователя {target.login}?"):
            print("Действие отменено.")
            return
        self._user_management_service.set_blocked(self._user, target.id, should_block)
        print(f"Пользователь {target.login} {'заблокирован' if should_block else 'разблокирован'}.")

    def _delete_user_flow(self) -> None:
        """Удалить пользователя."""
        others = self._other_users()
        if not others:
            print("Других пользователей пока нет — удалять некого.")
            return
        self._io.header("Удаление пользователя")
        target = self._picker.pick_user("ID пользователя: ", others)
        if not self._io.confirm(f"Удалить пользователя {target.login}?"):
            print("Удаление отменено.")
            return
        self._user_management_service.delete_user(self._user, target.id)
        print(f"Пользователь {target.login} удален.")

    def _print_events_flow(self) -> None:
        """Показать журнал событий."""
        events = self._event_log_service.list_events(self._user)
        if not events:
            print("Журнал событий пуст.")
            return
        logins = {u.id: u.login for u in self._user_management_service.list_users(self._user)}
        self._presenter.print_events(events, logins)
