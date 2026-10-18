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
    """Хранит пользователей в словаре в памяти процесса, ключ — id."""

    def __init__(self) -> None:
        self._users: dict[int, User] = {}
        self._next_id: int = 1

    def add(self, user: User) -> User:
        """Сохранить нового пользователя и вернуть его с присвоенным id."""
        user.id = self._next_id
        self._users[user.id] = user
        self._next_id += 1
        return user

    def get_by_id(self, user_id: int) -> User | None:
        """Вернуть пользователя с указанным id или None, если его нет."""
        return self._users.get(user_id)

    def get_by_login(self, login: str) -> User | None:
        """Вернуть пользователя с указанным логином или None, если его нет."""
        for user in self._users.values():
            if user.login == login:
                return user
        return None

    def list_all(self) -> list[User]:
        """Вернуть всех зарегистрированных пользователей."""
        return list(self._users.values())

    def update(self, user: User) -> None:
        """Сохранить изменения существующего пользователя."""
        self._users[user.id] = user

    def delete(self, user_id: int) -> None:
        """Удалить пользователя по id."""
        self._users.pop(user_id, None)


class InMemoryDisciplineRepository(DisciplineRepository):
    """Хранит дисциплины в словаре в памяти процесса, ключ — id."""

    def __init__(self) -> None:
        self._disciplines: dict[int, Discipline] = {}
        self._next_id: int = 1

    def add(self, discipline: Discipline) -> Discipline:
        """Сохранить новую дисциплину и вернуть её с присвоенным id."""
        discipline.id = self._next_id
        self._disciplines[discipline.id] = discipline
        self._next_id += 1
        return discipline

    def get_by_id(self, discipline_id: int) -> Discipline | None:
        """Вернуть дисциплину с указанным id или None, если её нет."""
        return self._disciplines.get(discipline_id)

    def update(self, discipline: Discipline) -> None:
        """Сохранить изменения существующей дисциплины."""
        self._disciplines[discipline.id] = discipline

    def get_by_name(self, name: str) -> Discipline | None:
        """Вернуть дисциплину с указанным названием (без учёта регистра) или None."""
        for discipline in self._disciplines.values():
            if discipline.name.casefold() == name.casefold():
                return discipline
        return None

    def list_all(self) -> list[Discipline]:
        """Вернуть все дисциплины."""
        return list(self._disciplines.values())


class InMemoryTopicRepository(TopicRepository):
    """Хранит темы в словаре в памяти процесса, ключ — id."""

    def __init__(self) -> None:
        self._topics: dict[int, Topic] = {}
        self._next_id: int = 1

    def add(self, topic: Topic) -> Topic:
        """Сохранить новую тему и вернуть её с присвоенным id."""
        topic.id = self._next_id
        self._topics[topic.id] = topic
        self._next_id += 1
        return topic

    def get_by_id(self, topic_id: int) -> Topic | None:
        """Вернуть тему с указанным id или None, если её нет."""
        return self._topics.get(topic_id)

    def update(self, topic: Topic) -> None:
        """Сохранить изменения существующей темы."""
        self._topics[topic.id] = topic

    def get_by_name(self, discipline_id: int, name: str) -> Topic | None:
        """Вернуть тему дисциплины с указанным названием (без учёта регистра) или None."""
        for topic in self._topics.values():
            if topic.discipline_id == discipline_id and topic.name.casefold() == name.casefold():
                return topic
        return None

    def list_by_discipline(self, discipline_id: int) -> list[Topic]:
        """Вернуть все темы указанной дисциплины."""
        return [t for t in self._topics.values() if t.discipline_id == discipline_id]


class InMemoryMaterialRepository(MaterialRepository):
    """Хранит материалы в словаре в памяти процесса, ключ — id."""

    def __init__(self) -> None:
        self._materials: dict[int, Material] = {}
        self._next_id: int = 1

    def add(self, material: Material) -> Material:
        """Сохранить новый материал и вернуть его с присвоенным id."""
        material.id = self._next_id
        self._materials[material.id] = material
        self._next_id += 1
        return material

    def get_by_id(self, material_id: int) -> Material | None:
        """Вернуть материал с указанным id или None, если его нет."""
        return self._materials.get(material_id)

    def list_all(self) -> list[Material]:
        """Вернуть все материалы."""
        return list(self._materials.values())

    def update(self, material: Material) -> None:
        """Сохранить изменения существующего материала."""
        self._materials[material.id] = material

    def delete(self, material_id: int) -> None:
        """Удалить материал по id."""
        self._materials.pop(material_id, None)


class InMemoryFavoriteRepository(FavoriteRepository):
    """Хранит избранное в списке в памяти процесса."""

    def __init__(self) -> None:
        self._favorites: list[Favorite] = []

    def add(self, favorite: Favorite) -> Favorite:
        """Сохранить новую закладку в избранном."""
        self._favorites.append(favorite)
        return favorite

    def remove(self, user_id: int, material_id: int) -> None:
        """Удалить закладку из избранного, если она есть."""
        self._favorites = [
            f
            for f in self._favorites
            if not (f.user_id == user_id and f.material_id == material_id)
        ]

    def list_by_user(self, user_id: int) -> list[Favorite]:
        """Вернуть все закладки указанного пользователя."""
        return [f for f in self._favorites if f.user_id == user_id]

    def exists(self, user_id: int, material_id: int) -> bool:
        """Вернуть, добавил ли пользователь материал в избранное."""
        return any(f.user_id == user_id and f.material_id == material_id for f in self._favorites)


class InMemoryEventRepository(EventRepository):
    """Хранит записи журнала событий в списке в памяти процесса."""

    def __init__(self) -> None:
        self._events: list[Event] = []
        self._next_id: int = 1

    def add(self, event: Event) -> Event:
        """Сохранить новое событие и вернуть его с присвоенным id."""
        event.id = self._next_id
        self._events.append(event)
        self._next_id += 1
        return event

    def list_all(self) -> list[Event]:
        """Вернуть все события журнала от старых к новым."""
        return list(self._events)
