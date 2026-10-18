from __future__ import annotations

from pathlib import Path

from src.config import ALLOWED_FILE_TYPES, MAX_FILE_SIZE_BYTES
from src.domain.enums import EventType, FileType, Role
from src.domain.exceptions import (
    DisciplineDoesNotExistError,
    FileTooLargeError,
    ForeignMaterialAccessError,
    MaterialAccessError,
    MaterialFileNotStoredError,
    MaterialNotFoundError,
    SourceFileNotFoundError,
    TopicDisciplineMismatchError,
    TopicDoesNotExistError,
    UnsupportedFileTypeError,
)
from src.domain.models import Material, User
from src.domain.validation import MAX_TITLE_LENGTH, require_text
from src.repositories.interfaces import DisciplineRepository, MaterialRepository, TopicRepository
from src.services.event_log_service import EventLogService
from src.storage.file_storage import FileStorage

_MATERIAL_MANAGER_ROLES = frozenset({Role.TEACHER, Role.ADMIN})


class MaterialService:
    """Создаёт, изменяет, удаляет и выдаёт списком учебные материалы."""

    def __init__(
        self,
        material_repository: MaterialRepository,
        discipline_repository: DisciplineRepository,
        topic_repository: TopicRepository,
        event_log_service: EventLogService,
        file_storage: FileStorage,
    ) -> None:
        self._material_repository = material_repository
        self._discipline_repository = discipline_repository
        self._topic_repository = topic_repository
        self._event_log_service = event_log_service
        self._file_storage = file_storage

    def create_material(
        self,
        author: User,
        title: str,
        description: str,
        discipline_id: int,
        topic_id: int,
        source_file_path: Path,
    ) -> Material:
        """Добавить материал: проверить данные, затем загрузить локальный файл.

        Тип файла определяется по расширению, а размер читается с диска,
        поэтому вызывающему коду не нужно передавать их вручную.
        """
        self._require_material_manager(author)
        title = require_text(title, "Название", MAX_TITLE_LENGTH)
        self._validate_classification(discipline_id, topic_id)
        file_type = self.validate_source_file(source_file_path)
        stored = self._file_storage.store(source_file_path)
        material = Material(
            id=0,
            title=title,
            description=description.strip(),
            discipline_id=discipline_id,
            topic_id=topic_id,
            file_name=stored.file_name,
            file_type=file_type,
            file_size_bytes=stored.size_bytes,
            author_id=author.id,
            storage_path=stored.storage_path,
        )
        created = self._material_repository.add(material)
        self._event_log_service.record(author.id, EventType.MATERIAL_CREATED, created.title)
        self._event_log_service.record(author.id, EventType.FILE_UPLOADED, created.file_name)
        return created

    def edit_material(
        self,
        editor: User,
        material_id: int,
        title: str | None = None,
        description: str | None = None,
        discipline_id: int | None = None,
        topic_id: int | None = None,
    ) -> Material:
        """Изменить данные материала, не требуя нового файла."""
        material = self._get_existing_material(material_id)
        self._require_ownership(editor, material)
        if title is not None:
            material.title = require_text(title, "Название", MAX_TITLE_LENGTH)
        if description is not None:
            material.description = description.strip()
        if discipline_id is not None or topic_id is not None:
            new_discipline_id = (
                discipline_id if discipline_id is not None else material.discipline_id
            )
            new_topic_id = topic_id if topic_id is not None else material.topic_id
            self._validate_classification(new_discipline_id, new_topic_id)
            material.discipline_id = new_discipline_id
            material.topic_id = new_topic_id
        self._material_repository.update(material)
        self._event_log_service.record(editor.id, EventType.MATERIAL_EDITED, material.title)
        return material

    def delete_material(self, remover: User, material_id: int) -> None:
        """Удалить материал и его сохранённый файл."""
        material = self._get_existing_material(material_id)
        self._require_ownership(remover, material)
        self._material_repository.delete(material_id)
        if material.storage_path:
            self._file_storage.delete(material.storage_path)
        self._event_log_service.record(remover.id, EventType.MATERIAL_DELETED, material.title)

    def list_materials(self) -> list[Material]:
        """Вернуть все материалы каталога."""
        return self._material_repository.list_all()

    def list_by_author(self, author: User) -> list[Material]:
        """Вернуть материалы, добавленные указанным пользователем."""
        return [m for m in self._material_repository.list_all() if m.author_id == author.id]

    def list_editable(self, user: User) -> list[Material]:
        """Вернуть материалы, которые пользователь может изменять или удалять.

        Администратор управляет всеми материалами, преподаватель — только своими,
        студент — никакими.
        """
        if user.role is Role.ADMIN:
            return self._material_repository.list_all()
        if user.role is Role.TEACHER:
            return [m for m in self._material_repository.list_all() if m.author_id == user.id]
        return []

    def get_material(self, material_id: int) -> Material:
        """Вернуть материал по id."""
        return self._get_existing_material(material_id)

    def resolve_file_path(self, material_id: int) -> Path:
        """Вернуть локальный путь к сохранённому файлу материала."""
        material = self._get_existing_material(material_id)
        if not material.storage_path:
            raise MaterialFileNotStoredError()
        return self._file_storage.resolve(material.storage_path)

    def record_download(self, downloader: User, material_id: int) -> None:
        """Записать в журнал, что пользователь скачал файл материала."""
        material = self._get_existing_material(material_id)
        self._event_log_service.record(downloader.id, EventType.MATERIAL_DOWNLOADED, material.title)

    def _get_existing_material(self, material_id: int) -> Material:
        """Вернуть материал или выбросить ошибку, если его нет."""
        material = self._material_repository.get_by_id(material_id)
        if material is None:
            raise MaterialNotFoundError(material_id=material_id)
        return material

    def validate_source_file(self, source_file_path: Path) -> FileType:
        """Проверить, что локальный файл существует, имеет разрешённый тип и не слишком большой.

        Возвращает определённый тип файла. Интерфейс вызывает метод сразу после
        ввода пути, чтобы неверный путь можно было переспросить немедленно.
        """
        if not source_file_path.is_file():
            raise SourceFileNotFoundError(path=source_file_path)
        file_type = self._detect_file_type(source_file_path)
        if source_file_path.stat().st_size > MAX_FILE_SIZE_BYTES:
            max_mb = MAX_FILE_SIZE_BYTES // (1024 * 1024)
            raise FileTooLargeError(max_mb=max_mb)
        return file_type

    def _detect_file_type(self, source_file_path: Path) -> FileType:
        """Определить тип файла по расширению и убедиться, что он разрешён."""
        extension = source_file_path.suffix.lstrip(".").lower()
        try:
            file_type = FileType(extension)
        except ValueError:
            file_type = None
        if file_type is None or file_type not in ALLOWED_FILE_TYPES:
            allowed = ", ".join(sorted(t.value for t in ALLOWED_FILE_TYPES))
            shown = f"'.{extension}'" if extension else "без расширения"
            raise UnsupportedFileTypeError(shown=shown, allowed=allowed)
        return file_type

    def _validate_classification(self, discipline_id: int, topic_id: int) -> None:
        """Проверить, что дисциплина и тема существуют и тема относится к дисциплине."""
        if self._discipline_repository.get_by_id(discipline_id) is None:
            raise DisciplineDoesNotExistError()
        topic = self._topic_repository.get_by_id(topic_id)
        if topic is None:
            raise TopicDoesNotExistError()
        if topic.discipline_id != discipline_id:
            raise TopicDisciplineMismatchError()

    def _require_material_manager(self, user: User) -> None:
        """Пропустить только преподавателя или администратора."""
        if user.role not in _MATERIAL_MANAGER_ROLES:
            raise MaterialAccessError()

    def _require_ownership(self, user: User, material: Material) -> None:
        """Проверить, что пользователь вправе менять именно этот материал."""
        self._require_material_manager(user)
        if user.role is Role.TEACHER and material.author_id != user.id:
            raise ForeignMaterialAccessError()
