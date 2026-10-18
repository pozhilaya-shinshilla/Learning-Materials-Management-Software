"""Проверка и разбор вводимых значений.

Все функции чистые: получают строку, возвращают готовое значение или
выбрасывают подкласс `ValidationError` с понятным пользователю сообщением. Благодаря
этому одни и те же правила используются и сервисами (последний рубеж защиты),
и интерфейсом (чтобы сразу переспросить поле, не отбрасывая пользователя назад).
"""

from __future__ import annotations

import re
from collections.abc import Callable
from datetime import date, datetime

from src.domain.enums import FileType, Role, SortField, SortOrder
from src.domain.exceptions import (
    EmptyFieldError,
    FieldTooLongError,
    InvalidDateError,
    InvalidEmailError,
    InvalidLoginError,
    InvalidYesNoError,
    LoginRequiredError,
    NotPositiveIntegerError,
    PasswordRequiredError,
    PasswordTooShortError,
    UnknownFileTypeError,
    UnknownRoleError,
    UnknownSortOptionError,
)

_LOGIN_PATTERN = re.compile(r"^[A-Za-z0-9_-]{3,32}$")
_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MIN_PASSWORD_LENGTH = 8
MAX_NAME_LENGTH = 100
MAX_TITLE_LENGTH = 200

_DATE_FORMATS = ("%d.%m.%Y", "%Y-%m-%d")

# Варианты сортировки списка материалов: (подпись, поле, направление).
SORT_OPTIONS: tuple[tuple[str, SortField, SortOrder], ...] = (
    ("по дате загрузки — сначала новые", SortField.UPLOAD_DATE, SortOrder.DESCENDING),
    ("по дате загрузки — сначала старые", SortField.UPLOAD_DATE, SortOrder.ASCENDING),
    ("по названию — от А до Я", SortField.TITLE, SortOrder.ASCENDING),
    ("по названию — от Я до А", SortField.TITLE, SortOrder.DESCENDING),
)

_ROLE_SHORTCUTS: dict[str, Role] = {"s": Role.STUDENT, "t": Role.TEACHER, "a": Role.ADMIN}
_YES = frozenset({"y", "yes", "д", "да"})
_NO = frozenset({"n", "no", "н", "нет"})


# --- учётные данные ---------------------------------------------------------


def validate_login(login: str) -> None:
    """Логин: 3-32 символа, латинские буквы, цифры, '_' или '-'."""
    if not _LOGIN_PATTERN.match(login):
        raise InvalidLoginError()


def validate_email(email: str) -> None:
    """Email должен выглядеть как local@domain.tld."""
    if not _EMAIL_PATTERN.match(email):
        raise InvalidEmailError()


def validate_password(plain_password: str) -> None:
    """Пароль не короче MIN_PASSWORD_LENGTH символов."""
    if len(plain_password) < MIN_PASSWORD_LENGTH:
        raise PasswordTooShortError(min_length=MIN_PASSWORD_LENGTH)


def validate_credentials_present(login: str, plain_password: str) -> None:
    """При входе оба поля обязательны (длину пароля при входе не проверяем)."""
    if not login.strip():
        raise LoginRequiredError()
    validate_login(login.strip())
    if not plain_password:
        raise PasswordRequiredError()


# --- текстовые поля ---------------------------------------------------------


def require_text(raw: str, field_name: str, max_length: int = MAX_NAME_LENGTH) -> str:
    """Вернуть строку без крайних пробелов; она не должна быть пустой или слишком длинной."""
    value = raw.strip()
    if not value:
        raise EmptyFieldError(field_name=field_name)
    if len(value) > max_length:
        raise FieldTooLongError(field_name=field_name, max_length=max_length)
    return value


# --- разбор значений из строки ----------------------------------------------


def parse_positive_int(raw: str) -> int:
    """Разобрать положительное целое число."""
    value = raw.strip()
    if not value.isdecimal() or int(value) < 1:
        raise NotPositiveIntegerError()
    return int(value)


def parse_yes_no(raw: str) -> bool:
    """Разобрать ответ «да/нет» (y/n, yes/no, д/н, да/нет)."""
    value = raw.strip().lower()
    if value in _YES:
        return True
    if value in _NO:
        return False
    raise InvalidYesNoError()


def role_hint() -> str:
    """Подсказка по допустимым вариантам роли, например 'student/s, teacher/t, admin/a'."""
    return ", ".join(f"{role.value}/{letter}" for letter, role in _ROLE_SHORTCUTS.items())


def parse_role(raw: str) -> Role:
    """Разобрать роль по полному названию или первой букве."""
    value = raw.strip().lower()
    if value in _ROLE_SHORTCUTS:
        return _ROLE_SHORTCUTS[value]
    try:
        return Role(value)
    except ValueError as error:
        raise UnknownRoleError(allowed=role_hint()) from error


def parse_file_type(raw: str) -> FileType:
    """Разобрать формат файла: 'pdf', '.pdf', 'PDF'."""
    value = raw.strip().lower().lstrip(".")
    try:
        return FileType(value)
    except ValueError as error:
        allowed = ", ".join(t.value for t in FileType)
        raise UnknownFileTypeError(allowed=allowed) from error


def parse_date(raw: str) -> date:
    """Разобрать дату в формате ДД.ММ.ГГГГ (допустим и ГГГГ-ММ-ДД)."""
    value = raw.strip()
    for date_format in _DATE_FORMATS:
        try:
            return datetime.strptime(value, date_format).date()
        except ValueError:
            continue
    raise InvalidDateError()


def parse_sort_option(raw: str) -> tuple[SortField, SortOrder]:
    """Разобрать номер варианта из SORT_OPTIONS; пустой ввод — первый вариант."""
    value = raw.strip()
    if not value:
        return SORT_OPTIONS[0][1], SORT_OPTIONS[0][2]
    if not value.isdecimal() or not 1 <= int(value) <= len(SORT_OPTIONS):
        raise UnknownSortOptionError(count=len(SORT_OPTIONS))
    _label, field, order = SORT_OPTIONS[int(value) - 1]
    return field, order


def optional[T](parser: Callable[[str], T]) -> Callable[[str], T | None]:
    """Сделать поле необязательным: пустая строка даёт None, остальное разбирает parser.

    Неверное значение по-прежнему вызывает ошибку проверки, то есть его не
    «молча игнорируют», а переспрашивают.
    """

    def parse(raw: str) -> T | None:
        if not raw.strip():
            return None
        return parser(raw)

    return parse
