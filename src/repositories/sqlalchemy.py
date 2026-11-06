"""SQLAlchemy-репозитории: общая реализация CRUD и конкретные репозитории моделей.

Здесь всё как в методичке (раздел 12): репозиторий работает с ORM-моделями, получает
`Session` снаружи, делает `flush()`, но не фиксирует транзакцию, и не содержит
бизнес-правил. Доменные dataclass-ы и мапперы сюда не попадают: их подключает слой
адаптеров `src/repositories/domain_adapters.py`.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from datetime import datetime

from sqlalchemy import delete, exists, func, literal_column, select
from sqlalchemy.dialects.postgresql import to_tsquery
from sqlalchemy.engine import Row
from sqlalchemy.orm import Session, scoped_session

from src.database.models import (
    SEARCH_CONFIG,
    AuthTokenEntity,
    DisciplineEntity,
    EventEntity,
    FailedLoginEntity,
    MaterialEntity,
    MaterialRevisionEntity,
    PasswordResetTokenEntity,
    TopicEntity,
    UserEntity,
    favorites,
    material_search_vector,
)
from src.domain.search import MaterialSearchQuery
from src.repositories.abstract import AbstractRepository, ModelT
from src.repositories.sorting import DEFAULT_SORT_STRATEGIES

# Номер «пространства» консультативных блокировок счётчика неудачных входов: блокировки
# PostgreSQL общие на всю базу, и чужие ключи не должны совпасть с нашими.
FAILED_LOGIN_LOCK_NAMESPACE = 7001

# `scoped_session` ведёт себя как `Session`; его выдаёт TransactionManager (сессия на операцию).
type SessionLike = Session | scoped_session[Session]


class SQLAlchemyRepository(AbstractRepository[ModelT]):
    """Общая реализация CRUD поверх Session SQLAlchemy."""

    model: type[ModelT]

    def __init__(self, session: SessionLike) -> None:
        self._session: SessionLike = session

    def add(self, entity: ModelT) -> ModelT:
        """Добавить сущность в сессию и отправить INSERT."""
        self._session.add(entity)
        self._session.flush()
        return entity

    def get_by_id(self, entity_id: int) -> ModelT | None:
        """Найти сущность по первичному ключу."""
        return self._session.get(self.model, entity_id)

    def get_all(self) -> list[ModelT]:
        """Вернуть все сущности (порядок не гарантирован: его задают конкретные репозитории)."""
        statement = select(self.model)
        return list(self._session.scalars(statement))

    def update(self, entity: ModelT) -> ModelT:
        """Сохранить изменения существующей сущности."""
        self._session.add(entity)
        self._session.flush()
        return entity

    def delete(self, entity: ModelT) -> None:
        """Удалить сущность."""
        self._session.delete(entity)
        self._session.flush()


class UserRepository(SQLAlchemyRepository[UserEntity]):
    """Репозиторий пользователей (и их избранного)."""

    model = UserEntity

    def get_all(self) -> list[UserEntity]:
        """Вернуть всех пользователей по возрастанию id."""
        statement = select(UserEntity).order_by(UserEntity.id)
        return list(self._session.scalars(statement))

    def get_by_login(self, login: str) -> UserEntity | None:
        """Найти пользователя по логину (точное совпадение)."""
        statement = select(UserEntity).where(UserEntity.login == login)
        return self._session.scalars(statement).first()

    def get_by_email(self, email: str) -> UserEntity | None:
        """Найти пользователя по email без учёта регистра.

        `lower(email) = lower(:email)` совпадает с выражением уникального индекса
        `uq_users_lower_email`, поэтому поиск идёт по индексу.
        """
        statement = select(UserEntity).where(func.lower(UserEntity.email) == func.lower(email))
        return self._session.scalars(statement).first()

    def lock(self, user_id: int) -> bool:
        """Взять блокировку строки пользователя (`FOR NO KEY UPDATE`) до конца транзакции.

        Слабее `FOR UPDATE`: не мешает другим транзакциям добавлять строки со ссылкой на
        пользователя (события, закладки), но двое с `lock` выстраиваются в очередь.
        """
        statement = (
            select(UserEntity.id).where(UserEntity.id == user_id).with_for_update(key_share=True)
        )
        return self._session.scalar(statement) is not None

    def lock_many(self, user_ids: Iterable[int], *, exclusive: bool = False) -> set[int]:
        """Заблокировать строки пользователей в порядке возрастания id; вернуть найденные id.

        `ORDER BY id` стоит под блокировкой строк (`LockRows` в плане запроса), поэтому строки
        действительно берутся по возрастанию. Слабая блокировка — `FOR KEY SHARE`: такую же
        берёт внешний ключ при записи события, а мешает она только удалению пользователя.
        Сильная — `FOR UPDATE`, как у самого `DELETE`.
        """
        ids = sorted(set(user_ids))
        if not ids:
            return set()
        statement = (
            select(UserEntity.id)
            .where(UserEntity.id.in_(ids))
            .order_by(UserEntity.id)
            .with_for_update(read=not exclusive, key_share=not exclusive)
        )
        return set(self._session.scalars(statement))

    def add_favorite(self, user: UserEntity, material: MaterialEntity) -> None:
        """Добавить материал в избранное: связь «многие ко многим» через `relationship`."""
        user.favorite_materials.append(material)
        self._session.flush()

    def remove_favorite(self, user: UserEntity, material: MaterialEntity) -> None:
        """Убрать материал из избранного, если он там есть."""
        if material in user.favorite_materials:
            user.favorite_materials.remove(material)
            self._session.flush()

    def has_favorite(self, user_id: int, material_id: int) -> bool:
        """Вернуть, лежит ли материал в избранном пользователя."""
        statement = select(
            exists().where(favorites.c.user_id == user_id, favorites.c.material_id == material_id)
        )
        return bool(self._session.scalar(statement))

    def get_favorite_rows(self, user_id: int) -> list[Row]:
        """Вернуть строки избранного пользователя (с датой добавления), от старых к новым."""
        statement = (
            select(favorites)
            .where(favorites.c.user_id == user_id)
            .order_by(favorites.c.added_at, favorites.c.material_id)
        )
        return list(self._session.execute(statement))

    def get_favorite_row(self, user_id: int, material_id: int) -> Row | None:
        """Вернуть одну строку избранного или None."""
        statement = select(favorites).where(
            favorites.c.user_id == user_id, favorites.c.material_id == material_id
        )
        return self._session.execute(statement).first()


class DisciplineRepository(SQLAlchemyRepository[DisciplineEntity]):
    """Репозиторий дисциплин."""

    model = DisciplineEntity

    def get_all(self) -> list[DisciplineEntity]:
        """Вернуть все дисциплины по возрастанию id."""
        statement = select(DisciplineEntity).order_by(DisciplineEntity.id)
        return list(self._session.scalars(statement))

    def get_by_name(self, name: str) -> DisciplineEntity | None:
        """Найти дисциплину по названию без учёта регистра."""
        statement = select(DisciplineEntity).where(
            func.lower(DisciplineEntity.name) == func.lower(name)
        )
        return self._session.scalars(statement).first()


class TopicRepository(SQLAlchemyRepository[TopicEntity]):
    """Репозиторий тем."""

    model = TopicEntity

    def get_by_name(self, discipline_id: int, name: str) -> TopicEntity | None:
        """Найти тему дисциплины по названию без учёта регистра."""
        statement = select(TopicEntity).where(
            TopicEntity.discipline_id == discipline_id,
            func.lower(TopicEntity.name) == func.lower(name),
        )
        return self._session.scalars(statement).first()

    def get_by_discipline(self, discipline_id: int) -> list[TopicEntity]:
        """Найти все темы дисциплины по возрастанию id."""
        statement = (
            select(TopicEntity)
            .where(TopicEntity.discipline_id == discipline_id)
            .order_by(TopicEntity.id)
        )
        return list(self._session.scalars(statement))


_QUERY_WORD = re.compile(r"[0-9a-zа-яё]+")
_MAX_QUERY_WORDS = 20


def build_tsquery(text: str | None) -> str | None:
    """Превратить строку поиска в текст запроса `to_tsquery`: все слова, каждое как префикс.

    «лекции по пределам» → `'лекции':* & 'по':* & 'пределам':*`. Слова берутся только из букв
    и цифр, поэтому служебные символы `tsquery` (`& | ! ( ) :`) в запрос попасть не могут.
    Префикс `:*` позволяет находить материалы по началу слова («лек»), а морфологию
    (основы слов, «ё», стоп-слова) выполняет сам PostgreSQL. Пустая строка даёт `None`.
    """
    if not text:
        return None
    words = _QUERY_WORD.findall(text.casefold())[:_MAX_QUERY_WORDS]
    return " & ".join(f"'{word}':*" for word in words) or None


class MaterialRepository(SQLAlchemyRepository[MaterialEntity]):
    """Репозиторий материалов."""

    model = MaterialEntity

    def search(self, query: MaterialSearchQuery) -> list[MaterialEntity]:
        """Найти материалы одним SQL-запросом: условия, полнотекстовый поиск, сортировка."""
        statement = self._filtered(select(MaterialEntity), query).order_by(
            *DEFAULT_SORT_STRATEGIES[query.sort_field].order_by(query.sort_order)
        )
        if query.limit is not None:
            statement = statement.limit(query.limit).offset(query.offset)
        return list(self._session.scalars(statement))

    def count(self, query: MaterialSearchQuery) -> int:
        """Посчитать материалы, подходящие под запрос (без страницы)."""
        statement = self._filtered(select(func.count()).select_from(MaterialEntity), query)
        return int(self._session.scalar(statement) or 0)

    def _filtered(self, statement, query: MaterialSearchQuery):
        """Добавить к запросу условия отбора из `query`."""
        if query.discipline_id is not None:
            statement = statement.where(MaterialEntity.discipline_id == query.discipline_id)
        if query.topic_id is not None:
            statement = statement.where(MaterialEntity.topic_id == query.topic_id)
        if query.file_type is not None:
            statement = statement.where(MaterialEntity.file_type == query.file_type)
        if query.uploaded_from is not None:
            statement = statement.where(MaterialEntity.uploaded_at >= query.uploaded_from)
        if query.uploaded_before is not None:
            statement = statement.where(MaterialEntity.uploaded_at < query.uploaded_before)
        text_condition = self._text_condition(query.text)
        if text_condition is not None:
            statement = statement.where(text_condition)
        return statement

    def _text_condition(self, text: str | None):
        """Условие полнотекстового поиска или `None`, если искать по тексту не нужно.

        Если запрос состоит только из стоп-слов («по», «и»), PostgreSQL выбрасывает их все:
        такой запрос не ограничивает выдачу, как и пустой.
        """
        source = build_tsquery(text)
        if source is None:
            return None
        tsquery = to_tsquery(literal_column(f"'{SEARCH_CONFIG}'::regconfig"), source)
        if not self._session.scalar(select(func.numnode(tsquery))):
            return None
        return material_search_vector().op("@@")(tsquery)

    def get_all(self) -> list[MaterialEntity]:
        """Вернуть все материалы по возрастанию id."""
        statement = select(MaterialEntity).order_by(MaterialEntity.id)
        return list(self._session.scalars(statement))

    def get_for_update(self, material_id: int) -> MaterialEntity | None:
        """Прочитать материал с блокировкой строки (`FOR NO KEY UPDATE`).

        `populate_existing` обновляет уже загруженный в сессию объект: после ожидания чужой
        фиксации нужно состояние из базы, а не старая копия.
        """
        statement = (
            select(MaterialEntity)
            .where(MaterialEntity.id == material_id)
            .with_for_update(key_share=True)
            .execution_options(populate_existing=True)
        )
        return self._session.scalars(statement).first()

    def find_author(self, material_id: int) -> tuple[bool, int | None]:
        """Узнать без блокировки, есть ли материал и кто его автор: `(есть, id автора или None)`."""
        row = self._session.execute(
            select(MaterialEntity.author_id).where(MaterialEntity.id == material_id)
        ).first()
        return (False, None) if row is None else (True, row.author_id)

    def get_by_author(self, author_id: int) -> list[MaterialEntity]:
        """Найти все материалы автора по возрастанию id."""
        statement = (
            select(MaterialEntity)
            .where(MaterialEntity.author_id == author_id)
            .order_by(MaterialEntity.id)
        )
        return list(self._session.scalars(statement))


class EventRepository(SQLAlchemyRepository[EventEntity]):
    """Репозиторий событий журнала."""

    model = EventEntity

    def get_all(self) -> list[EventEntity]:
        """Вернуть события от старых к новым."""
        statement = select(EventEntity).order_by(EventEntity.occurred_at, EventEntity.id)
        return list(self._session.scalars(statement))


class PasswordResetTokenRepository(SQLAlchemyRepository[PasswordResetTokenEntity]):
    """Репозиторий кодов восстановления пароля."""

    model = PasswordResetTokenEntity

    def get_by_hash(self, token_hash: str) -> PasswordResetTokenEntity | None:
        """Найти код по хешу."""
        statement = select(PasswordResetTokenEntity).where(
            PasswordResetTokenEntity.token_hash == token_hash
        )
        return self._session.scalars(statement).first()

    def delete_by_hash(self, token_hash: str) -> None:
        """Удалить код по хешу."""
        self._session.execute(
            delete(PasswordResetTokenEntity).where(
                PasswordResetTokenEntity.token_hash == token_hash
            )
        )

    def consume(self, token_hash: str, now: datetime) -> int | None:
        """Удалить действующий код одним `DELETE ... RETURNING` и вернуть id владельца.

        Проверка срока и удаление — один оператор, поэтому из двух одновременных вызовов
        строку удалит только первый: второй дождётся его фиксации и не найдёт строки.
        """
        statement = (
            delete(PasswordResetTokenEntity)
            .where(
                PasswordResetTokenEntity.token_hash == token_hash,
                PasswordResetTokenEntity.expires_at > now,
            )
            .returning(PasswordResetTokenEntity.user_id)
        )
        row = self._session.execute(statement).first()
        return None if row is None else int(row.user_id)

    def delete_by_user(self, user_id: int) -> None:
        """Удалить все коды пользователя."""
        self._session.execute(
            delete(PasswordResetTokenEntity).where(PasswordResetTokenEntity.user_id == user_id)
        )

    def delete_expired(self, now: datetime) -> None:
        """Удалить коды, срок которых истёк к моменту `now`."""
        self._session.execute(
            delete(PasswordResetTokenEntity).where(PasswordResetTokenEntity.expires_at < now)
        )


class AuthTokenRepository(SQLAlchemyRepository[AuthTokenEntity]):
    """Репозиторий токенов доступа к API."""

    model = AuthTokenEntity

    def get_by_hash(self, token_hash: str) -> AuthTokenEntity | None:
        """Найти токен по хешу."""
        statement = select(AuthTokenEntity).where(AuthTokenEntity.token_hash == token_hash)
        return self._session.scalars(statement).first()

    def delete_by_hash(self, token_hash: str) -> None:
        """Удалить токен по хешу (выход)."""
        self._session.execute(
            delete(AuthTokenEntity).where(AuthTokenEntity.token_hash == token_hash)
        )

    def delete_by_user(self, user_id: int) -> None:
        """Удалить все токены пользователя."""
        self._session.execute(delete(AuthTokenEntity).where(AuthTokenEntity.user_id == user_id))

    def delete_expired(self, now: datetime) -> None:
        """Удалить токены, срок которых истёк к моменту `now`."""
        self._session.execute(delete(AuthTokenEntity).where(AuthTokenEntity.expires_at < now))


class FailedLoginRepository(SQLAlchemyRepository[FailedLoginEntity]):
    """Репозиторий неудачных попыток входа."""

    model = FailedLoginEntity

    def lock_login(self, login: str) -> None:
        """Взять консультативную блокировку логина до конца транзакции.

        Без неё две параллельные неудачные попытки (в `READ COMMITTED` каждая видит только
        свою строку) обе насчитали бы порог и обе отправили бы оповещение. Блокировка не
        привязана к строке: строк у несуществующих логинов может не быть вовсе. Ключ состоит из
        номера «пространства» блокировок и хеша логина; совпадение хешей двух логинов лишь
        заставит их подождать друг друга.
        """
        self._session.execute(
            select(func.pg_advisory_xact_lock(FAILED_LOGIN_LOCK_NAMESPACE, func.hashtext(login)))
        )

    def count_by_login(self, login: str) -> int:
        """Сколько неудачных попыток записано для логина."""
        statement = (
            select(func.count())
            .select_from(FailedLoginEntity)
            .where(FailedLoginEntity.login == login)
        )
        return int(self._session.scalar(statement) or 0)

    def delete_by_login(self, login: str) -> None:
        """Удалить все попытки логина."""
        self._session.execute(delete(FailedLoginEntity).where(FailedLoginEntity.login == login))


class MaterialRevisionRepository(SQLAlchemyRepository[MaterialRevisionEntity]):
    """Репозиторий снимков материала."""

    model = MaterialRevisionEntity

    def get_by_material(self, material_id: int) -> list[MaterialRevisionEntity]:
        """Снимки материала от новых к старым."""
        statement = (
            select(MaterialRevisionEntity)
            .where(MaterialRevisionEntity.material_id == material_id)
            .order_by(MaterialRevisionEntity.id.desc())
        )
        return list(self._session.scalars(statement))

    def get_latest(self, material_id: int) -> MaterialRevisionEntity | None:
        """Последний снимок материала или None."""
        statement = (
            select(MaterialRevisionEntity)
            .where(MaterialRevisionEntity.material_id == material_id)
            .order_by(MaterialRevisionEntity.id.desc())
            .limit(1)
        )
        return self._session.scalars(statement).first()
