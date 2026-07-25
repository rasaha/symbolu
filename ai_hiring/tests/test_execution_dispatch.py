"""Dispatch and attempts: transport ≠ success, timeout ≠ failure, controlled retry."""

from __future__ import annotations

import pytest

from ai_hiring.executions import (
    ExecutionStatus,
    OfflineDeterministicExecutionAdapter,
    RetryClassification,
    TransportStatus,
)
from ai_hiring.errors import (
    ExecutionIdempotencyConflictError,
    MalformedExternalResponseError,
    UnsafeRetryError,
)
from ai_hiring.services.execution_service import ExecutionService

from .conftest import EXECUTOR, TENANT, authorized_request


def _svc_with_adapter(platform, adapter) -> ExecutionService:
    return ExecutionService(
        platform.execution_repo, platform.action_request_repo,
        platform.execution_validation_service, adapter, platform.audit_service,
        platform.identity_provider, platform.evidence_access_policy)


def _intent(platform, **kw):
    req = authorized_request(platform, **kw)
    return platform.execution_service.create_execution_intent(
        action_request_id=req.action_request_id, created_by=EXECUTOR)


def test_dispatch_creates_attempt_but_not_success(execution_platform):
    intent = _intent(execution_platform)
    attempt = execution_platform.execution_service.dispatch_execution(
        intent_id=intent.execution_intent_id, actor=EXECUTOR)
    assert attempt.attempt_number == 1
    assert attempt.transport_status is TransportStatus.ACKNOWLEDGED
    status = execution_platform.execution_service.get_execution_intent(
        intent.execution_intent_id).status
    # Acknowledged, NOT succeeded — and no execution record exists yet.
    assert status is ExecutionStatus.ACKNOWLEDGED
    assert execution_platform.reconciliation_service.get_execution_records(
        intent.execution_intent_id) == ()


def test_transport_failure_is_recorded(execution_platform):
    adapter = OfflineDeterministicExecutionAdapter(
        transport_failing=frozenset({"ADVANCE_WORKFLOW_STAGE"}))
    svc = _svc_with_adapter(execution_platform, adapter)
    intent = _intent(execution_platform)
    attempt = svc.dispatch_execution(intent_id=intent.execution_intent_id, actor=EXECUTOR)
    assert attempt.transport_status is TransportStatus.TRANSPORT_FAILED
    assert svc.get_execution_intent(intent.execution_intent_id).status is ExecutionStatus.FAILED


def test_timeout_produces_outcome_unknown_not_failure(execution_platform):
    adapter = OfflineDeterministicExecutionAdapter(
        timing_out=frozenset({"ADVANCE_WORKFLOW_STAGE"}))
    svc = _svc_with_adapter(execution_platform, adapter)
    intent = _intent(execution_platform)
    attempt = svc.dispatch_execution(intent_id=intent.execution_intent_id, actor=EXECUTOR)
    assert attempt.transport_status is TransportStatus.TIMED_OUT
    status = svc.get_execution_intent(intent.execution_intent_id).status
    assert status is ExecutionStatus.OUTCOME_UNKNOWN
    assert status is not ExecutionStatus.FAILED


def test_malformed_adapter_response_is_rejected(execution_platform):
    class BadAdapter:
        adapter_id = "bad"
        adapter_version = "0"
        def dispatch(self, intent):
            class R:  # not a valid transport status
                transport_status = "NONSENSE"
                external_request_id = "x"
                acknowledgement = ""
                retry_classification = RetryClassification.NOT_RETRYABLE
                error_code = ""
                error_detail = ""
            return R()
        def query_status(self, external_request_id):
            raise NotImplementedError

    svc = _svc_with_adapter(execution_platform, BadAdapter())
    intent = _intent(execution_platform)
    with pytest.raises(MalformedExternalResponseError):
        svc.dispatch_execution(intent_id=intent.execution_intent_id, actor=EXECUTOR)


def test_attempt_numbers_are_monotonic_on_retry(execution_platform):
    adapter = OfflineDeterministicExecutionAdapter(
        timing_out=frozenset({"ADVANCE_WORKFLOW_STAGE"}),
        retry_classification=RetryClassification.IDEMPOTENT_SAFE)
    svc = _svc_with_adapter(execution_platform, adapter)
    intent = _intent(execution_platform)
    svc.dispatch_execution(intent_id=intent.execution_intent_id, actor=EXECUTOR)
    svc.retry_execution(intent_id=intent.execution_intent_id, actor=EXECUTOR,
                        retry_classification=RetryClassification.IDEMPOTENT_SAFE)
    attempts = svc.get_execution_attempts(intent.execution_intent_id)
    assert [a.attempt_number for a in attempts] == [1, 2]


def test_unsafe_retry_is_rejected(execution_platform):
    adapter = OfflineDeterministicExecutionAdapter(
        timing_out=frozenset({"ADVANCE_WORKFLOW_STAGE"}))
    svc = _svc_with_adapter(execution_platform, adapter)
    intent = _intent(execution_platform)
    svc.dispatch_execution(intent_id=intent.execution_intent_id, actor=EXECUTOR)
    with pytest.raises(UnsafeRetryError):
        svc.retry_execution(intent_id=intent.execution_intent_id, actor=EXECUTOR,
                            retry_classification=RetryClassification.UNSAFE)


def test_non_idempotent_retry_requires_second_approver(execution_platform):
    adapter = OfflineDeterministicExecutionAdapter(
        timing_out=frozenset({"ADVANCE_WORKFLOW_STAGE"}))
    svc = _svc_with_adapter(execution_platform, adapter)
    intent = _intent(execution_platform)
    svc.dispatch_execution(intent_id=intent.execution_intent_id, actor=EXECUTOR)
    # REQUIRES_APPROVAL without a distinct second approver → rejected.
    with pytest.raises(UnsafeRetryError):
        svc.retry_execution(intent_id=intent.execution_intent_id, actor=EXECUTOR,
                            retry_classification=RetryClassification.REQUIRES_APPROVAL)
    # With a distinct, granted approver it proceeds.
    from .conftest import RECONCILER
    attempt = svc.retry_execution(
        intent_id=intent.execution_intent_id, actor=EXECUTOR,
        retry_classification=RetryClassification.REQUIRES_APPROVAL,
        second_approver=RECONCILER)
    assert attempt.attempt_number == 2


def test_idempotent_intent_creation_returns_existing(execution_platform):
    req = authorized_request(execution_platform)
    a = execution_platform.execution_service.create_execution_intent(
        action_request_id=req.action_request_id, created_by=EXECUTOR,
        execution_idempotency_key="ek-1")
    b = execution_platform.execution_service.create_execution_intent(
        action_request_id=req.action_request_id, created_by=EXECUTOR,
        execution_idempotency_key="ek-1")
    assert a.execution_intent_id == b.execution_intent_id


def test_conflicting_execution_idempotency_key_is_rejected(execution_platform):
    req = authorized_request(execution_platform, params={"stage": "interview"})
    execution_platform.execution_service.create_execution_intent(
        action_request_id=req.action_request_id, created_by=EXECUTOR,
        execution_idempotency_key="ek-dup")
    # Same key, different (subset) parameters → conflict.
    with pytest.raises(ExecutionIdempotencyConflictError):
        execution_platform.execution_service.create_execution_intent(
            action_request_id=req.action_request_id, created_by=EXECUTOR,
            execution_parameters={}, execution_idempotency_key="ek-dup")
