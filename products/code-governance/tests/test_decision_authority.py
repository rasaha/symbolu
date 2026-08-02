"""Acceptance tests 21-25: explicit authorized-actor decision recording."""
from __future__ import annotations

import pytest

from cg_helpers import (
    LOW_CLAIMS,
    T0,
    claim_inputs_for,
    make_evidence,
    make_payload,
    revision_of,
)
from ugence_code_governance import (
    AuthorizedActor,
    CodeGovernanceService,
    DecisionAuthorityRequiredError,
    DecisionInput,
    GovernanceRecommendation,
    RiskTier,
)


def _to_assertions(service, *, head_sha="head-sha-1", delivery="d"):
    change = service.ingest_change_event(make_payload(head_sha=head_sha), tenant_id="acme",
                                         captured_at=T0, delivery_id=delivery)
    rid = revision_of(change)
    for ct in LOW_CLAIMS:
        service.record_evidence("acme", rid, make_evidence(change, ct))
    service.build_claim_manifest("acme", rid, risk_tier=RiskTier.LOW,
                                 claim_inputs=claim_inputs_for(change, LOW_CLAIMS), captured_at=T0)
    service.evaluate_claim_requirements("acme", rid, at=T0)
    service.evaluate_assertions("acme", rid, at=T0)
    rec = service.create_recommendation("acme", rid, created_at=T0)
    return change, rid, rec


_ACTOR = AuthorizedActor(actor_id="user:jane", authority_id="role:code-approver",
                         decision_scope="merge_pull_request")


# 21. workflow cannot create binding decision without explicit actor input
def test_decision_requires_explicit_actor(service: CodeGovernanceService):
    change, rid, _ = _to_assertions(service)
    with pytest.raises(DecisionAuthorityRequiredError):
        service.record_authorized_decision(
            "acme", rid, actor=None, decision=DecisionInput(outcome="APPROVE"), at=T0)
    assert service.get_workflow("acme", rid).state.value == "DECISION_REQUIRED"


# 22. recommendation is not a DecisionRecord
def test_recommendation_is_not_a_decision_record(service: CodeGovernanceService):
    change, rid, rec = _to_assertions(service)
    assert isinstance(rec, GovernanceRecommendation)
    assert rec.is_binding is False
    # It has no decision-authority identity fields.
    assert not hasattr(rec, "authority_type")
    assert not hasattr(rec, "outcome")


# 23. valid explicit decision creates/reuses DecisionRecord through public API
def test_valid_decision_creates_decision_record(service: CodeGovernanceService):
    change, rid, _ = _to_assertions(service)
    record = service.record_authorized_decision(
        "acme", rid, actor=_ACTOR, decision=DecisionInput(outcome="APPROVE"), at=T0)
    # Reused upstream DecisionRecord — not a product-specific merge decision type.
    assert type(record).__name__ == "DecisionRecord"
    assert record.tenant_id == "acme"
    assert record.decided_by == "user:jane"
    assert service.get_workflow("acme", rid).state.value == "DECISION_RECORDED"


# 24. tenant mismatch fails
def test_decision_tenant_isolation(service: CodeGovernanceService):
    change, rid, _ = _to_assertions(service)
    # a decision recorded under acme is bound to tenant acme
    record = service.record_authorized_decision(
        "acme", rid, actor=_ACTOR, decision=DecisionInput(outcome="APPROVE"), at=T0)
    assert record.tenant_id == "acme"
    # a different tenant has no run for this revision
    from ugence_code_governance.errors import RecordNotFoundError
    with pytest.raises(RecordNotFoundError):
        service.record_authorized_decision(
            "globex", rid, actor=_ACTOR, decision=DecisionInput(outcome="APPROVE"), at=T0)


# 25. decision bound to old head cannot authorize new revision
def test_decision_bound_to_old_head_does_not_authorize_new_revision(service: CodeGovernanceService):
    change_a, rid_a, _ = _to_assertions(service, head_sha="head-A", delivery="dA")
    rec_a = service.record_authorized_decision(
        "acme", rid_a, actor=_ACTOR, decision=DecisionInput(outcome="APPROVE"), at=T0)
    # new head -> new revision, different decision required
    change_b, rid_b, _ = _to_assertions(service, head_sha="head-B", delivery="dB")
    assert rid_a != rid_b
    # the new revision has its own workflow with no decision yet
    wf_b = service.get_workflow("acme", rid_b)
    assert wf_b.decision_record_id is None
    rec_b = service.record_authorized_decision(
        "acme", rid_b, actor=_ACTOR, decision=DecisionInput(outcome="APPROVE"), at=T0)
    assert rec_b.decision_id != rec_a.decision_id


def test_denied_decision_blocks_workflow(service: CodeGovernanceService):
    change, rid, _ = _to_assertions(service)
    service.record_authorized_decision(
        "acme", rid, actor=_ACTOR, decision=DecisionInput(outcome="DENY"), at=T0)
    assert service.get_workflow("acme", rid).state.value == "BLOCKED"
