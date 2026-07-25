"""Enumerations for the deterministic assessment runtime (Phase 3B).

These describe *structural* lifecycle and completeness — never candidate quality.
Nothing here scores, ranks, recommends, or decides.
"""

from __future__ import annotations

from enum import Enum


class WorkspaceStatus(str, Enum):
    """Lifecycle of an assessment workspace / its finalized assessment."""

    CREATED = "CREATED"
    EVIDENCE_BINDING = "EVIDENCE_BINDING"
    READY_FOR_OBSERVATIONS = "READY_FOR_OBSERVATIONS"
    IN_PROGRESS = "IN_PROGRESS"
    VALIDATION_FAILED = "VALIDATION_FAILED"
    STRUCTURALLY_COMPLETE = "STRUCTURALLY_COMPLETE"
    FINALIZED_ADVISORY = "FINALIZED_ADVISORY"
    SUPERSEDED = "SUPERSEDED"
    CANCELLED = "CANCELLED"


class AssessmentStatus(str, Enum):
    """Status of a finalized assessment snapshot."""

    FINALIZED_ADVISORY = "FINALIZED_ADVISORY"
    SUPERSEDED = "SUPERSEDED"
    CANCELLED = "CANCELLED"


class CompletenessStatus(str, Enum):
    """Structural completeness — NOT a quality judgement."""

    NOT_STARTED = "NOT_STARTED"
    INCOMPLETE = "INCOMPLETE"
    COMPLETE_WITH_UNCERTAINTY = "COMPLETE_WITH_UNCERTAINTY"
    COMPLETE_WITH_CONFLICTS = "COMPLETE_WITH_CONFLICTS"
    COMPLETE = "COMPLETE"
    BLOCKED = "BLOCKED"


class BindingProvenance(str, Enum):
    """How an evidence binding was produced. No AI_INFERRED in Phase 3B."""

    MANUAL_AUTHORIZED = "MANUAL_AUTHORIZED"
    DETERMINISTIC_RULE = "DETERMINISTIC_RULE"
    APPROVED_MAPPING = "APPROVED_MAPPING"
    SYSTEM_REQUIRED = "SYSTEM_REQUIRED"


class SupplierType(str, Enum):
    """Who supplied an observation. AI_MODEL is representable but rejected in 3B."""

    HUMAN_ASSESSOR = "HUMAN_ASSESSOR"
    DETERMINISTIC_SYSTEM = "DETERMINISTIC_SYSTEM"
    IMPORTED_APPROVED_RECORD = "IMPORTED_APPROVED_RECORD"
    AI_MODEL = "AI_MODEL"  # rejected by validation in Phase 3B (no inference)


class ObservationValidationStatus(str, Enum):
    VALID = "VALID"
    INVALID = "INVALID"


# Supplier types permitted to supply observations in Phase 3B (AI is excluded).
PERMITTED_SUPPLIERS = frozenset(
    {SupplierType.HUMAN_ASSESSOR, SupplierType.DETERMINISTIC_SYSTEM,
     SupplierType.IMPORTED_APPROVED_RECORD}
)