"""The AI/human decision-boundary policy.

This module is the single, centralized place where the core architectural
invariant is enforced:

    AI evaluates evidence and produces advisory recommendations.
    Only an authenticated human actor may create a binding employment decision.

Every check raises a typed error and returns ``None`` on success, so callers
read as a sequence of assertions. Services call these before persistence and at
API boundaries — never relying on UI enforcement.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol, runtime_checkable

from ..domain.decision import Decision, Override
from ..domain.enums import ActorType, Disposition, WorkflowState
from ..domain.evaluation import CandidateEvaluation
from ..domain.recommendation import Recommendation
from ..errors import (
    BlockedEvaluationError,
    BoundaryViolationError,
    DomainValidationError,
    OverrideRequiredError,
    UnauthenticatedActorError,
)


from ugence_decision_authority.api.identity import (  # noqa: F401
    ActorIdentity,
    IdentityProvider,
    StaticIdentityProvider,
)


# --- Boundary assertions ---------------------------------------------------

def assert_recommendation_actor_is_ai(recommendation: Recommendation) -> None:
    if recommendation.actor_type is not ActorType.AI:
        raise BoundaryViolationError(
            "recommendations must be AI-authored (actor_type=AI)"
        )


def assert_decision_actor_is_human(decision: Decision) -> None:
    if decision.actor_type is not ActorType.HUMAN:
        raise BoundaryViolationError(
            "decisions must be human-authored (actor_type=HUMAN)"
        )


def assert_human_actor_is_authenticated(identity: ActorIdentity) -> None:
    """The actor must be authenticated *and* a human — no AI/service principal."""
    if not identity.authenticated:
        raise UnauthenticatedActorError(
            f"actor '{identity.actor_id}' is not authenticated"
        )
    if identity.actor_type is not ActorType.HUMAN:
        raise BoundaryViolationError(
            f"actor '{identity.actor_id}' is a {identity.actor_type.value} principal "
            "and may not author a binding human decision"
        )


def assert_decision_has_job_related_rationale(decision: Decision) -> None:
    if not decision.rationale_job_related.strip():
        raise DomainValidationError("a decision requires a non-empty job-related rationale")


def assert_override_present_when_required(
    disposition: Disposition,
    recommended: Disposition,
    override: Optional[Override],
) -> None:
    """If the human disposition diverges from the AI's, an override is required."""
    if disposition is not recommended and override is None:
        raise OverrideRequiredError(
            "decision disposition differs from the recommendation; an override "
            "with a recorded reason is required"
        )


def assert_ai_cannot_write_binding_state(
    actor_type: ActorType,
    target_state: WorkflowState,
    binding_states: frozenset[WorkflowState],
) -> None:
    """An AI actor may never drive a binding workflow transition."""
    if actor_type is ActorType.AI and target_state in binding_states:
        raise BoundaryViolationError(
            f"an AI actor may not transition a candidate to {target_state.value}"
        )


def assert_blocked_evaluation_cannot_be_decided(evaluation: CandidateEvaluation) -> None:
    if evaluation.is_blocked:
        raise BlockedEvaluationError(
            "a REVIEW_BLOCKED evaluation cannot receive a binding decision until "
            "it is explicitly unblocked"
        )
