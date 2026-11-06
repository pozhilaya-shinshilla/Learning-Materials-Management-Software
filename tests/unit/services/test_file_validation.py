"""Юнит-тесты цепочки проверки файлов: граничные размеры и расширения."""

from __future__ import annotations

import pytest

from src.configs.config import ALLOWED_FILE_TYPES, MAX_FILE_SIZE_BYTES
from src.domain.enums import FileType
from src.domain.exceptions import (
    FileTooLargeError,
    SourceFileNotFoundError,
    UnsupportedFileTypeError,
)
from src.services.file_validation import (
    FileCheck,
    FileExistsHandler,
    FileSizeHandler,
    FileTypeHandler,
    FileValidationHandler,
    build_file_validation_chain,
)


def _file(tmp_path, name="a.pdf", size=1):
    path = tmp_path / name
    path.write_bytes(b"x" * size)
    return path


class TestFileExistsHandler:
    def test_existing_file_passes(self, tmp_path):
        FileExistsHandler().handle(FileCheck(_file(tmp_path)))

    def test_missing_file(self, tmp_path):
        with pytest.raises(SourceFileNotFoundError):
            FileExistsHandler().handle(FileCheck(tmp_path / "none.pdf"))

    def test_directory_is_not_a_file(self, tmp_path):
        with pytest.raises(SourceFileNotFoundError):
            FileExistsHandler().handle(FileCheck(tmp_path))


class TestFileTypeHandler:
    @pytest.mark.parametrize("file_type", sorted(ALLOWED_FILE_TYPES))
    def test_each_allowed_type(self, tmp_path, file_type):
        path = _file(tmp_path, f"doc.{file_type.value}")
        check = FileTypeHandler(ALLOWED_FILE_TYPES).handle(FileCheck(path))
        assert check.file_type is file_type

    @pytest.mark.parametrize("name", ["a.PDF", "a.Pdf", "A.DOCX"])
    def test_extension_is_case_insensitive(self, tmp_path, name):
        FileTypeHandler(ALLOWED_FILE_TYPES).handle(FileCheck(_file(tmp_path, name)))

    @pytest.mark.parametrize(
        "name",
        ["a.exe", "a.txt", "a.pdf.exe", "a", "a.", ".pdf", "a.pdff", "a.p", "archive.tar.gz"],
    )
    def test_rejected_names(self, tmp_path, name):
        with pytest.raises(UnsupportedFileTypeError):
            FileTypeHandler(ALLOWED_FILE_TYPES).handle(FileCheck(_file(tmp_path, name)))

    def test_double_extension_uses_last_one(self, tmp_path):
        check = FileTypeHandler(ALLOWED_FILE_TYPES).handle(FileCheck(_file(tmp_path, "a.exe.pdf")))
        assert check.file_type is FileType.PDF

    def test_known_but_not_allowed_type(self, tmp_path):
        handler = FileTypeHandler({FileType.PDF})
        with pytest.raises(UnsupportedFileTypeError):
            handler.handle(FileCheck(_file(tmp_path, "a.png")))

    def test_message_mentions_extension_and_allowed(self, tmp_path):
        with pytest.raises(UnsupportedFileTypeError, match=r"\.exe.*pdf"):
            FileTypeHandler(ALLOWED_FILE_TYPES).handle(FileCheck(_file(tmp_path, "a.exe")))

    def test_message_for_missing_extension(self, tmp_path):
        with pytest.raises(UnsupportedFileTypeError, match="без расширения"):
            FileTypeHandler(ALLOWED_FILE_TYPES).handle(FileCheck(_file(tmp_path, "noext")))


class TestFileSizeHandler:
    @pytest.mark.parametrize(("size", "ok"), [(0, True), (9, True), (10, True), (11, False)])
    def test_boundary_around_limit(self, tmp_path, size, ok):
        handler = FileSizeHandler(10)
        check = FileCheck(_file(tmp_path, size=size))
        if ok:
            handler.handle(check)
        else:
            with pytest.raises(FileTooLargeError):
                handler.handle(check)

    def test_error_reports_limit_in_megabytes(self, tmp_path):
        with pytest.raises(FileTooLargeError, match="100"):
            FileSizeHandler(MAX_FILE_SIZE_BYTES).handle(
                FileCheck(_sparse(tmp_path, MAX_FILE_SIZE_BYTES + 1))
            )


def _sparse(tmp_path, size, name="big.pdf"):
    path = tmp_path / name
    with path.open("wb") as handle:
        handle.truncate(size)
    return path


class TestDefaultChain:
    def test_exactly_100_megabytes_is_accepted(self, tmp_path):
        chain = build_file_validation_chain(ALLOWED_FILE_TYPES, MAX_FILE_SIZE_BYTES)
        result = chain.handle(FileCheck(_sparse(tmp_path, MAX_FILE_SIZE_BYTES)))
        assert result.file_type is FileType.PDF

    def test_one_byte_over_100_megabytes_is_rejected(self, tmp_path):
        chain = build_file_validation_chain(ALLOWED_FILE_TYPES, MAX_FILE_SIZE_BYTES)
        with pytest.raises(FileTooLargeError):
            chain.handle(FileCheck(_sparse(tmp_path, MAX_FILE_SIZE_BYTES + 1)))

    def test_order_existence_before_type(self, tmp_path):
        chain = build_file_validation_chain(ALLOWED_FILE_TYPES, 10)
        with pytest.raises(SourceFileNotFoundError):
            chain.handle(FileCheck(tmp_path / "missing.exe"))

    def test_order_type_before_size(self, tmp_path):
        chain = build_file_validation_chain(ALLOWED_FILE_TYPES, 10)
        with pytest.raises(UnsupportedFileTypeError):
            chain.handle(FileCheck(_file(tmp_path, "big.exe", 100)))

    def test_valid_file_returns_detected_type(self, tmp_path):
        chain = build_file_validation_chain(ALLOWED_FILE_TYPES, 10)
        assert chain.handle(FileCheck(_file(tmp_path, "a.xlsx"))).file_type is FileType.XLSX


class TestChainMechanics:
    class Recorder(FileValidationHandler):
        def __init__(self, log, name, fail=False):
            super().__init__()
            self._log, self._name, self._fail = log, name, fail

        def _check(self, check):
            self._log.append(self._name)
            if self._fail:
                raise ValueError(self._name)

    def test_set_next_returns_next_handler(self):
        first, second = FileExistsHandler(), FileSizeHandler(1)
        assert first.set_next(second) is second

    def test_handlers_run_in_order(self, tmp_path):
        log: list[str] = []
        first = self.Recorder(log, "a")
        first.set_next(self.Recorder(log, "b")).set_next(self.Recorder(log, "c"))
        first.handle(FileCheck(tmp_path))
        assert log == ["a", "b", "c"]

    def test_failure_stops_the_chain(self, tmp_path):
        log: list[str] = []
        first = self.Recorder(log, "a")
        first.set_next(self.Recorder(log, "b", fail=True)).set_next(self.Recorder(log, "c"))
        with pytest.raises(ValueError):
            first.handle(FileCheck(tmp_path))
        assert log == ["a", "b"]

    def test_single_handler_chain(self, tmp_path):
        log: list[str] = []
        self.Recorder(log, "only").handle(FileCheck(tmp_path))
        assert log == ["only"]

    def test_handler_returns_the_check(self, tmp_path):
        check = FileCheck(tmp_path)
        assert self.Recorder([], "a").handle(check) is check
