"""Схемы запросов REST API (Pydantic).

Это «входные» DTO: что клиент вправе прислать. Лишние поля запрещены (`extra="forbid"`),
чтобы опечатка в имени поля давала ошибку 422, а не молча игнорировалась.
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from src.domain.enums import AccountStatus, FileType, Role, SortField, SortOrder
from src.domain.validation import MAX_NAME_LENGTH, MAX_TITLE_LENGTH

MAX_DESCRIPTION_LENGTH = 10_000
MAX_LOGIN_LENGTH = 50
MAX_EMAIL_LENGTH = 255
MAX_PASSWORD_LENGTH = 128
MAX_ID = 2**31 - 1  # максимум integer в PostgreSQL


class _Request(BaseModel):
    """Общая настройка входных схем: лишние поля запрещены, пробелы по краям обрезаются."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    @field_validator("*", mode="after")
    @classmethod
    def _no_control_characters(cls, value: object) -> object:
        """Текстовые поля не могут содержать нулевой и другие управляющие символы.

        Нулевой символ PostgreSQL не принимает вовсе, остальные управляющие не нужны ни в
        названиях, ни в логинах; перевод строки и табуляция допустимы (описания бывают длинными).
        """
        if isinstance(value, str) and any(
            ord(char) < 32 and char not in "\n\r\t" or ord(char) == 127 for char in value
        ):
            raise ValueError("Текст содержит недопустимые управляющие символы.")
        return value


class LoginRequest(_Request):
    """Вход по логину и паролю."""

    login: str = Field(
        min_length=1, max_length=MAX_LOGIN_LENGTH, description="Логин", examples=["teacher1"]
    )
    password: str = Field(
        min_length=1,
        max_length=MAX_PASSWORD_LENGTH,
        description="Пароль",
        examples=["Password123!"],
    )


class PasswordRecoveryRequest(_Request):
    """Запрос письма с кодом восстановления пароля."""

    email: str = Field(
        min_length=3,
        max_length=MAX_EMAIL_LENGTH,
        description="Адрес электронной почты учётной записи",
        examples=["user@example.org"],
    )


class PasswordResetRequest(_Request):
    """Установка нового пароля по коду из письма."""

    token: str = Field(
        min_length=1,
        max_length=128,
        description="Код восстановления из письма (одноразовый, действует 30 минут)",
        examples=["q3x9Zk1uWvB0f2Lm"],
    )
    new_password: str = Field(
        min_length=1,
        max_length=MAX_PASSWORD_LENGTH,
        description="Новый пароль: не короче 8 символов, буквы и цифры",
        examples=["NewPassword456!"],
    )


class MaterialCreateRequest(_Request):
    """Метаданные нового материала; файл передаётся отдельной частью `multipart/form-data`."""

    title: str = Field(
        min_length=1,
        max_length=MAX_TITLE_LENGTH,
        description="Название материала",
        examples=["Лекция 1. Пределы"],
    )
    description: str = Field(
        default="",
        max_length=MAX_DESCRIPTION_LENGTH,
        description="Описание материала (необязательно)",
        examples=["Определение предела последовательности и функции."],
    )
    discipline_id: int = Field(gt=0, le=MAX_ID, description="Номер дисциплины", examples=[3])
    topic_id: int = Field(
        gt=0,
        le=MAX_ID,
        description="Номер темы (должна принадлежать этой дисциплине)",
        examples=[7],
    )


class MaterialUpdateRequest(_Request):
    """Частичное изменение материала (PATCH): присылаются только изменяемые поля."""

    title: str | None = Field(
        default=None,
        min_length=1,
        max_length=MAX_TITLE_LENGTH,
        description="Новое название",
        examples=["Лекция 1. Пределы (новая редакция)"],
    )
    description: str | None = Field(
        default=None,
        max_length=MAX_DESCRIPTION_LENGTH,
        description="Новое описание",
        examples=["Дополнены примеры."],
    )
    discipline_id: int | None = Field(
        default=None, gt=0, le=MAX_ID, description="Новая дисциплина", examples=[3]
    )
    topic_id: int | None = Field(
        default=None, gt=0, le=MAX_ID, description="Новая тема", examples=[8]
    )


class MaterialListQuery(_Request):
    """Параметры поиска, фильтрации, сортировки и страницы списка материалов (query string)."""

    q: str | None = Field(
        default=None,
        max_length=200,
        description="Полнотекстовый запрос по названию и описанию (учитывает морфологию)",
        examples=["лекции по пределам"],
    )
    discipline_id: int | None = Field(
        default=None, gt=0, le=MAX_ID, description="Только эта дисциплина", examples=[3]
    )
    topic_id: int | None = Field(
        default=None, gt=0, le=MAX_ID, description="Только эта тема", examples=[7]
    )
    file_type: FileType | None = Field(
        default=None, description="Только этот формат файла", examples=["pdf"]
    )
    uploaded_from: date | None = Field(
        default=None,
        description="Загружен не раньше (включая), ГГГГ-ММ-ДД",
        examples=["2026-09-01"],
    )
    uploaded_to: date | None = Field(
        default=None, description="Загружен не позже (включая), ГГГГ-ММ-ДД", examples=["2026-10-31"]
    )
    sort_by: SortField = Field(
        default=SortField.UPLOAD_DATE, description="Поле сортировки", examples=["title"]
    )
    order: SortOrder = Field(
        default=SortOrder.DESCENDING, description="Направление сортировки", examples=["asc"]
    )
    limit: int | None = Field(
        default=None,
        ge=1,
        le=100,
        description="Размер страницы; без него возвращаются все материалы",
        examples=[10],
    )
    offset: int = Field(
        default=0,
        ge=0,
        le=MAX_ID,
        description="Сколько материалов пропустить от начала списка",
        examples=[0],
    )

    @model_validator(mode="after")
    def _check_date_range(self) -> MaterialListQuery:
        """Конечная дата периода не может быть раньше начальной."""
        if self.uploaded_from and self.uploaded_to and self.uploaded_to < self.uploaded_from:
            raise ValueError("Конечная дата не может быть раньше начальной.")
        return self


class DisciplineCreateRequest(_Request):
    """Новая дисциплина."""

    name: str = Field(
        min_length=1, max_length=MAX_NAME_LENGTH, description="Название", examples=["Математика"]
    )


class DisciplineUpdateRequest(_Request):
    """Частичное изменение дисциплины (PATCH)."""

    name: str | None = Field(
        default=None,
        min_length=1,
        max_length=MAX_NAME_LENGTH,
        description="Новое название",
        examples=["Высшая математика"],
    )


class TopicCreateRequest(_Request):
    """Новая тема внутри дисциплины."""

    name: str = Field(
        min_length=1, max_length=MAX_NAME_LENGTH, description="Название", examples=["Пределы"]
    )
    discipline_id: int = Field(
        gt=0, le=MAX_ID, description="Номер дисциплины, в которую входит тема", examples=[3]
    )


class TopicUpdateRequest(_Request):
    """Частичное изменение темы (PATCH)."""

    name: str | None = Field(
        default=None,
        min_length=1,
        max_length=MAX_NAME_LENGTH,
        description="Новое название",
        examples=["Производные"],
    )


class UserCreateRequest(_Request):
    """Новая учётная запись (создаёт администратор)."""

    login: str = Field(
        min_length=1, max_length=MAX_LOGIN_LENGTH, description="Логин", examples=["ivanov"]
    )
    email: str = Field(
        min_length=3,
        max_length=MAX_EMAIL_LENGTH,
        description="Электронная почта (уникальна без учёта регистра)",
        examples=["ivanov@example.org"],
    )
    password: str = Field(
        min_length=1,
        max_length=MAX_PASSWORD_LENGTH,
        description="Пароль: не короче 8 символов, буквы и цифры",
        examples=["Password123!"],
    )
    role: Role = Field(default=Role.STUDENT, description="Роль", examples=["teacher"])


class UserUpdateRequest(_Request):
    """Частичное изменение учётной записи (PATCH): роль и/или блокировка."""

    role: Role | None = Field(default=None, description="Новая роль", examples=["teacher"])
    status: AccountStatus | None = Field(
        default=None,
        description="`blocked` — заблокировать, `active` — разблокировать",
        examples=["blocked"],
    )
