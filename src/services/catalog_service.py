from __future__ import annotations

from src.domain.enums import EventType, Role
from src.domain.exceptions import AuthorizationError, ValidationError
from src.domain.models import Discipline, Topic, User
from src.repositories.interfaces import DisciplineRepository, TopicRepository
from src.services.event_log_service import EventLogService

_CATALOG_MANAGER_ROLES = frozenset({Role.TEACHER, Role.ADMIN})


class CatalogService:
    """Manages the disciplines and topics that materials are classified under."""

    def __init__(
        self,
        discipline_repository: DisciplineRepository,
        topic_repository: TopicRepository,
        event_log_service: EventLogService,
    ) -> None:
        self._discipline_repository = discipline_repository
        self._topic_repository = topic_repository
        self._event_log_service = event_log_service

    def list_disciplines(self) -> list[Discipline]:
        """Return every discipline in the catalog."""
        return self._discipline_repository.list_all()

    def list_topics(self, discipline_id: int) -> list[Topic]:
        """Return every topic that belongs to the given discipline."""
        return self._topic_repository.list_by_discipline(discipline_id)

    def create_discipline(self, requesting_user: User, name: str) -> Discipline:
        """Add a new discipline; only teachers or administrators may do this."""
        self._require_catalog_manager(requesting_user)
        if not name:
            raise ValidationError("Название дисциплины обязательно.")
        created = self._discipline_repository.add(Discipline(id=0, name=name))
        self._event_log_service.record(
            requesting_user.id, EventType.DISCIPLINE_CREATED, created.name
        )
        return created

    def create_topic(self, requesting_user: User, name: str, discipline_id: int) -> Topic:
        """Add a new topic under a discipline; only teachers or administrators may do this."""
        self._require_catalog_manager(requesting_user)
        if self._discipline_repository.get_by_id(discipline_id) is None:
            raise ValidationError(f"Дисциплина с id {discipline_id} не найдена.")
        if not name:
            raise ValidationError("Название темы обязательно.")
        created = self._topic_repository.add(Topic(id=0, name=name, discipline_id=discipline_id))
        self._event_log_service.record(requesting_user.id, EventType.TOPIC_CREATED, created.name)
        return created

    def _require_catalog_manager(self, user: User) -> None:
        if user.role not in _CATALOG_MANAGER_ROLES:
            raise AuthorizationError(
                "Только преподаватели и администраторы могут управлять каталогом."
            )
