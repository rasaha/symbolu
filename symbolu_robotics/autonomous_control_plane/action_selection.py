"""Deterministic action selection (reference implementation).

Contract (see ``ACP_ACTION_SELECTION_V2.md``):
* Hard constraints FILTER; soft objective RANKS; an unsafe action is never
  ranked.
* Absence of admissibility evidence is NOT admissibility — a candidate with no
  evaluated hard constraints cannot be selected (fail closed).
* Empty admissible set -> ``NO_SAFE_ACTION``; no evidence at all ->
  ``REQUEST_MORE_OBSERVATION``.
* Selection among survivors is a TOTAL order (soft cost -> larger safety margin
  -> candidate id), so the winner is unique and replayable.
* The BCVF advisory is never read here, so it cannot resurrect an inadmissible
  candidate.

Standard-library only.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, Optional, Sequence, Tuple

from .constraints import ConstraintResult
from .decision_trace import DecisionTrace, RejectedCandidate
from .envelopes import ActionDecision, CanonicalActionCandidate
from .world_state import CanonicalWorldState


@dataclass(frozen=True)
class SoftObjective:
    """Fixed-weight soft objective over ADMISSIBLE candidates only."""
    w_energy: float = 1.0
    w_time: float = 1.0
    w_goal: float = 1.0

    def cost(self, c: CanonicalActionCandidate) -> float:
        return (self.w_energy * c.energy_estimate
                + self.w_time * c.expected_duration_s
                + self.w_goal * (1.0 - c.goal_progress))


@dataclass(frozen=True)
class SelectionOutcome:
    decision: ActionDecision
    selected: Optional[CanonicalActionCandidate]
    trace: DecisionTrace


class DeterministicActionSelector:
    """Reference selector. Deterministic, bounded, fail-closed."""

    def __init__(self, objective: Optional[SoftObjective] = None):
        self._objective = objective or SoftObjective()

    def select(
        self,
        *,
        tick: int,
        decision_id: str,
        world_state: CanonicalWorldState,
        candidates: Sequence[CanonicalActionCandidate],
        candidate_constraints: Dict[str, Sequence[ConstraintResult]],
        soft_cost_fn: Optional[Callable[[CanonicalActionCandidate], float]] = None,
    ) -> SelectionOutcome:
        cost_fn = soft_cost_fn or self._objective.cost
        considered = tuple(c.candidate_id for c in candidates)
        hard_ids = tuple(sorted({
            r.constraint_id
            for results in candidate_constraints.values()
            for r in results if r.is_hard}))

        # No candidates at all -> nothing to do.
        if not candidates:
            return self._refuse(ActionDecision.NO_SAFE_ACTION, tick, decision_id,
                                world_state, considered, hard_ids, (), ())

        # No admissibility evidence for ANY candidate -> refuse to choose.
        any_evidence = any(candidate_constraints.get(c.candidate_id)
                           for c in candidates)
        if not any_evidence:
            return self._refuse(ActionDecision.REQUEST_MORE_OBSERVATION, tick,
                                decision_id, world_state, considered, hard_ids,
                                (), ())

        rejected = []
        admissible = []
        for c in candidates:
            results = list(candidate_constraints.get(c.candidate_id, ()))
            hard = [r for r in results if r.is_hard]
            failed_hard = [r for r in hard if not r.passed]
            if not hard:
                # No hard evidence for this candidate -> not proven admissible.
                rejected.append(RejectedCandidate(
                    candidate_id=c.candidate_id, reason_code="NO_HARD_EVIDENCE",
                    constraint_id="", observed_value=0.0, required_bound=0.0,
                    comparator="bool"))
                continue
            if failed_hard:
                rejected.append(RejectedCandidate.from_constraint(
                    c.candidate_id, failed_hard[0]))  # first = dispositive
                continue
            admissible.append(c)

        if not admissible:
            return self._refuse(ActionDecision.NO_SAFE_ACTION, tick, decision_id,
                                world_state, considered, hard_ids,
                                tuple(rejected), ())

        # Total-order tie-break: soft cost -> larger min margin -> candidate id.
        def key(c: CanonicalActionCandidate):
            return (round(cost_fn(c), 9),
                    -round(min(c.collision_margin_m, c.stability_margin), 9),
                    c.candidate_id)

        ordered = sorted(admissible, key=key)
        selected = ordered[0]
        surviving = tuple(c.candidate_id for c in admissible)
        tie_seq = tuple(c.candidate_id for c in ordered)

        # EXECUTE vs EXECUTE_WITH_CONSTRAINTS: any failed SOFT constraint on the
        # winner attaches execution caps.
        winner_soft = [r for r in candidate_constraints.get(selected.candidate_id, ())
                       if not r.is_hard and not r.passed]
        decision = (ActionDecision.EXECUTE_WITH_CONSTRAINTS if winner_soft
                    else ActionDecision.EXECUTE)

        trace = DecisionTrace(
            tick=tick, decision_id=decision_id,
            world_state_identity=world_state.version,
            candidate_ids_considered=considered,
            hard_constraints_evaluated=hard_ids,
            rejected=tuple(rejected),
            surviving_candidate_ids=surviving,
            tie_break_sequence=tie_seq,
            decision=decision,
            selected_candidate_id=selected.candidate_id,
            selected_action_identity=selected.identity)
        return SelectionOutcome(decision=decision, selected=selected, trace=trace)

    def _refuse(self, decision, tick, decision_id, world_state, considered,
                hard_ids, rejected, surviving) -> SelectionOutcome:
        trace = DecisionTrace(
            tick=tick, decision_id=decision_id,
            world_state_identity=world_state.version,
            candidate_ids_considered=considered,
            hard_constraints_evaluated=hard_ids,
            rejected=tuple(rejected),
            surviving_candidate_ids=tuple(surviving),
            tie_break_sequence=(),
            decision=decision,
            selected_candidate_id=None,
            selected_action_identity=None)
        return SelectionOutcome(decision=decision, selected=None, trace=trace)
