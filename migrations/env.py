"""Окружение Alembic: откуда брать метаданные моделей и как подключаться к БД."""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from src.configs.settings import settings
from src.database import models  # noqa: F401
from src.database.base import Base
from src.database.migrations import include_in_autogenerate

config = context.config

# Когда миграции запускает само приложение (`upgrade_to_head`), оно уже настроило логирование:
# `fileConfig` из alembic.ini сбросил бы его (уровень, формат). Без этого флага (команда
# `alembic ...` из консоли) логирование настраивается по alembic.ini, как обычно.
if config.config_file_name is not None and config.attributes.get("configure_logging", True):
    # Без `disable_existing_loggers=False` fileConfig молча отключает все уже созданные логгеры
    # приложения (например, журнал отправки писем), если миграции запускаются из его процесса.
    fileConfig(config.config_file_name, disable_existing_loggers=False)

# URL берётся из настроек приложения: и приложение, и Alembic читают settings.database_url.
# Явно заданный `sqlalchemy.url` (так тесты направляют Alembic на тестовую БД) важнее.
if not config.get_main_option("sqlalchemy.url"):
    config.set_main_option("sqlalchemy.url", settings.database_url.replace("%", "%%"))

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Запустить миграции в offline-режиме: без подключения к БД."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        include_object=include_in_autogenerate,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Запустить миграции в online-режиме: с подключением к БД."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            include_object=include_in_autogenerate,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
