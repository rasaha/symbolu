"""Reviewer principals are reachable ONLY by the safety posture (round PR-D).

The whole point of DEC-PR-4's identity layer is that it cannot be borrowed: the
application role that serves every user-facing route must not be able to read,
create, or authenticate a reviewer, and the reporting role must not see them at
all. Proven against real PostgreSQL under non-owner runtime roles.
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


async def _seed_reviewer(conn) -> uuid.UUID:
    reviewer_id = uuid.uuid4()
    await conn.execute("SET ROLE postgres")
    await conn.execute(
        "INSERT INTO safety_reviewers "
        "(id,label,credential_hash,role,status,created_at) "
        "VALUES ($1,$2,'$argon2id$fake','READ_ONLY_REVIEWER','ACTIVE',now())",
        reviewer_id,
        f"reviewer-{reviewer_id.hex[:8]}",
    )
    await conn.execute("RESET ROLE")
    return reviewer_id


async def _as(conn, coro, *, role: str, actor: str):
    async with conn.transaction():
        await conn.execute(f"SET LOCAL ROLE {role}")
        await conn.execute("SELECT set_config('app.current_user_id',$1,true)", "")
        await conn.execute("SELECT set_config('app.current_actor_type',$1,true)", actor)
        return await coro(conn)


async def test_app_role_cannot_read_reviewers_at_all():
    """A user-facing request can never authenticate a reviewer."""
    conn = await _connect()
    try:
        await _seed_reviewer(conn)

        async def read(c):
            return await c.fetchval("SELECT count(*) FROM safety_reviewers")

        with pytest.raises(asyncpg.exceptions.InsufficientPrivilegeError):
            await _as(conn, read, role="dilchat_app", actor="user")
    finally:
        await conn.close()


async def test_app_role_cannot_create_a_reviewer():
    conn = await _connect()
    try:

        async def insert(c):
            return await c.execute(
                "INSERT INTO safety_reviewers "
                "(id,label,credential_hash,role,status,created_at) "
                "VALUES ($1,'smuggled','x','READ_ONLY_REVIEWER','ACTIVE',now())",
                uuid.uuid4(),
            )

        with pytest.raises(asyncpg.exceptions.InsufficientPrivilegeError):
            await _as(conn, insert, role="dilchat_app", actor="user")
    finally:
        await conn.close()


async def test_readonly_reporting_role_cannot_see_reviewers():
    conn = await _connect()
    try:
        await _seed_reviewer(conn)

        async def read(c):
            return await c.fetchval("SELECT count(*) FROM safety_reviewers")

        with pytest.raises(asyncpg.exceptions.InsufficientPrivilegeError):
            await _as(conn, read, role="dilchat_readonly", actor="readonly")
    finally:
        await conn.close()


async def test_safety_role_reads_reviewers_only_in_the_safety_actor_context():
    """Holding the role is not enough — the transaction must declare the posture."""
    conn = await _connect()
    try:
        await _seed_reviewer(conn)

        async def read(c):
            return await c.fetchval("SELECT count(*) FROM safety_reviewers")

        assert await _as(conn, read, role="dilchat_safety", actor="safety") >= 1
        # Same role, wrong declared actor type: RLS returns nothing.
        assert await _as(conn, read, role="dilchat_safety", actor="user") == 0
    finally:
        await conn.close()


async def test_app_role_still_cannot_read_case_events_it_writes():
    """The audit trail of reviewer access is not visible to the user-facing role."""
    conn = await _connect()
    try:

        async def read(c):
            return await c.fetchval("SELECT count(*) FROM chat_safety_case_events")

        with pytest.raises(asyncpg.exceptions.InsufficientPrivilegeError):
            await _as(conn, read, role="dilchat_app", actor="user")
    finally:
        await conn.close()
