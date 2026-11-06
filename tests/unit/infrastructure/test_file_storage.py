"""Юнит-тесты локального файлового хранилища (во временной папке)."""

from __future__ import annotations

import pytest

from src.domain.exceptions import SourceFileNotFoundError
from src.storage.file_storage import LocalFileStorage


@pytest.fixture
def storage(tmp_path) -> LocalFileStorage:
    return LocalFileStorage(tmp_path / "root")


def _source(tmp_path, name="doc.pdf", content=b"data"):
    path = tmp_path / name
    path.write_bytes(content)
    return path


def test_root_is_created_with_parents(tmp_path):
    root = tmp_path / "a" / "b" / "c"
    LocalFileStorage(root)
    assert root.is_dir()


def test_existing_root_is_accepted(tmp_path):
    LocalFileStorage(tmp_path)
    LocalFileStorage(tmp_path)


def test_store_copies_content_and_reports_size(storage, tmp_path):
    stored = storage.store(_source(tmp_path, content=b"12345"))
    assert stored.size_bytes == 5
    assert stored.file_name == "doc.pdf"
    assert storage.resolve(stored.storage_path).read_bytes() == b"12345"


def test_empty_file_has_zero_size(storage, tmp_path):
    assert storage.store(_source(tmp_path, content=b"")).size_bytes == 0


def test_original_file_is_kept(storage, tmp_path):
    source = _source(tmp_path)
    storage.store(source)
    assert source.exists()


def test_same_name_is_stored_under_unique_paths(storage, tmp_path):
    source = _source(tmp_path)
    first = storage.store(source)
    second = storage.store(source)
    assert first.storage_path != second.storage_path
    assert storage.resolve(first.storage_path).exists()
    assert storage.resolve(second.storage_path).exists()


def test_stored_name_keeps_original_name_suffix(storage, tmp_path):
    stored = storage.store(_source(tmp_path, name="Лекция 1.docx"))
    assert stored.storage_path.endswith("_Лекция 1.docx")


def test_missing_source_raises(storage, tmp_path):
    with pytest.raises(SourceFileNotFoundError):
        storage.store(tmp_path / "missing.pdf")


def test_directory_as_source_raises(storage, tmp_path):
    with pytest.raises(SourceFileNotFoundError):
        storage.store(tmp_path)


def test_delete_removes_file(storage, tmp_path):
    stored = storage.store(_source(tmp_path))
    storage.delete(stored.storage_path)
    assert not storage.resolve(stored.storage_path).exists()


def test_delete_of_missing_file_is_not_an_error(storage, tmp_path):
    storage.delete(str(tmp_path / "nothing"))


def test_double_delete_is_not_an_error(storage, tmp_path):
    stored = storage.store(_source(tmp_path))
    storage.delete(stored.storage_path)
    storage.delete(stored.storage_path)
