"""M15 - Consolidated guarantee suite (Phase 21).

One place that asserts the non-negotiable constraints of the whole track hold together:
  G1  frozen prior artifacts untouched (45 guarded)
  G2  frozen minimal policy not modified (consumed read-only; still classifies)
  G3  human validation is NOT EVALUATED everywhere it could be claimed
  G4  simulated workflow can never produce a human-agreement number
  G5  blinding: the final set never exposes the system result; reveal is blocked before Stage A
  G6  native ActionGate 6 outcomes preserved, never collapsed
  G7  nothing enforces (enforced is always False; enforcement DISABLED in the freeze)
  G8  training and final sets disjoint; final excludes all prior source paths
  G9  downstream thresholds not lowered (stop-condition thresholds frozen; freeze forbids lowering)
"""
import pytest

from reviewer_ready_pilot import (dataset, verify_prior_artifacts, policy_runner, schema,
                                   simulated_workflow, metrics, stop_conditions,
                                   verify_evaluation_freeze)
from reviewer_ready_pilot.review_interface import BlindedReviewSession
from minimal_evidence_policy import classifier as mep


def test_g1_prior_artifacts_untouched():
    assert verify_prior_artifacts.verify() is True
    assert len(verify_prior_artifacts.FROZEN) == 45


def test_g2_frozen_policy_read_only_still_works():
    d = mep.classify({"artifact_id": "x", "text": "t", "risk_tier": "high",
                      "claim_family": "measured_performance"})
    assert d.final_obligation and d.policy_version == "minimal_evidence_policy_v1"


def test_g3_human_validation_not_evaluated():
    assert metrics.compute([])["human_validation"] == metrics.NOT_EVALUATED
    cfg = verify_evaluation_freeze.FUTURE_EVAL_CONFIG
    assert cfg["human_validation"] == "NOT_EVALUATED"
    assert cfg["production_readiness"] == "NOT_READY"
    assert cfg["external_customer_pilot"].startswith("BLOCKED")


def test_g4_simulation_never_yields_human_agreement():
    rep = simulated_workflow.run(dataset.load_final(), limit=25)
    assert rep["is_human_validation"] is False
    assert rep["metrics_on_real_records"]["status"] == metrics.STATUS_NO_HUMAN
    assert rep["metrics_on_real_records"]["reviewer_system_agreement"] == metrics.NOT_EVALUATED


def test_g5_blinding():
    final = dataset.load_final()
    for it in final:
        assert "gold_obligation" not in it
    s = BlindedReviewSession("REV-A", final[0])
    with pytest.raises(ValueError):
        s.reveal({"final_obligation": "E1"})   # cannot reveal before Stage A


def test_g6_actiongate_not_collapsed():
    assert set(policy_runner.NATIVE_ACTIONGATE_OUTCOMES) == set(schema.ACTIONGATE_OUTCOMES) - {"not_applicable"}
    bad = schema.StageBLabel(obligation="E3", acceptable_actiongate_outcome="allow")
    assert any("ActionGate" in x for x in schema.validate_stage_b(bad))


def test_g7_no_enforcement():
    r = policy_runner.run(dataset.load_final()[0])
    assert r.enforced is False
    assert verify_evaluation_freeze.FUTURE_EVAL_CONFIG["enforcement"] == "DISABLED"


def test_g8_sets_disjoint_and_prior_excluded():
    m = dataset.build()
    tr = {i["source_path"] for i in m["training"] if not i.get("synthetic")}
    fn = {i["source_path"] for i in m["final_review"] if not i.get("synthetic")}
    assert tr.isdisjoint(fn)
    prior = dataset._prior_paths()
    assert fn.isdisjoint(prior) and tr.isdisjoint(prior)


def test_g9_thresholds_not_lowered():
    # stop-condition thresholds are the frozen source of truth and the freeze forbids lowering
    assert stop_conditions.FROZEN_THRESHOLDS["min_trap_catch_rate"] >= 0.80
    assert stop_conditions.FROZEN_THRESHOLDS["min_reviewer_system_agreement_high_risk"] >= 0.80
    assert verify_evaluation_freeze.FUTURE_EVAL_CONFIG["no_threshold_lowering"] is True
