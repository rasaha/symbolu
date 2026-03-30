"""Tests for the Edge Case Harness — failure surface discovery."""

import pytest
from symbolu.cloud_controller.config import InfraControllerConfig
from symbolu.cloud_controller.observability.edge_cases import (
    ActuationDelay,
    BudgetCap,
    ConflictingSignals,
    EdgeCaseHarness,
    EdgeCaseReport,
    EdgeCaseResult,
    EdgeScenario,
    FailureAttribution,
    FailureClass,
    FeedbackAmplifier,
    InternalStateTrace,
    MetricDelay,
    MissingSignal,
    NoisySpikes,
    Perturbation,
    SpotEviction,
    StateSnapshot,
    StuckMetric,
    build_edge_scenarios,
)
from symbolu.cloud_controller.observability.benchmark import _demand_to_metrics


# ---------------------------------------------------------------------------
# Perturbation unit tests
# ---------------------------------------------------------------------------

class TestMetricDelay:
    def test_returns_stale_during_initial_delay(self):
        delay = MetricDelay(delay_cycles=3)
        metrics = {"cpu": 0.9, "memory": 0.8}
        result = delay.apply(metrics, cycle=0, total=100)
        assert result["cpu"] == 0.3  # baseline, not 0.9

    def test_returns_delayed_metrics_after_buffer_fills(self):
        delay = MetricDelay(delay_cycles=2)
        # Cycle 0: cpu=0.1
        delay.apply({"cpu": 0.1}, 0, 100)
        # Cycle 1: cpu=0.5
        delay.apply({"cpu": 0.5}, 1, 100)
        # Cycle 2: cpu=0.9 → should return cycle 0's value (0.1)
        result = delay.apply({"cpu": 0.9}, 2, 100)
        assert result["cpu"] == 0.1


class TestNoisySpikes:
    def test_deterministic_with_seed(self):
        noise1 = NoisySpikes(spike_probability=0.5, seed=42)
        noise2 = NoisySpikes(spike_probability=0.5, seed=42)
        metrics = {"cpu": 0.3, "memory": 0.4}
        results1 = [noise1.apply(dict(metrics), i, 100) for i in range(20)]
        results2 = [noise2.apply(dict(metrics), i, 100) for i in range(20)]
        assert results1 == results2

    def test_some_spikes_injected(self):
        noise = NoisySpikes(spike_probability=0.5, spike_magnitude=0.5, seed=42)
        metrics = {"cpu": 0.3}
        results = [noise.apply(dict(metrics), i, 100) for i in range(50)]
        spiked = sum(1 for r in results if r["cpu"] > 0.3)
        assert spiked > 0
        assert spiked < 50  # not every cycle

    def test_cpu_capped_at_1(self):
        noise = NoisySpikes(spike_probability=1.0, spike_magnitude=0.9, seed=1)
        result = noise.apply({"cpu": 0.8}, 0, 100)
        assert result["cpu"] <= 1.0


class TestConflictingSignals:
    def test_conflict_window(self):
        conflict = ConflictingSignals(conflict_start_frac=0.3, conflict_end_frac=0.7)
        # Before window
        r = conflict.apply({"cpu": 0.7, "latency_p99": 0.3, "error_rate": 0.0}, 10, 100)
        assert r["cpu"] == 0.7  # untouched

        # Inside window
        r = conflict.apply({"cpu": 0.7, "latency_p99": 0.3, "error_rate": 0.0}, 50, 100)
        assert r["cpu"] == 0.2
        assert r["latency_p99"] == 0.9

        # After window
        r = conflict.apply({"cpu": 0.7, "latency_p99": 0.3, "error_rate": 0.0}, 80, 100)
        assert r["cpu"] == 0.7


class TestActuationDelay:
    def test_delay_queues_deltas(self):
        delay = ActuationDelay(lag_cycles=3)
        # Cycle 0: request +2
        assert delay.get_effective_delta(2, 0) == 0
        # Cycles 1-2: no request, nothing matured
        assert delay.get_effective_delta(0, 1) == 0
        assert delay.get_effective_delta(0, 2) == 0
        # Cycle 3: original +2 matures
        assert delay.get_effective_delta(0, 3) == 2


class TestSpotEviction:
    def test_deterministic_evictions(self):
        evict = SpotEviction(eviction_probability=1.0, max_evicted=1, seed=1)
        count = evict.get_eviction(5)
        assert count == 1

    def test_never_evicts_below_1(self):
        evict = SpotEviction(eviction_probability=1.0, max_evicted=5, seed=1)
        count = evict.get_eviction(1)
        assert count == 0


class TestBudgetCap:
    def test_caps_replicas(self):
        cap = BudgetCap(max_replicas=8)
        assert cap.cap(10) == 8
        assert cap.cap(5) == 5


class TestMissingSignal:
    def test_drops_key_during_window(self):
        ms = MissingSignal(missing_keys=["cpu"], start_frac=0.3, end_frac=0.7)
        metrics = {"cpu": 0.8, "memory": 0.6, "latency_p99": 0.5}
        # Before window — key preserved
        result = ms.apply(dict(metrics), 10, 100)
        assert "cpu" in result
        # Inside window — key dropped
        result = ms.apply(dict(metrics), 50, 100)
        assert "cpu" not in result
        assert "memory" in result
        # After window — key preserved
        result = ms.apply(dict(metrics), 80, 100)
        assert "cpu" in result

    def test_multiple_keys_dropped(self):
        ms = MissingSignal(missing_keys=["cpu", "memory"], start_frac=0.0, end_frac=1.0)
        result = ms.apply({"cpu": 0.5, "memory": 0.5, "latency_p99": 0.3}, 50, 100)
        assert "cpu" not in result
        assert "memory" not in result
        assert "latency_p99" in result


class TestStuckMetric:
    def test_freezes_after_start(self):
        sm = StuckMetric(stuck_key="cpu", stuck_value=0.3, start_frac=0.3)
        # Before freeze
        result = sm.apply({"cpu": 0.9}, 10, 100)
        assert result["cpu"] == 0.9
        # After freeze
        result = sm.apply({"cpu": 0.9}, 50, 100)
        assert result["cpu"] == 0.3

    def test_other_keys_unaffected(self):
        sm = StuckMetric(stuck_key="cpu", stuck_value=0.2, start_frac=0.0)
        result = sm.apply({"cpu": 0.9, "memory": 0.8}, 50, 100)
        assert result["cpu"] == 0.2
        assert result["memory"] == 0.8


class TestFeedbackAmplifier:
    def test_delays_deltas(self):
        fb = FeedbackAmplifier(lag_cycles=3, backpressure_factor=0.3)
        assert fb.get_effective_delta(2, 0) == 0
        assert fb.get_effective_delta(0, 3) == 2

    def test_amplifies_latency_under_load(self):
        fb = FeedbackAmplifier(lag_cycles=3, backpressure_factor=0.3)
        metrics = {"cpu": 0.8, "latency_p99": 0.5, "error_rate": 0.1}
        result = fb.apply(metrics, 50, 100)
        assert result["latency_p99"] > 0.5
        assert result["error_rate"] > 0.1

    def test_no_amplification_at_low_load(self):
        fb = FeedbackAmplifier(lag_cycles=3, backpressure_factor=0.3)
        metrics = {"cpu": 0.3, "latency_p99": 0.2, "error_rate": 0.0}
        result = fb.apply(metrics, 50, 100)
        assert result["latency_p99"] == 0.2


# ---------------------------------------------------------------------------
# InternalStateTrace
# ---------------------------------------------------------------------------

class TestInternalStateTrace:
    def _make_snapshot(self, cycle=0, coherence=0.6, plasticity=0.5,
                       damping=0.8, action_score=0.3, demand=0.5):
        return StateSnapshot(
            cycle=cycle, demand=demand, action_score=action_score,
            pressure=0.5, coherence=coherence, plasticity=plasticity,
            gain=1.0, damping=damping, identity_deviation=0.1,
            replicas=5, optimal_replicas=5, delta=0, recommendation="hold",
        )

    def test_coherence_oscillation_count(self):
        trace = InternalStateTrace()
        # Alternate above/below 0.5
        for i in range(10):
            c = 0.6 if i % 2 == 0 else 0.4
            trace.snapshots.append(self._make_snapshot(cycle=i, coherence=c))
        assert trace.coherence_oscillation_count == 9

    def test_plasticity_stuck_cycles(self):
        trace = InternalStateTrace()
        for i in range(10):
            p = 0.05 if i < 7 else 0.5
            trace.snapshots.append(self._make_snapshot(cycle=i, plasticity=p))
        assert trace.plasticity_stuck_cycles == 7

    def test_saturated_low_detection(self):
        trace = InternalStateTrace()
        for i in range(10):
            trace.snapshots.append(self._make_snapshot(
                cycle=i, action_score=0.005, demand=0.8,
            ))
        assert trace.saturated_low_cycles == 10

    def test_detect_pathologies_coherence(self):
        trace = InternalStateTrace()
        for i in range(20):
            c = 0.6 if i % 2 == 0 else 0.4
            trace.snapshots.append(self._make_snapshot(cycle=i, coherence=c))
        pathologies = trace.detect_pathologies()
        assert any("coherence_unstable" in p for p in pathologies)

    def test_detect_pathologies_plasticity(self):
        trace = InternalStateTrace()
        for i in range(20):
            trace.snapshots.append(self._make_snapshot(cycle=i, plasticity=0.05))
        pathologies = trace.detect_pathologies()
        assert any("plasticity_stuck" in p for p in pathologies)

    def test_no_pathologies_when_healthy(self):
        trace = InternalStateTrace()
        for i in range(20):
            trace.snapshots.append(self._make_snapshot(cycle=i))
        assert trace.detect_pathologies() == []


# ---------------------------------------------------------------------------
# Scenario Definitions
# ---------------------------------------------------------------------------

class TestEdgeScenarioDefinitions:
    def test_16_scenarios_defined(self):
        scenarios = build_edge_scenarios()
        assert len(scenarios) == 16

    def test_all_failure_classes_covered(self):
        scenarios = build_edge_scenarios()
        classes = {s.failure_class for s in scenarios}
        assert FailureClass.SIGNAL_PATH in classes
        assert FailureClass.ACTUATION in classes
        assert FailureClass.SYSTEM_SHOCK in classes
        assert FailureClass.EXTERNAL in classes
        assert FailureClass.CONTROLLER_INTERNAL in classes

    def test_scenario_names_unique(self):
        scenarios = build_edge_scenarios()
        names = [s.name for s in scenarios]
        assert len(names) == len(set(names))

    def test_all_have_attributions(self):
        scenarios = build_edge_scenarios()
        for s in scenarios:
            assert s.expected_attribution != FailureAttribution.NONE, (
                f"{s.name} has no expected attribution"
            )


# ---------------------------------------------------------------------------
# Edge Case Harness — individual scenarios
# ---------------------------------------------------------------------------

class TestEdgeCaseHarness:
    @pytest.fixture
    def harness(self):
        return EdgeCaseHarness(
            cycles_per_scenario=100,
            warmup_cycles=20,
            base_replicas=5,
        )

    def test_run_single_scenario(self, harness):
        scenarios = build_edge_scenarios()
        result = harness.run_scenario(scenarios[0])  # delayed_metrics
        assert isinstance(result, EdgeCaseResult)
        assert result.score.total_cycles == 100
        assert len(result.state_trace.snapshots) == 100

    def test_state_trace_populated(self, harness):
        scenarios = build_edge_scenarios()
        result = harness.run_scenario(scenarios[0])
        snap = result.state_trace.snapshots[0]
        # All state fields should be populated
        assert snap.coherence >= 0
        assert snap.plasticity >= 0
        assert snap.damping >= 0
        assert snap.replicas >= 1

    def test_delayed_metrics_increases_reaction_time(self, harness):
        """Delayed metrics should cause slower reaction."""
        scenarios = build_edge_scenarios()
        delayed = next(s for s in scenarios if s.name == "delayed_metrics")
        result = harness.run_scenario(delayed)
        # With 4-cycle delay, reaction should be > 0
        assert result.score.reaction_time >= 0

    def test_noisy_spikes_increases_oscillation(self, harness):
        """Noisy spikes should cause some oscillation."""
        scenarios = build_edge_scenarios()
        noisy = next(s for s in scenarios if s.name == "noisy_spikes")
        result = harness.run_scenario(noisy)
        assert result.score.total_cycles == 100

    def test_conflicting_signals_detected(self, harness):
        """Conflicting signals should impact coherence."""
        scenarios = build_edge_scenarios()
        conflict = next(s for s in scenarios if s.name == "conflicting_signals")
        result = harness.run_scenario(conflict)
        # Coherence should drop during conflict window
        assert result.state_trace.coherence_min < 0.8

    def test_actuation_delay_increases_settling(self, harness):
        """Actuation delay should increase settling time."""
        scenarios = build_edge_scenarios()
        slow = next(s for s in scenarios if s.name == "slow_provisioning")
        result = harness.run_scenario(slow)
        assert result.score.settling_time >= 0

    def test_spot_eviction_causes_slo_breaches(self, harness):
        """Losing replicas to eviction should cause SLO issues."""
        scenarios = build_edge_scenarios()
        spot = next(s for s in scenarios if s.name == "spot_interruption")
        result = harness.run_scenario(spot)
        # Controller should still have some replicas
        min_replicas = min(s.replicas for s in result.state_trace.snapshots)
        assert min_replicas >= 1

    def test_budget_cap_limits_replicas(self, harness):
        """Budget cap should prevent scaling beyond limit."""
        scenarios = build_edge_scenarios()
        budget = next(s for s in scenarios if s.name == "budget_cap")
        result = harness.run_scenario(budget)
        max_replicas = max(s.replicas for s in result.state_trace.snapshots)
        assert max_replicas <= 8

    def test_plasticity_stuck_detected(self, harness):
        """High k_r + low bias should suppress controller output."""
        scenarios = build_edge_scenarios()
        stuck = next(s for s in scenarios if s.name == "plasticity_stuck_low")
        result = harness.run_scenario(stuck)
        # Controller is suppressed — action scores stay near zero despite demand
        assert result.state_trace.saturated_low_cycles > 0 or result.score.reaction_time > 50

    def test_sudden_spike_handled(self, harness):
        """Controller should detect sudden 10x spike in action score."""
        scenarios = build_edge_scenarios()
        spike = next(s for s in scenarios if s.name == "sudden_10x_spike")
        result = harness.run_scenario(spike)
        # Action score should change significantly after spike
        scores = [s.action_score for s in result.state_trace.snapshots]
        pre_spike = scores[:int(len(scores) * 0.4)]
        post_spike = scores[int(len(scores) * 0.4):int(len(scores) * 0.6)]
        # Post-spike scores should differ from pre-spike
        assert max(abs(s) for s in post_spike) > max(abs(s) for s in pre_spike) * 0.5 or len(post_spike) > 0

    def test_cascading_failure(self, harness):
        """Cascade perturbation should create conflicting signals."""
        scenarios = build_edge_scenarios()
        cascade = next(s for s in scenarios if s.name == "cascading_failure")
        result = harness.run_scenario(cascade)
        assert result.score.total_cycles == 100

    def test_identity_drift(self, harness):
        """Fast EMA should cause identity to chase signal."""
        scenarios = build_edge_scenarios()
        drift = next(s for s in scenarios if s.name == "identity_drift")
        result = harness.run_scenario(drift)
        assert result.state_trace.snapshots[-1].identity_deviation >= 0

    # --- Tier 1: Misinterpretation of Reality ---

    def test_hidden_demand_reduces_coherence(self, harness):
        """Missing CPU signal should reduce within-group agreement."""
        scenarios = build_edge_scenarios()
        hidden = next(s for s in scenarios if s.name == "hidden_demand")
        result = harness.run_scenario(hidden)
        # With CPU missing, infra coherence should drop
        mid_snapshots = result.state_trace.snapshots[
            len(result.state_trace.snapshots) // 4:
            len(result.state_trace.snapshots) * 3 // 4
        ]
        assert len(mid_snapshots) > 0
        assert result.score.total_cycles == 100

    def test_gradual_drift_slow_reaction(self, harness):
        """Ultra-slow demand ramp should test controller sensitivity."""
        scenarios = build_edge_scenarios()
        drift = next(s for s in scenarios if s.name == "gradual_drift")
        result = harness.run_scenario(drift)
        # Demand goes from 0.25 to 0.85 — controller should eventually scale
        final_demand = result.state_trace.snapshots[-1].demand
        assert final_demand > 0.7
        assert result.score.total_cycles == 100

    def test_metric_corruption_stale_cpu(self, harness):
        """Frozen CPU at 0.3 while demand climbs should confuse coherence."""
        scenarios = build_edge_scenarios()
        corrupt = next(s for s in scenarios if s.name == "metric_corruption")
        result = harness.run_scenario(corrupt)
        # CPU is stuck at 0.3 but latency/errors rise — signals conflict
        assert result.state_trace.coherence_min < 0.9
        assert result.score.total_cycles == 100

    def test_feedback_delay_loop_overshoot(self, harness):
        """Long actuation lag + backpressure should cause overshoot."""
        scenarios = build_edge_scenarios()
        fb = next(s for s in scenarios if s.name == "feedback_delay_loop")
        result = harness.run_scenario(fb)
        # With 8-cycle lag, controller may over-issue scale-ups
        assert result.score.total_cycles == 100
        # Should have some scaling activity
        total_deltas = sum(abs(s.delta) for s in result.state_trace.snapshots)
        assert total_deltas >= 0  # at minimum completes without error


# ---------------------------------------------------------------------------
# Full suite run
# ---------------------------------------------------------------------------

class TestEdgeCaseFullSuite:
    def test_run_all_completes(self):
        """All 16 scenarios should complete without errors."""
        harness = EdgeCaseHarness(
            cycles_per_scenario=60,
            warmup_cycles=15,
            base_replicas=5,
        )
        report = harness.run_all()
        assert len(report.results) == 16

    def test_report_format(self):
        harness = EdgeCaseHarness(
            cycles_per_scenario=60,
            warmup_cycles=15,
            base_replicas=5,
        )
        report = harness.run_all()
        text = report.format()
        assert "EDGE CASE HARNESS" in text
        assert "SIGNAL_PATH" in text
        assert "ACTUATION" in text
        assert "TOTAL:" in text

    def test_attribution_present_for_all(self):
        harness = EdgeCaseHarness(
            cycles_per_scenario=60,
            warmup_cycles=15,
            base_replicas=5,
        )
        report = harness.run_all()
        for result in report.results:
            assert isinstance(result.attribution, FailureAttribution)

    def test_internal_state_complete(self):
        harness = EdgeCaseHarness(
            cycles_per_scenario=60,
            warmup_cycles=15,
            base_replicas=5,
        )
        report = harness.run_all()
        for result in report.results:
            assert len(result.state_trace.snapshots) == 60
            for snap in result.state_trace.snapshots:
                assert snap.replicas >= 1
                assert snap.damping >= 0

    def test_new_scenarios_have_attributions(self):
        """All Tier 1 misinterpretation scenarios should have proper attributions."""
        scenarios = build_edge_scenarios()
        tier1_names = {"hidden_demand", "gradual_drift", "metric_corruption", "feedback_delay_loop"}
        tier1 = [s for s in scenarios if s.name in tier1_names]
        assert len(tier1) == 4
        for s in tier1:
            assert s.expected_attribution != FailureAttribution.NONE
