from __future__ import annotations

from collections.abc import Callable

from src.cli.console_io import ConsoleIO

MenuItem = tuple[str, Callable[[], None]]


class MenuRenderer:
    """Рисует меню на чистом экране и читает номер выбранного пункта."""

    def __init__(self, io: ConsoleIO) -> None:
        self._io = io

    def choose(self, title: str, items: list[MenuItem]) -> Callable[[], None] | None:
        """Показать меню и вернуть обработчик пункта; None означает «выйти из аккаунта»."""
        self._io.clear_screen()
        print(f"--- {title} ---")
        for index, (label, _handler) in enumerate(items, start=1):
            print(f"{index}) {label}")
        print("0) Выйти из аккаунта")
        return self._read_choice(items)

    def _read_choice(self, items: list[MenuItem]) -> Callable[[], None] | None:
        """Спрашивать, пока не введён верный номер пункта."""
        while True:
            choice = self._io.read_line("Выберите действие: ").strip()
            if choice == "0":
                return None
            if choice.isdecimal() and 1 <= int(choice) <= len(items):
                return items[int(choice) - 1][1]
            print(f"Нет такого пункта. Введите число от 0 до {len(items)}.")
