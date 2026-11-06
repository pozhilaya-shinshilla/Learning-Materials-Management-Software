from __future__ import annotations

import argparse
import dataclasses
import logging
import sys
from collections.abc import Sequence

import uvicorn
from sqlalchemy.exc import SQLAlchemyError

from src.api.app import create_app
from src.bootstrap import build_transactional_context
from src.cli.app import CliApplication
from src.cli.console_io import ConsoleIO
from src.configs.settings import ServerSettings, load_admin_settings, load_server_settings
from src.database.session import SessionFactory, engine
from src.domain.exceptions import DomainError
from src.runtime import check_configuration, prepare_database


def build_parser() -> argparse.ArgumentParser:
    """Описать команды и параметры командной строки."""
    parser = argparse.ArgumentParser(
        prog="python -m src.main",
        description="Сервис управления учебными материалами.",
    )
    commands = parser.add_subparsers(dest="command")
    serve = commands.add_parser("serve", help="запустить REST API (по умолчанию)")
    serve.add_argument("--host", help="адрес для прослушивания (APP_HOST)")
    serve.add_argument("--port", type=int, help="порт (APP_PORT)")
    serve.add_argument("--no-migrate", action="store_true", help="не применять миграции при старте")
    commands.add_parser("cli", help="консольное приложение")
    commands.add_parser("migrate", help="применить миграции и выйти")
    return parser


def _server_settings(args: argparse.Namespace) -> ServerSettings:
    """Настройки из окружения с поправками из командной строки."""
    settings = load_server_settings()
    changes: dict[str, object] = {}
    if getattr(args, "host", None):
        changes["host"] = args.host
    if getattr(args, "port", None):
        changes["port"] = args.port
    if getattr(args, "no_migrate", False):
        changes["auto_migrate"] = False
    return dataclasses.replace(settings, **changes)


def serve(args: argparse.Namespace) -> None:
    """Подготовить базу и запустить REST API."""
    settings = _server_settings(args)
    check_configuration()
    prepare_database(settings)
    logging.getLogger(__name__).info(
        "Сервер запущен: http://%s:%s (Swagger UI: /docs)", settings.host, settings.port
    )
    uvicorn.run(create_app(), host=settings.host, port=settings.port, log_level="info")


def run_cli(args: argparse.Namespace) -> None:
    """Подготовить базу и запустить консольное приложение."""
    settings = _server_settings(args)
    check_configuration()
    prepare_database(settings)
    context = build_transactional_context(SessionFactory, admin=load_admin_settings())
    try:
        CliApplication(context, ConsoleIO()).run()
    finally:
        engine.dispose()


def migrate(args: argparse.Namespace) -> None:
    """Применить миграции и выйти."""
    prepare_database(_server_settings(args), migrate=True)
    engine.dispose()
    print("Миграции применены.")


COMMANDS = {"serve": serve, "cli": run_cli, "migrate": migrate}


def main(argv: Sequence[str] | None = None) -> None:
    """Выбрать команду по аргументам и выполнить её; ошибки настроек и БД — понятным текстом."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = build_parser().parse_args(argv)
    command = COMMANDS[args.command or "serve"]
    try:
        command(args)
    except DomainError as error:
        sys.exit(f"Ошибка настройки приложения: {error}")
    except SQLAlchemyError as error:
        sys.exit(f"Не удалось работать с базой данных: {error.__class__.__name__}: {error}")


if __name__ == "__main__":
    main()
