"""Deterministic vocabularies for external execution & reconciliation (Phase 4C).

These enums name states and outcomes only. The central distinction they encode:
**authorization, dispatch, transport acknowledgement, and business success are
four different things.** Dispatch is not success; a transport ack is not business
completion; a timeout is not a failure.
"""

from __future__ import annotations

from enum import Enum

from ..action_requests.status import AuthorizationOutcome

#: Only these control-plane outcomes may permit an execution intent.
EXECUTABLE_AUTHORIZATION_OUTCOMES = frozenset({
    AuthorizationOutcome.AUTHORIZED,
    AuthorizationOutcome.AUTHORIZED_WITH_CONSTRAINTS,
})


class ExecutionStatus(str, Enum):
    """Lifecycle state of an execution. Dispatch/ack/success are distinct states."""

    INTENT_CREATED = "INTENT_CREATED"
    READY_FOR_DISPATCH = "READY_FOR_DISPATCH"
    DISPATCH_PENDING = "DISPATCH_PENDING"
    DISPATCHED = "DISPATCHED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    OUTCOME_UNKNOWN = "OUTCOME_UNKNOWN"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    PARTIALLY_SUCCEEDED = "PARTIALLY_SUCCEEDED"
    REJECTED = "REJECTED"
    RECONCILIATION_PENDING = "RECONCILIATION_PENDING"
    RECONCILED = "RECONCILED"
    MISMATCHED = "MISMATCHED"
    COMPENSATION_REQUIRED = "COMPENSATION_REQUIRED"
    MANUAL_REVIEW_REQUIRED = "MANUAL_REVIEW_REQUIRED"
    CANCELLED = "CANCELLED"
    SUPERSEDED = "SUPERSEDED"


#: States after which an execution snapshot is finalized and never mutated.
TERMINAL_EXECUTION_STATUSES = frozenset({
    ExecutionStatus.CANCELLED, ExecutionStatus.SUPERSEDED,
})


class TransportStatus(str, Enum):
    """The *transport* result of a dispatch — never a business outcome."""

    NOT_DISPATCHED = "NOT_DISPATCHED"
    DISPATCHED = "DISPATCHED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    TRANSPORT_FAILED = "TRANSPORT_FAILED"
    TIMED_OUT = "TIMED_OUT"
    UNKNOWN = "UNKNOWN"


class BusinessOutcome(str, Enum):
    """The *observed external-world* result — recorded, never inferred from dispatch."""

    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    PARTIALLY_SUCCEEDED = "PARTIALLY_SUCCEEDED"
    REJECTED = "REJECTED"
    CANCELLED_EXTERNALLY = "CANCELLED_EXTERNALLY"
    DUPLICATE = "DUPLICATE"
    UNKNOWN = "UNKNOWN"


#: Deterministic map from an observed business outcome to the execution status.
BUSINESS_OUTCOME_TO_STATUS: dict[BusinessOutcome, ExecutionStatus] = {
    BusinessOutcome.SUCCEEDED: ExecutionStatus.SUCCEEDED,
    BusinessOutcome.FAILED: ExecutionStatus.FAILED,
    BusinessOutcome.PARTIALLY_SUCCEEDED: ExecutionStatus.PARTIALLY_SUCCEEDED,
    BusinessOutcome.REJECTED: ExecutionStatus.REJECTED,
    BusinessOutcome.CANCELLED_EXTERNALLY: ExecutionStatus.FAILED,
    BusinessOutcome.DUPLICATE: ExecutionStatus.MANUAL_REVIEW_REQUIRED,
    BusinessOutcome.UNKNOWN: ExecutionStatus.OUTCOME_UNKNOWN,
}


class Finality(str, Enum):
    """Whether an observed outcome is final or may still change."""

    FINAL = "FINAL"
    NON_FINAL = "NON_FINAL"
    UNKNOWN = "UNKNOWN"


class ReconciliationStatus(str, Enum):
    RECONCILED = "RECONCILED"
    MISMATCHED = "MISMATCHED"
    PARTIALLY_RECONCILED = "PARTIALLY_RECONCILED"
    INDETERMINATE = "INDETERMINATE"
    MANUAL_REVIEW_REQUIRED = "MANUAL_REVIEW_REQUIRED"
    COMPENSATION_REQUIRED = "COMPENSATION_REQUIRED"


class RetryClassification(str, Enum):
    """How safe a retry is. A retry never happens without an explicit classification."""

    IDEMPOTENT_SAFE = "IDEMPOTENT_SAFE"
    REQUIRES_APPROVAL = "REQUIRES_APPROVAL"
    UNSAFE = "UNSAFE"
    NOT_RETRYABLE = "NOT_RETRYABLE"


class CompensationType(str, Enum):
    REVERSAL = "REVERSAL"
    MANUAL_INTERVENTION = "MANUAL_INTERVENTION"
    GOVERNED_ACTION_REQUEST = "GOVERNED_ACTION_REQUEST"
    NONE_POSSIBLE = "NONE_POSSIBLE"


class CompensationApprovalStatus(str, Enum):
    PROPOSED = "PROPOSED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    RESOLVED = "RESOLVED"


class OutcomeSource(str, Enum):
    """Where an observed outcome came from — never fabricated by this phase."""

    ADAPTER_DISPATCH = "ADAPTER_DISPATCH"
    ADAPTER_STATUS_QUERY = "ADAPTER_STATUS_QUERY"
    EXTERNAL_CALLBACK = "EXTERNAL_CALLBACK"
    MANUAL_ENTRY = "MANUAL_ENTRY"
