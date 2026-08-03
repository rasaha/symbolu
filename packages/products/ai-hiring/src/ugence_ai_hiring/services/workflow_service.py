"""Workflow service.

Owns the workflow state machine. Every transition is validated through the
transition policy, authorized by actor type, gated on a human decision where the
target is binding, persisted with version checking, and audited. AI actors can
never drive a transition.
"""

from __future__ import annotations

from typing import Optional

from ..common import Clock, utc_now
from ..domain.decision import Decision
from ..domain.enums import ActorType, AuditEventType, WorkflowState
from ..domain.evaluation import CandidateEvaluation
from ..domain.workflow import CandidateWorkflow
from ..errors import (
    BindingTransitionRequiresDecisionError,
    BlockedEvaluationError,
)
from ..policies import decision_boundary as boundary
from ..policies import transition_policy as tp
from ..repositories.interfaces import WorkflowRepository
from .audit_service import AuditService


class WorkflowService:
    def __init__(
        self,
        repository: WorkflowRepository,
        audit_service: AuditService,
        *,
        clock: Clock = utc_now,
    ) -> None:
        self._repo = repository
        self._audit = audit_service
        self._clock = clock

    def initialize(
        self,
        candidate_id: str,
        role_id: str,
        *,
        actor_type: ActorType = ActorType.SYSTEM,
        actor_id: Optional[str] = None,
        state: WorkflowState = WorkflowState.PLANNED,
        correlation_id: str,
    ) -> CandidateWorkflow:
        """Create the initial workflow record for a candidate."""
        workflow = CandidateWorkflow(
            candidate_id=candidate_id, role_id=role_id, state=state
        )
        saved = self._repo.save(workflow)
        self._audit.record(
            event_type=AuditEventType.WORKFLOW_INITIALIZED,
            entity_type="workflow",
            entity_id=candidate_id,
            actor_type=actor_type,
            actor_id=actor_id,
            correlation_id=correlation_id,
            new_state=state.value,
            payload={"role_id": role_id, "state": state.value},
        )
        return saved

    def get(self, candidate_id: str) -> CandidateWorkflow:
        return self._repo.get(candidate_id)

    def transition(
        self,
        candidate_id: str,
        target: WorkflowState,
        *,
        actor_type: ActorType,
        actor_id: Optional[str] = None,
        decision: Optional[Decision] = None,
        evaluation: Optional[CandidateEvaluation] = None,
        correlation_id: str,
        causation_id: Optional[str] = None,
    ) -> CandidateWorkflow:
        """Validate, authorize, perform, and audit a workflow transition."""
        workflow = self._repo.get(candidate_id)

        # 1. Legality of the transition itself.
        try:
            tp.validate_transition(workflow.state, target)
            # 2. Actor authorization (AI can never transition; SYSTEM is limited).
            tp.authorize_actor_for_target(actor_type, target)
            boundary.assert_ai_cannot_write_binding_state(
                actor_type, target, tp.HUMAN_DECISION_STATES | tp.AUTHORIZED_HUMAN_STATES
            )
        except Exception as exc:  # noqa: BLE001 - re-raised after auditing
            self._audit.record_denial(
                entity_type="workflow",
                entity_id=candidate_id,
                actor_type=actor_type,
                actor_id=actor_id,
                correlation_id=correlation_id,
                causation_id=causation_id,
                reason=str(exc),
                security=isinstance(exc, boundary.BoundaryViolationError),
            )
            raise

        # 3. Binding transitions require a valid human decision.
        if tp.requires_human_decision(target):
            if decision is None:
                self._audit.record_denial(
                    entity_type="workflow",
                    entity_id=candidate_id,
                    actor_type=actor_type,
                    actor_id=actor_id,
                    correlation_id=correlation_id,
                    causation_id=causation_id,
                    reason=f"transition to {target.value} requires a human decision",
                )
                raise BindingTransitionRequiresDecisionError(
                    f"transition to {target.value} requires a valid human decision"
                )
            boundary.assert_decision_actor_is_human(decision)

        # 4. A blocked evaluation may not enter review.
        if target is WorkflowState.IN_REVIEW and evaluation is not None:
            if evaluation.is_blocked:
                self._audit.record_denial(
                    entity_type="workflow",
                    entity_id=candidate_id,
                    actor_type=actor_type,
                    actor_id=actor_id,
                    correlation_id=correlation_id,
                    causation_id=causation_id,
                    reason="REVIEW_BLOCKED evaluation cannot enter review",
                )
                raise BlockedEvaluationError(
                    "a REVIEW_BLOCKED evaluation cannot enter review until unblocked"
                )

        # 5. Perform + persist + audit.
        new_workflow = workflow.transitioned(
            target,
            now=self._clock(),
            last_decision_id=decision.decision_id if decision else None,
        )
        saved = self._repo.save(new_workflow)
        self._audit.record(
            event_type=AuditEventType.WORKFLOW_TRANSITION,
            entity_type="workflow",
            entity_id=candidate_id,
            actor_type=actor_type,
            actor_id=actor_id,
            correlation_id=correlation_id,
            causation_id=causation_id,
            previous_state=workflow.state.value,
            new_state=target.value,
            payload={
                "from": workflow.state.value,
                "to": target.value,
                "decision_id": decision.decision_id if decision else None,
            },
        )
        return saved

    def request_review(
        self,
        candidate_id: str,
        evaluation: CandidateEvaluation,
        *,
        actor_type: ActorType = ActorType.SYSTEM,
        actor_id: Optional[str] = None,
        correlation_id: str,
        causation_id: Optional[str] = None,
    ) -> CandidateWorkflow:
        """System-triggered EVALUATED -> IN_REVIEW, gated on a clean evaluation."""
        return self.transition(
            candidate_id,
            WorkflowState.IN_REVIEW,
            actor_type=actor_type,
            actor_id=actor_id,
            evaluation=evaluation,
            correlation_id=correlation_id,
            causation_id=causation_id,
        )
