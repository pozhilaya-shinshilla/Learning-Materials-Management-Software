"""Избранные материалы текущего пользователя."""

from __future__ import annotations

from fastapi import APIRouter, Response, status

from src.api.assemblers import material_responses
from src.api.dependencies import ContextDep, CurrentUser
from src.api.errors import ERROR_RESPONSES
from src.api.params import MaterialId
from src.dtos.responses import FavoriteResponse, MaterialResponse

router = APIRouter(
    prefix="/api/favorites",
    tags=["Избранное"],
    responses={401: ERROR_RESPONSES[401], 403: ERROR_RESPONSES[403]},
)


@router.get("", response_model=list[MaterialResponse], summary="Избранные материалы")
def list_favorites(user: CurrentUser, context: ContextDep) -> list[MaterialResponse]:
    """Вернуть материалы, добавленные текущим пользователем в избранное."""
    return material_responses(context, context.favorite_service.list_favorites(user))


@router.post(
    "/{material_id}",
    response_model=FavoriteResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Добавить материал в избранное",
    responses={404: ERROR_RESPONSES[404], 409: ERROR_RESPONSES[409]},
)
def add_favorite(
    material_id: MaterialId, user: CurrentUser, context: ContextDep
) -> FavoriteResponse:
    """Добавить материал в избранное."""
    return FavoriteResponse.from_domain(context.favorite_service.add_favorite(user, material_id))


@router.delete(
    "/{material_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Убрать материал из избранного",
    responses={404: ERROR_RESPONSES[404]},
)
def remove_favorite(material_id: MaterialId, user: CurrentUser, context: ContextDep) -> Response:
    """Убрать материал из избранного."""
    context.favorite_service.remove_favorite(user, material_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
