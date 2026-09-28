from __future__ import annotations

import shutil
from collections.abc import Callable
from pathlib import Path

from src.domain.enums import FileType, Role, SortField, SortOrder
from src.domain.exceptions import DomainError
from src.domain.models import Material, User
from src.services.auth_service import AuthService
from src.services.catalog_service import CatalogService
from src.services.event_log_service import EventLogService
from src.services.favorite_service import FavoriteService
from src.services.material_service import MaterialService
from src.services.search_service import MaterialFilter, SearchService
from src.services.user_management_service import UserManagementService

_ROLE_SHORTCUTS: dict[str, Role] = {"s": Role.STUDENT, "t": Role.TEACHER, "a": Role.ADMIN}

MenuItem = tuple[str, Callable[[], None]]


class CliApplication:
    """Menu-driven terminal interface for the study materials service.

    Menus are cumulative by role: a teacher sees every student action plus
    their own, and an administrator sees every teacher (and thus student)
    action plus account management.
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

    def run(self) -> None:
        """Start the interactive command loop; returns when the user exits."""
        print("=== Сервис управления учебными материалами ===")
        try:
            while True:
                if self._current_user is None:
                    if not self._login_prompt():
                        break
                    continue
                self._show_menu()
        except (EOFError, KeyboardInterrupt):
            print("\nЗавершение работы.")

    def _login_prompt(self) -> bool:
        login = input("Логин (или 'exit' для выхода): ").strip()
        if login.lower() == "exit":
            return False
        password = input("Пароль: ").strip()
        try:
            self._current_user = self._auth_service.login(login, password)
            print(f"Добро пожаловать, {login}! Роль: {self._current_user.role.value}")
        except DomainError as error:
            print(f"Ошибка входа: {error}")
        return True

    def _logout(self) -> None:
        if self._current_user is not None:
            self._auth_service.logout(self._current_user)
        self._current_user = None

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
        title, items = self._items_for_current_role()
        print(f"\n--- {title} ---")
        for index, (label, _handler) in enumerate(items, start=1):
            print(f"{index}) {label}")
        print("0) Выйти из аккаунта")
        choice = input("Выберите действие: ").strip()
        if choice == "0":
            self._logout()
            return
        handler = self._resolve_choice(choice, items)
        if handler is None:
            print("Неизвестный пункт меню.")
            return
        try:
            handler()
        except DomainError as error:
            print(f"Ошибка: {error}")

    def _resolve_choice(self, choice: str, items: list[MenuItem]) -> Callable[[], None] | None:
        if not choice.isdigit():
            return None
        index = int(choice) - 1
        if index < 0 or index >= len(items):
            return None
        return items[index][1]

    # --- безопасный ввод: некорректные данные никогда не «роняют» программу ---

    def _read_int(self, prompt: str) -> int | None:
        raw = input(prompt).strip()
        try:
            return int(raw)
        except ValueError:
            print("Нужно ввести целое число.")
            return None

    def _read_optional_int(self, prompt: str) -> int | None:
        raw = input(prompt).strip()
        if not raw:
            return None
        try:
            return int(raw)
        except ValueError:
            print("Значение проигнорировано — нужно целое число.")
            return None

    def _read_yes_no(self, prompt: str) -> bool | None:
        raw = input(prompt).strip().lower()
        if raw in {"y", "yes"}:
            return True
        if raw in {"n", "no"}:
            return False
        print("Введите 'y' (да) или 'n' (нет).")
        return None

    def _role_prompt_hint(self) -> str:
        return ", ".join(f"{role.value}/{letter}" for letter, role in _ROLE_SHORTCUTS.items())

    def _read_role(self, prompt: str) -> Role | None:
        raw = input(prompt).strip().lower()
        if raw in _ROLE_SHORTCUTS:
            return _ROLE_SHORTCUTS[raw]
        try:
            return Role(raw)
        except ValueError:
            print(f"Неизвестная роль. Доступные варианты: {self._role_prompt_hint()}.")
            return None

    def _read_optional_file_type(self, prompt: str) -> FileType | None:
        raw = input(prompt).strip().lower()
        if not raw:
            return None
        try:
            return FileType(raw)
        except ValueError:
            allowed = ", ".join(t.value for t in FileType)
            print(f"Неизвестный формат, фильтр проигнорирован. Допустимые форматы: {allowed}.")
            return None

    # --- материалы (доступно студенту и выше) ---

    def _show_materials_flow(self) -> None:
        self._print_materials(self._material_service.list_materials())

    def _search_flow(self) -> None:
        query = input("Поисковый запрос (Enter — пропустить): ").strip() or None
        discipline_id = self._read_optional_int("Фильтр по ID дисциплины (Enter — пропустить): ")
        topic_id = self._read_optional_int("Фильтр по ID темы (Enter — пропустить): ")
        file_type = self._read_optional_file_type(
            "Фильтр по формату файла, например pdf (Enter — пропустить): "
        )
        criteria = MaterialFilter(
            query=query, discipline_id=discipline_id, topic_id=topic_id, file_type=file_type
        )
        results = self._search_service.search(
            criteria, sort_field=SortField.UPLOAD_DATE, sort_order=SortOrder.DESCENDING
        )
        self._print_materials(results)

    def _download_flow(self) -> None:
        material_id = self._read_int("ID материала: ")
        if material_id is None:
            return
        material = self._material_service.get_material(material_id)
        source_path = self._material_service.resolve_file_path(material_id)
        destination_raw = input("Папка для сохранения (Enter — текущая папка): ").strip()
        destination_dir = Path(destination_raw) if destination_raw else Path.cwd()
        try:
            destination_dir.mkdir(parents=True, exist_ok=True)
            destination = destination_dir / material.file_name
            shutil.copyfile(source_path, destination)
        except OSError as error:
            print(f"Не удалось сохранить файл: {error}")
            return
        self._material_service.record_download(self._current_user, material_id)
        print(f"Файл сохранен: {destination}")

    def _add_favorite_flow(self) -> None:
        material_id = self._read_int("ID материала: ")
        if material_id is None:
            return
        self._favorite_service.add_favorite(self._current_user, material_id)
        print("Материал добавлен в избранное.")

    def _remove_favorite_flow(self) -> None:
        material_id = self._read_int("ID материала: ")
        if material_id is None:
            return
        self._favorite_service.remove_favorite(self._current_user, material_id)
        print("Материал убран из избранного.")

    def _list_favorites_flow(self) -> None:
        self._print_materials(self._favorite_service.list_favorites(self._current_user))

    def _print_catalog(self) -> None:
        disciplines = self._catalog_service.list_disciplines()
        if not disciplines:
            print("Дисциплины не найдены.")
            return
        for discipline in disciplines:
            print(f"[{discipline.id}] {discipline.name}")
            for topic in self._catalog_service.list_topics(discipline.id):
                print(f"    [{topic.id}] {topic.name}")

    # --- материалы и каталог (преподаватель и выше) ---

    def _create_material_flow(self) -> None:
        title = input("Название: ").strip()
        description = input("Описание: ").strip()
        discipline_id = self._read_int("ID дисциплины: ")
        if discipline_id is None:
            return
        topic_id = self._read_int("ID темы: ")
        if topic_id is None:
            return
        file_path_raw = input("Путь к файлу на компьютере: ").strip()
        if not file_path_raw:
            print("Путь к файлу обязателен.")
            return
        material = self._material_service.create_material(
            self._current_user, title, description, discipline_id, topic_id, Path(file_path_raw)
        )
        print(
            f"Материал создан, ID: {material.id} "
            f"(файл: {material.file_name}, {material.file_size_bytes} байт, "
            f"формат {material.file_type.value})"
        )

    def _edit_material_flow(self) -> None:
        material_id = self._read_int("ID материала: ")
        if material_id is None:
            return
        title = input("Новое название (Enter — не менять): ").strip() or None
        description = input("Новое описание (Enter — не менять): ").strip() or None
        self._material_service.edit_material(
            self._current_user, material_id, title=title, description=description
        )
        print("Материал обновлен.")

    def _delete_material_flow(self) -> None:
        material_id = self._read_int("ID материала: ")
        if material_id is None:
            return
        self._material_service.delete_material(self._current_user, material_id)
        print("Материал удален.")

    def _create_discipline_flow(self) -> None:
        name = input("Название дисциплины: ").strip()
        discipline = self._catalog_service.create_discipline(self._current_user, name)
        print(f"Дисциплина создана, ID: {discipline.id}")

    def _create_topic_flow(self) -> None:
        name = input("Название темы: ").strip()
        discipline_id = self._read_int("ID дисциплины: ")
        if discipline_id is None:
            return
        topic = self._catalog_service.create_topic(self._current_user, name, discipline_id)
        print(f"Тема создана, ID: {topic.id}")

    # --- пользователи и журнал событий (только администратор) ---

    def _list_users_flow(self) -> None:
        self._print_users(self._user_management_service.list_users(self._current_user))

    def _create_user_flow(self) -> None:
        login = input("Логин: ").strip()
        email = input("Email: ").strip()
        password = input("Пароль: ").strip()
        role = self._read_role(f"Роль ({self._role_prompt_hint()}): ")
        if role is None:
            return
        user = self._user_management_service.create_user(
            self._current_user, login, email, password, role
        )
        print(f"Пользователь создан, ID: {user.id}")

    def _change_role_flow(self) -> None:
        user_id = self._read_int("ID пользователя: ")
        if user_id is None:
            return
        role = self._read_role(f"Новая роль ({self._role_prompt_hint()}): ")
        if role is None:
            return
        self._user_management_service.change_role(self._current_user, user_id, role)
        print("Роль обновлена.")

    def _toggle_block_flow(self) -> None:
        user_id = self._read_int("ID пользователя: ")
        if user_id is None:
            return
        blocked = self._read_yes_no("Заблокировать? (y/n): ")
        if blocked is None:
            return
        self._user_management_service.set_blocked(self._current_user, user_id, blocked)
        print("Статус учетной записи обновлен.")

    def _delete_user_flow(self) -> None:
        user_id = self._read_int("ID пользователя: ")
        if user_id is None:
            return
        self._user_management_service.delete_user(self._current_user, user_id)
        print("Пользователь удален.")

    def _print_events_flow(self) -> None:
        events = self._event_log_service.list_events(self._current_user)
        if not events:
            print("Журнал событий пуст.")
            return
        for event in events:
            print(
                f"{event.occurred_at:%Y-%m-%d %H:%M:%S} "
                f"user={event.user_id} {event.event_type.value} target={event.target}"
            )

    # --- вывод ---

    def _print_materials(self, materials: list[Material]) -> None:
        if not materials:
            print("Материалы не найдены.")
            return
        for material in materials:
            print(
                f"[{material.id}] {material.title} "
                f"({material.file_type.value}, {material.file_size_bytes} байт) — "
                f"{material.uploaded_at:%Y-%m-%d}"
            )

    def _print_users(self, users: list[User]) -> None:
        if not users:
            print("Пользователи не найдены.")
            return
        for user in users:
            print(f"[{user.id}] {user.login} — {user.role.value} — {user.status.value}")
