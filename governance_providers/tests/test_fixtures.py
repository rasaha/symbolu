"""Neutral integration fixtures: action→reconciled, assertion→recommendation."""
from __future__ import annotations

from decision_governance.api.audit import audit_namespace, AuditNamespace
from governance_providers.adapters import (
    ActionGovernanceControlPlaneAdapter, AssertionAssessmentIntegration,
    AssertionLinkedRecordAdapter)
from governance_providers.contracts import AssertionGovernanceRequest
from governance_providers.reference import (
    DeterministicActionGovernanceProvider, DeterministicAssertionProvider)

from .conftest import run_kernel_action_lifecycle


def _assertion_linked_record():
    integ = AssertionAssessmentIntegration(DeterministicAssertionProvider())
    assessment = integ.assess(AssertionGovernanceRequest(
        assertion="subject qualifies", assertion_type="claim", evidence_refs=("ev1",)))
    snap = integ.to_linked_record_snapshot(
        assessment, tenant_id="t", record_type="assertion", record_id="a1", subject_ref="subject")
    linked = AssertionLinkedRecordAdapter(); linked.register("a1", snap)
    return linked, assessment


def test_action_provider_drives_kernel_to_reconciled():
    control_plane = ActionGovernanceControlPlaneAdapter(DeterministicActionGovernanceProvider())
    linked, _ = _assertion_linked_record()
    status, events, resp = run_kernel_action_lifecycle(
        control_plane=control_plane, linked_record=linked)
    assert resp.outcome.value == "AUTHORIZED"
    assert status == "RECONCILED"
    assert events and all(audit_namespace(e) is AuditNamespace.KERNEL for e in events)


def test_assertion_feeds_assessment_not_execution():
    """Evidence + assertion → assertion provider → assessment → linked record
    consumed by the case (recommendation/decision), never through execution."""
    linked, assessment = _assertion_linked_record()
    assert assessment.finalized and assessment.provider_trace_id
    snap = linked.get_record(tenant_id="t", record_type="assertion", record_id="a1")
    assert snap is not None and snap.is_finalized
    # evidence coverage is carried as neutral metadata, not a business action
    assert "evidence_coverage" in snap.metadata
