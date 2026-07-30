"""Operational-safety adapter — Autonomous Control Plane ("safe right now?").

The Autonomous Control Plane clears an already-authorized action against *live
operational state* and returns CLEAR / HOLD. The platform ships two runtimes of
the same discipline applied to two worlds: the physical ACP
(``symbolu_robotics.autonomous_control_plane``, which clears robot actions
against world state) and this digital sibling, which clears an enterprise action
(e.g. a Kubernetes write) against live infrastructure signals.

This is a deterministic, fail-closed gate: any required signal that is missing
holds the action rather than assuming it is safe. It never authorizes — ActionGate
already decided *whether* the action may run; ACP decides *whether now*.
"""

from __future__ import annotations

from ..models import ClearanceVerdict, OperationalSignals

# Thresholds for the Kubernetes / infrastructure-agent wedge.
_MIN_ERROR_BUDGET = 0.10          # hold if under 10% of the SLO error budget remains
_UNSAFE_HEALTH = {"red"}
_OK_HEALTH = {"green", "yellow"}


def available() -> tuple[bool, str]:
    return True, ""


def clear(signals: OperationalSignals) -> ClearanceVerdict:
    reasons: list[str] = []
    evaluated: dict[str, str] = {}

    # Change-freeze window (fail closed on missing).
    if signals.change_freeze_active is None:
        reasons.append("MISSING_change_freeze")
    else:
        evaluated["change_freeze_active"] = str(signals.change_freeze_active)
        if signals.change_freeze_active:
            reasons.append("CHANGE_FREEZE_ACTIVE")

    # Cluster health (fail closed on missing / unknown).
    if signals.cluster_health is None:
        reasons.append("MISSING_cluster_health")
    else:
        health = signals.cluster_health.lower()
        evaluated["cluster_health"] = health
        if health in _UNSAFE_HEALTH:
            reasons.append("CLUSTER_UNHEALTHY")
        elif health not in _OK_HEALTH:
            reasons.append("CLUSTER_HEALTH_UNKNOWN")

    # SLO error budget (fail closed on missing).
    if signals.error_budget_remaining is None:
        reasons.append("MISSING_error_budget")
    else:
        evaluated["error_budget_remaining"] = f"{signals.error_budget_remaining:.3f}"
        if signals.error_budget_remaining < _MIN_ERROR_BUDGET:
            reasons.append("ERROR_BUDGET_EXHAUSTED")

    disposition = "CLEAR" if not reasons else "HOLD"
    if disposition == "CLEAR":
        reasons = ["OPERATIONALLY_SAFE"]
    return ClearanceVerdict(disposition=disposition, reason_codes=reasons, evaluated=evaluated)
