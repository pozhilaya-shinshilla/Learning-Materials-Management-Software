from __future__ import annotations

from src.domain.enums import EventType, Role
from src.domain.exceptions import (
    CatalogAccessError,
    DisciplineNotFoundError,
    DuplicateDisciplineError,
    DuplicateTopicError,
    NameUnchangedError,
    TopicNotFoundError,
    UnknownDisciplineError,
    UnknownTopicError,
)
from src.domain.models import Discipline, Topic, User
from src.domain.validation import require_text
from src.repositories.interfaces import DisciplineRepository, TopicRepository
from src.services.event_log_service import EventLogService

_CATALOG_MANAGER_ROLES = frozenset({Role.TEACHER, Role.ADMIN})


class CatalogService:
    """Управляет дисциплинами и темами, по которым классифицируются материалы.

    Дисциплины и темы задаются по *названию* (без учёта регистра), а не по
    числовому id, поэтому пользователю не нужно запоминать идентификаторы.
    """

    def __init__(
        self,
        discipline_repository: DisciplineRepository,
        topic_repository: TopicRepository,
        event_log_service: EventLogService,
    ) -> None:
        self._discipline_repository = discipline_repository
        self._topic_repository = topic_repository
        self._event_log_service = event_log_service

    # --- чтение ---

    def list_disciplines(self) -> list[Discipline]:
        """Вернуть все дисциплины каталога."""
        return self._discipline_repository.list_all()

    def list_topics(self, discipline_id: int) -> list[Topic]:
        """Вернуть все темы указанной дисциплины."""
        return self._topic_repository.list_by_discipline(discipline_id)

    def get_discipline_by_name(self, name: str) -> Discipline:
        """Найти дисциплину по названию; в тексте ошибки перечислены существующие названия."""
        discipline = self._discipline_repository.get_by_name(name.strip())
        if discipline is None:
            names = ", ".join(d.name for d in self.list_disciplines()) or "список пуст"
            raise DisciplineNotFoundError(name=name.strip(), available=names)
        return discipline

    def get_topic_by_name(self, discipline_id: int, name: str) -> Topic:
        """Найти тему дисциплины по названию; в тексте ошибки перечислены существующие названия."""
        topic = self._topic_repository.get_by_name(discipline_id, name.strip())
        if topic is None:
            names = ", ".join(t.name for t in self.list_topics(discipline_id)) or "список пуст"
            raise TopicNotFoundError(name=name.strip(), available=names)
        return topic

    def describe(self, discipline_id: int, topic_id: int) -> str:
        """Вернуть строку «Дисциплина / Тема» для показа; неизвестные id выводятся как «?»."""
        discipline = self._discipline_repository.get_by_id(discipline_id)
        topic = self._topic_repository.get_by_id(topic_id)
        return f"{discipline.name if discipline else '?'} / {topic.name if topic else '?'}"

    # --- проверки, которые интерфейс использует до отправки формы ---

    def ensure_discipline_name_free(self, name: str, *, exclude_id: int | None = None) -> str:
        """Вернуть очищенное название или выбросить ошибку, если оно пусто или занято.

        `exclude_id` — дисциплина, которую переименовывают: её собственное имя не считается занятым.
        """
        cleaned = require_text(name, "Название дисциплины")
        existing = self._discipline_repository.get_by_name(cleaned)
        if existing is not None and existing.id != exclude_id:
            raise DuplicateDisciplineError(name=cleaned)
        return cleaned

    def ensure_topic_name_free(
        self, discipline_id: int, name: str, *, exclude_id: int | None = None
    ) -> str:
        """Вернуть очищенное название или выбросить ошибку, если оно пусто или занято.

        Название должно быть уникальным внутри дисциплины. `exclude_id` — тема, которую
        переименовывают.
        """
        cleaned = require_text(name, "Название темы")
        existing = self._topic_repository.get_by_name(discipline_id, cleaned)
        if existing is not None and existing.id != exclude_id:
            raise DuplicateTopicError(name=cleaned)
        return cleaned

    def validate_discipline_rename(self, discipline: Discipline, new_name: str) -> str:
        """Проверить новое название дисциплины и вернуть его очищенным."""
        cleaned = self.ensure_discipline_name_free(new_name, exclude_id=discipline.id)
        if cleaned == discipline.name:
            raise NameUnchangedError()
        return cleaned

    def validate_topic_rename(self, topic: Topic, new_name: str) -> str:
        """Проверить новое название темы и вернуть его очищенным."""
        cleaned = self.ensure_topic_name_free(topic.discipline_id, new_name, exclude_id=topic.id)
        if cleaned == topic.name:
            raise NameUnchangedError()
        return cleaned

    # --- изменение ---

    def create_discipline(self, requesting_user: User, name: str) -> Discipline:
        """Добавить дисциплину; доступно только преподавателям и администраторам."""
        self._require_catalog_manager(requesting_user)
        cleaned = self.ensure_discipline_name_free(name)
        created = self._discipline_repository.add(Discipline(id=0, name=cleaned))
        self._event_log_service.record(
            requesting_user.id, EventType.DISCIPLINE_CREATED, created.name
        )
        return created

    def create_topic(self, requesting_user: User, name: str, discipline_id: int) -> Topic:
        """Добавить тему в дисциплину; доступно только преподавателям и администраторам."""
        self._require_catalog_manager(requesting_user)
        if self._discipline_repository.get_by_id(discipline_id) is None:
            raise UnknownDisciplineError()
        cleaned = self.ensure_topic_name_free(discipline_id, name)
        created = self._topic_repository.add(Topic(id=0, name=cleaned, discipline_id=discipline_id))
        self._event_log_service.record(requesting_user.id, EventType.TOPIC_CREATED, created.name)
        return created

    def rename_discipline(
        self, requesting_user: User, discipline_id: int, new_name: str
    ) -> Discipline:
        """Переименовать дисциплину; доступно только преподавателям и администраторам."""
        self._require_catalog_manager(requesting_user)
        discipline = self._discipline_repository.get_by_id(discipline_id)
        if discipline is None:
            raise UnknownDisciplineError()
        old_name = discipline.name
        discipline.name = self.validate_discipline_rename(discipline, new_name)
        self._discipline_repository.update(discipline)
        self._event_log_service.record(
            requesting_user.id,
            EventType.DISCIPLINE_RENAMED,
            f"{old_name} -> {discipline.name}",
        )
        return discipline

    def rename_topic(self, requesting_user: User, topic_id: int, new_name: str) -> Topic:
        """Переименовать тему; доступно только преподавателям и администраторам."""
        self._require_catalog_manager(requesting_user)
        topic = self._topic_repository.get_by_id(topic_id)
        if topic is None:
            raise UnknownTopicError()
        old_name = topic.name
        topic.name = self.validate_topic_rename(topic, new_name)
        self._topic_repository.update(topic)
        self._event_log_service.record(
            requesting_user.id, EventType.TOPIC_RENAMED, f"{old_name} -> {topic.name}"
        )
        return topic

    def _require_catalog_manager(self, user: User) -> None:
        """Пропустить только преподавателя или администратора."""
        if user.role not in _CATALOG_MANAGER_ROLES:
            raise CatalogAccessError()
