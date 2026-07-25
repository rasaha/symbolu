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


@dataclass(frozen=True)
class ActorIdentity:
    """The resolved identity of an actor, as returned by an IdentityProvider."""

    actor_id: str
    actor_type: ActorType
    authenticated: bool


@runtime_checkable
class IdentityProvider(Protocol):
    """Placeholder authentication hook.

    Later phases replace the test/static implementation with a real IdP
    (OIDC/SAML for humans, workload identity for services). The boundary policy
    depends only on this protocol, never on a concrete provider.
    """

    def authenticate(self, actor_id: str) -> ActorIdentity: ...


class StaticIdentityProvider:
    """A simple, in-memory identity provider for development and tests."""

    def __init__(self, identities: Optional[dict[str, ActorIdentity]] = None) -> None:
        self._identities: dict[str, ActorIdentity] = dict(identities or {})

    def register(self, identity: ActorIdentity) -> None:
        self._identities[identity.actor_id] = identity

    def register_human(self, actor_id: str, *, authenticated: bool = True) -> ActorIdentity:
        ident = ActorIdentity(actor_id, ActorType.HUMAN, authenticated)
        self._identities[actor_id] = ident
        return ident

    def register_ai(self, actor_id: str, *, authenticated: bool = True) -> ActorIdentity:
        ident = ActorIdentity(actor_id, ActorType.AI, authenticated)
        self._identities[actor_id] = ident
        return ident

    def register_service(self, actor_id: str, *, authenticated: bool = True) -> ActorIdentity:
        ident = ActorIdentity(actor_id, ActorType.SYSTEM, authenticated)
        self._identities[actor_id] = ident
        return ident

    def authenticate(self, actor_id: str) -> ActorIdentity:
        # Unknown principals resolve as unauthenticated, never as a human.
        return self._identities.get(
            actor_id, ActorIdentity(actor_id, ActorType.SYSTEM, False)
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
