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
from .repositories.evidence_artifacts import (
    InMemoryChunkRepository,
    InMemoryLineageRepository,
    InMemoryProvenanceRepository,
    InMemoryQuarantineRepository,
)
from .repositories.evidence_index_repository import InMemoryEvidenceIndexRepository
from .repositories.in_memory import (
    InMemoryAuditRepository,
    InMemoryDecisionRepository,
    InMemoryEvaluationRepository,
    InMemoryEvidenceRepository,
    InMemoryRecommendationRepository,
    InMemoryWorkflowRepository,
)
from .policies.evidence_access_policy import EvidenceAccessPolicy, GrantStore
from .repositories.ontology_repository import InMemoryOntologyRepository
from .repositories.rubric_repository import InMemoryRubricRepository
from .repositories.assessment_repository import InMemoryAssessmentRepository
from .repositories.assessment_workspace_repository import (
    InMemoryAssessmentWorkspaceRepository,
)
from .repositories.decision_case_repository import InMemoryDecisionCaseRepository
from .repositories.action_request_repository import InMemoryActionRequestRepository
from .action_requests.control_plane import (
    ActionControlPlanePort,
    OfflineDeterministicControlPlane,
)
from .services import (
    ActionAuthorizationService,
    ActionRequestService,
    ActionRequestValidationService,
    AssessmentCompletenessService,
    AssessmentService,
    AssessmentValidationService,
    AuditService,
    CaseDecisionService,
    CaseRecommendationService,
    CaseValidationService,
    CERBindingService,
    DecisionCaseService,
    DecisionService,
    EvaluationService,
    EvidenceAccessService,
    EvidenceBindingService,
    EvidenceIngestionService,
    EvidenceValidationService,
    OntologyService,
    ProvenanceService,
    RecommendationService,
    RubricService,
    RubricValidationService,
    SearchService,
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
    # --- Phase 2: evidence ingestion & normalization ---
    provenance_repo: InMemoryProvenanceRepository
    chunk_repo: InMemoryChunkRepository
    quarantine_repo: InMemoryQuarantineRepository
    lineage_repo: InMemoryLineageRepository
    evidence_index_repo: InMemoryEvidenceIndexRepository
    evidence_ingestion_service: EvidenceIngestionService
    search_service: SearchService
    provenance_service: ProvenanceService
    # --- Phase 2.5: evidence boundary hardening ---
    access_grants: GrantStore
    evidence_access_policy: EvidenceAccessPolicy
    evidence_validation_service: EvidenceValidationService
    evidence_access_service: EvidenceAccessService
    # --- Phase 3A: capability ontology & rubric contracts ---
    ontology_repo: InMemoryOntologyRepository
    rubric_repo: InMemoryRubricRepository
    ontology_service: OntologyService
    rubric_validation_service: RubricValidationService
    rubric_service: RubricService
    # --- Phase 3B: deterministic assessment runtime ---
    assessment_workspace_repo: InMemoryAssessmentWorkspaceRepository
    assessment_repo: InMemoryAssessmentRepository
    evidence_binding_service: EvidenceBindingService
    assessment_validation_service: AssessmentValidationService
    assessment_completeness_service: AssessmentCompletenessService
    assessment_service: AssessmentService
    # --- Phase 4A: DecisionCase aggregate & lifecycle ---
    decision_case_repo: InMemoryDecisionCaseRepository
    case_validation_service: CaseValidationService
    decision_case_service: DecisionCaseService
    case_recommendation_service: CaseRecommendationService
    case_decision_service: CaseDecisionService
    # --- Phase 4B: governed action request & CER binding ---
    action_request_repo: InMemoryActionRequestRepository
    control_plane: ActionControlPlanePort
    action_request_validation_service: ActionRequestValidationService
    action_request_service: ActionRequestService
    cer_binding_service: CERBindingService
    action_authorization_service: ActionAuthorizationService

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
            evidence_ingestion_service=self.evidence_ingestion_service,
            search_service=self.search_service,
            provenance_service=self.provenance_service,
            evidence_access_service=self.evidence_access_service,
            evidence_validation_service=self.evidence_validation_service,
        )

    def build_ontology_api(self):
        """Construct the callable :class:`~ai_hiring.api.OntologyAPI` facade."""
        from .api.ontology_routes import OntologyAPI

        return OntologyAPI(self.ontology_service, self.identity_provider)

    def build_rubric_api(self):
        """Construct the callable :class:`~ai_hiring.api.RubricAPI` facade."""
        from .api.rubric_routes import RubricAPI

        return RubricAPI(self.rubric_service, self.identity_provider)

    def build_assessment_api(self):
        """Construct the callable :class:`~ai_hiring.api.AssessmentAPI` facade."""
        from .api.assessment_routes import AssessmentAPI

        return AssessmentAPI(self.assessment_service, self.identity_provider)

    def build_decision_case_api(self):
        """Construct the callable :class:`~ai_hiring.api.DecisionCaseAPI` facade."""
        from .api.decision_case_routes import DecisionCaseAPI

        return DecisionCaseAPI(
            self.decision_case_service,
            self.case_recommendation_service,
            self.case_decision_service,
            self.identity_provider,
        )

    def build_action_request_api(self):
        """Construct the callable :class:`~ai_hiring.api.ActionRequestAPI` facade."""
        from .api.action_request_routes import ActionRequestAPI

        return ActionRequestAPI(
            self.action_request_service,
            self.cer_binding_service,
            self.action_authorization_service,
            self.identity_provider,
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

    # Phase 2: evidence ingestion & normalization.
    provenance_repo = InMemoryProvenanceRepository()
    chunk_repo = InMemoryChunkRepository()
    quarantine_repo = InMemoryQuarantineRepository()
    lineage_repo = InMemoryLineageRepository()
    evidence_index_repo = InMemoryEvidenceIndexRepository()

    evidence_ingestion_service = EvidenceIngestionService(
        evidence_repo,
        provenance_repo,
        chunk_repo,
        quarantine_repo,
        lineage_repo,
        evidence_index_repo,
        audit_service,
    )
    search_service = SearchService(evidence_index_repo)
    provenance_service = ProvenanceService(provenance_repo, lineage_repo)

    # Phase 2.5: validation + authorization-aware access.
    access_grants = GrantStore()
    evidence_access_policy = EvidenceAccessPolicy(access_grants)
    evidence_validation_service = EvidenceValidationService(
        evidence_repo, provenance_repo, chunk_repo, quarantine_repo, lineage_repo,
        audit_service,
    )
    evidence_access_service = EvidenceAccessService(
        evidence_repo, provenance_repo, lineage_repo, quarantine_repo, evidence_index_repo,
        identity, evidence_access_policy, audit_service,
    )

    # Phase 3A: capability ontology & rubric contracts.
    ontology_repo = InMemoryOntologyRepository()
    rubric_repo = InMemoryRubricRepository()
    ontology_service = OntologyService(ontology_repo, audit_service)
    rubric_validation_service = RubricValidationService(ontology_repo)
    rubric_service = RubricService(rubric_repo, rubric_validation_service, audit_service)

    # Phase 3B: deterministic assessment runtime.
    assessment_workspace_repo = InMemoryAssessmentWorkspaceRepository()
    assessment_repo = InMemoryAssessmentRepository()
    evidence_binding_service = EvidenceBindingService(
        evidence_repo, evidence_validation_service
    )
    assessment_validation_service = AssessmentValidationService()
    assessment_completeness_service = AssessmentCompletenessService()
    assessment_service = AssessmentService(
        assessment_workspace_repo,
        assessment_repo,
        rubric_repo,
        ontology_repo,
        evidence_binding_service,
        assessment_validation_service,
        assessment_completeness_service,
        audit_service,
        identity,
        evidence_access_policy,
    )

    # Phase 4A: DecisionCase aggregate & lifecycle orchestration.
    decision_case_repo = InMemoryDecisionCaseRepository()
    case_validation_service = CaseValidationService(assessment_repo)
    decision_case_service = DecisionCaseService(
        decision_case_repo, case_validation_service, audit_service, identity,
        evidence_access_policy)
    case_recommendation_service = CaseRecommendationService(
        decision_case_repo, case_validation_service, audit_service, identity,
        evidence_access_policy)
    case_decision_service = CaseDecisionService(
        decision_case_repo, case_validation_service, audit_service, identity,
        evidence_access_policy)

    # Phase 4B: governed action request & CER binding.
    action_request_repo = InMemoryActionRequestRepository()
    control_plane = OfflineDeterministicControlPlane()
    action_request_validation_service = ActionRequestValidationService(
        action_request_repo, decision_case_repo)
    action_request_service = ActionRequestService(
        action_request_repo, decision_case_repo, action_request_validation_service,
        audit_service, identity, evidence_access_policy)
    cer_binding_service = CERBindingService(
        action_request_repo, decision_case_repo, audit_service, identity,
        evidence_access_policy)
    action_authorization_service = ActionAuthorizationService(
        action_request_repo, control_plane, audit_service, identity,
        evidence_access_policy)

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
        provenance_repo=provenance_repo,
        chunk_repo=chunk_repo,
        quarantine_repo=quarantine_repo,
        lineage_repo=lineage_repo,
        evidence_index_repo=evidence_index_repo,
        evidence_ingestion_service=evidence_ingestion_service,
        search_service=search_service,
        provenance_service=provenance_service,
        access_grants=access_grants,
        evidence_access_policy=evidence_access_policy,
        evidence_validation_service=evidence_validation_service,
        evidence_access_service=evidence_access_service,
        ontology_repo=ontology_repo,
        rubric_repo=rubric_repo,
        ontology_service=ontology_service,
        rubric_validation_service=rubric_validation_service,
        rubric_service=rubric_service,
        assessment_workspace_repo=assessment_workspace_repo,
        assessment_repo=assessment_repo,
        evidence_binding_service=evidence_binding_service,
        assessment_validation_service=assessment_validation_service,
        assessment_completeness_service=assessment_completeness_service,
        assessment_service=assessment_service,
        decision_case_repo=decision_case_repo,
        case_validation_service=case_validation_service,
        decision_case_service=decision_case_service,
        case_recommendation_service=case_recommendation_service,
        case_decision_service=case_decision_service,
        action_request_repo=action_request_repo,
        control_plane=control_plane,
        action_request_validation_service=action_request_validation_service,
        action_request_service=action_request_service,
        cer_binding_service=cer_binding_service,
        action_authorization_service=action_authorization_service,
    )
