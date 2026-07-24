"""Phase 17-18 tests: preregistered nulls resolve as expected (including the adversarial derivation-
sensitivity probe), and the eval freeze manifest verifies against the frozen artifacts.
"""
from bounded_shadow_pilot import falsification as fx
from bounded_shadow_pilot import eval_freeze


def test_all_preregistered_nulls_rejected():
    m = fx.run()
    assert m["nulls_rejected"] == m["nulls_total"]
    by_id = {x["null_id"]: x for x in m["preregistered_nulls"]}
    assert by_id["H0_SAFETY_UNSAFE_PERMIT"]["null_rejected"] is True
    assert by_id["H0_ACTIONGATE_SEMANTIC_LOSS"]["null_rejected"] is True
    assert by_id["H0_INSUFFICIENT_EVIDENCE"]["null_rejected"] is True


def test_derivation_sensitivity_confirms_evidence_driven():
    m = fx.run()
    p = m["derivation_sensitivity_probe"]
    # honest base near-zero clean allow; optimistic base restores it -> finding is evidence-driven
    assert p["clean_allow_rate_honest_base"] < 0.05
    assert p["clean_allow_rate_optimistic_base"] > p["clean_allow_rate_honest_base"]
    assert p["over_qualification_is_derivation_dependent"] is True


def test_eval_freeze_verifies():
    eval_freeze.freeze()
    assert eval_freeze.verify() is True


def test_eval_config_disallows_final_set_tuning():
    m = eval_freeze.build_manifest()
    assert m["eval_config"]["threshold_tuning_on_final_set"] is False
    assert m["eval_config"]["score_once"] is True
