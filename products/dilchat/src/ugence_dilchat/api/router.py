"""Aggregate v1 router.

Includes the Phase 3A secure shared chat surface (``/conversations``). Deliberately
excludes any Guna Milan, daily-transit, agreement, or AI route. A guard test asserts
no ``guna``/compatibility path is ever registered.
"""

from __future__ import annotations

from fastapi import APIRouter

from .routes import auth, birth_profiles, chat, consent, couples, health, natal, users

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(birth_profiles.router)
api_router.include_router(natal.router)
api_router.include_router(couples.router)
api_router.include_router(consent.router)
api_router.include_router(chat.router)
