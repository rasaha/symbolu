#!/usr/bin/env python3
"""Deterministic action-selection baselines (Part 3 §action-selection baseline).

EVALUATION-ONLY. A canonical action envelope plus four selectors that consume
it, for head-to-head comparison with the BCVF action scorer:

  * ``LexicographicSelector``   — hard-constraint filter, then a fixed priority
                                  order (safety margin > goal > cost) with a
                                  deterministic index tie-break.
  * ``WeightedUtilitySelector`` — hard filter, then a linear utility.
  * ``ConstrainedOptSelector``  — hard filter, then maximise goal subject to a
                                  minimum-margin feasibility constraint.
  * ``BCVFActionSelector``      — thin adapter over the REAL production scorer
                                  ``symbolu_robotics.formulas.bcvf`` for
                                  apples-to-apples comparison.

Every selector returns a ``Selection`` and MUST be able to return
``NO_SAFE_ACTION``. The first three NEVER normalise an unsafe/infeasible
candidate into a winner: hard invariants are applied as a non-compensatory
pre-filter, so a good soft score cannot buy back a violated hard constraint.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional

import numpy as np


class Outcome(str, Enum):
    SELECTED = "SELECTED"
    NO_SAFE_ACTION = "NO_SAFE_ACTION"


@dataclass(frozen=True)
class ActionCandidate:
    """Canonical action envelope (domain-neutral, evaluation shape).

    Hard invariants (non-compensatory): ``hard_safe`` and ``feasible`` and the
    margin floors. Soft scores: ``goal_progress``, ``exec_cost``. The BCVF
    ``forward_score`` / ``backward_score`` are provided so the same candidate
    set feeds every selector without re-deriving scores.
    """
    name: str
    hard_safe: bool               # passes hard safety invariants
    feasible: bool                # physically executable (kinematics/limits)
    collision_margin: float       # m to nearest obstacle (>= floor required)
    stability_margin: float       # e.g. ZMP / tip-over margin (>= floor required)
    goal_progress: float          # [0,1] progress toward goal
    exec_cost: float              # >= 0, lower better
    forward_score: float          # sf for the BCVF port
    backward_score: float         # sb for the BCVF port


@dataclass
class Selection:
    outcome: Outcome
    index: Optional[int]
    name: Optional[str]
    rationale: str
    audit: dict = field(default_factory=dict)


# Frozen hard-constraint floors (see preregistration).
COLLISION_FLOOR_M = 0.20
STABILITY_FLOOR = 0.10


def _hard_admissible(c: ActionCandidate) -> bool:
    """Non-compensatory hard gate. No soft score can override this."""
    return (c.hard_safe and c.feasible
            and c.collision_margin >= COLLISION_FLOOR_M
            and c.stability_margin >= STABILITY_FLOOR)


def _admissible_indices(cands: List[ActionCandidate]) -> List[int]:
    return [i for i, c in enumerate(cands) if _hard_admissible(c)]


class LexicographicSelector:
    name = "Lexicographic"

    def select(self, cands: List[ActionCandidate]) -> Selection:
        adm = _admissible_indices(cands)
        if not adm:
            return Selection(Outcome.NO_SAFE_ACTION, None, None,
                             "no candidate passed hard safety+feasibility gate",
                             {"n_candidates": len(cands), "n_admissible": 0})
        # Priority: max safety margin, then goal, then min cost, then index.
        def key(i):
            c = cands[i]
            margin = min(c.collision_margin, c.stability_margin)
            return (-round(margin, 6), -round(c.goal_progress, 6),
                    round(c.exec_cost, 6), i)
        best = min(adm, key=key)
        return Selection(Outcome.SELECTED, best, cands[best].name,
                         "lexicographic: margin > goal > cost > index",
                         {"n_admissible": len(adm)})


class WeightedUtilitySelector:
    name = "WeightedUtility"
    W_MARGIN, W_GOAL, W_COST = 1.0, 1.0, 0.5

    def select(self, cands: List[ActionCandidate]) -> Selection:
        adm = _admissible_indices(cands)
        if not adm:
            return Selection(Outcome.NO_SAFE_ACTION, None, None,
                             "no candidate passed hard gate", {"n_admissible": 0})
        def util(i):
            c = cands[i]
            margin = min(c.collision_margin, c.stability_margin)
            return (self.W_MARGIN * margin + self.W_GOAL * c.goal_progress
                    - self.W_COST * c.exec_cost)
        best = max(adm, key=lambda i: (round(util(i), 6), -i))
        return Selection(Outcome.SELECTED, best, cands[best].name,
                         "weighted utility over admissible set", {"n_admissible": len(adm)})


class ConstrainedOptSelector:
    name = "ConstrainedOpt"
    MIN_MARGIN = 0.30  # require comfortable margin, else fall back to lexicographic

    def select(self, cands: List[ActionCandidate]) -> Selection:
        adm = _admissible_indices(cands)
        if not adm:
            return Selection(Outcome.NO_SAFE_ACTION, None, None,
                             "no candidate passed hard gate", {"n_admissible": 0})
        comfortable = [i for i in adm
                       if min(cands[i].collision_margin, cands[i].stability_margin)
                       >= self.MIN_MARGIN]
        pool = comfortable if comfortable else adm
        # maximise goal, tie-break by cost then index
        best = min(pool, key=lambda i: (-round(cands[i].goal_progress, 6),
                                        round(cands[i].exec_cost, 6), i))
        return Selection(Outcome.SELECTED, best, cands[best].name,
                         "argmax goal s.t. margin constraint (comfortable pool)"
                         if comfortable else "argmax goal over admissible (no comfortable)",
                         {"n_admissible": len(adm), "n_comfortable": len(comfortable)})


class BCVFActionSelector:
    """Adapter over the REAL production BCVF action scorer."""
    name = "BCVF"

    def __init__(self, pre_filter: bool = False):
        # pre_filter mirrors call sites: deliberative/conflict apply NO hard
        # gate before BCVF (pre_filter=False); task_allocation pre-filters
        # (pre_filter=True). Default False = the unguarded production path.
        self.pre_filter = pre_filter

    def select(self, cands: List[ActionCandidate]) -> Selection:
        from symbolu_robotics.formulas.bcvf import (BCVFConfig,
                                                    score_action_candidates)
        pool = _admissible_indices(cands) if self.pre_filter else list(range(len(cands)))
        if not pool:
            return Selection(Outcome.NO_SAFE_ACTION, None, None,
                             "pre-filter removed all candidates", {"n_admissible": 0})
        fwd = [cands[i].forward_score for i in pool]
        bwd = [cands[i].backward_score for i in pool]
        scores = score_action_candidates(fwd, bwd, BCVFConfig())
        best_local = max(range(len(scores)), key=lambda k: scores[k].normalized_weight)
        best = pool[best_local]
        # NOTE: BCVF returns a winner even if that winner is hard-unsafe when
        # pre_filter is False. That is the finding, not a bug in this adapter.
        return Selection(Outcome.SELECTED, best, cands[best].name,
                         f"BCVF argmax normalized_weight (pre_filter={self.pre_filter})",
                         {"winner_hard_safe": cands[best].hard_safe,
                          "winner_admissible": _hard_admissible(cands[best])})


ALL_SELECTORS = [LexicographicSelector(), WeightedUtilitySelector(),
                 ConstrainedOptSelector(), BCVFActionSelector(pre_filter=False)]


if __name__ == "__main__":
    # A scenario where BCVF's "most consistent" pick is hard-unsafe.
    cands = [
        # name, hard_safe, feasible, coll, stab, goal, cost, sf, sb
        ActionCandidate("charge_through", False, True, 0.05, 0.5, 0.95, 0.2, 0.92, 0.90),
        ActionCandidate("safe_detour",    True,  True, 0.60, 0.6, 0.55, 0.6, 0.70, 0.55),
        ActionCandidate("emergency_stop", True,  True, 0.90, 0.9, 0.10, 0.1, 1.00, 0.30),
    ]
    for sel in ALL_SELECTORS:
        s = sel.select(cands)
        print(f"{sel.name:16s} -> {s.outcome.value:14s} pick={s.name} audit={s.audit}")
