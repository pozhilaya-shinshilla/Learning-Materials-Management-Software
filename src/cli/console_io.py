from __future__ import annotations

import getpass
import os
import sys
from collections.abc import Callable

from src.domain.exceptions import DomainError
from src.domain.validation import MAX_NAME_LENGTH, parse_yes_no, require_text

_CANCEL_WORDS = frozenset({"0", "отмена", "cancel"})


class Cancelled(Exception):
    """Сигнал отмены текущего действия пользователем."""

    message = "Действие отменено."

    def __init__(self) -> None:
        super().__init__(self.message)


class ConsoleIO:
    """Консольный ввод-вывод: запросы с повтором при ошибке, подтверждения, экран и паузы."""

    def read_line(self, prompt: str) -> str:
        """Прочитать строку из консоли."""
        return input(prompt)

    def read_secret(self, prompt: str) -> str:
        """Прочитать строку без отображения вводимых символов (пароли)."""
        return getpass.getpass(prompt)

    def clear_screen(self) -> None:
        """Очистить консоль, чтобы меню перерисовывалось заново (только в настоящем терминале)."""
        if sys.stdout.isatty():
            os.system("cls" if os.name == "nt" else "clear")
        else:
            print()

    def pause(self) -> None:
        """Подождать нажатия Enter перед возвратом в меню."""
        input("\nНажмите Enter, чтобы вернуться в меню...")

    def header(self, title: str) -> None:
        """Напечатать заголовок формы с подсказкой про отмену."""
        print(f"== {title} ==  (0 — отмена)")

    def ask[T](self, prompt: str, parser: Callable[[str], T], *, secret: bool = False) -> T:
        """Спрашивать, пока `parser` не примет ответ; «0»/«отмена» вызывает Cancelled.

        При неверном вводе `parser` выбрасывает DomainError с понятным текстом;
        текст выводится, и тот же вопрос задаётся снова. При `secret=True` вводимый
        текст не отображается (пароли).
        """
        while True:
            raw = self.read_secret(prompt) if secret else self.read_line(prompt)
            if raw.strip().lower() in _CANCEL_WORDS:
                raise Cancelled
            try:
                return parser(raw)
            except DomainError as error:
                print(f"  ✗ {error}")

    def confirm(self, prompt: str) -> bool:
        """Задать вопрос «да/нет» и вернуть ответ."""
        return self.ask(prompt + " (y/n): ", parse_yes_no)

    def ask_text(self, prompt: str, field_name: str, max_length: int = MAX_NAME_LENGTH) -> str:
        """Спросить обязательное текстовое поле."""
        return self.ask(prompt, lambda raw: require_text(raw, field_name, max_length))

    def ask_optional_text(self, prompt: str) -> str | None:
        """Спросить необязательное текстовое поле; пустой ввод даёт None."""
        return self.ask(prompt, lambda raw: raw.strip() or None)
