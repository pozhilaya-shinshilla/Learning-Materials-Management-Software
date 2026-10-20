from __future__ import annotations

from src.domain.models import Event, Material, User
from src.services.catalog_service import CatalogService

_DATE_TIME_FORMAT = "%d.%m.%Y %H:%M:%S"


class Presenter:
    """Форматирует данные для консоли: материалы, пользователи, журнал событий, размеры."""

    def __init__(self, catalog_service: CatalogService) -> None:
        self._catalog_service = catalog_service

    @staticmethod
    def format_size(size_bytes: int) -> str:
        """Перевести размер в байтах в удобную строку (Б, КБ, МБ)."""
        if size_bytes < 1024:
            return f"{size_bytes} Б"
        if size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} КБ"
        return f"{size_bytes / (1024 * 1024):.1f} МБ"

    def print_materials(self, materials: list[Material]) -> None:
        """Напечатать список материалов."""
        for material in materials:
            where = self._catalog_service.describe(material.discipline_id, material.topic_id)
            print(
                f"[{material.id}] {material.title} — {where} — "
                f"{material.file_type.value}, {self.format_size(material.file_size_bytes)} — "
                f"{material.uploaded_at.astimezone():%d.%m.%Y}"
            )
            if material.description:
                print(f"      {material.description}")

    def print_material_details(
        self, material: Material, author_login: str, is_favorite: bool
    ) -> None:
        """Напечатать полные сведения об одном материале."""
        print()
        print(f"Название:    {material.title}")
        print(f"Описание:    {material.description or '—'}")
        print(
            "Дисциплина / тема: "
            f"{self._catalog_service.describe(material.discipline_id, material.topic_id)}"
        )
        print(
            f"Файл:        {material.file_name} "
            f"({material.file_type.value}, {self.format_size(material.file_size_bytes)})"
        )
        print(f"Автор:       {author_login}")
        print(f"Загружен:    {material.uploaded_at.astimezone():{_DATE_TIME_FORMAT}}")
        print(f"В избранном: {'да' if is_favorite else 'нет'}")

    def print_users(self, users: list[User]) -> None:
        """Напечатать список пользователей."""
        for user in users:
            print(
                f"[{user.id}] {user.login} ({user.email}) — {user.role.label} — {user.status.label}"
            )

    def print_events(self, events: list[Event], logins: dict[int, str]) -> None:
        """Напечатать журнал событий; `logins` сопоставляет id пользователя и его логин."""
        for event in events:
            who = logins.get(event.user_id) or (
                "гость" if event.user_id == 0 else f"ID {event.user_id} (удален)"
            )
            when = event.occurred_at.astimezone().strftime(_DATE_TIME_FORMAT)
            print(f"{when}  {who}: {event.event_type.label} — {event.target}")
