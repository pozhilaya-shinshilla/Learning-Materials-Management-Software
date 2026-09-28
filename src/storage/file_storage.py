from __future__ import annotations

import shutil
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from src.domain.exceptions import SourceFileNotFoundError


@dataclass
class StoredFile:
    """Result of persisting an uploaded file: where it now lives and its size."""

    storage_path: str
    file_name: str
    size_bytes: int


class FileStorage(ABC):
    """Contract for saving and retrieving the binary content of materials."""

    @abstractmethod
    def store(self, source_path: Path) -> StoredFile:
        """Copy the file at source_path into storage and return its record."""

    @abstractmethod
    def resolve(self, storage_path: str) -> Path:
        """Return a readable filesystem path for a previously stored file."""

    @abstractmethod
    def delete(self, storage_path: str) -> None:
        """Remove a previously stored file, ignoring a missing file."""


class LocalFileStorage(FileStorage):
    """Stores files under a local directory, each under a unique generated name."""

    def __init__(self, root: Path) -> None:
        self._root = root
        self._root.mkdir(parents=True, exist_ok=True)

    def store(self, source_path: Path) -> StoredFile:
        """Copy the file at source_path into storage and return its record."""
        if not source_path.is_file():
            raise SourceFileNotFoundError(f"Файл не найден: {source_path}")
        stored_name = f"{uuid4().hex}_{source_path.name}"
        destination = self._root / stored_name
        shutil.copyfile(source_path, destination)
        return StoredFile(
            storage_path=str(destination),
            file_name=source_path.name,
            size_bytes=destination.stat().st_size,
        )

    def resolve(self, storage_path: str) -> Path:
        """Return a readable filesystem path for a previously stored file."""
        return Path(storage_path)

    def delete(self, storage_path: str) -> None:
        """Remove a previously stored file, ignoring a missing file."""
        Path(storage_path).unlink(missing_ok=True)
