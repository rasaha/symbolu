"""External execution, immutable execution records, and outcome reconciliation
(Phase 4C).

Takes a valid, unexpired, control-plane-authorized ``ActionRequest``, dispatches it
through a provider-neutral external-execution port, records every attempt
immutably, and reconciles the *observed* external result against the authorized
intent.

Phase 4C records what was attempted and what the external system actually did.
**Dispatch, acknowledgement, authorization, and business success are distinct
states.**
"""

from __future__ import annotations

from .compensation import CompensationRequirement
from .execution_attempt import ExecutionAttempt
from .execution_intent import ExecutionIntent
from .execution_record import ExecutionRecord
from .external_system import (
    ExternalDispatchResponse,
    ExternalExecutionPort,
    ExternalStatusResponse,
    OfflineDeterministicExecutionAdapter,
)
from .lifecycle import ALLOWED_TRANSITIONS, is_legal_transition
from .reconciliation import ReconciliationResult
from .status import (
    BUSINESS_OUTCOME_TO_STATUS,
    BusinessOutcome,
    CompensationApprovalStatus,
    CompensationType,
    EXECUTABLE_AUTHORIZATION_OUTCOMES,
    ExecutionStatus,
    Finality,
    OutcomeSource,
    ReconciliationStatus,
    RetryClassification,
    TERMINAL_EXECUTION_STATUSES,
    TransportStatus,
)
from .validation import ExecutionValidationIssue, ExecutionValidationResult

__all__ = [
    # contracts
    "ExecutionIntent",
    "ExecutionAttempt",
    "ExecutionRecord",
    "ReconciliationResult",
    "CompensationRequirement",
    # external system
    "ExternalExecutionPort",
    "ExternalDispatchResponse",
    "ExternalStatusResponse",
    "OfflineDeterministicExecutionAdapter",
    # vocabularies
    "ExecutionStatus",
    "TransportStatus",
    "BusinessOutcome",
    "ReconciliationStatus",
    "RetryClassification",
    "CompensationType",
    "CompensationApprovalStatus",
    "Finality",
    "OutcomeSource",
    "BUSINESS_OUTCOME_TO_STATUS",
    "EXECUTABLE_AUTHORIZATION_OUTCOMES",
    "TERMINAL_EXECUTION_STATUSES",
    # lifecycle + validation
    "ALLOWED_TRANSITIONS",
    "is_legal_transition",
    "ExecutionValidationIssue",
    "ExecutionValidationResult",
]
