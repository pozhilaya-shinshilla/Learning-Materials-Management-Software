from __future__ import annotations

from abc import ABC, abstractmethod

from src.domain.models import Discipline, Event, Favorite, Material, Topic, User


class UserRepository(ABC):
    """Контракт хранения пользователей."""

    @abstractmethod
    def add(self, user: User) -> User:
        """Сохранить нового пользователя и вернуть его с присвоенным id."""

    @abstractmethod
    def get_by_id(self, user_id: int) -> User | None:
        """Вернуть пользователя с указанным id или None, если его нет."""

    @abstractmethod
    def get_by_login(self, login: str) -> User | None:
        """Вернуть пользователя с указанным логином или None, если его нет."""

    @abstractmethod
    def get_by_email(self, email: str) -> User | None:
        """Вернуть пользователя с указанным email (без учёта регистра) или None."""

    @abstractmethod
    def list_all(self) -> list[User]:
        """Вернуть всех зарегистрированных пользователей."""

    @abstractmethod
    def update(self, user: User) -> None:
        """Сохранить изменения существующего пользователя."""

    @abstractmethod
    def delete(self, user_id: int) -> None:
        """Удалить пользователя по id."""


class DisciplineRepository(ABC):
    """Контракт хранения дисциплин."""

    @abstractmethod
    def add(self, discipline: Discipline) -> Discipline:
        """Сохранить новую дисциплину и вернуть её с присвоенным id."""

    @abstractmethod
    def get_by_id(self, discipline_id: int) -> Discipline | None:
        """Вернуть дисциплину с указанным id или None, если её нет."""

    @abstractmethod
    def update(self, discipline: Discipline) -> None:
        """Сохранить изменения существующей дисциплины."""

    @abstractmethod
    def get_by_name(self, name: str) -> Discipline | None:
        """Вернуть дисциплину с указанным названием (без учёта регистра) или None."""

    @abstractmethod
    def list_all(self) -> list[Discipline]:
        """Вернуть все дисциплины."""


class TopicRepository(ABC):
    """Контракт хранения тем."""

    @abstractmethod
    def add(self, topic: Topic) -> Topic:
        """Сохранить новую тему и вернуть её с присвоенным id."""

    @abstractmethod
    def get_by_id(self, topic_id: int) -> Topic | None:
        """Вернуть тему с указанным id или None, если её нет."""

    @abstractmethod
    def update(self, topic: Topic) -> None:
        """Сохранить изменения существующей темы."""

    @abstractmethod
    def get_by_name(self, discipline_id: int, name: str) -> Topic | None:
        """Вернуть тему дисциплины с указанным названием (без учёта регистра) или None."""

    @abstractmethod
    def list_by_discipline(self, discipline_id: int) -> list[Topic]:
        """Вернуть все темы указанной дисциплины."""


class MaterialRepository(ABC):
    """Контракт хранения материалов."""

    @abstractmethod
    def add(self, material: Material) -> Material:
        """Сохранить новый материал и вернуть его с присвоенным id."""

    @abstractmethod
    def get_by_id(self, material_id: int) -> Material | None:
        """Вернуть материал с указанным id или None, если его нет."""

    @abstractmethod
    def list_all(self) -> list[Material]:
        """Вернуть все материалы."""

    @abstractmethod
    def update(self, material: Material) -> None:
        """Сохранить изменения существующего материала."""

    @abstractmethod
    def delete(self, material_id: int) -> None:
        """Удалить материал по id."""


class FavoriteRepository(ABC):
    """Контракт хранения избранного."""

    @abstractmethod
    def add(self, favorite: Favorite) -> Favorite:
        """Сохранить новую закладку в избранном."""

    @abstractmethod
    def remove(self, user_id: int, material_id: int) -> None:
        """Удалить закладку из избранного, если она есть."""

    @abstractmethod
    def list_by_user(self, user_id: int) -> list[Favorite]:
        """Вернуть все закладки указанного пользователя."""

    @abstractmethod
    def exists(self, user_id: int, material_id: int) -> bool:
        """Вернуть, добавил ли пользователь материал в избранное."""


class EventRepository(ABC):
    """Контракт хранения записей журнала событий."""

    @abstractmethod
    def add(self, event: Event) -> Event:
        """Сохранить новое событие и вернуть его с присвоенным id."""

    @abstractmethod
    def list_all(self) -> list[Event]:
        """Вернуть все события журнала от старых к новым."""
