"""H5 — determinism & reproducibility (normalized comparison)."""
from __future__ import annotations

from ugence_governance_provider_framework.contracts import AssertionCoverage

from ugence_ai_hiring.validation import CaseSpec, build_validation_env, run_lifecycle


def _norm(r):
    return (r.reached_stage, r.recommendation_status, r.recommendation_outcome, r.decision_outcome,
            r.override, r.authorization_outcome, r.execution_status, r.proposal_status,
            r.reconciliation_outcome, r.package_fingerprint)


def test_identical_inputs_produce_identical_normalized_outputs():
    a = run_lifecycle(build_validation_env(), CaseSpec(case_id="d1"))
    b = run_lifecycle(build_validation_env(), CaseSpec(case_id="d1"))
    assert _norm(a) == _norm(b)


def test_package_fingerprint_stable():
    a = run_lifecycle(build_validation_env(), CaseSpec(case_id="d2"))
    b = run_lifecycle(build_validation_env(), CaseSpec(case_id="d2"))
    assert a.package_fingerprint == b.package_fingerprint and a.package_fingerprint


def test_variation_changes_outputs_predictably():
    ok = run_lifecycle(build_validation_env(), CaseSpec(case_id="d3"))
    bad = run_lifecycle(build_validation_env(), CaseSpec(case_id="d3", assertion_coverage=AssertionCoverage.UNSUPPORTED))
    assert ok.recommendation_status != bad.recommendation_status
