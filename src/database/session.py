"""Движок и фабрика сессий.

`engine` создаётся один раз и не подключается к БД сразу. `Session` создаётся на каждую
операцию (см. `src/database/transaction.py`), а не одна на всё приложение: она не
потокобезопасна и должна жить недолго. Таблицы здесь не создаются: схему создаёт только
Alembic (`alembic upgrade head`).
"""

from __future__ import annotations

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.configs.settings import settings


def create_db_engine(url: str, *, echo: bool = False) -> Engine:
    """Создать движок для указанного URL; `pool_pre_ping` переживает перезапуск сервера БД."""
    # Сессия БД работает в UTC: время в ответах API везде в одном виде (`...Z`), независимо
    # от часового пояса, который настроен на сервере PostgreSQL.
    return create_engine(
        url, echo=echo, pool_pre_ping=True, connect_args={"options": "-c timezone=UTC"}
    )


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Создать фабрику сессий.

    `expire_on_commit=False`: после `commit()` объекты остаются доступными без повторного
    `SELECT`. Это не отменяет ленивую загрузку связей, поэтому репозитории превращают
    ORM-объекты в доменные ещё внутри сессии.
    """
    return sessionmaker(bind=engine, expire_on_commit=False)


engine = create_db_engine(settings.database_url, echo=False)
SessionFactory = create_session_factory(engine)
