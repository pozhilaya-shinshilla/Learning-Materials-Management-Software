"""Проверка и разбор вводимых значений.

Все функции чистые: получают строку, возвращают готовое значение или
выбрасывают `ValidationError` с понятным пользователю сообщением. Благодаря
этому одни и те же правила используются и сервисами (последний рубеж защиты),
и интерфейсом (чтобы сразу переспросить поле, не отбрасывая пользователя назад).
"""

from __future__ import annotations

import re
from collections.abc import Callable

from src.domain.enums import FileType, Role
from src.domain.exceptions import ValidationError

_LOGIN_PATTERN = re.compile(r"^[A-Za-z0-9_-]{3,32}$")
_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MIN_PASSWORD_LENGTH = 8
MAX_NAME_LENGTH = 100
MAX_TITLE_LENGTH = 200

_ROLE_SHORTCUTS: dict[str, Role] = {"s": Role.STUDENT, "t": Role.TEACHER, "a": Role.ADMIN}
_YES = frozenset({"y", "yes", "д", "да"})
_NO = frozenset({"n", "no", "н", "нет"})


# --- учётные данные ---------------------------------------------------------


def validate_login(login: str) -> None:
    """Логин: 3-32 символа, латинские буквы, цифры, '_' или '-'."""
    if not _LOGIN_PATTERN.match(login):
        raise ValidationError(
            "Логин должен быть 3-32 символа: латинские буквы, цифры, '_' или '-'."
        )


def validate_email(email: str) -> None:
    """Email должен выглядеть как local@domain.tld."""
    if not _EMAIL_PATTERN.match(email):
        raise ValidationError("Некорректный формат email (пример: name@example.org).")


def validate_password(plain_password: str) -> None:
    """Пароль не короче MIN_PASSWORD_LENGTH символов."""
    if len(plain_password) < MIN_PASSWORD_LENGTH:
        raise ValidationError(f"Пароль должен быть не короче {MIN_PASSWORD_LENGTH} символов.")


def validate_credentials_present(login: str, plain_password: str) -> None:
    """При входе оба поля обязательны (длину пароля при входе не проверяем)."""
    if not login.strip():
        raise ValidationError("Введите логин.")
    validate_login(login.strip())
    if not plain_password:
        raise ValidationError("Введите пароль.")


# --- текстовые поля ---------------------------------------------------------


def require_text(raw: str, field_name: str, max_length: int = MAX_NAME_LENGTH) -> str:
    """Вернуть строку без крайних пробелов; она не должна быть пустой или слишком длинной."""
    value = raw.strip()
    if not value:
        raise ValidationError(f"Поле «{field_name}» не может быть пустым.")
    if len(value) > max_length:
        raise ValidationError(f"Поле «{field_name}» не длиннее {max_length} символов.")
    return value


# --- разбор значений из строки ----------------------------------------------


def parse_positive_int(raw: str) -> int:
    """Разобрать положительное целое число."""
    value = raw.strip()
    if not value.isdecimal() or int(value) < 1:
        raise ValidationError("Нужно ввести положительное целое число.")
    return int(value)


def parse_yes_no(raw: str) -> bool:
    """Разобрать ответ «да/нет» (y/n, yes/no, д/н, да/нет)."""
    value = raw.strip().lower()
    if value in _YES:
        return True
    if value in _NO:
        return False
    raise ValidationError("Введите 'y' (да) или 'n' (нет).")


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
        raise ValidationError(f"Неизвестная роль. Допустимые варианты: {role_hint()}.") from error


def parse_file_type(raw: str) -> FileType:
    """Разобрать формат файла: 'pdf', '.pdf', 'PDF'."""
    value = raw.strip().lower().lstrip(".")
    try:
        return FileType(value)
    except ValueError as error:
        allowed = ", ".join(t.value for t in FileType)
        raise ValidationError(f"Неизвестный формат. Допустимые форматы: {allowed}.") from error


def optional[T](parser: Callable[[str], T]) -> Callable[[str], T | None]:
    """Сделать поле необязательным: пустая строка даёт None, остальное разбирает parser.

    Неверное значение по-прежнему вызывает ValidationError, то есть его не
    «молча игнорируют», а переспрашивают.
    """

    def parse(raw: str) -> T | None:
        if not raw.strip():
            return None
        return parser(raw)

    return parse
