"""Control-plane integration fixtures — ActionGate as ActionControlPlanePort.

Proves, through the framework adapter and the Decision Authority kernel, the frozen
dispatch invariants (F9/F10): AUTHORIZED reaches reconciliation; DENIED and
INDETERMINATE never dispatch; a normalized provider failure becomes INDETERMINATE
and never dispatches. The package does NOT implement dispatch/execution — those
steps are the kernel's; ActionGate only authorizes.

Requires the optional ``decision-authority`` dependency.
"""
from __future__ import annotations

import pytest

pytest.importorskip("decision_governance", reason="decision-authority extra not installed")

from ugence_governance_provider_framework.api import ActionGovernanceControlPlaneAdapter  # noqa: E402

from ugence_actiongate_provider.configuration import build_actiongate_provider  # noqa: E402
from ugence_actiongate_provider.core import (  # noqa: E402
    ActionGateConstraint, ActionGateEngine, ActionGateObligation, ConstrainedRule)

from lifecycle_harness import run_actiongate_lifecycle  # noqa: E402


def _control_plane(engine):
    provider = build_actiongate_provider(engine); provider.initialize()
    return ActionGovernanceControlPlaneAdapter(provider)


def test_authorized_reaches_reconciled():
    r = run_actiongate_lifecycle(_control_plane(ActionGateEngine()))
    assert r.authorization_outcome == "AUTHORIZED"
    assert r.reconciliation_status == "RECONCILED"
    assert r.dispatched


def test_authorized_with_constraints_preserves_controls_and_reconciles():
    rule = ConstrainedRule(
        constraints=(ActionGateConstraint("maximum_amount", "100000"),),
        obligations=(ActionGateObligation("human_review"),
                     ActionGateObligation("notification", "finance")),
        expiry_seconds=3600)
    r = run_actiongate_lifecycle(_control_plane(ActionGateEngine(constrained={"ACT": rule})))
    assert r.authorization_outcome == "AUTHORIZED_WITH_CONSTRAINTS"
    assert r.reconciliation_status == "RECONCILED"
    from decision_governance.api.audit import AuditEventType
    assert AuditEventType.ACTION_AUTHORIZATION_CONSTRAINED in r.events
    assert AuditEventType.EXECUTION_RECONCILED in r.events


def test_denied_never_dispatches():
    r = run_actiongate_lifecycle(_control_plane(ActionGateEngine(denied=frozenset({"ACT"}))))
    assert r.authorization_outcome == "DENIED"
    assert r.reconciliation_status is None
    assert not r.dispatched


def test_indeterminate_never_dispatches():
    r = run_actiongate_lifecycle(_control_plane(ActionGateEngine(unknown=frozenset({"ACT"}))))
    assert r.authorization_outcome == "INDETERMINATE"
    assert r.reconciliation_status is None
    assert not r.dispatched


def test_provider_failure_is_indeterminate_and_never_dispatches():
    r = run_actiongate_lifecycle(_control_plane(ActionGateEngine(fail="unavailable")))
    assert r.authorization_outcome == "INDETERMINATE"
    assert not r.dispatched
