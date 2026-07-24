"""Phase 22 test: the evaluation freeze verifies and locks the preregistered criteria."""
from evidence_obligation import verify_evaluation_freeze as vef


def test_eval_freeze_verifies():
    vef.freeze()
    assert vef.verify() is True


def test_criteria_frozen_and_score_once():
    cfg = vef.build_manifest()["eval_config"]
    assert cfg["score_once"] is True
    assert cfg["no_threshold_mutation_of_frozen_components"] is True
    assert "improves_over_risk_only_and_claim_type_only" in cfg["success_criteria"]
    assert "adversarial_unsafe_allow_nonzero" in cfg["kill_criteria"]
