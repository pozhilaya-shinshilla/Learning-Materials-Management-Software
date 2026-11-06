"""Сборка ответов API, которым нужны данные из нескольких сервисов."""

from __future__ import annotations

from collections.abc import Iterable

from src.bootstrap import ApplicationContext
from src.domain.models import Material
from src.dtos.responses import MaterialResponse


def material_responses(
    context: ApplicationContext, materials: Iterable[Material]
) -> list[MaterialResponse]:
    """Собрать ответы по материалам и добавить логин автора (одно обращение на автора)."""
    logins: dict[int | None, str] = {}
    result: list[MaterialResponse] = []
    for material in materials:
        if material.author_id not in logins:
            logins[material.author_id] = context.user_management_service.get_author_login(
                material.author_id
            )
        response = MaterialResponse.from_domain(material)
        response.author_login = logins[material.author_id]
        result.append(response)
    return result


def material_response(context: ApplicationContext, material: Material) -> MaterialResponse:
    """Собрать ответ по одному материалу с логином автора."""
    return material_responses(context, [material])[0]
