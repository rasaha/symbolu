"""Common benchmark strategy protocol + workload-cost scaffolding (Task 5/10)."""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..schemas.result import StrategyResult

#: workload counters (structural, NOT financial) — Task 10
COST_KEYS = (
    "provider_invocations", "assertion_evaluations", "authorization_evaluations",
    "human_review_events", "assessment_records", "recommendation_records",
    "decision_records", "authorization_records", "constraint_checks", "obligation_checks",
    "audit_events", "trace_links", "execution_attempts", "reconciliation_attempts",
    "failure_normalization_events",
)


def zero_cost() -> dict:
    return {k: 0 for k in COST_KEYS}


@runtime_checkable
class GovernanceStrategy(Protocol):
    @property
    def strategy_id(self) -> str: ...

    def run(self, scenario, *, registry_failure: bool = False) -> StrategyResult: ...
