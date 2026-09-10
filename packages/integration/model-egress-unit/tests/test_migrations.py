"""Migrations: deterministic, ordered, all-or-nothing, and drift-refusing."""

from __future__ import annotations

import uuid

import psycopg
import pytest

from ugence_model_egress_unit.postgres import (
    MIGRATIONS,
    SCHEMA_NAME,
    Migration,
    MigrationDrift,
    applied_versions,
    migrate,
    migration_digest,
    statements,
)

pytestmark = pytest.mark.postgres


@pytest.fixture
def blank(admin_dsn):
    """A database with no migrations applied. ``database`` is already migrated."""

    name = f"meu_blank_{uuid.uuid4().hex[:16]}"
    with psycopg.connect(admin_dsn, autocommit=True) as conn:
        conn.execute(f'CREATE DATABASE "{name}"')
    head, _, _tail = admin_dsn.rpartition("/")
    try:
        yield f"{head}/{name}"
    finally:
        with psycopg.connect(admin_dsn, autocommit=True) as conn:
            conn.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')


# --- the digest identity -----------------------------------------------------

def test_a_migration_is_identified_by_the_digest_of_its_own_text():
    for migration in MIGRATIONS:
        assert migration.digest == migration_digest(migration.sql)
        assert len(migration.digest) == 64


def test_whitespace_counts_as_a_change():
    """Reformatting *is* a change for the purpose of "did this file change since
    we ran it", so the digest is over the text verbatim."""

    assert migration_digest("SELECT 1") != migration_digest("SELECT  1")


def test_versions_are_unique_and_ordered():
    versions = [m.version for m in MIGRATIONS]
    assert versions == sorted(versions) == sorted(set(versions))


# --- applying ----------------------------------------------------------------

def test_migrating_a_blank_database_applies_everything_once(blank):
    with psycopg.connect(blank, autocommit=True) as conn:
        applied = migrate(conn)
        assert [m.version for m in applied] == [m.version for m in MIGRATIONS]
        assert applied_versions(conn) == {m.version: m.digest for m in MIGRATIONS}


def test_migrating_twice_is_a_no_op(blank):
    with psycopg.connect(blank, autocommit=True) as conn:
        migrate(conn)
        assert migrate(conn) == [], "the second run has nothing pending"


def test_the_schema_the_migration_claims_to_build_is_the_one_it_builds(blank):
    with psycopg.connect(blank, autocommit=True) as conn:
        migrate(conn)
        tables = {r[0] for r in conn.execute(
            "SELECT tablename FROM pg_tables WHERE schemaname = %s",
            (SCHEMA_NAME,)).fetchall()}
        assert tables == {"egress_request", "egress_result"}

        forced = dict(conn.execute(
            "SELECT relname, relforcerowsecurity FROM pg_class "
            "WHERE relnamespace = (SELECT oid FROM pg_namespace WHERE nspname = %s) "
            "AND relkind = 'r'", (SCHEMA_NAME,)).fetchall())
        assert forced == {"egress_request": True, "egress_result": True}


# --- drift -------------------------------------------------------------------

def test_an_edited_applied_migration_is_refused(blank):
    """The property Alembic's revision chain does not give.

    An applied migration whose text has changed means the live schema and this
    source have diverged. Stacking a new step on top would bury that; refusing
    surfaces it, naming the migration.
    """

    with psycopg.connect(blank, autocommit=True) as conn:
        migrate(conn)
        edited = (Migration(version=MIGRATIONS[0].version,
                            name=MIGRATIONS[0].name,
                            sql=MIGRATIONS[0].sql + "\n-- an innocent-looking edit\n"),)
        with pytest.raises(MigrationDrift, match="was applied as"):
            migrate(conn, edited)


def test_a_migration_the_distribution_does_not_know_is_refused(blank):
    """A database migrated by a newer version of this package. Downgrading a
    schema is not something this runner will guess at."""

    with psycopg.connect(blank, autocommit=True) as conn:
        migrate(conn)
        conn.execute(
            "INSERT INTO public.meu_schema_version (version, name, digest) "
            "VALUES (99, 'from_the_future', %s)", ("f" * 64,))
        with pytest.raises(MigrationDrift, match="not in this distribution"):
            migrate(conn)


def test_nothing_is_applied_when_drift_is_detected(blank):
    """Drift stops the run before any pending step lands, so a divergent schema
    never gains a half-built extension on top of it."""

    with psycopg.connect(blank, autocommit=True) as conn:
        migrate(conn)
        edited = MIGRATIONS[0].sql + "\n-- edit\n"
        plan = (
            Migration(version=1, name=MIGRATIONS[0].name, sql=edited),
            Migration(version=2, name="would_add_a_table",
                      sql=f"CREATE TABLE {SCHEMA_NAME}.should_not_exist (x int);"),
        )
        with pytest.raises(MigrationDrift):
            migrate(conn, plan)

        assert conn.execute(
            "SELECT to_regclass(%s)", (f"{SCHEMA_NAME}.should_not_exist",)
        ).fetchone()[0] is None


def test_a_failing_migration_leaves_no_partial_schema(blank):
    """Transactional DDL, relied on deliberately: a crash halfway leaves the
    database on the last fully applied version, not in a state no migration
    describes."""

    with psycopg.connect(blank, autocommit=True) as conn:
        broken = (
            Migration(version=1, name="half_good",
                      sql="CREATE TABLE public.first_half (x int);\n"
                          "CREATE TABLE public.first_half (x int);\n"),
        )
        with pytest.raises(psycopg.errors.DuplicateTable):
            migrate(conn, broken)

        assert conn.execute(
            "SELECT to_regclass('public.first_half')").fetchone()[0] is None
        assert applied_versions(conn) == {}


# --- the splitter ------------------------------------------------------------

def test_a_semicolon_inside_a_comment_does_not_split_a_statement():
    parts = statements("SELECT 1  -- not; a terminator\n, 2;")
    assert len(parts) == 1, parts


def test_a_dollar_quoted_body_is_kept_whole():
    parts = statements("DO $$ BEGIN PERFORM 1; PERFORM 2; END $$;\nSELECT 3;")
    assert len(parts) == 2, parts
    assert "PERFORM 1" in parts[0] and "PERFORM 2" in parts[0]
