"""Phases 8-9 tests: frozen policy runner (read-only, native ActionGate preserved, non-enforcing,
replayable) and orchestrator (blinded->run->reveal linkage, mock flagged, no enforcement)."""
from reviewer_calibration_pilot import policy_runner as pr, orchestrator as orch, review_interface as ri, dataset as d


def test_runner_non_enforcing_replayable():
    for it in d.load_final()[:20]:
        r = pr.run(it)
        assert r.enforced is False
        assert r.replay_signature
        assert r.policy_version == "minimal_evidence_policy_v1"


def test_runner_preserves_native_actiongate_vocabulary():
    native = {pr.run(it).native_actiongate_outcome for it in d.load_final() if pr.run(it).action_present}
    valid = {"ALLOW", "ALLOW_WITH_CONSTRAINTS", "DENY", "ESCALATE_TO_HUMAN",
             "REQUEST_MORE_EVIDENCE", "SIMULATE_AND_RETRY", None}
    assert native <= valid


def test_runner_deterministic():
    it = d.load_final()[0]
    assert pr.run(it).replay_signature == pr.run(it).replay_signature


def test_orchestrator_blinded_then_reveal_no_enforcement():
    def a(blinded):
        assert "obligation" not in blinded          # blinded: no system result
        return ri.ReviewerJudgment(obligation="E2")
    def b(blinded, reveal):
        assert "obligation" in reveal               # revealed after Stage A
        return {"judgment": ri.ReviewerJudgment(obligation=reveal["obligation"]),
                "agreement": True, "override": False}
    lr = orch.process_artifact(d.load_final()[0], "MOCK", a, b, is_mock=True)
    assert lr.is_mock is True
    assert lr.record.enforced is False
