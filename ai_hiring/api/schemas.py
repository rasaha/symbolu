"""API request/response schemas (DTOs).

Thin pydantic DTOs for the callable service interface. They carry no business
rules — validation of the underlying contracts happens in the domain models,
and enforcement happens in the policies/services. Every request carries a
``principal_id`` so the API layer can apply its authorization hook before
delegating.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict

from ..domain.decision import Approval, Override
from ..domain.enums import ActorType, CapabilityLayer, Disposition, WorkflowState
from ..domain.evaluation import CandidateEvaluation, Limitation
from ..normalization.models import RawSubmission


class _Request(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CreateEvaluationRequest(_Request):
    principal_id: str
    evaluation: CandidateEvaluation


class CreateRecommendationRequest(_Request):
    principal_id: str
    evaluation_id: str
    suggested_disposition: Disposition
    supporting_layers: tuple[CapabilityLayer, ...] = ()
    caveats: tuple[Limitation, ...] = ()


class CreateDecisionRequest(_Request):
    principal_id: str  # must resolve to an authenticated human
    recommendation_id: str
    disposition: Disposition
    panel: tuple[str, ...]
    rationale_job_related: str
    override: Optional[Override] = None
    approval: Optional[Approval] = None


class TransitionRequest(_Request):
    principal_id: str
    target: WorkflowState
    actor_type: ActorType = ActorType.HUMAN


# --- Phase 2: evidence ingestion & search ---------------------------------
class IngestEvidenceRequest(_Request):
    principal_id: str
    submission: "RawSubmission"
    parent_evidence_id: Optional[str] = None
    allow_duplicate: bool = False


class EvidenceSearchRequest(_Request):
    principal_id: str
    tenant_id: str = ""
    candidate_id: Optional[str] = None
    role_id: Optional[str] = None
    assessment_item_id: Optional[str] = None
    assessment_type: Optional[str] = None
    document_type: Optional[str] = None
    evidence_id: Optional[str] = None
    chunk_id: Optional[str] = None
    filename: Optional[str] = None
    keyword: Optional[str] = None
    metadata: dict[str, str] = {}

    def to_query(self) -> "SearchQuery":
        from ..index.interfaces import SearchQuery

        return SearchQuery(
            candidate_id=self.candidate_id,
            role_id=self.role_id,
            assessment_item_id=self.assessment_item_id,
            assessment_type=self.assessment_type,
            document_type=self.document_type,
            evidence_id=self.evidence_id,
            chunk_id=self.chunk_id,
            filename=self.filename,
            keyword=self.keyword,
            metadata=dict(self.metadata),
        )
