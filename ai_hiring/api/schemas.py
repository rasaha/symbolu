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
