from __future__ import annotations

from abc import ABC, abstractmethod

from src.domain.models import Discipline, Event, Favorite, Material, Topic, User


class UserRepository(ABC):
    """Persistence contract for User entities."""

    @abstractmethod
    def add(self, user: User) -> User:
        """Persist a new user and return it with its assigned id."""

    @abstractmethod
    def get_by_id(self, user_id: int) -> User | None:
        """Return the user with the given id, or None if not found."""

    @abstractmethod
    def get_by_login(self, login: str) -> User | None:
        """Return the user with the given login, or None if not found."""

    @abstractmethod
    def list_all(self) -> list[User]:
        """Return every registered user."""

    @abstractmethod
    def update(self, user: User) -> None:
        """Persist changes made to an existing user."""

    @abstractmethod
    def delete(self, user_id: int) -> None:
        """Remove a user by id."""


class DisciplineRepository(ABC):
    """Persistence contract for Discipline entities."""

    @abstractmethod
    def add(self, discipline: Discipline) -> Discipline:
        """Persist a new discipline and return it with its assigned id."""

    @abstractmethod
    def get_by_id(self, discipline_id: int) -> Discipline | None:
        """Return the discipline with the given id, or None if not found."""

    @abstractmethod
    def get_by_name(self, name: str) -> Discipline | None:
        """Return the discipline with the given name (case-insensitive), or None."""

    @abstractmethod
    def list_all(self) -> list[Discipline]:
        """Return every discipline."""


class TopicRepository(ABC):
    """Persistence contract for Topic entities."""

    @abstractmethod
    def add(self, topic: Topic) -> Topic:
        """Persist a new topic and return it with its assigned id."""

    @abstractmethod
    def get_by_id(self, topic_id: int) -> Topic | None:
        """Return the topic with the given id, or None if not found."""

    @abstractmethod
    def get_by_name(self, discipline_id: int, name: str) -> Topic | None:
        """Return the topic of the discipline with the given name (case-insensitive), or None."""

    @abstractmethod
    def list_by_discipline(self, discipline_id: int) -> list[Topic]:
        """Return every topic that belongs to the given discipline."""


class MaterialRepository(ABC):
    """Persistence contract for Material entities."""

    @abstractmethod
    def add(self, material: Material) -> Material:
        """Persist a new material and return it with its assigned id."""

    @abstractmethod
    def get_by_id(self, material_id: int) -> Material | None:
        """Return the material with the given id, or None if not found."""

    @abstractmethod
    def list_all(self) -> list[Material]:
        """Return every material."""

    @abstractmethod
    def update(self, material: Material) -> None:
        """Persist changes made to an existing material."""

    @abstractmethod
    def delete(self, material_id: int) -> None:
        """Remove a material by id."""


class FavoriteRepository(ABC):
    """Persistence contract for Favorite entities."""

    @abstractmethod
    def add(self, favorite: Favorite) -> Favorite:
        """Persist a new favorite bookmark."""

    @abstractmethod
    def remove(self, user_id: int, material_id: int) -> None:
        """Remove a favorite bookmark, if it exists."""

    @abstractmethod
    def list_by_user(self, user_id: int) -> list[Favorite]:
        """Return every favorite bookmark belonging to the given user."""

    @abstractmethod
    def exists(self, user_id: int, material_id: int) -> bool:
        """Return whether the given user already bookmarked the material."""


class EventRepository(ABC):
    """Persistence contract for Event log entries."""

    @abstractmethod
    def add(self, event: Event) -> Event:
        """Persist a new event and return it with its assigned id."""

    @abstractmethod
    def list_all(self) -> list[Event]:
        """Return every logged event, ordered from oldest to newest."""
