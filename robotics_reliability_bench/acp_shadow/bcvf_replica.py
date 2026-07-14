"""Faithful replicas of the three production BCVF call-site selections.

These reproduce EXACTLY what each production call site does to pick a winner,
using the REAL ``symbolu_robotics.formulas.bcvf`` scorer. They live in the eval
harness (not the ACP package) so the ACP core stays production-independent. They
are READ-ONLY reproductions — no production object is constructed or mutated;
production code is unchanged.

Line references pin each replica to the production logic it mirrors:
* deliberative:      tiers/deliberative.py:150-159  (score_candidates -> argmax)
* conflict:          coordination/conflict_resolution.py:392-412
                     (score -> *(1+0.3*priority)*(1+0.4*safety) -> renorm -> argmax)
* task_allocation:   coordination/task_allocation.py:358-376
                     (score -> *(1+0.1*priority) -> renorm -> argmax)
"""
from __future__ import annotations

from typing import List, Optional, Sequence

from symbolu_robotics.formulas.bcvf import (BCVFConfig, BCVFScorer,
                                            score_action_candidates)

# Production config defaults (verified against source).
_PRIORITY_WEIGHT = 0.3   # ConflictResolverConfig.priority_weight
_SAFETY_WEIGHT = 0.4     # ConflictResolverConfig.safety_weight


def bcvf_deliberative(ids: Sequence[str], forward: Sequence[float],
                      backward: Sequence[float]) -> Optional[str]:
    """Mirror tiers/deliberative.py: pure argmax of normalized_weight."""
    if not ids:
        return None
    scorer = BCVFScorer()  # default BCVFConfig (beta=2.0)
    scores = scorer.score_candidates(list(forward), list(backward))
    best = max(range(len(scores)), key=lambda i: scores[i].normalized_weight)
    return ids[best]


def bcvf_conflict(ids: Sequence[str], forward: Sequence[float],
                  backward: Sequence[float], priority: Sequence[float],
                  safety: Sequence[float]) -> Optional[str]:
    """Mirror conflict_resolution.py:392-412 exactly."""
    if not ids:
        return None
    scores = score_action_candidates(list(forward), list(backward), BCVFConfig())
    weights = []
    for i in range(len(ids)):
        w = scores[i].normalized_weight
        w *= (1.0 + _PRIORITY_WEIGHT * priority[i])
        w *= (1.0 + _SAFETY_WEIGHT * safety[i])
        weights.append(w)
    total = sum(weights)
    weights = [w / max(total, 1e-10) for w in weights]
    best = max(range(len(weights)), key=lambda i: weights[i])
    return ids[best]


def bcvf_task_allocation(ids: Sequence[str], forward: Sequence[float],
                         backward: Sequence[float],
                         priority_value: float) -> Optional[str]:
    """Mirror task_allocation.py:358-376 exactly (priority bonus 0.1*value)."""
    if not ids:
        return None
    scores = score_action_candidates(list(forward), list(backward), BCVFConfig())
    bonus = priority_value * 0.1
    weights = [s.normalized_weight * (1.0 + bonus) for s in scores]
    total = sum(weights)
    weights = [w / total for w in weights]
    best = max(range(len(weights)), key=lambda i: weights[i])
    return ids[best]
