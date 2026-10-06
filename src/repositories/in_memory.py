from __future__ import annotations

from src.domain.models import Discipline, Event, Favorite, Material, Topic, User
from src.repositories.interfaces import (
    DisciplineRepository,
    EventRepository,
    FavoriteRepository,
    MaterialRepository,
    TopicRepository,
    UserRepository,
)


class InMemoryUserRepository(UserRepository):
    """Keeps users in a process-local dictionary, keyed by id."""

    def __init__(self) -> None:
        self._users: dict[int, User] = {}
        self._next_id: int = 1

    def add(self, user: User) -> User:
        """Persist a new user and return it with its assigned id."""
        user.id = self._next_id
        self._users[user.id] = user
        self._next_id += 1
        return user

    def get_by_id(self, user_id: int) -> User | None:
        """Return the user with the given id, or None if not found."""
        return self._users.get(user_id)

    def get_by_login(self, login: str) -> User | None:
        """Return the user with the given login, or None if not found."""
        for user in self._users.values():
            if user.login == login:
                return user
        return None

    def list_all(self) -> list[User]:
        """Return every registered user."""
        return list(self._users.values())

    def update(self, user: User) -> None:
        """Persist changes made to an existing user."""
        self._users[user.id] = user

    def delete(self, user_id: int) -> None:
        """Remove a user by id."""
        self._users.pop(user_id, None)


class InMemoryDisciplineRepository(DisciplineRepository):
    """Keeps disciplines in a process-local dictionary, keyed by id."""

    def __init__(self) -> None:
        self._disciplines: dict[int, Discipline] = {}
        self._next_id: int = 1

    def add(self, discipline: Discipline) -> Discipline:
        """Persist a new discipline and return it with its assigned id."""
        discipline.id = self._next_id
        self._disciplines[discipline.id] = discipline
        self._next_id += 1
        return discipline

    def get_by_id(self, discipline_id: int) -> Discipline | None:
        """Return the discipline with the given id, or None if not found."""
        return self._disciplines.get(discipline_id)

    def get_by_name(self, name: str) -> Discipline | None:
        """Return the discipline with the given name (case-insensitive), or None."""
        for discipline in self._disciplines.values():
            if discipline.name.casefold() == name.casefold():
                return discipline
        return None

    def list_all(self) -> list[Discipline]:
        """Return every discipline."""
        return list(self._disciplines.values())


class InMemoryTopicRepository(TopicRepository):
    """Keeps topics in a process-local dictionary, keyed by id."""

    def __init__(self) -> None:
        self._topics: dict[int, Topic] = {}
        self._next_id: int = 1

    def add(self, topic: Topic) -> Topic:
        """Persist a new topic and return it with its assigned id."""
        topic.id = self._next_id
        self._topics[topic.id] = topic
        self._next_id += 1
        return topic

    def get_by_id(self, topic_id: int) -> Topic | None:
        """Return the topic with the given id, or None if not found."""
        return self._topics.get(topic_id)

    def get_by_name(self, discipline_id: int, name: str) -> Topic | None:
        """Return the topic of the discipline with the given name (case-insensitive), or None."""
        for topic in self._topics.values():
            if topic.discipline_id == discipline_id and topic.name.casefold() == name.casefold():
                return topic
        return None

    def list_by_discipline(self, discipline_id: int) -> list[Topic]:
        """Return every topic that belongs to the given discipline."""
        return [t for t in self._topics.values() if t.discipline_id == discipline_id]


class InMemoryMaterialRepository(MaterialRepository):
    """Keeps materials in a process-local dictionary, keyed by id."""

    def __init__(self) -> None:
        self._materials: dict[int, Material] = {}
        self._next_id: int = 1

    def add(self, material: Material) -> Material:
        """Persist a new material and return it with its assigned id."""
        material.id = self._next_id
        self._materials[material.id] = material
        self._next_id += 1
        return material

    def get_by_id(self, material_id: int) -> Material | None:
        """Return the material with the given id, or None if not found."""
        return self._materials.get(material_id)

    def list_all(self) -> list[Material]:
        """Return every material."""
        return list(self._materials.values())

    def update(self, material: Material) -> None:
        """Persist changes made to an existing material."""
        self._materials[material.id] = material

    def delete(self, material_id: int) -> None:
        """Remove a material by id."""
        self._materials.pop(material_id, None)


class InMemoryFavoriteRepository(FavoriteRepository):
    """Keeps favorites in a process-local list."""

    def __init__(self) -> None:
        self._favorites: list[Favorite] = []

    def add(self, favorite: Favorite) -> Favorite:
        """Persist a new favorite bookmark."""
        self._favorites.append(favorite)
        return favorite

    def remove(self, user_id: int, material_id: int) -> None:
        """Remove a favorite bookmark, if it exists."""
        self._favorites = [
            f
            for f in self._favorites
            if not (f.user_id == user_id and f.material_id == material_id)
        ]

    def list_by_user(self, user_id: int) -> list[Favorite]:
        """Return every favorite bookmark belonging to the given user."""
        return [f for f in self._favorites if f.user_id == user_id]

    def exists(self, user_id: int, material_id: int) -> bool:
        """Return whether the given user already bookmarked the material."""
        return any(f.user_id == user_id and f.material_id == material_id for f in self._favorites)


class InMemoryEventRepository(EventRepository):
    """Keeps event log entries in a process-local list."""

    def __init__(self) -> None:
        self._events: list[Event] = []
        self._next_id: int = 1

    def add(self, event: Event) -> Event:
        """Persist a new event and return it with its assigned id."""
        event.id = self._next_id
        self._events.append(event)
        self._next_id += 1
        return event

    def list_all(self) -> list[Event]:
        """Return every logged event, ordered from oldest to newest."""
        return list(self._events)
