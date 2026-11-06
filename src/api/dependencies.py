"""Зависимости FastAPI (`Depends`): сборка приложения, текущий пользователь, проверка роли.

Роутеры не создают сервисы сами и не знают, откуда они взялись: они просят их через `Depends`
(внедрение зависимостей, Dependency Injection). В тестах достаточно передать в `create_app`
другой `ApplicationContext`, а роутеры останутся прежними.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.bootstrap import ApplicationContext
from src.domain.enums import Role
from src.domain.exceptions import AuthorizationError, NotAuthenticatedError
from src.domain.models import User

bearer_scheme = HTTPBearer(
    auto_error=False,
    description="Токен из `POST /api/auth/login` (в Swagger UI: кнопка Authorize).",
)


def get_context(request: Request) -> ApplicationContext:
    """Вернуть собранное приложение (сервисы), лежащее в состоянии `app.state`."""
    context: ApplicationContext = request.app.state.context
    return context


ContextDep = Annotated[ApplicationContext, Depends(get_context)]


def get_token(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> str:
    """Достать токен из заголовка `Authorization: Bearer ...` или ответить 401."""
    if credentials is None:
        raise NotAuthenticatedError()
    return credentials.credentials


TokenDep = Annotated[str, Depends(get_token)]


def get_current_user(token: TokenDep, context: ContextDep) -> User:
    """Вернуть актуального пользователя по токену (роль и блокировка читаются из БД)."""
    return context.session_service.authenticate(token)


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_roles(*roles: Role) -> Callable[[User], User]:
    """Создать зависимость, пропускающую только пользователей с одной из перечисленных ролей."""

    def checker(user: CurrentUser) -> User:
        if user.role not in roles:
            raise AuthorizationError()
        return user

    return checker


AdminUser = Annotated[User, Depends(require_roles(Role.ADMIN))]
