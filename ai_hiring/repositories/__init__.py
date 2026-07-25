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
    # Phase 4A: DecisionCase aggregate & lifecycle
    "DecisionCaseRepository",
    "InMemoryDecisionCaseRepository",
    # Phase 4B: governed action request & CER binding
    "ActionRequestRepository",
    "InMemoryActionRequestRepository",
]

from .assessment_repository import (
    AssessmentRepository,
    InMemoryAssessmentRepository,
)
from .assessment_workspace_repository import (
    AssessmentWorkspaceRepository,
    InMemoryAssessmentWorkspaceRepository,
)
from .decision_case_repository import (
    DecisionCaseRepository,
    InMemoryDecisionCaseRepository,
)
from .action_request_repository import (
    ActionRequestRepository,
    InMemoryActionRequestRepository,
)
