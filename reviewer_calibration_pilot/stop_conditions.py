"""Phase 12 - Pilot stop conditions.

Immediate stop conditions (any one halts the pilot instantly) and cumulative stop criteria (thresholds
frozen before outcome-bearing review). Fail-closed: an erroring check stops the pilot. Deterministic.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

# frozen cumulative thresholds (set before any outcome-bearing review)
FROZEN_THRESHOLDS = {
    "max_unsafe_allow_disagreement_rate": 0.02,      # reviewers flag system unsafe-allow
    "min_high_risk_obligation_agreement": 0.80,
    "max_reviewer_workload_per_hour": 40,            # artifacts/hour ceiling (excessive above)
    "max_unresolved_rate": 0.20,
    "max_stricter_override_rate": 0.40,
    "min_explanation_usefulness": 2.5,               # 1-5
    "max_missing_context_rate": 0.25,
}

_IMMEDIATE = [
    "enforcement_attempt", "external_action_execution", "unauthorized_data_exposure",
    "sensitive_data_leakage", "audit_failure", "reviewer_identity_leakage",
    "unrecorded_reviewer_override", "policy_drift", "component_drift", "kill_switch_failure",
    "native_actiongate_semantic_loss", "repeated_high_risk_unsafe_system_allow",
    "repeated_high_risk_reviewer_disagreement", "undeletable_pilot_data",
]


@dataclass
class StopResult:
    should_stop: bool
    immediate_fired: List[str] = field(default_factory=list)
    cumulative_fired: List[str] = field(default_factory=list)
    detail: Dict[str, Any] = field(default_factory=dict)


def check_immediate(signals: Dict[str, bool]) -> List[str]:
    """signals: {condition_name: bool}. Returns the immediate conditions that fired. Unknown/erroring ->
    treated as fired (fail-closed)."""
    fired = []
    for cond in _IMMEDIATE:
        try:
            if signals.get(cond, False):
                fired.append(cond)
        except Exception:
            fired.append(cond)      # fail-closed
    return fired


def check_cumulative(metrics: Dict[str, Any], thresholds: Dict[str, Any] = None) -> List[str]:
    """metrics from metrics.compute(). Returns cumulative criteria that breached the frozen thresholds.
    If metrics are NOT_ENOUGH_HUMAN_EVIDENCE, no cumulative criteria fire (there is nothing to breach)."""
    t = thresholds or FROZEN_THRESHOLDS
    if metrics.get("status") != "COMPUTED":
        return []
    fired = []
    ua = metrics.get("unsafe_allow_disagreement", 0)
    n = metrics.get("human_records", 1) or 1
    if ua / n > t["max_unsafe_allow_disagreement_rate"]:
        fired.append("unsafe_allow_disagreement_above_threshold")
    hr = metrics.get("high_risk_obligation_agreement")
    if hr is not None and hr < t["min_high_risk_obligation_agreement"]:
        fired.append("high_risk_agreement_below_threshold")
    if (metrics.get("unresolved_rate") or 0) > t["max_unresolved_rate"]:
        fired.append("unresolved_rate_excessive")
    if (metrics.get("stricter_override_rate") or 0) > t["max_stricter_override_rate"]:
        fired.append("stricter_override_rate_excessive")
    if (metrics.get("explanation_usefulness_mean") or 5) < t["min_explanation_usefulness"]:
        fired.append("explanation_usefulness_too_low")
    return fired


def evaluate(signals: Dict[str, bool], metrics: Dict[str, Any],
             thresholds: Dict[str, Any] = None) -> StopResult:
    imm = check_immediate(signals)
    cum = check_cumulative(metrics, thresholds)
    return StopResult(should_stop=bool(imm or cum), immediate_fired=imm, cumulative_fired=cum,
                      detail={"thresholds": thresholds or FROZEN_THRESHOLDS})
