"""Database-domain ACP envelopes (V0.3).

A NEW sibling domain adapter modelled on the Kubernetes ``cloud/`` package: it
carries database-specific world/candidate types and reuses the frozen ACP
composition core UNCHANGED. Nothing here is Kubernetes-shaped; nothing modifies
the ACP core. Deterministic, shadow-only — no live database is touched.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Dict, Tuple


def _content_version(*parts: Any) -> str:
    """Deterministic content identity for a world snapshot (stdlib only)."""
    raw = "\x1f".join(str(p) for p in parts).encode("utf-8")
    return "dbworld:" + hashlib.sha256(raw).hexdigest()[:32]


@dataclass(frozen=True)
class DbWorldState:
    """Immutable snapshot of the database's operational safety posture (a fixture).

    These are deterministic operational facts a real read-only telemetry adapter
    would supply; here they come from an authored fixture (no live DB telemetry)."""
    connection_ref: str
    schema: str
    table: str
    observed_row_version: str
    reachable: bool
    healthy: bool
    active_transactions: int
    max_transactions: int
    max_affected_rows: int
    migration_active: bool
    freeze_active: bool
    replication_healthy: bool
    replication_lag_s: float
    max_replication_lag_s: float
    lock_contention_ok: bool
    backup_available: bool
    observation_time_s: float

    @property
    def version(self) -> str:
        return _content_version(
            self.connection_ref, self.schema, self.table, self.observed_row_version,
            self.reachable, self.healthy, self.active_transactions, self.max_transactions,
            self.max_affected_rows, self.migration_active, self.freeze_active,
            self.replication_healthy, self.replication_lag_s, self.max_replication_lag_s,
            self.lock_contention_ok, self.backup_available)


@dataclass(frozen=True)
class DbActionCandidate:
    """A proposed database mutation bound to an observed world version."""
    candidate_id: str
    connection_ref: str
    schema: str
    table: str
    sql_operation: str
    estimated_rows: int
    unbounded: bool
    reversibility: str
    expected_row_version: str
    compensation_ref: str
    origin_state_version: str

    @property
    def is_high_risk(self) -> bool:
        return self.reversibility != "REVERSIBLE"

    @property
    def targets(self) -> Tuple[str, str, str]:
        return (self.connection_ref, self.schema, self.table)


@dataclass(frozen=True)
class DbOperationalEvidence:
    """Deterministic evidence record produced by the safety evaluator."""
    reachable: bool
    state_current: bool
    within_scope: bool
    transaction_capacity_ok: bool
    replication_ok: bool
    rollback_available: bool
    freeze_active: bool
    migration_active: bool
    reason_codes: Tuple[str, ...] = ()
    validity: str = "VALID"  # VALID | STALE | MISSING | EVALUATOR_FAILED

    @property
    def is_usable(self) -> bool:
        return self.validity == "VALID"
