"""Migration tests against a real PostgreSQL.

Marked ``postgres`` and skipped unless ``DILCHAT_TEST_DATABASE_URL`` points at a
live PostgreSQL. Verifies that migrations apply to a clean database, downgrade to
base, and re-apply from the prior state.
"""

from __future__ import annotations

import os
import pathlib

import pytest

pytestmark = pytest.mark.postgres

_DB_URL = os.environ.get("DILCHAT_TEST_DATABASE_URL")
_PRODUCT_ROOT = pathlib.Path(__file__).resolve().parents[2]

pytest.importorskip("asyncpg")
if not _DB_URL or "postgresql" not in _DB_URL:
    pytest.skip("DILCHAT_TEST_DATABASE_URL (PostgreSQL) not set", allow_module_level=True)

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402


def _alembic_config() -> Config:
    cfg = Config(str(_PRODUCT_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(_PRODUCT_ROOT / "migrations"))
    return cfg


def _tables() -> set[str]:
    import asyncio

    import sqlalchemy as sa
    from sqlalchemy.ext.asyncio import create_async_engine

    async def _run() -> set[str]:
        engine = create_async_engine(_DB_URL)
        try:
            async with engine.connect() as conn:
                names = await conn.run_sync(lambda c: set(sa.inspect(c).get_table_names()))
            return names
        finally:
            await engine.dispose()

    return asyncio.run(_run())


def test_migrations_apply_downgrade_reapply():
    # Ensure the app resolves this DB URL for the migration env.
    os.environ["DILCHAT_DATABASE_URL"] = _DB_URL
    os.environ["DILCHAT_ENVIRONMENT"] = "test"
    cfg = _alembic_config()

    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
    tables = _tables()
    expected = {
        "users", "user_sessions", "birth_profiles", "natal_chart_snapshots",
        "couples", "couple_memberships", "couple_invitations", "consent_events",
        "shared_artifacts", "audit_events",
    }
    assert expected <= tables

    command.downgrade(cfg, "base")
    after = _tables()
    assert not (expected & after)  # all app tables dropped

    command.upgrade(cfg, "head")
    assert expected <= _tables()
