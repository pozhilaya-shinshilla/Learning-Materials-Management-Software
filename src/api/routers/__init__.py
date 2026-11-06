"""Роутеры REST API: по одному модулю на раздел."""

from fastapi import APIRouter

from src.api.routers import auth, disciplines, events, favorites, materials, topics, users

ALL_ROUTERS: list[APIRouter] = [
    auth.router,
    materials.router,
    disciplines.router,
    topics.router,
    favorites.router,
    users.router,
    events.router,
]
