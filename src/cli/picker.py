from __future__ import annotations

from collections.abc import Callable
from functools import partial

from src.cli.console_io import ConsoleIO
from src.cli.presenter import Presenter
from src.domain.exceptions import (
    DisciplineNameRequiredError,
    DisciplineNotInListError,
    MaterialNotInListError,
    TopicNameRequiredError,
    TopicNotInListError,
    UserNotInListError,
)
from src.domain.models import Discipline, Material, Topic, User
from src.domain.validation import OptionalParser, parse_positive_int


class Picker:
    """Выбор записи из показанного списка: дисциплины, темы, материала или пользователя."""

    def __init__(self, io: ConsoleIO, presenter: Presenter) -> None:
        self._io = io
        self._presenter = presenter

    def pick_discipline(self, prompt: str, disciplines: list[Discipline]) -> Discipline:
        """Показать дисциплины и спросить одну из них по названию (без учёта регистра)."""
        return self._io.ask(prompt, self._discipline_parser(disciplines))

    def pick_optional_discipline(
        self, prompt: str, disciplines: list[Discipline]
    ) -> Discipline | None:
        """То же, что pick_discipline, но пустой ввод даёт None."""
        return self._io.ask(prompt, OptionalParser(self._discipline_parser(disciplines)))

    def pick_topic(self, prompt: str, topics: list[Topic]) -> Topic:
        """Показать темы и спросить одну из них по названию (без учёта регистра)."""
        return self._io.ask(prompt, self._topic_parser(topics))

    def pick_optional_topic(self, prompt: str, topics: list[Topic]) -> Topic | None:
        """То же, что pick_topic, но пустой ввод даёт None."""
        return self._io.ask(prompt, OptionalParser(self._topic_parser(topics)))

    def pick_material(self, prompt: str, materials: list[Material]) -> Material:
        """Напечатать материалы и спросить ID одного из них."""
        self._presenter.print_materials(materials)
        by_id = {m.id: m for m in materials}
        return self._io.ask(prompt, partial(self._parse_material, by_id=by_id))

    def pick_user(self, prompt: str, users: list[User]) -> User:
        """Напечатать пользователей и спросить ID одного из них."""
        self._presenter.print_users(users)
        by_id = {u.id: u for u in users}
        return self._io.ask(prompt, partial(self._parse_user, by_id=by_id))

    def _discipline_parser(self, disciplines: list[Discipline]) -> Callable[[str], Discipline]:
        """Напечатать названия дисциплин и вернуть парсер ответа."""
        print("Доступные дисциплины:")
        for discipline in disciplines:
            print(f"  • {discipline.name}")
        by_name = {d.name.casefold(): d for d in disciplines}
        return partial(self._parse_discipline, by_name=by_name)

    def _topic_parser(self, topics: list[Topic]) -> Callable[[str], Topic]:
        """Напечатать названия тем и вернуть парсер ответа."""
        print("Доступные темы:")
        for topic in topics:
            print(f"  • {topic.name}")
        by_name = {t.name.casefold(): t for t in topics}
        return partial(self._parse_topic, by_name=by_name)

    @staticmethod
    def _parse_discipline(raw: str, by_name: dict[str, Discipline]) -> Discipline:
        """Найти дисциплину по названию без учёта регистра."""
        found = by_name.get(raw.strip().casefold())
        if found is not None:
            return found
        if not raw.strip():
            raise DisciplineNameRequiredError()
        raise DisciplineNotInListError(name=raw.strip())

    @staticmethod
    def _parse_topic(raw: str, by_name: dict[str, Topic]) -> Topic:
        """Найти тему по названию без учёта регистра."""
        found = by_name.get(raw.strip().casefold())
        if found is not None:
            return found
        if not raw.strip():
            raise TopicNameRequiredError()
        raise TopicNotInListError(name=raw.strip())

    @staticmethod
    def _parse_material(raw: str, by_id: dict[int, Material]) -> Material:
        """Найти материал среди предложенных по введённому ID."""
        material_id = parse_positive_int(raw)
        found = by_id.get(material_id)
        if found is None:
            ids = ", ".join(str(i) for i in by_id)
            raise MaterialNotInListError(material_id=material_id, available_ids=ids)
        return found

    @staticmethod
    def _parse_user(raw: str, by_id: dict[int, User]) -> User:
        """Найти пользователя среди предложенных по введённому ID."""
        user_id = parse_positive_int(raw)
        found = by_id.get(user_id)
        if found is None:
            ids = ", ".join(str(i) for i in by_id)
            raise UserNotInListError(user_id=user_id, available_ids=ids)
        return found
