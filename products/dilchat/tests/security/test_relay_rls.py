"""PostgreSQL RLS for the Phase 3C relay surface, via real NON-OWNER roles.

Proves invariants I6 and I8 at the database layer: only the worker posture can
claim/publish/prune outbox work, the DELETE policy admits PUBLISHED rows only,
device tokens are readable across users ONLY by the worker (delivery), and the
bounded ``app_release_push_token`` definer lets a new owner displace a hidden
previous registration without widening the app role's visibility.
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
        "a", "b", "couple1", "conv1", "out_unpub", "out_pub", "dev_a", "dev_b",
    )}
    await conn.execute("SET ROLE postgres")
    for who in ("a", "b"):
        await conn.execute(
            "INSERT INTO users (id,email,credential_hash,status,created_at,updated_at) "
            "VALUES ($1,$2,'h','ACTIVE',now(),now())",
            ids[who], f"{who}_{ids[who].hex[:8]}@e.com",
        )
    await conn.execute(
        "INSERT INTO couples (id,status,created_at,updated_at) VALUES ($1,'ACTIVE',now(),now())",
        ids["couple1"],
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
        "VALUES ($1,$2,'ACTIVE',1,1,now(),now())", ids["conv1"], ids["couple1"],
    )
    await conn.execute(
        "INSERT INTO chat_outbox (id,event_type,schema_version,conversation_id,couple_id,"
        " payload,created_at,attempt_count) "
        "VALUES ($1,'MESSAGE_CREATED',1,$2,$3,'{}'::jsonb,now(),0)",
        ids["out_unpub"], ids["conv1"], ids["couple1"],
    )
    await conn.execute(
        "INSERT INTO chat_outbox (id,event_type,schema_version,conversation_id,couple_id,"
        " payload,created_at,attempt_count,published_at) "
        "VALUES ($1,'MESSAGE_CREATED',1,$2,$3,'{}'::jsonb,now(),0,now())",
        ids["out_pub"], ids["conv1"], ids["couple1"],
    )
    for key, owner in (("dev_a", "a"), ("dev_b", "b")):
        await conn.execute(
            "INSERT INTO chat_devices (id,user_id,platform,status,push_token,"
            " created_at,updated_at) VALUES ($1,$2,'IOS','ACTIVE',$3,now(),now())",
            ids[key], ids[owner], f"tok-{key}-{ids[key].hex[:8]}",
        )
    await conn.execute("RESET ROLE")
    return ids


async def _as(conn, user_id, coro, *, role="dilchat_app", actor="user"):
    async with conn.transaction():
        await conn.execute(f"SET LOCAL ROLE {role}")
        await conn.execute("SELECT set_config('app.current_user_id',$1,true)", str(user_id or ""))
        await conn.execute("SELECT set_config('app.current_actor_type',$1,true)", actor)
        return await coro(conn)


async def test_only_worker_can_prune_and_only_published_rows():
    conn = await _connect()
    try:
        ids = await _seed(conn)

        async def app_delete(c):
            await c.execute("DELETE FROM chat_outbox WHERE id = $1", ids["out_pub"])

        # The app role holds no DELETE grant at all.
        with pytest.raises(asyncpg.PostgresError):
            await _as(conn, ids["a"], app_delete)

        async def worker_delete_unpublished(c):
            return await c.execute(
                "DELETE FROM chat_outbox WHERE id = $1", ids["out_unpub"]
            )

        async def worker_delete_published(c):
            return await c.execute("DELETE FROM chat_outbox WHERE id = $1", ids["out_pub"])

        # I8, DB-enforced: the worker's DELETE policy admits published rows only.
        status = await _as(
            conn, None, worker_delete_unpublished, role="dilchat_worker", actor="worker"
        )
        assert status == "DELETE 0"
        status = await _as(
            conn, None, worker_delete_published, role="dilchat_worker", actor="worker"
        )
        assert status == "DELETE 1"
    finally:
        await conn.close()


async def test_worker_claims_and_publishes_outbox_work():
    conn = await _connect()
    try:
        ids = await _seed(conn)

        async def worker_claim_and_publish(c):
            # Scoped to this seed's row (the shared DB accumulates across tests).
            row = await c.fetchrow(
                "SELECT id FROM chat_outbox WHERE published_at IS NULL AND id = $1 "
                "FOR UPDATE SKIP LOCKED LIMIT 1", ids["out_unpub"]
            )
            await c.execute(
                "UPDATE chat_outbox SET published_at = now() WHERE id = $1", row["id"]
            )
            return row["id"]

        claimed = await _as(
            conn, None, worker_claim_and_publish, role="dilchat_worker", actor="worker"
        )
        assert claimed == ids["out_unpub"]

        async def app_update(c):
            await c.execute(
                "UPDATE chat_outbox SET published_at = now() WHERE id = $1", ids["out_pub"]
            )

        # The app posture can never publish (no UPDATE visibility/grant path).
        with pytest.raises(asyncpg.PostgresError):
            await _as(conn, ids["a"], app_update)
    finally:
        await conn.close()


async def test_device_tokens_worker_read_and_owner_only_app_visibility():
    conn = await _connect()
    try:
        ids = await _seed(conn)

        async def count_devices(c):
            # Scoped to this seed's rows (the shared DB accumulates across tests).
            return await c.fetchval(
                "SELECT count(*) FROM chat_devices WHERE id = ANY($1::uuid[])",
                [ids["dev_a"], ids["dev_b"]],
            )

        # App role: strictly own rows.
        assert await _as(conn, ids["a"], count_devices) == 1
        assert await _as(conn, ids["b"], count_devices) == 1
        # Worker: reads across users (delivery needs the recipient's tokens).
        assert (
            await _as(conn, ids["a"], count_devices, role="dilchat_worker", actor="worker")
        ) == 2
        # Read-only and safety roles hold no grant on tokens at all.
        for role in ("dilchat_readonly", "dilchat_safety"):
            with pytest.raises(asyncpg.PostgresError):
                await _as(conn, ids["a"], count_devices, role=role, actor="user")
    finally:
        await conn.close()


async def test_release_token_definer_displaces_hidden_registration():
    conn = await _connect()
    try:
        ids = await _seed(conn)
        # Give B's device the token A's future registration wants to claim.
        await conn.execute("SET ROLE postgres")
        await conn.execute(
            "UPDATE chat_devices SET push_token = 'shared-token' WHERE id = $1", ids["dev_b"]
        )
        await conn.execute("RESET ROLE")

        async def a_sees_bs_row(c):
            return await c.fetchval(
                "SELECT count(*) FROM chat_devices WHERE push_token = 'shared-token'"
            )

        async def a_releases(c):
            return await c.fetchval("SELECT app_release_push_token('shared-token')")

        # A cannot SEE B's registration under owner-only RLS...
        assert await _as(conn, ids["a"], a_sees_bs_row) == 0
        # ...but the bounded definer still displaces it (returns only a count).
        assert await _as(conn, ids["a"], a_releases) == 1
        await conn.execute("SET ROLE postgres")
        status = await conn.fetchval(
            "SELECT status FROM chat_devices WHERE id = $1", ids["dev_b"]
        )
        await conn.execute("RESET ROLE")
        assert status == "REVOKED"
    finally:
        await conn.close()
