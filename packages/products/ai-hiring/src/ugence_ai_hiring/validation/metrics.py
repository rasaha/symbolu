"""Cohort metrics collectors (H5) — read-only descriptive statistics."""
from __future__ import annotations

from .lifecycle import CaseRun


def _rate(runs, pred):
    runs = list(runs)
    return round(sum(1 for r in runs if pred(r)) / len(runs), 4) if runs else 0.0


def cohort_metrics(runs: list[CaseRun]) -> dict:
    n = len(runs)
    decided = [r for r in runs if r.decision_id]
    acted = [r for r in runs if r.action_proposal_id]
    return {
        "cases": n,
        "review_ready_rate": _rate(runs, lambda r: r.recommendation_status == "READY_FOR_HUMAN_REVIEW"),
        "evidence_insufficiency_rate": _rate(runs, lambda r: r.reached_stage == "evidence_incomplete"),
        "assertion_review_required_rate": _rate(runs, lambda r: r.recommendation_status == "ASSERTION_REVIEW_REQUIRED"),
        "decision_rate": _rate(runs, lambda r: bool(r.decision_id)),
        "advancement_rate": _rate(decided, lambda r: r.decision_outcome == "ADVANCE"),
        "hold_rate": _rate(decided, lambda r: r.decision_outcome == "HOLD"),
        "reject_rate": _rate(decided, lambda r: r.decision_outcome == "REJECT"),
        "override_rate": _rate(decided, lambda r: r.override),
        "authorization_denial_rate": _rate(acted, lambda r: r.authorization_outcome == "DENIED"),
        "execution_failure_rate": _rate(acted, lambda r: r.proposal_status == "EXECUTION_FAILED"),
        "reconciliation_mismatch_rate": _rate(acted, lambda r: r.reconciliation_outcome in ("MISMATCHED", "DUPLICATE_EXECUTION")),
        "reconciled_rate": _rate(acted, lambda r: r.proposal_status in ("RECONCILED", "COMPENSATED")),
    }
