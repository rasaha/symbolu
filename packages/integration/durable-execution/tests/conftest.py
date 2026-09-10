"""Test harness for the durability and failure matrix.

Every matrix row runs against a **real** PostgreSQL server. There is no mock engine and
no fake database: a mocked crash proves nothing about what Postgres rolled back, which
is the only thing rows 1-3 and 7 are actually about.

Point ``UGENCE_DE_TEST_PG`` at a server (default:
``postgresql://postgres@127.0.0.1:5432/postgres``). Each test module gets freshly
created application and system databases, so no test can see another's rows.

SQLAlchemy is imported lazily rather than through a module-level ``importorskip``. A
module-level skip here is collected as a *directory* skip, which took the boundary and
ADR-conformance tests down with the matrix — and those assert the one-way dependency on
Agent Runtime and the pinned ADR section 4 Protocol surface, neither of which needs a
database. A contributor without Postgres now still gets that signal. Nothing about the
matrix is relaxed: a row that cannot reach a real server still skips, and CI still fails
the job if any matrix row skipped.
"""
from __future__ import annotations

import os
import uuid

import pytest

try:  # the matrix needs it; the boundary and ADR-conformance tests do not
    import sqlalchemy as sa
except ImportError:  # pragma: no cover - exercised by running without the extra
    sa = None

ADMIN_URL = os.environ.get(
    "UGENCE_DE_TEST_PG", "postgresql+psycopg://postgres@127.0.0.1:5432/postgres"
)


def _admin_engine():
    # pool_pre_ping, because row 7 really stops the server: a pooled admin connection
    # from before the outage is dead afterwards, and teardown must not fail on it.
    return sa.create_engine(
        ADMIN_URL, isolation_level="AUTOCOMMIT", pool_pre_ping=True
    )


def postgres_available() -> bool:
    if sa is None:
        return False
    try:
        with _admin_engine().connect() as c:
            c.execute(sa.text("SELECT 1"))
        return True
    except Exception:
        return False


requires_engine_deps = pytest.mark.skipif(
    sa is None,
    reason=(
        "SQLAlchemy is not installed, so the concrete DBOS adapter cannot be imported. "
        "Install the package's engine dependencies to exercise it."
    ),
)

requires_postgres = pytest.mark.skipif(
    not postgres_available(),
    reason=(
        "no PostgreSQL at UGENCE_DE_TEST_PG. The matrix is not satisfied by a skipped "
        "run: CI must provide a real server."
    ),
)


def _url_for(dbname: str) -> str:
    return ADMIN_URL.rsplit("/", 1)[0] + "/" + dbname


@pytest.fixture()
def pg_databases():
    """Create a fresh (application, system) database pair; drop them afterwards."""
    if sa is None:
        pytest.skip("SQLAlchemy is not installed; the matrix needs a real server.")
    tag = uuid.uuid4().hex[:10]
    app_db, sys_db = f"ude_app_{tag}", f"ude_sys_{tag}"
    admin = _admin_engine()
    with admin.connect() as c:
        c.execute(sa.text(f'CREATE DATABASE "{app_db}"'))
        c.execute(sa.text(f'CREATE DATABASE "{sys_db}"'))
    try:
        yield _url_for(app_db), _url_for(sys_db)
    finally:
        admin.dispose()
        _drop_databases(app_db, sys_db)


def _drop_databases(*names: str, attempts: int = 5) -> None:
    """Drop the test databases, tolerating a server that was restarted mid-test.

    Row 7 stops and starts the real server, so the first attempt here can meet a
    connection that died with it. Retrying with a fresh engine is the difference between
    a teardown failure that masks a passing row and a clean run.
    """
    import time as _time

    last: Exception | None = None
    for attempt in range(attempts):
        try:
            engine = _admin_engine()
            with engine.connect() as c:
                for db in names:
                    c.execute(
                        sa.text(
                            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                            "WHERE datname = :d AND pid <> pg_backend_pid()"
                        ),
                        {"d": db},
                    )
                    c.execute(sa.text(f'DROP DATABASE IF EXISTS "{db}"'))
            engine.dispose()
            return
        except Exception as exc:  # noqa: BLE001 - retried below
            last = exc
            _time.sleep(1.0 + attempt)
    raise AssertionError(f"could not drop test databases {names}: {last}")
