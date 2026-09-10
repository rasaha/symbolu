"""A real PostgreSQL database per test, and role-scoped connections into it.

**These tests do not skip when PostgreSQL is absent — they fail.** Row-level
security, forced or otherwise, cannot be exercised against a stand-in: SQLite has
no policies, no roles and no ``current_setting``, so a suite that silently fell
back to one would report green for the property it exists to prove. A skipped row
is not a passing row, and for a security boundary a skipped row is worse than a
red one because it looks like a pass.

The server is named by ``UGENCE_MEU_TEST_PG``. CI stands one up with ``pg_ctl``
on port 5433; locally any cluster will do.
"""

from __future__ import annotations

import os
import uuid

import psycopg
import pytest

from ugence_model_egress_unit.postgres import (
    UNIT_ROLE,
    WORKER_ROLE,
    Exchange,
    migrate,
)

_ENV = "UGENCE_MEU_TEST_PG"


def _admin_dsn() -> str:
    dsn = os.environ.get(_ENV)
    if not dsn:
        pytest.fail(
            f"{_ENV} is not set. This suite proves properties of PostgreSQL "
            f"row-level security and cannot be run against anything else; it "
            f"fails rather than skips so an absent server never reads as a pass. "
            f"Set it to a superuser DSN, e.g. "
            f"postgresql://postgres@127.0.0.1:5433/postgres"
        )
    return dsn


@pytest.fixture(scope="session")
def admin_dsn() -> str:
    return _admin_dsn()


@pytest.fixture
def database(admin_dsn):
    """A fresh database, migrated, dropped afterwards.

    Per-test rather than per-session because the migration ledger and the role
    grants are themselves under test, and a shared database would let one test's
    schema state decide another's result.
    """

    name = f"meu_test_{uuid.uuid4().hex[:16]}"
    with psycopg.connect(admin_dsn, autocommit=True) as conn:
        conn.execute(f'CREATE DATABASE "{name}"')

    target = _swap_dbname(admin_dsn, name)
    try:
        with psycopg.connect(target, autocommit=True) as conn:
            migrate(conn)
            # The two application roles need to reach the database at all before
            # their table grants mean anything.
            for role in (WORKER_ROLE, UNIT_ROLE):
                conn.execute(f'GRANT CONNECT ON DATABASE "{name}" TO {role}')
        yield target
    finally:
        with psycopg.connect(admin_dsn, autocommit=True) as conn:
            conn.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname = %s AND pid <> pg_backend_pid()",
                (name,),
            )
            conn.execute(f'DROP DATABASE IF EXISTS "{name}"')


def _swap_dbname(dsn: str, name: str) -> str:
    head, _, _tail = dsn.rpartition("/")
    return f"{head}/{name}"


def _role_connect(dsn: str, role: str):
    """A connection that has dropped to ``role`` before any statement runs.

    ``SET ROLE`` rather than a second login: the test cluster authenticates with
    ``trust`` and the point under test is the *privilege* boundary, not the
    authentication one. A superuser would bypass row-level security entirely, so
    dropping the role is what makes the assertions mean anything.
    """

    def connect():
        # autocommit for the SET ROLE, then off again — otherwise the statement
        # opens an implicit transaction and the connection reaches the exchange
        # already INTRANS, which it refuses (and rightly: SET LOCAL would then be
        # savepoint-scoped and would leak). See UnscopableConnection.
        conn = psycopg.connect(dsn, autocommit=True)
        conn.execute(f"SET ROLE {role}")
        conn.autocommit = False
        return conn

    return connect


@pytest.fixture
def worker_exchange(database) -> Exchange:
    return Exchange(_role_connect(database, WORKER_ROLE))


@pytest.fixture
def unit_exchange(database) -> Exchange:
    return Exchange(_role_connect(database, UNIT_ROLE))


@pytest.fixture
def admin_connect(database):
    """Superuser access, for arranging state the application roles may not."""

    def connect():
        return psycopg.connect(database)

    return connect


@pytest.fixture
def tenant() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def other_tenant() -> uuid.UUID:
    return uuid.uuid4()
