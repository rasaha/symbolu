"""Service layer.

Services orchestrate domain contracts, policies, and repositories. They are the
only place that mutates state, and every mutation is validated at the boundary
and audited. Repositories and the identity provider are injected, so services
are framework- and storage-agnostic.
"""

from __future__ import annotations

from .audit_service import AuditService
from .decision_service import DecisionService
from .evaluation_service import EvaluationService
from .evidence_access_service import EvidenceAccessService
from .evidence_ingestion_service import EvidenceIngestionService
from .evidence_validation_service import EvidenceValidationService
from .provenance_service import ProvenanceService
from .recommendation_service import RecommendationService
from .search_service import SearchService
from .workflow_service import WorkflowService

__all__ = [
    "AuditService",
    "EvaluationService",
    "RecommendationService",
    "DecisionService",
    "WorkflowService",
    # Phase 2: evidence ingestion & normalization
    "EvidenceIngestionService",
    "SearchService",
    "ProvenanceService",
    # Phase 2.5: evidence boundary hardening
    "EvidenceValidationService",
    "EvidenceAccessService",
    # Phase 3A: capability ontology & rubric contracts
    "OntologyService",
    "RubricService",
    "RubricValidationService",
    # Phase 3B: deterministic assessment runtime
    "EvidenceBindingService",
    "AssessmentValidationService",
    "AssessmentCompletenessService",
    "AssessmentService",
    # Phase 4A: DecisionCase aggregate & lifecycle
    "DecisionCaseService",
    "CaseRecommendationService",
    "CaseDecisionService",
    "CaseValidationService",
    # Phase 4B: governed action request & CER binding
    "ActionRequestService",
    "CERBindingService",
    "ActionAuthorizationService",
    "ActionRequestValidationService",
]

from .ontology_service import OntologyService
from .rubric_service import RubricService
from .rubric_validation_service import RubricValidationService
from .assessment_completeness_service import AssessmentCompletenessService
from .assessment_service import AssessmentService
from .assessment_validation_service import AssessmentValidationService
from .evidence_binding_service import EvidenceBindingService
from .case_validation_service import CaseValidationService
from .decision_case_service import DecisionCaseService
from .case_recommendation_service import CaseRecommendationService
from .case_decision_service import CaseDecisionService
from .action_request_validation_service import ActionRequestValidationService
from .action_request_service import ActionRequestService
from .cer_binding_service import CERBindingService
from .action_authorization_service import ActionAuthorizationService
