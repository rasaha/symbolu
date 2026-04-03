"""Scaling Effectiveness Report — answers "Did scaling help, or did we just spend money?"

Produces CAST-AI-style insights plus effectiveness metrics from the
EfficiencyEstimator and ScaleOutFutilityGuard. Purely observational —
does not modify controller, estimator, or guard behavior.

Sections:
  1. Scaling Effectiveness — event-level and cycle-level classification
  2. Futility Analysis — streak duration and time-in-futile-regime
  3. Causality Insights — replica/metric correlations, pattern detection
  4. Cost Attribution — non-causal cost, guard savings, residual cost

Output formats:
  - Console table (format_report)
  - Structured JSON (to_json)
  - CSV export (to_csv)

Usage:
    from edge_cases import EdgeCaseHarness
    from scaling_report import ScalingEffectivenessReport

    harness = EdgeCaseHarness()
    edge_report = harness.run_all()
    report = ScalingEffectivenessReport.from_edge_report(edge_report)
    print(report.format_report())
    report.to_json("report.json")
"""

import csv
import io
import json
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional

from symbolu_core.cloud_controller.observability.efficiency_estimator import (
    CycleEfficiency,
    EfficiencyState,
    EfficiencySummary,
    GuardSummary,
)


# ============================================================
# Per-Scenario Analysis
# ============================================================

@dataclass
class FutilityAnalysis:
    """Streak analysis for NOT_HELPING regime."""
    avg_streak_length: float = 0.0
    max_streak_length: int = 0
    total_futile_cycles: int = 0
    total_cycles: int = 0

    @property
    def pct_time_futile(self) -> float:
        if self.total_cycles == 0:
            return 0.0
        return self.total_futile_cycles / self.total_cycles * 100


@dataclass
class CausalityInsight:
    """Correlation and pattern detection for one scenario."""
    # Correlations
    replica_latency_corr: float = 0.0     # positive = more replicas, more latency (bad)
    replica_cpu_util_corr: float = 0.0    # negative = more replicas, less util (waste)

    # Detected patterns
    scaling_without_latency_improvement: int = 0
    external_bottleneck_cycles: int = 0   # low CPU + high latency
    waste_cycles: int = 0                 # high replicas + low utilization
    total_cycles: int = 0

    @property
    def pct_external_bottleneck(self) -> float:
        if self.total_cycles == 0:
            return 0.0
        return self.external_bottleneck_cycles / self.total_cycles * 100

    @property
    def pct_waste(self) -> float:
        if self.total_cycles == 0:
            return 0.0
        return self.waste_cycles / self.total_cycles * 100


@dataclass
class CostAttribution:
    """Enhanced cost attribution per scenario."""
    total_excess_replica_cycles: float = 0.0
    cost_due_to_non_causal_scaling: float = 0.0
    cost_prevented_by_guard: float = 0.0
    residual_cost_after_guard: float = 0.0
    cost_efficiency: float = 0.0

    @property
    def pct_non_causal(self) -> float:
        if self.total_excess_replica_cycles == 0:
            return 0.0
        return self.cost_due_to_non_causal_scaling / self.total_excess_replica_cycles * 100

    @property
    def pct_prevented(self) -> float:
        if self.total_excess_replica_cycles == 0:
            return 0.0
        return self.cost_prevented_by_guard / self.total_excess_replica_cycles * 100


@dataclass
class ScenarioReport:
    """Complete analysis for one scenario."""
    name: str
    severity: str
    slo_breach_rate: float
    cost_efficiency: float

    # Part 1: Scaling Effectiveness
    total_scale_outs: int = 0
    helping_scale_outs: int = 0
    neutral_scale_outs: int = 0
    not_helping_scale_outs: int = 0
    blocked_scale_outs: int = 0
    not_helping_excess_overlap: int = 0
    total_excess_cycles: int = 0

    # Part 2: Futility
    futility: FutilityAnalysis = field(default_factory=FutilityAnalysis)

    # Part 3: Causality
    causality: CausalityInsight = field(default_factory=CausalityInsight)

    # Part 4: Cost
    cost: CostAttribution = field(default_factory=CostAttribution)

    @property
    def pct_effective(self) -> float:
        if self.total_scale_outs == 0:
            return 0.0
        return self.helping_scale_outs / self.total_scale_outs * 100

    @property
    def pct_blocked(self) -> float:
        if self.total_scale_outs == 0:
            return 0.0
        return self.blocked_scale_outs / self.total_scale_outs * 100


# ============================================================
# Report Builder
# ============================================================

def _pearson_corr(xs: List[float], ys: List[float]) -> float:
    """Simple Pearson correlation. Returns 0 if degenerate."""
    n = len(xs)
    if n < 3:
        return 0.0
    mx = sum(xs) / n
    my = sum(ys) / n
    sx = sum((x - mx) ** 2 for x in xs) ** 0.5
    sy = sum((y - my) ** 2 for y in ys) ** 0.5
    if sx == 0 or sy == 0:
        return 0.0
    cov = sum((xs[i] - mx) * (ys[i] - my) for i in range(n)) / n
    return cov / (sx / n ** 0.5) / (sy / n ** 0.5)


def _compute_futility(cycle_log: List[CycleEfficiency], total_cycles: int) -> FutilityAnalysis:
    """Compute NOT_HELPING streak statistics."""
    streaks: List[int] = []
    current_streak = 0
    total_futile = 0

    for entry in cycle_log:
        if entry.state == EfficiencyState.NOT_HELPING:
            current_streak += 1
            total_futile += 1
        else:
            if current_streak > 0:
                streaks.append(current_streak)
            current_streak = 0
    if current_streak > 0:
        streaks.append(current_streak)

    return FutilityAnalysis(
        avg_streak_length=sum(streaks) / len(streaks) if streaks else 0.0,
        max_streak_length=max(streaks) if streaks else 0,
        total_futile_cycles=total_futile,
        total_cycles=total_cycles,
    )


def _compute_causality(
    cycle_log: List[CycleEfficiency],
    optimal_replicas_by_cycle: Dict[int, int],
) -> CausalityInsight:
    """Compute correlations and detect causal patterns."""
    if not cycle_log:
        return CausalityInsight()

    replicas_list = [e.replicas for e in cycle_log]
    latency_list = [e.latency for e in cycle_log]
    cpu_util_list = [e.cpu_per_replica for e in cycle_log]

    corr_lat = _pearson_corr(replicas_list, latency_list)
    corr_cpu = _pearson_corr(replicas_list, cpu_util_list)

    # Pattern detection
    scaling_no_improvement = 0
    external_bottleneck = 0
    waste = 0

    for entry in cycle_log:
        opt = optimal_replicas_by_cycle.get(entry.cycle, entry.replicas)

        # Scaling without latency improvement:
        # replicas > optimal AND latency still high AND state != HELPING
        if (entry.replicas > opt
                and entry.latency > 0.5
                and entry.state != EfficiencyState.HELPING):
            scaling_no_improvement += 1

        # External bottleneck: low CPU + high latency
        if entry.cpu_per_replica < 0.1 and entry.latency > 0.5:
            external_bottleneck += 1

        # Waste: high replicas + low utilization
        if entry.replicas > opt * 2 and entry.cpu_per_replica < 0.05:
            waste += 1

    return CausalityInsight(
        replica_latency_corr=corr_lat,
        replica_cpu_util_corr=corr_cpu,
        scaling_without_latency_improvement=scaling_no_improvement,
        external_bottleneck_cycles=external_bottleneck,
        waste_cycles=waste,
        total_cycles=len(cycle_log),
    )


def _compute_cost_attribution(
    snapshots: list,
    guard_summary: Optional[GuardSummary],
    cost_efficiency: float,
    cycle_log: List[CycleEfficiency],
) -> CostAttribution:
    """Compute enhanced cost attribution."""
    total_excess = 0.0
    non_causal = 0.0

    not_helping_cycles = {
        e.cycle for e in cycle_log
        if e.state == EfficiencyState.NOT_HELPING
    }

    for s in snapshots:
        if s.replicas > s.optimal_replicas:
            excess = s.replicas - s.optimal_replicas
            total_excess += excess
            if s.cycle in not_helping_cycles:
                non_causal += excess

    # Estimate cost prevented by guard: blocked events * average excess at block time
    prevented = 0.0
    if guard_summary and guard_summary.block_log:
        for block in guard_summary.block_log:
            # Each blocked +1 prevents ~1 excess replica for remaining cycles
            # Conservative: count as 1 replica-cycle per block
            prevented += block.get("blocked_delta", 1)

    return CostAttribution(
        total_excess_replica_cycles=total_excess,
        cost_due_to_non_causal_scaling=non_causal,
        cost_prevented_by_guard=prevented,
        residual_cost_after_guard=total_excess - prevented,
        cost_efficiency=cost_efficiency,
    )


# ============================================================
# Main Report
# ============================================================

@dataclass
class ScalingEffectivenessReport:
    """Complete scaling effectiveness analysis across all scenarios."""
    scenarios: List[ScenarioReport] = field(default_factory=list)

    @classmethod
    def from_edge_report(cls, edge_report) -> "ScalingEffectivenessReport":
        """Build from an EdgeCaseReport (output of EdgeCaseHarness.run_all())."""
        report = cls()

        for r in edge_report.results:
            es = r.efficiency_summary
            gs = r.guard_summary
            trace = r.state_trace
            snaps = trace.snapshots

            # Build optimal replicas map and cycle log from estimator
            optimal_map = {s.cycle: s.optimal_replicas for s in snaps}

            # Reconstruct cycle log from snapshots for causality
            cycle_log: List[CycleEfficiency] = []
            for s in snaps:
                cpu = 0.0
                if s.replicas > 0:
                    # Approximate CPU per replica from demand
                    cpu = s.demand / s.replicas
                cycle_log.append(CycleEfficiency(
                    cycle=s.cycle,
                    replicas=s.replicas,
                    cpu_per_replica=cpu,
                    latency=min(1.0, s.demand * 0.8 + 0.05),
                    error_rate=max(0.0, (s.demand - 0.7) * 2.0),
                    state=(
                        EfficiencyState.NOT_HELPING
                        if s.replicas > s.optimal_replicas * 2 and s.delta >= 0
                        else EfficiencyState.HELPING
                        if s.delta > 0 and s.replicas <= s.optimal_replicas + 2
                        else EfficiencyState.NEUTRAL
                    ),
                    confidence=0.5,
                ))

            # Use real estimator data if available
            if es and hasattr(r, '_estimator_cycle_log'):
                cycle_log = r._estimator_cycle_log

            # Futility analysis
            futility = _compute_futility(cycle_log, len(snaps))

            # Causality analysis
            causality = _compute_causality(cycle_log, optimal_map)

            # Cost attribution
            cost_attr = _compute_cost_attribution(
                snaps, gs, r.score.cost_efficiency, cycle_log,
            )

            scenario = ScenarioReport(
                name=r.scenario.name,
                severity=r.severity.value,
                slo_breach_rate=r.score.slo_breach_rate,
                cost_efficiency=r.score.cost_efficiency,
                total_scale_outs=es.total_scale_outs if es else 0,
                helping_scale_outs=es.helping_count if es else 0,
                neutral_scale_outs=es.neutral_count if es else 0,
                not_helping_scale_outs=es.not_helping_count if es else 0,
                blocked_scale_outs=gs.blocked_events if gs else 0,
                not_helping_excess_overlap=es.not_helping_during_excess if es else 0,
                total_excess_cycles=es.total_excess_cycles if es else 0,
                futility=futility,
                causality=causality,
                cost=cost_attr,
            )
            report.scenarios.append(scenario)

        return report

    # ==== Aggregates ====

    @property
    def total_scale_outs(self) -> int:
        return sum(s.total_scale_outs for s in self.scenarios)

    @property
    def total_helping(self) -> int:
        return sum(s.helping_scale_outs for s in self.scenarios)

    @property
    def total_not_helping(self) -> int:
        return sum(s.not_helping_scale_outs for s in self.scenarios)

    @property
    def total_blocked(self) -> int:
        return sum(s.blocked_scale_outs for s in self.scenarios)

    @property
    def pct_effective(self) -> float:
        t = self.total_scale_outs
        return self.total_helping / t * 100 if t > 0 else 0.0

    @property
    def pct_blocked(self) -> float:
        t = self.total_scale_outs
        return self.total_blocked / t * 100 if t > 0 else 0.0

    # ==== Console Report ====

    def format_report(self) -> str:
        lines: List[str] = []
        w = 94

        lines.append("=" * w)
        lines.append("SCALING EFFECTIVENESS REPORT")
        lines.append(
            '"Did scaling actually help, or did we just spend money?"'
        )
        lines.append("=" * w)

        # ---- Section 1: Scaling Effectiveness ----
        lines.append("")
        lines.append("  1. SCALING EFFECTIVENESS")
        lines.append("")
        lines.append(
            f"    {'Scenario':<28s} {'Outs':>5s} {'Help':>5s} "
            f"{'Neut':>5s} {'NotH':>5s} {'Blkd':>5s} "
            f"{'%Eff':>6s} {'%Blk':>6s} {'Overlap':>8s}"
        )
        lines.append("    " + "-" * 80)

        for s in sorted(self.scenarios, key=lambda x: -x.cost_efficiency):
            overlap = (
                f"{s.not_helping_excess_overlap / s.total_excess_cycles * 100:.0f}%"
                if s.total_excess_cycles > 0 else "n/a"
            )
            lines.append(
                f"    {s.name:<28s} {s.total_scale_outs:5d} "
                f"{s.helping_scale_outs:5d} {s.neutral_scale_outs:5d} "
                f"{s.not_helping_scale_outs:5d} {s.blocked_scale_outs:5d} "
                f"{s.pct_effective:5.1f}% {s.pct_blocked:5.1f}% "
                f"{overlap:>8s}"
            )

        lines.append("    " + "-" * 80)
        lines.append(
            f"    {'TOTAL':<28s} {self.total_scale_outs:5d} "
            f"{self.total_helping:5d} "
            f"{sum(s.neutral_scale_outs for s in self.scenarios):5d} "
            f"{self.total_not_helping:5d} "
            f"{self.total_blocked:5d} "
            f"{self.pct_effective:5.1f}% {self.pct_blocked:5.1f}%"
        )

        # ---- Section 2: Futility Analysis ----
        lines.append("")
        lines.append("  2. FUTILITY ANALYSIS")
        lines.append("")
        lines.append(
            f"    {'Scenario':<28s} {'AvgStreak':>9s} {'MaxStreak':>9s} "
            f"{'%Futile':>8s}"
        )
        lines.append("    " + "-" * 58)

        for s in sorted(self.scenarios, key=lambda x: -x.futility.pct_time_futile):
            f = s.futility
            if f.total_futile_cycles == 0:
                continue
            lines.append(
                f"    {s.name:<28s} {f.avg_streak_length:9.1f} "
                f"{f.max_streak_length:9d} {f.pct_time_futile:7.1f}%"
            )

        # ---- Section 3: Causality Insights ----
        lines.append("")
        lines.append("  3. CAUSALITY INSIGHTS")
        lines.append("")
        lines.append(
            f"    {'Scenario':<28s} {'Rep↔Lat':>8s} {'Rep↔CPU':>8s} "
            f"{'NoImprv':>8s} {'ExtBotl':>8s} {'Waste':>6s}"
        )
        lines.append("    " + "-" * 72)

        for s in sorted(self.scenarios, key=lambda x: -x.cost_efficiency):
            c = s.causality
            ext_pct = f"{c.pct_external_bottleneck:.0f}%" if c.external_bottleneck_cycles > 0 else "--"
            waste_pct = f"{c.pct_waste:.0f}%" if c.waste_cycles > 0 else "--"
            lines.append(
                f"    {s.name:<28s} {c.replica_latency_corr:+7.2f} "
                f"{c.replica_cpu_util_corr:+7.2f} "
                f"{c.scaling_without_latency_improvement:8d} "
                f"{ext_pct:>8s} {waste_pct:>6s}"
            )

        # Pattern summary
        total_ext = sum(s.causality.external_bottleneck_cycles for s in self.scenarios)
        total_waste = sum(s.causality.waste_cycles for s in self.scenarios)
        total_no_impr = sum(s.causality.scaling_without_latency_improvement for s in self.scenarios)
        lines.append("")
        lines.append("    Patterns detected:")
        lines.append(f"      Scaling without improvement:  {total_no_impr} cycles")
        lines.append(f"      External bottleneck:          {total_ext} cycles")
        lines.append(f"      High replicas + low util:     {total_waste} cycles")

        # ---- Section 4: Cost Attribution ----
        lines.append("")
        lines.append("  4. COST ATTRIBUTION")
        lines.append("")
        lines.append(
            f"    {'Scenario':<28s} {'Cost':>5s} {'ExcRep':>7s} "
            f"{'NonCausal':>10s} {'Prevented':>10s} {'Residual':>9s}"
        )
        lines.append("    " + "-" * 73)

        grand_excess = 0.0
        grand_noncausal = 0.0
        grand_prevented = 0.0
        grand_residual = 0.0

        for s in sorted(self.scenarios, key=lambda x: -x.cost_efficiency):
            ca = s.cost
            grand_excess += ca.total_excess_replica_cycles
            grand_noncausal += ca.cost_due_to_non_causal_scaling
            grand_prevented += ca.cost_prevented_by_guard
            grand_residual += ca.residual_cost_after_guard
            lines.append(
                f"    {s.name:<28s} {s.cost_efficiency:4.2f}x "
                f"{ca.total_excess_replica_cycles:7.0f} "
                f"{ca.cost_due_to_non_causal_scaling:10.0f} "
                f"{ca.cost_prevented_by_guard:10.0f} "
                f"{ca.residual_cost_after_guard:9.0f}"
            )

        lines.append("    " + "-" * 73)
        lines.append(
            f"    {'TOTAL':<28s}       "
            f"{grand_excess:7.0f} "
            f"{grand_noncausal:10.0f} "
            f"{grand_prevented:10.0f} "
            f"{grand_residual:9.0f}"
        )

        if grand_excess > 0:
            lines.append("")
            lines.append(
                f"    Non-causal scaling:  {grand_noncausal/grand_excess*100:5.1f}% "
                f"of excess cost"
            )
            lines.append(
                f"    Prevented by guard:  {grand_prevented/grand_excess*100:5.1f}% "
                f"of excess cost"
            )
            lines.append(
                f"    Residual:            {grand_residual/grand_excess*100:5.1f}% "
                f"of excess cost"
            )

        # ---- Summary ----
        lines.append("")
        lines.append("  " + "-" * (w - 4))
        lines.append("  SUMMARY")
        lines.append(
            f"    Scale-outs: {self.total_scale_outs} total, "
            f"{self.total_helping} effective ({self.pct_effective:.0f}%), "
            f"{self.total_not_helping} ineffective, "
            f"{self.total_blocked} blocked ({self.pct_blocked:.0f}%)"
        )

        # Verdict
        if self.pct_effective < 10:
            verdict = "Most scaling was reactive, not effective. Guard is critical."
        elif self.pct_effective < 30:
            verdict = "Mixed effectiveness. Guard prevents significant waste."
        else:
            verdict = "Scaling is mostly effective. Guard provides marginal savings."

        lines.append(f"    Verdict: {verdict}")
        lines.append("")
        lines.append("=" * w)
        return "\n".join(lines)

    # ==== JSON Export ====

    def to_dict(self) -> Dict:
        """Convert to a serializable dict."""
        result = {
            "summary": {
                "total_scale_outs": self.total_scale_outs,
                "helping": self.total_helping,
                "not_helping": self.total_not_helping,
                "blocked": self.total_blocked,
                "pct_effective": round(self.pct_effective, 1),
                "pct_blocked": round(self.pct_blocked, 1),
            },
            "scenarios": [],
        }

        for s in self.scenarios:
            entry = {
                "name": s.name,
                "severity": s.severity,
                "slo_breach_rate": round(s.slo_breach_rate, 4),
                "cost_efficiency": round(s.cost_efficiency, 2),
                "scaling_effectiveness": {
                    "total_scale_outs": s.total_scale_outs,
                    "helping": s.helping_scale_outs,
                    "neutral": s.neutral_scale_outs,
                    "not_helping": s.not_helping_scale_outs,
                    "blocked": s.blocked_scale_outs,
                    "pct_effective": round(s.pct_effective, 1),
                    "pct_blocked": round(s.pct_blocked, 1),
                },
                "futility": {
                    "avg_streak_length": round(s.futility.avg_streak_length, 1),
                    "max_streak_length": s.futility.max_streak_length,
                    "pct_time_futile": round(s.futility.pct_time_futile, 1),
                },
                "causality": {
                    "replica_latency_corr": round(s.causality.replica_latency_corr, 3),
                    "replica_cpu_util_corr": round(s.causality.replica_cpu_util_corr, 3),
                    "scaling_without_improvement": s.causality.scaling_without_latency_improvement,
                    "external_bottleneck_cycles": s.causality.external_bottleneck_cycles,
                    "waste_cycles": s.causality.waste_cycles,
                },
                "cost_attribution": {
                    "total_excess_replica_cycles": round(s.cost.total_excess_replica_cycles, 1),
                    "non_causal": round(s.cost.cost_due_to_non_causal_scaling, 1),
                    "prevented_by_guard": round(s.cost.cost_prevented_by_guard, 1),
                    "residual": round(s.cost.residual_cost_after_guard, 1),
                },
            }
            result["scenarios"].append(entry)

        return result

    def to_json(self, path: Optional[str] = None, indent: int = 2) -> str:
        """Export as JSON string. Optionally write to file."""
        data = self.to_dict()
        text = json.dumps(data, indent=indent)
        if path:
            with open(path, "w") as f:
                f.write(text)
        return text

    # ==== CSV Export ====

    def to_csv(self, path: Optional[str] = None) -> str:
        """Export as CSV string. Optionally write to file."""
        output = io.StringIO()
        writer = csv.writer(output)

        # Header
        writer.writerow([
            "scenario", "severity", "slo_breach_rate", "cost_efficiency",
            "total_scale_outs", "helping", "neutral", "not_helping", "blocked",
            "pct_effective", "pct_blocked",
            "avg_streak", "max_streak", "pct_futile",
            "replica_latency_corr", "replica_cpu_corr",
            "external_bottleneck", "waste_cycles",
            "excess_replica_cycles", "non_causal_cost",
            "prevented_cost", "residual_cost",
        ])

        for s in self.scenarios:
            writer.writerow([
                s.name, s.severity,
                f"{s.slo_breach_rate:.4f}", f"{s.cost_efficiency:.2f}",
                s.total_scale_outs, s.helping_scale_outs,
                s.neutral_scale_outs, s.not_helping_scale_outs,
                s.blocked_scale_outs,
                f"{s.pct_effective:.1f}", f"{s.pct_blocked:.1f}",
                f"{s.futility.avg_streak_length:.1f}",
                s.futility.max_streak_length,
                f"{s.futility.pct_time_futile:.1f}",
                f"{s.causality.replica_latency_corr:.3f}",
                f"{s.causality.replica_cpu_util_corr:.3f}",
                s.causality.external_bottleneck_cycles,
                s.causality.waste_cycles,
                f"{s.cost.total_excess_replica_cycles:.0f}",
                f"{s.cost.cost_due_to_non_causal_scaling:.0f}",
                f"{s.cost.cost_prevented_by_guard:.0f}",
                f"{s.cost.residual_cost_after_guard:.0f}",
            ])

        text = output.getvalue()
        if path:
            with open(path, "w") as f:
                f.write(text)
        return text
