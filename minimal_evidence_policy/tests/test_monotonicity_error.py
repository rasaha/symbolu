"""Phases 14-15 tests: exhaustive monotonicity (0 violations = no blocker); burden-stripping errors
propagate while evidence-absent errors are absorbed."""
from minimal_evidence_policy import monotonicity as mono, error_propagation as ep


def test_monotonicity_no_violations():
    m = mono.check()
    assert m["violations"] == 0
    assert m["monotonic"] is True
    assert m["blocker"] is False
    assert m["tested_transitions"] > 400


def test_burden_stripping_errors_propagate():
    by = {r["error"]: r["induced_unsafe_allows"] for r in ep.compute()["errors"]}
    assert by["risk_downgrade"] > 0
    assert by["factual_as_opinion"] > 0
    assert by["generated_as_evidence"] > 0


def test_some_errors_absorbed():
    by = {r["error"]: r["induced_unsafe_allows"] for r in ep.compute()["errors"]}
    assert by["attribution_as_truth"] == 0
    assert by["unknown_forced_internal"] == 0
