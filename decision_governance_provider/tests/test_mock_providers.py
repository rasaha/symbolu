"""Mock providers behave deterministically across their configured paths."""
from __future__ import annotations

from decision_governance_provider.contracts import (
    AuthorizationContext, AuthorizationOutcome, BusinessOutcome)
from decision_governance_provider.mock import (
    MockAssertionProvider, MockAuthorizationProvider, MockExecutionProvider)


def test_assertion_found_and_blocked():
    p = MockAssertionProvider()
    r = p.resolve_assertion(tenant_id="t", record_type="assessment", record_id="x")
    assert r.found and r.finalized and not r.blocked
    b = MockAssertionProvider(blocked=True).resolve_assertion(
        tenant_id="t", record_type="a", record_id="x")
    assert b.blocked
    nf = MockAssertionProvider(found=False).resolve_assertion(
        tenant_id="t", record_type="a", record_id="x")
    assert not nf.found


def test_authorization_paths():
    p = MockAuthorizationProvider(denied=frozenset({"D"}), constrained=frozenset({"C"}))
    ctx = lambda at, exp=False: AuthorizationContext(action_type=at, parameters={}, cer_expired=exp)
    assert p.authorize(ctx("OK")).outcome is AuthorizationOutcome.AUTHORIZED
    assert p.authorize(ctx("D")).outcome is AuthorizationOutcome.DENIED
    assert p.authorize(ctx("C")).outcome is AuthorizationOutcome.AUTHORIZED_WITH_CONSTRAINTS
    assert p.authorize(ctx("OK", exp=True)).outcome is AuthorizationOutcome.EXPIRED


def test_execution_paths():
    p = MockExecutionProvider(transport_failing=frozenset({"F"}),
                              timing_out=frozenset({"T"}),
                              outcomes={"R": BusinessOutcome.REJECTED})
    assert not p.dispatch(action_type="F", parameters={}).accepted
    assert p.dispatch(action_type="T", parameters={}).timed_out
    ok = p.dispatch(action_type="R", parameters={})
    assert ok.accepted
    assert p.observe(external_request_id=ok.external_request_id).business_outcome is BusinessOutcome.REJECTED
    ok2 = p.dispatch(action_type="S", parameters={})
    assert p.observe(external_request_id=ok2.external_request_id).business_outcome is BusinessOutcome.SUCCEEDED
