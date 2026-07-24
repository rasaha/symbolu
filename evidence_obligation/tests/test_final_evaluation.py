"""Phase 23 test: final evaluation verifies guards, scores frozen criteria honestly (utility passes,
adversarial-safety and risk-only-dominance fail), and is deterministic."""
from evidence_obligation import final_evaluation as fe


def test_guards_intact():
    m = fe.run()
    assert m["guards"]["prior_artifacts_intact"] is True
    assert m["guards"]["evaluation_freeze_intact"] is True


def test_utility_criteria_pass():
    c = fe.run()["success_criteria"]
    assert c["clean_allow_materially_above_prior_zero"] is True
    assert c["over_qualification_materially_reduced"] is True
    assert c["no_high_risk_unsafe_allows"] is True


def test_honest_failures_recorded():
    c = fe.run()["success_criteria"]
    # the two falsification-signal criteria fail honestly
    assert c["no_adversarial_unsafe_allows"] is False
    assert c["improves_over_risk_only"] is False


def test_high_risk_subgroup_conservative():
    m = fe.run()
    hi = m["subgroups"]["by_risk_tier"].get("high")
    assert hi["clean_allow_rate"] < m["subgroups"]["by_risk_tier"]["low"]["clean_allow_rate"]
