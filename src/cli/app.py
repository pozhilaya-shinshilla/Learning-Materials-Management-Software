from __future__ import annotations

import getpass
import os
import shutil
import sys
from collections.abc import Callable
from pathlib import Path

from src.config import ALLOWED_FILE_TYPES
from src.domain.enums import Role, SortField, SortOrder
from src.domain.exceptions import DomainError, EntityNotFoundError, ValidationError
from src.domain.models import Discipline, Material, Topic, User
from src.domain.validation import (
    MAX_TITLE_LENGTH,
    optional,
    parse_file_type,
    parse_positive_int,
    parse_role,
    parse_yes_no,
    require_text,
    role_hint,
    validate_login,
    validate_password,
)
from src.services.auth_service import AuthService
from src.services.catalog_service import CatalogService
from src.services.event_log_service import EventLogService
from src.services.favorite_service import FavoriteService
from src.services.material_service import MaterialService
from src.services.search_service import MaterialFilter, SearchService
from src.services.user_management_service import UserManagementService

MenuItem = tuple[str, Callable[[], None]]

_CANCEL_WORDS = frozenset({"0", "отмена", "cancel"})
_DATE_TIME_FORMAT = "%d.%m.%Y %H:%M:%S"


class _Cancelled(Exception):
    """Пользователь отказался от текущего действия (ввёл 0 / «отмена»)."""


class CliApplication:
    """Menu-driven terminal interface for the study materials service.

    Menus are cumulative by role: a teacher sees every student action plus
    their own, and an administrator sees every teacher (and thus student)
    action plus account management.

    Input rules shared by every form:
    * an invalid value is explained and the *same* question is asked again —
      the user is never thrown back to the menu because of a typo;
    * "0" (or "отмена") cancels the current action;
    * before asking anything the form checks that there is something to work
      with (materials, disciplines, topics, users) and says so right away.
    """

    def __init__(
        self,
        auth_service: AuthService,
        user_management_service: UserManagementService,
        material_service: MaterialService,
        search_service: SearchService,
        favorite_service: FavoriteService,
        event_log_service: EventLogService,
        catalog_service: CatalogService,
    ) -> None:
        self._auth_service = auth_service
        self._user_management_service = user_management_service
        self._material_service = material_service
        self._search_service = search_service
        self._favorite_service = favorite_service
        self._event_log_service = event_log_service
        self._catalog_service = catalog_service
        self._current_user: User | None = None

    # ------------------------------------------------------------------ цикл

    def run(self) -> None:
        """Start the interactive command loop; returns when the user exits."""
        try:
            while True:
                if self._current_user is None:
                    self._clear_screen()
                    print("=== Сервис управления учебными материалами ===")
                    if not self._login_prompt():
                        break
                    continue
                self._show_menu()
        except (EOFError, KeyboardInterrupt):
            print("\nЗавершение работы.")

    def _login_prompt(self) -> bool:
        """Ask for credentials until login succeeds; return False if the user chose to exit."""
        while self._current_user is None:
            login = self._read_login()
            if login is None:
                return False
            password = self._read_password()
            try:
                self._current_user = self._auth_service.login(login, password)
            except DomainError as error:
                print(f"Ошибка входа: {error}")
                continue
            print(f"Добро пожаловать, {login}! Роль: {self._current_user.role.label}.")
            self._pause()
        return True

    def _read_login(self) -> str | None:
        while True:
            raw = input("Логин (или 'exit' для выхода): ").strip()
            if raw.lower() == "exit":
                return None
            try:
                if not raw:
                    raise ValidationError("Введите логин.")
                validate_login(raw)
            except ValidationError as error:
                print(f"Ошибка: {error}")
                continue
            return raw

    def _read_password(self) -> str:
        while True:
            password = getpass.getpass("Пароль: ")
            if password:
                return password
            print("Ошибка: введите пароль.")

    def _logout(self) -> None:
        if self._current_user is not None:
            self._auth_service.logout(self._current_user)
        self._current_user = None

    # ------------------------------------------------------------------ меню

    def _student_items(self) -> list[MenuItem]:
        return [
            ("Просмотреть каталог материалов", self._show_materials_flow),
            ("Поиск и фильтрация материалов", self._search_flow),
            ("Скачать материал", self._download_flow),
            ("Добавить материал в избранное", self._add_favorite_flow),
            ("Убрать материал из избранного", self._remove_favorite_flow),
            ("Список избранных материалов", self._list_favorites_flow),
            ("Просмотреть дисциплины и темы", self._print_catalog),
        ]

    def _teacher_items(self) -> list[MenuItem]:
        return self._student_items() + [
            ("Добавить материал", self._create_material_flow),
            ("Редактировать материал", self._edit_material_flow),
            ("Удалить материал", self._delete_material_flow),
            ("Добавить дисциплину", self._create_discipline_flow),
            ("Добавить тему", self._create_topic_flow),
        ]

    def _admin_items(self) -> list[MenuItem]:
        return self._teacher_items() + [
            ("Список пользователей", self._list_users_flow),
            ("Создать пользователя", self._create_user_flow),
            ("Изменить роль пользователя", self._change_role_flow),
            ("Заблокировать/разблокировать пользователя", self._toggle_block_flow),
            ("Удалить пользователя", self._delete_user_flow),
            ("Просмотреть журнал событий", self._print_events_flow),
        ]

    def _items_for_current_role(self) -> tuple[str, list[MenuItem]]:
        role = self._current_user.role if self._current_user is not None else None
        if role is Role.TEACHER:
            return "Меню преподавателя", self._teacher_items()
        if role is Role.ADMIN:
            return "Меню администратора", self._admin_items()
        return "Меню студента", self._student_items()

    def _show_menu(self) -> None:
        """Redraw the menu on a clean screen, run one action, wait for Enter."""
        title, items = self._items_for_current_role()
        self._clear_screen()
        print(f"--- {title} ({self._current_user.login}) ---")
        for index, (label, _handler) in enumerate(items, start=1):
            print(f"{index}) {label}")
        print("0) Выйти из аккаунта")
        handler = self._read_menu_choice(items)
        if handler is None:
            self._logout()
            return
        print()
        try:
            handler()
        except _Cancelled:
            print("Действие отменено.")
        except DomainError as error:
            print(f"Ошибка: {error}")
        self._pause()

    def _read_menu_choice(self, items: list[MenuItem]) -> Callable[[], None] | None:
        """Ask until a valid item number is typed; None means "log out"."""
        while True:
            choice = input("Выберите действие: ").strip()
            if choice == "0":
                return None
            if choice.isdecimal() and 1 <= int(choice) <= len(items):
                return items[int(choice) - 1][1]
            print(f"Нет такого пункта. Введите число от 0 до {len(items)}.")

    # ----------------------------------------------------------- экран/пауза

    def _clear_screen(self) -> None:
        """Wipe the console so the menu is redrawn in place (only in a real terminal)."""
        if sys.stdout.isatty():
            os.system("cls" if os.name == "nt" else "clear")  # noqa: S605
        else:
            print()

    def _pause(self) -> None:
        input("\nНажмите Enter, чтобы вернуться в меню...")

    def _header(self, title: str) -> None:
        print(f"== {title} ==  (0 — отмена)")

    # ------------------------------------------------- ввод: общий механизм

    def _ask[T](self, prompt: str, parser: Callable[[str], T]) -> T:
        """Ask until `parser` accepts the answer; "0"/"отмена" raises _Cancelled.

        `parser` raises DomainError with a user-readable message on bad input;
        the message is printed and the same question is asked again.
        """
        while True:
            raw = input(prompt)
            if raw.strip().lower() in _CANCEL_WORDS:
                raise _Cancelled
            try:
                return parser(raw)
            except DomainError as error:
                print(f"  ✗ {error}")

    def _confirm(self, prompt: str) -> bool:
        return self._ask(prompt + " (y/n): ", parse_yes_no)

    def _ask_text(self, prompt: str, field_name: str, max_length: int = 100) -> str:
        return self._ask(prompt, lambda raw: require_text(raw, field_name, max_length))

    def _ask_optional_text(self, prompt: str) -> str | None:
        return self._ask(prompt, lambda raw: raw.strip() or None)

    # --------------------------------------- проверки «есть ли с чем работать»

    def _can_manage_catalog(self) -> bool:
        return self._current_user is not None and self._current_user.role is not Role.STUDENT

    def _say_no_materials(self) -> None:
        if self._can_manage_catalog():
            print(
                "Каталог материалов пуст. Добавьте первый материал через пункт «Добавить материал»."
            )
        else:
            print("Каталог материалов пока пуст. Материалы добавляют преподаватели.")

    def _say_no_disciplines(self) -> None:
        if self._can_manage_catalog():
            print("Дисциплин пока нет. Сначала добавьте дисциплину (пункт «Добавить дисциплину»).")
        else:
            print("Дисциплин пока нет. Их добавляют преподаватели.")

    def _say_no_topics(self, discipline: Discipline) -> None:
        if self._can_manage_catalog():
            print(
                f"В дисциплине «{discipline.name}» пока нет тем. "
                "Сначала добавьте тему (пункт «Добавить тему»)."
            )
        else:
            print(f"В дисциплине «{discipline.name}» пока нет тем.")

    # ------------------------------------------- выбор дисциплины/темы/записи

    def _pick_discipline(
        self,
        prompt: str,
        disciplines: list[Discipline],
        *,
        allow_empty: bool = False,
    ) -> Discipline | None:
        """Show discipline names and ask for one by name (case-insensitive)."""
        print("Доступные дисциплины:")
        for discipline in disciplines:
            print(f"  • {discipline.name}")
        by_name = {d.name.casefold(): d for d in disciplines}

        def parse(raw: str) -> Discipline:
            found = by_name.get(raw.strip().casefold())
            if found is None:
                if not raw.strip():
                    raise ValidationError("Введите название дисциплины из списка.")
                raise EntityNotFoundError(
                    f"Дисциплина «{raw.strip()}» не найдена. Введите название из списка."
                )
            return found

        return self._ask(prompt, optional(parse) if allow_empty else parse)

    def _pick_topic(
        self, prompt: str, topics: list[Topic], *, allow_empty: bool = False
    ) -> Topic | None:
        """Show topic names and ask for one by name (case-insensitive)."""
        print("Доступные темы:")
        for topic in topics:
            print(f"  • {topic.name}")
        by_name = {t.name.casefold(): t for t in topics}

        def parse(raw: str) -> Topic:
            found = by_name.get(raw.strip().casefold())
            if found is None:
                if not raw.strip():
                    raise ValidationError("Введите название темы из списка.")
                raise EntityNotFoundError(
                    f"Тема «{raw.strip()}» не найдена. Введите название из списка."
                )
            return found

        return self._ask(prompt, optional(parse) if allow_empty else parse)

    def _disciplines_with_topics(self) -> list[Discipline]:
        return [
            d
            for d in self._catalog_service.list_disciplines()
            if self._catalog_service.list_topics(d.id)
        ]

    def _pick_material(self, prompt: str, materials: list[Material]) -> Material:
        """Print the given materials and ask for the ID of one of them."""
        self._print_materials(materials)
        by_id = {m.id: m for m in materials}

        def parse(raw: str) -> Material:
            material_id = parse_positive_int(raw)
            found = by_id.get(material_id)
            if found is None:
                ids = ", ".join(str(i) for i in by_id)
                raise EntityNotFoundError(
                    f"В списке нет материала с ID {material_id}. Доступные ID: {ids}."
                )
            return found

        return self._ask(prompt, parse)

    def _pick_user(self, prompt: str, users: list[User]) -> User:
        """Print the given users and ask for the ID of one of them."""
        self._print_users(users)
        by_id = {u.id: u for u in users}

        def parse(raw: str) -> User:
            user_id = parse_positive_int(raw)
            found = by_id.get(user_id)
            if found is None:
                ids = ", ".join(str(i) for i in by_id)
                raise EntityNotFoundError(
                    f"В списке нет пользователя с ID {user_id}. Доступные ID: {ids}."
                )
            return found

        return self._ask(prompt, parse)

    def _other_users(self) -> list[User]:
        users = self._user_management_service.list_users(self._current_user)
        return [u for u in users if u.id != self._current_user.id]

    # --------------------------------------- материалы (студент и выше)

    def _show_materials_flow(self) -> None:
        materials = self._material_service.list_materials()
        if not materials:
            self._say_no_materials()
            return
        self._print_materials(materials)

    def _search_flow(self) -> None:
        if not self._material_service.list_materials():
            self._say_no_materials()
            return
        self._header("Поиск материалов (Enter — пропустить условие)")
        query = self._ask_optional_text("Поисковый запрос: ")
        discipline: Discipline | None = None
        topic: Topic | None = None
        disciplines = self._catalog_service.list_disciplines()
        if disciplines:
            discipline = self._pick_discipline("Дисциплина: ", disciplines, allow_empty=True)
        if discipline is not None:
            topics = self._catalog_service.list_topics(discipline.id)
            if topics:
                topic = self._pick_topic("Тема: ", topics, allow_empty=True)
            else:
                self._say_no_topics(discipline)
        allowed = ", ".join(sorted(t.value for t in ALLOWED_FILE_TYPES))
        file_type = self._ask(f"Формат файла ({allowed}): ", optional(parse_file_type))
        criteria = MaterialFilter(
            query=query,
            discipline_id=discipline.id if discipline else None,
            topic_id=topic.id if topic else None,
            file_type=file_type,
        )
        results = self._search_service.search(
            criteria, sort_field=SortField.UPLOAD_DATE, sort_order=SortOrder.DESCENDING
        )
        if not results:
            print("По заданным условиям ничего не найдено.")
            return
        print(f"Найдено материалов: {len(results)}")
        self._print_materials(results)

    def _download_flow(self) -> None:
        materials = self._material_service.list_materials()
        if not materials:
            self._say_no_materials()
            return
        self._header("Скачивание материала")
        material = self._pick_material("ID материала: ", materials)
        source_path = self._material_service.resolve_file_path(material.id)
        if not source_path.is_file():
            print("Файл материала не найден в хранилище — возможно, он был удалён вручную.")
            return
        destination_dir = self._ask(
            "Папка для сохранения (Enter — текущая папка): ", self._parse_destination_dir
        )
        destination = destination_dir / material.file_name
        if destination.exists() and not self._confirm(f"Файл {destination} уже есть. Заменить?"):
            print("Скачивание отменено.")
            return
        try:
            shutil.copyfile(source_path, destination)
        except OSError as error:
            print(f"Не удалось сохранить файл: {error}")
            return
        self._material_service.record_download(self._current_user, material.id)
        print(f"Файл сохранен: {destination}")

    def _parse_destination_dir(self, raw: str) -> Path:
        cleaned = self._clean_path(raw)
        directory = Path(cleaned).expanduser() if cleaned else Path.cwd()
        if directory.exists() and not directory.is_dir():
            raise ValidationError("Указанный путь — это файл, нужна папка.")
        try:
            directory.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            raise ValidationError(f"Не удалось открыть или создать папку: {error}") from error
        return directory

    @staticmethod
    def _clean_path(raw: str) -> str:
        """Strip spaces and the quotes Windows adds with "Copy as path"."""
        return raw.strip().strip('"').strip("'").strip()

    def _add_favorite_flow(self) -> None:
        materials = self._material_service.list_materials()
        if not materials:
            self._say_no_materials()
            return
        favorite_ids = {m.id for m in self._favorite_service.list_favorites(self._current_user)}
        available = [m for m in materials if m.id not in favorite_ids]
        if not available:
            print("Все материалы каталога уже в вашем избранном.")
            return
        self._header("Добавление в избранное")
        material = self._pick_material("ID материала: ", available)
        self._favorite_service.add_favorite(self._current_user, material.id)
        print(f"Материал «{material.title}» добавлен в избранное.")

    def _remove_favorite_flow(self) -> None:
        favorites = self._favorite_service.list_favorites(self._current_user)
        if not favorites:
            print("В избранном пока ничего нет.")
            return
        self._header("Удаление из избранного")
        material = self._pick_material("ID материала: ", favorites)
        self._favorite_service.remove_favorite(self._current_user, material.id)
        print(f"Материал «{material.title}» убран из избранного.")

    def _list_favorites_flow(self) -> None:
        favorites = self._favorite_service.list_favorites(self._current_user)
        if not favorites:
            print("В избранном пока ничего нет.")
            return
        self._print_materials(favorites)

    def _print_catalog(self) -> None:
        disciplines = self._catalog_service.list_disciplines()
        if not disciplines:
            self._say_no_disciplines()
            return
        for discipline in disciplines:
            print(f"• {discipline.name}")
            topics = self._catalog_service.list_topics(discipline.id)
            if not topics:
                print("    (тем пока нет)")
            for topic in topics:
                print(f"    – {topic.name}")

    # --------------------------- материалы и каталог (преподаватель и выше)

    def _create_material_flow(self) -> None:
        disciplines = self._catalog_service.list_disciplines()
        if not disciplines:
            self._say_no_disciplines()
            return
        with_topics = self._disciplines_with_topics()
        if not with_topics:
            print(
                "Ни в одной дисциплине пока нет тем. Сначала добавьте тему (пункт «Добавить тему»)."
            )
            return
        self._header("Добавление материала")
        title = self._ask_text("Название: ", "Название", MAX_TITLE_LENGTH)
        description = self._ask_optional_text("Описание (Enter — пропустить): ") or ""
        discipline = self._pick_discipline("Дисциплина: ", with_topics)
        topic = self._pick_topic("Тема: ", self._catalog_service.list_topics(discipline.id))
        source_path = self._ask("Путь к файлу на компьютере: ", self._parse_source_file)
        material = self._material_service.create_material(
            self._current_user, title, description, discipline.id, topic.id, source_path
        )
        print(
            f"Материал создан, ID: {material.id} "
            f"(файл: {material.file_name}, {self._format_size(material.file_size_bytes)}, "
            f"формат {material.file_type.value})"
        )

    def _parse_source_file(self, raw: str) -> Path:
        cleaned = self._clean_path(raw)
        if not cleaned:
            raise ValidationError("Путь к файлу обязателен.")
        path = Path(cleaned).expanduser()
        self._material_service.validate_source_file(path)
        return path

    def _edit_material_flow(self) -> None:
        editable = self._material_service.list_editable(self._current_user)
        if not editable:
            if self._material_service.list_materials():
                print("У вас нет материалов для редактирования: можно менять только свои.")
            else:
                self._say_no_materials()
            return
        self._header("Редактирование материала (Enter — не менять)")
        material = self._pick_material("ID материала: ", editable)
        print(
            f"Выбрано: «{material.title}» "
            f"({self._catalog_service.describe(material.discipline_id, material.topic_id)})"
        )
        title = self._ask(
            "Новое название: ",
            optional(lambda raw: require_text(raw, "Название", MAX_TITLE_LENGTH)),
        )
        description = self._ask_optional_text("Новое описание: ")

        new_discipline_id: int | None = None
        new_topic_id: int | None = None
        disciplines = self._disciplines_with_topics()
        if disciplines:
            discipline = self._pick_discipline("Новая дисциплина: ", disciplines, allow_empty=True)
            if discipline is not None:
                topic = self._pick_topic(
                    "Тема новой дисциплины: ", self._catalog_service.list_topics(discipline.id)
                )
                new_discipline_id, new_topic_id = discipline.id, topic.id
            else:
                current_topics = self._catalog_service.list_topics(material.discipline_id)
                topic = self._pick_topic("Новая тема: ", current_topics, allow_empty=True)
                if topic is not None:
                    new_topic_id = topic.id

        if title is None and description is None and new_topic_id is None:
            print("Ничего не изменено.")
            return
        self._material_service.edit_material(
            self._current_user,
            material.id,
            title=title,
            description=description,
            discipline_id=new_discipline_id,
            topic_id=new_topic_id,
        )
        print("Материал обновлен.")

    def _delete_material_flow(self) -> None:
        deletable = self._material_service.list_editable(self._current_user)
        if not deletable:
            if self._material_service.list_materials():
                print("У вас нет материалов для удаления: можно удалять только свои.")
            else:
                self._say_no_materials()
            return
        self._header("Удаление материала")
        material = self._pick_material("ID материала: ", deletable)
        if not self._confirm(f"Удалить «{material.title}» без возможности восстановления?"):
            print("Удаление отменено.")
            return
        self._material_service.delete_material(self._current_user, material.id)
        print("Материал удален.")

    def _create_discipline_flow(self) -> None:
        self._header("Добавление дисциплины")
        disciplines = self._catalog_service.list_disciplines()
        if disciplines:
            print("Уже существуют: " + ", ".join(d.name for d in disciplines))
        name = self._ask("Название дисциплины: ", self._catalog_service.ensure_discipline_name_free)
        self._catalog_service.create_discipline(self._current_user, name)
        print(f"Дисциплина «{name}» создана.")

    def _create_topic_flow(self) -> None:
        disciplines = self._catalog_service.list_disciplines()
        if not disciplines:
            self._say_no_disciplines()
            return
        self._header("Добавление темы")
        discipline = self._pick_discipline("Дисциплина, к которой относится тема: ", disciplines)
        topics = self._catalog_service.list_topics(discipline.id)
        if topics:
            print("Уже есть темы: " + ", ".join(t.name for t in topics))
        name = self._ask(
            "Название темы: ",
            lambda raw: self._catalog_service.ensure_topic_name_free(discipline.id, raw),
        )
        self._catalog_service.create_topic(self._current_user, name, discipline.id)
        print(f"Тема «{name}» добавлена в дисциплину «{discipline.name}».")

    # --------------------------- пользователи и журнал (только администратор)

    def _list_users_flow(self) -> None:
        self._print_users(self._user_management_service.list_users(self._current_user))

    def _create_user_flow(self) -> None:
        self._header("Создание пользователя")
        service = self._user_management_service

        def parse_login(raw: str) -> str:
            login = raw.strip()
            service.ensure_login_available(login)
            return login

        def parse_email(raw: str) -> str:
            email = raw.strip()
            service.ensure_email_available(email)
            return email

        def parse_password(raw: str) -> str:
            validate_password(raw)
            return raw

        login = self._ask("Логин (3-32: латиница, цифры, _ и -): ", parse_login)
        email = self._ask("Email: ", parse_email)
        password = self._ask("Пароль (не короче 8 символов): ", parse_password)
        role = self._ask(f"Роль ({role_hint()}): ", parse_role)
        user = service.create_user(self._current_user, login, email, password, role)
        print(f"Пользователь {user.login} создан, ID: {user.id}, роль: {user.role.label}.")

    def _change_role_flow(self) -> None:
        others = self._other_users()
        if not others:
            print("Других пользователей пока нет — менять роль некому.")
            return
        self._header("Изменение роли")
        target = self._pick_user("ID пользователя: ", others)

        def parse_new_role(raw: str) -> Role:
            role = parse_role(raw)
            if role is target.role:
                raise ValidationError(f"У пользователя {target.login} уже роль «{role.label}».")
            return role

        role = self._ask(f"Новая роль ({role_hint()}): ", parse_new_role)
        self._user_management_service.change_role(self._current_user, target.id, role)
        print(f"Роль пользователя {target.login} изменена на «{role.label}».")

    def _toggle_block_flow(self) -> None:
        others = self._other_users()
        if not others:
            print("Других пользователей пока нет — блокировать некого.")
            return
        self._header("Блокировка / разблокировка")
        target = self._pick_user("ID пользователя: ", others)
        block = target.is_active()  # активного блокируем, заблокированного разблокируем
        action = "Заблокировать" if block else "Разблокировать"
        if not self._confirm(f"{action} пользователя {target.login}?"):
            print("Действие отменено.")
            return
        self._user_management_service.set_blocked(self._current_user, target.id, block)
        print(f"Пользователь {target.login} {'заблокирован' if block else 'разблокирован'}.")

    def _delete_user_flow(self) -> None:
        others = self._other_users()
        if not others:
            print("Других пользователей пока нет — удалять некого.")
            return
        self._header("Удаление пользователя")
        target = self._pick_user("ID пользователя: ", others)
        if not self._confirm(f"Удалить пользователя {target.login}?"):
            print("Удаление отменено.")
            return
        self._user_management_service.delete_user(self._current_user, target.id)
        print(f"Пользователь {target.login} удален.")

    def _print_events_flow(self) -> None:
        events = self._event_log_service.list_events(self._current_user)
        if not events:
            print("Журнал событий пуст.")
            return
        logins = {
            u.id: u.login for u in self._user_management_service.list_users(self._current_user)
        }
        for event in events:
            who = logins.get(event.user_id) or (
                "гость" if event.user_id == 0 else f"ID {event.user_id} (удален)"
            )
            when = event.occurred_at.astimezone().strftime(_DATE_TIME_FORMAT)
            print(f"{when}  {who}: {event.event_type.label} — {event.target}")

    # ------------------------------------------------------------------ вывод

    @staticmethod
    def _format_size(size_bytes: int) -> str:
        if size_bytes < 1024:
            return f"{size_bytes} Б"
        if size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} КБ"
        return f"{size_bytes / (1024 * 1024):.1f} МБ"

    def _print_materials(self, materials: list[Material]) -> None:
        for material in materials:
            where = self._catalog_service.describe(material.discipline_id, material.topic_id)
            print(
                f"[{material.id}] {material.title} — {where} — "
                f"{material.file_type.value}, {self._format_size(material.file_size_bytes)} — "
                f"{material.uploaded_at.astimezone():%d.%m.%Y}"
            )
            if material.description:
                print(f"      {material.description}")

    def _print_users(self, users: list[User]) -> None:
        for user in users:
            print(
                f"[{user.id}] {user.login} ({user.email}) — {user.role.label} — {user.status.label}"
            )
