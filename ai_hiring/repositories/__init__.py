"""Repository layer: ports (interfaces) and in-memory adapters."""

from __future__ import annotations

from .in_memory import (
    InMemoryAuditRepository,
    InMemoryDecisionRepository,
    InMemoryEvaluationRepository,
    InMemoryEvidenceRepository,
    InMemoryRecommendationRepository,
    InMemoryWorkflowRepository,
)
from .interfaces import (
    AuditRepository,
    DecisionRepository,
    EvaluationRepository,
    EvidenceRepository,
    RecommendationRepository,
    WorkflowRepository,
)

__all__ = [
    # ports
    "EvidenceRepository",
    "EvaluationRepository",
    "RecommendationRepository",
    "DecisionRepository",
    "WorkflowRepository",
    "AuditRepository",
    # in-memory adapters
    "InMemoryEvidenceRepository",
    "InMemoryEvaluationRepository",
    "InMemoryRecommendationRepository",
    "InMemoryDecisionRepository",
    "InMemoryWorkflowRepository",
    "InMemoryAuditRepository",
]
