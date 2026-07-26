"""H4 — execution: authorization enforcement, obligations, idempotency, retries."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from governance_providers.api import ExecutionBusinessOutcome
from governance_providers.contracts.action import (
    ActionGovernanceOutcome,
    ActionGovernanceResult,
)

from ai_hiring.actions.action_types import HiringActionType
from ai_hiring.actions.actiongate_integration import ActionAuthorizationIntegration
from ai_hiring.actions.status import ActionProposalStatus
from ai_hiring.errors import (
    ActionConstraintViolationError,
    ActionNotAuthorizedError,
    HiringAuthorizationExpiredError,
    DuplicateExecutionError,
    IllegalActionTransitionError,
    MalformedReceiptError,
    ObligationUnmetError,
    TargetMismatchError,
)
from ai_hiring.tests.h3_helpers import ai_ctx
from ai_hiring.tests.h4_helpers import (
    action_integration,
    build_h4_env,
    decided_recommendation,
    exec_adapter,
    propose_and_authorize,
)


class _ExpiringProvider:
    """Minimal action-governance provider that authorizes with a past expiry."""
    def descriptor(self):
        return type("D", (), {"provider_id": "expiring"})()
    def authorize(self, request):
        return ActionGovernanceResult(
            outcome=ActionGovernanceOutcome.AUTHORIZED,
            expiry=datetime(2000, 1, 1, tzinfo=timezone.utc), obligations=())


def test_successful_execution_reaches_reconciliation_required():
    env = build_h4_env()
    prop, auth = propose_and_authorize(env, decided_recommendation(env))
    attempt = env.execution_service.execute(
        ai_ctx(), proposal_id=prop.action_proposal_id, adapter=exec_adapter(),
        satisfied_obligations=auth.obligations)
    assert attempt.execution_status == "SUCCEEDED"
    assert env.proposals.get(prop.action_proposal_id).status == ActionProposalStatus.RECONCILIATION_REQUIRED


def test_unmet_obligation_blocks_execution():
    env = build_h4_env()
    prop, auth = propose_and_authorize(
        env, decided_recommendation(env),
        integration=action_integration(constrained=frozenset({"ADVANCE_STAGE"})))
    assert auth.obligations
    with pytest.raises(ObligationUnmetError):
        env.execution_service.execute(ai_ctx(), proposal_id=prop.action_proposal_id,
                                      adapter=exec_adapter())  # obligations NOT satisfied


def test_execution_without_authorization_rejected():
    env = build_h4_env()
    rec = decided_recommendation(env)
    prop = env.proposal_service.propose(
        ai_ctx(), recommendation_id=rec.recommendation_id, action_type=HiringActionType.ADVANCE_STAGE,
        target_system="ats")  # DRAFT, never authorized
    with pytest.raises((ActionNotAuthorizedError, IllegalActionTransitionError)):
        env.execution_service.execute(ai_ctx(), proposal_id=prop.action_proposal_id, adapter=exec_adapter())


def test_expired_authorization_blocks_execution():
    env = build_h4_env()
    rec = decided_recommendation(env)
    prop = env.proposal_service.propose(
        ai_ctx(), recommendation_id=rec.recommendation_id, action_type=HiringActionType.ADVANCE_STAGE,
        target_system="ats", parameters=(("stage", "onsite"),))
    env.proposal_service.mark_ready(ai_ctx(), prop.action_proposal_id)
    env.authorization_service.authorize(
        ai_ctx(), proposal_id=prop.action_proposal_id,
        integration=ActionAuthorizationIntegration(_ExpiringProvider()))
    with pytest.raises(HiringAuthorizationExpiredError):
        env.execution_service.execute(ai_ctx(), proposal_id=prop.action_proposal_id, adapter=exec_adapter())


def test_modified_parameters_after_authorization_rejected():
    env = build_h4_env()
    prop, auth = propose_and_authorize(env, decided_recommendation(env))
    # simulate an out-of-band parameter change (new version, different params)
    tampered = prop.model_copy(update={
        "status": ActionProposalStatus.AUTHORIZED,
        "normalized_parameters": (("stage", "final"),), "version": prop.version + 5})
    env.proposals.add(tampered)
    with pytest.raises(ActionConstraintViolationError):
        env.execution_service.execute(ai_ctx(), proposal_id=prop.action_proposal_id,
                                      adapter=exec_adapter(), satisfied_obligations=auth.obligations)


def test_transient_failure_then_bounded_retry_succeeds():
    env = build_h4_env()
    prop, auth = propose_and_authorize(env, decided_recommendation(env))
    a1 = env.execution_service.execute(
        ai_ctx(), proposal_id=prop.action_proposal_id,
        adapter=exec_adapter(transport_fail=True, transport_retryable=True),
        satisfied_obligations=auth.obligations)
    assert a1.error_classification.value == "RETRYABLE"
    assert env.proposals.get(prop.action_proposal_id).status == ActionProposalStatus.EXECUTION_FAILED
    a2 = env.execution_service.execute(
        ai_ctx(), proposal_id=prop.action_proposal_id, adapter=exec_adapter(),
        satisfied_obligations=auth.obligations)
    assert a2.attempt_number == 2 and a2.execution_status == "SUCCEEDED"


def test_permanent_failure_is_not_retryable():
    env = build_h4_env()
    prop, auth = propose_and_authorize(env, decided_recommendation(env))
    env.execution_service.execute(
        ai_ctx(), proposal_id=prop.action_proposal_id,
        adapter=exec_adapter(transport_fail=True, transport_retryable=False),
        satisfied_obligations=auth.obligations)
    with pytest.raises(IllegalActionTransitionError):
        env.execution_service.execute(ai_ctx(), proposal_id=prop.action_proposal_id,
                                      adapter=exec_adapter(), satisfied_obligations=auth.obligations)


def test_no_retry_after_success():
    env = build_h4_env()
    prop, auth = propose_and_authorize(env, decided_recommendation(env))
    env.execution_service.execute(ai_ctx(), proposal_id=prop.action_proposal_id, adapter=exec_adapter(),
                                  satisfied_obligations=auth.obligations)
    with pytest.raises((DuplicateExecutionError, IllegalActionTransitionError)):
        env.execution_service.execute(ai_ctx(), proposal_id=prop.action_proposal_id, adapter=exec_adapter(),
                                      satisfied_obligations=auth.obligations)


def test_malformed_receipt_fails_safe():
    env = build_h4_env()
    prop, auth = propose_and_authorize(env, decided_recommendation(env))
    with pytest.raises(MalformedReceiptError):
        env.execution_service.execute(ai_ctx(), proposal_id=prop.action_proposal_id,
                                      adapter=exec_adapter(malformed=True), satisfied_obligations=auth.obligations)
    assert env.proposals.get(prop.action_proposal_id).status == ActionProposalStatus.EXECUTION_FAILED


def test_target_mismatch_fails_safe():
    env = build_h4_env()
    prop, auth = propose_and_authorize(env, decided_recommendation(env))
    with pytest.raises(TargetMismatchError):
        env.execution_service.execute(ai_ctx(), proposal_id=prop.action_proposal_id,
                                      adapter=exec_adapter(observed_target="rogue-hris"),
                                      satisfied_obligations=auth.obligations)
    assert env.proposals.get(prop.action_proposal_id).status == ActionProposalStatus.EXECUTION_FAILED
