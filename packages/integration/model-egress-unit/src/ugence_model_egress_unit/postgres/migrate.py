"""Apply the migration list, refusing a schema that has drifted from its text.

Deliberately not called at import. A deployment decides when DDL runs; a library
that migrates on import migrates during ``pytest --collect-only``.
"""

from __future__ import annotations

from typing import Sequence

from .migrations import LEDGER_DDL, MIGRATIONS, Migration, statements

__all__ = ["MigrationDrift", "applied_versions", "migrate"]


class MigrationDrift(RuntimeError):
    """An already-applied migration's text no longer matches its recorded digest.

    The database and the source have diverged, and no further migration can be
    applied safely: the schema is not the one this code was written against, and
    running the remaining steps would build on an unknown foundation.
    """


def applied_versions(conn) -> dict:
    """Version → recorded digest, for every migration the database has applied."""

    with conn.cursor() as cur:
        cur.execute(LEDGER_DDL)
        cur.execute("SELECT version, digest FROM public.meu_schema_version")
        return {row[0]: row[1] for row in cur.fetchall()}


def migrate(conn, migrations: Sequence[Migration] = MIGRATIONS) -> list:
    """Apply every pending migration in one transaction. Returns those applied.

    The whole run commits together or not at all — PostgreSQL's DDL is
    transactional, so a crash halfway leaves the database on the last fully
    applied version rather than in a state no migration describes.

    Before applying anything, every already-applied migration is re-hashed and
    compared with what the ledger recorded. A mismatch raises
    :class:`MigrationDrift` and nothing is applied: an edited migration means the
    schema in front of us is not the one this list describes, and stacking a new
    step on top of it would bury the divergence instead of surfacing it.
    """

    already = applied_versions(conn)
    known = {m.version: m for m in migrations}

    for version, recorded in sorted(already.items()):
        migration = known.get(version)
        if migration is None:
            raise MigrationDrift(
                f"migration {version} is recorded as applied but is not in this "
                f"distribution's list. The database was migrated by a different "
                f"version of this package; downgrading the schema is not something "
                f"this runner will guess at.")
        if migration.digest != recorded:
            raise MigrationDrift(
                f"migration {version} ({migration.name}) was applied as {recorded} "
                f"but its text now hashes to {migration.digest}. An applied "
                f"migration was edited, so the live schema and this source have "
                f"diverged. Add a new migration rather than changing this one.")

    pending = [m for m in migrations if m.version not in already]
    if not pending:
        return []

    with conn.transaction():
        with conn.cursor() as cur:
            for migration in pending:
                for statement in statements(migration.sql):
                    cur.execute(statement)
                cur.execute(
                    "INSERT INTO public.meu_schema_version (version, name, digest) "
                    "VALUES (%s, %s, %s)",
                    (migration.version, migration.name, migration.digest),
                )
    return list(pending)
