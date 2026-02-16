"""Tests for USE-6G metrics collection."""

import pytest

from simulator.use_6g.core.metrics import (
    LatencyStats,
    SyncMetrics,
    BeamformingMetrics,
    PowerMetrics,
    ThroughputMetrics,
    USE6GMetrics,
    MetricsCollector,
)


class TestLatencyStats:
    """Tests for latency statistics."""

    def test_empty_stats(self):
        stats = LatencyStats()
        assert stats.count == 0
        assert stats.mean == 0.0
        assert stats.p50 == 0.0
        assert stats.p95 == 0.0
        assert stats.p99 == 0.0

    def test_single_sample(self):
        stats = LatencyStats()
        stats.add(100.0)
        assert stats.count == 1
        assert stats.mean == 100.0
        assert stats.p50 == 100.0

    def test_multiple_samples(self):
        stats = LatencyStats()
        for v in [10, 20, 30, 40, 50]:
            stats.add(float(v))
        assert stats.count == 5
        assert stats.mean == 30.0
        assert stats.p50 == 30.0

    def test_percentiles_ordered(self):
        stats = LatencyStats()
        for v in range(100):
            stats.add(float(v))
        assert stats.p50 <= stats.p95 <= stats.p99

    def test_to_dict(self):
        stats = LatencyStats()
        stats.add(100.0)
        d = stats.to_dict()
        assert "count" in d
        assert "mean" in d
        assert "p50" in d
        assert "p95" in d
        assert "p99" in d


class TestSyncMetrics:
    """Tests for synchronization metrics."""

    def test_empty_metrics(self):
        m = SyncMetrics()
        assert m.mean_coherence == 0.0
        assert m.mean_phase_error_deg == 0.0
        assert m.lock_ratio == 0.0

    def test_add_coherence(self):
        m = SyncMetrics()
        m.add_coherence(0.95)
        m.add_coherence(0.97)
        assert abs(m.mean_coherence - 0.96) < 1e-10

    def test_lock_ratio(self):
        m = SyncMetrics()
        m.lock_time_us = 800.0
        m.total_time_us = 1000.0
        assert abs(m.lock_ratio - 0.8) < 1e-10

    def test_to_dict(self):
        m = SyncMetrics()
        m.add_coherence(0.95)
        d = m.to_dict()
        assert "mean_coherence" in d
        assert "lock_ratio" in d


class TestBeamformingMetrics:
    """Tests for beamforming metrics."""

    def test_empty_metrics(self):
        m = BeamformingMetrics()
        assert m.mean_gain_db == 0.0
        assert m.steer_success_rate == 0.0

    def test_record_steer(self):
        m = BeamformingMetrics()
        m.record_steer(True)
        m.record_steer(True)
        m.record_steer(False)
        assert m.total_steers == 3
        assert abs(m.steer_success_rate - 2 / 3) < 1e-10

    def test_gain_tracking(self):
        m = BeamformingMetrics()
        m.add_gain(18.0)
        m.add_gain(20.0)
        assert abs(m.mean_gain_db - 19.0) < 1e-10


class TestPowerMetrics:
    """Tests for power metrics."""

    def test_empty_metrics(self):
        m = PowerMetrics()
        assert m.total_energy_wus == 0.0
        assert m.peak_power_w == 0.0

    def test_peak_power_tracked(self):
        m = PowerMetrics()
        m.add_power_sample(3.0, 10.0)
        m.add_power_sample(8.0, 5.0)
        m.add_power_sample(2.0, 20.0)
        assert m.peak_power_w == 8.0


class TestThroughputMetrics:
    """Tests for throughput metrics."""

    def test_empty(self):
        m = ThroughputMetrics()
        assert m.sync_ops_per_sec == 0.0

    def test_ops_per_sec(self):
        m = ThroughputMetrics()
        m.total_sync_ops = 1000
        m.total_time_us = 1000.0  # 1ms
        # 1000 ops / 0.001 sec = 1,000,000 ops/sec
        assert abs(m.sync_ops_per_sec - 1e6) < 1.0


class TestUSE6GMetrics:
    """Tests for aggregate metrics."""

    def test_acceptance_gates_all_pass(self):
        """With ideal values, all gates should pass."""
        m = USE6GMetrics()
        m.sync.add_coherence(0.99)
        m.sync.add_phase_error(1.0)
        m.sync.time_to_lock_samples.append(100.0)
        m.beamforming.add_gain(20.0)
        m.throughput.total_sync_ops = 200000
        m.throughput.total_beam_ops = 20000
        m.throughput.total_time_us = 1e6  # 1 second
        m.power.peak_power_w = 15.0

        gates = m.check_acceptance_gates()
        assert gates["sync_coherence"] is True
        assert gates["phase_error"] is True
        assert gates["beam_gain"] is True
        assert gates["power"] is True

    def test_acceptance_gates_coherence_fail(self):
        m = USE6GMetrics()
        m.sync.add_coherence(0.5)  # Below 0.95 threshold
        gates = m.check_acceptance_gates()
        assert gates["sync_coherence"] is False

    def test_to_dict(self):
        m = USE6GMetrics()
        d = m.to_dict()
        assert "sync" in d
        assert "beamforming" in d
        assert "power" in d
        assert "throughput" in d

    def test_summary_string(self):
        m = USE6GMetrics()
        m.sync.add_coherence(0.95)
        summary = m.summary()
        assert "USE-6G Metrics" in summary
        assert "Synchronization:" in summary
        assert "Beamforming:" in summary
        assert "Power:" in summary


class TestMetricsCollector:
    """Tests for metrics collection during simulation."""

    def test_start_and_finalize(self):
        c = MetricsCollector()
        c.start(0.0)
        c.record_sync_step(0.95, 3.0, 5.0, 100.0, 3.0)
        metrics = c.finalize()
        assert isinstance(metrics, USE6GMetrics)
        assert metrics.sync.mean_coherence > 0

    def test_record_sync_step(self):
        c = MetricsCollector()
        c.start(0.0)
        c.record_sync_step(0.95, 3.0, 5.0, 10.0, 3.0)
        c.record_sync_step(0.97, 2.0, 4.0, 20.0, 3.0)
        metrics = c.finalize()
        assert len(metrics.sync.coherence_samples) == 2
        assert metrics.throughput.total_sync_ops == 2

    def test_record_beam_steer(self):
        c = MetricsCollector()
        c.start(0.0)
        c.record_beam_steer(18.0, -13.0, True, 10.0, 8.0)
        metrics = c.finalize()
        assert metrics.beamforming.total_steers == 1
        assert metrics.beamforming.successful_steers == 1
        assert metrics.throughput.total_beam_ops == 1

    def test_record_lock_maintenance(self):
        c = MetricsCollector()
        c.start(0.0)
        c.record_lock_maintained(500.0)
        c.record_lock_maintained(300.0)
        assert c.metrics.sync.lock_time_us == 800.0

    def test_record_idle(self):
        c = MetricsCollector()
        c.start(0.0)
        c.record_idle(100.0, 0.5)
        assert c.metrics.power.idle_energy_wus == 50.0

    def test_lock_acquired_tracking(self):
        c = MetricsCollector()
        c.start(0.0)
        c._lock_start_time = 0.0
        c.record_lock_acquired(100.0, 10)
        assert len(c.metrics.sync.time_to_lock_samples) == 1
        assert c.metrics.sync.time_to_lock_samples[0] == 100.0
