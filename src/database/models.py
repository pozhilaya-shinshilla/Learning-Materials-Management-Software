"""ORM-модели SQLAlchemy: отражение ER-диаграммы (`docs/er.md`).

Это *не* доменные модели. Доменные `dataclass`-ы из `src/domain/models.py` ничего не знают
о БД; преобразование в обе стороны выполняют классы-мапперы (`src/database/mappers.py`).

Каскады: ORM и база — не одно и то же. Правила удаления лежат в самой БД (`ON DELETE ...`),
а у `relationship` стоит то, что с ними согласовано:

| Удаляем                    | База               | ORM                                   |
|----------------------------|--------------------|---------------------------------------|
| пользователя               | закладки CASCADE   | `favorite_materials`: passive_deletes |
|                            | материалы SET NULL | `materials`: каскада нет              |
|                            | события SET NULL   | `events`: каскада нет                 |
| материал                   | закладки CASCADE   | `favorited_by`: passive_deletes       |
| пользователя               | коды сброса CASCADE| `reset_tokens`: delete-orphan         |
| пользователя               | токены API CASCADE | `auth_tokens`: delete-orphan          |
| материал                   | снимки правок CASC.| `revisions`: delete-orphan            |
| дисциплину с темами        | RESTRICT           | `topics`: passive_deletes="all"       |
| тему с материалами         | RESTRICT           | `materials`: passive_deletes="all"    |

`passive_deletes=True` — «не загружай связанные объекты, решает база». `"all"` строже: ORM
не обнуляет внешний ключ даже у уже загруженных детей и оставляет отказ (`RESTRICT`) базе.
`cascade="all, delete-orphan"` стоит только у «собственных» детей, которые не живут без
родителя: коды восстановления пароля пользователя и снимки правок материала (вместе с
`passive_deletes=True`: само удаление выполняет база). Закладки удаляет база.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Identity,
    Index,
    String,
    Table,
    Text,
    UniqueConstraint,
    func,
    literal,
    literal_column,
)
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.dialects.postgresql import to_tsvector
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.base import Base
from src.domain.enums import AccountStatus, EventType, FileType, Role


def _enum(enum_class: type, name: str) -> SqlEnum:
    """Нативный enum PostgreSQL со значениями `value`, а не именами членов Python-enum.

    Без `values_callable` в БД попали бы `STUDENT`, `ADMIN`, а ER и `StrEnum` используют
    `student`, `admin`.
    """
    return SqlEnum(
        enum_class,
        name=name,
        values_callable=lambda members: [member.value for member in members],
        validate_strings=True,
    )


def _timestamptz() -> Mapped[datetime]:
    """Столбец `timestamptz NOT NULL DEFAULT now()`."""
    return mapped_column(DateTime(timezone=True), server_default=func.now())


# Промежуточная таблица «многие ко многим»: пользователи <-> материалы (закладки).
# Оба столбца входят в составной первичный ключ: одна закладка на пару.
favorites = Table(
    "favorites",
    Base.metadata,
    Column("user_id", ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column(
        "material_id",
        ForeignKey("materials.id", ondelete="CASCADE"),
        primary_key=True,
        index=True,
    ),
    Column("added_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
)


class UserEntity(Base):
    """Учётная запись пользователя."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    login: Mapped[str] = mapped_column(String(50), unique=True)
    email: Mapped[str] = mapped_column(String(255))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[Role] = mapped_column(_enum(Role, "user_role"))
    status: Mapped[AccountStatus] = mapped_column(
        _enum(AccountStatus, "account_status"), server_default=AccountStatus.ACTIVE.value
    )
    created_at: Mapped[datetime] = _timestamptz()

    # Один ко многим: материалы автора. БД обнуляет `materials.author_id` (SET NULL).
    materials: Mapped[list[MaterialEntity]] = relationship(
        back_populates="author", passive_deletes=True
    )
    # Один ко многим: журнал сохраняется, `events.user_id` становится NULL (SET NULL).
    events: Mapped[list[EventEntity]] = relationship(back_populates="user", passive_deletes=True)
    # Многие ко многим через `favorites`; закладки удаляет БД (CASCADE).
    favorite_materials: Mapped[list[MaterialEntity]] = relationship(
        secondary=favorites, back_populates="favorited_by", passive_deletes=True
    )
    # Один ко многим: выданные коды восстановления пароля; удаляются вместе с пользователем.
    reset_tokens: Mapped[list[PasswordResetTokenEntity]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )
    # Один ко многим: токены доступа к API; удаляются вместе с пользователем.
    auth_tokens: Mapped[list[AuthTokenEntity]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )


# Уникальность email без учёта регистра — как `UserRepository.get_by_email`.
Index("uq_users_lower_email", func.lower(UserEntity.email), unique=True)


class DisciplineEntity(Base):
    """Учебная дисциплина."""

    __tablename__ = "disciplines"

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    name: Mapped[str] = mapped_column(String(100))

    # Один ко многим; RESTRICT: дисциплину с темами удалить нельзя.
    topics: Mapped[list[TopicEntity]] = relationship(
        back_populates="discipline", passive_deletes="all"
    )
    # «Дисциплина -> материалы» обеспечивает составной FK через тему; отдельного внешнего
    # ключа на `disciplines` у материалов нет, поэтому связь только для чтения.
    materials: Mapped[list[MaterialEntity]] = relationship(
        primaryjoin="DisciplineEntity.id == foreign(MaterialEntity.discipline_id)",
        back_populates="discipline",
        viewonly=True,
    )


Index("uq_disciplines_lower_name", func.lower(DisciplineEntity.name), unique=True)


class TopicEntity(Base):
    """Тема внутри дисциплины."""

    __tablename__ = "topics"
    __table_args__ = (
        # Цель составного внешнего ключа из `materials`: тема материала принадлежит
        # дисциплине материала, и БД не даёт нарушить это правило.
        UniqueConstraint("id", "discipline_id", name="uq_topics_id_discipline_id"),
    )

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    # Отдельный индекс не нужен: его заменяет уникальный `(discipline_id, lower(name))`.
    discipline_id: Mapped[int] = mapped_column(ForeignKey("disciplines.id", ondelete="RESTRICT"))
    name: Mapped[str] = mapped_column(String(100))

    discipline: Mapped[DisciplineEntity] = relationship(back_populates="topics")
    # RESTRICT через составной FK: тему с материалами удалить нельзя.
    materials: Mapped[list[MaterialEntity]] = relationship(
        back_populates="topic", passive_deletes="all"
    )


# Тема уникальна внутри дисциплины без учёта регистра.
Index(
    "uq_topics_discipline_id_lower_name",
    TopicEntity.discipline_id,
    func.lower(TopicEntity.name),
    unique=True,
)


SEARCH_CONFIG = "russian"


def material_search_vector(*, for_index: bool = False):
    """Вектор полнотекстового поиска материала: название и описание, русская морфология.

    Конфигурация `russian` приводит слова к основе (Snowball) и для русских, и для английских
    слов, отбрасывает стоп-слова и понимает «ё». Выражение в индексе и в запросе должно
    совпадать: только тогда PostgreSQL воспользуется GIN-индексом (это проверяет тест).

    `for_index=True` собирает то же выражение из значений-параметров: в DDL SQLAlchemy
    подставляет их как литералы, а `literal_column` мешал бы привязать индекс к таблице
    (тогда Alembic не знал бы, что такой индекс описан в моделях).
    """
    if for_index:
        config, separator = literal(SEARCH_CONFIG), literal(" ")
    else:
        config = literal_column(f"'{SEARCH_CONFIG}'::regconfig")
        separator = literal_column("' '")
    return to_tsvector(config, MaterialEntity.title + separator + MaterialEntity.description)


class MaterialEntity(Base):
    """Учебный материал."""

    __tablename__ = "materials"
    __table_args__ = (
        ForeignKeyConstraint(
            ["topic_id", "discipline_id"],
            ["topics.id", "topics.discipline_id"],
            ondelete="RESTRICT",
            name="fk_materials_topic_id_discipline_id_topics",
        ),
        CheckConstraint("file_size_bytes >= 0", name="file_size_non_negative"),
        Index("ix_materials_discipline_id_topic_id", "discipline_id", "topic_id"),
    )

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    title: Mapped[str] = mapped_column(String(200), index=True)
    description: Mapped[str] = mapped_column(Text)
    discipline_id: Mapped[int] = mapped_column()
    topic_id: Mapped[int] = mapped_column()
    # Автора можно удалить, а материал остаётся: `author_id` становится NULL.
    author_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    file_name: Mapped[str] = mapped_column(String(255))
    file_type: Mapped[FileType] = mapped_column(_enum(FileType, "file_type"))
    file_size_bytes: Mapped[int] = mapped_column(BigInteger)
    storage_path: Mapped[str] = mapped_column(String(500))
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    author: Mapped[UserEntity | None] = relationship(back_populates="materials")
    # Запись `topic` синхронизирует сразу оба столбца составного внешнего ключа.
    topic: Mapped[TopicEntity] = relationship(back_populates="materials")
    discipline: Mapped[DisciplineEntity] = relationship(
        primaryjoin="foreign(MaterialEntity.discipline_id) == DisciplineEntity.id",
        back_populates="materials",
        viewonly=True,
    )
    favorited_by: Mapped[list[UserEntity]] = relationship(
        secondary=favorites, back_populates="favorite_materials", passive_deletes=True
    )
    # Один ко многим: снимки прежних версий для отмены правок; удаляются вместе с материалом.
    revisions: Mapped[list[MaterialRevisionEntity]] = relationship(
        back_populates="material", cascade="all, delete-orphan", passive_deletes=True
    )


# Полнотекстовый поиск по названию и описанию: GIN-индекс по тому же выражению, что в запросе.
Index("ix_materials_search_vector", material_search_vector(for_index=True), postgresql_using="gin")


class EventEntity(Base):
    """Запись журнала событий."""

    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    # NULL у гостя и у события, чей пользователь был удалён (SET NULL).
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    event_type: Mapped[EventType] = mapped_column(_enum(EventType, "event_type"))
    target: Mapped[str] = mapped_column(String(255))
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )

    user: Mapped[UserEntity | None] = relationship(back_populates="events")


class PasswordResetTokenEntity(Base):
    """Код восстановления пароля. Хранится только хеш; код одноразовый и со сроком жизни."""

    __tablename__ = "password_reset_tokens"

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = _timestamptz()
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)

    user: Mapped[UserEntity] = relationship(back_populates="reset_tokens")


class AuthTokenEntity(Base):
    """Токен доступа к REST API. Хранится только хеш; токен можно отозвать (выход) и он истекает."""

    __tablename__ = "auth_tokens"

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = _timestamptz()
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)

    user: Mapped[UserEntity] = relationship(back_populates="auth_tokens")


class FailedLoginEntity(Base):
    """Неудачная попытка входа: по числу строк логина считаются попытки подряд.

    Это не связь с `users`: попытки бывают и под несуществующими логинами.
    """

    __tablename__ = "failed_logins"

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    login: Mapped[str] = mapped_column(String(255), index=True)
    occurred_at: Mapped[datetime] = _timestamptz()


class MaterialRevisionEntity(Base):
    """Снимок прежнего состояния материала (Memento): стек для отмены правок.

    `discipline_id` и `topic_id` без внешних ключей: это значения на момент снимка.
    """

    __tablename__ = "material_revisions"

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    material_id: Mapped[int] = mapped_column(
        ForeignKey("materials.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    discipline_id: Mapped[int] = mapped_column()
    topic_id: Mapped[int] = mapped_column()
    created_at: Mapped[datetime] = _timestamptz()

    material: Mapped[MaterialEntity] = relationship(back_populates="revisions")
