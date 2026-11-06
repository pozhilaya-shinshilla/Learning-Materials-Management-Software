"""Цепочка обязанностей (Chain of Responsibility): проверки файла перед загрузкой.

Каждое звено проверяет одно условие и передаёт файл дальше; первое же нарушение
прерывает цепочку исключением. Новое правило (например, проверка имени) — это
новое звено, а `MaterialService` при этом не меняется.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Collection
from dataclasses import dataclass
from pathlib import Path

from src.domain.enums import FileType
from src.domain.exceptions import (
    FileTooLargeError,
    SourceFileNotFoundError,
    UnsupportedFileTypeError,
)

# Другие написания расширений одного формата: `.jpeg` — тот же JPEG, что и `.jpg`.
_EXTENSION_ALIASES: dict[str, str] = {"jpeg": "jpg"}


@dataclass
class FileCheck:
    """Проверяемый файл и результат, который звенья накапливают по ходу цепочки."""

    path: Path
    file_type: FileType | None = None


class FileValidationHandler(ABC):
    """Звено цепочки: выполняет свою проверку и передаёт файл следующему звену."""

    def __init__(self) -> None:
        """Создать звено без продолжения."""
        self._next: FileValidationHandler | None = None

    def set_next(self, handler: FileValidationHandler) -> FileValidationHandler:
        """Назначить следующее звено и вернуть его, чтобы звенья можно было соединять в строку."""
        self._next = handler
        return handler

    def handle(self, check: FileCheck) -> FileCheck:
        """Проверить файл этим звеном, затем передать дальше; ошибка прерывает цепочку."""
        self._check(check)
        if self._next is not None:
            return self._next.handle(check)
        return check

    @abstractmethod
    def _check(self, check: FileCheck) -> None:
        """Проверить файл; при нарушении выбросить исключение предметной области."""


class FileExistsHandler(FileValidationHandler):
    """Файл должен существовать на диске."""

    def _check(self, check: FileCheck) -> None:
        """Выбросить ошибку, если по пути нет файла."""
        if not check.path.is_file():
            raise SourceFileNotFoundError(path=check.path)


class FileTypeHandler(FileValidationHandler):
    """Расширение файла должно входить в список разрешённых; определяет `file_type`."""

    def __init__(self, allowed_types: Collection[FileType]) -> None:
        """Запомнить разрешённые типы файлов."""
        super().__init__()
        self._allowed_types = frozenset(allowed_types)

    def _check(self, check: FileCheck) -> None:
        """Определить тип по расширению и убедиться, что он разрешён."""
        extension = check.path.suffix.lstrip(".").lower()
        extension = _EXTENSION_ALIASES.get(extension, extension)
        try:
            file_type = FileType(extension)
        except ValueError:
            file_type = None
        if file_type is None or file_type not in self._allowed_types:
            allowed = ", ".join(sorted(t.value for t in self._allowed_types))
            shown = f"'.{extension}'" if extension else "без расширения"
            raise UnsupportedFileTypeError(shown=shown, allowed=allowed)
        check.file_type = file_type


class FileSizeHandler(FileValidationHandler):
    """Размер файла не должен превышать максимум."""

    def __init__(self, max_size_bytes: int) -> None:
        """Запомнить предельный размер в байтах."""
        super().__init__()
        self._max_size_bytes = max_size_bytes

    def _check(self, check: FileCheck) -> None:
        """Выбросить ошибку, если файл больше допустимого."""
        if check.path.stat().st_size > self._max_size_bytes:
            raise FileTooLargeError(max_mb=self._max_size_bytes // (1024 * 1024))


def build_file_validation_chain(
    allowed_types: Collection[FileType], max_size_bytes: int
) -> FileValidationHandler:
    """Собрать стандартную цепочку: существование → тип → размер; вернуть её первое звено."""
    first = FileExistsHandler()
    first.set_next(FileTypeHandler(allowed_types)).set_next(FileSizeHandler(max_size_bytes))
    return first
