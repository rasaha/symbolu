"""Phase 20 test: evaluation freeze verifies and locks the criteria + NOT-EVALUATED external gate."""
from minimal_evidence_policy import verify_evaluation_freeze as vef


def test_eval_freeze_verifies():
    vef.freeze()
    assert vef.verify() is True


def test_external_pilot_blocked_and_score_once():
    cfg = vef.build_manifest()["eval_config"]
    assert cfg["human_validation"] == "NOT_EVALUATED"
    assert "BLOCKED" in cfg["external_pilot"]
    assert cfg["score_once"] is True
