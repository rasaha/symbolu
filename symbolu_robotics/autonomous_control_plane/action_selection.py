"""Deterministic action selection (reference + lexicographic implementations).

Contract (see ``ACP_ACTION_SELECTION_V2.md``):
* Hard constraints FILTER; soft objective RANKS; an unsafe action is never
  ranked.
* Absence of admissibility evidence is NOT admissibility — a candidate with no
  evaluated hard constraints cannot be selected (fail closed).
* Empty admissible set -> ``NO_SAFE_ACTION``; no evidence at all ->
  ``REQUEST_MORE_OBSERVATION``.
* Selection among survivors is a TOTAL order, so the winner is unique and
  replayable.
* The BCVF advisory is never read here, so it cannot resurrect an inadmissible
  candidate.

Two selectors share the identical admissibility filter:
* ``DeterministicActionSelector`` (Phase 0) — orders by a scalar soft cost, then
  larger safety margin, then id.
* ``LexicographicActionSelector`` (Phase 1) — orders by a caller-supplied total
  lexicographic key (frozen per call site), then id.

Standard-library only.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Sequence, Tuple

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
class AdmissibilityResult:
    admissible: Tuple[CanonicalActionCandidate, ...]
    rejected: Tuple[RejectedCandidate, ...]
    hard_ids: Tuple[str, ...]
    any_evidence: bool


@dataclass(frozen=True)
class SelectionOutcome:
    decision: ActionDecision
    selected: Optional[CanonicalActionCandidate]
    trace: DecisionTrace


def filter_admissible(
    candidates: Sequence[CanonicalActionCandidate],
    candidate_constraints: Dict[str, Sequence[ConstraintResult]],
) -> AdmissibilityResult:
    """Shared non-compensatory hard filter used by every ACP selector.

    A candidate is admissible iff it has at least one HARD constraint result and
    no failed HARD result. No hard evidence => not admissible (fail closed). The
    first failed HARD result is the dispositive rejection reason.
    """
    hard_ids = tuple(sorted({
        r.constraint_id
        for results in candidate_constraints.values()
        for r in results if r.is_hard}))
    any_evidence = any(candidate_constraints.get(c.candidate_id)
                       for c in candidates)
    rejected: List[RejectedCandidate] = []
    admissible: List[CanonicalActionCandidate] = []
    for c in candidates:
        results = list(candidate_constraints.get(c.candidate_id, ()))
        hard = [r for r in results if r.is_hard]
        failed_hard = [r for r in hard if not r.passed]
        if not hard:
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
    return AdmissibilityResult(tuple(admissible), tuple(rejected), hard_ids,
                              any_evidence)


def _refuse(decision, tick, decision_id, world_state, considered, hard_ids,
            rejected, surviving) -> SelectionOutcome:
    trace = DecisionTrace(
        tick=tick, decision_id=decision_id,
        world_state_identity=world_state.version,
        candidate_ids_considered=considered, hard_constraints_evaluated=hard_ids,
        rejected=tuple(rejected), surviving_candidate_ids=tuple(surviving),
        tie_break_sequence=(), decision=decision,
        selected_candidate_id=None, selected_action_identity=None)
    return SelectionOutcome(decision=decision, selected=None, trace=trace)


def _winner_decision(selected, candidate_constraints) -> ActionDecision:
    winner_soft_failed = [
        r for r in candidate_constraints.get(selected.candidate_id, ())
        if not r.is_hard and not r.passed]
    return (ActionDecision.EXECUTE_WITH_CONSTRAINTS if winner_soft_failed
            else ActionDecision.EXECUTE)


def _build_outcome(*, tick, decision_id, world_state, considered, adm, ordered,
                   candidate_constraints) -> SelectionOutcome:
    selected = ordered[0]
    surviving = tuple(c.candidate_id for c in adm.admissible)
    tie_seq = tuple(c.candidate_id for c in ordered)
    decision = _winner_decision(selected, candidate_constraints)
    trace = DecisionTrace(
        tick=tick, decision_id=decision_id,
        world_state_identity=world_state.version,
        candidate_ids_considered=considered,
        hard_constraints_evaluated=adm.hard_ids, rejected=adm.rejected,
        surviving_candidate_ids=surviving, tie_break_sequence=tie_seq,
        decision=decision, selected_candidate_id=selected.candidate_id,
        selected_action_identity=selected.identity)
    return SelectionOutcome(decision=decision, selected=selected, trace=trace)


class DeterministicActionSelector:
    """Phase-0 reference selector: scalar soft cost, margin, id."""

    def __init__(self, objective: Optional[SoftObjective] = None):
        self._objective = objective or SoftObjective()

    def select(self, *, tick: int, decision_id: str,
               world_state: CanonicalWorldState,
               candidates: Sequence[CanonicalActionCandidate],
               candidate_constraints: Dict[str, Sequence[ConstraintResult]],
               soft_cost_fn: Optional[Callable[[CanonicalActionCandidate], float]] = None
               ) -> SelectionOutcome:
        cost_fn = soft_cost_fn or self._objective.cost
        considered = tuple(c.candidate_id for c in candidates)
        adm = filter_admissible(candidates, candidate_constraints)
        if not candidates:
            return _refuse(ActionDecision.NO_SAFE_ACTION, tick, decision_id,
                           world_state, considered, adm.hard_ids, (), ())
        if not adm.any_evidence:
            return _refuse(ActionDecision.REQUEST_MORE_OBSERVATION, tick,
                           decision_id, world_state, considered, adm.hard_ids,
                           (), ())
        if not adm.admissible:
            return _refuse(ActionDecision.NO_SAFE_ACTION, tick, decision_id,
                           world_state, considered, adm.hard_ids, adm.rejected, ())

        def key(c: CanonicalActionCandidate):
            return (round(cost_fn(c), 9),
                    -round(min(c.collision_margin_m, c.stability_margin), 9),
                    c.candidate_id)
        ordered = sorted(adm.admissible, key=key)
        return _build_outcome(tick=tick, decision_id=decision_id,
                              world_state=world_state, considered=considered,
                              adm=adm, ordered=ordered,
                              candidate_constraints=candidate_constraints)


class LexicographicActionSelector:
    """Phase-1 selector: caller supplies a frozen total lexicographic key.

    ``sort_key`` returns a tuple; candidate id is appended as the final,
    always-unique tie-break so the ordering is total and replayable. Shares the
    identical admissibility filter, so it can never rank an inadmissible
    candidate either.
    """

    def __init__(self, sort_key: Callable[[CanonicalActionCandidate], tuple]):
        self._sort_key = sort_key

    def select(self, *, tick: int, decision_id: str,
               world_state: CanonicalWorldState,
               candidates: Sequence[CanonicalActionCandidate],
               candidate_constraints: Dict[str, Sequence[ConstraintResult]]
               ) -> SelectionOutcome:
        considered = tuple(c.candidate_id for c in candidates)
        adm = filter_admissible(candidates, candidate_constraints)
        if not candidates:
            return _refuse(ActionDecision.NO_SAFE_ACTION, tick, decision_id,
                           world_state, considered, adm.hard_ids, (), ())
        if not adm.any_evidence:
            return _refuse(ActionDecision.REQUEST_MORE_OBSERVATION, tick,
                           decision_id, world_state, considered, adm.hard_ids,
                           (), ())
        if not adm.admissible:
            return _refuse(ActionDecision.NO_SAFE_ACTION, tick, decision_id,
                           world_state, considered, adm.hard_ids, adm.rejected, ())
        ordered = sorted(adm.admissible,
                         key=lambda c: (self._sort_key(c), c.candidate_id))
        return _build_outcome(tick=tick, decision_id=decision_id,
                              world_state=world_state, considered=considered,
                              adm=adm, ordered=ordered,
                              candidate_constraints=candidate_constraints)
