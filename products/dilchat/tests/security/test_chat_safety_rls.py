"""PostgreSQL RLS for the Phase 3B chat-safety tables, via real NON-OWNER roles.

Mirrors ``tests/security/test_chat_rls.py``: seed as the owner (bypasses RLS), then
run every assertion under ``SET LOCAL ROLE dilchat_app`` / ``dilchat_safety`` (both
NOBYPASSRLS) with a transaction-local ``app.current_user_id`` context. Proves the
DB layer independently keeps a block invisible to the blocked user, answers the
bidirectional ``app_block_exists`` check anyway, and keeps evidence, cases, and
case events INTERNAL (the app role may never read them; only ``dilchat_safety``).
"""

from __future__ import annotations

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


async def _seed(conn):
    """Seed a couple (a, b) + conversation + message, an ACTIVE block a->b, and one
    report (by a) with its internal case, evidence snapshot, and case event."""
    ids = {k: uuid.uuid4() for k in (
        "a", "b", "stranger", "couple1", "conv1", "msg1", "block1", "case1",
        "report1", "evidence1", "caseevt1",
    )}
    await conn.execute("SET ROLE postgres")
    for who in ("a", "b", "stranger"):
        await conn.execute(
            "INSERT INTO users (id,email,credential_hash,status,created_at,updated_at) "
            "VALUES ($1,$2,'h','ACTIVE',now(),now())",
            ids[who], f"{who}_{ids[who].hex[:8]}@e.com",
        )
    await conn.execute(
        "INSERT INTO couples (id,status,created_at,updated_at) "
        "VALUES ($1,'ACTIVE',now(),now())", ids["couple1"],
    )
    for member, slot in (("a", "A"), ("b", "B")):
        await conn.execute(
            "INSERT INTO couple_memberships (id,couple_id,user_id,scope_slot,status,joined_at) "
            "VALUES ($1,$2,$3,$4,'ACTIVE',now())",
            uuid.uuid4(), ids["couple1"], ids[member], slot,
        )
    await conn.execute(
        "INSERT INTO chat_conversations "
        "(id,couple_id,status,next_sequence,version,created_at,updated_at) "
        "VALUES ($1,$2,'ACTIVE',2,1,now(),now())", ids["conv1"], ids["couple1"],
    )
    await conn.execute(
        "INSERT INTO chat_messages "
        "(id,conversation_id,couple_id,sender_user_id,client_message_id,server_sequence,"
        " body,created_at) VALUES ($1,$2,$3,$4,'k1',1,'hello',now())",
        ids["msg1"], ids["conv1"], ids["couple1"], ids["b"],
    )
    await conn.execute(
        "INSERT INTO chat_user_blocks "
        "(id,blocker_user_id,blocked_user_id,status,created_at,updated_at) "
        "VALUES ($1,$2,$3,'ACTIVE',now(),now())",
        ids["block1"], ids["a"], ids["b"],
    )
    await conn.execute(
        "INSERT INTO chat_safety_cases (id,state,conversation_id,couple_id,"
        " created_at,updated_at) VALUES ($1,'OPEN',$2,$3,now(),now())",
        ids["case1"], ids["conv1"], ids["couple1"],
    )
    await conn.execute(
        "INSERT INTO chat_reports "
        "(id,reporter_user_id,conversation_id,couple_id,target_type,target_message_id,"
        " reason,status,case_id,client_report_id,created_at,updated_at) "
        "VALUES ($1,$2,$3,$4,'MESSAGE',$5,'HARASSMENT','SUBMITTED',$6,'r1',now(),now())",
        ids["report1"], ids["a"], ids["conv1"], ids["couple1"], ids["msg1"], ids["case1"],
    )
    await conn.execute(
        "INSERT INTO chat_report_evidence "
        "(id,report_id,evidence_sequence,source_conversation_id,source_message_id,"
        " source_sender_id,source_server_sequence,body_snapshot,integrity_sha256,created_at) "
        "VALUES ($1,$2,1,$3,$4,$5,1,'hello',$6,now())",
        ids["evidence1"], ids["report1"], ids["conv1"], ids["msg1"], ids["b"], "a" * 64,
    )
    await conn.execute(
        "INSERT INTO chat_safety_case_events "
        "(id,case_id,event_type,actor_type,created_at) "
        "VALUES ($1,$2,'CASE_OPENED','SYSTEM',now())",
        ids["caseevt1"], ids["case1"],
    )
    await conn.execute("RESET ROLE")
    return ids


async def _as(conn, user_id, coro, *, role="dilchat_app", actor="user"):
    async with conn.transaction():
        await conn.execute(f"SET LOCAL ROLE {role}")
        await conn.execute("SELECT set_config('app.current_user_id',$1,true)", str(user_id or ""))
        await conn.execute("SELECT set_config('app.current_actor_type',$1,true)", actor)
        return await coro(conn)


async def test_block_visible_to_blocker_and_invisible_to_blocked_user():
    conn = await _connect()
    try:
        ids = await _seed(conn)

        async def count_blocks(c):
            return await c.fetchval("SELECT count(*) FROM chat_user_blocks")

        assert await _as(conn, ids["a"], count_blocks) == 1  # blocker sees own block
        assert await _as(conn, ids["b"], count_blocks) == 0  # blocked user sees nothing
        assert await _as(conn, ids["stranger"], count_blocks) == 0
    finally:
        await conn.close()


async def test_app_block_exists_is_bidirectional_despite_blocker_only_rls():
    conn = await _connect()
    try:
        ids = await _seed(conn)

        def exists_vs(other):
            async def probe(c):
                return await c.fetchval("SELECT app_block_exists($1)", other)
            return probe

        # The blocker sees it; the blocked user gets the same answer even though
        # the row itself is invisible to them (SECURITY DEFINER bypasses RLS).
        assert await _as(conn, ids["a"], exists_vs(ids["b"])) is True
        assert await _as(conn, ids["b"], exists_vs(ids["a"])) is True
        assert await _as(conn, ids["stranger"], exists_vs(ids["a"])) is False
        assert await _as(conn, ids["a"], exists_vs(ids["stranger"])) is False
    finally:
        await conn.close()


async def test_app_role_cannot_read_evidence_cases_or_case_events():
    conn = await _connect()
    try:
        ids = await _seed(conn)

        scoped = (
            ("chat_report_evidence", "report_id", ids["report1"]),
            ("chat_safety_cases", "id", ids["case1"]),
            ("chat_safety_case_events", "case_id", ids["case1"]),
        )
        for table, key_col, key in scoped:
            async def read_internal(c, t=table, k=key_col, v=key):
                return await c.fetchval(f"SELECT count(*) FROM {t} WHERE {k} = $1", v)

            # App actor: no SELECT privilege at all -> permission denied, even for
            # the reporter whose own report produced the rows.
            with pytest.raises(asyncpg.PostgresError):
                await _as(conn, ids["a"], read_internal)
            # Safety role: may read every INTERNAL table.
            assert await _as(
                conn, ids["a"], read_internal, role="dilchat_safety", actor="safety"
            ) == 1
    finally:
        await conn.close()


async def test_safety_role_reads_blocks_and_reports():
    conn = await _connect()
    try:
        ids = await _seed(conn)

        async def count_blocks(c):
            return await c.fetchval(
                "SELECT count(*) FROM chat_user_blocks WHERE id = $1", ids["block1"]
            )

        async def count_reports(c):
            return await c.fetchval(
                "SELECT count(*) FROM chat_reports WHERE id = $1", ids["report1"]
            )

        assert await _as(
            conn, ids["a"], count_blocks, role="dilchat_safety", actor="safety"
        ) == 1
        assert await _as(
            conn, ids["a"], count_reports, role="dilchat_safety", actor="safety"
        ) == 1
        # The safety role is a genuine non-owner: NOSUPERUSER and NOBYPASSRLS.
        async def role_props(c):
            return await c.fetchrow(
                "SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user"
            )

        props = await _as(conn, ids["a"], role_props, role="dilchat_safety", actor="safety")
        assert props["rolsuper"] is False
        assert props["rolbypassrls"] is False
    finally:
        await conn.close()
