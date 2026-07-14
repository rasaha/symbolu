"""ACP deterministic interfaces (Protocols).

Each Protocol documents: inputs, outputs, determinism requirement, boundedness /
runtime expectation, failure behaviour, and whether an implementation is
safety-critical. These are structural (``typing.Protocol``) so reference
implementations need not import this module.

Full prose contracts: ``ACP_INTERFACE_CONTRACTS.md``.

Standard-library only.
"""
from __future__ import annotations

from typing import Dict, Optional, Protocol, Sequence, Tuple, runtime_checkable

from .constraints import ConstraintResult
from .decision_trace import DecisionTrace
from .envelopes import ActionDecision, CanonicalActionCandidate
from .predictor_evidence import PredictorEvidence
from .world_state import CanonicalWorldState


@runtime_checkable
class WorldStateProvider(Protocol):
    """Produce a validated, immutable ``CanonicalWorldState``.

    inputs: raw world model (implementation-specific).
    outputs: a ``CanonicalWorldState`` (with a content ``version``).
    determinism: pure w.r.t. its inputs + injected clock; no ambient time.
    boundedness: O(sources); bounded by a fixed source/obstacle cap.
    failure: raise ``SchemaValidationError`` / ``NonFiniteValueError`` on invalid
             or stale input — never return a partially-valid snapshot.
    safety_critical: YES (its output gates every downstream decision).
    """

    def get_world_state(self) -> CanonicalWorldState: ...


@runtime_checkable
class PredictorReliabilityEvaluator(Protocol):
    """Reduce predictor streams to deterministic per-predictor evidence.

    inputs: predictor streams + freshness (implementation-specific).
    outputs: a tuple of ``PredictorEvidence`` (deterministic states, not
             probabilities). Empty tuple => caller must treat as ABSTAIN.
    determinism: no learned weights, no softmax; threshold state machine.
    boundedness: O(M*H) with fixed M, H.
    failure: fail closed — insufficient evidence yields evidence marked
             SUSPECT/FAILED or an empty tuple, never a fabricated TRUSTED.
    safety_critical: YES.
    """

    def evaluate(self, streams: object) -> Tuple[PredictorEvidence, ...]: ...


@runtime_checkable
class HardConstraintEvaluator(Protocol):
    """Evaluate the non-compensatory hard constraints for a candidate.

    inputs: a ``CanonicalActionCandidate`` + ``CanonicalWorldState``.
    outputs: a tuple of HARD ``ConstraintResult``.
    determinism: pure predicate evaluation; fixed constraint order.
    boundedness: O(C) with fixed C.
    failure: a malformed feature is treated as a violation (fail closed);
             absence of results => the candidate is NOT proven admissible.
    safety_critical: YES.
    """

    def evaluate(self, candidate: CanonicalActionCandidate,
                 world_state: CanonicalWorldState) -> Tuple[ConstraintResult, ...]: ...


@runtime_checkable
class SoftObjectiveEvaluator(Protocol):
    """Score an ADMISSIBLE candidate. Never gates admissibility.

    inputs: a ``CanonicalActionCandidate`` (already admissible) + world state.
    outputs: a finite float cost (lower is better).
    determinism: fixed weights; no randomness.
    boundedness: O(1).
    failure: raise on a non-finite cost.
    safety_critical: NO (cannot admit an unsafe action by construction).
    """

    def cost(self, candidate: CanonicalActionCandidate,
             world_state: CanonicalWorldState) -> float: ...


@runtime_checkable
class DeterministicActionSelector(Protocol):
    """Choose one action among survivors or refuse.

    inputs: candidates + per-candidate hard/soft ``ConstraintResult`` + world state.
    outputs: a ``SelectionOutcome`` (decision + optional selected + trace).
    determinism: total-order tie-break; unique replayable winner.
    boundedness: O(K log K).
    failure: empty admissible => ``NO_SAFE_ACTION``; no evidence =>
             ``REQUEST_MORE_OBSERVATION``. Never ranks an inadmissible candidate.
    safety_critical: YES.
    """

    def select(self, *, tick: int, decision_id: str,
               world_state: CanonicalWorldState,
               candidates: Sequence[CanonicalActionCandidate],
               candidate_constraints: Dict[str, Sequence[ConstraintResult]]
               ) -> object: ...


@runtime_checkable
class ControlAuthorizer(Protocol):
    """Mint a one-shot ``ControlAuthorization`` for an executable decision only.

    inputs: decision + selected candidate + world state + constraint-set version.
    outputs: ``Optional[ControlAuthorization]`` (None for non-executable outcomes).
    determinism: pure; binds exact identities + a freshness bound.
    boundedness: O(1).
    failure: an executable decision without a candidate raises; every
             non-executable decision yields None (no grant).
    safety_critical: YES.
    """

    def authorize(self, *, decision: ActionDecision,
                  candidate: Optional[CanonicalActionCandidate],
                  world_state: CanonicalWorldState,
                  constraint_set_version: str, decision_id: str,
                  issued_time_s: float, ttl_s: float) -> object: ...


@runtime_checkable
class CommitStateRevalidator(Protocol):
    """Re-check an authorization at commit (TOCTOU).

    inputs: authorization + candidate + current world state + constraint version
            + current time.
    outputs: None if still valid.
    determinism: pure exact-identity comparison.
    boundedness: O(1).
    failure: raise ``StaleAuthorizationError`` on version drift / expiry,
             ``AuthorizationBindingError`` on action mismatch.
    safety_critical: YES.
    """

    def revalidate(self, *, authorization: object,
                   candidate: CanonicalActionCandidate,
                   current_world_state: CanonicalWorldState,
                   current_constraint_set_version: str, now_s: float) -> None: ...


@runtime_checkable
class FailureStateMachine(Protocol):
    """Deterministic posture machine.

    inputs: target posture + event/reason (+ operator for manual resets).
    outputs: an immutable ``TransitionRecord``.
    determinism: fixed legal-transition table.
    boundedness: O(1) transition.
    failure: raise ``IllegalTransitionError`` on an illegal or ungated move.
    safety_critical: YES.
    """

    @property
    def state(self) -> object: ...
    def transition(self, to_state: object, *, event_code: str, reason: str,
                   operator: Optional[str] = None) -> object: ...


@runtime_checkable
class DecisionTraceSink(Protocol):
    """Persist immutable decision traces (the explanation surface).

    inputs: a ``DecisionTrace``.
    outputs: None.
    determinism: append-only; insertion order preserved.
    boundedness: O(1) per record (implementation may bound total retention).
    failure: raise on a non-trace input; never silently drop.
    safety_critical: NO (observability), but MANDATORY — a decision without a
                     recorded trace is a contract violation.
    """

    def record(self, trace: DecisionTrace) -> None: ...
