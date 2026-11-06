"""Абстрактный репозиторий: контракт хранилища, общий для любой реализации."""

from abc import ABC, abstractmethod
from typing import Generic, TypeVar

ModelT = TypeVar("ModelT")


class AbstractRepository(ABC, Generic[ModelT]):  # noqa: UP046  (форма из методички)
    """Контракт хранилища: что умеет любой репозиторий."""

    @abstractmethod
    def add(self, entity: ModelT) -> ModelT:
        """Сохранить новую сущность и вернуть её."""
        ...

    @abstractmethod
    def get_by_id(self, entity_id: int) -> ModelT | None:
        """Найти сущность по первичному ключу."""
        ...

    @abstractmethod
    def get_all(self) -> list[ModelT]:
        """Вернуть все сущности."""
        ...

    @abstractmethod
    def update(self, entity: ModelT) -> ModelT:
        """Сохранить изменения существующей сущности."""
        ...

    @abstractmethod
    def delete(self, entity: ModelT) -> None:
        """Удалить сущность."""
        ...
