"""Workflow state-machine + tenant-isolation tests (design §19, §26)."""
from __future__ import annotations

import pytest

from cg_helpers import (
    LOW_CLAIMS,
    T0,
    claim_inputs_for,
    drive_to_shadow_complete,
    make_evidence,
    make_payload,
    revision_of,
)
from ugence_code_governance import ClaimType, CodeGovernanceService, RiskTier
from ugence_code_governance.errors import (
    CrossTenantAccessError,
    InvalidWorkflowTransitionError,
)
from ugence_code_governance.models.enums import WorkflowState
from ugence_code_governance.workflow.state_machine import is_legal_transition


def test_state_machine_is_fail_closed():
    # An illegal transition is refused.
    assert not is_legal_transition(WorkflowState.RECEIVED, WorkflowState.SHADOW_COMPLETE)
    assert is_legal_transition(WorkflowState.RECEIVED, WorkflowState.IDENTITY_BOUND)
    # Terminal states have no successors.
    assert not is_legal_transition(WorkflowState.SHADOW_COMPLETE, WorkflowState.RECEIVED)


def test_full_forward_path_reaches_shadow_complete(service: CodeGovernanceService):
    change = service.ingest_change_event(make_payload(), tenant_id="acme",
                                         captured_at=T0, delivery_id="d")
    rid = drive_to_shadow_complete(service, change)
    assert service.get_workflow("acme", rid).state is WorkflowState.SHADOW_COMPLETE


def test_claims_incomplete_is_terminal_fail_closed(service: CodeGovernanceService):
    change = service.ingest_change_event(make_payload(), tenant_id="acme",
                                         captured_at=T0, delivery_id="d")
    rid = revision_of(change)
    # only BUILD -> mandatory incomplete
    service.record_evidence("acme", rid, make_evidence(change, ClaimType.BUILD))
    service.build_claim_manifest("acme", rid, risk_tier=RiskTier.LOW,
                                 claim_inputs=claim_inputs_for(change, (ClaimType.BUILD,)),
                                 captured_at=T0)
    ev = service.evaluate_claim_requirements("acme", rid, at=T0)
    assert not ev.proceed
    assert service.get_workflow("acme", rid).state is WorkflowState.CLAIMS_INCOMPLETE
    # cannot advance from a terminal state
    with pytest.raises(InvalidWorkflowTransitionError):
        service.evaluate_assertions("acme", rid, at=T0)


# --- tenant isolation (design §26) --------------------------------------
def test_cross_tenant_evidence_rejected(service: CodeGovernanceService):
    change = service.ingest_change_event(make_payload(), tenant_id="acme",
                                         captured_at=T0, delivery_id="d")
    rid = revision_of(change)
    foreign = make_evidence(change, ClaimType.BUILD)
    # evidence claiming a different tenant than the workflow
    import dataclasses
    foreign = dataclasses.replace(foreign, tenant_id="globex")
    with pytest.raises(CrossTenantAccessError):
        service.record_evidence("acme", rid, foreign)


def test_same_repo_pr_different_tenants_are_separate(service: CodeGovernanceService):
    a = service.ingest_change_event(make_payload(), tenant_id="acme", captured_at=T0, delivery_id="da")
    b = service.ingest_change_event(make_payload(), tenant_id="globex", captured_at=T0, delivery_id="db")
    assert a.fingerprint != b.fingerprint
    assert revision_of(a) != revision_of(b)


def test_cross_tenant_evidence_cannot_satisfy_other_tenant(service: CodeGovernanceService):
    a = service.ingest_change_event(make_payload(), tenant_id="acme", captured_at=T0, delivery_id="da")
    ev_a = make_evidence(a, ClaimType.BUILD)
    service.record_evidence("acme", revision_of(a), ev_a)
    # tenant globex cannot read acme's evidence
    assert service._evidence_repo.get("globex", ev_a.evidence_id) is None
    assert service._evidence_repo.get("acme", ev_a.evidence_id) is not None


def test_fingerprint_includes_tenant():
    from ugence_code_governance.github import normalize_pull_request_event
    a = normalize_pull_request_event(make_payload(), tenant_id="acme", captured_at=T0, delivery_id="d")
    b = normalize_pull_request_event(make_payload(), tenant_id="globex", captured_at=T0, delivery_id="d")
    assert a.fingerprint != b.fingerprint
