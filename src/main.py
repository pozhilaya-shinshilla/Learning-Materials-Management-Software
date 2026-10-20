from __future__ import annotations

import sys

from src.bootstrap import build_application_context
from src.cli.app import CliApplication
from src.cli.console_io import ConsoleIO
from src.domain.exceptions import DomainError
from src.settings import load_admin_settings


def main() -> None:
    """Собрать приложение из частей и запустить интерактивный интерфейс."""
    try:
        admin = load_admin_settings()
    except DomainError as error:
        sys.exit(f"Некорректные настройки администратора (ADMIN_*): {error}")
    if admin.password_generated:
        print(
            "ADMIN_PASSWORD не задан: пароль администратора сгенерирован при запуске "
            "и показывается один раз.\n"
            f"Логин: {admin.login}, пароль: {admin.password}"
        )
    context = build_application_context(admin=admin)
    CliApplication(context, ConsoleIO()).run()


if __name__ == "__main__":
    main()
