"""Deterministic migrations: an ordered, digest-pinned list applied in one transaction.

What "deterministic" buys, and why not Alembic
----------------------------------------------
Alembic orders by a ``down_revision`` chain and identifies a migration by a hash
somebody typed. Here a migration is identified by **the digest of its own text**,
the list is a Python tuple in apply order, and :func:`migrate` refuses to proceed
if a migration that was already applied no longer hashes to what was recorded.

That last property is the one worth having. Editing an already-applied migration
is the classic way a schema silently diverges between two deployments: the file
says one thing, the database contains another, and nothing notices until a
constraint that "exists" turns out not to. Pinning the digest turns that from a
latent divergence into a refusal at startup, naming the migration.

Applying is all-or-nothing. PostgreSQL has transactional DDL, so every pending
migration and the ledger rows recording them commit together or not at all.

**Migration is never startup.** ``migrate`` is not called at import and no runtime
composes it: the ruling of 2026-09-10 forbids role creation, grants and migration
authority during worker or MEU startup, because a service that provisions its own
privileges on boot holds, for one moment on every deploy, exactly the authority
the boundary denies it. A separately controlled migration identity assumes the
non-login owner role during reviewed migrations only.

**Provisioning and credential custody are unimplemented production prerequisites**
`[G]`, recorded as such rather than substituted by a runbook claim. This module
creates the roles a *test* cluster needs; it does not issue credentials, and the
runtime roles are created without ``LOGIN`` precisely so that nothing here can be
mistaken for having provisioned a usable identity.
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
    """SHA-256 over the migration's exact text, domain-separated."""

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
--
-- None of the three has LOGIN. Credential custody is an unimplemented production
-- prerequisite, and a role with a password here would be a credential this
-- repository had provisioned without any custody for it.
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
-- owner cannot log in" property would be a claim about an empty schema.
SET ROLE {OWNER_ROLE};

-- One authorized request for a model exchange.
--
-- The primary key is (tenant_id, request_id), not request_id alone. Tenant
-- identity participates in request identity and uniqueness, so two tenants'
-- requests can never collapse into one row and the dedup key is tenant-scoped by
-- construction rather than by every query remembering to say so.
--
-- ``minimized_context`` is a purgeable artifact with its own creation clock;
-- ``content_digest`` beside it is NOT NULL and survives, which is what makes a
-- purged row a tombstone rather than a hole.
CREATE TABLE IF NOT EXISTS {SCHEMA_NAME}.egress_request (
    tenant_id         uuid NOT NULL,
    request_id        uuid NOT NULL,
    correlation_id    uuid NOT NULL,
    exchange_schema_version text NOT NULL,
    submitted_at      timestamptz NOT NULL,
    not_valid_after   timestamptz NOT NULL,
    state             text NOT NULL,

    -- The authorization binding. Verified by the MEU, never decided by it.
    clearance_ref     text NOT NULL,
    clearance_digest  char(64) NOT NULL,
    authorized_vendor text NOT NULL,
    authorized_model  text NOT NULL,
    policy_id         text NOT NULL,
    reservation_id    text NOT NULL,

    parameters        jsonb NOT NULL,

    -- Content artifact, independently retained.
    minimized_context jsonb,
    content_digest    char(64) NOT NULL,
    content_created_at timestamptz NOT NULL,
    content_purged_at timestamptz,

    request_digest    char(64) NOT NULL,

    -- Mutable, and excluded from the request digest for that reason.
    lease_holder      text,
    lease_expires_at  timestamptz,
    dispatched_at     timestamptz,
    terminal_at       timestamptz,

    PRIMARY KEY (tenant_id, request_id),
    CONSTRAINT egress_request_tenant_not_empty CHECK (tenant_id IS NOT NULL),
    CONSTRAINT egress_request_state_known CHECK (
        state IN ('PENDING', 'LEASED', 'COMPLETED', 'REFUSED', 'FAILED',
                  'OUTCOME_UNKNOWN')),
    -- A leased request has a lease; an unleased one does not. Without this a
    -- crashed claim could leave a row LEASED forever with nothing to expire.
    CONSTRAINT egress_request_lease_iff_leased CHECK (
        (state = 'LEASED') = (lease_holder IS NOT NULL AND lease_expires_at IS NOT NULL)),
    CONSTRAINT egress_request_terminal_at_iff_terminal CHECK (
        (state IN ('COMPLETED', 'REFUSED', 'FAILED', 'OUTCOME_UNKNOWN'))
        = (terminal_at IS NOT NULL)),
    -- Purge destroys content and records when. One without the other would be
    -- either an unrecorded destruction or a claim of one that did not happen.
    CONSTRAINT egress_request_purged_has_no_content CHECK (
        (content_purged_at IS NULL) OR (minimized_context IS NULL))
);

-- What came back, or what could not be determined. One result per request within
-- a tenant, so a second write is a key violation rather than a silent second
-- answer.
CREATE TABLE IF NOT EXISTS {SCHEMA_NAME}.egress_result (
    tenant_id         uuid NOT NULL,
    request_id        uuid NOT NULL,
    correlation_id    uuid NOT NULL,
    recorded_at       timestamptz NOT NULL,
    trust             text NOT NULL,
    outcome           text NOT NULL,
    refusal_reason    text,

    -- Provenance survives every purge: it is what keeps a purged
    -- OUTCOME_UNKNOWN reconcilable, and what names the adapter and whether the
    -- call was genuine.
    adapter_id        text NOT NULL,
    provenance_kind   text NOT NULL,
    genuine_call      boolean NOT NULL,
    provenance        jsonb NOT NULL,

    -- Content artifact, independently retained on its own clock.
    payload           text,
    content_digest    char(64),
    content_created_at timestamptz NOT NULL,
    content_purged_at timestamptz,

    response_digest   char(64) NOT NULL,
    acknowledged_at   timestamptz,

    -- The vendor allocation D-5 reserved. Neither lease expiry nor content
    -- purging releases it, and the CHECK makes "released" unrepresentable rather
    -- than merely unwritten: purging the content does not purge the obligation.
    reservation_released boolean NOT NULL DEFAULT false,

    PRIMARY KEY (tenant_id, request_id),
    FOREIGN KEY (tenant_id, request_id)
        REFERENCES {SCHEMA_NAME}.egress_request (tenant_id, request_id),
    CONSTRAINT egress_result_trust_is_constant CHECK (trust = 'UNTRUSTED_EVIDENCE'),
    CONSTRAINT egress_result_outcome_known CHECK (
        outcome IN ('ANSWERED', 'REFUSED', 'FAILED', 'OUTCOME_UNKNOWN')),
    CONSTRAINT egress_result_provenance_kind_known CHECK (
        provenance_kind IN ('RESPONSE', 'DISPATCH_ATTEMPT')),
    -- An ambiguous dispatch writes a distinct record type, never a response
    -- record with empty fields.
    CONSTRAINT egress_result_unknown_is_a_dispatch_attempt CHECK (
        (outcome = 'OUTCOME_UNKNOWN') = (provenance_kind = 'DISPATCH_ATTEMPT')),
    -- This distribution makes no genuine provider call, and no row may claim one.
    CONSTRAINT egress_result_no_genuine_call CHECK (genuine_call = false),
    CONSTRAINT egress_result_reservation_never_released CHECK (
        reservation_released = false),
    CONSTRAINT egress_result_reason_iff_refused CHECK (
        (outcome = 'REFUSED') = (refusal_reason IS NOT NULL)),
    CONSTRAINT egress_result_payload_only_when_answered CHECK (
        outcome = 'ANSWERED' OR (payload IS NULL AND content_digest IS NULL)),
    CONSTRAINT egress_result_purged_has_no_payload CHECK (
        (content_purged_at IS NULL) OR (payload IS NULL))
);

-- The queue read: claimable work for one tenant, oldest first. Partial, because
-- the terminal rows accumulate and the claim never looks at them.
CREATE INDEX IF NOT EXISTS egress_request_claimable
    ON {SCHEMA_NAME}.egress_request (tenant_id, submitted_at)
    WHERE state = 'PENDING';

-- The reconciler's read: leases that may have expired.
CREATE INDEX IF NOT EXISTS egress_request_expiring_lease
    ON {SCHEMA_NAME}.egress_request (lease_expires_at)
    WHERE state = 'LEASED';

-- The retention sweep's reads: content still present, by its own clock.
CREATE INDEX IF NOT EXISTS egress_request_unpurged_content
    ON {SCHEMA_NAME}.egress_request (tenant_id, content_created_at)
    WHERE content_purged_at IS NULL;

CREATE INDEX IF NOT EXISTS egress_result_unpurged_content
    ON {SCHEMA_NAME}.egress_result (tenant_id, content_created_at)
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
-- conversation. The worker creates authorized requests, reads terminal results
-- for its tenant and acknowledges consumption; the MEU leases requests and
-- writes terminal results.
--
-- The worker's writes are granted **by column**. It has to purge content and
-- stamp an acknowledgement, and a table-level UPDATE that let it do so would
-- also let it set ``state`` — so a worker could mark its own request COMPLETED
-- with no exchange having happened, or rewrite an outcome the unit recorded.
GRANT SELECT, INSERT ON {SCHEMA_NAME}.egress_request TO {WORKER_ROLE};
GRANT UPDATE (minimized_context, content_purged_at)
    ON {SCHEMA_NAME}.egress_request TO {WORKER_ROLE};

GRANT SELECT, UPDATE ON {SCHEMA_NAME}.egress_request TO {UNIT_ROLE};

GRANT SELECT ON {SCHEMA_NAME}.egress_result TO {WORKER_ROLE};
GRANT UPDATE (acknowledged_at, payload, content_purged_at)
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
