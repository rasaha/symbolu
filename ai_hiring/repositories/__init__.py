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
    # Phase 3B: deterministic assessment runtime
    "AssessmentWorkspaceRepository",
    "InMemoryAssessmentWorkspaceRepository",
    "AssessmentRepository",
    "InMemoryAssessmentRepository",
]

from .assessment_repository import (
    AssessmentRepository,
    InMemoryAssessmentRepository,
)
from .assessment_workspace_repository import (
    AssessmentWorkspaceRepository,
    InMemoryAssessmentWorkspaceRepository,
)
