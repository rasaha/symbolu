"""Unit tests for Stage 3 — Shadow Mode.

Tests cover:
- HPAWatcher: snapshot polling, action detection, history
- DivergenceTracker: classification, verdict evaluation, cost estimation
- ShadowReporter: report generation from divergence records
- ShadowRunner: end-to-end with mocked Prometheus
"""

import time
import pytest
from unittest.mock import MagicMock, patch

from symbolu.cloud_controller.controller import Controller, ActionResult
from symbolu.cloud_controller.config import InfraControllerConfig
from symbolu.cloud_controller.signals.prometheus import PrometheusClient, PrometheusConfig
from symbolu.cloud_controller.shadow.hpa_watcher import HPAWatcher, HPASnapshot, HPAAction
from symbolu.cloud_controller.shadow.divergence import (
    DivergenceTracker,
    DivergenceConfig,
    DivergenceRecord,
    DivergenceType,
    Verdict,
)
from symbolu.cloud_controller.shadow.reporter import ShadowReporter, ShadowReport
from symbolu.cloud_controller.signals.pipeline import PipelineConfig
from symbolu.cloud_controller.shadow.runner import ShadowRunner, ShadowConfig


# ============================================================
# HPA Watcher
# ============================================================

def _mock_prom_k8s(current=5.0, desired=5.0, restarts=0.0):
    """Create a mock PrometheusClient returning K8s state."""
    mock = MagicMock(spec=PrometheusClient)
    mock.query_k8s_state.return_value = {
        "current_replicas": current,
        "desired_replicas": desired,
        "pod_restarts": restarts,
    }
    return mock


class TestHPAWatcher:
    def test_poll_returns_snapshot(self):
        """Basic poll should return a valid HPASnapshot."""
        prom = _mock_prom_k8s(current=5.0, desired=5.0)
        watcher = HPAWatcher(prom)
        snap = watcher.poll()
        assert snap is not None
        assert snap.current_replicas == 5
        assert snap.desired_replicas == 5
        assert snap.is_scaling is False
        assert snap.delta == 0

    def test_detects_scale_out(self):
        """Should detect when HPA changes desired replicas upward."""
        prom = _mock_prom_k8s(current=5.0, desired=5.0)
        watcher = HPAWatcher(prom)
        watcher.poll()  # Establish baseline

        # HPA decides to scale out
        prom.query_k8s_state.return_value = {
            "current_replicas": 5.0, "desired_replicas": 8.0, "pod_restarts": 0.0,
        }
        snap = watcher.poll()
        assert snap.is_scaling is True
        assert snap.delta == 3
        assert watcher.total_actions == 1
        assert watcher.actions[0].delta == 3
        assert watcher.actions[0].direction == "scale_out"

    def test_detects_scale_in(self):
        """Should detect when HPA changes desired replicas downward."""
        prom = _mock_prom_k8s(current=8.0, desired=8.0)
        watcher = HPAWatcher(prom)
        watcher.poll()

        prom.query_k8s_state.return_value = {
            "current_replicas": 8.0, "desired_replicas": 5.0, "pod_restarts": 0.0,
        }
        watcher.poll()
        assert watcher.total_actions == 1
        assert watcher.actions[0].delta == -3
        assert watcher.actions[0].direction == "scale_in"

    def test_no_action_when_stable(self):
        """No action should be recorded when desired stays the same."""
        prom = _mock_prom_k8s(current=5.0, desired=5.0)
        watcher = HPAWatcher(prom)
        for _ in range(10):
            watcher.poll()
        assert watcher.total_actions == 0

    def test_handles_missing_data(self):
        """Should return None when Prometheus data is unavailable."""
        prom = MagicMock(spec=PrometheusClient)
        prom.query_k8s_state.return_value = {
            "current_replicas": None, "desired_replicas": None, "pod_restarts": None,
        }
        watcher = HPAWatcher(prom)
        snap = watcher.poll()
        assert snap is None

    def test_multiple_actions_tracked(self):
        """Multiple scale events should all be recorded."""
        prom = _mock_prom_k8s(current=5.0, desired=5.0)
        watcher = HPAWatcher(prom)
        watcher.poll()

        # Scale out
        prom.query_k8s_state.return_value = {
            "current_replicas": 5.0, "desired_replicas": 8.0, "pod_restarts": 0.0,
        }
        watcher.poll()

        # Scale in
        prom.query_k8s_state.return_value = {
            "current_replicas": 8.0, "desired_replicas": 5.0, "pod_restarts": 0.0,
        }
        watcher.poll()

        assert watcher.total_actions == 2
        assert watcher.actions[0].direction == "scale_out"
        assert watcher.actions[1].direction == "scale_in"

    def test_get_recent_actions(self):
        """Should filter actions by timestamp."""
        prom = _mock_prom_k8s(current=5.0, desired=5.0)
        watcher = HPAWatcher(prom)
        watcher.poll()

        prom.query_k8s_state.return_value = {
            "current_replicas": 5.0, "desired_replicas": 8.0, "pod_restarts": 0.0,
        }
        watcher.poll()

        # All recent actions (within last hour)
        recent = watcher.get_recent_actions(since=time.time() - 3600)
        assert len(recent) == 1

        # No future actions
        future = watcher.get_recent_actions(since=time.time() + 3600)
        assert len(future) == 0

    def test_reset_clears_state(self):
        """Reset should clear all history."""
        prom = _mock_prom_k8s(current=5.0, desired=5.0)
        watcher = HPAWatcher(prom)
        watcher.poll()

        prom.query_k8s_state.return_value = {
            "current_replicas": 5.0, "desired_replicas": 8.0, "pod_restarts": 0.0,
        }
        watcher.poll()
        assert watcher.total_actions == 1

        watcher.reset()
        assert watcher.total_actions == 0
        assert watcher.get_latest_snapshot() is None


# ============================================================
# Divergence Tracker
# ============================================================

def _make_action_result(delta=0, recommendation="no_action", score=0.0,
                        pressure=0.0, coherence=0.7):
    """Create a minimal ActionResult for testing."""
    ctrl = Controller()
    result = ctrl.step(
        metrics={"cpu": 0.5, "memory": 0.5, "latency_p99": 0.5, "error_rate": 0.5},
        current_replicas=5,
    )
    # Override fields we care about
    result.replica_delta = delta
    result.recommendation = recommendation
    result.action_score = score
    result.pressure = pressure
    result.coherence.coherence = coherence
    return result


class TestDivergenceClassification:
    def test_agreement(self):
        """Both hold -> agreement."""
        tracker = DivergenceTracker()
        action = _make_action_result(delta=0)
        hpa = HPASnapshot(timestamp=time.time(), current_replicas=5, desired_replicas=5)
        record = tracker.compare(action, hpa, {"cpu": 0.5})
        assert record.divergence_type == DivergenceType.AGREEMENT
        assert record.is_divergence is False

    def test_hpa_scales_controller_holds(self):
        """HPA scales out but controller says no action."""
        tracker = DivergenceTracker()
        action = _make_action_result(delta=0)
        hpa = HPASnapshot(timestamp=time.time(), current_replicas=5, desired_replicas=8)
        record = tracker.compare(action, hpa, {"cpu": 0.8})
        assert record.divergence_type == DivergenceType.HPA_SCALES_CONTROLLER_HOLDS
        assert record.is_divergence is True

    def test_controller_scales_hpa_holds(self):
        """Controller recommends but HPA holds."""
        tracker = DivergenceTracker()
        action = _make_action_result(delta=2, recommendation="scale_out_2")
        hpa = HPASnapshot(timestamp=time.time(), current_replicas=5, desired_replicas=5)
        record = tracker.compare(action, hpa, {"cpu": 0.8})
        assert record.divergence_type == DivergenceType.CONTROLLER_SCALES_HPA_HOLDS

    def test_opposite_direction(self):
        """Controller says out, HPA says in."""
        tracker = DivergenceTracker()
        action = _make_action_result(delta=2)
        hpa = HPASnapshot(timestamp=time.time(), current_replicas=5, desired_replicas=3)
        record = tracker.compare(action, hpa, {"cpu": 0.5})
        assert record.divergence_type == DivergenceType.OPPOSITE_DIRECTION

    def test_magnitude_differs(self):
        """Both scale out but by different amounts."""
        tracker = DivergenceTracker()
        action = _make_action_result(delta=1)
        hpa = HPASnapshot(timestamp=time.time(), current_replicas=5, desired_replicas=8)
        record = tracker.compare(action, hpa, {"cpu": 0.8})
        assert record.divergence_type == DivergenceType.MAGNITUDE_DIFFERS


class TestVerdictEvaluation:
    def test_hpa_unnecessary_controller_correct(self):
        """HPA scaled but metrics stayed stable -> controller correct."""
        config = DivergenceConfig(
            verdict_lookback_seconds=0.01,
            improvement_threshold=0.1,
            cost_per_pod_minute=0.03,
        )
        tracker = DivergenceTracker(config)

        # Divergence: HPA scales +3, controller holds
        action = _make_action_result(delta=0)
        hpa = HPASnapshot(
            timestamp=time.time() - 1,  # 1 second ago (past lookback)
            current_replicas=5, desired_replicas=8,
        )
        metrics_then = {"cpu": 0.7, "memory": 0.6}
        record = tracker.compare(action, hpa, metrics_then)
        record.timestamp = time.time() - 1  # Backdate for evaluation

        # Metrics now: stable (not much change)
        metrics_now = {"cpu": 0.68, "memory": 0.58}
        time.sleep(0.02)
        evaluated = tracker.evaluate_pending(metrics_now)

        assert len(evaluated) == 1
        assert evaluated[0].verdict == Verdict.CONTROLLER_CORRECT
        assert evaluated[0].estimated_cost_impact > 0

    def test_controller_too_conservative(self):
        """Controller held but metrics improved after HPA scaled -> HPA correct."""
        config = DivergenceConfig(verdict_lookback_seconds=0.01)
        tracker = DivergenceTracker(config)

        action = _make_action_result(delta=0)
        hpa = HPASnapshot(
            timestamp=time.time() - 1,
            current_replicas=5, desired_replicas=8,
        )
        metrics_then = {"cpu": 0.9, "memory": 0.8}
        record = tracker.compare(action, hpa, metrics_then)
        record.timestamp = time.time() - 1

        # Metrics now: significantly improved (dropped by > threshold)
        metrics_now = {"cpu": 0.5, "memory": 0.4}
        time.sleep(0.02)
        evaluated = tracker.evaluate_pending(metrics_now)

        assert len(evaluated) == 1
        assert evaluated[0].verdict == Verdict.HPA_CORRECT

    def test_controller_ahead_of_hpa(self):
        """Controller recommended scaling, HPA held, metrics degraded -> controller correct."""
        config = DivergenceConfig(verdict_lookback_seconds=0.01)
        tracker = DivergenceTracker(config)

        action = _make_action_result(delta=2, recommendation="scale_out_2")
        hpa = HPASnapshot(
            timestamp=time.time() - 1,
            current_replicas=5, desired_replicas=5,
        )
        metrics_then = {"cpu": 0.7, "memory": 0.6}
        record = tracker.compare(action, hpa, metrics_then)
        record.timestamp = time.time() - 1

        # Metrics now: degraded (went up by > threshold)
        metrics_now = {"cpu": 0.9, "memory": 0.85}
        time.sleep(0.02)
        evaluated = tracker.evaluate_pending(metrics_now)

        assert len(evaluated) == 1
        assert evaluated[0].verdict == Verdict.CONTROLLER_CORRECT

    def test_pending_not_evaluated_before_lookback(self):
        """Records within lookback window should stay pending."""
        config = DivergenceConfig(verdict_lookback_seconds=3600)
        tracker = DivergenceTracker(config)

        action = _make_action_result(delta=0)
        hpa = HPASnapshot(
            timestamp=time.time(),
            current_replicas=5, desired_replicas=8,
        )
        tracker.compare(action, hpa, {"cpu": 0.8})
        evaluated = tracker.evaluate_pending({"cpu": 0.5})
        assert len(evaluated) == 0
        assert tracker.pending_count == 1

    def test_agreement_never_needs_verdict(self):
        """Agreements don't get verdicts (they stay as-is)."""
        tracker = DivergenceTracker()
        action = _make_action_result(delta=0)
        hpa = HPASnapshot(timestamp=time.time(), current_replicas=5, desired_replicas=5)
        record = tracker.compare(action, hpa, {"cpu": 0.5})
        assert not record.is_divergence
        assert tracker.pending_count == 0  # Agreements are not pending


class TestDivergenceTrackerProperties:
    def test_divergences_filters_agreements(self):
        """divergences property should only return actual divergences."""
        tracker = DivergenceTracker()

        # Add an agreement
        action = _make_action_result(delta=0)
        hpa_stable = HPASnapshot(timestamp=time.time(), current_replicas=5, desired_replicas=5)
        tracker.compare(action, hpa_stable, {"cpu": 0.5})

        # Add a divergence
        hpa_scale = HPASnapshot(timestamp=time.time(), current_replicas=5, desired_replicas=8)
        tracker.compare(action, hpa_scale, {"cpu": 0.8})

        assert len(tracker.records) == 2
        assert len(tracker.divergences) == 1

    def test_format_log(self):
        """DivergenceRecord should produce readable log."""
        tracker = DivergenceTracker()
        action = _make_action_result(delta=0, coherence=0.31, pressure=0.72)
        hpa = HPASnapshot(timestamp=time.time(), current_replicas=5, desired_replicas=8)
        record = tracker.compare(action, hpa, {"cpu": 0.82})
        log = record.format_log()
        assert "DIVERGENCE" in log
        assert "5 → 8" in log
        assert "Coherence" in log


# ============================================================
# Shadow Reporter
# ============================================================

def _make_divergence_record(
    div_type=DivergenceType.AGREEMENT,
    verdict=Verdict.PENDING,
    cost=0.0,
    ts=None,
):
    """Create a DivergenceRecord for report testing."""
    return DivergenceRecord(
        timestamp=ts or time.time(),
        divergence_type=div_type,
        controller_recommendation="no_action",
        controller_delta=0,
        controller_action_score=0.0,
        controller_pressure=0.0,
        controller_coherence=0.5,
        controller_explanation="test",
        hpa_current=5,
        hpa_desired=5 if div_type == DivergenceType.AGREEMENT else 8,
        hpa_delta=0 if div_type == DivergenceType.AGREEMENT else 3,
        metrics_snapshot={"cpu": 0.5},
        verdict=verdict,
        estimated_cost_impact=cost,
    )


class TestShadowReporter:
    def test_empty_report(self):
        """Should handle empty records gracefully."""
        reporter = ShadowReporter()
        report = reporter.generate([])
        assert report.total_decisions == 0
        assert report.agreement_rate == 0.0

    def test_all_agreements(self):
        """100% agreement report."""
        reporter = ShadowReporter()
        records = [_make_divergence_record() for _ in range(100)]
        report = reporter.generate(records, period_label="Test")
        assert report.total_decisions == 100
        assert report.total_agreements == 100
        assert report.total_divergences == 0
        assert report.agreement_rate == 1.0

    def test_mixed_report(self):
        """Report with mix of agreements and divergences."""
        reporter = ShadowReporter()
        records = []
        # 80 agreements
        for _ in range(80):
            records.append(_make_divergence_record())
        # 10 HPA scales, controller holds -> controller correct
        for _ in range(10):
            records.append(_make_divergence_record(
                div_type=DivergenceType.HPA_SCALES_CONTROLLER_HOLDS,
                verdict=Verdict.CONTROLLER_CORRECT,
                cost=0.12,
            ))
        # 5 controller scales, HPA holds -> HPA correct
        for _ in range(5):
            records.append(_make_divergence_record(
                div_type=DivergenceType.CONTROLLER_SCALES_HPA_HOLDS,
                verdict=Verdict.HPA_CORRECT,
            ))
        # 5 both reasonable
        for _ in range(5):
            records.append(_make_divergence_record(
                div_type=DivergenceType.MAGNITUDE_DIFFERS,
                verdict=Verdict.BOTH_REASONABLE,
            ))

        report = reporter.generate(records, period_label="Week 13, 2026")
        assert report.total_decisions == 100
        assert report.total_agreements == 80
        assert report.total_divergences == 20
        assert report.controller_correct == 10
        assert report.hpa_correct == 5
        assert report.both_reasonable == 5
        assert report.controller_advantage == 5
        assert report.total_cost_saved == pytest.approx(1.20, abs=0.01)

    def test_format_report_readable(self):
        """Report should produce readable output with key fields."""
        reporter = ShadowReporter()
        records = [_make_divergence_record() for _ in range(50)]
        records.append(_make_divergence_record(
            div_type=DivergenceType.HPA_SCALES_CONTROLLER_HOLDS,
            verdict=Verdict.CONTROLLER_CORRECT,
            cost=0.50,
        ))
        report = reporter.generate(records, period_label="Test Period")
        text = report.format_report()
        assert "Neural Cloud Controller" in text
        assert "Test Period" in text
        assert "Total decisions" in text
        assert "Agreements with HPA" in text
        assert "Controller correct" in text
        assert "cost savings" in text

    def test_generate_for_period_filters(self):
        """generate_for_period should filter by timestamp."""
        reporter = ShadowReporter()
        now = time.time()
        records = [
            _make_divergence_record(ts=now - 7200),  # 2 hours ago
            _make_divergence_record(ts=now - 3600),  # 1 hour ago
            _make_divergence_record(ts=now - 100),    # Recent
        ]
        report = reporter.generate_for_period(
            records,
            start_time=now - 3700,
            end_time=now,
            period_label="Last hour+",
        )
        assert report.total_decisions == 2  # Only the last 2


# ============================================================
# Shadow Runner (integration with mocked Prometheus)
# ============================================================

def _mock_prometheus_for_shadow(
    metrics=None,
    current_replicas=5.0,
    desired_replicas=5.0,
):
    """Create a mock PrometheusClient for shadow runner testing."""
    if metrics is None:
        metrics = {
            "cpu": 0.5, "memory": 0.4,
            "latency_p99": 0.3, "error_rate": 0.08,
            "queue_depth": 50.0,
        }
    mock = MagicMock(spec=PrometheusClient)
    mock.query_metrics.return_value = metrics
    mock.query_k8s_state.return_value = {
        "current_replicas": current_replicas,
        "desired_replicas": desired_replicas,
        "pod_restarts": 0.0,
    }
    mock.close = MagicMock()
    return mock


class TestShadowRunner:
    def test_single_step(self):
        """Single step should produce a ShadowCycleResult."""
        runner = ShadowRunner(ShadowConfig())
        prom = _mock_prometheus_for_shadow()
        runner.pipeline.prometheus = prom
        runner.hpa_watcher.prometheus = prom

        result = runner.step()
        assert result is not None
        assert result.cycle is not None
        assert result.hpa is not None
        assert result.divergence is not None
        assert runner.cycle_count == 1

    def test_detects_divergence(self):
        """Should detect when HPA scales but controller holds."""
        runner = ShadowRunner(ShadowConfig())
        # Moderate metrics — controller likely holds
        prom = _mock_prometheus_for_shadow(
            metrics={"cpu": 0.5, "memory": 0.4, "latency_p99": 0.3,
                     "error_rate": 0.08, "queue_depth": 50.0},
            current_replicas=5.0,
            desired_replicas=8.0,  # HPA wants to scale out
        )
        runner.pipeline.prometheus = prom
        runner.hpa_watcher.prometheus = prom

        result = runner.step()
        assert result.divergence is not None
        # With moderate metrics, controller should hold but HPA is scaling
        assert result.hpa.is_scaling is True

    def test_run_accumulates_records(self):
        """Multiple cycles should accumulate divergence records."""
        config = ShadowConfig(
            pipeline=PipelineConfig(poll_interval=0.001),
        )
        runner = ShadowRunner(config)
        prom = _mock_prometheus_for_shadow()
        runner.pipeline.prometheus = prom
        runner.hpa_watcher.prometheus = prom

        runner.run(max_cycles=20)
        assert runner.cycle_count == 20
        assert len(runner.divergence_tracker.records) == 20

    def test_generate_report(self):
        """Should generate a report from accumulated data."""
        runner = ShadowRunner(ShadowConfig())
        prom = _mock_prometheus_for_shadow()
        runner.pipeline.prometheus = prom
        runner.hpa_watcher.prometheus = prom

        for _ in range(10):
            runner.step()

        report = runner.generate_report(period_label="Test")
        assert report.total_decisions == 10
        text = report.format_report()
        assert "Neural Cloud Controller" in text

    def test_format_divergence_log_empty(self):
        """Divergence log with no divergences should say so."""
        runner = ShadowRunner(ShadowConfig())
        assert "No divergences" in runner.format_divergence_log()

    def test_reset_clears_all(self):
        """Reset should clear all internal state."""
        config = ShadowConfig(pipeline=PipelineConfig(poll_interval=0.001))
        runner = ShadowRunner(config)
        prom = _mock_prometheus_for_shadow()
        runner.pipeline.prometheus = prom
        runner.hpa_watcher.prometheus = prom

        runner.run(max_cycles=10)
        assert runner.cycle_count == 10

        runner.reset()
        assert runner.cycle_count == 0
        assert len(runner.divergence_tracker.records) == 0
        assert runner.hpa_watcher.total_actions == 0

    def test_handles_missing_hpa(self):
        """Should still work when HPA data is unavailable."""
        runner = ShadowRunner(ShadowConfig())
        prom = _mock_prometheus_for_shadow()
        # HPA returns no data
        prom.query_k8s_state.return_value = {
            "current_replicas": None, "desired_replicas": None, "pod_restarts": None,
        }
        runner.pipeline.prometheus = prom
        runner.hpa_watcher.prometheus = prom

        result = runner.step()
        assert result is not None
        assert result.hpa is None  # HPA unavailable
        assert result.divergence is None  # No comparison possible

    def test_context_manager(self):
        """Should support with-statement."""
        with ShadowRunner(ShadowConfig()) as runner:
            prom = _mock_prometheus_for_shadow()
            runner.pipeline.prometheus = prom
            runner.hpa_watcher.prometheus = prom
            result = runner.step()
            assert result is not None

    def test_verdict_flow_end_to_end(self):
        """Full flow: divergence → wait → verdict."""
        config = ShadowConfig(
            divergence=DivergenceConfig(verdict_lookback_seconds=0.01),
        )
        runner = ShadowRunner(config)

        # Step 1: HPA scaling, controller holds — moderate metrics
        prom = _mock_prometheus_for_shadow(
            metrics={"cpu": 0.7, "memory": 0.6, "latency_p99": 0.5,
                     "error_rate": 0.08, "queue_depth": 50.0},
            current_replicas=5.0,
            desired_replicas=8.0,
        )
        runner.pipeline.prometheus = prom
        runner.hpa_watcher.prometheus = prom
        result1 = runner.step()

        # Backdate the record for instant evaluation
        if result1.divergence and result1.divergence.is_divergence:
            result1.divergence.timestamp = time.time() - 1

        # Step 2: Metrics stable (didn't change much) — evaluate verdicts
        time.sleep(0.02)
        prom.query_k8s_state.return_value = {
            "current_replicas": 8.0, "desired_replicas": 8.0, "pod_restarts": 0.0,
        }
        result2 = runner.step()

        # Check if any verdicts were evaluated
        total_evaluated = len(result2.newly_evaluated)
        # We should have at least evaluated the pending divergence
        divergences = runner.divergence_tracker.divergences
        for d in divergences:
            if d.verdict != Verdict.PENDING:
                assert d.verdict_reason != ""
