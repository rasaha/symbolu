"""Correlated audit-trace assembly + completeness (Task 112).

For every full workflow the runner assembles a single correlated trace that
permits reconstruction of the whole decision, from supplied evidence through
reconciliation. This module defines the required trace fields and a completeness
check. Provider payloads are referenced, not duplicated.
"""
from __future__ import annotations

from dataclasses import dataclass

#: Trace keys that must always be present (a workflow that stops early sets the
#: downstream keys to explicit sentinels, not missing).
REQUIRED_KEYS = (
    "scenario_id", "correlation_id", "case_id", "evidence_ids", "assertion",
    "assertion_provider", "tap_outcome", "assessment_id", "recommendation_id",
    "recommendation_cites_assessment", "decision_id", "proceeded_to_action",
    "action_provider", "authorization_outcome", "constraints", "obligations",
    "dispatched", "execution_outcome", "reconciliation_status",
)


@dataclass(frozen=True)
class TraceCompleteness:
    complete: bool
    missing: tuple[str, ...]
    present: tuple[str, ...]


def check_completeness(trace: dict) -> TraceCompleteness:
    missing = tuple(k for k in REQUIRED_KEYS
                    if k not in trace or trace[k] is None or trace[k] == "")
    present = tuple(k for k in REQUIRED_KEYS if k not in missing)
    return TraceCompleteness(complete=not missing, missing=missing, present=present)
