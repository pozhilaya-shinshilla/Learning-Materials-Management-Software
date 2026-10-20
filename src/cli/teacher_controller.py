from __future__ import annotations

from pathlib import Path

from src.cli.menu import MenuItem
from src.cli.student_controller import StudentController
from src.domain.exceptions import SourceFilePathRequiredError
from src.domain.models import Discipline
from src.domain.validation import MAX_TITLE_LENGTH, OptionalParser, require_text


class TeacherController(StudentController):
    """Сценарии преподавателя: свои материалы, дисциплины и темы поверх возможностей студента."""

    menu_title = "Меню преподавателя"
    _manages_catalog = True

    def menu_items(self) -> list[MenuItem]:
        """Пункты меню преподавателя: действия студента плюс свои."""
        return super().menu_items() + [
            ("Мои материалы", self._my_materials_flow),
            ("Добавить материал", self._create_material_flow),
            ("Редактировать материал", self._edit_material_flow),
            ("Удалить материал", self._delete_material_flow),
            ("Добавить дисциплину", self._create_discipline_flow),
            ("Добавить тему", self._create_topic_flow),
            ("Переименовать дисциплину", self._rename_discipline_flow),
            ("Переименовать тему", self._rename_topic_flow),
        ]

    def _disciplines_with_topics(self) -> list[Discipline]:
        """Вернуть только те дисциплины, в которых есть хотя бы одна тема."""
        return [
            d
            for d in self._catalog_service.list_disciplines()
            if self._catalog_service.list_topics(d.id)
        ]

    def _my_materials_flow(self) -> None:
        """Показать материалы, добавленные текущим пользователем."""
        materials = self._material_service.list_by_author(self._user)
        if not materials:
            print("Вы пока не добавили ни одного материала.")
            return
        self._presenter.print_materials(materials)

    def _create_material_flow(self) -> None:
        """Добавить новый материал."""
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
        self._io.header("Добавление материала")
        title = self._io.ask_text("Название: ", "Название", MAX_TITLE_LENGTH)
        description = self._io.ask_optional_text("Описание (Enter — пропустить): ") or ""
        discipline = self._picker.pick_discipline("Дисциплина: ", with_topics)
        topic = self._picker.pick_topic("Тема: ", self._catalog_service.list_topics(discipline.id))
        source_path = self._io.ask("Путь к файлу на компьютере: ", self._parse_source_file)
        material = self._material_service.create_material(
            self._user, title, description, discipline.id, topic.id, source_path
        )
        size = self._presenter.format_size(material.file_size_bytes)
        print(
            f"Материал создан, ID: {material.id} "
            f"(файл: {material.file_name}, {size}, формат {material.file_type.value})"
        )

    def _parse_source_file(self, raw: str) -> Path:
        """Разобрать путь к загружаемому файлу и проверить сам файл."""
        cleaned = self._clean_path(raw)
        if not cleaned:
            raise SourceFilePathRequiredError()
        path = Path(cleaned).expanduser()
        self._material_service.validate_source_file(path)
        return path

    @staticmethod
    def _parse_title(raw: str) -> str:
        """Разобрать название материала: непустое и не длиннее MAX_TITLE_LENGTH."""
        return require_text(raw, "Название", MAX_TITLE_LENGTH)

    def _edit_material_flow(self) -> None:
        """Изменить данные материала."""
        editable = self._material_service.list_editable(self._user)
        if not editable:
            if self._material_service.list_materials():
                print("У вас нет материалов для редактирования: можно менять только свои.")
            else:
                self._say_no_materials()
            return
        self._io.header("Редактирование материала (Enter — не менять)")
        material = self._picker.pick_material("ID материала: ", editable)
        print(
            f"Выбрано: «{material.title}» "
            f"({self._catalog_service.describe(material.discipline_id, material.topic_id)})"
        )
        title = self._io.ask("Новое название: ", OptionalParser(self._parse_title))
        description = self._io.ask_optional_text("Новое описание: ")

        new_discipline_id: int | None = None
        new_topic_id: int | None = None
        disciplines = self._disciplines_with_topics()
        if disciplines:
            discipline = self._picker.pick_optional_discipline("Новая дисциплина: ", disciplines)
            if discipline is not None:
                topic = self._picker.pick_topic(
                    "Тема новой дисциплины: ", self._catalog_service.list_topics(discipline.id)
                )
                new_discipline_id, new_topic_id = discipline.id, topic.id
            else:
                current_topics = self._catalog_service.list_topics(material.discipline_id)
                topic = self._picker.pick_optional_topic("Новая тема: ", current_topics)
                if topic is not None:
                    new_topic_id = topic.id

        if title is None and description is None and new_topic_id is None:
            print("Ничего не изменено.")
            return
        self._material_service.edit_material(
            self._user,
            material.id,
            title=title,
            description=description,
            discipline_id=new_discipline_id,
            topic_id=new_topic_id,
        )
        print("Материал обновлен.")

    def _delete_material_flow(self) -> None:
        """Удалить материал."""
        deletable = self._material_service.list_editable(self._user)
        if not deletable:
            if self._material_service.list_materials():
                print("У вас нет материалов для удаления: можно удалять только свои.")
            else:
                self._say_no_materials()
            return
        self._io.header("Удаление материала")
        material = self._picker.pick_material("ID материала: ", deletable)
        if not self._io.confirm(f"Удалить «{material.title}» без возможности восстановления?"):
            print("Удаление отменено.")
            return
        self._material_service.delete_material(self._user, material.id)
        print("Материал удален.")

    def _create_discipline_flow(self) -> None:
        """Добавить дисциплину."""
        self._io.header("Добавление дисциплины")
        disciplines = self._catalog_service.list_disciplines()
        if disciplines:
            print("Уже существуют: " + ", ".join(d.name for d in disciplines))
        name = self._io.ask(
            "Название дисциплины: ", self._catalog_service.ensure_discipline_name_free
        )
        self._catalog_service.create_discipline(self._user, name)
        print(f"Дисциплина «{name}» создана.")

    def _create_topic_flow(self) -> None:
        """Добавить тему в дисциплину."""
        disciplines = self._catalog_service.list_disciplines()
        if not disciplines:
            self._say_no_disciplines()
            return
        self._io.header("Добавление темы")
        discipline = self._picker.pick_discipline(
            "Дисциплина, к которой относится тема: ", disciplines
        )
        topics = self._catalog_service.list_topics(discipline.id)
        if topics:
            print("Уже есть темы: " + ", ".join(t.name for t in topics))
        name = self._io.ask(
            "Название темы: ",
            lambda raw: self._catalog_service.ensure_topic_name_free(discipline.id, raw),
        )
        self._catalog_service.create_topic(self._user, name, discipline.id)
        print(f"Тема «{name}» добавлена в дисциплину «{discipline.name}».")

    def _rename_discipline_flow(self) -> None:
        """Переименовать дисциплину."""
        disciplines = self._catalog_service.list_disciplines()
        if not disciplines:
            self._say_no_disciplines()
            return
        self._io.header("Переименование дисциплины")
        discipline = self._picker.pick_discipline("Какую дисциплину переименовать: ", disciplines)
        new_name = self._io.ask(
            "Новое название: ",
            lambda raw: self._catalog_service.validate_discipline_rename(discipline, raw),
        )
        old_name = discipline.name
        self._catalog_service.rename_discipline(self._user, discipline.id, new_name)
        print(f"Дисциплина «{old_name}» переименована в «{new_name}».")

    def _rename_topic_flow(self) -> None:
        """Переименовать тему."""
        disciplines = self._catalog_service.list_disciplines()
        if not disciplines:
            self._say_no_disciplines()
            return
        with_topics = self._disciplines_with_topics()
        if not with_topics:
            print("Ни в одной дисциплине пока нет тем — переименовывать нечего.")
            return
        self._io.header("Переименование темы")
        discipline = self._picker.pick_discipline(
            "Дисциплина, к которой относится тема: ", with_topics
        )
        topic = self._picker.pick_topic(
            "Какую тему переименовать: ", self._catalog_service.list_topics(discipline.id)
        )
        new_name = self._io.ask(
            "Новое название: ",
            lambda raw: self._catalog_service.validate_topic_rename(topic, raw),
        )
        old_name = topic.name
        self._catalog_service.rename_topic(self._user, topic.id, new_name)
        print(f"Тема «{old_name}» переименована в «{new_name}».")
