from __future__ import annotations

from src.bootstrap import DEFAULT_ADMIN_LOGIN, DEFAULT_ADMIN_PASSWORD, build_application_context
from src.cli.app import CliApplication


def main() -> None:
    """Wire the application together and start the interactive CLI."""
    context = build_application_context()
    print(
        f"Учетная запись администратора по умолчанию: "
        f"{DEFAULT_ADMIN_LOGIN} / {DEFAULT_ADMIN_PASSWORD}"
    )
    application = CliApplication(
        auth_service=context.auth_service,
        user_management_service=context.user_management_service,
        material_service=context.material_service,
        search_service=context.search_service,
        favorite_service=context.favorite_service,
        event_log_service=context.event_log_service,
        catalog_service=context.catalog_service,
    )
    application.run()


if __name__ == "__main__":
    main()
