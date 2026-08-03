"""Evaluation service.

Stores validated candidate evaluations and audits them, and implements the
explicit *unblock* action for a REVIEW_BLOCKED evaluation. It does not compute
scores, confidence, gaps, or fairness — those are later phases; the evaluation
arrives already-shaped and is validated by the domain contract.

(Not enumerated in the original four-service list, this small service exists so
evaluation intake and unblocking are not smuggled into route handlers or the
workflow service; see docs/IMPLEMENTATION_STATUS.md.)
"""

from __future__ import annotations

from typing import Optional

from ..domain.enums import ActorType, AuditEventType, EvaluationStatus
from ..domain.evaluation import CandidateEvaluation
from ..repositories.interfaces import EvaluationRepository
from .audit_service import AuditService


class EvaluationService:
    def __init__(
        self,
        repository: EvaluationRepository,
        audit_service: AuditService,
    ) -> None:
        self._repo = repository
        self._audit = audit_service

    def store(
        self,
        evaluation: CandidateEvaluation,
        *,
        actor_type: ActorType = ActorType.AI,
        actor_id: Optional[str] = None,
        correlation_id: str,
        causation_id: Optional[str] = None,
    ) -> CandidateEvaluation:
        """Persist a validated evaluation and audit its creation."""
        saved = self._repo.add(evaluation)
        self._audit.record(
            event_type=AuditEventType.EVALUATION_CREATED,
            entity_type="evaluation",
            entity_id=evaluation.evaluation_id,
            actor_type=actor_type,
            actor_id=actor_id,
            correlation_id=correlation_id,
            causation_id=causation_id,
            new_state=evaluation.status.value,
            payload={
                "candidate_id": evaluation.candidate_id,
                "role_id": evaluation.role_id,
                "status": evaluation.status.value,
                "rubric_version": evaluation.rubric_version,
            },
        )
        return saved

    def get(self, evaluation_id: str) -> CandidateEvaluation:
        return self._repo.get(evaluation_id)

    def unblock(
        self,
        evaluation_id: str,
        *,
        human_actor_id: str,
        correlation_id: str,
        note: str = "",
        causation_id: Optional[str] = None,
    ) -> CandidateEvaluation:
        """Explicitly clear a REVIEW_BLOCKED status, recorded as a new version.

        Evaluations are immutable, so unblocking produces a new, higher-versioned
        evaluation with status EVALUATED. The action is audited as an explicit,
        attributable human act.
        """
        current = self._repo.get(evaluation_id)
        unblocked = current.as_status(EvaluationStatus.EVALUATED)
        saved = self._repo.add(unblocked)
        self._audit.record(
            event_type=AuditEventType.EVALUATION_UNBLOCKED,
            entity_type="evaluation",
            entity_id=evaluation_id,
            actor_type=ActorType.HUMAN,
            actor_id=human_actor_id,
            correlation_id=correlation_id,
            causation_id=causation_id,
            previous_state=EvaluationStatus.REVIEW_BLOCKED.value,
            new_state=EvaluationStatus.EVALUATED.value,
            payload={"note": note, "version": saved.version},
        )
        return saved
