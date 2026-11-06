"""Учебные материалы: список с поиском, карточка, загрузка, правка, удаление, скачивание."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse
from pydantic import ValidationError as PydanticValidationError

from src.api.assemblers import material_response, material_responses
from src.api.dependencies import ContextDep, CurrentUser, get_current_user
from src.api.errors import ERROR_RESPONSES
from src.api.params import MaterialId
from src.api.uploads import saved_upload
from src.domain.exceptions import MaterialFileNotStoredError
from src.domain.validation import MAX_TITLE_LENGTH
from src.dtos.requests import (
    MAX_DESCRIPTION_LENGTH,
    MAX_ID,
    MaterialCreateRequest,
    MaterialListQuery,
    MaterialUpdateRequest,
)
from src.dtos.responses import MaterialResponse
from src.services.search_service import MaterialFilter, MaterialFilterBuilder

TOTAL_COUNT_HEADER = "X-Total-Count"

router = APIRouter(
    prefix="/api/materials",
    tags=["Учебные материалы"],
    responses={401: ERROR_RESPONSES[401], 403: ERROR_RESPONSES[403]},
)


def material_create_form(
    title: Annotated[
        str,
        Form(
            min_length=1,
            max_length=MAX_TITLE_LENGTH,
            description="Название материала",
            examples=["Лекция 1. Пределы"],
        ),
    ],
    discipline_id: Annotated[
        int, Form(gt=0, le=MAX_ID, description="Номер дисциплины", examples=[3])
    ],
    topic_id: Annotated[
        int,
        Form(
            gt=0,
            le=MAX_ID,
            description="Номер темы (должна принадлежать этой дисциплине)",
            examples=[7],
        ),
    ],
    description: Annotated[
        str,
        Form(
            max_length=MAX_DESCRIPTION_LENGTH,
            description="Описание материала (необязательно)",
            examples=["Определение предела последовательности и функции."],
        ),
    ] = "",
) -> MaterialCreateRequest:
    """Собрать `MaterialCreateRequest` из полей формы.

    FastAPI не умеет получать Pydantic-модель формы вместе с загружаемым файлом,
    поэтому поля читаются по отдельности, а DTO собирается из них.
    """
    try:
        return MaterialCreateRequest(
            title=title, description=description, discipline_id=discipline_id, topic_id=topic_id
        )
    except PydanticValidationError as error:
        # Ошибки собственных проверок DTO отдаём тем же 422, что и ошибки полей формы.
        issues = [{**issue, "loc": ("body", *issue["loc"])} for issue in error.errors()]
        raise RequestValidationError(issues) from error


def _to_filter(query: MaterialListQuery) -> MaterialFilter:
    """Собрать фильтр поиска из параметров запроса (паттерн «Строитель»)."""
    return (
        MaterialFilterBuilder()
        .with_query(query.q)
        .in_discipline(query.discipline_id)
        .in_topic(query.topic_id)
        .of_type(query.file_type)
        .uploaded_between(query.uploaded_from, query.uploaded_to)
        .build()
    )


@router.get(
    "",
    response_model=list[MaterialResponse],
    summary="Список материалов с поиском, фильтрами и сортировкой",
    dependencies=[Depends(get_current_user)],
)
def list_materials(
    query: Annotated[MaterialListQuery, Query()], context: ContextDep, response: Response
) -> list[MaterialResponse]:
    """Вернуть материалы, подходящие под запрос (поиск учитывает морфологию русского языка).

    С параметром `limit` возвращается одна страница, а заголовок `X-Total-Count` содержит
    общее число подходящих материалов; без `limit` — все материалы.
    """
    criteria = _to_filter(query)
    if query.limit is None:
        found = context.search_service.search(criteria, query.sort_by, query.order)
        response.headers[TOTAL_COUNT_HEADER] = str(len(found))
    else:
        found, total = context.search_service.search_page(
            criteria, query.sort_by, query.order, limit=query.limit, offset=query.offset
        )
        response.headers[TOTAL_COUNT_HEADER] = str(total)
    return material_responses(context, found)


@router.get(
    "/{material_id}",
    response_model=MaterialResponse,
    summary="Сведения о материале",
    dependencies=[Depends(get_current_user)],
    responses={404: ERROR_RESPONSES[404]},
)
def get_material(material_id: MaterialId, context: ContextDep) -> MaterialResponse:
    """Вернуть карточку материала."""
    return material_response(context, context.material_service.get_material(material_id))


@router.post(
    "",
    response_model=MaterialResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Создание материала с загрузкой файла",
    responses={
        403: ERROR_RESPONSES[403],
        404: ERROR_RESPONSES[404],
        413: ERROR_RESPONSES[413],
        415: ERROR_RESPONSES[415],
    },
)
def create_material(
    form: Annotated[MaterialCreateRequest, Depends(material_create_form)],
    file: Annotated[
        UploadFile,
        File(
            description="Файл: PDF, DOCX, PPTX, XLSX, JPG (JPEG) или PNG, до 100 МБ",
            examples=["lecture1.pdf"],
        ),
    ],
    user: CurrentUser,
    context: ContextDep,
) -> MaterialResponse:
    """Создать материал (преподаватель или администратор) и сохранить файл."""
    with saved_upload(file) as path:
        created = context.material_service.create_material(
            user, form.title, form.description, form.discipline_id, form.topic_id, path
        )
    return material_response(context, created)


@router.patch(
    "/{material_id}",
    response_model=MaterialResponse,
    summary="Частичное изменение материала",
    responses={403: ERROR_RESPONSES[403], 404: ERROR_RESPONSES[404]},
)
def update_material(
    material_id: MaterialId, body: MaterialUpdateRequest, user: CurrentUser, context: ContextDep
) -> MaterialResponse:
    """Изменить данные материала; повторная загрузка файла не требуется."""
    updated = context.material_service.edit_material(
        user,
        material_id,
        title=body.title,
        description=body.description,
        discipline_id=body.discipline_id,
        topic_id=body.topic_id,
    )
    return material_response(context, updated)


@router.delete(
    "/{material_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Удаление материала",
    responses={403: ERROR_RESPONSES[403], 404: ERROR_RESPONSES[404]},
)
def delete_material(material_id: MaterialId, user: CurrentUser, context: ContextDep) -> Response:
    """Удалить материал вместе с файлом."""
    context.material_service.delete_material(user, material_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/{material_id}/download",
    summary="Скачивание файла материала",
    response_class=FileResponse,
    responses={404: ERROR_RESPONSES[404]},
)
def download_material(
    material_id: MaterialId, user: CurrentUser, context: ContextDep
) -> FileResponse:
    """Отдать файл материала и записать скачивание в журнал."""
    material = context.material_service.get_material(material_id)
    path = context.material_service.resolve_file_path(material_id)
    if not path.is_file():
        raise MaterialFileNotStoredError()
    context.material_service.record_download(user, material_id)
    return FileResponse(path, filename=material.file_name)
