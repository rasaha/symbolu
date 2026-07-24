"""M14 tests - future human-evaluation protocol freeze (Phase 20)."""
from reviewer_ready_pilot import verify_evaluation_freeze as vf


def test_freeze_then_verify_ok():
    vf.freeze()
    assert vf.verify() is True


def test_manifest_pins_data_and_config():
    m = vf.build_manifest()
    assert m["n_artifacts"] == len(vf.FROZEN_ARTIFACTS)
    assert m["config_sha256"] and m["manifest_sha256"]
    for rel, h in m["artifact_sha256"].items():
        assert h is not None, rel


def test_honesty_invariants_present():
    c = vf.FUTURE_EVAL_CONFIG
    assert c["human_validation"] == "NOT_EVALUATED"
    assert c["production_readiness"] == "NOT_READY"
    assert c["external_customer_pilot"].startswith("BLOCKED")
    assert c["policy_modified"] is False
    assert c["enforcement"] == "DISABLED"
    assert c["reviewer_count"] == 0 and c["reviewer_roster"] == []
    assert c["no_threshold_lowering"] is True and c["no_final_set_tuning"] is True


def test_actiongate_vocabulary_not_collapsed():
    assert set(vf.FUTURE_EVAL_CONFIG["native_actiongate_outcomes"]) == {
        "ALLOW", "ALLOW_WITH_CONSTRAINTS", "DENY", "ESCALATE_TO_HUMAN",
        "REQUEST_MORE_EVIDENCE", "SIMULATE_AND_RETRY"}
