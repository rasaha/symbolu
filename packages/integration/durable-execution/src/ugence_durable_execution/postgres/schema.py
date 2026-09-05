"""DDL for the durable Agent Runtime stores (ADR §5).

Every table lives in the **application** database — the same one DBOS writes its
``dbos.datasource_outputs`` step record into — because that co-location is what makes
the single-transaction property of OD-1 available at all. The DBOS *system* database
(workflow status) is deliberately a different database and is NOT part of that
transaction; see the README's consistency-boundary section.

Two shapes recur and are load-bearing:

* **Append-only with a unique ``(instance_id, seq)``.** Checkpoints and events are
  history; nothing updates them. The unique constraint is what makes a duplicate
  engine delivery collide loudly instead of interleaving silently.
* **One row per instance for resume state.** ``runtime_state`` is the row a worker
  takes ``SELECT ... FOR UPDATE`` on to claim an instance. That lock is what makes
  "one instance is driven by one worker at a time" a database property rather than a
  convention — the property Agent Runtime itself does not provide (its README states
  it is not distributed-safe).
"""
from __future__ import annotations

SCHEMA_NAME = "ugence_art"

SCHEMA_SQL = f"""
CREATE SCHEMA IF NOT EXISTS {SCHEMA_NAME};

-- One row per instance. The claim row (SELECT ... FOR UPDATE) and the resume point.
CREATE TABLE IF NOT EXISTS {SCHEMA_NAME}.runtime_state (
    instance_id        text PRIMARY KEY,
    workflow_id        text NOT NULL,
    definition_digest  text NOT NULL,
    correlation_id     text,
    engine_id          text NOT NULL,
    checkpoint         jsonb NOT NULL,
    updated_seq        bigint NOT NULL DEFAULT 0
);

-- Append-only checkpoint history. put() inserts; it never updates.
CREATE TABLE IF NOT EXISTS {SCHEMA_NAME}.checkpoints (
    instance_id  text NOT NULL,
    seq          bigint NOT NULL,
    digest       text NOT NULL,
    ext_digest   text NOT NULL,
    body         jsonb NOT NULL,
    PRIMARY KEY (instance_id, seq)
);

-- Append-only runtime event log. attempt_token/engine_id are observability columns
-- that NO read path branches on: a duplicate delivery is recorded, never suppressed.
CREATE TABLE IF NOT EXISTS {SCHEMA_NAME}.runtime_events (
    instance_id    text NOT NULL,
    seq            bigint NOT NULL,
    event_type     text NOT NULL,
    body           jsonb NOT NULL,
    attempt_token  text,
    engine_id      text,
    PRIMARY KEY (instance_id, seq)
);

-- Budget ledger (ADR §8 row 8). The ceiling is enforced by a CHECK constraint, so
-- over-consumption is refused by Postgres rather than by in-process bookkeeping.
CREATE TABLE IF NOT EXISTS {SCHEMA_NAME}.budgets (
    budget_id  text PRIMARY KEY,
    ceiling    bigint NOT NULL,
    consumed   bigint NOT NULL DEFAULT 0,
    CONSTRAINT budget_within_ceiling CHECK (consumed >= 0 AND consumed <= ceiling)
);

-- One row per consumed unit, keyed by the runtime's OWN idempotency key. A retry
-- carrying the same key settles once, however many times it is delivered.
CREATE TABLE IF NOT EXISTS {SCHEMA_NAME}.budget_consumption (
    budget_id        text NOT NULL REFERENCES {SCHEMA_NAME}.budgets(budget_id),
    idempotency_key  text NOT NULL,
    instance_id      text NOT NULL,
    units            bigint NOT NULL,
    PRIMARY KEY (budget_id, idempotency_key)
);

-- Worker claims, for recover(). A crashed worker's rows are reclaimable; the claim
-- itself grants nothing beyond the right to drive.
CREATE TABLE IF NOT EXISTS {SCHEMA_NAME}.worker_claims (
    instance_id  text PRIMARY KEY,
    worker_id    text NOT NULL,
    claimed_at   double precision NOT NULL
);
"""


def schema_statements() -> tuple:
    """``SCHEMA_SQL`` as individual statements, with line comments stripped first.

    Splitting the raw text on ``;`` is wrong: the comments above each table contain
    sentences that end in a full stop and, more to the point, the parenthesised prose
    contains semicolons. Comments are removed before splitting so the DDL executes as
    written rather than as punctuated.
    """
    lines = [
        ln for ln in SCHEMA_SQL.splitlines() if not ln.lstrip().startswith("--")
    ]
    body = "\n".join(lines)
    return tuple(s.strip() for s in body.split(";") if s.strip())
