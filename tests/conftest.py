"""Общие фикстуры.

По умолчанию тесты не трогают базу данных: `repository_factory` — это хранилище в памяти
(`tests/memory.py`), у каждого теста своё и пустое, поэтому порядок запуска ничего не меняет.
Всё, что зависит от SQL (ограничения, миграции, транзакции, гонки, морфология поиска), лежит в
`tests/integration/db` и помечено `db`: любой тест, которому нужна настоящая БД, получает метку
автоматически (см. `pytest_collection_modifyitems`), а обычный прогон `pytest` такие тесты не
запускает. Прогон с базой: `pytest -m db` (или `pytest -m "db or not db"` — вообще всё).

Тестовая база берётся из `TEST_DATABASE_URL` (по умолчанию `lms_test` из docker-compose.yaml) и
пересоздаётся при запуске, поэтому она не должна совпадать с рабочей `DATABASE_URL`. Если сервер
недоступен, `pytest -m db` падает с понятным сообщением, а не пропускает тесты: «зелёный» прогон
без базы ничего бы не доказывал.

Изоляция в режиме БД: каждому тесту выдаётся одна `Session`, репозитории только делают `flush()`,
в конце транзакция откатывается. Тесты, которым нужны настоящие `commit`/`rollback`, берут
`clean_db` и `session_factory` и очищают таблицы сами.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import psycopg
import pytest
from alembic import command
from sqlalchemy import Engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker

import src.database.models  # noqa: F401  (регистрирует таблицы в metadata)
from src.configs.settings import settings
from src.database.base import Base
from src.database.migrations import make_alembic_config
from src.database.session import create_db_engine, create_session_factory
from src.domain.enums import FileType, Role
from src.domain.models import Material, Topic, User
from src.repositories.factory import SQLAlchemyRepositoryFactory
from src.services.event_log_service import EventLogService
from tests.fakes import (
    FakeFileStorage,
    PlainPasswordHasher,
    RecordingEmailSender,
    make_user,
)
from tests.memory import InMemoryRepositoryFactory


@pytest.fixture(scope="session")
def db_engine() -> Iterator[Engine]:
    """Движок тестовой БД с чистой схемой, созданной миграциями Alembic."""
    url = settings.test_database_url
    if url == settings.database_url:
        pytest.exit("TEST_DATABASE_URL совпадает с DATABASE_URL: тесты стёрли бы рабочие данные")
    engine = create_db_engine(url)
    try:
        engine.connect().close()
    except OperationalError as error:
        engine.dispose()
        pytest.exit(
            "Тестовая БД недоступна. Запустите PostgreSQL (`docker compose up -d`) или задайте "
            f"TEST_DATABASE_URL.\n{error.orig}",
            returncode=2,
        )
    config = make_alembic_config(engine.url.render_as_string(hide_password=False))
    command.downgrade(config, "base")
    command.upgrade(config, "head")
    yield engine
    engine.dispose()


@pytest.fixture(scope="session")
def alembic_config(db_engine: Engine):
    """Конфигурация Alembic, направленная на тестовую БД."""
    return make_alembic_config(db_engine.url.render_as_string(hide_password=False))


@pytest.fixture
def clean_db(db_engine: Engine) -> Engine:
    """Тестовая БД с пустыми таблицами (схема остаётся), счётчики id начинаются с 1."""
    tables = ", ".join(table.name for table in Base.metadata.sorted_tables)
    with db_engine.begin() as connection:
        connection.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
    return db_engine


@pytest.fixture
def session_factory(clean_db: Engine) -> sessionmaker[Session]:
    """Фабрика сессий тестовой БД с пустыми таблицами."""
    return create_session_factory(clean_db)


@pytest.fixture
def db_session(session_factory: sessionmaker[Session]) -> Iterator[Session]:
    """Одна сессия на тест. Репозитории делают только `flush()`, коммита нет, а в конце
    теста всё откатывается."""
    with session_factory() as session:
        yield session
        session.rollback()


@pytest.fixture
def db_repository_factory(db_session: Session) -> SQLAlchemyRepositoryFactory:
    """Семейство репозиториев PostgreSQL на сессии теста (только для тестов с меткой `db`)."""
    return SQLAlchemyRepositoryFactory(db_session)


@pytest.fixture
def repository_factory(request: pytest.FixtureRequest):
    """Семейство репозиториев: в памяти (чистое для каждого теста, без базы данных).

    Тест, которому нужна настоящая PostgreSQL (например, морфология поиска), помечается
    `@pytest.mark.db`: тогда те же фикстуры получат репозитории на тестовой БД.
    """
    if request.node.get_closest_marker("db") is not None:
        return request.getfixturevalue("db_repository_factory")
    return InMemoryRepositoryFactory()


class FrozenClock:
    """Подменяемые часы: время стоит, пока тест сам не передвинет его (`advance`)."""

    def __init__(self, start: datetime) -> None:
        self.current = start

    def advance(self, **delta: float) -> None:
        self.current += timedelta(**delta)


_CLOCK_MODULES = ("src.services.session_service", "src.services.auth_service")


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> FrozenClock:
    """Заморозить `datetime.now()` в сервисах, которые считают сроки действия токенов и кодов.

    Время — внешняя зависимость: тест не ждёт и не зависит от скорости машины, а проверяет
    поведение ровно на границе срока (за секунду до, в сам момент, после).
    """
    frozen = FrozenClock(datetime(2026, 11, 3, 12, 0, tzinfo=UTC))

    class FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):  # type: ignore[override]
            return frozen.current if tz is None else frozen.current.astimezone(tz)

    for module in _CLOCK_MODULES:
        monkeypatch.setattr(f"{module}.datetime", FrozenDateTime)
    return frozen


@pytest.fixture
def forbid_real_database(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> None:
    """Запретить любое подключение к PostgreSQL в тестах без метки `db`.

    Если тест (или код, который он вызывает) всё же попытается открыть соединение, он упадёт
    с понятным сообщением: так изоляция от настоящей БД не держится на честном слове.
    """
    if request.node.get_closest_marker("db") is not None:
        return

    def refuse(*_args, **_kwargs):
        raise AssertionError("Тест без метки `db` обратился к настоящей базе данных")

    # `psycopg.connect` — это привязанный при импорте метод, поэтому подменяются обе точки входа:
    # и сам класс (его использует пул), и функция верхнего уровня (её вызывает SQLAlchemy).
    monkeypatch.setattr(psycopg.Connection, "connect", classmethod(lambda cls, *a, **k: refuse()))
    monkeypatch.setattr(psycopg, "connect", refuse)


@pytest.fixture(autouse=True)
def _isolation(forbid_real_database) -> None:
    """Автоматически подключает запрет на обращения к БД ко всем тестам."""


@pytest.fixture
def email_sender() -> RecordingEmailSender:
    return RecordingEmailSender()


@pytest.fixture
def hasher() -> PlainPasswordHasher:
    return PlainPasswordHasher()


@pytest.fixture
def file_storage() -> FakeFileStorage:
    return FakeFileStorage()


@pytest.fixture
def user_repo(repository_factory):
    return repository_factory.create_user_repository()


@pytest.fixture
def discipline_repo(repository_factory):
    return repository_factory.create_discipline_repository()


@pytest.fixture
def topic_repo(repository_factory):
    return repository_factory.create_topic_repository()


@pytest.fixture
def material_repo(repository_factory):
    return repository_factory.create_material_repository()


@pytest.fixture
def favorite_repo(repository_factory):
    return repository_factory.create_favorite_repository()


@pytest.fixture
def reset_token_repo(repository_factory):
    return repository_factory.create_password_reset_token_repository()


@pytest.fixture
def auth_token_repo(repository_factory):
    return repository_factory.create_auth_token_repository()


@pytest.fixture
def failed_login_repo(repository_factory):
    return repository_factory.create_failed_login_repository()


@pytest.fixture
def revision_repo(repository_factory):
    return repository_factory.create_material_revision_repository()


@pytest.fixture
def event_repo(repository_factory):
    return repository_factory.create_event_repository()


@pytest.fixture
def event_log(event_repo) -> EventLogService:
    return EventLogService(event_repo)


@pytest.fixture
def admin_user(user_repo) -> User:
    return user_repo.add(make_user(100, "admin", Role.ADMIN))


@pytest.fixture
def teacher_user(user_repo) -> User:
    return user_repo.add(make_user(101, "teacher", Role.TEACHER))


@pytest.fixture
def other_teacher(user_repo) -> User:
    return user_repo.add(make_user(102, "teacher2", Role.TEACHER))


@pytest.fixture
def student_user(user_repo) -> User:
    return user_repo.add(make_user(103, "student", Role.STUDENT))


def new_user(login: str = "alice", role: Role = Role.TEACHER, email: str | None = None) -> User:
    """Новый (ещё не сохранённый) пользователь."""
    return User(0, login, email or f"{login}@example.org", "hash", role)


def new_material(topic: Topic, author_id: int | None, title: str = "Лекция") -> Material:
    """Новый (ещё не сохранённый) материал указанной темы."""
    return Material(
        id=0,
        title=title,
        description="описание",
        discipline_id=topic.discipline_id,
        topic_id=topic.id,
        file_name=f"{title}.pdf",
        file_type=FileType.PDF,
        file_size_bytes=10,
        author_id=author_id,
        storage_path=f"uploads/{title}.pdf",
    )


@pytest.fixture
def seeded(user_repo, discipline_repo, topic_repo) -> SimpleNamespace:
    """Преподаватель, дисциплина и тема, уже сохранённые в БД."""
    from src.domain.models import Discipline

    teacher = user_repo.add(new_user("teacher"))
    discipline = discipline_repo.add(Discipline(0, "Математика"))
    topic = topic_repo.add(Topic(0, "Алгебра", discipline.id))
    return SimpleNamespace(teacher=teacher, discipline=discipline, topic=topic)


@pytest.fixture
def reference_data(repository_factory, user_repo, discipline_repo, topic_repo) -> None:
    """Опорные строки, на которые ссылаются «типовые» тестовые объекты из `tests/fakes.py`.

    В PostgreSQL внешние ключи настоящие, поэтому `make_material()` (автор 1, дисциплина 1,
    тема 1) и `make_event()` (пользователь 1) требуют, чтобы эти строки существовали. Темы
    принадлежат дисциплинам, как того требует составной внешний ключ: 1->1, 2->2, 3->3,
    5 и 6->2, 7->3. В памяти ключей нет, но данные те же, чтобы тесты были одинаковыми.
    """
    from src.domain.models import Discipline

    user_repo.add(make_user(1, "user1"))
    for discipline_id in (1, 2, 3):
        discipline_repo.add(Discipline(discipline_id, f"Дисциплина {discipline_id}"))
    for topic_id, discipline_id in ((1, 1), (2, 2), (3, 3), (5, 2), (6, 2), (7, 3)):
        topic_repo.add(Topic(topic_id, f"Тема {topic_id}", discipline_id))
    if isinstance(repository_factory, SQLAlchemyRepositoryFactory):
        # Явная вставка `id` не двигает счётчик identity: без этого следующая строка с
        # автоматическим id получила бы занятый номер.
        session = repository_factory._session
        for table in ("users", "disciplines", "topics"):
            session.execute(
                text(
                    f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), "
                    f"(SELECT max(id) FROM {table}))"
                )
            )


_DB_FIXTURES = {"db_engine", "clean_db", "session_factory", "db_session", "db_repository_factory"}


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Пометить `db` каждый тест, которому (прямо или через другие фикстуры) нужна настоящая БД."""
    for item in items:
        if _DB_FIXTURES & set(getattr(item, "fixturenames", ())):
            item.add_marker(pytest.mark.db)
