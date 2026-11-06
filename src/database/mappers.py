"""Классы-мапперы: перевод между доменными `dataclass`-ами и ORM-сущностями.

Паттерн Data Mapper: домен (`src/domain/models.py`) не знает о SQLAlchemy, а ORM-сущности
(`src/database/models.py`) не содержат бизнес-логики. Каждый маппер умеет три вещи:
- `to_domain(entity)` — прочитать строку БД как доменный объект;
- `to_entity(model)` — создать новую ORM-сущность для `INSERT`;
- `apply(entity, model)` — перенести изменённые поля в уже загруженную сущность (`UPDATE`).

`FavoriteMapper` и `MaterialRevisionMapper` намеренно не наследуют `Mapper`: у закладки нет
собственной ORM-сущности (это таблица связи `secondary`), а снимку материала для `to_entity`
нужен ещё `material_id`, поэтому сигнатуры отличаются от общего контракта.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from src.database.models import (
    AuthTokenEntity,
    DisciplineEntity,
    EventEntity,
    MaterialEntity,
    MaterialRevisionEntity,
    PasswordResetTokenEntity,
    TopicEntity,
    UserEntity,
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


class Mapper[DomainT, EntityT](ABC):
    """Контракт маппера между доменной моделью и ORM-сущностью."""

    @abstractmethod
    def to_domain(self, entity: EntityT) -> DomainT:
        """Построить доменный объект по ORM-сущности."""

    @abstractmethod
    def to_entity(self, model: DomainT) -> EntityT:
        """Построить новую ORM-сущность по доменному объекту."""

    @abstractmethod
    def apply(self, entity: EntityT, model: DomainT) -> None:
        """Перенести изменяемые поля доменного объекта в существующую сущность."""


class UserMapper(Mapper[User, UserEntity]):
    """User <-> UserEntity. `created_at` есть только в БД и в домен не попадает."""

    def to_domain(self, entity: UserEntity) -> User:
        """Построить `User` по строке `users`."""
        return User(
            id=entity.id,
            login=entity.login,
            email=entity.email,
            password_hash=entity.password_hash,
            role=entity.role,
            status=entity.status,
        )

    def to_entity(self, model: User) -> UserEntity:
        """Создать `UserEntity`; `id=0` («ещё не сохранён») оставляет выдачу id базе."""
        entity = UserEntity(
            login=model.login,
            email=model.email,
            password_hash=model.password_hash,
            role=model.role,
            status=model.status,
        )
        if model.id:
            entity.id = model.id
        return entity

    def apply(self, entity: UserEntity, model: User) -> None:
        """Обновить поля существующей строки `users`."""
        entity.login = model.login
        entity.email = model.email
        entity.password_hash = model.password_hash
        entity.role = model.role
        entity.status = model.status


class DisciplineMapper(Mapper[Discipline, DisciplineEntity]):
    """Discipline <-> DisciplineEntity."""

    def to_domain(self, entity: DisciplineEntity) -> Discipline:
        """Построить `Discipline` по строке `disciplines`."""
        return Discipline(id=entity.id, name=entity.name)

    def to_entity(self, model: Discipline) -> DisciplineEntity:
        """Создать `DisciplineEntity`; `id=0` оставляет выдачу id базе."""
        entity = DisciplineEntity(name=model.name)
        if model.id:
            entity.id = model.id
        return entity

    def apply(self, entity: DisciplineEntity, model: Discipline) -> None:
        """Обновить название дисциплины."""
        entity.name = model.name


class TopicMapper(Mapper[Topic, TopicEntity]):
    """Topic <-> TopicEntity."""

    def to_domain(self, entity: TopicEntity) -> Topic:
        """Построить `Topic` по строке `topics`."""
        return Topic(id=entity.id, name=entity.name, discipline_id=entity.discipline_id)

    def to_entity(self, model: Topic) -> TopicEntity:
        """Создать `TopicEntity`; `id=0` оставляет выдачу id базе."""
        entity = TopicEntity(name=model.name, discipline_id=model.discipline_id)
        if model.id:
            entity.id = model.id
        return entity

    def apply(self, entity: TopicEntity, model: Topic) -> None:
        """Обновить название и дисциплину темы."""
        entity.name = model.name
        entity.discipline_id = model.discipline_id


class MaterialMapper(Mapper[Material, MaterialEntity]):
    """Material <-> MaterialEntity. `updated_at` ведёт БД и в домен не попадает."""

    def to_domain(self, entity: MaterialEntity) -> Material:
        """Построить `Material` по строке `materials`; `author_id` может быть None."""
        return Material(
            id=entity.id,
            title=entity.title,
            description=entity.description,
            discipline_id=entity.discipline_id,
            topic_id=entity.topic_id,
            file_name=entity.file_name,
            file_type=entity.file_type,
            file_size_bytes=entity.file_size_bytes,
            author_id=entity.author_id,
            storage_path=entity.storage_path,
            uploaded_at=entity.uploaded_at,
        )

    def to_entity(self, model: Material) -> MaterialEntity:
        """Создать `MaterialEntity`; `id=0` оставляет выдачу id базе."""
        entity = MaterialEntity(
            title=model.title,
            description=model.description,
            discipline_id=model.discipline_id,
            topic_id=model.topic_id,
            author_id=model.author_id,
            file_name=model.file_name,
            file_type=model.file_type,
            file_size_bytes=model.file_size_bytes,
            storage_path=model.storage_path,
            uploaded_at=model.uploaded_at,
        )
        if model.id:
            entity.id = model.id
        return entity

    def apply(self, entity: MaterialEntity, model: Material) -> None:
        """Обновить поля материала; `updated_at` пересчитает `onupdate` модели."""
        entity.title = model.title
        entity.description = model.description
        entity.discipline_id = model.discipline_id
        entity.topic_id = model.topic_id
        entity.author_id = model.author_id
        entity.file_name = model.file_name
        entity.file_type = model.file_type
        entity.file_size_bytes = model.file_size_bytes
        entity.storage_path = model.storage_path
        entity.uploaded_at = model.uploaded_at


class FavoriteMapper:
    """Favorite <-> строка промежуточной таблицы `favorites`.

    У закладки нет собственного ORM-класса: это таблица связи «многие ко многим»
    (`secondary`), поэтому маппер работает со строкой результата .
    """

    def to_domain(self, row: Any) -> Favorite:
        """Построить `Favorite` по строке таблицы `favorites`."""
        return Favorite(user_id=row.user_id, material_id=row.material_id, added_at=row.added_at)


class EventMapper(Mapper[Event, EventEntity]):
    """Event <-> EventEntity."""

    def to_domain(self, entity: EventEntity) -> Event:
        """Построить `Event` по строке `events`; `user_id` может быть None."""
        return Event(
            id=entity.id,
            user_id=entity.user_id,
            event_type=entity.event_type,
            target=entity.target,
            occurred_at=entity.occurred_at,
        )

    def to_entity(self, model: Event) -> EventEntity:
        """Создать `EventEntity`; `id=0` оставляет выдачу id базе."""
        entity = EventEntity(
            user_id=model.user_id,
            event_type=model.event_type,
            target=model.target,
            occurred_at=model.occurred_at,
        )
        if model.id:
            entity.id = model.id
        return entity

    def apply(self, entity: EventEntity, model: Event) -> None:
        """Журнал событий не редактируется, поэтому переносить нечего."""
        return None


class PasswordResetTokenMapper(Mapper[PasswordResetToken, PasswordResetTokenEntity]):
    """PasswordResetToken <-> PasswordResetTokenEntity."""

    def to_domain(self, entity: PasswordResetTokenEntity) -> PasswordResetToken:
        """Построить `PasswordResetToken` по строке `password_reset_tokens`."""
        return PasswordResetToken(
            id=entity.id,
            user_id=entity.user_id,
            token_hash=entity.token_hash,
            expires_at=entity.expires_at,
        )

    def to_entity(self, model: PasswordResetToken) -> PasswordResetTokenEntity:
        """Создать `PasswordResetTokenEntity`; `id=0` оставляет выдачу id базе."""
        entity = PasswordResetTokenEntity(
            user_id=model.user_id, token_hash=model.token_hash, expires_at=model.expires_at
        )
        if model.id:
            entity.id = model.id
        return entity

    def apply(self, entity: PasswordResetTokenEntity, model: PasswordResetToken) -> None:
        """Код не редактируется: его выдают заново, поэтому переносить нечего."""
        return None


class AuthTokenMapper(Mapper[AuthToken, AuthTokenEntity]):
    """AuthToken <-> AuthTokenEntity."""

    def to_domain(self, entity: AuthTokenEntity) -> AuthToken:
        """Построить `AuthToken` по строке `auth_tokens`."""
        return AuthToken(
            id=entity.id,
            user_id=entity.user_id,
            token_hash=entity.token_hash,
            expires_at=entity.expires_at,
        )

    def to_entity(self, model: AuthToken) -> AuthTokenEntity:
        """Создать `AuthTokenEntity`; `id=0` оставляет выдачу id базе."""
        entity = AuthTokenEntity(
            user_id=model.user_id, token_hash=model.token_hash, expires_at=model.expires_at
        )
        if model.id:
            entity.id = model.id
        return entity

    def apply(self, entity: AuthTokenEntity, model: AuthToken) -> None:
        """Токен не редактируется: его выдают заново, поэтому переносить нечего."""
        return None


class MaterialRevisionMapper:
    """MaterialMemento <-> строка `material_revisions`.

    Снимок (`MaterialMemento`) не знает, какому материалу он принадлежит, поэтому
    `material_id` передаётся отдельно.
    """

    def to_domain(self, entity: MaterialRevisionEntity) -> MaterialMemento:
        """Построить снимок материала по строке `material_revisions`."""
        return MaterialMemento(
            title=entity.title,
            description=entity.description,
            discipline_id=entity.discipline_id,
            topic_id=entity.topic_id,
        )

    def to_entity(self, material_id: int, memento: MaterialMemento) -> MaterialRevisionEntity:
        """Создать `MaterialRevisionEntity` для материала `material_id`."""
        return MaterialRevisionEntity(
            material_id=material_id,
            title=memento.title,
            description=memento.description,
            discipline_id=memento.discipline_id,
            topic_id=memento.topic_id,
        )
