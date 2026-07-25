"""Phase 4C contract invariants: immutable intents, attempts, records, results."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ai_hiring.executions import (
    BusinessOutcome,
    CompensationApprovalStatus,
    CompensationRequirement,
    CompensationType,
    ExecutionAttempt,
    ExecutionIntent,
    ExecutionRecord,
    ExecutionStatus,
    Finality,
    ReconciliationResult,
    ReconciliationStatus,
    TransportStatus,
)
from ai_hiring.errors import DomainValidationError

INVALID = (ValidationError, DomainValidationError)


def _intent(**kw) -> ExecutionIntent:
    base = dict(execution_intent_id="ei1", tenant_id="t1", action_request_id="ar1",
                action_request_version=1, authorization_id="az1", cer_id="cer1",
                action_type="ADVANCE_WORKFLOW_STAGE", target_system="ATS",
                authorized_parameters={"stage": "interview"}, created_by="exec-1",
                intent_version_id="iv1")
    base.update(kw)
    return ExecutionIntent(**base)


def test_intent_is_frozen_and_hash_stable_across_lifecycle():
    intent = _intent()
    intent = intent.model_copy(update={"content_hash": intent.compute_hash()})
    with pytest.raises(ValidationError):
        intent.status = ExecutionStatus.SUCCEEDED
    evolved = intent.evolve(intent_version_id="iv2",
                            status=ExecutionStatus.READY_FOR_DISPATCH)
    # Lifecycle change does NOT change the authorized-content hash.
    assert evolved.compute_hash() == intent.content_hash
    assert evolved.version == 2 and intent.version == 1


def test_intent_material_change_alters_hash():
    a = _intent()
    b = _intent(authorized_parameters={"stage": "onsite"})
    assert a.compute_hash() != b.compute_hash()


def test_intent_stores_no_external_result_fields():
    forbidden = {"business_outcome", "external_result_id", "observed_parameters",
                 "execution_record_id", "succeeded"}
    assert forbidden.isdisjoint(ExecutionIntent.model_fields.keys())


def test_attempt_is_frozen_and_transport_only():
    attempt = ExecutionAttempt(
        execution_attempt_id="exa1", execution_intent_id="ei1", attempt_number=1,
        adapter_id="offline", adapter_version="1.0", request_payload_hash="h",
        transport_status=TransportStatus.ACKNOWLEDGED)
    with pytest.raises(ValidationError):
        attempt.transport_status = TransportStatus.DISPATCHED
    # An attempt carries transport state, never a business outcome field.
    assert "business_outcome" not in ExecutionAttempt.model_fields


def test_attempt_number_must_be_positive():
    with pytest.raises(INVALID):
        ExecutionAttempt(
            execution_attempt_id="exa1", execution_intent_id="ei1", attempt_number=0,
            adapter_id="offline", adapter_version="1.0", request_payload_hash="h")


def test_execution_record_is_frozen_and_hashes():
    record = ExecutionRecord(
        execution_record_id="exr1", execution_intent_id="ei1",
        execution_attempt_id="exa1", tenant_id="t1", external_system="ATS",
        external_request_id="ext1", business_outcome=BusinessOutcome.SUCCEEDED,
        finality=Finality.FINAL)
    with pytest.raises(ValidationError):
        record.business_outcome = BusinessOutcome.FAILED
    assert record.compute_hash() == record.compute_hash()
    other = record.model_copy(update={"business_outcome": BusinessOutcome.FAILED})
    assert other.compute_hash() != record.compute_hash()


def test_reconciliation_is_frozen():
    result = ReconciliationResult(
        reconciliation_id="rec1", execution_intent_id="ei1", tenant_id="t1",
        execution_record_ids=("exr1",), expected_action_type="ADVANCE_WORKFLOW_STAGE",
        expected_target_system="ATS", observed_outcome=BusinessOutcome.SUCCEEDED,
        status=ReconciliationStatus.RECONCILED)
    with pytest.raises(ValidationError):
        result.status = ReconciliationStatus.MISMATCHED


def test_compensation_requires_reasons_and_is_immutable_by_revision():
    from ai_hiring.common import utc_now
    with pytest.raises(INVALID):
        CompensationRequirement(
            compensation_id="c1", execution_intent_id="ei1", reconciliation_id="rec1",
            tenant_id="t1", reason_codes=())
    comp = CompensationRequirement(
        compensation_id="c1", execution_intent_id="ei1", reconciliation_id="rec1",
        tenant_id="t1", reason_codes=("MISMATCH",),
        proposed_compensation_type=CompensationType.MANUAL_INTERVENTION)
    resolved = comp.resolved(by="ops-1", at=utc_now(), resolution_ref="ticket-9",
                             status=CompensationApprovalStatus.RESOLVED)
    assert resolved.revision == 2 and comp.revision == 1
    assert comp.approval_status is CompensationApprovalStatus.PROPOSED  # untouched


def test_no_execution_success_is_a_transport_status():
    # Transport and business outcomes are different enums; a transport ack is never
    # a business "SUCCEEDED".
    assert "SUCCEEDED" not in {s.value for s in TransportStatus}
    assert "ACKNOWLEDGED" not in {o.value for o in BusinessOutcome}
