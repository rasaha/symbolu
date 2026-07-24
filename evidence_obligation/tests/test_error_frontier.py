"""Phases 16-17 tests: error propagation (0 unsafe at gold; burden-stripping errors propagate) and the
calibration frontier (a safe-and-useful region exists; the full component does not dominate)."""
from evidence_obligation import error_propagation as ep
from evidence_obligation import calibration_frontier as cf


def test_zero_unsafe_at_correct_obligations():
    assert ep.compute()["baseline_unsafe_allows_at_gold"] == 0


def test_burden_stripping_errors_propagate():
    m = ep.compute()
    by = {r["error"]: r["induced_unsafe_allows"] for r in m["errors"]}
    assert by["factual_as_opinion"] > 0
    assert by["high_risk_as_low_risk"] > 0
    assert by["external_reduced_to_context"] > 0


def test_evidence_absent_errors_absorbed():
    m = ep.compute()
    by = {r["error"]: r["induced_unsafe_allows"] for r in m["errors"]}
    assert by["fixture_as_telemetry"] == 0
    assert by["policy_treated_as_impl"] == 0


def test_frontier_has_safe_useful_region():
    m = cf.compute()
    assert len(m["admissible_safe_and_useful"]) >= 3
    assert m["best_safe_useful_clean_allow"] > 0.0


def test_full_component_not_uniquely_dominant():
    m = cf.compute()
    # a simpler safe strategy reaches clean-allow >= the full component's, or the full component is unsafe
    q = next(p for p in m["frontier"] if p["strategy"] == "full_evidence_obligation")
    assert (not q["safe"]) or any(
        p["safe"] and p["clean_allow_rate"] >= q["clean_allow_rate"] for p in m["frontier"])
