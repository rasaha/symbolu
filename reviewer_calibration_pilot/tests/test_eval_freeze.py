"""Phase 15 test: evaluation freeze verifies and locks the empty roster + NOT-EVALUATED external gate."""
from reviewer_calibration_pilot import verify_evaluation_freeze as vef


def test_eval_freeze_verifies():
    vef.freeze()
    assert vef.verify() is True


def test_roster_empty_and_external_blocked():
    cfg = vef.build_manifest()["eval_config"]
    assert cfg["reviewer_count"] == 0
    assert cfg["reviewer_roster"] == []
    assert cfg["human_validation"] == "NOT_EVALUATED"
    assert "BLOCKED" in cfg["external_pilot"]
    assert cfg["no_final_set_tuning"] is True
