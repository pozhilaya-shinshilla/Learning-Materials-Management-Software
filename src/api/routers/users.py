"""Управление учётными записями (только администратор)."""

from __future__ import annotations

from fastapi import APIRouter, Response, status

from src.api.dependencies import AdminUser, ContextDep
from src.api.errors import ERROR_RESPONSES
from src.api.params import UserId
from src.domain.enums import AccountStatus
from src.dtos.requests import UserCreateRequest, UserUpdateRequest
from src.dtos.responses import UserResponse

router = APIRouter(
    prefix="/api/users",
    tags=["Пользователи"],
    responses={401: ERROR_RESPONSES[401], 403: ERROR_RESPONSES[403]},
)


@router.get("", response_model=list[UserResponse], summary="Список пользователей")
def list_users(admin: AdminUser, context: ContextDep) -> list[UserResponse]:
    """Вернуть все учётные записи."""
    return [UserResponse.from_domain(u) for u in context.user_management_service.list_users(admin)]


@router.post(
    "",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Создание учётной записи",
    responses={409: ERROR_RESPONSES[409]},
)
def create_user(body: UserCreateRequest, admin: AdminUser, context: ContextDep) -> UserResponse:
    """Создать учётную запись: регистрация выполняется только администратором."""
    created = context.user_management_service.create_user(
        admin, body.login, body.email, body.password, body.role
    )
    return UserResponse.from_domain(created)


@router.patch(
    "/{user_id}",
    response_model=UserResponse,
    summary="Частичное изменение учётной записи (роль, блокировка)",
    responses={404: ERROR_RESPONSES[404]},
)
def update_user(
    user_id: UserId, body: UserUpdateRequest, admin: AdminUser, context: ContextDep
) -> UserResponse:
    """Изменить роль и/или заблокировать (`blocked`) либо разблокировать (`active`) запись."""
    blocked = None if body.status is None else body.status is AccountStatus.BLOCKED
    updated = context.user_management_service.update_user(
        admin, user_id, role=body.role, blocked=blocked
    )
    return UserResponse.from_domain(updated)


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Удаление учётной записи",
    responses={404: ERROR_RESPONSES[404]},
)
def delete_user(user_id: UserId, admin: AdminUser, context: ContextDep) -> Response:
    """Удалить учётную запись."""
    context.user_management_service.delete_user(admin, user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
