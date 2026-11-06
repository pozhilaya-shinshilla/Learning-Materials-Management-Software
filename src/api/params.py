"""Описанные параметры пути: идентификаторы с границами и примерами для Swagger UI.

Верхняя граница равна максимуму `integer` в PostgreSQL: больший номер заведомо не существует,
и клиент получает понятный `422`, а не ошибку базы данных.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Path

MAX_ID = 2**31 - 1

MaterialId = Annotated[
    int, Path(ge=1, le=MAX_ID, description="Номер учебного материала", examples=[12])
]
DisciplineId = Annotated[int, Path(ge=1, le=MAX_ID, description="Номер дисциплины", examples=[3])]
TopicId = Annotated[int, Path(ge=1, le=MAX_ID, description="Номер темы", examples=[7])]
UserId = Annotated[int, Path(ge=1, le=MAX_ID, description="Номер пользователя", examples=[5])]
