"""H4 — reconciliation of authorized intent vs actual outcome."""

from __future__ import annotations

from governance_providers.api import ExecutionBusinessOutcome

from ai_hiring.actions.records import ReconciliationOutcome
from ai_hiring.actions.status import ActionProposalStatus
from ai_hiring.tests.h3_helpers import ai_ctx
from ai_hiring.tests.h4_helpers import build_h4_env, decided_recommendation, exec_adapter, propose_and_authorize


def _executed(env, *, adapter):
    prop, auth = propose_and_authorize(env, decided_recommendation(env))
    env.execution_service.execute(ai_ctx(), proposal_id=prop.action_proposal_id, adapter=adapter,
                                  satisfied_obligations=auth.obligations)
    return prop


def test_reconciliation_matched():
    env = build_h4_env()
    prop = _executed(env, adapter=exec_adapter())
    r = env.reconciliation_service.reconcile(ai_ctx(), proposal_id=prop.action_proposal_id)
    assert r.outcome is ReconciliationOutcome.MATCHED
    assert env.proposals.get(prop.action_proposal_id).status == ActionProposalStatus.RECONCILED


def test_reconciliation_partially_matched():
    env = build_h4_env()
    prop = _executed(env, adapter=exec_adapter(observed_params_override=(("other", "x"),)))
    r = env.reconciliation_service.reconcile(ai_ctx(), proposal_id=prop.action_proposal_id)
    assert r.outcome is ReconciliationOutcome.PARTIALLY_MATCHED
    assert "stage" in r.mismatched_fields  # missing authorized field


def test_reconciliation_mismatched_requires_compensation():
    env = build_h4_env()
    prop = _executed(env, adapter=exec_adapter(observed_params_override=(("stage", "different"),)))
    r = env.reconciliation_service.reconcile(ai_ctx(), proposal_id=prop.action_proposal_id)
    assert r.outcome is ReconciliationOutcome.MISMATCHED and r.compensation_required
    assert env.proposals.get(prop.action_proposal_id).status == ActionProposalStatus.COMPENSATION_REQUIRED


def test_reconciliation_duplicate_execution():
    env = build_h4_env()
    prop = _executed(env, adapter=exec_adapter(business_outcome=ExecutionBusinessOutcome.DUPLICATE))
    r = env.reconciliation_service.reconcile(ai_ctx(), proposal_id=prop.action_proposal_id)
    assert r.outcome is ReconciliationOutcome.DUPLICATE_EXECUTION and r.compensation_required


def test_reconciliation_not_executed():
    env = build_h4_env()
    prop, auth = propose_and_authorize(env, decided_recommendation(env))  # authorized, not executed
    r = env.reconciliation_service.reconcile(ai_ctx(), proposal_id=prop.action_proposal_id)
    assert r.outcome is ReconciliationOutcome.NOT_EXECUTED


def test_success_response_alone_is_not_reconciled():
    """Reconciliation is a distinct step; execution success does not auto-reconcile."""
    env = build_h4_env()
    prop = _executed(env, adapter=exec_adapter())
    assert env.proposals.get(prop.action_proposal_id).status == ActionProposalStatus.RECONCILIATION_REQUIRED
    assert env.reconciliations.latest_for_proposal(prop.action_proposal_id) is None
