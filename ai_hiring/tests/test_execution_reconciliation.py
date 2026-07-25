"""External observations and reconciliation of authorized vs observed effects."""

from __future__ import annotations

import pytest

from ai_hiring.executions import (
    BusinessOutcome,
    ExecutionStatus,
    Finality,
    OutcomeSource,
    ReconciliationStatus,
)
from ai_hiring.errors import ExternalRequestMismatchError, ReconciliationIncompleteError

from .conftest import EXECUTOR, RECONCILER, authorized_request


def _dispatched_intent(platform, *, params=None):
    req = authorized_request(platform, params=params)
    intent = platform.execution_service.create_execution_intent(
        action_request_id=req.action_request_id, created_by=EXECUTOR)
    platform.execution_service.dispatch_execution(
        intent_id=intent.execution_intent_id, actor=EXECUTOR)
    return platform.execution_service.get_execution_intent(intent.execution_intent_id)


def _record(platform, intent, outcome, *, params=None, finality=Finality.FINAL,
            external_result_id="res-1"):
    return platform.reconciliation_service.record_external_outcome(
        intent_id=intent.execution_intent_id, actor=RECONCILER,
        business_outcome=outcome, observed_parameters=params,
        external_result_id=external_result_id, finality=finality,
        source=OutcomeSource.EXTERNAL_CALLBACK)


def test_success_recorded_only_from_observed_response(execution_platform):
    intent = _dispatched_intent(execution_platform, params={"stage": "interview"})
    record = _record(execution_platform, intent, BusinessOutcome.SUCCEEDED,
                     params={"stage": "interview"})
    assert record.business_outcome is BusinessOutcome.SUCCEEDED
    assert record.source is OutcomeSource.EXTERNAL_CALLBACK
    assert execution_platform.execution_service.get_execution_intent(
        intent.execution_intent_id).status is ExecutionStatus.SUCCEEDED


def test_failure_is_preserved(execution_platform):
    intent = _dispatched_intent(execution_platform)
    record = _record(execution_platform, intent, BusinessOutcome.FAILED)
    assert record.business_outcome is BusinessOutcome.FAILED
    assert execution_platform.execution_service.get_execution_intent(
        intent.execution_intent_id).status is ExecutionStatus.FAILED


def test_partial_success_is_preserved(execution_platform):
    intent = _dispatched_intent(execution_platform)
    record = _record(execution_platform, intent, BusinessOutcome.PARTIALLY_SUCCEEDED)
    assert record.business_outcome is BusinessOutcome.PARTIALLY_SUCCEEDED
    assert execution_platform.execution_service.get_execution_intent(
        intent.execution_intent_id).status is ExecutionStatus.PARTIALLY_SUCCEEDED


def test_multiple_observations_are_retained(execution_platform):
    intent = _dispatched_intent(execution_platform)
    _record(execution_platform, intent, BusinessOutcome.UNKNOWN,
            finality=Finality.NON_FINAL, external_result_id="res-a")
    _record(execution_platform, intent, BusinessOutcome.SUCCEEDED,
            finality=Finality.FINAL, external_result_id="res-b")
    records = execution_platform.reconciliation_service.get_execution_records(
        intent.execution_intent_id)
    assert len(records) == 2


def test_duplicate_result_is_detected(execution_platform):
    intent = _dispatched_intent(execution_platform)
    _record(execution_platform, intent, BusinessOutcome.SUCCEEDED,
            external_result_id="same-res")
    dup = _record(execution_platform, intent, BusinessOutcome.SUCCEEDED,
                  external_result_id="same-res")
    # The second observation of the same external result id is flagged DUPLICATE.
    assert dup.business_outcome is BusinessOutcome.DUPLICATE


def test_external_request_id_mismatch_is_rejected(execution_platform):
    intent = _dispatched_intent(execution_platform)
    with pytest.raises(ExternalRequestMismatchError):
        execution_platform.reconciliation_service.record_external_outcome(
            intent_id=intent.execution_intent_id, actor=RECONCILER,
            business_outcome=BusinessOutcome.SUCCEEDED,
            external_request_id="some-other-ext-id")


def test_query_status_creates_record_from_adapter(execution_platform):
    intent = _dispatched_intent(execution_platform, params={"stage": "interview"})
    record = execution_platform.reconciliation_service.query_external_status(
        intent_id=intent.execution_intent_id, actor=RECONCILER)
    assert record.business_outcome is BusinessOutcome.SUCCEEDED
    assert record.source is OutcomeSource.ADAPTER_STATUS_QUERY


def test_exact_match_reconciles(execution_platform):
    intent = _dispatched_intent(execution_platform, params={"stage": "interview"})
    _record(execution_platform, intent, BusinessOutcome.SUCCEEDED,
            params={"stage": "interview"})
    result = execution_platform.reconciliation_service.reconcile_execution(
        intent_id=intent.execution_intent_id, actor=RECONCILER)
    assert result.status is ReconciliationStatus.RECONCILED
    assert result.mismatch_codes == ()
    assert execution_platform.execution_service.get_execution_intent(
        intent.execution_intent_id).status is ExecutionStatus.RECONCILED


def test_parameter_mismatch_is_detected(execution_platform):
    intent = _dispatched_intent(execution_platform, params={"stage": "interview"})
    _record(execution_platform, intent, BusinessOutcome.SUCCEEDED,
            params={"stage": "DIFFERENT_STAGE"})
    result = execution_platform.reconciliation_service.reconcile_execution(
        intent_id=intent.execution_intent_id, actor=RECONCILER)
    assert result.status is ReconciliationStatus.MISMATCHED
    assert any(c.startswith("PARAM_MISMATCH") for c in result.mismatch_codes)


def test_unknown_finality_is_indeterminate(execution_platform):
    intent = _dispatched_intent(execution_platform)
    _record(execution_platform, intent, BusinessOutcome.UNKNOWN, finality=Finality.UNKNOWN)
    result = execution_platform.reconciliation_service.reconcile_execution(
        intent_id=intent.execution_intent_id, actor=RECONCILER)
    assert result.status is ReconciliationStatus.INDETERMINATE


def test_failed_outcome_requires_compensation(execution_platform):
    intent = _dispatched_intent(execution_platform)
    _record(execution_platform, intent, BusinessOutcome.FAILED)
    result = execution_platform.reconciliation_service.reconcile_execution(
        intent_id=intent.execution_intent_id, actor=RECONCILER)
    assert result.status is ReconciliationStatus.COMPENSATION_REQUIRED
    assert result.compensation_required is True


def test_duplicate_effects_trigger_manual_review(execution_platform):
    intent = _dispatched_intent(execution_platform)
    _record(execution_platform, intent, BusinessOutcome.SUCCEEDED, external_result_id="r1")
    _record(execution_platform, intent, BusinessOutcome.SUCCEEDED, external_result_id="r1")
    result = execution_platform.reconciliation_service.reconcile_execution(
        intent_id=intent.execution_intent_id, actor=RECONCILER)
    assert result.status is ReconciliationStatus.MANUAL_REVIEW_REQUIRED
    assert "DUPLICATE_EFFECT" in result.mismatch_codes


def test_reconciliation_does_not_mutate_source_records(execution_platform):
    intent = _dispatched_intent(execution_platform, params={"stage": "interview"})
    record = _record(execution_platform, intent, BusinessOutcome.SUCCEEDED,
                     params={"stage": "interview"})
    before = record.content_hash
    execution_platform.reconciliation_service.reconcile_execution(
        intent_id=intent.execution_intent_id, actor=RECONCILER)
    records = execution_platform.reconciliation_service.get_execution_records(
        intent.execution_intent_id)
    assert records[0].content_hash == before  # unchanged


def test_reconcile_without_observations_is_incomplete(execution_platform):
    intent = _dispatched_intent(execution_platform)
    with pytest.raises(ReconciliationIncompleteError):
        execution_platform.reconciliation_service.reconcile_execution(
            intent_id=intent.execution_intent_id, actor=RECONCILER)


def test_compensation_requirement_is_governed(execution_platform):
    intent = _dispatched_intent(execution_platform)
    _record(execution_platform, intent, BusinessOutcome.FAILED)
    result = execution_platform.reconciliation_service.reconcile_execution(
        intent_id=intent.execution_intent_id, actor=RECONCILER)
    comp = execution_platform.compensation_service.create_compensation_requirement(
        intent_id=intent.execution_intent_id, reconciliation_id=result.reconciliation_id,
        actor=RECONCILER, reason_codes=("OUTCOME_FAILED",))
    from ai_hiring.executions import CompensationApprovalStatus
    assert comp.approval_status is CompensationApprovalStatus.PROPOSED
    resolved = execution_platform.compensation_service.resolve_compensation_requirement(
        compensation_id=comp.compensation_id, actor=RECONCILER,
        resolution_ref="ticket-42")
    assert resolved.approval_status is CompensationApprovalStatus.RESOLVED
    # History preserves both the proposal and the resolution.
    history = execution_platform.compensation_service.get_compensation_history(
        intent.execution_intent_id)
    assert history[0].revision == 2  # latest snapshot
