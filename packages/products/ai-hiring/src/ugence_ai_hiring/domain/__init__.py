"""Domain layer: immutable, validated contracts and enumerations.

The domain layer is intentionally free of service, repository, and web-framework
coupling. It depends only on pydantic (the repository's established validation
library) and the stdlib helpers in :mod:`ugence_ai_hiring.common`.
"""

from __future__ import annotations

from .audit import AuditEvent
from .base import DomainModel
from .decision import Approval, Decision, Override
from .enums import (
    ActorType,
    AuditEventType,
    CapabilityLayer,
    ConfidenceLevel,
    Disposition,
    EvaluationStatus,
    WorkflowState,
)
from .evaluation import (
    CandidateEvaluation,
    FairnessReport,
    Gap,
    LayerScore,
    Limitation,
    ReasonCode,
    WeightedSummary,
)
from .evidence import EvidenceRef, NormalizedEvidence
from .recommendation import Recommendation
from .workflow import CandidateWorkflow

__all__ = [
    "DomainModel",
    # enums
    "ActorType",
    "AuditEventType",
    "CapabilityLayer",
    "ConfidenceLevel",
    "Disposition",
    "EvaluationStatus",
    "WorkflowState",
    # evidence
    "EvidenceRef",
    "NormalizedEvidence",
    # evaluation
    "CandidateEvaluation",
    "FairnessReport",
    "Gap",
    "LayerScore",
    "Limitation",
    "ReasonCode",
    "WeightedSummary",
    # recommendation / decision
    "Recommendation",
    "Approval",
    "Decision",
    "Override",
    # workflow / audit
    "CandidateWorkflow",
    "AuditEvent",
]
