"""Adapters translate providers onto the frozen kernel ports."""
from __future__ import annotations

from types import SimpleNamespace

from decision_governance.api.ports import (
    ActionControlPlanePort, ExternalExecutionPort, LinkedRecordPort)
from decision_governance_provider.adapters import (
    AssertionProviderLinkedRecordAdapter,
    AuthorizationProviderControlPlaneAdapter,
    ExecutionProviderExternalSystemAdapter)
from decision_governance_provider.contracts import BusinessOutcome
from decision_governance_provider.mock import (
    MockAssertionProvider, MockAuthorizationProvider, MockExecutionProvider)


def test_adapters_conform_to_kernel_ports():
    assert isinstance(AssertionProviderLinkedRecordAdapter(MockAssertionProvider()), LinkedRecordPort)
    assert isinstance(AuthorizationProviderControlPlaneAdapter(MockAuthorizationProvider()), ActionControlPlanePort)
    assert isinstance(ExecutionProviderExternalSystemAdapter(MockExecutionProvider()), ExternalExecutionPort)


def test_assertion_adapter_maps_snapshot():
    a = AssertionProviderLinkedRecordAdapter(MockAssertionProvider(subject_ref="s1"))
    snap = a.get_record(tenant_id="t", record_type="assessment", record_id="x")
    assert snap is not None and snap.is_finalized and snap.subject_ref == "s1"
    # not found → None (kernel fails closed)
    a2 = AssertionProviderLinkedRecordAdapter(MockAssertionProvider(found=False))
    assert a2.get_record(tenant_id="t", record_type="a", record_id="x") is None
    # blocked flag propagates
    a3 = AssertionProviderLinkedRecordAdapter(MockAssertionProvider(blocked=True))
    assert a3.get_record(tenant_id="t", record_type="a", record_id="x").is_blocked


def _fake_request(action_type="ACT", params=None):
    return SimpleNamespace(
        action_type=action_type, requested_parameters=params or {"amount": "10"},
        tenant_id="t", subject_refs=(), action_request_id="areq-1")


def _fake_cer(expired=False):
    from datetime import datetime, timedelta, timezone
    exp = datetime.now(timezone.utc) - timedelta(hours=1) if expired else None
    policy_ctx = SimpleNamespace(policy_refs=())
    return SimpleNamespace(cer_id="cer-1", correlation_id="corr-1",
                           policy_context=policy_ctx, expires_at=exp)


def test_authorization_adapter_maps_outcomes():
    from decision_governance.api.contracts import AuthorizationOutcome as K
    a = AuthorizationProviderControlPlaneAdapter(
        MockAuthorizationProvider(denied=frozenset({"D"}), constrained=frozenset({"C"})))
    assert a.authorize(_fake_request("OK"), _fake_cer()).outcome is K.AUTHORIZED
    assert a.authorize(_fake_request("D"), _fake_cer()).outcome is K.DENIED
    assert a.authorize(_fake_request("C"), _fake_cer()).outcome is K.AUTHORIZED_WITH_CONSTRAINTS
    assert a.authorize(_fake_request("OK"), _fake_cer(expired=True)).outcome is K.EXPIRED


def test_execution_adapter_maps_dispatch_and_status():
    from decision_governance.api.contracts import (
        BusinessOutcome as KB, TransportStatus as KT)
    prov = MockExecutionProvider(outcomes={"R": BusinessOutcome.REJECTED})
    a = ExecutionProviderExternalSystemAdapter(prov)
    intent = SimpleNamespace(action_type="R", authorized_parameters={"k": "v"})
    disp = a.dispatch(intent)
    assert disp.transport_status is KT.ACKNOWLEDGED and disp.external_request_id
    obs = a.query_status(disp.external_request_id)
    assert obs.business_outcome is KB.REJECTED
