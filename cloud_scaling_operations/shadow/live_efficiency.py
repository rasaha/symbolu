"""LiveEfficiencyShadow — Track A's live-shadow runner.

Wraps the existing Stage-3 `ShadowRunner` (pipeline → HPA-watcher →
divergence-tracker → reporter) and rides a read-only `EfficiencyObserver`
alongside it, closing the Phase-0 gap: the EfficiencyEstimator + futility guard
ran only in the offline 19-scenario harness, so a real-cluster shadow run
produced divergences + $/replica but NOT the "futile scale-outs the guard would
have blocked" number.

Here the observer computes, each cycle, what the guard WOULD have done —
`blocked_events` is the **counterfactual**. Nothing is actuated: the controller
is read-only, HPA does the real scaling. By construction the guard causes **zero**
real SLO regressions (it never touched the cluster).

This produces the combined "real proof-of-value report":
  - futile scale-outs the guard would have blocked   (observer, counterfactual)
  - $/replica savings estimate                        (ShadowReport, from divergences)
  - SLO-regression count                              (0 caused by guard; observed
                                                       breach cycles reported as context)
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

from cloud_scaling_operations.shadow.runner import ShadowRunner, ShadowConfig, ShadowCycleResult
from ugence_cloud_scaling_controller.observability.efficiency_observer import (
    EfficiencyObserver,
    ObservedCycle,
)


@dataclass
class LiveEfficiencyConfig:
    shadow: ShadowConfig = field(default_factory=ShadowConfig)
    futility_window: int = 5
    high_replica_threshold: int = 20
    # SLO thresholds (normalized [0,1]) for the observed-breach context counter.
    latency_slo: float = 0.8
    error_slo: float = 0.5


@dataclass
class LiveCycle:
    shadow: ShadowCycleResult
    observed: ObservedCycle
    slo_breach: bool


@dataclass
class LiveEfficiencyReport:
    """The combined, labelled proof-of-value report for a live shadow run."""
    period_label: str
    label: str = "live-shadow-self-run"   # real cluster, OUR injected faults
    start_time: float = 0.0
    end_time: float = 0.0
    cycles: int = 0

    # Divergence / cost (from ShadowReport)
    total_decisions: int = 0
    total_agreements: int = 0
    total_divergences: int = 0
    controller_correct: int = 0
    hpa_correct: int = 0
    estimated_cost_saved_usd: float = 0.0

    # Guard counterfactual (from EfficiencyObserver)
    scale_outs_observed: int = 0
    futile_scale_outs_guard_would_block: int = 0
    guard_activation_reason: str = ""

    # SLO
    slo_regressions_caused_by_guard: int = 0   # 0 by construction (read-only)
    observed_slo_breach_cycles: int = 0        # environment context

    cost_per_replica_minute: float = 0.03
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "label": self.label,
            "period_label": self.period_label,
            "cycles": self.cycles,
            "divergence": {
                "total_decisions": self.total_decisions,
                "total_agreements": self.total_agreements,
                "total_divergences": self.total_divergences,
                "controller_correct": self.controller_correct,
                "hpa_correct": self.hpa_correct,
                "estimated_cost_saved_usd": round(self.estimated_cost_saved_usd, 2),
            },
            "guard": {
                "scale_outs_observed": self.scale_outs_observed,
                "futile_scale_outs_guard_would_block": self.futile_scale_outs_guard_would_block,
                "activation_reason": self.guard_activation_reason,
            },
            "slo": {
                "regressions_caused_by_guard": self.slo_regressions_caused_by_guard,
                "observed_breach_cycles": self.observed_slo_breach_cycles,
            },
            "notes": self.notes,
        }

    def format_markdown(self) -> str:
        L = [
            f"# Live-shadow proof-of-value — {self.period_label}",
            "",
            f"> **Label: `{self.label}`.** Real cluster, real Prometheus, real HPA, "
            f"OUR injected faults. The controller ran **read-only** alongside HPA — "
            f"zero write permissions, zero actuation. Savings shown are what the guard "
            f"*would* have saved; they are NOT independently verified (that is the "
            f"third-party rung, still pending).",
            "",
            f"- Cycles observed: **{self.cycles:,}**",
            "",
            "## Decision quality vs HPA",
            f"- Decisions: {self.total_decisions:,} "
            f"({self.total_agreements:,} agreements, {self.total_divergences:,} divergences)",
            f"- Controller correct: {self.controller_correct} · HPA correct: {self.hpa_correct}",
            f"- Estimated cost saved: **${self.estimated_cost_saved_usd:,.2f}** "
            f"(@ ${self.cost_per_replica_minute}/replica·min)",
            "",
            "## Futility guard (counterfactual — never actuated)",
            f"- Scale-outs observed: {self.scale_outs_observed:,}",
            f"- **Futile scale-outs the guard would have blocked: "
            f"{self.futile_scale_outs_guard_would_block:,}**",
            f"- Activation reason: `{self.guard_activation_reason or 'n/a'}`",
            "",
            "## SLO",
            f"- **SLO regressions caused by the guard: "
            f"{self.slo_regressions_caused_by_guard}** (0 by construction — read-only)",
            f"- Observed SLO-breach cycles in the environment: "
            f"{self.observed_slo_breach_cycles:,} (context; driven by the injected faults)",
        ]
        if self.notes:
            L += ["", "## Notes", *[f"- {n}" for n in self.notes]]
        return "\n".join(L)


class LiveEfficiencyShadow:
    """ShadowRunner + read-only EfficiencyObserver for a real cluster."""

    def __init__(self, config: Optional[LiveEfficiencyConfig] = None):
        self.config = config or LiveEfficiencyConfig()
        self.runner = ShadowRunner(self.config.shadow)
        self.observer = EfficiencyObserver(
            futility_window=self.config.futility_window,
            high_replica_threshold=self.config.high_replica_threshold,
        )
        self._start = time.time()
        self._cycles = 0
        self._observed_breach = 0

    def step(self) -> Optional[LiveCycle]:
        result = self.runner.step()
        if result is None:
            return None
        cyc = result.cycle
        raw_delta = cyc.action.replica_delta
        obs = self.observer.observe(
            metrics=cyc.normalized_metrics,
            replicas=cyc.current_replicas,
            raw_delta=raw_delta,
            optimal_replicas=0,   # no oracle on a live cluster; estimator does not need it
        )
        m = cyc.normalized_metrics
        breach = (
            m.get("latency_p99", 0.0) >= self.config.latency_slo
            or m.get("error_rate", 0.0) >= self.config.error_slo
        )
        if breach:
            self._observed_breach += 1
        self._cycles += 1
        return LiveCycle(shadow=result, observed=obs, slo_breach=breach)

    def run(
        self,
        callback: Optional[Callable[[LiveCycle], None]] = None,
        max_cycles: Optional[int] = None,
    ) -> None:
        cycle = 0
        while max_cycles is None or cycle < max_cycles:
            lc = self.step()
            if lc is not None and callback is not None:
                callback(lc)
            cycle += 1
            if max_cycles is None or cycle < max_cycles:
                time.sleep(self.config.shadow.pipeline.poll_interval)

    def report(self, period_label: str = "") -> LiveEfficiencyReport:
        sr = self.runner.generate_report(period_label=period_label)
        gs = self.observer.guard_summary()
        eff = self.observer.efficiency_summary()
        rep = LiveEfficiencyReport(
            period_label=period_label or "live shadow run",
            start_time=self._start,
            end_time=time.time(),
            cycles=self._cycles,
            total_decisions=sr.total_decisions,
            total_agreements=sr.total_agreements,
            total_divergences=sr.total_divergences,
            controller_correct=sr.controller_correct,
            hpa_correct=sr.hpa_correct,
            estimated_cost_saved_usd=sr.total_cost_saved,
            scale_outs_observed=eff.total_scale_outs,
            futile_scale_outs_guard_would_block=self.observer.blocked_events,
            guard_activation_reason=gs.activation_reason,
            slo_regressions_caused_by_guard=0,   # read-only — never actuated
            observed_slo_breach_cycles=self._observed_breach,
            notes=[
                "Controller ran read-only in shadow; the guard's blocks are a "
                "counterfactual, never applied to the cluster.",
                "Cost/divergence verdicts are correlation, not causation (see "
                "DivergenceTracker docstring).",
            ],
        )
        return rep

    def write_report(self, path_md: str, path_json: str, period_label: str = "") -> LiveEfficiencyReport:
        rep = self.report(period_label)
        with open(path_md, "w") as f:
            f.write(rep.format_markdown())
        with open(path_json, "w") as f:
            json.dump(rep.to_dict(), f, indent=2)
        return rep

    def close(self) -> None:
        self.runner.close()
