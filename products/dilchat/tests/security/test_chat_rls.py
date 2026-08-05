"""PostgreSQL RLS for the secure-chat tables, via a real NON-OWNER runtime role.

Mirrors ``tests/security/test_rls.py``: seed as the owner (bypasses RLS), then run
every assertion under ``SET LOCAL ROLE dilchat_app`` / ``dilchat_worker`` (both
NOBYPASSRLS) with a transaction-local ``app.current_user_id`` context. Proves the
DB layer independently denies cross-couple access, enforces sender-only writes,
and keeps the outbox off the user API surface.
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
    ids = {k: uuid.uuid4() for k in (
        "a", "b", "c", "d", "stranger", "couple1", "couple2", "conv1", "conv2",
        "msg1", "msg2",
    )}
    await conn.execute("SET ROLE postgres")
    for who in ("a", "b", "c", "d", "stranger"):
        await conn.execute(
            "INSERT INTO users (id,email,credential_hash,status,created_at,updated_at) "
            "VALUES ($1,$2,'h','ACTIVE',now(),now())",
            ids[who], f"{who}_{ids[who].hex[:8]}@e.com",
        )
    for couple, (m1, m2) in (("couple1", ("a", "b")), ("couple2", ("c", "d"))):
        await conn.execute(
            "INSERT INTO couples (id,status,created_at,updated_at) "
            "VALUES ($1,'ACTIVE',now(),now())",
            ids[couple],
        )
        await conn.execute(
            "INSERT INTO couple_memberships (id,couple_id,user_id,scope_slot,status,joined_at) "
            "VALUES ($1,$2,$3,'A','ACTIVE',now())", uuid.uuid4(), ids[couple], ids[m1],
        )
        await conn.execute(
            "INSERT INTO couple_memberships (id,couple_id,user_id,scope_slot,status,joined_at) "
            "VALUES ($1,$2,$3,'B','ACTIVE',now())", uuid.uuid4(), ids[couple], ids[m2],
        )
    for conv, couple in (("conv1", "couple1"), ("conv2", "couple2")):
        await conn.execute(
            "INSERT INTO chat_conversations "
            "(id,couple_id,status,next_sequence,version,created_at,updated_at) "
            "VALUES ($1,$2,'ACTIVE',2,1,now(),now())", ids[conv], ids[couple],
        )
    await conn.execute(
        "INSERT INTO chat_messages "
        "(id,conversation_id,couple_id,sender_user_id,client_message_id,server_sequence,"
        " body,created_at) VALUES ($1,$2,$3,$4,'k1',1,'hello',now())",
        ids["msg1"], ids["conv1"], ids["couple1"], ids["a"],
    )
    await conn.execute(
        "INSERT INTO chat_messages "
        "(id,conversation_id,couple_id,sender_user_id,client_message_id,server_sequence,"
        " body,created_at) VALUES ($1,$2,$3,$4,'k1',1,'world',now())",
        ids["msg2"], ids["conv2"], ids["couple2"], ids["c"],
    )
    await conn.execute(
        "INSERT INTO chat_read_states "
        "(id,conversation_id,couple_id,user_id,last_read_sequence,updated_at) "
        "VALUES ($1,$2,$3,$4,1,now())",
        uuid.uuid4(), ids["conv1"], ids["couple1"], ids["a"],
    )
    await conn.execute(
        "INSERT INTO chat_outbox (id,event_type,schema_version,conversation_id,couple_id,"
        " payload,created_at) VALUES ($1,'MESSAGE_CREATED',1,$2,$3,'{}'::jsonb,now())",
        uuid.uuid4(), ids["conv1"], ids["couple1"],
    )
    await conn.execute("RESET ROLE")
    return ids


async def _as(conn, user_id, coro, *, role="dilchat_app", actor="user"):
    async with conn.transaction():
        await conn.execute(f"SET LOCAL ROLE {role}")
        await conn.execute("SELECT set_config('app.current_user_id',$1,true)", str(user_id or ""))
        await conn.execute("SELECT set_config('app.current_actor_type',$1,true)", actor)
        return await coro(conn)


async def test_member_sees_only_own_conversation_rows():
    conn = await _connect()
    try:
        ids = await _seed(conn)

        async def count_msgs(c):
            return await c.fetchval("SELECT count(*) FROM chat_messages")

        async def count_convs(c):
            return await c.fetchval("SELECT count(*) FROM chat_conversations")

        assert await _as(conn, ids["a"], count_msgs) == 1        # only couple1
        assert await _as(conn, ids["c"], count_msgs) == 1        # only couple2
        assert await _as(conn, ids["stranger"], count_msgs) == 0
        assert await _as(conn, ids["a"], count_convs) == 1
        assert await _as(conn, ids["stranger"], count_convs) == 0
    finally:
        await conn.close()


async def test_former_member_loses_visibility_after_revoke():
    conn = await _connect()
    try:
        ids = await _seed(conn)
        await conn.execute("SET ROLE postgres")
        await conn.execute(
            "UPDATE couple_memberships SET status='REVOKED' WHERE couple_id=$1", ids["couple1"]
        )
        await conn.execute("RESET ROLE")

        async def count_msgs(c):
            return await c.fetchval("SELECT count(*) FROM chat_messages")

        assert await _as(conn, ids["a"], count_msgs) == 0
    finally:
        await conn.close()


async def test_message_insert_sender_must_be_current_user():
    conn = await _connect()
    try:
        ids = await _seed(conn)

        async def insert_as_self(c):
            await c.execute(
                "INSERT INTO chat_messages "
                "(id,conversation_id,couple_id,sender_user_id,client_message_id,"
                " server_sequence,body,created_at) VALUES ($1,$2,$3,$4,'kk',9,'x',now())",
                uuid.uuid4(), ids["conv1"], ids["couple1"], ids["a"],
            )

        async def insert_as_partner(c):
            await c.execute(
                "INSERT INTO chat_messages "
                "(id,conversation_id,couple_id,sender_user_id,client_message_id,"
                " server_sequence,body,created_at) VALUES ($1,$2,$3,$4,'kk',10,'x',now())",
                uuid.uuid4(), ids["conv1"], ids["couple1"], ids["b"],
            )

        await _as(conn, ids["a"], insert_as_self)  # allowed
        with pytest.raises(asyncpg.PostgresError):  # WITH CHECK: sender must be self
            await _as(conn, ids["a"], insert_as_partner)
    finally:
        await conn.close()


async def test_no_hard_delete_privilege_on_messages():
    conn = await _connect()
    try:
        ids = await _seed(conn)

        async def hard_delete(c):
            await c.execute("DELETE FROM chat_messages")

        with pytest.raises(asyncpg.PostgresError):  # no DELETE grant (tombstone only)
            await _as(conn, ids["a"], hard_delete)
    finally:
        await conn.close()


async def test_outbox_hidden_from_app_and_readonly_visible_to_worker():
    conn = await _connect()
    try:
        ids = await _seed(conn)

        async def read_outbox(c):
            return await c.fetchval("SELECT count(*) FROM chat_outbox")

        # App actor: no SELECT privilege on the outbox at all -> permission denied.
        with pytest.raises(asyncpg.PostgresError):
            await _as(conn, ids["a"], read_outbox)
        # Read-only reporting role: also denied.
        with pytest.raises(asyncpg.PostgresError):
            await _as(conn, ids["a"], read_outbox, role="dilchat_readonly")
        # Worker role: may read the outbox (delivery relay).
        assert await _as(conn, ids["a"], read_outbox, role="dilchat_worker", actor="worker") >= 1
    finally:
        await conn.close()


async def test_app_may_insert_outbox_in_transaction():
    conn = await _connect()
    try:
        ids = await _seed(conn)

        async def insert_event(c):
            await c.execute(
                "INSERT INTO chat_outbox (id,event_type,schema_version,conversation_id,"
                " couple_id,payload,created_at) "
                "VALUES ($1,'MESSAGE_CREATED',1,$2,$3,'{}'::jsonb,now())",
                uuid.uuid4(), ids["conv1"], ids["couple1"],
            )

        await _as(conn, ids["a"], insert_event)  # app INSERT allowed (same-tx writes)
    finally:
        await conn.close()


async def test_outbox_app_role_cannot_update_or_delete_worker_may_update():
    """The application role can never mutate ``chat_outbox``; only the worker may UPDATE.

    The audit flagged that only outbox SELECT/INSERT were asserted. This proves the
    full least-privilege posture directly under the real non-owner runtime role:
    the app role cannot SELECT / UPDATE / DELETE the outbox nor weaken its RLS, yet
    can still INSERT an allow-listed event in its own transaction, while the worker
    relay retains its documented read + mark-published (UPDATE) capability. The test
    fails if ``UPDATE chat_outbox`` ever succeeds under the application role.
    """
    conn = await _connect()
    try:
        ids = await _seed(conn)  # seeds one MESSAGE_CREATED outbox row (conv1)

        # The runtime role must be a genuine non-owner, else the denials are vacuous.
        async def role_props(c):
            return await c.fetchrow(
                "SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user"
            )

        props = await _as(conn, ids["a"], role_props)
        assert props["rolsuper"] is False
        assert props["rolbypassrls"] is False

        async def app_select(c):
            return await c.fetchval("SELECT count(*) FROM chat_outbox")

        async def app_update(c):
            await c.execute("UPDATE chat_outbox SET published_at = now()")

        async def app_delete(c):
            await c.execute("DELETE FROM chat_outbox")

        # App actor: no read, no update, no delete on the outbox.
        with pytest.raises(asyncpg.PostgresError):
            await _as(conn, ids["a"], app_select)
        with pytest.raises(asyncpg.PostgresError):
            await _as(conn, ids["a"], app_update)
        with pytest.raises(asyncpg.PostgresError):
            await _as(conn, ids["a"], app_delete)

        # App actor cannot weaken the outbox RLS protections either.
        async def app_disable_rls(c):
            await c.execute("ALTER TABLE chat_outbox DISABLE ROW LEVEL SECURITY")

        async def app_drop_policy(c):
            await c.execute("DROP POLICY chat_outbox_worker_write ON chat_outbox")

        with pytest.raises(asyncpg.PostgresError):
            await _as(conn, ids["a"], app_disable_rls)
        with pytest.raises(asyncpg.PostgresError):
            await _as(conn, ids["a"], app_drop_policy)

        # App actor CAN still insert an allow-listed event in its own transaction.
        async def app_insert(c):
            await c.execute(
                "INSERT INTO chat_outbox (id,event_type,schema_version,conversation_id,"
                " couple_id,payload,created_at) "
                "VALUES ($1,'MESSAGE_CREATED',1,$2,$3,'{}'::jsonb,now())",
                uuid.uuid4(), ids["conv1"], ids["couple1"],
            )

        await _as(conn, ids["a"], app_insert)

        # Worker relay: retains read + mark-published (UPDATE) on the outbox.
        async def worker_update(c):
            return await c.execute("UPDATE chat_outbox SET published_at = now()")

        status = await _as(
            conn, ids["a"], worker_update, role="dilchat_worker", actor="worker"
        )
        assert status.startswith("UPDATE ")
        assert int(status.split()[1]) >= 1  # at least the seeded row was marked published
    finally:
        await conn.close()


async def test_runtime_role_cannot_disable_rls_or_drop_chat_policy():
    conn = await _connect()
    try:
        await _seed(conn)

        async def disable(c):
            await c.execute("ALTER TABLE chat_messages DISABLE ROW LEVEL SECURITY")

        async def drop_policy(c):
            await c.execute("DROP POLICY chat_msg_member ON chat_messages")

        with pytest.raises(asyncpg.PostgresError):
            await _as(conn, uuid.uuid4(), disable)
        with pytest.raises(asyncpg.PostgresError):
            await _as(conn, uuid.uuid4(), drop_policy)
    finally:
        await conn.close()
