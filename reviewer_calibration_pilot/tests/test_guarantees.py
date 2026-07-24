"""Phase 23 - Consolidated guarantees: freeze, blinding, immutability, native ActionGate vocabulary,
non-enforcement, no external customer data, pseudonymization, no final-set tuning.
"""
from reviewer_calibration_pilot import (verify_prior_artifacts, dataset, review_interface as ri,
                                        policy_runner as pr, orchestrator as orch)


def test_no_frozen_component_modification():
    assert verify_prior_artifacts.verify() is True
    assert len(verify_prior_artifacts.FROZEN) == 59


def test_policy_version_frozen():
    for it in dataset.load_final()[:5]:
        assert pr.run(it).policy_version == "minimal_evidence_policy_v1"


def test_native_actiongate_vocabulary_preserved():
    valid = {"ALLOW", "ALLOW_WITH_CONSTRAINTS", "DENY", "ESCALATE_TO_HUMAN",
             "REQUEST_MORE_EVIDENCE", "SIMULATE_AND_RETRY", None}
    for it in dataset.load_final():
        assert pr.run(it).native_actiongate_outcome in valid


def test_reviewer_id_is_pseudonymous_only():
    # the interface stores only the reviewer_id string; no personal fields exist on the record
    rec = ri.ReviewRecord(artifact_id="a", reviewer_id="REV-A")
    fields = rec.__dict__.keys()
    assert not any(f in fields for f in ("name", "email", "employee_id", "real_name"))


def test_no_enforcement_anywhere():
    def a(b): return ri.ReviewerJudgment(obligation="E2")
    def b(bl, rv): return {"judgment": ri.ReviewerJudgment(obligation=rv["obligation"]),
                           "agreement": True, "override": False}
    lr = orch.process_artifact(dataset.load_final()[0], "MOCK", a, b, is_mock=True)
    assert lr.record.enforced is False
    assert pr.run(dataset.load_final()[0]).enforced is False


def test_no_final_set_tuning_final_has_no_gold():
    # the final set carries no reviewer gold -> it cannot be used to tune the policy
    for it in dataset.load_final():
        if not it.get("synthetic"):
            assert "gold_obligation" not in it


def test_training_final_separation():
    tr = {i["artifact_id"] for i in dataset.load_training()}
    fn = {i["artifact_id"] for i in dataset.load_final()}
    assert tr.isdisjoint(fn)
