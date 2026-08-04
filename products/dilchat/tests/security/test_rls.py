"""PostgreSQL RLS tests exercised through a real NON-OWNER runtime role (Area D).

These connect to PostgreSQL, seed data as the superuser/owner (which bypasses RLS),
then run every assertion under ``SET LOCAL ROLE dilchat_app`` (a NOBYPASSRLS,
non-owner role) with a transaction-local ``app.current_user_id`` context. Owner
bypass is deliberately avoided so the policies themselves are what is tested.
Application-level 404 tests remain separate and do not substitute for these.
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
    # postgresql+asyncpg://postgres@/dilchat_test?host=/tmp&port=5433
    from urllib.parse import parse_qs, urlparse

    u = urlparse(_DB_URL.replace("+asyncpg", ""))
    q = parse_qs(u.query)
    return {
        "user": u.username or "postgres",
        "database": u.path.lstrip("/"),
        "host": q.get("host", ["/tmp"])[0],
        "port": int(q.get("port", ["5432"])[0]),
    }


async def _connect():
    return await asyncpg.connect(**_dsn())


async def _seed(conn):
    # Superuser seeding (bypasses RLS). Fresh couple + members + artifacts.
    ids = {k: uuid.uuid4() for k in ("a", "b", "stranger", "couple", "ma", "mb",
                                     "consent", "artifact", "inv")}
    await conn.execute("SET ROLE postgres")
    for who in ("a", "b", "stranger"):
        await conn.execute(
            "INSERT INTO users (id,email,credential_hash,status,created_at,updated_at) "
            "VALUES ($1,$2,'h','ACTIVE',now(),now())",
            ids[who], f"{who}_{ids[who].hex[:8]}@e.com",
        )
    await conn.execute(
        "INSERT INTO couples (id,status,created_at,updated_at) VALUES ($1,'ACTIVE',now(),now())",
        ids["couple"],
    )
    await conn.execute(
        "INSERT INTO couple_memberships (id,couple_id,user_id,scope_slot,status,joined_at) "
        "VALUES ($1,$2,$3,'A','ACTIVE',now())", ids["ma"], ids["couple"], ids["a"],
    )
    await conn.execute(
        "INSERT INTO couple_memberships (id,couple_id,user_id,scope_slot,status,joined_at) "
        "VALUES ($1,$2,$3,'B','ACTIVE',now())", ids["mb"], ids["couple"], ids["b"],
    )
    for who in ("a", "b"):
        await conn.execute(
            "INSERT INTO birth_profiles "
            "(id,user_id,version,preferred_name,birth_date,birth_time_precision,"
            " birthplace_label,latitude,longitude,iana_timezone,input_confidence,"
            " created_at,updated_at) "
            "VALUES ($1,$2,1,'N','1990-01-01','UNKNOWN','X',0,0,'UTC',0.2,now(),now())",
            uuid.uuid4(), ids[who],
        )
    await conn.execute(
        "INSERT INTO consent_events "
        "(id,couple_id,granter_user_id,event_type,state,source_scope,artifact_type,"
        " bounded_summary,created_at) "
        "VALUES ($1,$2,$3,'GRANT','GRANTED','PRIVATE_A','bounded_summary','s',now())",
        ids["consent"], ids["couple"], ids["a"],
    )
    await conn.execute(
        "INSERT INTO shared_artifacts "
        "(id,couple_id,consent_event_id,source_scope,artifact_type,payload_snapshot,"
        " provenance,created_at) "
        "VALUES ($1,$2,$3,'PRIVATE_A','bounded_summary','x','{}'::jsonb,now())",
        ids["artifact"], ids["couple"], ids["consent"],
    )
    await conn.execute(
        "INSERT INTO couple_invitations "
        "(id,inviter_user_id,token_hash,status,expires_at,created_at,updated_at) "
        "VALUES ($1,$2,$3,'PENDING',now()+interval '1 day',now(),now())",
        ids["inv"], ids["a"], "tokenhash_" + ids["inv"].hex,
    )
    await conn.execute("RESET ROLE")
    return ids


async def _as_app(conn, user_id, coro, *, role="dilchat_app", actor="user"):
    """Run ``coro(conn)`` inside a tx as the non-owner role with RLS context."""
    async with conn.transaction():
        await conn.execute(f"SET LOCAL ROLE {role}")
        await conn.execute("SELECT set_config('app.current_user_id',$1,true)", str(user_id or ""))
        await conn.execute("SELECT set_config('app.current_actor_type',$1,true)", actor)
        return await coro(conn)


async def test_owner_private_access_succeeds_cross_private_denied():
    conn = await _connect()
    try:
        ids = await _seed(conn)

        async def a_sees_own(c):
            return await c.fetchval(
                "SELECT count(*) FROM birth_profiles WHERE user_id=$1", ids["a"]
            )

        async def a_sees_b(c):
            return await c.fetchval(
                "SELECT count(*) FROM birth_profiles WHERE user_id=$1", ids["b"]
            )

        assert await _as_app(conn, ids["a"], a_sees_own) == 1
        # Cross-private: RLS returns zero rows (existence not exposed at the DB layer).
        assert await _as_app(conn, ids["a"], a_sees_b) == 0
    finally:
        await conn.close()


async def test_shared_artifact_member_vs_stranger_and_after_unpair():
    conn = await _connect()
    try:
        ids = await _seed(conn)

        async def count_art(c):
            return await c.fetchval("SELECT count(*) FROM shared_artifacts")

        assert await _as_app(conn, ids["a"], count_art) == 1        # active member
        assert await _as_app(conn, ids["b"], count_art) == 1        # active member
        assert await _as_app(conn, ids["stranger"], count_art) == 0  # stranger: hidden

        # Unpair (revoke memberships) as owner; former members lose access at once.
        await conn.execute("SET ROLE postgres")
        await conn.execute(
            "UPDATE couple_memberships SET status='REVOKED' WHERE couple_id=$1", ids["couple"]
        )
        await conn.execute("RESET ROLE")
        assert await _as_app(conn, ids["a"], count_art) == 0
    finally:
        await conn.close()


async def test_invitation_cannot_be_enumerated_but_token_lookup_works():
    conn = await _connect()
    try:
        ids = await _seed(conn)

        async def stranger_enum(c):
            return await c.fetchval("SELECT count(*) FROM couple_invitations")

        async def inviter_sees(c):
            return await c.fetchval("SELECT count(*) FROM couple_invitations")

        assert await _as_app(conn, ids["stranger"], stranger_enum) == 0  # cannot enumerate
        assert await _as_app(conn, ids["a"], inviter_sees) == 1          # inviter sees own

        async def accepter_token_lookup(c):
            return await c.fetchval(
                "SELECT app_find_invitation($1)", "tokenhash_" + ids["inv"].hex
            )

        # The accepter (not the inviter) resolves the invitation by token (definer fn).
        found = await _as_app(conn, ids["b"], accepter_token_lookup)
        assert found == ids["inv"]
    finally:
        await conn.close()


async def test_stale_worker_cannot_write_after_revocation():
    conn = await _connect()
    try:
        ids = await _seed(conn)
        # Revoke B's membership.
        await conn.execute("SET ROLE postgres")
        await conn.execute(
            "UPDATE couple_memberships SET status='REVOKED' WHERE user_id=$1", ids["b"]
        )
        await conn.execute("RESET ROLE")

        async def worker_insert(c):
            await c.execute(
                "INSERT INTO shared_artifacts "
                "(id,couple_id,consent_event_id,source_scope,artifact_type,payload_snapshot,"
                " provenance,created_at) VALUES ($1,$2,$3,'PRIVATE_B','bounded_summary','y',"
                " '{}'::jsonb,now())",
                uuid.uuid4(), ids["couple"], ids["consent"],
            )

        with pytest.raises(asyncpg.PostgresError):  # RLS WITH CHECK violation
            await _as_app(conn, ids["b"], worker_insert, role="dilchat_worker", actor="worker")
    finally:
        await conn.close()


async def test_runtime_role_cannot_disable_rls_or_alter_policy():
    conn = await _connect()
    try:
        await _seed(conn)

        async def disable_rls(c):
            await c.execute("ALTER TABLE users DISABLE ROW LEVEL SECURITY")

        async def drop_policy(c):
            await c.execute("DROP POLICY bp_owner ON birth_profiles")

        with pytest.raises(asyncpg.PostgresError):
            await _as_app(conn, uuid.uuid4(), disable_rls)
        with pytest.raises(asyncpg.PostgresError):
            await _as_app(conn, uuid.uuid4(), drop_policy)
    finally:
        await conn.close()


async def test_runtime_role_cannot_modify_immutable_or_audit():
    conn = await _connect()
    try:
        ids = await _seed(conn)

        async def update_artifact(c):
            await c.execute("UPDATE shared_artifacts SET payload_snapshot='z'")

        async def delete_audit(c):
            await c.execute("DELETE FROM audit_events")

        # No UPDATE/DELETE privilege was granted on these tables -> permission denied.
        with pytest.raises(asyncpg.PostgresError):
            await _as_app(conn, ids["a"], update_artifact)
        with pytest.raises(asyncpg.PostgresError):
            await _as_app(conn, ids["a"], delete_audit)
    finally:
        await conn.close()


async def test_transaction_local_context_does_not_leak_across_pool():
    conn = await _connect()
    try:
        await _seed(conn)
        uid = uuid.uuid4()
        async with conn.transaction():
            await conn.execute("SELECT set_config('app.current_user_id',$1,true)", str(uid))
            v = await conn.fetchval("SELECT current_setting('app.current_user_id', true)")
            assert v == str(uid)
        # After the transaction the local setting is gone on the same connection.
        leaked = await conn.fetchval("SELECT current_setting('app.current_user_id', true)")
        assert leaked in ("", None)
    finally:
        await conn.close()
