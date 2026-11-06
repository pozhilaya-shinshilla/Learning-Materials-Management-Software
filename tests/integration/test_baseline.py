"""Тесты фиксируют поведение сервисов; они должны проходить до и после внедрения паттернов."""

from __future__ import annotations

import pytest

from src.configs.config import ALLOWED_FILE_TYPES
from src.domain.enums import SortField, SortOrder
from src.domain.exceptions import (
    AuthenticationError,
    FileTooLargeError,
    SourceFileNotFoundError,
    UnsupportedFileTypeError,
)
from src.services.file_validation import FileCheck, build_file_validation_chain
from src.services.search_service import MaterialFilter


@pytest.fixture
def material_setup(context, teacher, tmp_path):
    discipline = context.catalog_service.create_discipline(teacher, "Математика")
    topic = context.catalog_service.create_topic(teacher, "Алгебра", discipline.id)
    return discipline, topic


def _file(tmp_path, name="a.pdf", content=b"x"):
    path = tmp_path / name
    path.write_bytes(content)
    return path


def _create(context, teacher, setup, tmp_path, title, name="a.pdf"):
    discipline, topic = setup
    return context.material_service.create_material(
        teacher, title, "описание", discipline.id, topic.id, _file(tmp_path, name)
    )


def test_create_and_list(context, teacher, material_setup, tmp_path):
    material = _create(context, teacher, material_setup, tmp_path, "Лекция")
    assert [m.id for m in context.material_service.list_materials()] == [material.id]


def test_edit_visible_after_listing(context, teacher, material_setup, tmp_path):
    material = _create(context, teacher, material_setup, tmp_path, "Лекция")
    context.material_service.list_materials()
    context.material_service.edit_material(teacher, material.id, title="Новая")
    assert context.material_service.list_materials()[0].title == "Новая"


def test_delete_visible_after_listing(context, teacher, material_setup, tmp_path):
    material = _create(context, teacher, material_setup, tmp_path, "Лекция")
    context.material_service.list_materials()
    context.material_service.delete_material(teacher, material.id)
    assert context.material_service.list_materials() == []


@pytest.mark.parametrize(
    ("name", "error"),
    [("a.exe", UnsupportedFileTypeError), ("noext", UnsupportedFileTypeError)],
)
def test_unsupported_type(context, teacher, material_setup, tmp_path, name, error):
    discipline, topic = material_setup
    with pytest.raises(error):
        context.material_service.create_material(
            teacher, "T", "", discipline.id, topic.id, _file(tmp_path, name)
        )


def test_missing_file(context, tmp_path):
    with pytest.raises(SourceFileNotFoundError):
        context.material_service.validate_source_file(tmp_path / "nope.pdf")


def test_too_large(tmp_path):
    chain = build_file_validation_chain(ALLOWED_FILE_TYPES, 1)
    with pytest.raises(FileTooLargeError):
        chain.handle(FileCheck(_file(tmp_path, "b.pdf", b"xx")))


def test_sort_by_title(context, teacher, material_setup, tmp_path):
    _create(context, teacher, material_setup, tmp_path, "Бета", "b.pdf")
    _create(context, teacher, material_setup, tmp_path, "Альфа", "a.pdf")
    asc = context.search_service.search(
        None, sort_field=SortField.TITLE, sort_order=SortOrder.ASCENDING
    )
    assert [m.title for m in asc] == ["Альфа", "Бета"]
    desc = context.search_service.search(
        None, sort_field=SortField.TITLE, sort_order=SortOrder.DESCENDING
    )
    assert [m.title for m in desc] == ["Бета", "Альфа"]


def test_sort_by_date(context, teacher, material_setup, tmp_path):
    first = _create(context, teacher, material_setup, tmp_path, "Первый", "a.pdf")
    second = _create(context, teacher, material_setup, tmp_path, "Второй", "b.pdf")
    desc = context.search_service.search()
    assert [m.id for m in desc] == [second.id, first.id]


@pytest.mark.db  # морфологию русского языка выполняет PostgreSQL
def test_filter_query(context, teacher, material_setup, tmp_path):
    _create(context, teacher, material_setup, tmp_path, "Линейные уравнения", "a.pdf")
    _create(context, teacher, material_setup, tmp_path, "Геометрия", "b.pdf")
    found = context.search_service.search(MaterialFilter(query="уравнение"))
    assert [m.title for m in found] == ["Линейные уравнения"]


def test_login_events(context):
    with pytest.raises(AuthenticationError):
        context.auth_service.login("admin", "wrong-password")
    context.auth_service.login("admin", "Admin12345!")
