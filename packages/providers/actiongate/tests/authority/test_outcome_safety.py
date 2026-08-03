"""RELEASE GATE — the ActionGate outcome-safety invariants.

> Uncertainty or infrastructure failure is NEVER promoted to AUTHORIZED, and
> authorization is never execution.

Every unknown/unmapped native outcome, malformed result, timeout, unavailability,
and configuration error maps to INDETERMINATE (or raises a classified ProviderError
that the framework normalizes to INDETERMINATE) — never AUTHORIZED. DENIED stays
distinct from INDETERMINATE; AUTHORIZED_WITH_CONSTRAINTS stays distinct from
unrestricted AUTHORIZED; constraints/obligations are never silently dropped while
keeping an authorized outcome.
"""
from __future__ import annotations

import pytest

from ugence_governance_provider_framework.api import (
    ActionGovernanceOutcome, ActionGovernanceRequest, ProviderError,
    ProviderResultValidationError, ProviderTimeoutError, ProviderUnavailableError)

from ugence_actiongate_provider.configuration import build_actiongate_provider
from ugence_actiongate_provider.core import (
    ActionGateConstraint, ActionGateDecision, ActionGateEngine, ActionGateObligation,
    ActionGateOutcome, ConstrainedRule)
from ugence_actiongate_provider.mapping import map_result

AUTHORIZING = {ActionGovernanceOutcome.AUTHORIZED,
               ActionGovernanceOutcome.AUTHORIZED_WITH_CONSTRAINTS}


def _p(**kw):
    p = build_actiongate_provider(ActionGateEngine(**kw)); p.initialize()
    return p


def test_unknown_outcome_is_indeterminate_not_authorized():
    r = _p(unknown=frozenset({"U"})).authorize(ActionGovernanceRequest("U"))
    assert r.outcome is ActionGovernanceOutcome.INDETERMINATE
    assert r.outcome not in AUTHORIZING


def test_unmapped_native_outcome_never_authorizes():
    # A native decision whose outcome is not in the frozen map must fail closed.
    class _Rogue(str):
        pass
    d = ActionGateDecision(outcome=ActionGateOutcome.UNKNOWN)
    object.__setattr__(d, "outcome", _Rogue("TOTALLY_NEW"))
    assert map_result(d).outcome is ActionGovernanceOutcome.INDETERMINATE


@pytest.mark.parametrize("fail,exc", [
    ("timeout", ProviderTimeoutError),
    ("unavailable", ProviderUnavailableError),
    ("malformed", ProviderResultValidationError),
    ("config", ProviderError),
])
def test_infrastructure_failure_never_authorizes(fail, exc):
    with pytest.raises(exc):
        _p(fail=fail).authorize(ActionGovernanceRequest("X"))


def test_denied_is_distinct_from_indeterminate():
    denied = _p(denied=frozenset({"D"})).authorize(ActionGovernanceRequest("D"))
    indet = _p(unknown=frozenset({"U"})).authorize(ActionGovernanceRequest("U"))
    assert denied.outcome is ActionGovernanceOutcome.DENIED
    assert indet.outcome is ActionGovernanceOutcome.INDETERMINATE
    assert denied.outcome is not indet.outcome
    assert denied.outcome not in AUTHORIZING


def test_constrained_allow_is_distinct_from_unrestricted_allow():
    rule = ConstrainedRule(constraints=(ActionGateConstraint("maximum_amount", "10"),),
                           obligations=(ActionGateObligation("human_review"),))
    constrained = _p(constrained={"C": rule}).authorize(ActionGovernanceRequest("C"))
    allow = _p().authorize(ActionGovernanceRequest("OK"))
    assert constrained.outcome is ActionGovernanceOutcome.AUTHORIZED_WITH_CONSTRAINTS
    assert allow.outcome is ActionGovernanceOutcome.AUTHORIZED
    assert constrained.constraints and not allow.constraints


def test_constraints_not_dropped_while_authorized():
    rule = ConstrainedRule(constraints=(ActionGateConstraint("maximum_amount", "10"),
                                        ActionGateConstraint("required_approval", "senior")),
                           obligations=())
    r = _p(constrained={"C": rule}).authorize(ActionGovernanceRequest("C"))
    assert r.outcome is ActionGovernanceOutcome.AUTHORIZED_WITH_CONSTRAINTS
    # constrained authorization must carry its constraints — never silently empty
    assert set(r.constraints) == {"maximum_amount=10", "required_approval=senior"}


def test_obligations_not_dropped_when_claimed():
    rule = ConstrainedRule(constraints=(),
                           obligations=(ActionGateObligation("human_review"),
                                        ActionGateObligation("notification", "ops")))
    r = _p(constrained={"C": rule}).authorize(ActionGovernanceRequest("C"))
    assert "human_review" in r.obligations and "notification=ops" in r.obligations
