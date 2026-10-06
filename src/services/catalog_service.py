from __future__ import annotations

from src.domain.enums import EventType, Role
from src.domain.exceptions import (
    AuthorizationError,
    DuplicateEntityError,
    EntityNotFoundError,
)
from src.domain.models import Discipline, Topic, User
from src.domain.validation import require_text
from src.repositories.interfaces import DisciplineRepository, TopicRepository
from src.services.event_log_service import EventLogService

_CATALOG_MANAGER_ROLES = frozenset({Role.TEACHER, Role.ADMIN})


class CatalogService:
    """Manages the disciplines and topics that materials are classified under.

    Disciplines and topics are addressed by *name* (case-insensitive), not by
    numeric id, so users never have to look up or remember identifiers.
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
        """Return every discipline in the catalog."""
        return self._discipline_repository.list_all()

    def list_topics(self, discipline_id: int) -> list[Topic]:
        """Return every topic that belongs to the given discipline."""
        return self._topic_repository.list_by_discipline(discipline_id)

    def get_discipline_by_name(self, name: str) -> Discipline:
        """Find a discipline by name; the error lists the existing names."""
        discipline = self._discipline_repository.get_by_name(name.strip())
        if discipline is None:
            names = ", ".join(d.name for d in self.list_disciplines()) or "список пуст"
            raise EntityNotFoundError(
                f"Дисциплина «{name.strip()}» не найдена. Доступные дисциплины: {names}."
            )
        return discipline

    def get_topic_by_name(self, discipline_id: int, name: str) -> Topic:
        """Find a topic of the given discipline by name; the error lists the existing names."""
        topic = self._topic_repository.get_by_name(discipline_id, name.strip())
        if topic is None:
            names = ", ".join(t.name for t in self.list_topics(discipline_id)) or "список пуст"
            raise EntityNotFoundError(
                f"Тема «{name.strip()}» не найдена в этой дисциплине. Доступные темы: {names}."
            )
        return topic

    def describe(self, discipline_id: int, topic_id: int) -> str:
        """Return 'Дисциплина / Тема' for display; unknown ids are shown as '?'."""
        discipline = self._discipline_repository.get_by_id(discipline_id)
        topic = self._topic_repository.get_by_id(topic_id)
        return f"{discipline.name if discipline else '?'} / {topic.name if topic else '?'}"

    # --- проверки, которые интерфейс использует до отправки формы ---

    def ensure_discipline_name_free(self, name: str) -> str:
        """Return the cleaned name, or raise if it is empty or already taken."""
        cleaned = require_text(name, "Название дисциплины")
        if self._discipline_repository.get_by_name(cleaned) is not None:
            raise DuplicateEntityError(f"Дисциплина «{cleaned}» уже существует.")
        return cleaned

    def ensure_topic_name_free(self, discipline_id: int, name: str) -> str:
        """Return the cleaned name, or raise if it is empty or taken within the discipline."""
        cleaned = require_text(name, "Название темы")
        if self._topic_repository.get_by_name(discipline_id, cleaned) is not None:
            raise DuplicateEntityError(f"Тема «{cleaned}» уже есть в этой дисциплине.")
        return cleaned

    # --- изменение ---

    def create_discipline(self, requesting_user: User, name: str) -> Discipline:
        """Add a new discipline; only teachers or administrators may do this."""
        self._require_catalog_manager(requesting_user)
        cleaned = self.ensure_discipline_name_free(name)
        created = self._discipline_repository.add(Discipline(id=0, name=cleaned))
        self._event_log_service.record(
            requesting_user.id, EventType.DISCIPLINE_CREATED, created.name
        )
        return created

    def create_topic(self, requesting_user: User, name: str, discipline_id: int) -> Topic:
        """Add a new topic under a discipline; only teachers or administrators may do this."""
        self._require_catalog_manager(requesting_user)
        if self._discipline_repository.get_by_id(discipline_id) is None:
            raise EntityNotFoundError("Дисциплина не найдена.")
        cleaned = self.ensure_topic_name_free(discipline_id, name)
        created = self._topic_repository.add(Topic(id=0, name=cleaned, discipline_id=discipline_id))
        self._event_log_service.record(requesting_user.id, EventType.TOPIC_CREATED, created.name)
        return created

    def _require_catalog_manager(self, user: User) -> None:
        if user.role not in _CATALOG_MANAGER_ROLES:
            raise AuthorizationError(
                "Только преподаватели и администраторы могут управлять каталогом."
            )
