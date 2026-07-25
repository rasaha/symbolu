"""Recommendation service.

Creates advisory AI recommendations. It validates that the referenced
evaluation exists, enforces ``actor_type=AI`` through the boundary policy,
persists the recommendation, and audits it. It never performs a workflow
transition — a recommendation cannot advance, hold, or reject a candidate.
"""

from __future__ import annotations

from typing import Optional

from ..common import IdFactory, new_id
from ..domain.enums import ActorType, AuditEventType, Disposition
from ..domain.evaluation import Limitation
from ..domain.recommendation import Recommendation
from ..domain.enums import CapabilityLayer
from ..policies import decision_boundary as boundary
from ..repositories.interfaces import EvaluationRepository, RecommendationRepository
from .audit_service import AuditService


class RecommendationService:
    def __init__(
        self,
        recommendation_repository: RecommendationRepository,
        evaluation_repository: EvaluationRepository,
        audit_service: AuditService,
        *,
        id_factory: IdFactory = new_id,
    ) -> None:
        self._repo = recommendation_repository
        self._evals = evaluation_repository
        self._audit = audit_service
        self._new_id = id_factory

    def create(
        self,
        *,
        evaluation_id: str,
        suggested_disposition: Disposition,
        supporting_layers: tuple[CapabilityLayer, ...] = (),
        caveats: tuple[Limitation, ...] = (),
        actor_id: str = "",
        correlation_id: str,
        causation_id: Optional[str] = None,
    ) -> Recommendation:
        """Create and persist an advisory recommendation for an evaluation."""
        # The referenced evaluation must exist (RecordNotFoundError otherwise).
        evaluation = self._evals.get(evaluation_id)

        recommendation = Recommendation(
            recommendation_id=self._new_id("rec"),
            evaluation_id=evaluation.evaluation_id,
            suggested_disposition=suggested_disposition,
            supporting_layers=supporting_layers,
            caveats=caveats,
            actor_type=ActorType.AI,
            actor_id=actor_id,
        )
        # Belt-and-suspenders: the domain model already pins actor_type=AI.
        boundary.assert_recommendation_actor_is_ai(recommendation)

        saved = self._repo.add(recommendation)
        self._audit.record(
            event_type=AuditEventType.RECOMMENDATION_CREATED,
            entity_type="recommendation",
            entity_id=recommendation.recommendation_id,
            actor_type=ActorType.AI,
            actor_id=actor_id or None,
            correlation_id=correlation_id,
            causation_id=causation_id,
            payload={
                "evaluation_id": evaluation.evaluation_id,
                "suggested_disposition": suggested_disposition.value,
            },
        )
        return saved

    def get(self, recommendation_id: str) -> Recommendation:
        return self._repo.get(recommendation_id)
