"""M16 tests - readiness assessment (Phase 22)."""
from reviewer_ready_pilot import readiness as rd


def test_assessment_is_reviewer_ready():
    r = rd.assess()
    assert r.decision == rd.D_READY
    assert all(d.passed for d in r.dimensions)


def test_never_claims_human_validation():
    r = rd.assess()
    assert r.human_validation == "NOT_EVALUATED"
    assert r.external_customer_pilot == "BLOCKED"
    assert r.production_readiness == "NOT_READY"
    # the ready decision is about the apparatus, and says nothing about human agreement
    assert "human" not in r.decision.lower() or "waiting" in r.decision.lower()


def test_decision_is_one_of_eight():
    eight = {rd.D_READY, rd.D_WORKFLOW, rd.D_REVIEW_SET, rd.D_GUIDE, rd.D_METADATA, rd.D_ARTIFACTS,
             rd.D_PILOT, rd.D_STOP}
    assert rd.assess().decision in eight


def test_first_failing_dimension_selects_decision(monkeypatch):
    # force the review-set audit to fail and confirm the decision points at the review set
    import reviewer_ready_pilot.review_set_audit as rsa
    bad = rsa.AuditReport(status="REVIEW_SET_NEEDS_IMPROVEMENT", checks=[], stats={})
    monkeypatch.setattr(rd.review_set_audit, "audit", lambda: bad)
    r = rd.assess()
    assert r.decision == rd.D_REVIEW_SET


def test_serializable():
    d = rd.assess().as_dict()
    assert d["decision"] and "dimensions" in d and d["human_validation"] == "NOT_EVALUATED"
