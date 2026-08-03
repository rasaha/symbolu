"""Decision service.

Creates binding, human-authored employment decisions and drives the resulting
workflow transition. This is where the AI/human boundary is most load-bearing:

* the actor must authenticate as a *human* (never an AI or service principal);
* a job-related rationale is mandatory;
* a divergence from the AI recommendation requires a recorded override;
* a REVIEW_BLOCKED evaluation cannot be decided;
* the decision then drives the workflow transition (ADVANCE/HOLD/REJECT),
  which itself re-checks that a valid human decision backs a binding move.

Correlation ids propagate from the originating recommendation through the
decision to the workflow transition, so the full chain is reconstructable.
"""

from __future__ import annotations

from typing import Optional

from ..common import IdFactory, new_id
from ..domain.decision import Approval, Decision, Override
from ..domain.enums import ActorType, AuditEventType, Disposition
from ..domain.workflow import CandidateWorkflow
from ..policies import decision_boundary as boundary
from ..policies import transition_policy as tp
from ..repositories.interfaces import (
    DecisionRepository,
    EvaluationRepository,
    RecommendationRepository,
)
from .audit_service import AuditService
from .workflow_service import WorkflowService


class DecisionService:
    def __init__(
        self,
        decision_repository: DecisionRepository,
        recommendation_repository: RecommendationRepository,
        evaluation_repository: EvaluationRepository,
        workflow_service: WorkflowService,
        audit_service: AuditService,
        identity_provider: boundary.IdentityProvider,
        *,
        id_factory: IdFactory = new_id,
    ) -> None:
        self._repo = decision_repository
        self._recs = recommendation_repository
        self._evals = evaluation_repository
        self._workflow = workflow_service
        self._audit = audit_service
        self._identity = identity_provider
        self._new_id = id_factory

    def create(
        self,
        *,
        recommendation_id: str,
        human_actor_id: str,
        disposition: Disposition,
        panel: tuple[str, ...],
        rationale_job_related: str,
        override: Optional[Override] = None,
        approval: Optional[Approval] = None,
        correlation_id: Optional[str] = None,
    ) -> Decision:
        """Create a binding decision and perform the authorized transition."""
        recommendation = self._recs.get(recommendation_id)
        evaluation = self._evals.get(recommendation.evaluation_id)

        # Correlation: inherit the recommendation's chain unless told otherwise,
        # so recommendation -> decision -> transition share a correlation id.
        rec_event = self._audit.latest_for(recommendation_id)
        corr = correlation_id or (rec_event.correlation_id if rec_event else self._new_id("corr"))
        causation = rec_event.event_id if rec_event else None

        # 1. Authenticate the actor as a human. Denials are audited then raised.
        identity = self._identity.authenticate(human_actor_id)
        try:
            boundary.assert_human_actor_is_authenticated(identity)
        except Exception as exc:  # noqa: BLE001
            self._audit.record_denial(
                entity_type="decision",
                entity_id=recommendation.evaluation_id,
                actor_type=identity.actor_type,
                actor_id=human_actor_id,
                correlation_id=corr,
                causation_id=causation,
                reason=str(exc),
                security=True,
            )
            raise

        # 2. Evaluation must not be blocked.
        try:
            boundary.assert_blocked_evaluation_cannot_be_decided(evaluation)
            # 3. Divergence from the recommendation requires an override.
            boundary.assert_override_present_when_required(
                disposition, recommendation.suggested_disposition, override
            )
        except Exception as exc:  # noqa: BLE001
            self._audit.record_denial(
                entity_type="decision",
                entity_id=recommendation.evaluation_id,
                actor_type=ActorType.HUMAN,
                actor_id=human_actor_id,
                correlation_id=corr,
                causation_id=causation,
                reason=str(exc),
            )
            raise

        # 4. Build the decision (domain pins actor_type=HUMAN + rationale rules).
        decision = Decision(
            decision_id=self._new_id("dec"),
            recommendation_id=recommendation.recommendation_id,
            evaluation_id=evaluation.evaluation_id,
            candidate_id=evaluation.candidate_id,
            role_id=evaluation.role_id,
            disposition=disposition,
            human_actor_id=human_actor_id,
            panel=panel,
            rationale_job_related=rationale_job_related,
            override=override,
            approval=approval,
            actor_type=ActorType.HUMAN,
        )
        boundary.assert_decision_actor_is_human(decision)
        boundary.assert_decision_has_job_related_rationale(decision)

        # 5. Persist (one binding decision per evaluation stage) + audit.
        saved = self._repo.add(decision)
        decision_event = self._audit.record(
            event_type=AuditEventType.DECISION_CREATED,
            entity_type="decision",
            entity_id=decision.decision_id,
            actor_type=ActorType.HUMAN,
            actor_id=human_actor_id,
            correlation_id=corr,
            causation_id=causation,
            payload={
                "recommendation_id": recommendation.recommendation_id,
                "evaluation_id": evaluation.evaluation_id,
                "disposition": disposition.value,
                "override": bool(override),
            },
        )

        # 6. Drive the authorized workflow transition (re-checks the boundary).
        target = tp.disposition_to_state(disposition)
        self._workflow.transition(
            evaluation.candidate_id,
            target,
            actor_type=ActorType.HUMAN,
            actor_id=human_actor_id,
            decision=saved,
            evaluation=evaluation,
            correlation_id=corr,
            causation_id=decision_event.event_id,
        )
        return saved

    def get(self, decision_id: str) -> Decision:
        return self._repo.get(decision_id)
