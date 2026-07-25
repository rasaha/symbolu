"""Failure injection fail-safety (Task 111) and audit-trace completeness (Task 112)."""
from __future__ import annotations

import pytest

from enterprise_validation_pilot.datasets.build_dataset import build
from enterprise_validation_pilot.evaluators import run_failure_injection
from enterprise_validation_pilot.runners.trace import check_completeness
from enterprise_validation_pilot.runners.workflow import run_scenario

_INJECTIONS = run_failure_injection()


@pytest.mark.parametrize("inj", _INJECTIONS, ids=[i.injection for i in _INJECTIONS])
def test_injection_is_fail_safe(inj):
    assert inj.fail_safe, f"{inj.injection}: {inj.detail}"


def test_all_required_injections_present():
    names = {i.injection for i in _INJECTIONS}
    for required in ("tap_timeout", "tap_unavailable", "tap_malformed",
                     "actiongate_timeout", "actiongate_unavailable", "actiongate_malformed",
                     "execution_timeout", "execution_business_rejection",
                     "execution_transport_failure", "reconciliation_mismatch",
                     "missing_obligation_evidence", "registry_resolution_failure",
                     "incompatible_provider_version"):
        assert required in names, required


def test_every_workflow_produces_a_complete_trace():
    for s in build().ordered():
        r = run_scenario(s)
        comp = check_completeness(r.trace)
        assert comp.complete, (s.scenario_id, comp.missing)


def test_trace_carries_correlated_references():
    r = run_scenario(build().by_id("procurement-001"))
    for key in ("correlation_id", "case_id", "assessment_id", "recommendation_id",
                "decision_id", "authorization_id"):
        assert r.trace.get(key), key
    assert r.trace["recommendation_cites_assessment"] is True
