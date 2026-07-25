"""Three complete lifecycle fixtures with ActionGate as the control plane."""
from __future__ import annotations

from governance_providers.api import ActionGovernanceControlPlaneAdapter
from actiongate_provider.configuration import build_actiongate_provider
from actiongate_provider.core import (
    ActionGateConstraint, ActionGateEngine, ActionGateObligation, ConstrainedRule)

from .conftest import run_actiongate_lifecycle


def _control_plane(engine):
    provider = build_actiongate_provider(engine); provider.initialize()
    return ActionGovernanceControlPlaneAdapter(provider)


def test_authorized_reaches_reconciled():
    cp = _control_plane(ActionGateEngine())
    r = run_actiongate_lifecycle(cp)
    assert r.authorization_outcome == "AUTHORIZED"
    assert r.reconciliation_status == "RECONCILED"
    assert r.dispatched


def test_authorized_with_constraints_preserves_controls_and_reconciles():
    rule = ConstrainedRule(
        constraints=(ActionGateConstraint("maximum_amount", "100000"),),
        obligations=(ActionGateObligation("human_review"),
                     ActionGateObligation("notification", "finance")),
        expiry_seconds=3600)
    cp = _control_plane(ActionGateEngine(constrained={"ACT": rule}))
    r = run_actiongate_lifecycle(cp)
    assert r.authorization_outcome == "AUTHORIZED_WITH_CONSTRAINTS"
    assert r.reconciliation_status == "RECONCILED"
    # audit preserved: the governance chain still emitted its milestones
    from decision_governance.api.audit import AuditEventType
    assert AuditEventType.ACTION_AUTHORIZATION_CONSTRAINED in r.events
    assert AuditEventType.EXECUTION_RECONCILED in r.events


def test_denied_never_dispatches():
    cp = _control_plane(ActionGateEngine(denied=frozenset({"ACT"})))
    r = run_actiongate_lifecycle(cp)
    assert r.authorization_outcome == "DENIED"
    assert r.reconciliation_status is None
    assert not r.dispatched


def test_indeterminate_never_dispatches():
    cp = _control_plane(ActionGateEngine(unknown=frozenset({"ACT"})))
    r = run_actiongate_lifecycle(cp)
    assert r.authorization_outcome == "INDETERMINATE"
    assert r.reconciliation_status is None
    assert not r.dispatched


def test_provider_failure_is_indeterminate_and_never_dispatches():
    # a vendor failure normalizes to INDETERMINATE at the adapter — no execution
    cp = _control_plane(ActionGateEngine(fail="unavailable"))
    r = run_actiongate_lifecycle(cp)
    assert r.authorization_outcome == "INDETERMINATE"
    assert not r.dispatched
