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
from fastapi import Request, Response
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

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


class RequestTransactionMiddleware(BaseHTTPMiddleware):
    """Own the request transaction and finalize it BEFORE the response is sent.

    FastAPI runs yield-dependency teardown AFTER the response has been
    transmitted, so a commit placed there races the client's next request: a
    fast follow-up on another pooled connection could observe pre-commit state
    (e.g. a just-issued refresh token "not existing", an unpair "not yet
    happened"). ``call_next`` returns once the response is built but before it
    reaches the transport, so committing here closes that race for every route
    at once. Semantics are unchanged otherwise: 2xx/3xx commit, 4xx/5xx and
    escaped exceptions roll back — exactly what the old teardown did, earlier.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        sm = get_sessionmaker()
        async with sm() as session:
            request.state.dilchat_db_session = session
            try:
                response = await call_next(request)
            except Exception:
                await session.rollback()
                raise
            if response.status_code < 400:
                await session.commit()
            else:
                await session.rollback()
            return response


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: the per-request session/transaction.

    The session is owned by ``RequestTransactionMiddleware``, which commits or
    rolls back before the response leaves the process; this dependency only
    hands it out and applies the default pre-auth RLS context
    (``get_current_principal`` upgrades it to 'user'). The fallback path keeps
    the old commit-in-teardown behaviour for an app constructed without the
    middleware (defensive only — ``create_app`` always installs it).
    """
    owned = getattr(request.state, "dilchat_db_session", None)
    if owned is not None:
        await set_transaction_context(owned, actor_type="auth")
        yield owned
        return
    sm = get_sessionmaker()
    async with sm() as session:
        try:
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
