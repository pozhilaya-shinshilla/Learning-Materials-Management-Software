"""Дисциплины учебного каталога."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response, status

from src.api.dependencies import ContextDep, CurrentUser, get_current_user
from src.api.errors import ERROR_RESPONSES
from src.api.params import DisciplineId
from src.dtos.requests import DisciplineCreateRequest, DisciplineUpdateRequest
from src.dtos.responses import DisciplineResponse

router = APIRouter(
    prefix="/api/disciplines",
    tags=["Дисциплины"],
    responses={401: ERROR_RESPONSES[401], 403: ERROR_RESPONSES[403]},
)


@router.get(
    "",
    response_model=list[DisciplineResponse],
    summary="Список дисциплин",
    dependencies=[Depends(get_current_user)],
)
def list_disciplines(context: ContextDep) -> list[DisciplineResponse]:
    """Вернуть все дисциплины."""
    return [DisciplineResponse.from_domain(d) for d in context.catalog_service.list_disciplines()]


@router.get(
    "/{discipline_id}",
    response_model=DisciplineResponse,
    summary="Сведения о дисциплине",
    dependencies=[Depends(get_current_user)],
    responses={404: ERROR_RESPONSES[404]},
)
def get_discipline(discipline_id: DisciplineId, context: ContextDep) -> DisciplineResponse:
    """Вернуть дисциплину по id."""
    return DisciplineResponse.from_domain(context.catalog_service.get_discipline(discipline_id))


@router.post(
    "",
    response_model=DisciplineResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Создание дисциплины",
    responses={403: ERROR_RESPONSES[403], 409: ERROR_RESPONSES[409]},
)
def create_discipline(
    body: DisciplineCreateRequest, user: CurrentUser, context: ContextDep
) -> DisciplineResponse:
    """Создать дисциплину (преподаватель или администратор)."""
    return DisciplineResponse.from_domain(
        context.catalog_service.create_discipline(user, body.name)
    )


@router.patch(
    "/{discipline_id}",
    response_model=DisciplineResponse,
    summary="Частичное изменение дисциплины",
    responses={403: ERROR_RESPONSES[403], 404: ERROR_RESPONSES[404], 409: ERROR_RESPONSES[409]},
)
def update_discipline(
    discipline_id: DisciplineId,
    body: DisciplineUpdateRequest,
    user: CurrentUser,
    context: ContextDep,
) -> DisciplineResponse:
    """Переименовать дисциплину (преподаватель или администратор)."""
    if body.name is None:
        return DisciplineResponse.from_domain(context.catalog_service.get_discipline(discipline_id))
    renamed = context.catalog_service.rename_discipline(user, discipline_id, body.name)
    return DisciplineResponse.from_domain(renamed)


@router.delete(
    "/{discipline_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Удаление дисциплины",
    responses={403: ERROR_RESPONSES[403], 404: ERROR_RESPONSES[404], 409: ERROR_RESPONSES[409]},
)
def delete_discipline(
    discipline_id: DisciplineId, user: CurrentUser, context: ContextDep
) -> Response:
    """Удалить дисциплину без тем (преподаватель или администратор); с темами — 409."""
    context.catalog_service.delete_discipline(user, discipline_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
