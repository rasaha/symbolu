"""Deterministic database operational-safety evaluator (V0.3 §7).

Answers ACP's question — *"is this mutation operationally safe against the
observed database state right now?"* — never ActionGate's authorization question.
Every check is a HARD, non-compensatory deterministic predicate over an authored
fixture world; one failed HARD check makes the candidate inadmissible (fail
closed). Produces a frozen ACP ``CloudRecommendation`` (reused unchanged), which
the adapter composes with the ActionGate verdict.

Checks implemented (all deterministic, fixture-backed — no live DB telemetry):
  state binding   candidate.origin_state_version == world.version
  reachable       world.reachable and world.healthy
  target bound    candidate names this connection/schema/table
  state current   expected_row_version == observed_row_version (optimistic concurrency)
  scope bound     not unbounded and estimated_rows <= max_affected_rows
  txn capacity    active_transactions < max_transactions
  no migration    not migration_active
  no freeze       not freeze_active
  replication     replication_healthy and replication_lag_s <= max_replication_lag_s
  lock posture    lock_contention_ok
  rollback ready  high-risk mutations require compensation_ref or an available backup
"""
from __future__ import annotations

from typing import List, Optional, Tuple

from .envelopes import DbActionCandidate, DbOperationalEvidence, DbWorldState

# Reuse the frozen ACP recommendation vocabulary UNCHANGED (no new enum).
from symbolu_robotics.autonomous_control_plane.cloud.outcomes import CloudRecommendation

# default freshness bound for a database observation (seconds)
DEFAULT_MAX_FRESHNESS_S = 30.0


def _checks(candidate: DbActionCandidate, world: DbWorldState) -> List[Tuple[str, bool]]:
    results: List[Tuple[str, bool]] = []
    results.append(("REACHABLE", world.reachable and world.healthy))
    results.append(("TARGET_BOUND",
                    candidate.targets == (world.connection_ref, world.schema, world.table)))
    results.append(("STATE_VERSION_CURRENT",
                    candidate.expected_row_version == world.observed_row_version))
    results.append(("SCOPE_WITHIN_BOUND",
                    (not candidate.unbounded)
                    and candidate.estimated_rows <= world.max_affected_rows))
    results.append(("TRANSACTION_CAPACITY",
                    world.active_transactions < world.max_transactions))
    results.append(("NO_MIGRATION_CONFLICT", not world.migration_active))
    results.append(("NO_ACTIVE_FREEZE", not world.freeze_active))
    results.append(("REPLICATION_ACCEPTABLE",
                    world.replication_healthy
                    and world.replication_lag_s <= world.max_replication_lag_s))
    results.append(("LOCK_CONTENTION_OK", world.lock_contention_ok))
    if candidate.is_high_risk:
        results.append(("ROLLBACK_AVAILABLE",
                        bool(candidate.compensation_ref) or world.backup_available))
    return results


def evaluate(candidate: DbActionCandidate, world: Optional[DbWorldState], *,
             now_s: float, freshness_s: float,
             max_freshness_s: float = DEFAULT_MAX_FRESHNESS_S
             ) -> Tuple[DbOperationalEvidence, CloudRecommendation]:
    """Return (evidence, recommendation). Fail closed on any HARD failure."""
    # fail-closed pre-checks
    if world is None:
        return (DbOperationalEvidence(False, False, False, False, False, False, False, False,
                                      reason_codes=("STATE_MISSING",), validity="MISSING"),
                CloudRecommendation.HOLD)
    if candidate.origin_state_version != world.version:
        return (DbOperationalEvidence(world.reachable, False, False, False, False, False,
                                      world.freeze_active, world.migration_active,
                                      reason_codes=("STATE_BINDING_MISMATCH",), validity="MISSING"),
                CloudRecommendation.HOLD)
    if freshness_s < 0.0 or freshness_s > max_freshness_s:
        return (DbOperationalEvidence(world.reachable, False, False, False, False, False,
                                      world.freeze_active, world.migration_active,
                                      reason_codes=("STATE_STALE",), validity="STALE"),
                CloudRecommendation.REOBSERVE)

    results = _checks(candidate, world)
    failed = tuple(f"{name}_FAILED" for name, ok in results if not ok)
    passed = {name: ok for name, ok in results}
    evidence = DbOperationalEvidence(
        reachable=passed.get("REACHABLE", False),
        state_current=passed.get("STATE_VERSION_CURRENT", False),
        within_scope=passed.get("SCOPE_WITHIN_BOUND", False),
        transaction_capacity_ok=passed.get("TRANSACTION_CAPACITY", False),
        replication_ok=passed.get("REPLICATION_ACCEPTABLE", False),
        rollback_available=passed.get("ROLLBACK_AVAILABLE", True),
        freeze_active=world.freeze_active, migration_active=world.migration_active,
        reason_codes=failed, validity="VALID")
    rec = CloudRecommendation.PROCEED if not failed else CloudRecommendation.HOLD
    return evidence, rec
