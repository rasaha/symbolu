"""EfficiencyObserver — read-only wrapper around the EfficiencyEstimator and the
ScaleOutFutilityGuard, shared by Track A (live shadow) and Track B (offline
replay).

It runs the *exact* estimator + guard logic the 19-scenario harness runs, but
factored out so it can ride alongside any cycle loop. The observer only
**computes** what the guard would do (`guarded_delta`, `blocked`); the caller
decides whether to apply it:

  - Track B (offline replay): the caller applies `guarded_delta` so the savings
    show up in the replica trajectory.
  - Track A (live shadow): the caller IGNORES `guarded_delta` (HPA does the real
    scaling). The observer's `blocked_events` is then the *counterfactual* —
    "futile scale-outs the guard would have blocked" — for the proof-of-value
    report. Nothing is ever actuated.

This component has no write path to anything. It records.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

from cloud_controller.observability.efficiency_estimator import (
    EfficiencyEstimator,
    EfficiencyState,
    EfficiencySummary,
    GuardSummary,
    ScaleOutFutilityGuard,
)


@dataclass
class ObservedCycle:
    """What the estimator+guard saw and would have done this cycle."""
    cycle: int
    state: EfficiencyState
    confidence: float
    raw_delta: int
    guarded_delta: int           # what the guard would actuate
    blocked: bool                # guard capped a scale-out this cycle
    guard_active: bool


class EfficiencyObserver:
    """Runs EfficiencyEstimator + ScaleOutFutilityGuard alongside a cycle loop."""

    def __init__(
        self,
        futility_window: int = 5,
        high_replica_threshold: int = 20,
        confidence_threshold: float = 0.0,
    ):
        self.estimator = EfficiencyEstimator()
        self.guard = ScaleOutFutilityGuard(
            futility_window=futility_window,
            high_replica_threshold=high_replica_threshold,
            confidence_threshold=confidence_threshold,
        )
        self._cycle = 0

    def observe(
        self,
        metrics: Dict[str, float],
        replicas: int,
        raw_delta: int,
        optimal_replicas: int = 0,
    ) -> ObservedCycle:
        """Observe one cycle. Mirrors the order in EdgeCaseHarness.run_scenario:
        estimator.observe → guard.update → guard.filter_delta, all on the
        replica count *before* the delta is applied.
        """
        entry = self.estimator.observe(
            cycle=self._cycle,
            metrics=metrics,
            replicas=replicas,
            delta=raw_delta,
            optimal_replicas=optimal_replicas,
        )
        self.guard.update(entry.state, entry.confidence)
        guarded_delta = self.guard.filter_delta(raw_delta, replicas)
        obs = ObservedCycle(
            cycle=self._cycle,
            state=entry.state,
            confidence=entry.confidence,
            raw_delta=raw_delta,
            guarded_delta=guarded_delta,
            blocked=(guarded_delta != raw_delta),
            guard_active=self.guard.is_active,
        )
        self._cycle += 1
        return obs

    @property
    def blocked_events(self) -> int:
        return self.guard.blocked_scale_out_events

    @property
    def total_evaluated(self) -> int:
        return self.guard.total_evaluated

    def efficiency_summary(self, excess_cycles=None) -> EfficiencySummary:
        return self.estimator.summary(excess_cycles=excess_cycles)

    def guard_summary(self) -> GuardSummary:
        stats = self.guard.confidence_stats
        blog = self.guard.block_log
        avg_conf_at_block = (
            sum(b["avg_confidence"] for b in blog) / len(blog) if blog else 0.0
        )
        return GuardSummary(
            total_evaluated=self.guard.total_evaluated,
            blocked_events=self.guard.blocked_scale_out_events,
            block_log=blog,
            avg_confidence_at_block=avg_conf_at_block,
            confidence_mean=stats["mean"],
            confidence_min=stats["min"],
            confidence_max=stats["max"],
            activation_reason=self.guard.activation_reason,
        )
