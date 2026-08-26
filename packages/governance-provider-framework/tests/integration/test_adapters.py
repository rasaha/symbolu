"""Adapters translate providers onto frozen kernel ports (action/execution) +
the optional assertion linked-record projection."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from decision_governance.api.contracts import (
    AuthorizationOutcome as KAuth, BusinessOutcome as KBiz, TransportStatus as KT)
from decision_governance.api.ports import (
    ActionControlPlanePort, ExternalExecutionPort)
from ugence_governance_provider_framework.adapters import (
    ActionGovernanceControlPlaneAdapter, AssertionAssessmentIntegration,
    ExternalExecutionAdapter)
from ugence_governance_provider_framework.contracts import (
    AssertionCoverage, AssertionGovernanceRequest, ExecutionBusinessOutcome)
from ugence_governance_provider_framework.reference import (
    DeterministicActionGovernanceProvider, DeterministicAssertionProvider,
    DeterministicExecutionProvider)


def _cer(expired=False, expires_at=None):
    exp = expires_at if expires_at is not None else (
        datetime.now(timezone.utc) - timedelta(hours=1) if expired else None)
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


def test_action_adapter_treats_the_expiry_instant_itself_as_expired():
    """The boundary instant is expired, not the last valid tick.

    The adapter previously read ``expires_at < now``, which authorizes at the
    instant a CER expires. ``ugence_action_clearance`` uses the inclusive form
    (``evaluation_time >= expires_at``) in both places it evaluates validity, so
    the exclusive form left a one-instant window in which authorization and
    clearance disagreed about whether the same CER was live. Neither this file
    nor any other test in this package pinned the boundary instant, so the
    disagreement was invisible here.

    The adapter cannot call ``ugence_actiongate_provider.vnext.is_expired``,
    which states the same rule: the framework does not depend on a provider, and
    inverting that direction to share four lines would be the worse trade. The
    rule is therefore written twice, and this test is what keeps the two copies
    honest from the framework's side.
    """
    instant = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    a = ActionGovernanceControlPlaneAdapter(
        DeterministicActionGovernanceProvider(), clock=lambda: instant)

    # now == expires_at: expired. Under `expires_at < now` this authorized.
    assert a.authorize(_req("ACT"), _cer(expires_at=instant)).outcome is KAuth.EXPIRED
    # One microsecond earlier: still expired, and was under either form.
    assert a.authorize(
        _req("ACT"),
        _cer(expires_at=instant - timedelta(microseconds=1))).outcome is KAuth.EXPIRED
    # One microsecond later: live, and must stay live — the inclusive boundary
    # retires the expiry instant itself, not the instant before it.
    assert a.authorize(
        _req("ACT"),
        _cer(expires_at=instant + timedelta(microseconds=1))).outcome is KAuth.AUTHORIZED
    # No declared expiry never expires.
    assert a.authorize(_req("ACT"), _cer()).outcome is KAuth.AUTHORIZED


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
