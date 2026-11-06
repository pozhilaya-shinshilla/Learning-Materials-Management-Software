"""Перевод ошибок предметной области в HTTP-ответы.

Сервисы выбрасывают `DomainError` и ничего не знают об HTTP. Здесь для каждого семейства
ошибок задан статус ответа; тело всегда одно: `{"detail": "<текст>", "code": "<ИмяКласса>"}`.
Статус выбирается по ближайшему предку класса ошибки, поэтому новая ошибка получает
правильный статус без правок: достаточно унаследовать её от подходящей базовой.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence

import psycopg
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import DBAPIError, IntegrityError, SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

from src.domain.exceptions import (
    AccountBlockedError,
    AuthenticationError,
    AuthorizationError,
    DatabaseSchemaError,
    DatabaseSettingsError,
    DomainError,
    DuplicateEntityError,
    EntityInUseError,
    EntityNotFoundError,
    FileTooLargeError,
    SmtpSettingsError,
    TimezoneSettingsError,
    UnsupportedFileTypeError,
    ValidationError,
)
from src.dtos.responses import ErrorResponse, ValidationErrorResponse, ValidationIssue

logger = logging.getLogger(__name__)

# Порядок не важен: проход идёт по цепочке предков ошибки (MRO), от ближайшего к дальнему.
_STATUS_BY_ERROR: dict[type[DomainError], int] = {
    FileTooLargeError: 413,
    UnsupportedFileTypeError: 415,
    AuthenticationError: 401,
    AccountBlockedError: 403,
    AuthorizationError: 403,
    EntityNotFoundError: 404,
    DuplicateEntityError: 409,
    EntityInUseError: 409,
    ValidationError: 422,
    DatabaseSchemaError: 500,
    DatabaseSettingsError: 500,
    SmtpSettingsError: 500,
    TimezoneSettingsError: 500,
    DomainError: 400,
}

ERROR_RESPONSES: dict[int | str, dict[str, object]] = {
    400: {"model": ErrorResponse, "description": "Запрос нельзя выполнить (общая ошибка правил)"},
    401: {"model": ErrorResponse, "description": "Нет входа или токен недействителен"},
    403: {
        "model": ErrorResponse,
        "description": "Недостаточно прав или учётная запись заблокирована",
    },
    404: {"model": ErrorResponse, "description": "Объект не найден"},
    409: {"model": ErrorResponse, "description": "Такой объект уже существует или используется"},
    413: {"model": ErrorResponse, "description": "Файл больше 100 МБ"},
    415: {"model": ErrorResponse, "description": "Формат файла не поддерживается"},
    422: {"model": ValidationErrorResponse, "description": "Данные не прошли проверку"},
    500: {"model": ErrorResponse, "description": "Непредвиденная ошибка сервера"},
    503: {"model": ErrorResponse, "description": "База данных временно недоступна"},
}

# Ответы, которые возможны у любого метода: подключаются ко всему приложению (см. `create_app`).
COMMON_RESPONSES: dict[int | str, dict[str, object]] = {
    400: ERROR_RESPONSES[400],
    422: ERROR_RESPONSES[422],
    500: ERROR_RESPONSES[500],
    503: ERROR_RESPONSES[503],
}


def status_for(error: DomainError) -> int:
    """Вернуть HTTP-статус для ошибки предметной области."""
    for cls in type(error).__mro__:
        status = _STATUS_BY_ERROR.get(cls)  # type: ignore[arg-type]
        if status is not None:
            return status
    return 400


async def _handle_domain_error(_request: Request, error: Exception) -> JSONResponse:
    """Превратить `DomainError` в JSON с подходящим статусом."""
    assert isinstance(error, DomainError)
    status = status_for(error)
    headers = {"WWW-Authenticate": "Bearer"} if status == 401 else None
    body = ErrorResponse(detail=str(error), code=type(error).__name__)
    return JSONResponse(status_code=status, content=body.model_dump(), headers=headers)


_VALIDATION_TEXTS: dict[str, str] = {
    "missing": "обязательное поле не указано",
    "extra_forbidden": "такого поля нет в запросе",
    "string_too_short": "слишком короткое значение (минимум символов: {min_length})",
    "string_too_long": "слишком длинное значение (максимум символов: {max_length})",
    "string_type": "нужна строка",
    "int_type": "нужно целое число",
    "int_parsing": "нужно целое число",
    "int_from_float": "нужно целое число",
    "greater_than": "значение должно быть больше {gt}",
    "greater_than_equal": "значение должно быть не меньше {ge}",
    "less_than": "значение должно быть меньше {lt}",
    "less_than_equal": "значение должно быть не больше {le}",
    "date_parsing": "нужна дата в формате ГГГГ-ММ-ДД",
    "date_from_datetime_parsing": "нужна дата в формате ГГГГ-ММ-ДД",
    "date_type": "нужна дата в формате ГГГГ-ММ-ДД",
    "json_invalid": "тело запроса не является корректным JSON",
    "model_attributes_type": "тело запроса должно быть объектом",
    "dict_type": "тело запроса должно быть объектом",
    "bool_parsing": "нужно значение true или false",
    "bool_type": "нужно значение true или false",
    "missing_argument": "обязательный параметр не указан",
    "bytes_type": "нужен файл",
    "url_parsing": "некорректный адрес",
}


def _enum_text(context: dict[str, object] | None) -> str:
    """Перечислить допустимые значения перечисления."""
    expected = (context or {}).get("expected")
    return f"допустимые значения: {expected}" if expected else "недопустимое значение"


def _issue_text(issue: dict[str, object]) -> str:
    """Человекочитаемый текст одной ошибки проверки данных."""
    kind = str(issue.get("type", ""))
    context = issue.get("ctx")
    context = context if isinstance(context, dict) else {}
    if kind == "enum":
        return _enum_text(context)
    if kind == "value_error":
        # Собственные проверки пишут русский текст; убираем служебный префикс Pydantic.
        return str(issue.get("msg", "")).removeprefix("Value error, ") or "недопустимое значение"
    template = _VALIDATION_TEXTS.get(kind)
    if template is None:
        return "недопустимое значение"
    try:
        return template.format(**context)
    except (KeyError, IndexError):
        return template.split(" (")[0]


def _field_name(location: Sequence[object]) -> str:
    """Имя поля из пути ошибки: без служебных `body`, `query`, `path`."""
    parts = [str(part) for part in location if part not in ("body", "query", "path", "form")]
    return ".".join(parts)


async def _handle_validation_error(_request: Request, error: Exception) -> JSONResponse:
    """422: данные запроса не прошли проверку; `detail` — текст, `errors` — разбор по полям."""
    assert isinstance(error, RequestValidationError)
    issues = [
        ValidationIssue(
            loc=[str(part) for part in item.get("loc", ())],
            field=_field_name(item.get("loc", ())),
            message=_issue_text(item),  # type: ignore[arg-type]
            type=str(item.get("type", "")),
        )
        for item in error.errors()
    ]
    lines = [
        f"{issue.field}: {issue.message}" if issue.field else issue.message for issue in issues
    ]
    body = ValidationErrorResponse(
        detail="Данные не прошли проверку: " + "; ".join(lines) + "."
        if lines
        else "Данные не прошли проверку.",
        code="RequestValidationError",
        errors=issues,
    )
    return JSONResponse(status_code=422, content=body.model_dump())


_HTTP_TEXTS: dict[int, str] = {
    400: "Некорректный запрос.",
    401: "Войдите в систему.",
    403: "Недостаточно прав.",
    404: "Такого адреса нет.",
    405: "Метод не поддерживается для этого адреса.",
    413: "Слишком большой запрос.",
    415: "Неподдерживаемый тип содержимого.",
    429: "Слишком много запросов. Повторите позже.",
}


async def _handle_http_error(_request: Request, error: Exception) -> JSONResponse:
    """Ошибки самого HTTP (нет маршрута, неверный метод и т. п.) в том же виде `{detail, code}`."""
    assert isinstance(error, StarletteHTTPException)
    detail = error.detail if isinstance(error.detail, str) and error.detail else ""
    if detail in ("", "Not Found", "Method Not Allowed", "Forbidden", "Unauthorized"):
        detail = _HTTP_TEXTS.get(error.status_code, "Запрос не выполнен.")
    body = ErrorResponse(detail=detail, code="HttpError")
    return JSONResponse(
        status_code=error.status_code,
        content=body.model_dump(),
        headers=dict(error.headers) if error.headers else None,
    )


async def _handle_database_error(_request: Request, error: Exception) -> JSONResponse:
    """Сбой базы данных: недоступность — 503, отказ данных (длина, диапазон) — 422."""
    assert isinstance(error, SQLAlchemyError)
    if isinstance(error, DBAPIError) and isinstance(error.orig, psycopg.errors.DataError):
        logger.warning("База отклонила значение: %s", error)
        body = ErrorResponse(detail="Значение не подходит для хранения.", code="DataError")
        return JSONResponse(status_code=422, content=body.model_dump())
    if isinstance(error, IntegrityError):
        logger.warning("Нарушено ограничение БД: %s", error)
        body = ErrorResponse(
            detail="Операция противоречит данным в системе. Обновите страницу и повторите.",
            code="IntegrityError",
        )
        return JSONResponse(status_code=409, content=body.model_dump())
    logger.error("База данных недоступна: %s", error)
    body = ErrorResponse(
        detail="База данных временно недоступна. Повторите запрос позже.",
        code="DatabaseUnavailable",
    )
    return JSONResponse(status_code=503, content=body.model_dump(), headers={"Retry-After": "5"})


async def _handle_unexpected_error(_request: Request, error: Exception) -> JSONResponse:
    """Последний рубеж: любая непредвиденная ошибка — JSON с понятным текстом, без трассировки."""
    logger.exception("Непредвиденная ошибка при обработке запроса", exc_info=error)
    body = ErrorResponse(
        detail="Внутренняя ошибка сервера. Мы уже знаем о ней; повторите попытку позже.",
        code="InternalError",
    )
    return JSONResponse(status_code=500, content=body.model_dump())


def register_exception_handlers(app: FastAPI) -> None:
    """Подключить глобальные обработчики: любая ошибка станет JSON `{detail, code}`."""
    app.add_exception_handler(DomainError, _handle_domain_error)
    app.add_exception_handler(RequestValidationError, _handle_validation_error)
    app.add_exception_handler(StarletteHTTPException, _handle_http_error)
    app.add_exception_handler(SQLAlchemyError, _handle_database_error)
    app.add_exception_handler(Exception, _handle_unexpected_error)
