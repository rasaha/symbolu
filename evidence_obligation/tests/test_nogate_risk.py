"""Phases 13-14 tests: the no-gate class is never assigned to high-risk/factual claims (pilot blocker),
and risk escalation resolves upward / never lowers."""
from evidence_obligation import no_evidence_gate as ng
from evidence_obligation import risk as risk_mod
from evidence_obligation import schema as s, classifier


def test_no_high_risk_factual_no_gate_blocker_false():
    m = ng.validate()
    assert m["high_risk_or_factual_no_gate_violations"] == 0
    assert m["blocker"] is False


def test_no_gate_eligibility_fail_closed():
    assert ng.eligible_for_no_gate("I prefer tabs over spaces.", "low") is True
    assert ng.eligible_for_no_gate("In my opinion the drug cures the patient.", "low") is False  # factual leak
    assert ng.eligible_for_no_gate("I think this is fine.", "high") is False                      # high risk


def test_risk_resolves_upward():
    assert risk_mod.assess_risk("deploy to production now", "code_behavior",
                                actionability="action_directive")[0] == "high"
    assert risk_mod.assess_risk("this bypasses the credential check", "process_description")[0] == "high"


def test_escalation_never_lowers():
    # a high-risk code_behavior escalates to a stronger obligation, never weaker
    base = s.IMPLEMENTATION_EVIDENCE_SUFFICIENT
    out, _ = risk_mod.escalate_obligation(base, "high", "code_behavior")
    from evidence_obligation import ground_truth as gt
    assert gt._RANK[out] >= gt._RANK[base]


def test_classifier_high_risk_medical_not_no_gate():
    o = classifier.classify({"artifact_id": "x", "source_path": "d.md", "source_kind": "doc",
                             "text": "In my opinion this drug completely cures the patient."})
    assert o.evidence_obligation_type != s.NO_FACTUAL_EVIDENCE_GATE
