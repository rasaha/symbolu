"""Shared pytest fixtures.

API/integration/security tests run against a shared in-memory SQLite database
(fast, no server). Migration tests (marked ``postgres``) use a real PostgreSQL via
``DILCHAT_TEST_DATABASE_URL``. The httpx ASGITransport does not trigger the app
lifespan, so the pre-initialised in-memory engine is used throughout a test.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ugence_dilchat import db as db_module
from ugence_dilchat.app import create_app
from ugence_dilchat.base import Base
from ugence_dilchat.config import Environment, Settings


@dataclass
class Ctx:
    client: AsyncClient
    sessionmaker: async_sessionmaker[AsyncSession]
    settings: Settings
    app: object


@pytest_asyncio.fixture
async def ctx():
    settings = Settings(
        environment=Environment.TEST,
        database_url="sqlite+aiosqlite://",
        astrology_provider="fake",
        # High-volume 3A tests legitimately send >30 messages/minute; raise the
        # SEND windows so they are not throttled. The ratified production
        # defaults are pinned by tests/unit/test_ratified_rate_limits.py, and
        # enforcement is proven by seeding counters to the configured limit
        # (tests/integration/test_safety_flows.py), independent of the values.
        ratelimit_send_per_minute=10_000,
        ratelimit_send_per_hour=100_000,
    )
    engine = db_module.init_engine(settings)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    app = create_app(settings)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield Ctx(
            client=client,
            sessionmaker=db_module.get_sessionmaker(),
            settings=settings,
            app=app,
        )
    await db_module.dispose_engine()
