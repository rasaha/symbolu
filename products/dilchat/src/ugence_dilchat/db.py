"""Async database engine and session management.

Provides the engine/sessionmaker, a FastAPI dependency that yields a session with
an explicit transaction boundary (commit on success, rollback on error), and a
standalone ``transaction`` context manager used by background jobs.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from .config import Settings

_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def init_engine(settings: Settings) -> AsyncEngine:
    global _engine, _sessionmaker
    connect_args: dict = {}
    kwargs: dict = {"future": True}
    url = settings.database_url
    if url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
        # A single shared connection so an in-memory DB persists across sessions.
        kwargs["poolclass"] = StaticPool
    _engine = create_async_engine(url, connect_args=connect_args, **kwargs)
    _sessionmaker = async_sessionmaker(_engine, expire_on_commit=False, class_=AsyncSession)
    return _engine


def is_initialized() -> bool:
    return _engine is not None


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    if _sessionmaker is None:
        raise RuntimeError("Engine not initialised; call init_engine() first.")
    return _sessionmaker


async def dispose_engine() -> None:
    global _engine, _sessionmaker
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _sessionmaker = None


async def set_transaction_context(
    session: AsyncSession,
    *,
    user_id: uuid.UUID | None = None,
    actor_type: str = "auth",
    couple_id: uuid.UUID | None = None,
) -> None:
    """Set transaction-local RLS context (PostgreSQL only; no-op elsewhere).

    Uses ``set_config(..., is_local => true)`` so the values are scoped to the
    current transaction and cannot leak across pooled connections (DEC-030).
    Background workers must call this with their own actor/scope before writing.
    """
    if session.bind is None or session.bind.dialect.name != "postgresql":
        return
    await session.execute(
        sa.text("SELECT set_config('app.current_user_id', :v, true)"),
        {"v": str(user_id) if user_id else ""},
    )
    await session.execute(
        sa.text("SELECT set_config('app.current_actor_type', :v, true)"),
        {"v": actor_type},
    )
    await session.execute(
        sa.text("SELECT set_config('app.current_couple_id', :v, true)"),
        {"v": str(couple_id) if couple_id else ""},
    )


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: one transaction per request."""
    sm = get_sessionmaker()
    async with sm() as session:
        try:
            # Default pre-auth context; get_current_principal upgrades it to 'user'.
            await set_transaction_context(session, actor_type="auth")
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


@asynccontextmanager
async def transaction() -> AsyncIterator[AsyncSession]:
    """Explicit transaction boundary for background jobs and scripts."""
    sm = get_sessionmaker()
    async with sm() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
