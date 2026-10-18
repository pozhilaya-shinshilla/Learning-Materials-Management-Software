from __future__ import annotations

import shutil
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from src.domain.exceptions import SourceFileNotFoundError


@dataclass
class StoredFile:
    """Результат сохранения загруженного файла: где он лежит и какого он размера."""

    storage_path: str
    file_name: str
    size_bytes: int


class FileStorage(ABC):
    """Контракт сохранения и получения содержимого файлов материалов."""

    @abstractmethod
    def store(self, source_path: Path) -> StoredFile:
        """Скопировать файл в хранилище и вернуть сведения о нём."""

    @abstractmethod
    def resolve(self, storage_path: str) -> Path:
        """Вернуть путь в файловой системе к ранее сохранённому файлу."""

    @abstractmethod
    def delete(self, storage_path: str) -> None:
        """Удалить ранее сохранённый файл; отсутствие файла не считается ошибкой."""


class LocalFileStorage(FileStorage):
    """Хранит файлы в локальной папке, каждый под уникальным сгенерированным именем."""

    def __init__(self, root: Path) -> None:
        self._root = root
        self._root.mkdir(parents=True, exist_ok=True)

    def store(self, source_path: Path) -> StoredFile:
        """Скопировать файл в хранилище и вернуть сведения о нём."""
        if not source_path.is_file():
            raise SourceFileNotFoundError(path=source_path)
        stored_name = f"{uuid4().hex}_{source_path.name}"
        destination = self._root / stored_name
        shutil.copyfile(source_path, destination)
        return StoredFile(
            storage_path=str(destination),
            file_name=source_path.name,
            size_bytes=destination.stat().st_size,
        )

    def resolve(self, storage_path: str) -> Path:
        """Вернуть путь в файловой системе к ранее сохранённому файлу."""
        return Path(storage_path)

    def delete(self, storage_path: str) -> None:
        """Удалить ранее сохранённый файл; отсутствие файла не считается ошибкой."""
        Path(storage_path).unlink(missing_ok=True)
