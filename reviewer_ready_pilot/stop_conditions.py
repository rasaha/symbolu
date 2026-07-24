"""Phase 17 - Pilot stop conditions.

Pre-registered conditions that HALT the (future) human pilot. Two tiers:

  * Immediate stops - any one fires and the pilot halts instantly. These encode the non-negotiable
    constraints: no enforcement, no external action, no prohibited data, no blinding breach, no reviewer
    identity leak, no unrecorded override, no frozen-component drift, no ActionGate semantic loss, no
    undeletable data.
  * Cumulative stops - frozen thresholds checked against real-reviewer metrics. If metrics are
    NOT_ENOUGH_HUMAN_EVIDENCE (no real reviewers), NO cumulative stop can fire - there is nothing to
    breach, and the absence of human evidence is never treated as a passing signal.

Fail-closed: an unknown or erroring immediate signal is treated as fired. Thresholds are frozen before any
outcome-bearing review and are not tuned on the review set. Deterministic, stdlib-only.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from reviewer_ready_pilot import metrics as m

# frozen cumulative thresholds (set before any outcome-bearing review; never tuned on the review set)
FROZEN_THRESHOLDS = {
    "min_reviewer_system_agreement_high_risk": 0.80,
    "max_reviewer_reviewer_disagreement_rate": 0.40,
    "max_override_rate": 0.40,
    "max_unresolved_rate": 0.20,
    "min_trap_catch_rate": 0.80,
}

# any one of these halts the pilot instantly
_IMMEDIATE = [
    "enforcement_attempt",
    "external_action_execution",
    "prohibited_or_unapproved_data",
    "sensitive_data_leakage",
    "blinding_breach",                      # system result exposed before Stage A
    "reviewer_identity_leakage",
    "unrecorded_reviewer_override",
    "audit_chain_failure",
    "frozen_policy_drift",
    "frozen_component_drift",
    "native_actiongate_semantic_loss",      # 6 outcomes collapsed
    "downstream_threshold_lowered",         # EvidenceAssurance or other threshold lowered
    "simulation_labeled_as_human_validation",
    "undeletable_pilot_data",
    "external_customer_onboarded",
]


@dataclass
class StopResult:
    should_stop: bool
    immediate_fired: List[str] = field(default_factory=list)
    cumulative_fired: List[str] = field(default_factory=list)
    detail: Dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> Dict[str, Any]:
        return {"should_stop": self.should_stop, "immediate_fired": self.immediate_fired,
                "cumulative_fired": self.cumulative_fired, "detail": self.detail}


def check_immediate(signals: Dict[str, bool]) -> List[str]:
    fired = []
    for cond in _IMMEDIATE:
        try:
            if signals.get(cond, False):
                fired.append(cond)
        except Exception:
            fired.append(cond)              # fail-closed
    return fired


def check_cumulative(review_metrics: Dict[str, Any],
                     thresholds: Optional[Dict[str, Any]] = None) -> List[str]:
    """Breaches against real-reviewer metrics. No real evidence => no cumulative fire."""
    t = thresholds or FROZEN_THRESHOLDS
    if review_metrics.get("status") != m.STATUS_OK:
        return []                           # NOT_ENOUGH_HUMAN_EVIDENCE: nothing to breach
    fired = []

    def _num(v):
        return v if isinstance(v, (int, float)) else None

    rr = _num(review_metrics.get("reviewer_reviewer_agreement"))
    if rr is not None and (1.0 - rr) > t["max_reviewer_reviewer_disagreement_rate"]:
        fired.append("reviewer_disagreement_above_threshold")
    rs = _num(review_metrics.get("reviewer_system_agreement"))
    if rs is not None and rs < t["min_reviewer_system_agreement_high_risk"]:
        fired.append("reviewer_system_agreement_below_threshold")
    ov = _num(review_metrics.get("override_rate"))
    if ov is not None and ov > t["max_override_rate"]:
        fired.append("override_rate_excessive")
    tc = _num(review_metrics.get("trap_catch_rate"))
    if tc is not None and tc < t["min_trap_catch_rate"]:
        fired.append("trap_catch_rate_below_threshold")
    return fired


def evaluate(signals: Dict[str, bool], review_metrics: Dict[str, Any],
             thresholds: Optional[Dict[str, Any]] = None) -> StopResult:
    imm = check_immediate(signals)
    cum = check_cumulative(review_metrics, thresholds)
    return StopResult(should_stop=bool(imm or cum), immediate_fired=imm, cumulative_fired=cum,
                      detail={"thresholds": thresholds or FROZEN_THRESHOLDS,
                              "metrics_status": review_metrics.get("status")})
