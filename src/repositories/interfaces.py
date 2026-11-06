from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable
from datetime import datetime

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

    @abstractmethod
    def lock(self, user_id: int) -> bool:
        """Заблокировать строку пользователя до конца транзакции.

        Другая транзакция, которая тоже вызовет `lock` для этого пользователя, дождётся
        фиксации первой. Возвращает False, если пользователя уже нет.
        """

    @abstractmethod
    def lock_many(self, user_ids: Iterable[int], *, exclusive: bool = False) -> set[int]:
        """Заблокировать строки пользователей до конца транзакции и вернуть id существующих.

        Строки берутся в порядке возрастания id. Единый порядок исключает взаимные ожидания двух
        транзакций, которые берут одни и те же строки в разном порядке (PostgreSQL разрывает их
        как взаимную блокировку, и одна транзакция гибнет).

        По умолчанию блокировка слабая: она лишь не даёт удалить пользователя, пока операция не
        завершена, а изменению роли или статуса не мешает. `exclusive=True` блокирует так же, как
        само удаление. Несуществующие id в результат не попадают.
        """


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
    def delete(self, discipline_id: int) -> None:
        """Удалить дисциплину; если в ней есть темы, выбросить `DisciplineNotEmptyError`."""

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
    def delete(self, topic_id: int) -> None:
        """Удалить тему; если к ней привязаны материалы, выбросить `TopicInUseError`."""

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
    def search(self, query: MaterialSearchQuery) -> list[Material]:
        """Вернуть материалы, подходящие под запрос, в запрошенном порядке.

        Отбор и сортировка выполняются в хранилище, а не после загрузки всего каталога.
        Если задан `limit`, возвращается только запрошенная страница (`offset` — сколько
        материалов пропустить).
        """

    @abstractmethod
    def count(self, query: MaterialSearchQuery) -> int:
        """Вернуть, сколько материалов подходит под запрос (без учёта `limit` и `offset`)."""

    @abstractmethod
    def get_by_id_for_update(
        self, material_id: int, *, acting_user_id: int | None = None
    ) -> Material | None:
        """Вернуть материал, заблокировав его строку до конца транзакции.

        Читает самое свежее состояние: если материал менялся в другой транзакции, дождётся её
        фиксации. Так две правки одного материала выполняются по очереди, а не вслепую
        поверх друг друга. None, если материала нет (в том числе уже удалён).

        `acting_user_id` — пользователь, от чьего имени материал меняют. Его строка и строка
        автора блокируются раньше самого материала (порядок «пользователь, затем материал»,
        как у удаления пользователя, которое обнуляет `author_id` у его материалов). Если
        пользователя уже удалили, выбрасывается `AccountDeletedError`: его сеанс закончился.
        """

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


class AuthTokenRepository(ABC):
    """Контракт хранения токенов доступа к API (в виде хеша)."""

    @abstractmethod
    def add(self, token: AuthToken) -> AuthToken:
        """Сохранить выданный токен и вернуть его с присвоенным id."""

    @abstractmethod
    def get_by_hash(self, token_hash: str) -> AuthToken | None:
        """Вернуть токен по его хешу или None, если такого нет."""

    @abstractmethod
    def delete_by_hash(self, token_hash: str) -> None:
        """Удалить токен (выход из системы)."""

    @abstractmethod
    def delete_by_user(self, user_id: int) -> None:
        """Удалить все токены пользователя."""

    @abstractmethod
    def delete_expired(self, now: datetime) -> None:
        """Удалить токены, срок которых истёк к моменту `now`."""


class PasswordResetTokenRepository(ABC):
    """Контракт хранения кодов восстановления пароля (в виде хеша)."""

    @abstractmethod
    def add(self, token: PasswordResetToken) -> PasswordResetToken:
        """Сохранить выданный код и вернуть его с присвоенным id."""

    @abstractmethod
    def get_by_hash(self, token_hash: str) -> PasswordResetToken | None:
        """Вернуть код по его хешу или None, если такого нет."""

    @abstractmethod
    def delete_by_hash(self, token_hash: str) -> None:
        """Удалить код (использован или истёк)."""

    @abstractmethod
    def consume(self, token_hash: str, now: datetime) -> int | None:
        """Атомарно списать действующий код и вернуть id его владельца.

        Единственный способ использовать код: из двух одновременных вызовов с одним кодом
        владельца получит только один, второй получит None (как и для неверного или
        просроченного кода).
        """

    @abstractmethod
    def delete_by_user(self, user_id: int) -> None:
        """Удалить все коды пользователя."""

    @abstractmethod
    def delete_expired(self, now: datetime) -> None:
        """Удалить все коды, срок которых истёк к моменту `now`."""


class FailedLoginRepository(ABC):
    """Контракт хранения неудачных попыток входа (для оповещения о подборе пароля)."""

    @abstractmethod
    def register(self, login: str) -> int:
        """Записать неудачную попытку и вернуть число попыток подряд для этого логина.

        Попытки одного логина обрабатываются по очереди: пока транзакция первой не зафиксирована,
        вторая ждёт и считает уже с учётом первой. Иначе обе насчитали бы по порогу и обе
        оповестили бы владельца.
        """

    @abstractmethod
    def reset(self, login: str) -> None:
        """Забыть попытки логина (успешный вход или отправленное оповещение)."""


class MaterialRevisionRepository(ABC):
    """Контракт хранения снимков материала для отмены правок (опекун в паттерне Memento)."""

    @abstractmethod
    def push(self, material_id: int, memento: MaterialMemento) -> None:
        """Запомнить состояние материала перед изменением."""

    @abstractmethod
    def pop(self, material_id: int) -> MaterialMemento | None:
        """Достать и удалить последний снимок или вернуть None, если отменять нечего."""

    @abstractmethod
    def has_history(self, material_id: int) -> bool:
        """Вернуть, есть ли у материала изменения, которые можно отменить."""
