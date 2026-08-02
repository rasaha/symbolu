"""Provider lifecycle transitions, error taxonomy, and observability records."""
from __future__ import annotations

import pytest

from ugence_governance_provider_framework.lifecycle import (
    ProviderLifecycleState, is_legal_transition)
from ugence_governance_provider_framework.errors import (
    FailureClass, ProviderError, ProviderTimeoutError, ProviderUnavailableError)
from ugence_governance_provider_framework.observability import (
    ProviderInvocationLog, record_invocation)
from ugence_governance_provider_framework.reference import DeterministicActionGovernanceProvider
from ugence_governance_provider_framework.contracts import ActionGovernanceRequest


def test_legal_and_illegal_transitions():
    S = ProviderLifecycleState
    assert is_legal_transition(S.REGISTERED, S.INITIALIZING)
    assert is_legal_transition(S.AVAILABLE, S.DEGRADED)
    assert not is_legal_transition(S.STOPPED, S.AVAILABLE)
    assert not is_legal_transition(S.REGISTERED, S.AVAILABLE)


def test_provider_lifecycle_flow():
    p = DeterministicActionGovernanceProvider()
    assert p.state is ProviderLifecycleState.REGISTERED
    p.initialize()
    assert p.health().healthy and p.state is ProviderLifecycleState.AVAILABLE
    p.shutdown()
    assert p.state is ProviderLifecycleState.STOPPED and not p.health().healthy


def test_error_failure_classes():
    assert ProviderTimeoutError.failure_class is FailureClass.RETRYABLE
    assert ProviderUnavailableError.failure_class is FailureClass.RETRYABLE
    assert issubclass(ProviderTimeoutError, ProviderError)


def test_observability_records_success_and_failure():
    log = ProviderInvocationLog()
    p = DeterministicActionGovernanceProvider(); p.initialize()
    record_invocation("deterministic-action", "ACTION_GOVERNANCE", "authorize",
                      lambda: p.authorize(ActionGovernanceRequest("OK")), log=log)
    bad = DeterministicActionGovernanceProvider(unavailable=True); bad.initialize()
    with pytest.raises(ProviderUnavailableError):
        record_invocation("deterministic-action", "ACTION_GOVERNANCE", "authorize",
                          lambda: bad.authorize(ActionGovernanceRequest("OK")), log=log)
    recs = log.all()
    assert recs[0].completed and recs[0].outcome
    assert not recs[1].completed and recs[1].error_class == "ProviderUnavailableError"
    assert recs[1].failure_class == "RETRYABLE"
