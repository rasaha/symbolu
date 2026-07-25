"""Public API — governance record models and their controlled enums.

The immutable governance contracts and the frozen status / outcome / authority
vocabularies. The per-package lifecycle transition tables and internal helper
constants (``ALLOWED_TRANSITIONS``, ``is_legal_transition``, …) are *not* flattened
here — they are enforced inside the services and remain available on the internal
modules for advanced use; the lifecycle itself is frozen (see
``decision_governance.version``).
"""

from __future__ import annotations

from ..base import DomainModel
from ..ports.linked_record import LinkedRecordSnapshot

# --- Decision-case chain (Phase 4A) ----------------------------------------
from ..decisions import (
    AuthorityContext,
    AuthorityType,
    CaseStatus,
    CaseValidationIssue,
    CaseValidationResult,
    DecisionCase,
    DecisionOutcome,
    DecisionReadinessResult,
    DecisionRecord,
    EffectiveStatus,
    GeneratorType,
    OperatingMode,
    OverrideRecord,
    ProposedOutcome,
    RecommendationRecord,
    RecommendationStatus,
    ReviewTask,
    ReviewTaskStatus,
    ReviewTaskType,
    SubjectRef,
    VersionedRef,
)

# --- Action-request chain (Phase 4B) ---------------------------------------
from ..actions import (
    ActionAuthorizationResponse,
    ActionMapping,
    ActionMappingStatus,
    ActionRequest,
    ActionRequestStatus,
    ActionRequestValidationIssue,
    ActionRequestValidationResult,
    AuthoritySummary,
    AuthorizationOutcome,
    ContextEnvelopeRecord,
    DecisionContext,
    ParameterSchema,
    PolicyContext,
    SubjectContext,
)

# --- Execution chain (Phase 4C) --------------------------------------------
from ..execution import (
    BusinessOutcome,
    CompensationApprovalStatus,
    CompensationRequirement,
    CompensationType,
    ExecutionAttempt,
    ExecutionIntent,
    ExecutionRecord,
    ExecutionStatus,
    ExecutionValidationIssue,
    ExecutionValidationResult,
    Finality,
    OutcomeSource,
    ReconciliationResult,
    ReconciliationStatus,
    RetryClassification,
    TransportStatus,
)

__all__ = [
    "DomainModel",
    "LinkedRecordSnapshot",
    # decision-case records
    "DecisionCase",
    "RecommendationRecord",
    "DecisionRecord",
    "OverrideRecord",
    "ReviewTask",
    "AuthorityContext",
    "SubjectRef",
    "VersionedRef",
    "CaseValidationIssue",
    "CaseValidationResult",
    "DecisionReadinessResult",
    # decision-case enums
    "CaseStatus",
    "OperatingMode",
    "ProposedOutcome",
    "GeneratorType",
    "RecommendationStatus",
    "DecisionOutcome",
    "AuthorityType",
    "EffectiveStatus",
    "ReviewTaskType",
    "ReviewTaskStatus",
    # action-request records
    "ActionRequest",
    "ActionMapping",
    "ParameterSchema",
    "ContextEnvelopeRecord",
    "SubjectContext",
    "AuthoritySummary",
    "PolicyContext",
    "DecisionContext",
    "ActionAuthorizationResponse",
    "ActionRequestValidationIssue",
    "ActionRequestValidationResult",
    # action-request enums
    "ActionRequestStatus",
    "AuthorizationOutcome",
    "ActionMappingStatus",
    # execution records
    "ExecutionIntent",
    "ExecutionAttempt",
    "ExecutionRecord",
    "ReconciliationResult",
    "CompensationRequirement",
    "ExecutionValidationIssue",
    "ExecutionValidationResult",
    # execution enums
    "ExecutionStatus",
    "TransportStatus",
    "BusinessOutcome",
    "ReconciliationStatus",
    "RetryClassification",
    "CompensationType",
    "CompensationApprovalStatus",
    "Finality",
    "OutcomeSource",
]
