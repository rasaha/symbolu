"""Adapters translate providers onto frozen kernel ports (action/execution) +
the optional assertion linked-record projection."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from decision_governance.api.contracts import (
    AuthorizationOutcome as KAuth, BusinessOutcome as KBiz, TransportStatus as KT)
from decision_governance.api.ports import (
    ActionControlPlanePort, ExternalExecutionPort)
from governance_providers.adapters import (
    ActionGovernanceControlPlaneAdapter, AssertionAssessmentIntegration,
    ExternalExecutionAdapter)
from governance_providers.contracts import (
    AssertionCoverage, AssertionGovernanceRequest, ExecutionBusinessOutcome)
from governance_providers.reference import (
    DeterministicActionGovernanceProvider, DeterministicAssertionProvider,
    DeterministicExecutionProvider)


def _cer(expired=False):
    exp = datetime.now(timezone.utc) - timedelta(hours=1) if expired else None
    return SimpleNamespace(cer_id="cer-1", correlation_id="c", expires_at=exp,
                           policy_context=SimpleNamespace(policy_refs=()))


def _req(action_type="ACT"):
    return SimpleNamespace(action_type=action_type, requested_parameters={"k": "v"},
                           created_by="u", authority_ref="auth", target_system="SYS",
                           decision_id="d1", idempotency_key="", action_request_id="areq")


def test_action_adapter_conforms_and_maps():
    a = ActionGovernanceControlPlaneAdapter(
        DeterministicActionGovernanceProvider(denied=frozenset({"D"}), constrained=frozenset({"C"})))
    assert isinstance(a, ActionControlPlanePort)
    assert a.authorize(_req("ACT"), _cer()).outcome is KAuth.AUTHORIZED
    assert a.authorize(_req("D"), _cer()).outcome is KAuth.DENIED
    assert a.authorize(_req("C"), _cer()).outcome is KAuth.AUTHORIZED_WITH_CONSTRAINTS
    assert a.authorize(_req("ACT"), _cer(expired=True)).outcome is KAuth.EXPIRED


def test_action_adapter_normalizes_provider_failure():
    a = ActionGovernanceControlPlaneAdapter(DeterministicActionGovernanceProvider(unavailable=True))
    resp = a.authorize(_req("ACT"), _cer())
    # a vendor failure becomes a fail-safe INDETERMINATE, never a leaked exception
    assert resp.outcome is KAuth.INDETERMINATE
    assert any("provider_error" in rc for rc in resp.reason_codes)


def test_execution_adapter_conforms_and_maps():
    prov = DeterministicExecutionProvider(outcomes={"R": ExecutionBusinessOutcome.REJECTED})
    a = ExternalExecutionAdapter(prov)
    assert isinstance(a, ExternalExecutionPort)
    intent = SimpleNamespace(action_type="R", authorized_parameters={"k": "v"})
    disp = a.dispatch(intent)
    assert disp.transport_status is KT.ACKNOWLEDGED
    assert a.query_status(disp.external_request_id).business_outcome is KBiz.REJECTED


def test_assertion_integration_is_not_execution():
    """Assertion governance produces an assessment, never an execution dispatch."""
    integ = AssertionAssessmentIntegration(DeterministicAssertionProvider())
    a = integ.assess(AssertionGovernanceRequest(assertion="x", evidence_refs=("e1",)))
    assert a.coverage is AssertionCoverage.SUPPORTED and a.finalized
    # the integration exposes no dispatch/observe surface
    assert not hasattr(integ, "dispatch") and not hasattr(integ, "observe")


def test_assertion_optional_linked_record_projection():
    integ = AssertionAssessmentIntegration(DeterministicAssertionProvider(
        coverage=AssertionCoverage.CONSTRAINED))
    a = integ.assess(AssertionGovernanceRequest(assertion="x", evidence_refs=("e1",)))
    snap = integ.to_linked_record_snapshot(a, tenant_id="t", record_type="assertion",
                                            record_id="a1", subject_ref="s")
    assert snap.is_finalized and snap.is_blocked  # CONSTRAINED → finalized + blocked
    unsupported = integ.assess(AssertionGovernanceRequest(assertion="x"))
    unsupported2 = AssertionAssessmentIntegration(
        DeterministicAssertionProvider(coverage=AssertionCoverage.UNSUPPORTED)
    ).assess(AssertionGovernanceRequest(assertion="x"))
    snap2 = AssertionAssessmentIntegration.to_linked_record_snapshot(
        unsupported2, tenant_id="t", record_type="assertion", record_id="a2", subject_ref="s")
    assert not snap2.is_finalized  # UNSUPPORTED → kernel fails closed
