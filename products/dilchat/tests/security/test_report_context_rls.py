"""PostgreSQL semantics of the ``app_conversation_context`` definer helper.

Mirrors ``test_chat_safety_rls.py``: seed as the owner, assert under the real
NON-OWNER ``dilchat_app`` role. The helper exists because RLS keys
``chat_conversations`` visibility on ACTIVE membership, yet the post-revocation
reporting window must let a FORMER member address their ended conversation. It
returns only ``couple_id``/``status``/``revoked_at`` — bounded facts, no
content — and nothing at all to a stranger.
"""

from __future__ import annotations

import datetime as dt
import os
import uuid

import pytest

pytestmark = pytest.mark.postgres

_DB_URL = os.environ.get("DILCHAT_TEST_DATABASE_URL")
asyncpg = pytest.importorskip("asyncpg")
if not _DB_URL or "postgresql" not in _DB_URL:
    pytest.skip("DILCHAT_TEST_DATABASE_URL (PostgreSQL) not set", allow_module_level=True)


def _dsn() -> dict:
    from urllib.parse import parse_qs, urlparse

    u = urlparse(_DB_URL.replace("+asyncpg", ""))
    q = parse_qs(u.query)
    dsn = {
        "user": u.username or "postgres",
        "database": u.path.lstrip("/"),
        "host": q.get("host", [u.hostname or "/tmp"])[0],
        "port": int(q.get("port", [str(u.port or 5432)])[0]),
    }
    if u.password:
        dsn["password"] = u.password
    return dsn


async def _connect():
    return await asyncpg.connect(**_dsn())


async def _seed(conn, *, revoke: bool):
    ids = {k: uuid.uuid4() for k in ("a", "b", "stranger", "couple1", "conv1")}
    await conn.execute("SET ROLE postgres")
    for who in ("a", "b", "stranger"):
        await conn.execute(
            "INSERT INTO users (id,email,credential_hash,status,created_at,updated_at) "
            "VALUES ($1,$2,'h','ACTIVE',now(),now())",
            ids[who], f"{who}_{ids[who].hex[:8]}@e.com",
        )
    await conn.execute(
        "INSERT INTO couples (id,status,created_at,updated_at) "
        "VALUES ($1,$2,now(),now())", ids["couple1"], "UNPAIRED" if revoke else "ACTIVE",
    )
    m_status = "REVOKED" if revoke else "ACTIVE"
    for member, slot in (("a", "A"), ("b", "B")):
        await conn.execute(
            "INSERT INTO couple_memberships (id,couple_id,user_id,scope_slot,status,joined_at) "
            "VALUES ($1,$2,$3,$4,$5,now())",
            uuid.uuid4(), ids["couple1"], ids[member], slot, m_status,
        )
    await conn.execute(
        "INSERT INTO chat_conversations "
        "(id,couple_id,status,next_sequence,version,revoked_at,created_at,updated_at) "
        "VALUES ($1,$2,$3,1,1,$4,now(),now())",
        ids["conv1"], ids["couple1"], "REVOKED" if revoke else "ACTIVE",
        dt.datetime.now(dt.UTC) if revoke else None,
    )
    await conn.execute("RESET ROLE")
    return ids


async def _as(conn, user_id, coro, *, role="dilchat_app", actor="user"):
    async with conn.transaction():
        await conn.execute(f"SET LOCAL ROLE {role}")
        await conn.execute("SELECT set_config('app.current_user_id',$1,true)", str(user_id or ""))
        await conn.execute("SELECT set_config('app.current_actor_type',$1,true)", actor)
        return await coro(conn)


async def test_former_member_gets_bounded_context_despite_rls():
    conn = await _connect()
    try:
        ids = await _seed(conn, revoke=True)

        async def direct_select(c):
            return await c.fetchrow(
                "SELECT id FROM chat_conversations WHERE id = $1", ids["conv1"]
            )

        async def via_helper(c):
            return await c.fetchrow(
                "SELECT couple_id, status, revoked_at FROM app_conversation_context($1)",
                ids["conv1"],
            )

        # RLS hides the revoked conversation from the former member entirely...
        assert await _as(conn, ids["a"], direct_select) is None
        # ...but the bounded helper returns exactly the reporting facts.
        row = await _as(conn, ids["a"], via_helper)
        assert row is not None
        assert row["couple_id"] == ids["couple1"]
        assert row["status"] == "REVOKED"
        assert row["revoked_at"] is not None
    finally:
        await conn.close()


async def test_stranger_gets_nothing_from_the_helper():
    conn = await _connect()
    try:
        ids = await _seed(conn, revoke=True)

        async def via_helper(c):
            return await c.fetchrow(
                "SELECT couple_id FROM app_conversation_context($1)", ids["conv1"]
            )

        assert await _as(conn, ids["stranger"], via_helper) is None
        # An unknown conversation id is equally empty (no existence oracle).
        async def unknown(c):
            return await c.fetchrow(
                "SELECT couple_id FROM app_conversation_context($1)", uuid.uuid4()
            )

        assert await _as(conn, ids["a"], unknown) is None
    finally:
        await conn.close()


async def test_active_member_also_resolves_context():
    conn = await _connect()
    try:
        ids = await _seed(conn, revoke=False)

        async def via_helper(c):
            return await c.fetchrow(
                "SELECT status, revoked_at FROM app_conversation_context($1)", ids["conv1"]
            )

        row = await _as(conn, ids["b"], via_helper)
        assert row is not None and row["status"] == "ACTIVE" and row["revoked_at"] is None
    finally:
        await conn.close()
