"""Disposition reconciliation (Phase 4). Maps each stage's LOCAL disposition vocabulary to the unified
shadow outcome WITHOUT conflating them. Stage-local decisions are preserved (in the envelope's
stage_dispositions); this module only decides the single final shadow outcome by PRECEDENCE, so the
final outcome never erases the underlying stage outcomes.
"""
from __future__ import annotations

from typing import Dict, List, Tuple

# the 11 shadow-only outcomes
SHADOW_OUTCOMES = ("WOULD_ALLOW", "WOULD_QUALIFY", "WOULD_REJECT", "WOULD_ESCALATE",
                   "WOULD_BLOCK_ACTION", "WOULD_CONSTRAIN_ACTION", "INDETERMINATE",
                   "PIPELINE_ERROR", "CONTRACT_ERROR", "EVIDENCE_UNAVAILABLE", "EXECUTION_UNAVAILABLE")

# precedence: higher = wins when multiple stages produce outcomes (most safety-critical first).
# errors and unavailability outrank permissive outcomes; action blocks outrank assertion allows.
PRECEDENCE = {
    "CONTRACT_ERROR": 100, "PIPELINE_ERROR": 95,
    "EXECUTION_UNAVAILABLE": 90, "EVIDENCE_UNAVAILABLE": 85,
    "WOULD_BLOCK_ACTION": 80, "WOULD_REJECT": 75, "WOULD_ESCALATE": 70,
    "WOULD_CONSTRAIN_ACTION": 60, "INDETERMINATE": 55, "WOULD_QUALIFY": 40, "WOULD_ALLOW": 10,
}

# per-stage local vocabulary -> shadow outcome (mapping, not conflation)
EXECUTION_MAP = {"ELIGIBLE": "WOULD_ALLOW", "CONDITIONALLY_ELIGIBLE": "WOULD_QUALIFY",
                 "INELIGIBLE": "EXECUTION_UNAVAILABLE", "INDETERMINATE": "INDETERMINATE"}
MODEL_POLICY_MAP = {"selected": "WOULD_ALLOW", "abstain": "EXECUTION_UNAVAILABLE"}
CLAIM_MAP = {"VALID": "WOULD_ALLOW", "VALID_WITH_ALTERNATIVES": "WOULD_ALLOW",
             "INDETERMINATE": "INDETERMINATE", "AMBIGUOUS": "INDETERMINATE",
             "REFERENCE_ERROR": "WOULD_QUALIFY", "REJECT_DECOMPOSITION": "WOULD_REJECT",
             "ESCALATE": "WOULD_ESCALATE"}
SCOPE_MAP = {"resolved": "WOULD_ALLOW", "INDETERMINATE_SCOPE": "INDETERMINATE"}
EVIDENCE_DELIVERY_MAP = {"ALLOW": "WOULD_ALLOW", "QUALIFY": "WOULD_QUALIFY", "REJECT": "WOULD_REJECT",
                         "ESCALATE": "WOULD_ESCALATE", "INDETERMINATE": "EVIDENCE_UNAVAILABLE"}
ASSERTION_MAP = {"ALLOW": "WOULD_ALLOW", "QUALIFY": "WOULD_QUALIFY", "REJECT": "WOULD_REJECT",
                 "ESCALATE": "WOULD_ESCALATE", "INDETERMINATE": "INDETERMINATE"}
ACTION_MAP = {"PERMIT": "WOULD_ALLOW", "CONSTRAIN": "WOULD_CONSTRAIN_ACTION",
              "BLOCK": "WOULD_BLOCK_ACTION", "ESCALATE": "WOULD_ESCALATE",
              "INDETERMINATE": "INDETERMINATE", "NO_ACTION": ""}


def map_stage(stage: str, local: str) -> str:
    table = {"execution_gate": EXECUTION_MAP, "model_policy": MODEL_POLICY_MAP,
             "claim_integrity": CLAIM_MAP, "scope_integrity": SCOPE_MAP,
             "evidence_assurance": EVIDENCE_DELIVERY_MAP, "assertion_gate": ASSERTION_MAP,
             "action_gate": ACTION_MAP}.get(stage, {})
    return table.get(local, "INDETERMINATE")   # unknown local disposition -> INDETERMINATE (fail closed)


def reconcile(stage_outcomes: List[Tuple[str, str]]) -> Tuple[str, Dict[str, str]]:
    """stage_outcomes: [(stage, shadow_outcome)] in pipeline order. Returns (final, per_stage).
    The final is the highest-precedence non-empty outcome; per_stage preserves each mapping."""
    per_stage = {stage: out for stage, out in stage_outcomes if out}
    if not per_stage:
        return "INDETERMINATE", {}
    final = max(per_stage.values(), key=lambda o: PRECEDENCE.get(o, 50))
    return final, per_stage


def delivered_as_supported(final: str) -> bool:
    return final in ("WOULD_ALLOW", "WOULD_QUALIFY")
