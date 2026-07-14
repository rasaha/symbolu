"""Structured decision trace (the explanation surface).

Every ACP decision emits a ``DecisionTrace`` with the full, deterministic
rationale: candidates considered, hard constraints evaluated, each rejection's
dispositive reason, survivors, the tie-break sequence, the outcome, and the
world/action/authorization identities. No black-box scalar alone is ever a valid
explanation. An optional BCVF diagnostic may be attached but is clearly marked
advisory and is never a dispositive reason.

Standard-library only.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Tuple

from .constraints import ConstraintResult
from .envelopes import ActionDecision
from .errors import SchemaValidationError


@dataclass(frozen=True)
class RejectedCandidate:
    """A candidate and the single dispositive hard-constraint failure."""
    candidate_id: str
    reason_code: str
    constraint_id: str
    observed_value: float
    required_bound: float
    comparator: str

    @staticmethod
    def from_constraint(candidate_id: str, c: ConstraintResult) -> "RejectedCandidate":
        return RejectedCandidate(
            candidate_id=candidate_id, reason_code=c.reason_code,
            constraint_id=c.constraint_id, observed_value=c.observed_value,
            required_bound=c.required_bound, comparator=c.comparator)


@dataclass(frozen=True)
class DecisionTrace:
    """Complete, deterministic explanation of one decision."""
    tick: int
    decision_id: str
    world_state_identity: str
    candidate_ids_considered: Tuple[str, ...]
    hard_constraints_evaluated: Tuple[str, ...]
    rejected: Tuple[RejectedCandidate, ...]
    surviving_candidate_ids: Tuple[str, ...]
    tie_break_sequence: Tuple[str, ...]      # ordered survivor ids after tie-break
    decision: ActionDecision
    selected_candidate_id: Optional[str] = None
    selected_action_identity: Optional[str] = None
    authorization_identity: Optional[str] = None
    failure_transition: Optional[str] = None
    # Advisory only; never a dispositive reason.
    bcvf_diagnostic: Optional[str] = field(default=None)

    def __post_init__(self) -> None:
        if not self.decision_id:
            raise SchemaValidationError("decision_id required")
        if not isinstance(self.decision, ActionDecision):
            raise SchemaValidationError("decision must be ActionDecision")
        for name in ("candidate_ids_considered", "hard_constraints_evaluated",
                     "rejected", "surviving_candidate_ids", "tie_break_sequence"):
            if not isinstance(getattr(self, name), tuple):
                raise SchemaValidationError(f"{name} must be an immutable tuple")

    def is_complete(self) -> bool:
        """A trace is complete iff it carries the mandatory explanation fields
        for its decision type. Selection outcomes must name a selected action;
        refusal outcomes must not."""
        base = bool(self.decision_id and self.world_state_identity)
        selects = self.decision in (ActionDecision.EXECUTE,
                                    ActionDecision.EXECUTE_WITH_CONSTRAINTS)
        if selects:
            return base and (self.selected_candidate_id is not None
                             and self.selected_action_identity is not None)
        # refusals must NOT smuggle a selected action
        return base and self.selected_candidate_id is None

    def to_dict(self) -> dict:
        return {
            "tick": self.tick,
            "decision_id": self.decision_id,
            "world_state_identity": self.world_state_identity,
            "candidate_ids_considered": list(self.candidate_ids_considered),
            "hard_constraints_evaluated": list(self.hard_constraints_evaluated),
            "rejected": [vars(r) for r in self.rejected],
            "surviving_candidate_ids": list(self.surviving_candidate_ids),
            "tie_break_sequence": list(self.tie_break_sequence),
            "decision": self.decision.value,
            "selected_candidate_id": self.selected_candidate_id,
            "selected_action_identity": self.selected_action_identity,
            "authorization_identity": self.authorization_identity,
            "failure_transition": self.failure_transition,
            "bcvf_diagnostic_advisory": self.bcvf_diagnostic,
        }


class InMemoryDecisionTraceSink:
    """Reference sink: stores immutable traces in insertion order."""

    def __init__(self) -> None:
        self._records: Tuple[DecisionTrace, ...] = ()

    def record(self, trace: DecisionTrace) -> None:
        if not isinstance(trace, DecisionTrace):
            raise SchemaValidationError("trace must be a DecisionTrace")
        self._records = self._records + (trace,)

    @property
    def records(self) -> Tuple[DecisionTrace, ...]:
        return self._records
