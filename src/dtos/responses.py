"""Схемы ответов REST API (Pydantic).

«Выходные» DTO: что сервер возвращает клиенту. Каждая схема собирается из доменного объекта
методом `from_domain` (в терминах Фаулера — Assembler). В схемах нет лишних полей: например,
в `UserResponse` нет хеша пароля, поэтому он не может попасть в ответ даже по ошибке.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field

from src.domain.enums import AccountStatus, EventType, FileType, Role
from src.domain.models import Event


class _Response(BaseModel):
    """Общая настройка выходных схем: значения читаются из атрибутов доменных объектов."""

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_domain(cls, source: object) -> Self:
        """Собрать DTO из доменного объекта."""
        return cls.model_validate(source)


class UserResponse(_Response):
    """Основные сведения об учётной записи (без пароля и его хеша)."""

    id: int = Field(description="Номер пользователя", examples=[5])
    login: str = Field(description="Логин", examples=["teacher1"])
    email: str = Field(description="Электронная почта", examples=["teacher1@example.org"])
    role: Role = Field(description="Роль", examples=["teacher"])
    status: AccountStatus = Field(description="Статус учётной записи", examples=["active"])


class TokenResponse(_Response):
    """Ответ на успешный вход: токен для заголовка `Authorization: Bearer <токен>`."""

    access_token: str = Field(
        description="Токен доступа; передаётся в заголовке Authorization",
        examples=["kQ3v0Zy7mYb1xUeP5r2nTq9sWfHjLc8dA4gV6oXtB1E"],
    )
    token_type: Literal["bearer"] = Field(
        default="bearer", description="Тип токена", examples=["bearer"]
    )
    expires_at: datetime = Field(
        description="Когда токен перестанет действовать (UTC)", examples=["2026-11-03T08:30:00Z"]
    )
    user: UserResponse = Field(
        description="Вошедший пользователь",
        examples=[
            {
                "id": 5,
                "login": "teacher1",
                "email": "teacher1@example.org",
                "role": "teacher",
                "status": "active",
            }
        ],
    )


class DisciplineResponse(_Response):
    """Дисциплина."""

    id: int = Field(description="Номер дисциплины", examples=[3])
    name: str = Field(description="Название", examples=["Математика"])


class TopicResponse(_Response):
    """Тема дисциплины."""

    id: int = Field(description="Номер темы", examples=[7])
    name: str = Field(description="Название", examples=["Пределы"])
    discipline_id: int = Field(description="Номер дисциплины темы", examples=[3])


class MaterialResponse(_Response):
    """Сведения об учебном материале (сам файл отдаёт `GET /api/materials/{id}/download`)."""

    id: int = Field(description="Номер материала", examples=[12])
    title: str = Field(description="Название", examples=["Лекция 1. Пределы"])
    description: str = Field(
        description="Описание", examples=["Определение предела последовательности и функции."]
    )
    discipline_id: int = Field(description="Номер дисциплины", examples=[3])
    topic_id: int = Field(description="Номер темы", examples=[7])
    file_name: str = Field(description="Имя загруженного файла", examples=["lecture1.pdf"])
    file_type: FileType = Field(description="Формат файла", examples=["pdf"])
    file_size_bytes: int = Field(description="Размер файла в байтах", examples=[482113])
    author_id: int | None = Field(
        description="Номер автора; `null`, если автора удалили", examples=[5]
    )
    author_login: str | None = Field(
        default=None,
        description="Логин автора; «автор удалён», если автора удалили",
        examples=["teacher1"],
    )
    uploaded_at: datetime = Field(
        description="Когда загружен (UTC)", examples=["2026-11-02T09:48:31Z"]
    )


class FavoriteResponse(_Response):
    """Закладка пользователя на материал."""

    user_id: int = Field(description="Номер пользователя", examples=[5])
    material_id: int = Field(description="Номер материала", examples=[12])
    added_at: datetime = Field(
        description="Когда добавлено в избранное (UTC)", examples=["2026-11-02T10:15:00Z"]
    )


class EventResponse(_Response):
    """Запись журнала событий."""

    id: int = Field(description="Номер записи", examples=[101])
    user_id: int | None = Field(
        description="Кто совершил действие; `null`, если пользователя удалили", examples=[5]
    )
    event_type: EventType = Field(
        description="Тип события (машинное имя)", examples=["material_created"]
    )
    description: str = Field(description="Тип события по-русски", examples=["материал создан"])
    target: str = Field(
        description="К чему относится событие (название, логин)", examples=["Лекция 1"]
    )
    occurred_at: datetime = Field(
        description="Когда произошло (UTC)", examples=["2026-11-02T09:48:31Z"]
    )

    @classmethod
    def from_domain(cls, source: object) -> Self:
        """Собрать запись журнала и добавить читаемое описание типа события."""
        if not isinstance(source, Event):
            raise TypeError("ожидалось событие журнала")
        return cls(
            id=source.id,
            user_id=source.user_id,
            event_type=source.event_type,
            description=source.event_type.label,
            target=source.target,
            occurred_at=source.occurred_at,
        )


class ValidationIssue(BaseModel):
    """Одна ошибка проверки данных запроса."""

    loc: list[str] = Field(description="Путь к полю в запросе", examples=[["body", "title"]])
    field: str = Field(description="Имя поля без служебных частей пути", examples=["title"])
    message: str = Field(
        description="Что не так, по-русски",
        examples=["слишком длинное значение (максимум символов: 200)"],
    )
    type: str = Field(description="Машинный код ошибки Pydantic", examples=["string_too_long"])


class ValidationErrorResponse(BaseModel):
    """Ответ 422: общий текст и разбор по полям."""

    detail: str = Field(
        description="Сводка для человека",
        examples=[
            "Данные не прошли проверку: title: слишком длинное значение (максимум символов: 200)."
        ],
    )
    code: str = Field(description="Код ошибки", examples=["RequestValidationError"])
    errors: list[ValidationIssue] = Field(
        description="Ошибки по полям",
        examples=[
            [
                {
                    "loc": ["body", "title"],
                    "field": "title",
                    "message": "слишком длинное значение (максимум символов: 200)",
                    "type": "string_too_long",
                }
            ]
        ],
    )


class MessageResponse(BaseModel):
    """Простое сообщение об успехе."""

    detail: str = Field(description="Текст сообщения", examples=["Выход выполнен."])


class ErrorResponse(BaseModel):
    """Единый вид ошибки: текст для человека и код для программы."""

    detail: str = Field(description="Что произошло, по-русски", examples=["Материал не найден."])
    code: str = Field(
        description="Имя ошибки для программ: по нему клиент выбирает поведение",
        examples=["MaterialNotFoundError"],
    )
