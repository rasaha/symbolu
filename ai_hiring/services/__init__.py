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
]

from .ontology_service import OntologyService
from .rubric_service import RubricService
from .rubric_validation_service import RubricValidationService
