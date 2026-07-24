"""Phases 22-23 tests: null resolution and the evidence-gated decision (keep distinct stage; internal
pilot)."""
from minimal_evidence_policy import architectural_decision as ad


def test_nulls_resolved():
    m = ad.decide()
    assert m["nulls_total"] == 17
    assert m["nulls_rejected"] >= 10


def test_dimension_findings():
    d = ad.decide()["dimension_findings"]
    assert d["safe"] and d["useful"] and d["monotonic"] and d["within_budget"]
    assert d["claim_type_safety_critical"] is True
    assert d["human_validation_missing"] is True


def test_decision_keep_stage_and_internal_pilot():
    m = ad.decide()
    assert m["architectural_decision"].startswith("1 KEEP MINIMAL")
    assert m["pilot_decision"].startswith("B PROCEED TO INTERNAL")


def test_external_readiness_retained_blocked():
    n = ad.decide()["nulls"]
    assert n["H0-17_external_readiness_blocked"]["verdict"] == "RETAINED"
    assert n["H0-12_reviewers_cannot_agree"]["verdict"] == "NOT_EVALUATED"
