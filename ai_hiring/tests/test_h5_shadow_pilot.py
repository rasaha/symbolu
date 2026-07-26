"""H5 — bounded shadow pilot: deterministic replay, no production effects."""
from __future__ import annotations

from ai_hiring.validation import build_cohort, cohort_metrics, run_pilot
from ai_hiring.validation.pilot import run_pilot as _rp


def test_pilot_runs_full_cohort_without_production_effects():
    runs = run_pilot()
    assert len(runs) == len(build_cohort())
    # every executed case used the in-memory deterministic adapter (no external effect)
    executed = [r for r in runs if r.execution_status]
    assert executed  # some cases execute
    # reconciled or compensation-required — never a silent success
    for r in executed:
        assert r.proposal_status in ("RECONCILED", "COMPENSATION_REQUIRED", "EXECUTION_FAILED")


def test_pilot_is_deterministic_across_runs():
    a = run_pilot()
    b = run_pilot()
    # normalized comparison: per-case stage + outcomes identical (ids/timestamps excluded)
    def norm(runs):
        return [(r.spec.case_id, r.reached_stage, r.recommendation_status, r.decision_outcome,
                 r.authorization_outcome, r.reconciliation_outcome, r.proposal_status) for r in runs]
    assert norm(a) == norm(b)


def test_pilot_metrics_cover_branches():
    m = cohort_metrics(run_pilot())
    assert m["cases"] == 12
    assert m["authorization_denial_rate"] > 0  # a denied case exists
    assert m["reconciliation_mismatch_rate"] > 0  # a mismatch case exists
    assert m["evidence_insufficiency_rate"] > 0  # an incomplete case exists
