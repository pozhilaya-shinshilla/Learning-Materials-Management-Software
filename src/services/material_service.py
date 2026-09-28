from __future__ import annotations

from pathlib import Path

from src.config import ALLOWED_FILE_TYPES, MAX_FILE_SIZE_BYTES
from src.domain.enums import EventType, FileType, Role
from src.domain.exceptions import (
    AuthorizationError,
    EntityNotFoundError,
    FileTooLargeError,
    UnsupportedFileTypeError,
    ValidationError,
)
from src.domain.models import Material, User
from src.repositories.interfaces import MaterialRepository
from src.services.event_log_service import EventLogService
from src.storage.file_storage import FileStorage

_MATERIAL_MANAGER_ROLES = frozenset({Role.TEACHER, Role.ADMIN})


class MaterialService:
    """Creates, edits, deletes and lists teaching materials."""

    def __init__(
        self,
        material_repository: MaterialRepository,
        event_log_service: EventLogService,
        file_storage: FileStorage,
    ) -> None:
        self._material_repository = material_repository
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
        if not title:
            raise ValidationError("Название материала обязательно.")
        file_type = self._detect_file_type(source_file_path)
        self._validate_file_size(source_file_path)
        stored = self._file_storage.store(source_file_path)
        material = Material(
            id=0,
            title=title,
            description=description,
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
            material.title = title
        if description is not None:
            material.description = description
        if discipline_id is not None:
            material.discipline_id = discipline_id
        if topic_id is not None:
            material.topic_id = topic_id
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
            raise EntityNotFoundError(f"Материал с id {material_id} не найден.")
        return material

    def _detect_file_type(self, source_file_path: Path) -> FileType:
        extension = source_file_path.suffix.lstrip(".").lower()
        try:
            file_type = FileType(extension)
        except ValueError as error:
            allowed = ", ".join(t.value for t in ALLOWED_FILE_TYPES)
            raise UnsupportedFileTypeError(
                f"Формат '.{extension}' не поддерживается. Допустимые форматы: {allowed}."
            ) from error
        if file_type not in ALLOWED_FILE_TYPES:
            allowed = ", ".join(t.value for t in ALLOWED_FILE_TYPES)
            raise UnsupportedFileTypeError(
                f"Формат '.{extension}' не поддерживается. Допустимые форматы: {allowed}."
            )
        return file_type

    def _validate_file_size(self, source_file_path: Path) -> None:
        if not source_file_path.is_file():
            return
        if source_file_path.stat().st_size > MAX_FILE_SIZE_BYTES:
            max_mb = MAX_FILE_SIZE_BYTES // (1024 * 1024)
            raise FileTooLargeError(f"Файл превышает максимально допустимый размер {max_mb} МБ.")

    def _require_material_manager(self, user: User) -> None:
        if user.role not in _MATERIAL_MANAGER_ROLES:
            raise AuthorizationError(
                "Только преподаватели и администраторы могут управлять материалами."
            )

    def _require_ownership(self, user: User, material: Material) -> None:
        self._require_material_manager(user)
        if user.role is Role.TEACHER and material.author_id != user.id:
            raise AuthorizationError("Преподаватель может изменять только свои материалы.")
