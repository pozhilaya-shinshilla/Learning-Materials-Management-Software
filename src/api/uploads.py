"""Адаптер (Adapter): приводит `UploadFile` из HTTP к пути на диске, которого ждёт сервис.

`MaterialService.create_material` принимает путь к локальному файлу (так он работает и в CLI),
а HTTP отдаёт поток байт. Адаптер сохраняет поток во временную папку под исходным именем
(расширение определяет тип файла) и убирает её после операции. Размер ограничен на лету:
сервер не станет записывать на диск гигабайты, чтобы потом отклонить файл.
"""

from __future__ import annotations

import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from fastapi import UploadFile

from src.configs.config import MAX_FILE_SIZE_BYTES
from src.domain.exceptions import (
    FieldTooLongError,
    FileTooLargeError,
    InvalidFileNameError,
    SourceFilePathRequiredError,
)

_CHUNK_BYTES = 1024 * 1024
# Имя хранится в БД в поле на 255 символов, а файловая система считает байты, а не символы.
MAX_FILE_NAME_LENGTH = 200


@contextmanager
def saved_upload(upload: UploadFile) -> Iterator[Path]:
    """Сохранить загруженный файл во временную папку и отдать путь к нему."""
    name = Path((upload.filename or "").replace("\\", "/")).name
    if not name or name in {".", ".."}:
        raise SourceFilePathRequiredError()
    if "\x00" in name:
        raise InvalidFileNameError()
    if len(name) > MAX_FILE_NAME_LENGTH:
        raise FieldTooLongError(field_name="Имя файла", max_length=MAX_FILE_NAME_LENGTH)
    with tempfile.TemporaryDirectory(prefix="lms-upload-") as folder:
        target = Path(folder) / name
        written = 0
        with target.open("wb") as out:
            while chunk := upload.file.read(_CHUNK_BYTES):
                written += len(chunk)
                if written > MAX_FILE_SIZE_BYTES:
                    raise FileTooLargeError(max_mb=MAX_FILE_SIZE_BYTES // (1024 * 1024))
                out.write(chunk)
        yield target
