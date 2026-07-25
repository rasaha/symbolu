"""Request/result/constraint mapping + error translation."""
from __future__ import annotations

import pytest

from governance_providers.api import (
    ActionGovernanceOutcome, ActionGovernanceRequest,
    ProviderResultValidationError, ProviderTimeoutError, ProviderUnavailableError)
from actiongate_provider.configuration import build_actiongate_provider
from actiongate_provider.core import (
    ActionGateConstraint, ActionGateEngine, ActionGateObligation, ConstrainedRule)
from actiongate_provider.mapping import map_request, map_result
from actiongate_provider.core import ActionGateDecision, ActionGateOutcome


def test_request_mapping_preserves_fields():
    n = map_request(ActionGovernanceRequest(
        action_type="A", requested_parameters={"k": "v"}, actor="u", authority_context="au",
        target_resource="r", policy_refs=("p:1",), decision_refs=("d",),
        idempotency_key="i", correlation_id="c"))
    assert (n.action_type, n.principal, n.authority, n.resource) == ("A", "u", "au", "r")
    assert n.policy_context == ("p:1",) and n.decision_refs == ("d",)
    assert n.idempotency_key == "i" and n.correlation_id == "c"


def test_unknown_native_outcome_never_authorizes():
    # A hypothetical unmapped native outcome maps to INDETERMINATE.
    d = ActionGateDecision(ActionGateOutcome.UNKNOWN)
    assert map_result(d).outcome is ActionGovernanceOutcome.INDETERMINATE


def test_constraint_and_obligation_encoding():
    rule = ConstrainedRule(
        constraints=(ActionGateConstraint("maximum_amount", "100000"),
                     ActionGateConstraint("weird_ext", "x")),
        obligations=(ActionGateObligation("human_review"),))
    p = build_actiongate_provider(ActionGateEngine(constrained={"C": rule})); p.initialize()
    r = p.authorize(ActionGovernanceRequest("C"))
    assert "maximum_amount=100000" in r.constraints
    assert "ext:weird_ext=x" in r.constraints        # unknown kept, never discarded
    assert "human_review" in r.obligations


@pytest.mark.parametrize("fail,exc", [
    ("timeout", ProviderTimeoutError),
    ("unavailable", ProviderUnavailableError),
    ("malformed", ProviderResultValidationError),
])
def test_error_translation(fail, exc):
    p = build_actiongate_provider(ActionGateEngine(fail=fail)); p.initialize()
    with pytest.raises(exc):
        p.authorize(ActionGovernanceRequest("X"))


def test_no_native_exception_leaks():
    from actiongate_provider.core import ActionGateError
    from governance_providers.api import ProviderError
    p = build_actiongate_provider(ActionGateEngine(fail="config")); p.initialize()
    with pytest.raises(ProviderError) as ei:
        p.authorize(ActionGovernanceRequest("X"))
    assert not isinstance(ei.value, ActionGateError)
