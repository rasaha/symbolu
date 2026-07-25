"""Canonical enumerations for the AI-Assisted Hiring module.

All enums subclass ``str`` for stable, human-readable serialization (mirroring
the repository's ``agentic.governance_models`` convention). The ten capability
layers are fixed identifiers; role-specific weighting is a later phase and does
not change this set.
"""

from __future__ import annotations

from enum import Enum


class ActorType(str, Enum):
    """Who is acting. The AI/human split is load-bearing across the module."""

    AI = "AI"
    HUMAN = "HUMAN"
    SYSTEM = "SYSTEM"


class WorkflowState(str, Enum):
    """Canonical end-to-end hiring workflow states."""

    PLANNED = "PLANNED"
    SOURCED = "SOURCED"
    ASSESSING = "ASSESSING"
    EVALUATED = "EVALUATED"
    IN_REVIEW = "IN_REVIEW"
    ADVANCED = "ADVANCED"
    HOLD = "HOLD"
    REJECTED = "REJECTED"
    OFFERED = "OFFERED"
    ONBOARDED = "ONBOARDED"


class Disposition(str, Enum):
    """A human review outcome."""

    ADVANCE = "ADVANCE"
    HOLD = "HOLD"
    REJECT = "REJECT"


class EvaluationStatus(str, Enum):
    """Whether an evaluation is clean or held back by the fairness gate."""

    EVALUATED = "EVALUATED"
    REVIEW_BLOCKED = "REVIEW_BLOCKED"


class ConfidenceLevel(str, Enum):
    """How much the system trusts its own layer score.

    A low confidence is a signal to the human reviewer, never a reason to lower
    a score. Calibration of these levels is a later phase.
    """

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class CapabilityLayer(str, Enum):
    """The ten fixed evaluation layers.

    Definition order is the canonical order (layer numbers 1..10); use
    :meth:`ordered` and :attr:`layer_number` rather than hard-coding indices.
    """

    EXECUTION = "EXECUTION"
    QUALIFICATION_AND_IDENTITY = "QUALIFICATION_AND_IDENTITY"
    WORK_PRODUCT_STRUCTURE = "WORK_PRODUCT_STRUCTURE"
    ADAPTIVE_COGNITION = "ADAPTIVE_COGNITION"
    AGENCY_AND_DECISION_OWNERSHIP = "AGENCY_AND_DECISION_OWNERSHIP"
    REASONING_AND_ANALYSIS = "REASONING_AND_ANALYSIS"
    ROLE_PURPOSE = "ROLE_PURPOSE"
    REFLECTION_AND_SELF_CORRECTION = "REFLECTION_AND_SELF_CORRECTION"
    PROFESSIONAL_COHERENCE = "PROFESSIONAL_COHERENCE"
    SYSTEM_AND_STAKEHOLDER_RESPONSIBILITY = "SYSTEM_AND_STAKEHOLDER_RESPONSIBILITY"

    @classmethod
    def ordered(cls) -> tuple["CapabilityLayer", ...]:
        """Return all ten layers in canonical order."""
        return tuple(cls)

    @property
    def layer_number(self) -> int:
        """1-based canonical position of this layer (1..10)."""
        return list(CapabilityLayer).index(self) + 1


class AuditEventType(str, Enum):
    """The kinds of events written to the append-only audit log."""

    WORKFLOW_INITIALIZED = "WORKFLOW_INITIALIZED"
    WORKFLOW_TRANSITION = "WORKFLOW_TRANSITION"
    EVALUATION_CREATED = "EVALUATION_CREATED"
    EVALUATION_UNBLOCKED = "EVALUATION_UNBLOCKED"
    RECOMMENDATION_CREATED = "RECOMMENDATION_CREATED"
    DECISION_CREATED = "DECISION_CREATED"
    POLICY_DENIED = "POLICY_DENIED"
    SECURITY_VIOLATION = "SECURITY_VIOLATION"
    # --- Phase 2: evidence ingestion & normalization (additive) ---
    EVIDENCE_UPLOAD_RECEIVED = "EVIDENCE_UPLOAD_RECEIVED"
    EVIDENCE_INTEGRITY_VALIDATED = "EVIDENCE_INTEGRITY_VALIDATED"
    EVIDENCE_PROVENANCE_CAPTURED = "EVIDENCE_PROVENANCE_CAPTURED"
    EVIDENCE_CONTENT_HASHED = "EVIDENCE_CONTENT_HASHED"
    EVIDENCE_CONTENT_EXTRACTED = "EVIDENCE_CONTENT_EXTRACTED"
    EVIDENCE_NORMALIZED = "EVIDENCE_NORMALIZED"
    EVIDENCE_PII_QUARANTINED = "EVIDENCE_PII_QUARANTINED"
    EVIDENCE_CHUNK_CREATED = "EVIDENCE_CHUNK_CREATED"
    EVIDENCE_VERSION_CREATED = "EVIDENCE_VERSION_CREATED"
    EVIDENCE_INDEXED = "EVIDENCE_INDEXED"
    EVIDENCE_DUPLICATE_DETECTED = "EVIDENCE_DUPLICATE_DETECTED"
    # --- Phase 2.5: evidence boundary hardening (additive) ---
    EVIDENCE_EXTRACTION_SUCCEEDED = "EVIDENCE_EXTRACTION_SUCCEEDED"
    EVIDENCE_EXTRACTION_WARNING = "EVIDENCE_EXTRACTION_WARNING"
    EVIDENCE_EXTRACTION_EMPTY = "EVIDENCE_EXTRACTION_EMPTY"
    EVIDENCE_EXTRACTION_UNSUPPORTED = "EVIDENCE_EXTRACTION_UNSUPPORTED"
    EVIDENCE_EXTRACTION_MALFORMED = "EVIDENCE_EXTRACTION_MALFORMED"
    EVIDENCE_EXTRACTION_ENCRYPTED = "EVIDENCE_EXTRACTION_ENCRYPTED"
    EVIDENCE_RESOURCE_LIMIT_EXCEEDED = "EVIDENCE_RESOURCE_LIMIT_EXCEEDED"
    EVIDENCE_INTEGRITY_FAILED = "EVIDENCE_INTEGRITY_FAILED"
    EVIDENCE_ELIGIBILITY_BLOCKED = "EVIDENCE_ELIGIBILITY_BLOCKED"
    EVIDENCE_MANUAL_REVIEW_REQUIRED = "EVIDENCE_MANUAL_REVIEW_REQUIRED"
    EVIDENCE_ACCESS_DENIED = "EVIDENCE_ACCESS_DENIED"
    EVIDENCE_LINEAGE_VALIDATED = "EVIDENCE_LINEAGE_VALIDATED"
    EVIDENCE_LINEAGE_REJECTED = "EVIDENCE_LINEAGE_REJECTED"
    EVIDENCE_RECONSTRUCTION_VALIDATED = "EVIDENCE_RECONSTRUCTION_VALIDATED"
    EVIDENCE_RECONSTRUCTION_FAILED = "EVIDENCE_RECONSTRUCTION_FAILED"
    EVIDENCE_DUPLICATE_CLASSIFIED = "EVIDENCE_DUPLICATE_CLASSIFIED"
    EVIDENCE_INGESTION_RECEIVED = "EVIDENCE_INGESTION_RECEIVED"
    EVIDENCE_INGESTION_COMPLETED = "EVIDENCE_INGESTION_COMPLETED"
    EVIDENCE_INGESTION_FAILED = "EVIDENCE_INGESTION_FAILED"
