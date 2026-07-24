"""Phases 18-19 tests: ablation identifies risk as load-bearing for safety; the complexity challenge
shows a simple comparator matches/beats the full component."""
from evidence_obligation import ablation


def test_risk_is_load_bearing_for_safety():
    m = ablation.compute()
    assert "risk" in m["load_bearing_for_safety"]
    # removing risk increases adversarial unsafe
    assert m["ablations"]["risk"]["adversarial_unsafe_allow"] > m["full_component"]["adversarial_unsafe_allow"]


def test_defensive_features_inert_on_this_data():
    m = ablation.compute()
    for feat in ("authority_guard", "risk_escalation", "structural_floors"):
        assert m["ablations"][feat]["adversarial_unsafe_delta"] == 0


def test_simple_comparator_matches_or_beats_full():
    m = ablation.compute()
    c = m["complexity_comparators"]
    simple = c["Simple1_risk_only"]
    full = c["Full_Q"]
    # simple risk-only: >= clean allow AND <= adversarial unsafe, at far fewer rules
    assert simple["clean_allow_rate"] >= full["clean_allow_rate"]
    assert simple["adversarial_unsafe_allow"] <= full["adversarial_unsafe_allow"]
    assert simple["approx_rule_count"] < full["approx_rule_count"]


def test_ablation_deterministic():
    import json, hashlib
    a = hashlib.sha256(json.dumps(ablation.compute()["ablations"], sort_keys=True).encode()).hexdigest()
    b = hashlib.sha256(json.dumps(ablation.compute()["ablations"], sort_keys=True).encode()).hexdigest()
    assert a == b
