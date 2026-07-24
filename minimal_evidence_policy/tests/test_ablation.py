"""Phases 17-18 tests: risk_floor and claim_type are safety-critical; a 12-rule MVP reaches 0 unsafe;
rich component remains unsafe."""
from minimal_evidence_policy import ablation


def test_safety_critical_elements():
    m = ablation.compute()
    assert "risk_floor" in m["safety_critical_elements"]
    assert "claim_type" in m["safety_critical_elements"]


def test_minimum_viable_safe_policy_smaller_than_full():
    m = ablation.compute()
    mvp = m["minimum_viable_safe_policy"]
    c = m["complexity_comparators"][mvp]
    assert c["held_unsafe_allow"] == 0 and c["adversarial_unsafe_allow"] == 0
    assert c["approx_rules"] <= m["complexity_comparators"]["full_minimal"]["approx_rules"]


def test_rich_component_unsafe():
    m = ablation.compute()
    r = m["complexity_comparators"]["rich_component"]
    assert (r["held_unsafe_allow"] + r["adversarial_unsafe_allow"]) > 0
