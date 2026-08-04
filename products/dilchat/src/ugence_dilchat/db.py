"""Async database engine and session management.

Provides the engine/sessionmaker, a FastAPI dependency that yields a session with
an explicit transaction boundary (commit on success, rollback on error), and a
standalone ``transaction`` context manager used by background jobs.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

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


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: one transaction per request."""
    sm = get_sessionmaker()
    async with sm() as session:
        try:
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
