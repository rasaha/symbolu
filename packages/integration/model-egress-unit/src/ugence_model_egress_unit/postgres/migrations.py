"""Deterministic migrations: an ordered, digest-pinned list applied in one transaction.

What "deterministic" buys, and why not Alembic
----------------------------------------------
Alembic orders by a ``down_revision`` chain and identifies a migration by a hash
somebody typed. That is fine, and it is not what this exchange needs. Here a
migration is identified by **the digest of its own text**, the list is a Python
tuple in apply order, and :func:`migrate` refuses to proceed if a migration that
was already applied no longer hashes to what was recorded.

That last property is the one worth having. Editing an already-applied migration
is the classic way a schema silently diverges between two deployments: the file
says one thing, the database contains another, and nothing notices until a
constraint that "exists" turns out not to. Pinning the digest turns that from a
latent divergence into a refusal at startup, naming the migration that changed.

Applying is all-or-nothing. PostgreSQL has transactional DDL, so every pending
migration and the ledger rows recording them commit together or not at all. A
crash halfway through leaves the database on the last fully-applied version, not
in a state no migration describes.

The ledger is created outside the exchange schema's ownership dance because it
has to exist before the owner role does.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Sequence

from .schema import OWNER_ROLE, SCHEMA_NAME, TENANT_SETTING, UNIT_ROLE, WORKER_ROLE

__all__ = ["Migration", "MIGRATIONS", "LEDGER_DDL", "migration_digest", "statements"]


@dataclass(frozen=True)
class Migration:
    """One ordered schema step, identified by the digest of its own text."""

    version: int
    name: str
    sql: str

    @property
    def digest(self) -> str:
        return migration_digest(self.sql)


def migration_digest(sql: str) -> str:
    """SHA-256 over the migration's exact text.

    Domain-separated so a migration digest cannot be presented as an exchange
    digest, and computed over the text verbatim — including whitespace, because
    a reformatted migration *is* a different migration as far as "did this file
    change since we ran it" is concerned.
    """

    framed = b"ugence.model-egress-unit/migration/v1\x00" + sql.encode("utf-8")
    return hashlib.sha256(framed).hexdigest()


#: The applied-migration ledger. Outside :data:`SCHEMA_NAME` and owned by whoever
#: runs the migration, because it must exist before the owner role is created.
LEDGER_DDL = """
CREATE TABLE IF NOT EXISTS public.meu_schema_version (
    version      integer PRIMARY KEY,
    name         text NOT NULL,
    digest       char(64) NOT NULL,
    applied_at   timestamptz NOT NULL DEFAULT now()
)
"""


_0001 = f"""
-- Roles. Created idempotently: a shared cluster may already carry them, and a
-- migration that fell over on CREATE ROLE would be un-rerunnable.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{OWNER_ROLE}') THEN
        -- NOLOGIN, and no BYPASSRLS: the owner owns the tables and is still
        -- subject to their policies, which is what FORCE below relies on.
        CREATE ROLE {OWNER_ROLE} NOLOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{WORKER_ROLE}') THEN
        CREATE ROLE {WORKER_ROLE} NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{UNIT_ROLE}') THEN
        CREATE ROLE {UNIT_ROLE} NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE;
    END IF;
END
$$;

-- Created by the migrating role, which needs CREATE on the database; the owner
-- role deliberately has neither CREATEDB nor CREATEROLE.
CREATE SCHEMA IF NOT EXISTS {SCHEMA_NAME} AUTHORIZATION {OWNER_ROLE};

-- Everything below is created *as* the owner.
--
-- ``CREATE SCHEMA ... AUTHORIZATION`` sets the owner of the schema and nothing
-- else: tables created inside it still belong to whoever ran the statement. Left
-- that way the migrating role — typically a superuser — would own the tables,
-- FORCE ROW LEVEL SECURITY would be binding a role nobody uses, and the "the
-- owner cannot log in" property would be a claim about an empty schema. The
-- package's RLS tests assert the ownership directly for this reason.
SET ROLE {OWNER_ROLE};

-- One request for a model exchange.
--
-- ``content`` and ``canonical_request`` are nullable because a purge destroys
-- them; the digests beside them are NOT NULL and survive, which is what makes a
-- purged row a tombstone rather than a hole.
CREATE TABLE IF NOT EXISTS {SCHEMA_NAME}.egress_request (
    request_id        uuid PRIMARY KEY,
    tenant_id         uuid NOT NULL,
    submitted_at      timestamptz NOT NULL,
    state             text NOT NULL,
    model_id          text NOT NULL,
    purpose           text NOT NULL,
    parameters        jsonb NOT NULL,
    content           text,
    content_sha256    char(64) NOT NULL,
    request_digest    char(64) NOT NULL,
    lease_holder      text,
    lease_expires_at  timestamptz,
    dispatched_at     timestamptz,
    terminal_at       timestamptz,
    content_purged_at timestamptz,
    CONSTRAINT egress_request_state_known CHECK (
        state IN ('PENDING', 'LEASED', 'COMPLETED', 'REFUSED', 'OUTCOME_UNKNOWN')),
    -- A leased request has a lease; an unleased one does not. Without this a
    -- crashed claim could leave a row that is LEASED forever with nothing for
    -- the reconciler to expire.
    CONSTRAINT egress_request_lease_iff_leased CHECK (
        (state = 'LEASED') = (lease_holder IS NOT NULL AND lease_expires_at IS NOT NULL)),
    CONSTRAINT egress_request_terminal_at_iff_terminal CHECK (
        (state IN ('COMPLETED', 'REFUSED', 'OUTCOME_UNKNOWN')) = (terminal_at IS NOT NULL)),
    -- Purge destroys content and records when. One without the other would be
    -- either an unrecorded destruction or a claim of one that did not happen.
    CONSTRAINT egress_request_purged_has_no_content CHECK (
        (content_purged_at IS NULL) OR (content IS NULL))
);

-- What came back, or what could not be determined. One result per request: the
-- primary key is the request id, so a second write for the same request is a
-- key violation rather than a silent second answer.
CREATE TABLE IF NOT EXISTS {SCHEMA_NAME}.egress_result (
    request_id        uuid PRIMARY KEY
                      REFERENCES {SCHEMA_NAME}.egress_request (request_id),
    tenant_id         uuid NOT NULL,
    recorded_at       timestamptz NOT NULL,
    outcome           text NOT NULL,
    provider_id       text NOT NULL,
    refusal_reason    text,
    content           text,
    content_sha256    char(64),
    response_digest   char(64) NOT NULL,
    acknowledged_at   timestamptz,
    content_purged_at timestamptz,
    CONSTRAINT egress_result_outcome_known CHECK (
        outcome IN ('ANSWERED', 'REFUSED', 'OUTCOME_UNKNOWN')),
    -- A refusal names its reason and carries nothing else; anything else carries
    -- no reason. An unexplained refusal cannot be acted on by the requester.
    CONSTRAINT egress_result_reason_iff_refused CHECK (
        (outcome = 'REFUSED') = (refusal_reason IS NOT NULL)),
    CONSTRAINT egress_result_content_only_when_answered CHECK (
        outcome = 'ANSWERED' OR (content IS NULL AND content_sha256 IS NULL)),
    CONSTRAINT egress_result_purged_has_no_content CHECK (
        (content_purged_at IS NULL) OR (content IS NULL))
);

-- The queue read: pending work for one tenant, oldest first. Partial, because
-- the terminal rows are the ones that accumulate and the claim never looks at
-- them.
CREATE INDEX IF NOT EXISTS egress_request_claimable
    ON {SCHEMA_NAME}.egress_request (tenant_id, submitted_at)
    WHERE state = 'PENDING';

-- The reconciler's read: leases that may have expired.
CREATE INDEX IF NOT EXISTS egress_request_expiring_lease
    ON {SCHEMA_NAME}.egress_request (lease_expires_at)
    WHERE state = 'LEASED';

-- The purge sweep's read: answered-and-acknowledged results still holding content.
CREATE INDEX IF NOT EXISTS egress_result_purgeable
    ON {SCHEMA_NAME}.egress_result (tenant_id, acknowledged_at)
    WHERE content_purged_at IS NULL;

ALTER TABLE {SCHEMA_NAME}.egress_request ENABLE ROW LEVEL SECURITY;
ALTER TABLE {SCHEMA_NAME}.egress_request FORCE ROW LEVEL SECURITY;
ALTER TABLE {SCHEMA_NAME}.egress_result ENABLE ROW LEVEL SECURITY;
ALTER TABLE {SCHEMA_NAME}.egress_result FORCE ROW LEVEL SECURITY;

-- One policy per table, covering read and write. current_setting is called
-- WITHOUT missing_ok, so a session that never established a tenant identity
-- raises here instead of quietly matching no rows.
CREATE POLICY tenant_isolation ON {SCHEMA_NAME}.egress_request
    USING (tenant_id = current_setting('{TENANT_SETTING}')::uuid)
    WITH CHECK (tenant_id = current_setting('{TENANT_SETTING}')::uuid);

CREATE POLICY tenant_isolation ON {SCHEMA_NAME}.egress_result
    USING (tenant_id = current_setting('{TENANT_SETTING}')::uuid)
    WITH CHECK (tenant_id = current_setting('{TENANT_SETTING}')::uuid);

GRANT USAGE ON SCHEMA {SCHEMA_NAME} TO {WORKER_ROLE}, {UNIT_ROLE};

-- Asymmetric by design: neither side can forge the other's half of the
-- conversation. The worker writes requests, acknowledges results and purges
-- content; the unit dispositions requests and writes results.
--
-- The worker's writes are granted **by column**, not by table. It has to be able
-- to purge content and stamp an acknowledgement, and a table-level UPDATE that
-- let it do so would also let it set ``state`` — so a worker could mark its own
-- request COMPLETED with no exchange having happened, or rewrite an outcome the
-- unit recorded. Column grants give it exactly the two capabilities it needs and
-- refuse the rest at the database.
GRANT SELECT, INSERT ON {SCHEMA_NAME}.egress_request TO {WORKER_ROLE};
GRANT UPDATE (content, content_purged_at)
    ON {SCHEMA_NAME}.egress_request TO {WORKER_ROLE};

GRANT SELECT, UPDATE ON {SCHEMA_NAME}.egress_request TO {UNIT_ROLE};

GRANT SELECT ON {SCHEMA_NAME}.egress_result TO {WORKER_ROLE};
GRANT UPDATE (acknowledged_at, content, content_purged_at)
    ON {SCHEMA_NAME}.egress_result TO {WORKER_ROLE};

GRANT SELECT, INSERT, UPDATE ON {SCHEMA_NAME}.egress_result TO {UNIT_ROLE};

-- Back to the migrating role: the ledger row that records this migration lives
-- in ``public`` and the owner has no rights there.
RESET ROLE;
"""


#: Every migration, in apply order. Append only: editing an applied migration is
#: refused at startup by the digest check, and the fix is a new migration.
MIGRATIONS: Sequence[Migration] = (
    Migration(version=1, name="exchange_roles_tables_and_rls", sql=_0001),
)


def statements(sql: str) -> list:
    """Split a migration into executable statements.

    Line comments are stripped **before** splitting, because a ``;`` inside a
    trailing ``--`` comment is not a statement terminator and naive splitting
    would cut a statement in half. Dollar-quoted blocks are kept whole for the
    same reason: the ``;`` inside a ``DO $$ ... $$`` body belongs to the body.
    """

    out: list = []
    buf: list = []
    in_dollar = False
    for raw in sql.splitlines():
        line = raw
        if not in_dollar:
            marker = line.find("--")
            if marker != -1:
                line = line[:marker]
        if line.count("$$") % 2 == 1:
            in_dollar = not in_dollar
        buf.append(line)
        if not in_dollar and line.rstrip().endswith(";"):
            statement = "\n".join(buf).strip().rstrip(";").strip()
            if statement:
                out.append(statement)
            buf = []
    tail = "\n".join(buf).strip().rstrip(";").strip()
    if tail:
        out.append(tail)
    return out
