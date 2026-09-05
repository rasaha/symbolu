"""Test harness for the durability and failure matrix.

Every matrix row runs against a **real** PostgreSQL server. There is no mock engine and
no fake database: a mocked crash proves nothing about what Postgres rolled back, which
is the only thing rows 1-3 and 7 are actually about.

Point ``UGENCE_DE_TEST_PG`` at a server (default:
``postgresql://postgres@127.0.0.1:5432/postgres``). Each test module gets freshly
created application and system databases, so no test can see another's rows.
"""
from __future__ import annotations

import os
import uuid

import pytest

sa = pytest.importorskip("sqlalchemy", reason="SQLAlchemy is required for the matrix")

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
    try:
        with _admin_engine().connect() as c:
            c.execute(sa.text("SELECT 1"))
        return True
    except Exception:
        return False


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
