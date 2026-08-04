"""Stale-state and HPA-interaction classification coverage."""
from __future__ import annotations

from shadow_validation.contracts import StaleClassification, HpaInteraction
from shadow_validation.evidence import run_stale_state_cases, run_hpa_cases


def test_stale_state_all_classifications_and_correct():
    res = run_stale_state_cases()
    assert res["all_ok"] is True
    produced = {c["classification"] for c in res["cases"]}
    expected = {c.value for c in StaleClassification}
    assert expected.issubset(produced), expected - produced
    # Only FRESH is actionable.
    for c in res["cases"]:
        assert c["actionable"] == (c["classification"] == StaleClassification.FRESH.value)


def test_hpa_all_classifications_and_correct():
    res = run_hpa_cases()
    assert res["all_ok"] is True
    produced = set(res["classifications_present"])
    for required in (HpaInteraction.NO_HPA, HpaInteraction.HPA_OBSERVED_COMPATIBLE,
                     HpaInteraction.HPA_BOUNDS_CONFLICT, HpaInteraction.HPA_OBSERVED_CONFLICT,
                     HpaInteraction.HPA_STATE_INCOMPLETE):
        assert required.value in produced


def test_bounds_and_direction_conflicts_flag_contention():
    res = run_hpa_cases()
    by = {c["case"]: c for c in res["cases"]}
    assert by["bounds_conflict"]["contention_risk"] is True
    assert by["direction_conflict"]["contention_risk"] is True
    assert by["compatible"]["contention_risk"] is False
