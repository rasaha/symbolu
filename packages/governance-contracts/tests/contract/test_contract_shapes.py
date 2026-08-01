"""C3 — contract shape stability (fields, defaults, enum values, protocols).

Locks the field sets, defaults, and enum members of the neutral contracts so any
accidental field/enum change during a future edit fails loudly.
"""

from __future__ import annotations

import dataclasses

import ugence_governance_contracts as A


def _fields(cls):
    return {f.name: (f.default is not dataclasses.MISSING
                     or f.default_factory is not dataclasses.MISSING)  # has default
            for f in dataclasses.fields(cls)}


def test_action_request_fields():
    f = _fields(A.ActionGovernanceRequest)
    assert set(f) == {
        "action_type", "requested_parameters", "actor", "authority_context",
        "target_resource", "policy_refs", "risk_context", "evidence_refs",
        "decision_refs", "idempotency_key", "correlation_id", "authorization_expired"}
    assert f["action_type"] is False  # required
    assert all(v for k, v in f.items() if k != "action_type")  # rest optional


def test_assertion_result_fields_and_property():
    f = _fields(A.AssertionGovernanceResult)
    assert "coverage" in f and f["coverage"] is False
    r = A.AssertionGovernanceResult(coverage=A.AssertionCoverage.SUPPORTED)
    assert r.is_supported is True
    assert A.AssertionGovernanceResult(coverage=A.AssertionCoverage.UNSUPPORTED).is_supported is False


def test_enum_values():
    assert [m.value for m in A.ActionGovernanceOutcome] == [
        "AUTHORIZED", "AUTHORIZED_WITH_CONSTRAINTS", "DENIED", "INDETERMINATE", "EXPIRED"]
    assert [m.value for m in A.AssertionCoverage] == [
        "SUPPORTED", "UNSUPPORTED", "INDETERMINATE", "CONSTRAINED"]
    assert [m.value for m in A.ExecutionBusinessOutcome] == [
        "SUCCEEDED", "FAILED", "REJECTED", "PENDING", "DUPLICATE", "UNKNOWN"]
    assert [m.value for m in A.ProviderKind] == [
        "ASSERTION_GOVERNANCE", "ACTION_GOVERNANCE", "EXTERNAL_EXECUTION"]
    assert [m.value for m in A.ProviderLifecycleState] == [
        "REGISTERED", "INITIALIZING", "AVAILABLE", "DEGRADED", "UNAVAILABLE",
        "STOPPING", "STOPPED"]


def test_provider_protocols_are_runtime_checkable():
    for P in (A.Provider, A.ActionGovernanceProvider, A.AssertionGovernanceProvider,
              A.ExternalExecutionProvider):
        assert getattr(P, "_is_protocol", False), P


def test_lifecycle_transition_rules_unchanged():
    S = A.ProviderLifecycleState
    assert A.is_legal_transition(S.AVAILABLE, S.DEGRADED)
    assert A.is_legal_transition(S.DEGRADED, S.AVAILABLE)
    assert not A.is_legal_transition(S.STOPPED, S.AVAILABLE)
    assert not A.is_legal_transition(S.REGISTERED, S.AVAILABLE)
