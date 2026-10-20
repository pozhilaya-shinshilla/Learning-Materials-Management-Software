from __future__ import annotations

import shutil
from datetime import date
from pathlib import Path

from src.bootstrap import ApplicationContext
from src.cli.console_io import ConsoleIO
from src.cli.menu import MenuItem
from src.cli.picker import Picker
from src.cli.presenter import Presenter
from src.config import ALLOWED_FILE_TYPES
from src.domain.enums import SortField, SortOrder
from src.domain.exceptions import (
    DateRangeError,
    DirectoryUnavailableError,
    NotADirectoryPathError,
)
from src.domain.models import Discipline, Topic, User
from src.domain.validation import (
    SORT_OPTIONS,
    OptionalParser,
    parse_date,
    parse_file_type,
    parse_sort_option,
)
from src.services.search_service import MaterialFilter


class StudentController:
    """Сценарии студента: каталог, поиск, скачивание, избранное, просмотр дисциплин и тем."""

    menu_title = "Меню студента"
    _manages_catalog = False

    def __init__(self, context: ApplicationContext, io: ConsoleIO, user: User) -> None:
        self._io = io
        self._user = user
        self._material_service = context.material_service
        self._search_service = context.search_service
        self._favorite_service = context.favorite_service
        self._catalog_service = context.catalog_service
        self._user_management_service = context.user_management_service
        self._presenter = Presenter(context.catalog_service)
        self._picker = Picker(io, self._presenter)

    def menu_items(self) -> list[MenuItem]:
        """Пункты меню студента."""
        return [
            ("Просмотреть каталог материалов", self._show_materials_flow),
            ("Сведения о материале", self._material_details_flow),
            ("Поиск, фильтрация и сортировка материалов", self._search_flow),
            ("Скачать материал", self._download_flow),
            ("Добавить материал в избранное", self._add_favorite_flow),
            ("Убрать материал из избранного", self._remove_favorite_flow),
            ("Список избранных материалов", self._list_favorites_flow),
            ("Просмотреть дисциплины и темы", self._print_catalog),
        ]

    def _say_no_materials(self) -> None:
        """Сообщить, что каталог материалов пуст, с подсказкой по роли."""
        if self._manages_catalog:
            print(
                "Каталог материалов пуст. Добавьте первый материал через пункт «Добавить материал»."
            )
        else:
            print("Каталог материалов пока пуст. Материалы добавляют преподаватели.")

    def _say_no_disciplines(self) -> None:
        """Сообщить, что дисциплин нет, с подсказкой по роли."""
        if self._manages_catalog:
            print("Дисциплин пока нет. Сначала добавьте дисциплину (пункт «Добавить дисциплину»).")
        else:
            print("Дисциплин пока нет. Их добавляют преподаватели.")

    def _say_no_topics(self, discipline: Discipline) -> None:
        """Сообщить, что в дисциплине нет тем, с подсказкой по роли."""
        if self._manages_catalog:
            print(
                f"В дисциплине «{discipline.name}» пока нет тем. "
                "Сначала добавьте тему (пункт «Добавить тему»)."
            )
        else:
            print(f"В дисциплине «{discipline.name}» пока нет тем.")

    def _show_materials_flow(self) -> None:
        """Показать каталог материалов."""
        materials = self._material_service.list_materials()
        if not materials:
            self._say_no_materials()
            return
        self._presenter.print_materials(materials)

    def _search_flow(self) -> None:
        """Поиск и фильтрация материалов."""
        if not self._material_service.list_materials():
            self._say_no_materials()
            return
        self._io.header("Поиск материалов (Enter — пропустить условие)")
        query = self._io.ask_optional_text("Поисковый запрос: ")
        discipline: Discipline | None = None
        topic: Topic | None = None
        disciplines = self._catalog_service.list_disciplines()
        if disciplines:
            discipline = self._picker.pick_optional_discipline("Дисциплина: ", disciplines)
        if discipline is not None:
            topics = self._catalog_service.list_topics(discipline.id)
            if topics:
                topic = self._picker.pick_optional_topic("Тема: ", topics)
            else:
                self._say_no_topics(discipline)
        allowed = ", ".join(sorted(t.value for t in ALLOWED_FILE_TYPES))
        file_type = self._io.ask(f"Формат файла ({allowed}): ", OptionalParser(parse_file_type))
        date_from = self._io.ask("Загружено с даты (ДД.ММ.ГГГГ): ", OptionalParser(parse_date))
        date_to = self._io.ask(
            "Загружено по дату (ДД.ММ.ГГГГ): ",
            lambda raw: self._parse_date_to(raw, date_from),
        )
        sort_field, sort_order = self._ask_sort_option()
        criteria = MaterialFilter(
            query=query,
            discipline_id=discipline.id if discipline else None,
            topic_id=topic.id if topic else None,
            file_type=file_type,
            uploaded_on_or_after=date_from,
            uploaded_on_or_before=date_to,
        )
        results = self._search_service.search(
            criteria, sort_field=sort_field, sort_order=sort_order
        )
        if not results:
            print("По заданным условиям ничего не найдено.")
            return
        print(f"Найдено материалов: {len(results)}")
        self._presenter.print_materials(results)

    @staticmethod
    def _parse_date_to(raw: str, date_from: date | None) -> date | None:
        """Разобрать конечную дату периода; она не может быть раньше начальной."""
        date_to = OptionalParser(parse_date)(raw)
        if date_to is not None and date_from is not None and date_to < date_from:
            raise DateRangeError()
        return date_to

    def _ask_sort_option(self) -> tuple[SortField, SortOrder]:
        """Показать варианты сортировки и спросить номер (Enter — по умолчанию первый)."""
        print("Сортировка:")
        for number, (label, _field, _order) in enumerate(SORT_OPTIONS, start=1):
            print(f"  {number}) {label}")
        return self._io.ask("Номер варианта (Enter — 1): ", parse_sort_option)

    def _material_details_flow(self) -> None:
        """Показать полные сведения об одном материале."""
        materials = self._material_service.list_materials()
        if not materials:
            self._say_no_materials()
            return
        self._io.header("Сведения о материале")
        material = self._picker.pick_material("ID материала: ", materials)
        favorite_ids = {m.id for m in self._favorite_service.list_favorites(self._user)}
        author = self._user_management_service.get_author_login(material.author_id)
        self._presenter.print_material_details(material, author, material.id in favorite_ids)

    def _download_flow(self) -> None:
        """Скачать файл материала в выбранную папку."""
        materials = self._material_service.list_materials()
        if not materials:
            self._say_no_materials()
            return
        self._io.header("Скачивание материала")
        material = self._picker.pick_material("ID материала: ", materials)
        source_path = self._material_service.resolve_file_path(material.id)
        if not source_path.is_file():
            print("Файл материала не найден в хранилище — возможно, он был удалён вручную.")
            return
        destination_dir = self._io.ask(
            "Папка для сохранения (Enter — текущая папка): ", self._parse_destination_dir
        )
        destination = destination_dir / material.file_name
        if destination.exists() and not self._io.confirm(f"Файл {destination} уже есть. Заменить?"):
            print("Скачивание отменено.")
            return
        try:
            shutil.copyfile(source_path, destination)
        except OSError as error:
            print(f"Не удалось сохранить файл: {error}")
            return
        self._material_service.record_download(self._user, material.id)
        print(f"Файл сохранен: {destination}")

    def _parse_destination_dir(self, raw: str) -> Path:
        """Разобрать путь к папке для сохранения; пустой ввод — текущая папка."""
        cleaned = self._clean_path(raw)
        directory = Path(cleaned).expanduser() if cleaned else Path.cwd()
        if directory.exists() and not directory.is_dir():
            raise NotADirectoryPathError()
        try:
            directory.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            raise DirectoryUnavailableError(reason=error) from error
        return directory

    @staticmethod
    def _clean_path(raw: str) -> str:
        """Убрать пробелы и кавычки, которые Windows добавляет при «Копировать как путь»."""
        return raw.strip().strip('"').strip("'").strip()

    def _add_favorite_flow(self) -> None:
        """Добавить материал в избранное."""
        materials = self._material_service.list_materials()
        if not materials:
            self._say_no_materials()
            return
        favorite_ids = {m.id for m in self._favorite_service.list_favorites(self._user)}
        available = [m for m in materials if m.id not in favorite_ids]
        if not available:
            print("Все материалы каталога уже в вашем избранном.")
            return
        self._io.header("Добавление в избранное")
        material = self._picker.pick_material("ID материала: ", available)
        self._favorite_service.add_favorite(self._user, material.id)
        print(f"Материал «{material.title}» добавлен в избранное.")

    def _remove_favorite_flow(self) -> None:
        """Убрать материал из избранного."""
        favorites = self._favorite_service.list_favorites(self._user)
        if not favorites:
            print("В избранном пока ничего нет.")
            return
        self._io.header("Удаление из избранного")
        material = self._picker.pick_material("ID материала: ", favorites)
        self._favorite_service.remove_favorite(self._user, material.id)
        print(f"Материал «{material.title}» убран из избранного.")

    def _list_favorites_flow(self) -> None:
        """Показать избранные материалы."""
        favorites = self._favorite_service.list_favorites(self._user)
        if not favorites:
            print("В избранном пока ничего нет.")
            return
        self._presenter.print_materials(favorites)

    def _print_catalog(self) -> None:
        """Показать дисциплины и их темы."""
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
