"""AI-Assisted Hiring Framework — Phase 1 Foundation.

An isolated module implementing the *foundation* of the AI-Assisted Hiring
Framework: canonical data contracts, an audited workflow state machine, and the
hard, enforced separation between AI recommendations (advisory) and human
employment decisions (binding).

Core architectural invariant, enforced in types, services, persistence, and API
permissions — not merely documented:

    AI evaluates evidence and produces advisory recommendations.
    Only an authenticated human actor may create a binding employment decision.

This phase deliberately does *not* implement AI scoring, candidate ranking,
résumé evaluation, fairness models, assessment generation, or production
integrations. See ``docs/IMPLEMENTATION_STATUS.md`` for the full boundary.
"""

from __future__ import annotations

from dataclasses import dataclass

from .policies.decision_boundary import IdentityProvider, StaticIdentityProvider
from .repositories.in_memory import (
    InMemoryAuditRepository,
    InMemoryDecisionRepository,
    InMemoryEvaluationRepository,
    InMemoryEvidenceRepository,
    InMemoryRecommendationRepository,
    InMemoryWorkflowRepository,
)
from .services import (
    AuditService,
    DecisionService,
    EvaluationService,
    RecommendationService,
    WorkflowService,
)

__version__ = "0.1.0"

__all__ = [
    "HiringPlatform",
    "build_in_memory_platform",
    "__version__",
]


@dataclass
class HiringPlatform:
    """A fully-wired set of repositories and services for the foundation phase.

    Bundles the in-memory adapters and the services that depend on them. Use
    :func:`build_in_memory_platform` to construct one for development or tests;
    swap the repositories for production adapters in a later phase.
    """

    identity_provider: IdentityProvider
    evidence_repo: InMemoryEvidenceRepository
    evaluation_repo: InMemoryEvaluationRepository
    recommendation_repo: InMemoryRecommendationRepository
    decision_repo: InMemoryDecisionRepository
    workflow_repo: InMemoryWorkflowRepository
    audit_repo: InMemoryAuditRepository
    audit_service: AuditService
    evaluation_service: EvaluationService
    workflow_service: WorkflowService
    recommendation_service: RecommendationService
    decision_service: DecisionService

    def build_api(self):
        """Construct the callable :class:`~ai_hiring.api.HiringAPI` facade."""
        from .api.routes import HiringAPI

        return HiringAPI(
            evaluation_service=self.evaluation_service,
            recommendation_service=self.recommendation_service,
            decision_service=self.decision_service,
            workflow_service=self.workflow_service,
            audit_service=self.audit_service,
            identity_provider=self.identity_provider,
        )


def build_in_memory_platform(
    identity_provider: IdentityProvider | None = None,
) -> HiringPlatform:
    """Wire an in-memory platform with dependency-injected repositories.

    A ``StaticIdentityProvider`` is used by default; register humans, AI, and
    service principals on it (or pass your own provider) to exercise the
    authorization boundary.
    """
    identity = identity_provider or StaticIdentityProvider()

    evidence_repo = InMemoryEvidenceRepository()
    evaluation_repo = InMemoryEvaluationRepository()
    recommendation_repo = InMemoryRecommendationRepository()
    decision_repo = InMemoryDecisionRepository()
    workflow_repo = InMemoryWorkflowRepository()
    audit_repo = InMemoryAuditRepository()

    audit_service = AuditService(audit_repo)
    evaluation_service = EvaluationService(evaluation_repo, audit_service)
    workflow_service = WorkflowService(workflow_repo, audit_service)
    recommendation_service = RecommendationService(
        recommendation_repo, evaluation_repo, audit_service
    )
    decision_service = DecisionService(
        decision_repo,
        recommendation_repo,
        evaluation_repo,
        workflow_service,
        audit_service,
        identity,
    )

    return HiringPlatform(
        identity_provider=identity,
        evidence_repo=evidence_repo,
        evaluation_repo=evaluation_repo,
        recommendation_repo=recommendation_repo,
        decision_repo=decision_repo,
        workflow_repo=workflow_repo,
        audit_repo=audit_repo,
        audit_service=audit_service,
        evaluation_service=evaluation_service,
        workflow_service=workflow_service,
        recommendation_service=recommendation_service,
        decision_service=decision_service,
    )
