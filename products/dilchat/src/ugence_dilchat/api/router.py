"""Aggregate v1 router.

Deliberately excludes any Guna Milan, daily-transit, chat, agreement, or AI route
(Phase A/B scope). A guard test asserts no ``guna`` path is ever registered.
"""

from __future__ import annotations

from fastapi import APIRouter

from .routes import auth, birth_profiles, consent, couples, health, natal, users

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(birth_profiles.router)
api_router.include_router(natal.router)
api_router.include_router(couples.router)
api_router.include_router(consent.router)
