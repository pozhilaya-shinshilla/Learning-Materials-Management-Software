"""Аутентификация: вход, выход и восстановление пароля."""

from __future__ import annotations

from fastapi import APIRouter, status

from src.api.dependencies import ContextDep, CurrentUser, TokenDep
from src.api.errors import ERROR_RESPONSES
from src.dtos.requests import LoginRequest, PasswordRecoveryRequest, PasswordResetRequest
from src.dtos.responses import MessageResponse, TokenResponse, UserResponse

router = APIRouter(prefix="/api/auth", tags=["Аутентификация"])


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Вход по логину и паролю",
    responses={401: ERROR_RESPONSES[401], 403: ERROR_RESPONSES[403]},
)
def login(body: LoginRequest, context: ContextDep) -> TokenResponse:
    """Проверить учётные данные и выдать токен доступа."""
    opened = context.session_service.open_session(body.login, body.password)
    return TokenResponse(
        access_token=opened.token,
        expires_at=opened.expires_at,
        user=UserResponse.from_domain(opened.user),
    )


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Текущий пользователь",
    responses={401: ERROR_RESPONSES[401], 403: ERROR_RESPONSES[403]},
)
def current_user(user: CurrentUser) -> UserResponse:
    """Вернуть учётную запись по токену: актуальные роль и статус (читаются из БД)."""
    return UserResponse.from_domain(user)


@router.post(
    "/logout",
    response_model=MessageResponse,
    summary="Выход из системы",
    responses={401: ERROR_RESPONSES[401], 403: ERROR_RESPONSES[403]},
)
def logout(token: TokenDep, context: ContextDep) -> MessageResponse:
    """Отозвать токен: после выхода он перестаёт действовать."""
    context.session_service.close_session(token)
    return MessageResponse(detail="Выход выполнен.")


@router.post(
    "/password/recovery",
    response_model=MessageResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Запрос кода восстановления пароля по e-mail",
)
def request_password_recovery(
    body: PasswordRecoveryRequest, context: ContextDep
) -> MessageResponse:
    """Отправить на e-mail код восстановления.

    Ответ одинаков, есть такая учётная запись или нет: по нему нельзя узнать,
    какие адреса зарегистрированы.
    """
    context.auth_service.request_password_reset(body.email)
    return MessageResponse(detail="Если такой адрес зарегистрирован, на него отправлен код.")


@router.post(
    "/password/reset",
    response_model=MessageResponse,
    summary="Установка нового пароля по коду из письма",
    responses={401: ERROR_RESPONSES[401]},
)
def reset_password(body: PasswordResetRequest, context: ContextDep) -> MessageResponse:
    """Сменить пароль по коду восстановления (код одноразовый и с ограниченным сроком)."""
    context.auth_service.reset_password_with_token(body.token, body.new_password)
    return MessageResponse(detail="Пароль изменён.")
