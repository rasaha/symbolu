"""Neutral, benchmark-owned strategy result (Task 6).

Every strategy returns this common record. Capabilities a strategy does not
possess are marked with explicit sentinels (``NOT_APPLICABLE`` / ``NOT_PERFORMED``
/ ``UNKNOWN``) — never fabricated as ``False``/empty where the semantics differ.
"""
from __future__ import annotations

from dataclasses import dataclass, field

# sentinels
NOT_APPLICABLE = "NOT_APPLICABLE"
NOT_PERFORMED = "NOT_PERFORMED"
UNKNOWN = "UNKNOWN"


@dataclass
class StrategyResult:
    scenario_id: str
    strategy_id: str

    # --- assertion layer ---------------------------------------------------
    assertion_evaluated: bool = False
    assertion_outcome: str = NOT_PERFORMED          # SUPPORTED/UNSUPPORTED/CONSTRAINED/INDETERMINATE
    assertion_supported: str = UNKNOWN              # YES / NO / UNKNOWN / NOT_PERFORMED
    qualifiers_preserved: object = NOT_PERFORMED    # tuple[str,...] or sentinel
    unsupported_components_preserved: object = NOT_PERFORMED
    evidence_provenance_preserved: str = NOT_PERFORMED  # YES / NO / NOT_PERFORMED

    # --- action layer ------------------------------------------------------
    action_proposed: bool = False
    authorization_performed: bool = False
    authorization_outcome: str = NOT_PERFORMED      # AUTHORIZED/AUTHORIZED_WITH_CONSTRAINTS/DENIED/INDETERMINATE
    constraints_issued: object = NOT_APPLICABLE     # tuple[str,...] or sentinel
    constraints_enforced: str = NOT_APPLICABLE      # ENFORCED / NOT_ENFORCED / NOT_APPLICABLE
    obligations_issued: object = NOT_APPLICABLE
    obligations_verified: str = NOT_APPLICABLE      # VERIFIED / NOT_VERIFIED / NOT_APPLICABLE

    # --- execution / reconciliation ---------------------------------------
    dispatch_attempted: bool = False
    dispatch_allowed: bool = False
    dispatched: bool = False
    execution_attempted: bool = False
    execution_outcome: str = NOT_PERFORMED          # SUCCEEDED/FAILED/REJECTED/TRANSPORT_FAILED/TIMED_OUT/BLOCKED/...
    reconciliation_performed: bool = False
    reconciliation_outcome: str = NOT_PERFORMED     # RECONCILED/MISMATCHED/FAILED/NOT_PERFORMED

    # --- human review ------------------------------------------------------
    human_review_requested: bool = False
    human_review_completed: bool = False
    human_authority: str = ""

    # --- workload / records ------------------------------------------------
    provider_failures: int = 0
    audit_events: int = 0
    trace_links: int = 0
    lifecycle_records: int = 0

    # --- benchmark-owned neutral classification (set post-strategy) --------
    final_safety_outcome: str = UNKNOWN
    final_governance_compliance: str = UNKNOWN      # COMPLIANT/NONCOMPLIANT/NOT_APPLICABLE/UNKNOWN

    # --- workload counters (cost model, Task 10) ---------------------------
    cost: dict = field(default_factory=dict)

    # raw trace (not scored; excluded from substantive digest)
    trace: dict = field(default_factory=dict)
    error: object = None

    def to_dict(self) -> dict:
        d = dict(self.__dict__)
        for k in ("qualifiers_preserved", "unsupported_components_preserved",
                  "constraints_issued", "obligations_issued"):
            v = d[k]
            if isinstance(v, tuple):
                d[k] = list(v)
        d.pop("trace", None)
        return d
