"""Хранилище в памяти: семейство репозиториев без базы данных для юнит- и API-тестов.

Класс `InMemoryRepositoryFactory` реализует тот же интерфейс `RepositoryFactory`, что и
PostgreSQL-вариант, поэтому сервисы, консоль и REST API собираются на нём без единой правки
(`build_application_context(InMemoryRepositoryFactory())`). Все репозитории семейства делят
одно `Store`, как репозитории PostgreSQL делят сессию.

Что воспроизведено из поведения БД, на которое опираются сервисы и тесты: автоматические id,
уникальность логина, email и названий без учёта регистра, каскады (удаление пользователя
обнуляет автора материалов и событий и удаляет закладки и токены), запрет удалить дисциплину с
темами и тему с материалами, отбор, сортировка и страницы поиска. Чего нет: транзакций (откат
ничего не отменяет), внешних ключей на вставке и морфологии русского языка. Всё, что зависит
от SQL, проверяется в `tests/integration` на настоящем PostgreSQL.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from copy import copy
from dataclasses import dataclass, field, replace
from datetime import datetime

from src.configs.config import MAX_REVISIONS_PER_MATERIAL
from src.domain.enums import SortField, SortOrder
from src.domain.exceptions import (
    AccountDeletedError,
    DisciplineNotEmptyError,
    DuplicateDisciplineError,
    DuplicateEmailError,
    DuplicateFavoriteError,
    DuplicateLoginError,
    DuplicateTopicError,
    MaterialNotFoundError,
    TopicInUseError,
)
from src.domain.models import (
    AuthToken,
    Discipline,
    Event,
    Favorite,
    Material,
    MaterialMemento,
    PasswordResetToken,
    Topic,
    User,
)
from src.domain.search import MaterialSearchQuery
from src.repositories import interfaces
from src.repositories.factory import RepositoryFactory

_WORD = re.compile(r"[0-9a-zа-яё]+")


@dataclass
class Store:
    """Все «таблицы» семейства репозиториев и счётчики id."""

    users: dict[int, User] = field(default_factory=dict)
    disciplines: dict[int, Discipline] = field(default_factory=dict)
    topics: dict[int, Topic] = field(default_factory=dict)
    materials: dict[int, Material] = field(default_factory=dict)
    favorites: list[Favorite] = field(default_factory=list)
    events: list[Event] = field(default_factory=list)
    reset_tokens: dict[int, PasswordResetToken] = field(default_factory=dict)
    auth_tokens: dict[int, AuthToken] = field(default_factory=dict)
    failed_logins: dict[str, int] = field(default_factory=dict)
    revisions: dict[int, list[MaterialMemento]] = field(default_factory=dict)
    counters: dict[str, int] = field(default_factory=dict)

    def next_id(self, table: str, explicit: int = 0) -> int:
        """Выдать id: заданный явно (и сдвинуть счётчик за него) или следующий по порядку."""
        current = self.counters.get(table, 0)
        value = explicit or current + 1
        self.counters[table] = max(current, value)
        return value


class _Repository:
    def __init__(self, store: Store) -> None:
        self._s = store


class InMemoryUserRepository(_Repository, interfaces.UserRepository):
    def add(self, user: User) -> User:
        for other in self._s.users.values():
            if other.login == user.login:
                raise DuplicateLoginError(login=user.login)
            if other.email.lower() == user.email.lower():
                raise DuplicateEmailError(email=user.email)
        user.id = self._s.next_id("users", user.id)
        self._s.users[user.id] = copy(user)
        return user

    def get_by_id(self, user_id: int) -> User | None:
        found = self._s.users.get(user_id)
        return copy(found) if found else None

    def get_by_login(self, login: str) -> User | None:
        return next((copy(u) for u in self._s.users.values() if u.login == login), None)

    def get_by_email(self, email: str) -> User | None:
        wanted = email.lower()
        return next((copy(u) for u in self._s.users.values() if u.email.lower() == wanted), None)

    def list_all(self) -> list[User]:
        return [copy(u) for _, u in sorted(self._s.users.items())]

    def update(self, user: User) -> None:
        if user.id in self._s.users:
            self._s.users[user.id] = copy(user)

    def delete(self, user_id: int) -> None:
        if self._s.users.pop(user_id, None) is None:
            return
        for material in self._s.materials.values():
            if material.author_id == user_id:
                material.author_id = None
        self._s.events[:] = [
            replace(e, user_id=None) if e.user_id == user_id else e for e in self._s.events
        ]
        self._s.favorites[:] = [f for f in self._s.favorites if f.user_id != user_id]
        for table in (self._s.auth_tokens, self._s.reset_tokens):
            for key in [k for k, t in table.items() if t.user_id == user_id]:
                del table[key]

    def lock(self, user_id: int) -> bool:
        return user_id in self._s.users

    def lock_many(self, user_ids: Iterable[int], *, exclusive: bool = False) -> set[int]:
        return {uid for uid in user_ids if uid in self._s.users}


class InMemoryDisciplineRepository(_Repository, interfaces.DisciplineRepository):
    def _check_name(self, name: str, own_id: int | None) -> None:
        for other in self._s.disciplines.values():
            if other.id != own_id and other.name.lower() == name.lower():
                raise DuplicateDisciplineError(name=name)

    def add(self, discipline: Discipline) -> Discipline:
        self._check_name(discipline.name, None)
        discipline.id = self._s.next_id("disciplines", discipline.id)
        self._s.disciplines[discipline.id] = copy(discipline)
        return discipline

    def get_by_id(self, discipline_id: int) -> Discipline | None:
        found = self._s.disciplines.get(discipline_id)
        return copy(found) if found else None

    def update(self, discipline: Discipline) -> None:
        if discipline.id in self._s.disciplines:
            self._check_name(discipline.name, discipline.id)
            self._s.disciplines[discipline.id] = copy(discipline)

    def delete(self, discipline_id: int) -> None:
        found = self._s.disciplines.get(discipline_id)
        if found is None:
            return
        if any(t.discipline_id == discipline_id for t in self._s.topics.values()):
            raise DisciplineNotEmptyError(name=found.name)
        del self._s.disciplines[discipline_id]

    def get_by_name(self, name: str) -> Discipline | None:
        return next(
            (copy(d) for d in self._s.disciplines.values() if d.name.lower() == name.lower()), None
        )

    def list_all(self) -> list[Discipline]:
        return [copy(d) for _, d in sorted(self._s.disciplines.items())]


class InMemoryTopicRepository(_Repository, interfaces.TopicRepository):
    def _check_name(self, topic: Topic) -> None:
        for other in self._s.topics.values():
            same_place = other.discipline_id == topic.discipline_id and other.id != topic.id
            if same_place and other.name.lower() == topic.name.lower():
                raise DuplicateTopicError(name=topic.name)

    def add(self, topic: Topic) -> Topic:
        topic.id = self._s.next_id("topics", topic.id)
        self._check_name(topic)
        self._s.topics[topic.id] = copy(topic)
        return topic

    def get_by_id(self, topic_id: int) -> Topic | None:
        found = self._s.topics.get(topic_id)
        return copy(found) if found else None

    def update(self, topic: Topic) -> None:
        if topic.id in self._s.topics:
            self._check_name(topic)
            self._s.topics[topic.id] = copy(topic)

    def delete(self, topic_id: int) -> None:
        found = self._s.topics.get(topic_id)
        if found is None:
            return
        if any(m.topic_id == topic_id for m in self._s.materials.values()):
            raise TopicInUseError(name=found.name)
        del self._s.topics[topic_id]

    def get_by_name(self, discipline_id: int, name: str) -> Topic | None:
        return next(
            (
                copy(t)
                for t in self._s.topics.values()
                if t.discipline_id == discipline_id and t.name.lower() == name.lower()
            ),
            None,
        )

    def list_by_discipline(self, discipline_id: int) -> list[Topic]:
        return [
            copy(t) for _, t in sorted(self._s.topics.items()) if t.discipline_id == discipline_id
        ]


def _words(text: str) -> list[str]:
    return _WORD.findall(text.lower())


class InMemoryMaterialRepository(_Repository, interfaces.MaterialRepository):
    def add(self, material: Material) -> Material:
        if material.author_id is not None and material.author_id not in self._s.users:
            raise AccountDeletedError()
        material.id = self._s.next_id("materials", material.id)
        self._s.materials[material.id] = copy(material)
        return material

    def get_by_id(self, material_id: int) -> Material | None:
        found = self._s.materials.get(material_id)
        return copy(found) if found else None

    def list_all(self) -> list[Material]:
        return [copy(m) for _, m in sorted(self._s.materials.items())]

    def _matches(self, material: Material, query: MaterialSearchQuery) -> bool:
        if query.discipline_id is not None and material.discipline_id != query.discipline_id:
            return False
        if query.topic_id is not None and material.topic_id != query.topic_id:
            return False
        if query.file_type is not None and material.file_type is not query.file_type:
            return False
        if query.uploaded_from is not None and material.uploaded_at < query.uploaded_from:
            return False
        if query.uploaded_before is not None and material.uploaded_at >= query.uploaded_before:
            return False
        wanted = _words(query.text or "")
        if wanted:
            have = _words(f"{material.title} {material.description}")
            # Без морфологии: слово запроса должно быть началом слова текста (как `слово:*`).
            return all(any(h.startswith(w) for h in have) for w in wanted)
        return True

    def _found(self, query: MaterialSearchQuery) -> list[Material]:
        found = [m for m in self._s.materials.values() if self._matches(m, query)]
        found.sort(key=lambda m: m.id)
        key = (
            (lambda m: m.title.lower())
            if query.sort_field is SortField.TITLE
            else (lambda m: m.uploaded_at)
        )
        found.sort(key=key, reverse=query.sort_order is SortOrder.DESCENDING)
        return found

    def search(self, query: MaterialSearchQuery) -> list[Material]:
        found = self._found(query)
        if query.limit is not None:
            found = found[query.offset : query.offset + query.limit]
        return [copy(m) for m in found]

    def count(self, query: MaterialSearchQuery) -> int:
        return len(self._found(query))

    def get_by_id_for_update(
        self, material_id: int, *, acting_user_id: int | None = None
    ) -> Material | None:
        found = self._s.materials.get(material_id)
        if found is None:
            return None
        if acting_user_id is not None and acting_user_id not in self._s.users:
            raise AccountDeletedError()
        return copy(found)

    def update(self, material: Material) -> None:
        if material.id in self._s.materials:
            self._s.materials[material.id] = copy(material)

    def delete(self, material_id: int) -> None:
        if self._s.materials.pop(material_id, None) is None:
            return
        self._s.favorites[:] = [f for f in self._s.favorites if f.material_id != material_id]
        self._s.revisions.pop(material_id, None)


class InMemoryFavoriteRepository(_Repository, interfaces.FavoriteRepository):
    def add(self, favorite: Favorite) -> Favorite:
        if favorite.user_id not in self._s.users:
            raise AccountDeletedError()
        material = self._s.materials.get(favorite.material_id)
        if material is None:
            raise MaterialNotFoundError(material_id=favorite.material_id)
        if self.exists(favorite.user_id, favorite.material_id):
            raise DuplicateFavoriteError(title=material.title)
        self._s.favorites.append(copy(favorite))
        return copy(favorite)

    def remove(self, user_id: int, material_id: int) -> None:
        self._s.favorites[:] = [
            f for f in self._s.favorites if (f.user_id, f.material_id) != (user_id, material_id)
        ]

    def list_by_user(self, user_id: int) -> list[Favorite]:
        found = [copy(f) for f in self._s.favorites if f.user_id == user_id]
        return sorted(found, key=lambda f: f.added_at)

    def exists(self, user_id: int, material_id: int) -> bool:
        return any((f.user_id, f.material_id) == (user_id, material_id) for f in self._s.favorites)


class InMemoryEventRepository(_Repository, interfaces.EventRepository):
    def add(self, event: Event) -> Event:
        event.id = self._s.next_id("events", event.id)
        self._s.events.append(copy(event))
        return event

    def list_all(self) -> list[Event]:
        return [copy(e) for e in self._s.events]


class InMemoryAuthTokenRepository(_Repository, interfaces.AuthTokenRepository):
    def add(self, token: AuthToken) -> AuthToken:
        token.id = self._s.next_id("auth_tokens", token.id)
        self._s.auth_tokens[token.id] = copy(token)
        return token

    def get_by_hash(self, token_hash: str) -> AuthToken | None:
        return next(
            (copy(t) for t in self._s.auth_tokens.values() if t.token_hash == token_hash), None
        )

    def delete_by_hash(self, token_hash: str) -> None:
        for key in [k for k, t in self._s.auth_tokens.items() if t.token_hash == token_hash]:
            del self._s.auth_tokens[key]

    def delete_by_user(self, user_id: int) -> None:
        for key in [k for k, t in self._s.auth_tokens.items() if t.user_id == user_id]:
            del self._s.auth_tokens[key]

    def delete_expired(self, now: datetime) -> None:
        for key in [k for k, t in self._s.auth_tokens.items() if t.expires_at <= now]:
            del self._s.auth_tokens[key]


class InMemoryPasswordResetTokenRepository(_Repository, interfaces.PasswordResetTokenRepository):
    def add(self, token: PasswordResetToken) -> PasswordResetToken:
        token.id = self._s.next_id("reset_tokens", token.id)
        self._s.reset_tokens[token.id] = copy(token)
        return token

    def get_by_hash(self, token_hash: str) -> PasswordResetToken | None:
        return next(
            (copy(t) for t in self._s.reset_tokens.values() if t.token_hash == token_hash), None
        )

    def delete_by_hash(self, token_hash: str) -> None:
        for key in [k for k, t in self._s.reset_tokens.items() if t.token_hash == token_hash]:
            del self._s.reset_tokens[key]

    def consume(self, token_hash: str, now: datetime) -> int | None:
        found = next(
            (
                t
                for t in self._s.reset_tokens.values()
                if t.token_hash == token_hash and t.expires_at > now
            ),
            None,
        )
        if found is None:
            return None
        del self._s.reset_tokens[found.id]
        return found.user_id

    def delete_by_user(self, user_id: int) -> None:
        for key in [k for k, t in self._s.reset_tokens.items() if t.user_id == user_id]:
            del self._s.reset_tokens[key]

    def delete_expired(self, now: datetime) -> None:
        for key in [k for k, t in self._s.reset_tokens.items() if t.expires_at <= now]:
            del self._s.reset_tokens[key]


class InMemoryFailedLoginRepository(_Repository, interfaces.FailedLoginRepository):
    def register(self, login: str) -> int:
        self._s.failed_logins[login] = self._s.failed_logins.get(login, 0) + 1
        return self._s.failed_logins[login]

    def reset(self, login: str) -> None:
        self._s.failed_logins.pop(login, None)


class InMemoryMaterialRevisionRepository(_Repository, interfaces.MaterialRevisionRepository):
    def push(self, material_id: int, memento: MaterialMemento) -> None:
        history = self._s.revisions.setdefault(material_id, [])
        history.append(memento)
        del history[:-MAX_REVISIONS_PER_MATERIAL]

    def pop(self, material_id: int) -> MaterialMemento | None:
        history = self._s.revisions.get(material_id)
        return history.pop() if history else None

    def has_history(self, material_id: int) -> bool:
        return bool(self._s.revisions.get(material_id))


class InMemoryRepositoryFactory(RepositoryFactory):
    """Семейство репозиториев в памяти; все они работают с одним `Store`."""

    def __init__(self, store: Store | None = None) -> None:
        self.store = store or Store()

    def create_user_repository(self) -> interfaces.UserRepository:
        return InMemoryUserRepository(self.store)

    def create_discipline_repository(self) -> interfaces.DisciplineRepository:
        return InMemoryDisciplineRepository(self.store)

    def create_topic_repository(self) -> interfaces.TopicRepository:
        return InMemoryTopicRepository(self.store)

    def create_material_repository(self) -> interfaces.MaterialRepository:
        return InMemoryMaterialRepository(self.store)

    def create_favorite_repository(self) -> interfaces.FavoriteRepository:
        return InMemoryFavoriteRepository(self.store)

    def create_event_repository(self) -> interfaces.EventRepository:
        return InMemoryEventRepository(self.store)

    def create_password_reset_token_repository(self) -> interfaces.PasswordResetTokenRepository:
        return InMemoryPasswordResetTokenRepository(self.store)

    def create_auth_token_repository(self) -> interfaces.AuthTokenRepository:
        return InMemoryAuthTokenRepository(self.store)

    def create_failed_login_repository(self) -> interfaces.FailedLoginRepository:
        return InMemoryFailedLoginRepository(self.store)

    def create_material_revision_repository(self) -> interfaces.MaterialRevisionRepository:
        return InMemoryMaterialRevisionRepository(self.store)


__all__ = ["InMemoryRepositoryFactory", "Store"]
