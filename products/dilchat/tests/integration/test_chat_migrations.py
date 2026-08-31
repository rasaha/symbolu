"""Migration/backfill tests for the secure-chat migration on real PostgreSQL.

Verifies the ``c3d4e5f6a7b8`` migration: exactly one head, deterministic
downgrade/re-upgrade, and that the active-pair conversation backfill creates one
ACTIVE conversation per ACTIVE couple while REVOKED (UNPAIRED) couples receive none.
"""

from __future__ import annotations

import asyncio
import os
import pathlib
import uuid

import pytest

pytestmark = pytest.mark.postgres

_DB_URL = os.environ.get("DILCHAT_TEST_DATABASE_URL")
_PRODUCT_ROOT = pathlib.Path(__file__).resolve().parents[2]
asyncpg = pytest.importorskip("asyncpg")
if not _DB_URL or "postgresql" not in _DB_URL:
    pytest.skip("DILCHAT_TEST_DATABASE_URL (PostgreSQL) not set", allow_module_level=True)

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from alembic.script import ScriptDirectory  # noqa: E402

_PRE_CHAT = "b2c3d4e5f6a7"  # the revision immediately before the chat migration


def _cfg() -> Config:
    cfg = Config(str(_PRODUCT_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(_PRODUCT_ROOT / "migrations"))
    return cfg


def _dsn() -> str:
    from urllib.parse import parse_qs, urlparse

    u = urlparse(_DB_URL.replace("+asyncpg", ""))
    q = parse_qs(u.query)
    host = q.get("host", [u.hostname or "/tmp"])[0]
    port = q.get("port", [str(u.port or 5432)])[0]
    auth = u.username or "postgres"
    if u.password:
        auth = f"{auth}:{u.password}"
    return f"postgresql://{auth}@{host}:{port}/{u.path.lstrip('/')}"


async def _seed_couples() -> dict:
    """Seed one ACTIVE and one UNPAIRED couple (at the pre-chat schema)."""
    conn = await asyncpg.connect(dsn=_dsn())
    ids = {k: uuid.uuid4() for k in ("active", "unpaired", "ua", "ub", "uc", "ud")}
    try:
        for who in ("ua", "ub", "uc", "ud"):
            await conn.execute(
                "INSERT INTO users (id,email,credential_hash,status,created_at,updated_at) "
                "VALUES ($1,$2,'h','ACTIVE',now(),now())",
                ids[who], f"{who}_{ids[who].hex[:8]}@e.com",
            )
        await conn.execute(
            "INSERT INTO couples (id,status,created_at,updated_at) "
            "VALUES ($1,'ACTIVE',now(),now())", ids["active"],
        )
        await conn.execute(
            "INSERT INTO couples (id,status,unpaired_at,created_at,updated_at) "
            "VALUES ($1,'UNPAIRED',now(),now(),now())", ids["unpaired"],
        )
        await conn.execute(
            "INSERT INTO couple_memberships (id,couple_id,user_id,scope_slot,status,joined_at) "
            "VALUES ($1,$2,$3,'A','ACTIVE',now())", uuid.uuid4(), ids["active"], ids["ua"],
        )
        await conn.execute(
            "INSERT INTO couple_memberships (id,couple_id,user_id,scope_slot,status,joined_at) "
            "VALUES ($1,$2,$3,'B','ACTIVE',now())", uuid.uuid4(), ids["active"], ids["ub"],
        )
        await conn.execute(
            "INSERT INTO couple_memberships (id,couple_id,user_id,scope_slot,status,joined_at) "
            "VALUES ($1,$2,$3,'A','REVOKED',now())", uuid.uuid4(), ids["unpaired"], ids["uc"],
        )
    finally:
        await conn.close()
    return ids


async def _conv_rows(couple_id) -> list:
    conn = await asyncpg.connect(dsn=_dsn())
    try:
        return await conn.fetch(
            "SELECT status FROM chat_conversations WHERE couple_id=$1", couple_id
        )
    finally:
        await conn.close()


async def _outbox_created(couple_id) -> int:
    conn = await asyncpg.connect(dsn=_dsn())
    try:
        return await conn.fetchval(
            "SELECT count(*) FROM chat_outbox "
            "WHERE couple_id=$1 AND event_type='CONVERSATION_CREATED'",
            couple_id,
        )
    finally:
        await conn.close()


def test_exactly_one_head():
    script = ScriptDirectory.from_config(_cfg())
    assert len(script.get_heads()) == 1
    assert script.get_current_head() == "a7b8c9d0e1f2"


def test_backfill_active_only_and_downgrade_reupgrade():
    os.environ["DILCHAT_DATABASE_URL"] = _DB_URL
    os.environ["DILCHAT_ENVIRONMENT"] = "test"
    cfg = _cfg()

    # Roll back to just before the chat migration, seed couples, then upgrade.
    command.downgrade(cfg, _PRE_CHAT)
    ids = asyncio.run(_seed_couples())
    command.upgrade(cfg, "head")

    active_rows = asyncio.run(_conv_rows(ids["active"]))
    unpaired_rows = asyncio.run(_conv_rows(ids["unpaired"]))
    assert len(active_rows) == 1 and active_rows[0]["status"] == "ACTIVE"
    assert len(unpaired_rows) == 0  # revoked couples get no active conversation
    assert asyncio.run(_outbox_created(ids["active"])) == 1

    # Downgrade removes chat tables; re-upgrade backfills again (idempotent shape).
    command.downgrade(cfg, _PRE_CHAT)
    command.upgrade(cfg, "head")
    active_again = asyncio.run(_conv_rows(ids["active"]))
    assert len(active_again) == 1 and active_again[0]["status"] == "ACTIVE"
