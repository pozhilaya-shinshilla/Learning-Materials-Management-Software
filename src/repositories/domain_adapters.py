"""Адаптеры: интерфейсы сервисов (`interfaces.py`) поверх SQLAlchemy-репозиториев.

Сервисы и CLI работают с доменными dataclass-ами и ничего не знают об ORM. Репозитории из
`sqlalchemy.py` работают с ORM-моделями, как в методичке. Адаптер связывает их: берёт
ORM-модель из репозитория и превращает её в доменный объект классом-маппером
(`src/database/mappers.py`), а при записи переносит поля обратно.

Превращение происходит внутри открытой сессии, поэтому наружу не попадают ленивые связи
и не бывает `DetachedInstanceError`. Транзакцию адаптер не фиксирует: это делает владелец
сессии (`src/database/transaction.py`).
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator
from contextlib import contextmanager
from datetime import datetime

from sqlalchemy.exc import IntegrityError

from src.configs.config import MAX_REVISIONS_PER_MATERIAL
from src.database.mappers import (
    AuthTokenMapper,
    DisciplineMapper,
    EventMapper,
    FavoriteMapper,
    MaterialMapper,
    MaterialRevisionMapper,
    PasswordResetTokenMapper,
    TopicMapper,
    UserMapper,
)
from src.database.models import FailedLoginEntity
from src.domain.exceptions import (
    AccountDeletedError,
    DisciplineNotEmptyError,
    DomainError,
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
from src.repositories import sqlalchemy as orm
from src.repositories.sqlalchemy import SessionLike

type _ConflictMap = dict[str, Callable[[], DomainError]]


def _violated_constraint(error: IntegrityError) -> str:
    """Имя нарушенного ограничения (или уникального индекса) из ответа PostgreSQL."""
    diag = getattr(error.orig, "diag", None)
    return getattr(diag, "constraint_name", None) or ""


@contextmanager
def _translate_conflicts(session: SessionLike, conflicts: _ConflictMap) -> Iterator[None]:
    """Превратить нарушение ограничения БД в доменную ошибку.

    Проверки вида «такого логина ещё нет» выполняются до записи, а другая транзакция успевает
    занять логин между проверкой и `INSERT`. Тогда последнее слово за уникальным индексом БД, и
    пользователь должен увидеть обычное «Логин занят», а не трассировку `IntegrityError`.

    Запись идёт внутри SAVEPOINT: после ошибки откатывается только он, а сессия остаётся
    рабочей, и `TransactionManager` может спокойно зафиксировать или откатить транзакцию.
    Ограничения, которых нет в `conflicts`, пробрасываются как есть: это уже настоящий сбой.
    """
    try:
        with session.begin_nested():
            yield
    except IntegrityError as error:
        factory = conflicts.get(_violated_constraint(error))
        if factory is None:
            raise
        raise factory() from error


class SqlUserRepository(interfaces.UserRepository):
    """Пользователи в PostgreSQL."""

    def __init__(self, session: SessionLike) -> None:
        self._session = session
        self._repository = orm.UserRepository(session)
        self._mapper = UserMapper()

    def add(self, user: User) -> User:
        """Сохранить нового пользователя и вернуть его с присвоенным id."""
        with _translate_conflicts(
            self._session,
            {
                "uq_users_login": lambda: DuplicateLoginError(login=user.login),
                "uq_users_lower_email": lambda: DuplicateEmailError(email=user.email),
            },
        ):
            entity = self._repository.add(self._mapper.to_entity(user))
        user.id = entity.id
        return user

    def get_by_id(self, user_id: int) -> User | None:
        """Вернуть пользователя с указанным id или None, если его нет."""
        entity = self._repository.get_by_id(user_id)
        return self._mapper.to_domain(entity) if entity else None

    def get_by_login(self, login: str) -> User | None:
        """Вернуть пользователя с указанным логином или None, если его нет."""
        entity = self._repository.get_by_login(login)
        return self._mapper.to_domain(entity) if entity else None

    def get_by_email(self, email: str) -> User | None:
        """Вернуть пользователя с указанным email (без учёта регистра) или None."""
        entity = self._repository.get_by_email(email)
        return self._mapper.to_domain(entity) if entity else None

    def list_all(self) -> list[User]:
        """Вернуть всех зарегистрированных пользователей (по возрастанию id)."""
        return [self._mapper.to_domain(e) for e in self._repository.get_all()]

    def update(self, user: User) -> None:
        """Сохранить изменения существующего пользователя."""
        entity = self._repository.get_by_id(user.id)
        if entity is not None:
            self._mapper.apply(entity, user)
            self._repository.update(entity)

    def delete(self, user_id: int) -> None:
        """Удалить пользователя: закладки удалит БД, у материалов и событий обнулится автор."""
        entity = self._repository.get_by_id(user_id)
        if entity is not None:
            self._repository.delete(entity)
            # БД изменила другие строки (обнулила автора): загруженные копии устарели.
            self._session.expire_all()

    def lock(self, user_id: int) -> bool:
        """Заблокировать строку пользователя до конца транзакции; False, если его нет."""
        return self._repository.lock(user_id)

    def lock_many(self, user_ids: Iterable[int], *, exclusive: bool = False) -> set[int]:
        """Заблокировать строки пользователей по возрастанию id; вернуть id существующих."""
        return self._repository.lock_many(user_ids, exclusive=exclusive)


class SqlDisciplineRepository(interfaces.DisciplineRepository):
    """Дисциплины в PostgreSQL."""

    def __init__(self, session: SessionLike) -> None:
        self._session = session
        self._repository = orm.DisciplineRepository(session)
        self._mapper = DisciplineMapper()

    def _conflicts(self, discipline: Discipline) -> _ConflictMap:
        return {"uq_disciplines_lower_name": lambda: DuplicateDisciplineError(name=discipline.name)}

    def add(self, discipline: Discipline) -> Discipline:
        """Сохранить новую дисциплину и вернуть её с присвоенным id."""
        with _translate_conflicts(self._session, self._conflicts(discipline)):
            entity = self._repository.add(self._mapper.to_entity(discipline))
        discipline.id = entity.id
        return discipline

    def get_by_id(self, discipline_id: int) -> Discipline | None:
        """Вернуть дисциплину с указанным id или None, если её нет."""
        entity = self._repository.get_by_id(discipline_id)
        return self._mapper.to_domain(entity) if entity else None

    def update(self, discipline: Discipline) -> None:
        """Сохранить изменения существующей дисциплины."""
        entity = self._repository.get_by_id(discipline.id)
        if entity is not None:
            self._mapper.apply(entity, discipline)
            with _translate_conflicts(self._session, self._conflicts(discipline)):
                self._repository.update(entity)

    def delete(self, discipline_id: int) -> None:
        """Удалить дисциплину; внешний ключ БД не даёт удалить ту, в которой есть темы."""
        entity = self._repository.get_by_id(discipline_id)
        if entity is None:
            return
        name = entity.name
        conflicts: _ConflictMap = {
            "fk_topics_discipline_id_disciplines": lambda: DisciplineNotEmptyError(name=name)
        }
        with _translate_conflicts(self._session, conflicts):
            self._repository.delete(entity)

    def get_by_name(self, name: str) -> Discipline | None:
        """Вернуть дисциплину с указанным названием (без учёта регистра) или None."""
        entity = self._repository.get_by_name(name)
        return self._mapper.to_domain(entity) if entity else None

    def list_all(self) -> list[Discipline]:
        """Вернуть все дисциплины (по возрастанию id)."""
        return [self._mapper.to_domain(e) for e in self._repository.get_all()]


class SqlTopicRepository(interfaces.TopicRepository):
    """Темы в PostgreSQL."""

    def __init__(self, session: SessionLike) -> None:
        self._session = session
        self._repository = orm.TopicRepository(session)
        self._mapper = TopicMapper()

    def _conflicts(self, topic: Topic) -> _ConflictMap:
        return {"uq_topics_discipline_id_lower_name": lambda: DuplicateTopicError(name=topic.name)}

    def add(self, topic: Topic) -> Topic:
        """Сохранить новую тему и вернуть её с присвоенным id."""
        with _translate_conflicts(self._session, self._conflicts(topic)):
            entity = self._repository.add(self._mapper.to_entity(topic))
        topic.id = entity.id
        return topic

    def get_by_id(self, topic_id: int) -> Topic | None:
        """Вернуть тему с указанным id или None, если её нет."""
        entity = self._repository.get_by_id(topic_id)
        return self._mapper.to_domain(entity) if entity else None

    def update(self, topic: Topic) -> None:
        """Сохранить изменения существующей темы."""
        entity = self._repository.get_by_id(topic.id)
        if entity is not None:
            self._mapper.apply(entity, topic)
            with _translate_conflicts(self._session, self._conflicts(topic)):
                self._repository.update(entity)

    def delete(self, topic_id: int) -> None:
        """Удалить тему; составной внешний ключ БД не даёт удалить ту, к которой есть материалы."""
        entity = self._repository.get_by_id(topic_id)
        if entity is None:
            return
        name = entity.name
        conflicts: _ConflictMap = {
            "fk_materials_topic_id_discipline_id_topics": lambda: TopicInUseError(name=name)
        }
        with _translate_conflicts(self._session, conflicts):
            self._repository.delete(entity)

    def get_by_name(self, discipline_id: int, name: str) -> Topic | None:
        """Вернуть тему дисциплины с указанным названием (без учёта регистра) или None."""
        entity = self._repository.get_by_name(discipline_id, name)
        return self._mapper.to_domain(entity) if entity else None

    def list_by_discipline(self, discipline_id: int) -> list[Topic]:
        """Вернуть все темы указанной дисциплины (по возрастанию id)."""
        return [
            self._mapper.to_domain(e) for e in self._repository.get_by_discipline(discipline_id)
        ]


class SqlMaterialRepository(interfaces.MaterialRepository):
    """Материалы в PostgreSQL."""

    def __init__(self, session: SessionLike) -> None:
        self._session = session
        self._repository = orm.MaterialRepository(session)
        self._users = orm.UserRepository(session)
        self._mapper = MaterialMapper()

    def add(self, material: Material) -> Material:
        """Сохранить новый материал и вернуть его с присвоенным id."""
        # Автора могли удалить, пока шла загрузка: это не сбой, а завершённый сеанс.
        with _translate_conflicts(
            self._session, {"fk_materials_author_id_users": AccountDeletedError}
        ):
            entity = self._repository.add(self._mapper.to_entity(material))
        material.id = entity.id
        return material

    def get_by_id(self, material_id: int) -> Material | None:
        """Вернуть материал с указанным id или None, если его нет."""
        entity = self._repository.get_by_id(material_id)
        return self._mapper.to_domain(entity) if entity else None

    def get_by_id_for_update(
        self, material_id: int, *, acting_user_id: int | None = None
    ) -> Material | None:
        """Вернуть материал, заблокировав его строку; чужие правки выстраиваются в очередь.

        Сначала блокируются пользователи (действующий и автор, по возрастанию id), потом сам
        материал: тот же порядок, в котором идёт удаление пользователя. Автор известен только
        из материала, поэтому его читают без блокировки; он меняется лишь при удалении автора
        (`SET NULL`), а это пользователь, которого мы как раз блокируем.
        """
        exists, author_id = self._repository.find_author(material_id)
        if not exists:
            return None
        wanted = {uid for uid in (acting_user_id, author_id) if uid is not None}
        locked = self._users.lock_many(wanted)
        if acting_user_id is not None and acting_user_id not in locked:
            raise AccountDeletedError()
        entity = self._repository.get_for_update(material_id)
        return self._mapper.to_domain(entity) if entity else None

    def list_all(self) -> list[Material]:
        """Вернуть все материалы (по возрастанию id)."""
        return [self._mapper.to_domain(e) for e in self._repository.get_all()]

    def search(self, query: MaterialSearchQuery) -> list[Material]:
        """Найти материалы по запросу: отбор, полнотекстовый поиск и сортировка делает БД."""
        return [self._mapper.to_domain(e) for e in self._repository.search(query)]

    def count(self, query: MaterialSearchQuery) -> int:
        """Посчитать материалы, подходящие под запрос (без страницы)."""
        return self._repository.count(query)

    def update(self, material: Material) -> None:
        """Сохранить изменения существующего материала (`updated_at` обновится само)."""
        entity = self._repository.get_by_id(material.id)
        if entity is not None:
            self._mapper.apply(entity, material)
            self._repository.update(entity)

    def delete(self, material_id: int) -> None:
        """Удалить материал; закладки на него удалит БД (CASCADE)."""
        entity = self._repository.get_by_id(material_id)
        if entity is not None:
            self._repository.delete(entity)
            self._session.expire_all()


class SqlFavoriteRepository(interfaces.FavoriteRepository):
    """Избранное в PostgreSQL: связь «многие ко многим» пользователей и материалов."""

    def __init__(self, session: SessionLike) -> None:
        self._session = session
        self._users = orm.UserRepository(session)
        self._materials = orm.MaterialRepository(session)
        self._mapper = FavoriteMapper()

    def add(self, favorite: Favorite) -> Favorite:
        """Добавить материал в избранное; дубль отклонит составной первичный ключ.

        Дату добавления ставит БД (`DEFAULT now()`), поэтому возвращается строка из таблицы.
        """
        user = self._users.get_by_id(favorite.user_id)
        material = self._materials.get_by_id(favorite.material_id)
        # Сервис уже проверил оба id, но между проверкой и записью другой пользователь
        # мог удалить материал или учётную запись.
        if user is None:
            raise AccountDeletedError()
        if material is None:
            raise MaterialNotFoundError(material_id=favorite.material_id)
        with _translate_conflicts(
            self._session,
            {
                "pk_favorites": lambda: DuplicateFavoriteError(title=material.title),
                "fk_favorites_material_id_materials": lambda: MaterialNotFoundError(
                    material_id=favorite.material_id
                ),
                "fk_favorites_user_id_users": AccountDeletedError,
            },
        ):
            self._users.add_favorite(user, material)
        row = self._users.get_favorite_row(favorite.user_id, favorite.material_id)
        return self._mapper.to_domain(row)

    def remove(self, user_id: int, material_id: int) -> None:
        """Удалить закладку из избранного, если она есть."""
        user = self._users.get_by_id(user_id)
        material = self._materials.get_by_id(material_id)
        if user is not None and material is not None:
            self._users.remove_favorite(user, material)

    def list_by_user(self, user_id: int) -> list[Favorite]:
        """Вернуть все закладки указанного пользователя (от старых к новым)."""
        return [self._mapper.to_domain(row) for row in self._users.get_favorite_rows(user_id)]

    def exists(self, user_id: int, material_id: int) -> bool:
        """Вернуть, добавил ли пользователь материал в избранное."""
        return self._users.has_favorite(user_id, material_id)


class SqlEventRepository(interfaces.EventRepository):
    """Журнал событий в PostgreSQL."""

    def __init__(self, session: SessionLike) -> None:
        self._session = session
        self._repository = orm.EventRepository(session)
        self._mapper = EventMapper()

    def add(self, event: Event) -> Event:
        """Сохранить новое событие и вернуть его с присвоенным id."""
        # Пользователя могли удалить посреди его же операции: операция откатится целиком.
        with _translate_conflicts(self._session, {"fk_events_user_id_users": AccountDeletedError}):
            entity = self._repository.add(self._mapper.to_entity(event))
        event.id = entity.id
        return event

    def list_all(self) -> list[Event]:
        """Вернуть все события журнала от старых к новым."""
        return [self._mapper.to_domain(e) for e in self._repository.get_all()]


class SqlAuthTokenRepository(interfaces.AuthTokenRepository):
    """Токены доступа к API в PostgreSQL (общие для всех процессов приложения)."""

    def __init__(self, session: SessionLike) -> None:
        self._repository = orm.AuthTokenRepository(session)
        self._mapper = AuthTokenMapper()

    def add(self, token: AuthToken) -> AuthToken:
        """Сохранить выданный токен и вернуть его с присвоенным id."""
        entity = self._repository.add(self._mapper.to_entity(token))
        token.id = entity.id
        return token

    def get_by_hash(self, token_hash: str) -> AuthToken | None:
        """Вернуть токен по его хешу или None, если такого нет."""
        entity = self._repository.get_by_hash(token_hash)
        return self._mapper.to_domain(entity) if entity else None

    def delete_by_hash(self, token_hash: str) -> None:
        """Удалить токен (выход из системы)."""
        self._repository.delete_by_hash(token_hash)

    def delete_by_user(self, user_id: int) -> None:
        """Удалить все токены пользователя."""
        self._repository.delete_by_user(user_id)

    def delete_expired(self, now: datetime) -> None:
        """Удалить токены, срок которых истёк к моменту `now`."""
        self._repository.delete_expired(now)


class SqlPasswordResetTokenRepository(interfaces.PasswordResetTokenRepository):
    """Коды восстановления пароля в PostgreSQL (общие для всех процессов приложения)."""

    def __init__(self, session: SessionLike) -> None:
        self._repository = orm.PasswordResetTokenRepository(session)
        self._mapper = PasswordResetTokenMapper()

    def add(self, token: PasswordResetToken) -> PasswordResetToken:
        """Сохранить выданный код и вернуть его с присвоенным id."""
        entity = self._repository.add(self._mapper.to_entity(token))
        token.id = entity.id
        return token

    def get_by_hash(self, token_hash: str) -> PasswordResetToken | None:
        """Вернуть код по его хешу или None, если такого нет."""
        entity = self._repository.get_by_hash(token_hash)
        return self._mapper.to_domain(entity) if entity else None

    def delete_by_hash(self, token_hash: str) -> None:
        """Удалить код (использован или истёк)."""
        self._repository.delete_by_hash(token_hash)

    def consume(self, token_hash: str, now: datetime) -> int | None:
        """Атомарно списать действующий код и вернуть id владельца (или None)."""
        return self._repository.consume(token_hash, now)

    def delete_by_user(self, user_id: int) -> None:
        """Удалить все коды пользователя."""
        self._repository.delete_by_user(user_id)

    def delete_expired(self, now: datetime) -> None:
        """Удалить все коды, срок которых истёк к моменту `now`."""
        self._repository.delete_expired(now)


class SqlFailedLoginRepository(interfaces.FailedLoginRepository):
    """Неудачные попытки входа в PostgreSQL: счётчик общий для всех процессов."""

    def __init__(self, session: SessionLike) -> None:
        self._repository = orm.FailedLoginRepository(session)

    def register(self, login: str) -> int:
        """Записать неудачную попытку и вернуть число попыток подряд для этого логина."""
        self._repository.lock_login(login)
        self._repository.add(FailedLoginEntity(login=login))
        return self._repository.count_by_login(login)

    def reset(self, login: str) -> None:
        """Забыть попытки логина (успешный вход или отправленное оповещение)."""
        self._repository.delete_by_login(login)


class SqlMaterialRevisionRepository(interfaces.MaterialRevisionRepository):
    """Снимки материалов в PostgreSQL: история правок переживает перезапуск и общая для процессов.

    Это опекун из паттерна Memento: хранит снимки, но не заглядывает внутрь. На материал
    хранится не более `MAX_REVISIONS_PER_MATERIAL` последних.
    """

    def __init__(self, session: SessionLike) -> None:
        self._repository = orm.MaterialRevisionRepository(session)
        self._mapper = MaterialRevisionMapper()

    def push(self, material_id: int, memento: MaterialMemento) -> None:
        """Запомнить состояние материала перед изменением; лишние старые снимки удаляются."""
        self._repository.add(self._mapper.to_entity(material_id, memento))
        for old in self._repository.get_by_material(material_id)[MAX_REVISIONS_PER_MATERIAL:]:
            self._repository.delete(old)

    def pop(self, material_id: int) -> MaterialMemento | None:
        """Достать и удалить последний снимок или вернуть None, если отменять нечего."""
        entity = self._repository.get_latest(material_id)
        if entity is None:
            return None
        memento = self._mapper.to_domain(entity)
        self._repository.delete(entity)
        return memento

    def has_history(self, material_id: int) -> bool:
        """Вернуть, есть ли у материала изменения, которые можно отменить."""
        return self._repository.get_latest(material_id) is not None
