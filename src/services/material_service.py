from __future__ import annotations

from functools import partial
from pathlib import Path
from typing import cast

from src.configs.config import ALLOWED_FILE_TYPES, MAX_FILE_SIZE_BYTES
from src.domain.enums import EventType, FileType, Role
from src.domain.exceptions import (
    DisciplineDoesNotExistError,
    ForeignMaterialAccessError,
    MaterialAccessError,
    MaterialFileNotStoredError,
    MaterialNotFoundError,
    NothingToUndoError,
    TopicDisciplineMismatchError,
    TopicDoesNotExistError,
)
from src.domain.models import Material, User
from src.domain.validation import MAX_TITLE_LENGTH, require_text
from src.repositories.interfaces import (
    DisciplineRepository,
    MaterialRepository,
    MaterialRevisionRepository,
    TopicRepository,
)
from src.services.event_log_service import EventLogService
from src.services.file_validation import (
    FileCheck,
    FileValidationHandler,
    build_file_validation_chain,
)
from src.services.transaction_hooks import ImmediateHooks, TransactionHooks
from src.storage.file_storage import FileStorage

_MATERIAL_MANAGER_ROLES = frozenset({Role.TEACHER, Role.ADMIN})


class MaterialService:
    """Создаёт, изменяет, удаляет и выдаёт списком учебные материалы."""

    def __init__(
        self,
        material_repository: MaterialRepository,
        discipline_repository: DisciplineRepository,
        topic_repository: TopicRepository,
        revision_repository: MaterialRevisionRepository,
        event_log_service: EventLogService,
        file_storage: FileStorage,
        file_validator: FileValidationHandler | None = None,
        transaction_hooks: TransactionHooks | None = None,
    ) -> None:
        """Принять хранилища, журнал событий, файловое хранилище и цепочку проверки файлов.

        `revision_repository` хранит снимки материалов для отмены правок (в БД, не в памяти).
        `transaction_hooks` привязывает операции с файлами к исходу транзакции: файл удаляется
        после фиксации, а копия при откате убирается.
        """
        self._material_repository = material_repository
        self._discipline_repository = discipline_repository
        self._topic_repository = topic_repository
        self._event_log_service = event_log_service
        self._file_storage = file_storage
        self._revision_repository = revision_repository
        self._file_validator = file_validator or build_file_validation_chain(
            ALLOWED_FILE_TYPES, MAX_FILE_SIZE_BYTES
        )
        self._hooks = transaction_hooks or ImmediateHooks()

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

        Файл копируется сразу (его путь и размер нужны для строки в БД), поэтому на случай отката
        транзакции копия заранее ставится на удаление: «сирота» без строки в БД не остаётся.
        """
        self._require_material_manager(author)
        title = require_text(title, "Название", MAX_TITLE_LENGTH)
        self._validate_classification(discipline_id, topic_id)
        file_type = self.validate_source_file(source_file_path)
        stored = self._file_storage.store(source_file_path)
        self._hooks.on_rollback(partial(self._file_storage.delete, stored.storage_path))
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
        """Изменить данные материала, не требуя нового файла.

        Все новые значения сначала вычисляются и проверяются, и только потом
        присваиваются: при ошибке проверки материал остаётся прежним.
        """
        material = self._get_existing_material(material_id, for_update=True, acting_user=editor)
        self._require_ownership(editor, material)
        new_title = (
            material.title if title is None else require_text(title, "Название", MAX_TITLE_LENGTH)
        )
        new_description = material.description if description is None else description.strip()
        new_discipline_id = material.discipline_id if discipline_id is None else discipline_id
        new_topic_id = material.topic_id if topic_id is None else topic_id

        if discipline_id is not None or topic_id is not None:
            self._validate_classification(new_discipline_id, new_topic_id)

        self._revision_repository.push(material.id, material.create_memento())
        material.title = new_title
        material.description = new_description
        material.discipline_id = new_discipline_id
        material.topic_id = new_topic_id
        self._material_repository.update(material)
        self._event_log_service.record(editor.id, EventType.MATERIAL_EDITED, material.title)
        return material

    def undo_last_edit(self, editor: User, material_id: int) -> Material:
        """Отменить последнее изменение материала, вернув его прежние данные."""
        material = self._get_existing_material(material_id, for_update=True, acting_user=editor)
        self._require_ownership(editor, material)
        memento = self._revision_repository.pop(material_id)
        if memento is None:
            raise NothingToUndoError()
        material.restore(memento)
        self._material_repository.update(material)
        self._event_log_service.record(editor.id, EventType.MATERIAL_EDIT_UNDONE, material.title)
        return material

    def can_undo(self, material_id: int) -> bool:
        """Вернуть, есть ли у материала изменения, которые можно отменить."""
        return self._revision_repository.has_history(material_id)

    def delete_material(self, remover: User, material_id: int) -> None:
        """Удалить материал; его файл удаляется после фиксации транзакции.

        Если удалять файл сразу, а фиксация не пройдёт, строка в БД останется без файла.
        Обратный сбой безвреден: файл без строки лишь занимает место.
        """
        material = self._get_existing_material(material_id, for_update=True, acting_user=remover)
        self._require_ownership(remover, material)
        self._material_repository.delete(material_id)
        if material.storage_path:
            self._hooks.on_commit(partial(self._file_storage.delete, material.storage_path))
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

    def _get_existing_material(
        self, material_id: int, *, for_update: bool = False, acting_user: User | None = None
    ) -> Material:
        """Вернуть материал или выбросить ошибку, если его нет.

        `for_update=True` блокирует строку до конца транзакции. Так делают все операции,
        которые читают материал, чтобы потом его менять: правку, отмену правки и удаление.
        Две такие операции над одним материалом выполняются по очереди, и вторая видит
        результат первой: снимок для отмены берётся с настоящего прежнего состояния, один
        снимок не достают дважды, а правка удалённого материала даёт `MaterialNotFoundError`,
        а не молчаливый успех.

        `acting_user` — кто меняет материал. Его строку и строку автора хранилище блокирует
        раньше строки материала: удаление пользователя идёт в том же порядке (пользователь, затем
        его материалы), и встречных ожиданий, которые PostgreSQL разрывает как взаимную
        блокировку, не возникает. Если пользователя уже удалили, это `AccountDeletedError`.
        """
        if for_update:
            material = self._material_repository.get_by_id_for_update(
                material_id, acting_user_id=None if acting_user is None else acting_user.id
            )
        else:
            material = self._material_repository.get_by_id(material_id)
        if material is None:
            raise MaterialNotFoundError(material_id=material_id)
        return material

    def validate_source_file(self, source_file_path: Path) -> FileType:
        """Проверить, что локальный файл существует, имеет разрешённый тип и не слишком большой.

        Возвращает определённый тип файла. Интерфейс вызывает метод сразу после
        ввода пути, чтобы неверный путь можно было переспросить немедленно.
        """
        checked = self._file_validator.handle(FileCheck(source_file_path))
        return cast(FileType, checked.file_type)

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
