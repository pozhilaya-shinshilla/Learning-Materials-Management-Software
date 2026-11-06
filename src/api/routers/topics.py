"""Темы внутри дисциплин."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response, status

from src.api.dependencies import ContextDep, CurrentUser, get_current_user
from src.api.errors import ERROR_RESPONSES
from src.api.params import TopicId
from src.dtos.requests import TopicCreateRequest, TopicUpdateRequest
from src.dtos.responses import TopicResponse

router = APIRouter(
    prefix="/api/topics",
    tags=["Темы"],
    responses={401: ERROR_RESPONSES[401], 403: ERROR_RESPONSES[403]},
)


@router.get(
    "",
    response_model=list[TopicResponse],
    summary="Список тем (можно отфильтровать по дисциплине)",
    dependencies=[Depends(get_current_user)],
)
def list_topics(
    context: ContextDep, discipline_id: int | None = Query(default=None, gt=0)
) -> list[TopicResponse]:
    """Вернуть темы всех дисциплин или только указанной."""
    service = context.catalog_service
    topics = (
        service.list_all_topics() if discipline_id is None else service.list_topics(discipline_id)
    )
    return [TopicResponse.from_domain(topic) for topic in topics]


@router.get(
    "/{topic_id}",
    response_model=TopicResponse,
    summary="Сведения о теме",
    dependencies=[Depends(get_current_user)],
    responses={404: ERROR_RESPONSES[404]},
)
def get_topic(topic_id: TopicId, context: ContextDep) -> TopicResponse:
    """Вернуть тему по id."""
    return TopicResponse.from_domain(context.catalog_service.get_topic(topic_id))


@router.post(
    "",
    response_model=TopicResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Создание темы",
    responses={403: ERROR_RESPONSES[403], 404: ERROR_RESPONSES[404], 409: ERROR_RESPONSES[409]},
)
def create_topic(body: TopicCreateRequest, user: CurrentUser, context: ContextDep) -> TopicResponse:
    """Создать тему в дисциплине (преподаватель или администратор)."""
    created = context.catalog_service.create_topic(user, body.name, body.discipline_id)
    return TopicResponse.from_domain(created)


@router.patch(
    "/{topic_id}",
    response_model=TopicResponse,
    summary="Частичное изменение темы",
    responses={403: ERROR_RESPONSES[403], 404: ERROR_RESPONSES[404], 409: ERROR_RESPONSES[409]},
)
def update_topic(
    topic_id: TopicId, body: TopicUpdateRequest, user: CurrentUser, context: ContextDep
) -> TopicResponse:
    """Переименовать тему (преподаватель или администратор)."""
    if body.name is None:
        return TopicResponse.from_domain(context.catalog_service.get_topic(topic_id))
    return TopicResponse.from_domain(
        context.catalog_service.rename_topic(user, topic_id, body.name)
    )


@router.delete(
    "/{topic_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Удаление темы",
    responses={403: ERROR_RESPONSES[403], 404: ERROR_RESPONSES[404], 409: ERROR_RESPONSES[409]},
)
def delete_topic(topic_id: TopicId, user: CurrentUser, context: ContextDep) -> Response:
    """Удалить тему без материалов (преподаватель или администратор); с материалами — 409."""
    context.catalog_service.delete_topic(user, topic_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
