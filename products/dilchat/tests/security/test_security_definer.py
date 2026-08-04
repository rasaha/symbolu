"""SECURITY DEFINER / helper privilege tests via a real non-owner role (Workstream C).

Confirms that a runtime role cannot tamper with the RLS helper functions and that
the helpers are configured with least privilege and a fixed search_path.
"""

from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.postgres

_DB_URL = os.environ.get("DILCHAT_TEST_DATABASE_URL")
asyncpg = pytest.importorskip("asyncpg")
if not _DB_URL or "postgresql" not in _DB_URL:
    pytest.skip("DILCHAT_TEST_DATABASE_URL (PostgreSQL) not set", allow_module_level=True)


def _dsn() -> dict:
    # Accepts socket-style (…?host=/tmp&port=5433) and TCP netloc
    # (…:pw@host:port/db) URLs; query wins, netloc is the fallback (CI service).
    from urllib.parse import parse_qs, urlparse

    u = urlparse(_DB_URL.replace("+asyncpg", ""))
    q = parse_qs(u.query)
    dsn = {"user": u.username or "postgres", "database": u.path.lstrip("/"),
           "host": q.get("host", [u.hostname or "/tmp"])[0],
           "port": int(q.get("port", [str(u.port or 5432)])[0])}
    if u.password:
        dsn["password"] = u.password
    return dsn


async def _connect():
    return await asyncpg.connect(**_dsn())


async def _as_app(conn, coro, role="dilchat_app"):
    async with conn.transaction():
        await conn.execute(f"SET LOCAL ROLE {role}")
        return await coro(conn)


# --- configuration / metadata ---------------------------------------------- #
async def test_secdef_helpers_owner_and_config():
    conn = await _connect()
    try:
        rows = await conn.fetch(
            "SELECT p.proname, r.rolname AS owner, p.prosecdef, p.proconfig "
            "FROM pg_proc p JOIN pg_roles r ON r.oid=p.proowner "
            "WHERE p.proname IN ('app_is_active_member','app_find_invitation')"
        )
        for row in rows:
            assert row["owner"] == "dilchat_secfn_owner"   # dedicated non-login owner
            assert row["prosecdef"] is True                 # SECURITY DEFINER
            assert any("search_path=" in c for c in (row["proconfig"] or [])), row["proname"]
        # The dedicated owner is non-login and distinct from runtime roles.
        owner = await conn.fetchrow(
            "SELECT rolcanlogin, rolbypassrls FROM pg_roles WHERE rolname='dilchat_secfn_owner'"
        )
        assert owner["rolcanlogin"] is False
    finally:
        await conn.close()


async def test_public_cannot_execute_restricted_helper():
    conn = await _connect()
    try:
        # A throwaway role with no explicit grant relies on PUBLIC (which was revoked).
        await conn.execute(
            "DO $$ BEGIN IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='dilchat_nogrant') "
            "THEN CREATE ROLE dilchat_nogrant NOLOGIN; END IF; END $$;"
        )

        async def exec_helper(c):
            await c.fetchval("SELECT app_actor_type()")

        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await _as_app(conn, exec_helper, role="dilchat_nogrant")
    finally:
        await conn.close()


# --- runtime role cannot tamper -------------------------------------------- #
async def test_runtime_cannot_replace_helper():
    conn = await _connect()
    try:
        async def replace(c):
            await c.execute(
                "CREATE OR REPLACE FUNCTION app_is_active_member(uuid) RETURNS boolean "
                "LANGUAGE sql AS $$ SELECT true $$"
            )
        with pytest.raises(asyncpg.PostgresError):
            await _as_app(conn, replace)
    finally:
        await conn.close()


async def test_runtime_cannot_alter_config_or_owner():
    conn = await _connect()
    try:
        async def alter_sp(c):
            await c.execute("ALTER FUNCTION app_is_active_member(uuid) SET search_path = public")

        async def alter_owner(c):
            await c.execute("ALTER FUNCTION app_is_active_member(uuid) OWNER TO dilchat_app")

        with pytest.raises(asyncpg.PostgresError):
            await _as_app(conn, alter_sp)
        with pytest.raises(asyncpg.PostgresError):
            await _as_app(conn, alter_owner)
    finally:
        await conn.close()


async def test_runtime_cannot_grant_execute():
    conn = await _connect()
    try:
        await conn.execute(
            "DO $$ BEGIN IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='dilchat_nogrant') "
            "THEN CREATE ROLE dilchat_nogrant NOLOGIN; END IF; END $$;"
        )
        # A runtime role lacks grant option, so this GRANT confers nothing (Postgres
        # emits a warning and grants no privilege — it does not error).
        async def try_grant(c):
            await c.execute(
                "GRANT EXECUTE ON FUNCTION app_find_invitation(text) TO dilchat_nogrant"
            )
        await _as_app(conn, try_grant)

        # Prove the effect: the target still cannot execute the helper.
        async def exec_helper(c):
            await c.fetchval("SELECT app_find_invitation('nope')")
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await _as_app(conn, exec_helper, role="dilchat_nogrant")
    finally:
        await conn.close()


async def test_runtime_cannot_create_shadow_object_in_public():
    conn = await _connect()
    try:
        async def create_tbl(c):
            await c.execute("CREATE TABLE public.couple_memberships_shadow (x int)")
        with pytest.raises(asyncpg.PostgresError):
            await _as_app(conn, create_tbl)
    finally:
        await conn.close()


async def test_runtime_cannot_disable_rls_or_use_bypassrls():
    conn = await _connect()
    try:
        role = await conn.fetchrow("SELECT rolbypassrls FROM pg_roles WHERE rolname='dilchat_app'")
        assert role["rolbypassrls"] is False

        async def disable(c):
            await c.execute("ALTER TABLE couple_memberships DISABLE ROW LEVEL SECURITY")
        with pytest.raises(asyncpg.PostgresError):
            await _as_app(conn, disable)
    finally:
        await conn.close()
