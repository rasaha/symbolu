"""Track B — offline trace-replay harness.

Runs a real-world trace (as a `TraceSeries`) through the **unmodified** control
core (Controller + EfficiencyEstimator + ScaleOutFutilityGuard + scorer) using
the SAME loop and the SAME demand→metrics transfer function as the 19 synthetic
scenarios. The only changed variable is the workload distribution.

For each trace it runs the loop twice — guard ON (the guard's cap is applied to
the replica trajectory) and guard OFF (raw controller) — so the report can state,
on a real distribution:

  * blocked scale-outs and % of scale-outs blocked   (guard activity)
  * SLO-safety: slo_breach_rate(guard_on) ≤ slo_breach_rate(guard_off)
  * cost: replica-cycles saved by the guard
  * NOT_HELPING futility structure on real load

Every number this module emits is `real-trace-replay` (offline; no live
actuation). It is NOT live-shadow and NOT third-party.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from cloud_controller.config import InfraControllerConfig
from cloud_controller.controller import Controller
from cloud_controller.observability.benchmark import (
    ScenarioScore,
    _optimal_replicas,
    _score_run,
)
from cloud_controller.observability.efficiency_estimator import EfficiencySummary
from cloud_controller.replay.adapters.base import AdapterStatus, TraceSeries
from cloud_controller.replay.efficiency_observer import EfficiencyObserver


@dataclass
class ReplayRun:
    """One pass over a trace (guard on or off)."""
    label: str                       # "guard_on" | "guard_off"
    score: ScenarioScore
    total_scale_outs: int
    blocked_scale_outs: int
    efficiency: EfficiencySummary
    replica_cycles: int
    final_replicas: int
    max_replicas: int


@dataclass
class ReplayResult:
    """Complete Track-B result for one trace."""
    trace_name: str
    source: str
    license: str
    status: str                      # AdapterStatus value
    label: str = "real-trace-replay"
    n_cycles: int = 0
    base_replicas: int = 5
    guard_on: Optional[ReplayRun] = None
    guard_off: Optional[ReplayRun] = None
    meta: Dict[str, object] = field(default_factory=dict)

    # ---- headline properties ----
    @property
    def blocked_scale_outs(self) -> int:
        return self.guard_on.blocked_scale_outs if self.guard_on else 0

    @property
    def total_scale_outs(self) -> int:
        return self.guard_off.total_scale_outs if self.guard_off else 0

    @property
    def pct_scale_outs_blocked(self) -> float:
        t = self.total_scale_outs
        return (self.blocked_scale_outs / t * 100.0) if t else 0.0

    @property
    def slo_safe(self) -> bool:
        """True iff turning the guard ON did not increase the SLO-breach rate."""
        if not (self.guard_on and self.guard_off):
            return False
        return self.guard_on.score.slo_breach_rate <= self.guard_off.score.slo_breach_rate + 1e-9

    @property
    def slo_breach_on(self) -> float:
        return self.guard_on.score.slo_breach_rate if self.guard_on else 0.0

    @property
    def slo_breach_cycles_off(self) -> int:
        return self.guard_off.score.slo_breach_cycles if self.guard_off else 0

    @property
    def slo_breach_cycles_on(self) -> int:
        return self.guard_on.score.slo_breach_cycles if self.guard_on else 0

    @property
    def slo_breach_cycle_delta(self) -> int:
        """A/B: extra (or fewer) SLO-breach cycles caused by enabling the guard."""
        return self.slo_breach_cycles_on - self.slo_breach_cycles_off

    @property
    def slo_breach_pp_delta(self) -> float:
        """Same as above, in percentage-points of total cycles."""
        if not self.guard_on or self.guard_on.score.total_cycles == 0:
            return 0.0
        return self.slo_breach_cycle_delta / self.guard_on.score.total_cycles * 100.0

    @property
    def slo_breach_off(self) -> float:
        return self.guard_off.score.slo_breach_rate if self.guard_off else 0.0

    @property
    def replica_cycles_saved(self) -> int:
        if not (self.guard_on and self.guard_off):
            return 0
        return self.guard_off.replica_cycles - self.guard_on.replica_cycles

    @property
    def pct_replica_cycles_saved(self) -> float:
        if not self.guard_off or self.guard_off.replica_cycles == 0:
            return 0.0
        return self.replica_cycles_saved / self.guard_off.replica_cycles * 100.0

    def cost_saved_usd(self, cost_per_replica_minute: float, cycle_seconds: float) -> float:
        """$ saved = replica-cycles saved × cycle-minutes × $/replica·min.

        Uses the same $/replica·min basis as the shadow reporter
        (DivergenceConfig.cost_per_pod_minute default 0.03).
        """
        cycle_minutes = cycle_seconds / 60.0
        return self.replica_cycles_saved * cycle_minutes * cost_per_replica_minute


class TraceReplayHarness:
    """Drives a TraceSeries through the unmodified control core."""

    def __init__(
        self,
        base_replicas: int = 5,
        warmup_cycles: int = 40,
        controller_config: Optional[InfraControllerConfig] = None,
        futility_window: int = 5,
        high_replica_threshold: int = 20,
    ):
        self.base_replicas = base_replicas
        self.warmup = warmup_cycles
        self.controller_config = controller_config
        self.futility_window = futility_window
        self.high_replica_threshold = high_replica_threshold

    def _default_config(self) -> InfraControllerConfig:
        if self.controller_config is not None:
            return self.controller_config
        # Match the synthetic suite's tuned config for an apples-to-apples baseline.
        try:
            from cloud_controller.observability.edge_cases import _tuned_config
            return _tuned_config()
        except Exception:
            return InfraControllerConfig()

    def _run_once(self, series: TraceSeries, apply_guard: bool) -> ReplayRun:
        cfg = self._default_config()
        ctrl = Controller(cfg)
        observer = EfficiencyObserver(
            futility_window=self.futility_window,
            high_replica_threshold=self.high_replica_threshold,
        )

        metrics_series = series.to_metrics_series()
        demand = series.demand
        replicas = self.base_replicas

        # Warmup on the first cycle's metrics (same as the synthetic harness).
        warm_metrics = metrics_series[0] if metrics_series else {}
        for _ in range(self.warmup):
            ctrl.step(metrics=warm_metrics, current_replicas=replicas)

        replica_history: List[int] = []
        delta_history: List[int] = []
        max_replicas = replicas

        for i, metrics in enumerate(metrics_series):
            result = ctrl.step(metrics=metrics, current_replicas=replicas)
            raw_delta = result.replica_delta
            optimal = _optimal_replicas(demand[i], self.base_replicas)
            obs = observer.observe(metrics, replicas, raw_delta, optimal)
            effective_delta = obs.guarded_delta if apply_guard else raw_delta
            replicas = max(1, replicas + effective_delta)
            max_replicas = max(max_replicas, replicas)
            replica_history.append(replicas)
            # Score on raw_delta (controller intent), matching the synthetic harness.
            delta_history.append(raw_delta)

        score = _score_run(
            series.name, "controller",
            replica_history, delta_history, demand, self.base_replicas,
        )
        excess_cycles = [
            i for i in range(len(replica_history))
            if replica_history[i] > _optimal_replicas(demand[i], self.base_replicas)
        ]
        eff = observer.efficiency_summary(excess_cycles=excess_cycles)

        return ReplayRun(
            label="guard_on" if apply_guard else "guard_off",
            score=score,
            total_scale_outs=eff.total_scale_outs,
            blocked_scale_outs=observer.blocked_events,
            efficiency=eff,
            replica_cycles=sum(replica_history),
            final_replicas=replicas,
            max_replicas=max_replicas,
        )

    def run(self, series: TraceSeries) -> ReplayResult:
        guard_off = self._run_once(series, apply_guard=False)
        guard_on = self._run_once(series, apply_guard=True)
        return ReplayResult(
            trace_name=series.name,
            source=series.source,
            license=series.license,
            status=series.status.value if isinstance(series.status, AdapterStatus) else str(series.status),
            n_cycles=series.n_cycles,
            base_replicas=self.base_replicas,
            guard_on=guard_on,
            guard_off=guard_off,
            meta=dict(series.meta),
        )
