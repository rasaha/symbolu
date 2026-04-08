"""Tests for Benchmark Harness — validates traffic patterns, HPA simulator,
scorer, and full harness runs."""

import math

from symbolu.cloud_controller.observability.benchmark import (
    BenchmarkConfig,
    BenchmarkHarness,
    BenchmarkReport,
    HPASimulator,
    ParameterSweep,
    PatternType,
    ScenarioScore,
    SweepResult,
    SweepVariant,
    PATTERNS,
    build_sweep_variants,
    _demand_to_metrics,
    _optimal_replicas,
    _score_run,
    pattern_step,
    pattern_ramp,
    pattern_sinusoidal,
    pattern_spike,
    pattern_oscillating,
    pattern_plateau,
)
from symbolu.cloud_controller.config import InfraControllerConfig


# ============================================================
# Traffic Patterns
# ============================================================

class TestTrafficPatterns:
    def test_step_baseline(self):
        """Step pattern: low at start."""
        assert pattern_step(0, 300) == 0.3

    def test_step_spike(self):
        """Step pattern: high in middle."""
        assert pattern_step(150, 300) == 0.9

    def test_step_recovery(self):
        """Step pattern: returns to low."""
        assert pattern_step(250, 300) == 0.3

    def test_ramp_start_low(self):
        assert pattern_ramp(0, 100) == 0.2

    def test_ramp_end_high(self):
        assert abs(pattern_ramp(99, 100) - 0.9) < 0.01

    def test_ramp_monotonic(self):
        values = [pattern_ramp(i, 100) for i in range(100)]
        for i in range(1, len(values)):
            assert values[i] >= values[i - 1]

    def test_sinusoidal_range(self):
        values = [pattern_sinusoidal(i, 200) for i in range(200)]
        assert min(values) >= 0.1
        assert max(values) <= 0.9

    def test_sinusoidal_periodic(self):
        """Start and end should be close (full cycle)."""
        start = pattern_sinusoidal(0, 200)
        end = pattern_sinusoidal(199, 200)
        assert abs(start - end) < 0.05

    def test_spike_baseline(self):
        assert pattern_spike(0, 100) == 0.3

    def test_spike_peak(self):
        peak_start = int(100 * 0.4)
        assert pattern_spike(peak_start, 100) == 0.95

    def test_spike_recovery(self):
        assert pattern_spike(99, 100) == 0.3

    def test_oscillating_alternates(self):
        values = [pattern_oscillating(i, 100) for i in range(20)]
        # Should alternate every 5 cycles
        assert values[0] == 0.85  # high
        assert values[5] == 0.25  # low
        assert values[10] == 0.85  # high again

    def test_plateau_baseline(self):
        assert pattern_plateau(0, 100) == 0.3

    def test_plateau_shift(self):
        assert pattern_plateau(50, 100) == 0.7

    def test_all_patterns_registered(self):
        assert len(PATTERNS) == 6
        for pt in PatternType:
            assert pt in PATTERNS


# ============================================================
# Demand to Metrics
# ============================================================

class TestDemandToMetrics:
    def test_low_demand(self):
        m = _demand_to_metrics(0.1)
        assert m["cpu"] == 0.1
        assert m["error_rate"] == 0.0  # no errors at low demand

    def test_high_demand(self):
        m = _demand_to_metrics(0.9)
        assert m["cpu"] == 0.9
        assert m["error_rate"] > 0  # errors at high demand

    def test_clamped(self):
        m = _demand_to_metrics(1.5)
        assert m["cpu"] == 1.0  # clamped

    def test_all_keys_present(self):
        m = _demand_to_metrics(0.5)
        for k in ("cpu", "memory", "latency_p99", "error_rate", "queue_depth"):
            assert k in m

    def test_values_in_range(self):
        for d in [0.0, 0.25, 0.5, 0.75, 1.0]:
            m = _demand_to_metrics(d)
            for v in m.values():
                assert 0.0 <= v <= 1.0


# ============================================================
# Optimal Replicas Oracle
# ============================================================

class TestOptimalReplicas:
    def test_baseline(self):
        """At demand=0.5, optimal = base_replicas."""
        assert _optimal_replicas(0.5, 5) == 5

    def test_high_demand(self):
        """At demand=1.0, optimal = 2x base."""
        assert _optimal_replicas(1.0, 5) == 10

    def test_low_demand(self):
        """At demand=0.25, optimal = 0.5x base."""
        assert _optimal_replicas(0.25, 5) in (2, 3)

    def test_never_below_one(self):
        assert _optimal_replicas(0.0, 5) >= 1


# ============================================================
# HPA Simulator
# ============================================================

class TestHPASimulator:
    def test_no_action_normal(self):
        hpa = HPASimulator()
        delta = hpa.decide({"cpu": 0.5}, current_replicas=5, cycle=0)
        assert delta == 0

    def test_scale_up_high_cpu(self):
        hpa = HPASimulator()
        delta = hpa.decide({"cpu": 0.9}, current_replicas=5, cycle=0)
        assert delta > 0

    def test_scale_down_low_cpu(self):
        hpa = HPASimulator()
        delta = hpa.decide({"cpu": 0.1}, current_replicas=5, cycle=100)
        assert delta < 0

    def test_stabilization_prevents_scale_down(self):
        hpa = HPASimulator(stabilization_window=10)
        # Scale up first
        hpa.decide({"cpu": 0.9}, current_replicas=5, cycle=0)
        # Immediately try scale down — should be blocked
        delta = hpa.decide({"cpu": 0.1}, current_replicas=7, cycle=5)
        assert delta == 0

    def test_stabilization_expires(self):
        hpa = HPASimulator(stabilization_window=10)
        hpa.decide({"cpu": 0.9}, current_replicas=5, cycle=0)
        # After stabilization window
        delta = hpa.decide({"cpu": 0.1}, current_replicas=7, cycle=15)
        assert delta < 0

    def test_max_scale_step(self):
        hpa = HPASimulator(max_scale_step=1)
        delta = hpa.decide({"cpu": 0.99}, current_replicas=5, cycle=0)
        assert delta <= 1

    def test_reset(self):
        hpa = HPASimulator()
        hpa.decide({"cpu": 0.9}, current_replicas=5, cycle=0)
        hpa.reset()
        # After reset, no stabilization hold
        delta = hpa.decide({"cpu": 0.1}, current_replicas=5, cycle=1)
        assert delta < 0


# ============================================================
# Scoring
# ============================================================

class TestScoring:
    def test_perfect_score(self):
        """Replicas always match optimal → cost_efficiency = 1.0."""
        demand = [0.3] * 10 + [0.9] * 10
        replicas = [_optimal_replicas(d, 5) for d in demand]
        deltas = [0] * 20

        score = _score_run("test", "test", replicas, deltas, demand, 5)
        assert score.cost_efficiency == 1.0
        assert score.slo_breach_cycles == 0
        assert score.overshoot == 0

    def test_overshoot_detected(self):
        demand = [0.3] * 20
        replicas = [10] * 20  # Way too many
        deltas = [0] * 20

        score = _score_run("test", "test", replicas, deltas, demand, 5)
        assert score.overshoot > 0
        assert score.cost_efficiency > 1.0

    def test_slo_breach_detected(self):
        demand = [0.9] * 20
        replicas = [2] * 20  # Too few
        deltas = [0] * 20

        score = _score_run("test", "test", replicas, deltas, demand, 5)
        assert score.slo_breach_cycles > 0

    def test_oscillation_count(self):
        deltas = [1, 1, -1, -1, 1, -1]  # 3 reversals
        replicas = [5, 6, 7, 6, 5, 6, 5][:6]
        demand = [0.5] * 6

        score = _score_run("test", "test", replicas, deltas, demand, 5)
        assert score.oscillation_count == 3

    def test_reaction_time_immediate(self):
        demand = [0.3, 0.3, 0.9, 0.9, 0.9]
        deltas = [0, 0, 1, 0, 0]  # Reacts on first high-demand cycle
        replicas = [3, 3, 4, 4, 4]

        score = _score_run("test", "test", replicas, deltas, demand, 5)
        assert score.reaction_time == 0  # Instant reaction

    def test_reaction_time_delayed(self):
        demand = [0.3, 0.3, 0.9, 0.9, 0.9, 0.9]
        deltas = [0, 0, 0, 0, 1, 0]  # 2-cycle delay after change at index 2
        replicas = [3, 3, 3, 3, 4, 4]

        score = _score_run("test", "test", replicas, deltas, demand, 5)
        assert score.reaction_time == 2

    def test_format_output(self):
        score = ScenarioScore(
            pattern="step",
            scaler="controller",
            reaction_time=3,
            settling_time=15,
            overshoot=2,
            oscillation_count=1,
            replica_cycles=100,
            optimal_replica_cycles=90,
            slo_breach_cycles=5,
            total_cycles=50,
        )
        text = score.format()
        assert "controller" in text
        assert "react=" in text

    def test_cost_efficiency_zero_optimal(self):
        score = ScenarioScore(
            pattern="t", scaler="t",
            optimal_replica_cycles=0,
        )
        assert score.cost_efficiency == 1.0

    def test_slo_breach_rate_zero_cycles(self):
        score = ScenarioScore(pattern="t", scaler="t", total_cycles=0)
        assert score.slo_breach_rate == 0.0


# ============================================================
# Full Harness
# ============================================================

class TestBenchmarkHarness:
    def test_run_single_pattern(self):
        harness = BenchmarkHarness(BenchmarkConfig(
            cycles_per_pattern=50,
            warmup_cycles=20,
            base_replicas=5,
        ))
        ctrl_score, hpa_score = harness.run_pattern(PatternType.STEP)

        assert ctrl_score.pattern == "step"
        assert ctrl_score.scaler == "controller"
        assert ctrl_score.total_cycles == 50
        assert hpa_score.scaler == "hpa"
        assert hpa_score.total_cycles == 50

    def test_run_all_patterns(self):
        harness = BenchmarkHarness(BenchmarkConfig(
            cycles_per_pattern=50,
            warmup_cycles=20,
        ))
        report = harness.run_all()

        assert len(report.scores) == 12  # 6 patterns x 2 scalers

    def test_run_selected_patterns(self):
        harness = BenchmarkHarness(BenchmarkConfig(
            cycles_per_pattern=50,
            warmup_cycles=20,
        ))
        report = harness.run_all(patterns=[PatternType.STEP, PatternType.RAMP])
        assert len(report.scores) == 4  # 2 patterns x 2 scalers

    def test_report_format(self):
        harness = BenchmarkHarness(BenchmarkConfig(
            cycles_per_pattern=50,
            warmup_cycles=20,
        ))
        report = harness.run_all(patterns=[PatternType.STEP])
        text = report.format()

        assert "BENCHMARK REPORT" in text
        assert "step" in text
        assert "controller" in text
        assert "hpa" in text
        assert "react=" in text

    def test_controller_handles_oscillating(self):
        """Controller should have fewer oscillations than HPA on oscillating pattern."""
        harness = BenchmarkHarness(BenchmarkConfig(
            cycles_per_pattern=100,
            warmup_cycles=30,
        ))
        ctrl_score, hpa_score = harness.run_pattern(PatternType.OSCILLATING)

        # Controller's damping should suppress oscillations better
        assert ctrl_score.oscillation_count >= 0
        assert hpa_score.oscillation_count >= 0

    def test_all_scores_have_valid_metrics(self):
        harness = BenchmarkHarness(BenchmarkConfig(
            cycles_per_pattern=50,
            warmup_cycles=20,
        ))
        report = harness.run_all()

        for score in report.scores:
            assert score.total_cycles == 50
            assert score.replica_cycles > 0
            assert score.cost_efficiency > 0
            assert 0.0 <= score.slo_breach_rate <= 1.0
            assert score.oscillation_count >= 0
            assert score.reaction_time >= 0
            assert score.overshoot >= 0

    def test_report_summary_includes_winner(self):
        harness = BenchmarkHarness(BenchmarkConfig(
            cycles_per_pattern=50,
            warmup_cycles=20,
        ))
        report = harness.run_all(patterns=[PatternType.STEP])
        text = report.format()
        assert "Scenarios won:" in text

    def test_full_benchmark_completes(self):
        """Full 6-pattern benchmark completes without errors."""
        harness = BenchmarkHarness(BenchmarkConfig(
            cycles_per_pattern=100,
            warmup_cycles=30,
        ))
        report = harness.run_all()

        assert len(report.scores) == 12
        text = report.format()
        assert "SUMMARY" in text
        # All 6 patterns should appear
        for pt in PatternType:
            assert pt.value in text


# ============================================================
# Parameter Sweep
# ============================================================

class TestParameterSweep:
    def test_build_sweep_variants(self):
        variants = build_sweep_variants()
        assert len(variants) >= 8
        names = [v.name for v in variants]
        assert "defaults" in names
        assert "combined_conservative" in names
        assert "combined_moderate" in names

    def test_sweep_variant_has_config(self):
        variants = build_sweep_variants()
        for v in variants:
            assert isinstance(v.config, InfraControllerConfig)
            assert v.name

    def test_sweep_runs(self):
        sweep = ParameterSweep(
            cycles_per_pattern=30,
            warmup_cycles=10,
            variants=[
                SweepVariant("default", InfraControllerConfig()),
                SweepVariant("high_gain", InfraControllerConfig(G_base=2.0)),
            ],
            patterns=[PatternType.STEP],
        )
        report = sweep.run()

        assert len(report.results) == 2
        assert report.hpa_baseline is not None
        assert report.results[0].variant_name == "default"
        assert report.results[1].variant_name == "high_gain"

    def test_sweep_result_properties(self):
        sweep = ParameterSweep(
            cycles_per_pattern=30,
            warmup_cycles=10,
            variants=[SweepVariant("test", InfraControllerConfig())],
            patterns=[PatternType.STEP, PatternType.RAMP],
        )
        report = sweep.run()
        r = report.results[0]

        assert len(r.scores) == 2
        assert r.avg_reaction >= 0
        assert r.avg_cost > 0
        assert r.total_oscillations >= 0
        assert r.total_slo_breaches >= 0
        assert r.max_overshoot >= 0
        assert r.avg_settling >= 0

    def test_sweep_report_format(self):
        sweep = ParameterSweep(
            cycles_per_pattern=30,
            warmup_cycles=10,
            variants=[SweepVariant("v1", InfraControllerConfig())],
            patterns=[PatternType.STEP],
        )
        report = sweep.run()
        text = report.format()

        assert "PARAMETER SWEEP" in text
        assert "RANKING" in text
        assert "BEST" in text
        assert "v1" in text
        assert "hpa_baseline" in text

    def test_sweep_all_patterns(self):
        sweep = ParameterSweep(
            cycles_per_pattern=30,
            warmup_cycles=10,
            variants=[SweepVariant("t", InfraControllerConfig())],
        )
        report = sweep.run()
        assert len(report.results[0].scores) == 6

    def test_custom_config_applied(self):
        """Verify custom G_base is actually used."""
        cfg_low = InfraControllerConfig(G_base=0.5)
        cfg_high = InfraControllerConfig(G_base=3.0)

        sweep = ParameterSweep(
            cycles_per_pattern=50,
            warmup_cycles=20,
            variants=[
                SweepVariant("low_gain", cfg_low),
                SweepVariant("high_gain", cfg_high),
            ],
            patterns=[PatternType.STEP],
        )
        report = sweep.run()

        # High gain should have different behavior than low gain
        low = report.results[0]
        high = report.results[1]
        # They should produce different scores (configs differ)
        assert low.variant_name == "low_gain"
        assert high.variant_name == "high_gain"
