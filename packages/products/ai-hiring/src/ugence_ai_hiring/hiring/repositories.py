"""Hiring-domain repositories — canonical import surface.

Re-exports the hiring-domain in-memory repository adapters. These are the
*hiring* record stores (evidence, evaluation, recommendation, decision,
workflow, provenance, ontology, rubric, assessment). The governance-chain
repositories (DecisionCase / ActionRequest / Execution) are domain-neutral and
belong to the kernel — import those from ``ugence_decision_authority.repositories``,
not here.

The implementations live physically under ``ugence_ai_hiring.repositories`` (retained
for import stability); this module is the canonical place for hiring-domain and
application code to import them, and preserves object identity.
"""

from __future__ import annotations

from ugence_ai_hiring.repositories.in_memory import (
    InMemoryDecisionRepository,
    InMemoryEvaluationRepository,
    InMemoryEvidenceRepository,
    InMemoryRecommendationRepository,
    InMemoryWorkflowRepository,
)
from ugence_ai_hiring.repositories.evidence_artifacts import (
    InMemoryChunkRepository,
    InMemoryLineageRepository,
    InMemoryProvenanceRepository,
    InMemoryQuarantineRepository,
)
from ugence_ai_hiring.repositories.evidence_index_repository import (
    InMemoryEvidenceIndexRepository,
)
from ugence_ai_hiring.repositories.ontology_repository import InMemoryOntologyRepository
from ugence_ai_hiring.repositories.rubric_repository import InMemoryRubricRepository
from ugence_ai_hiring.repositories.assessment_repository import InMemoryAssessmentRepository
from ugence_ai_hiring.repositories.assessment_workspace_repository import (
    InMemoryAssessmentWorkspaceRepository,
)

__all__ = [
    "InMemoryEvidenceRepository",
    "InMemoryEvaluationRepository",
    "InMemoryRecommendationRepository",
    "InMemoryDecisionRepository",
    "InMemoryWorkflowRepository",
    "InMemoryProvenanceRepository",
    "InMemoryChunkRepository",
    "InMemoryQuarantineRepository",
    "InMemoryLineageRepository",
    "InMemoryEvidenceIndexRepository",
    "InMemoryOntologyRepository",
    "InMemoryRubricRepository",
    "InMemoryAssessmentRepository",
    "InMemoryAssessmentWorkspaceRepository",
]
