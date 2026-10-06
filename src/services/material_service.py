from __future__ import annotations

from pathlib import Path

from src.config import ALLOWED_FILE_TYPES, MAX_FILE_SIZE_BYTES
from src.domain.enums import EventType, FileType, Role
from src.domain.exceptions import (
    AuthorizationError,
    EntityNotFoundError,
    FileTooLargeError,
    SourceFileNotFoundError,
    UnsupportedFileTypeError,
    ValidationError,
)
from src.domain.models import Material, User
from src.domain.validation import MAX_TITLE_LENGTH, require_text
from src.repositories.interfaces import DisciplineRepository, MaterialRepository, TopicRepository
from src.services.event_log_service import EventLogService
from src.storage.file_storage import FileStorage

_MATERIAL_MANAGER_ROLES = frozenset({Role.TEACHER, Role.ADMIN})


class MaterialService:
    """Creates, edits, deletes and lists teaching materials."""

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
        """Add a new material: validates metadata, then uploads the given local file.

        The file's type is detected from its extension and its size is read
        from disk, so the caller never supplies them manually.
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
        """Update a material's metadata without requiring a new file."""
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
        """Remove a material and its stored file."""
        material = self._get_existing_material(material_id)
        self._require_ownership(remover, material)
        self._material_repository.delete(material_id)
        if material.storage_path:
            self._file_storage.delete(material.storage_path)
        self._event_log_service.record(remover.id, EventType.MATERIAL_DELETED, material.title)

    def list_materials(self) -> list[Material]:
        """Return every material in the catalog."""
        return self._material_repository.list_all()

    def list_editable(self, user: User) -> list[Material]:
        """Return the materials this user may edit or delete.

        Administrators manage every material; teachers only their own; students none.
        """
        if user.role is Role.ADMIN:
            return self._material_repository.list_all()
        if user.role is Role.TEACHER:
            return [m for m in self._material_repository.list_all() if m.author_id == user.id]
        return []

    def get_material(self, material_id: int) -> Material:
        """Return a single material by id."""
        return self._get_existing_material(material_id)

    def resolve_file_path(self, material_id: int) -> Path:
        """Return a readable local path to the material's stored file."""
        material = self._get_existing_material(material_id)
        if not material.storage_path:
            raise EntityNotFoundError("Для этого материала не сохранен файл.")
        return self._file_storage.resolve(material.storage_path)

    def record_download(self, downloader: User, material_id: int) -> None:
        """Log that a user downloaded a material's file."""
        material = self._get_existing_material(material_id)
        self._event_log_service.record(downloader.id, EventType.MATERIAL_DOWNLOADED, material.title)

    def _get_existing_material(self, material_id: int) -> Material:
        material = self._material_repository.get_by_id(material_id)
        if material is None:
            raise EntityNotFoundError(f"Материал с ID {material_id} не найден.")
        return material

    def validate_source_file(self, source_file_path: Path) -> FileType:
        """Check that the local file exists, has an allowed type and fits the size limit.

        Returns the detected file type. Interfaces call this right after the user
        types a path, so a bad path can be re-asked immediately.
        """
        if not source_file_path.is_file():
            raise SourceFileNotFoundError(f"Файл не найден: {source_file_path}")
        file_type = self._detect_file_type(source_file_path)
        if source_file_path.stat().st_size > MAX_FILE_SIZE_BYTES:
            max_mb = MAX_FILE_SIZE_BYTES // (1024 * 1024)
            raise FileTooLargeError(f"Файл превышает максимально допустимый размер {max_mb} МБ.")
        return file_type

    def _detect_file_type(self, source_file_path: Path) -> FileType:
        extension = source_file_path.suffix.lstrip(".").lower()
        try:
            file_type = FileType(extension)
        except ValueError:
            file_type = None
        if file_type is None or file_type not in ALLOWED_FILE_TYPES:
            allowed = ", ".join(sorted(t.value for t in ALLOWED_FILE_TYPES))
            shown = f"'.{extension}'" if extension else "без расширения"
            raise UnsupportedFileTypeError(
                f"Формат {shown} не поддерживается. Допустимые форматы: {allowed}."
            )
        return file_type

    def _validate_classification(self, discipline_id: int, topic_id: int) -> None:
        if self._discipline_repository.get_by_id(discipline_id) is None:
            raise ValidationError("Указанная дисциплина не существует.")
        topic = self._topic_repository.get_by_id(topic_id)
        if topic is None:
            raise ValidationError("Указанная тема не существует.")
        if topic.discipline_id != discipline_id:
            raise ValidationError("Тема не относится к выбранной дисциплине.")

    def _require_material_manager(self, user: User) -> None:
        if user.role not in _MATERIAL_MANAGER_ROLES:
            raise AuthorizationError(
                "Только преподаватели и администраторы могут управлять материалами."
            )

    def _require_ownership(self, user: User, material: Material) -> None:
        self._require_material_manager(user)
        if user.role is Role.TEACHER and material.author_id != user.id:
            raise AuthorizationError("Преподаватель может изменять только свои материалы.")
