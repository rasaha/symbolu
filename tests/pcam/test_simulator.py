"""
Tests for PCAM simulator.
"""

import pytest
from simulator.pcam.simulator import PCAMSimulator, SimulationResult, run_quick_validation
from simulator.pcam.core.config import PCAMConfig
from simulator.pcam.core.metrics import PCAMMetrics, MetricsCollector, LatencyStats
from simulator.pcam.core.state import AttentionState, BlockScore
from simulator.pcam.interface import SoftwarePCAMInterface
from simulator.pcam.traces.generators import (
    generate_chat_trace,
    generate_long_context_trace,
)
from simulator.pcam.baselines import (
    SinkLRUController,
    H2OController,
    IndustryStyleController,
)
from simulator.pcam.baselines.base import ControllerConfig


class TestPCAMConfig:
    """Tests for PCAM configuration."""

    def test_default_config(self):
        """Test default configuration."""
        config = PCAMConfig()
        assert config.max_entries == 1_000_000
        assert config.max_sequences == 64
        assert config.banks.num_banks == 64

    def test_latency_calculation(self):
        """Test latency calculation."""
        config = PCAMConfig()

        # ATTEND latency
        latency = config.calculate_attend_latency(num_candidates=64, bank_conflicts=0)
        assert latency > 0
        assert latency < 1000  # Should be under 1us

        # With conflicts
        latency_with_conflicts = config.calculate_attend_latency(
            num_candidates=64, bank_conflicts=10
        )
        assert latency_with_conflicts > latency

    def test_update_latency_calculation(self):
        """Test UPDATE latency calculation."""
        config = PCAMConfig()

        latency = config.calculate_update_latency(coalesced_count=1)
        assert latency > 0

        # Coalesced updates should be more efficient per-op
        batch_latency = config.calculate_update_latency(coalesced_count=10)
        assert batch_latency > latency  # Total is higher
        assert batch_latency < latency * 10  # But less than 10x


class TestAttentionState:
    """Tests for attention state management."""

    @pytest.fixture
    def state(self):
        return AttentionState(max_sequences=4, max_blocks_per_sequence=256, num_banks=16)

    def test_sequence_allocation(self, state):
        """Test sequence allocation."""
        assert state.allocate_sequence(0, 256)
        assert state.allocate_sequence(1, 256)

        # Should have 2 sequences
        assert len(state.sequences) == 2

    def test_sequence_free(self, state):
        """Test sequence freeing."""
        state.allocate_sequence(0, 256)
        assert state.free_sequence(0)
        assert len(state.sequences) == 0

    def test_attend_operation(self, state):
        """Test ATTEND operation."""
        state.allocate_sequence(0, 256)

        # Add some attention data
        state.update(0, 5, 10, 0.8, step=0)
        state.update(0, 5, 11, 0.6, step=1)
        state.update(0, 5, 12, 0.9, step=2)

        # ATTEND should return candidates
        candidates, conflicts = state.attend(0, 5, k=3)

        assert len(candidates) <= 3
        assert conflicts >= 0

    def test_update_operation(self, state):
        """Test UPDATE operation."""
        state.allocate_sequence(0, 256)

        success = state.update(0, 5, 10, 0.8, step=0)
        assert success

        # Check that score was updated
        seq = state.get_sequence(0)
        assert 10 in seq.block_scores
        assert seq.block_scores[10].score > 0

    def test_decay_operation(self, state):
        """Test DECAY operation."""
        state.allocate_sequence(0, 256)
        state.update(0, 5, 10, 1.0, step=0)

        initial_score = state.get_sequence(0).block_scores[10].score

        state.decay(0.5)

        new_score = state.get_sequence(0).block_scores[10].score
        assert new_score < initial_score

    def test_get_block_scores(self, state):
        """Test getting block scores."""
        state.allocate_sequence(0, 256)
        state.update(0, 5, 10, 0.8, step=0)
        state.update(0, 5, 11, 0.6, step=1)

        scores = state.get_block_scores(0, [10, 11, 12])

        assert 10 in scores
        assert 11 in scores
        assert 12 in scores
        assert scores[10] > 0
        assert scores[12] == 0  # Never updated


class TestSoftwarePCAMInterface:
    """Tests for software PCAM interface."""

    @pytest.fixture
    def interface(self):
        return SoftwarePCAMInterface(max_sequences=4, max_blocks_per_sequence=256)

    def test_allocate_sequence(self, interface):
        """Test sequence allocation via interface."""
        assert interface.allocate_sequence(0, 256)
        assert interface.allocate_sequence(1, 128)

    def test_attend_interface(self, interface):
        """Test ATTEND via interface."""
        interface.allocate_sequence(0, 256)

        candidates, latency, conflicts = interface.attend(
            query_block_id=5,
            k=32,
            sequence_id=0,
        )

        assert isinstance(candidates, list)
        assert latency > 0
        assert conflicts >= 0

    def test_update_interface(self, interface):
        """Test UPDATE via interface."""
        interface.allocate_sequence(0, 256)

        success, latency = interface.update(
            query_block_id=5,
            key_block_id=10,
            weight=0.8,
            sequence_id=0,
        )

        assert success
        assert latency > 0

    def test_batch_update_interface(self, interface):
        """Test batch UPDATE via interface."""
        interface.allocate_sequence(0, 256)

        count, latency = interface.update_batch(
            sequence_id=0,
            block_ids=[10, 11, 12, 13],
            weights=[0.4, 0.3, 0.2, 0.1],
        )

        assert count == 4
        assert latency > 0


class TestMetrics:
    """Tests for metrics collection."""

    def test_latency_stats(self):
        """Test latency statistics."""
        stats = LatencyStats()

        for i in range(100):
            stats.add(float(i))

        assert stats.count == 100
        assert stats.p50 == pytest.approx(49.5, abs=1)
        assert stats.p95 > stats.p50
        assert stats.p99 > stats.p95

    def test_metrics_collector(self):
        """Test metrics collector."""
        collector = MetricsCollector(controller_name="test")
        collector.start()

        for i in range(10):
            collector.record_attend(
                latency_ns=100.0,
                candidates=[0, 1, 2],
                true_top_k=[0, 1, 2],
                bank_conflicts=0,
            )
            collector.record_update(latency_ns=50.0, count=1)
            collector.record_token()

        metrics = collector.finalize()

        assert metrics.attend_latency.count == 10
        assert metrics.update_latency.count == 10
        assert metrics.throughput.total_tokens == 10
        assert metrics.quality.mean_coverage == 1.0  # Perfect coverage

    def test_acceptance_gates(self):
        """Test acceptance gate checking."""
        metrics = PCAMMetrics(controller_name="test")

        # Set up metrics that should pass
        for _ in range(100):
            metrics.attend_latency.add(80.0)  # Under 100ns threshold

        metrics.quality.candidate_coverage_samples = [0.85] * 100  # Above 80%
        metrics.throughput.total_tokens = 1000
        metrics.throughput.total_time_ns = 1e9  # 1 second

        gates = metrics.check_acceptance_gates()

        assert gates["hw_attend_p50"]  # p50 under 100ns
        assert gates["quality_coverage"]  # Coverage above 80%


class TestPCAMSimulator:
    """Tests for PCAM simulator."""

    @pytest.fixture
    def simulator(self):
        config = PCAMConfig()
        config.topk.default_k = 16
        return PCAMSimulator(config=config, verbose=False)

    @pytest.fixture
    def small_trace(self):
        return generate_chat_trace(num_turns=2, tokens_per_turn=(5, 10), top_k=16)

    def test_run_pcam(self, simulator, small_trace):
        """Test running PCAM simulation."""
        result = simulator.run_pcam(small_trace, "test_trace", progress_interval=1000)

        assert isinstance(result, SimulationResult)
        assert result.controller_name == "pcam"
        assert result.elapsed_time_sec > 0
        assert result.metrics.throughput.total_tokens > 0

    def test_run_baseline(self, simulator, small_trace):
        """Test running baseline simulation."""
        config = ControllerConfig(cache_capacity=32, num_sinks=2, recent_window=8, top_k=16)
        controller = SinkLRUController(config)

        result = simulator.run_baseline(
            small_trace, controller, "test_trace", progress_interval=1000
        )

        assert isinstance(result, SimulationResult)
        assert result.controller_name == "sink_lru"
        assert result.elapsed_time_sec > 0

    def test_compare_results(self, simulator, small_trace):
        """Test result comparison."""
        config = ControllerConfig(cache_capacity=32, num_sinks=2, recent_window=8, top_k=16)

        # Run multiple controllers
        results = [
            simulator.run_pcam(small_trace, "test"),
            simulator.run_baseline(small_trace, SinkLRUController(config), "test"),
            simulator.run_baseline(small_trace, H2OController(config), "test"),
        ]

        comparison = simulator.compare_results(results)

        assert "results" in comparison
        assert len(comparison["results"]) == 3
        assert "best_throughput" in comparison

    def test_full_validation(self, simulator):
        """Test full validation suite."""
        # Small traces for testing
        traces = {
            "mini_chat": generate_chat_trace(num_turns=2, tokens_per_turn=(5, 10)),
        }

        config = ControllerConfig(cache_capacity=32, num_sinks=2, recent_window=8, top_k=16)
        controllers = [
            SinkLRUController(config),
            H2OController(config),
        ]

        results = simulator.run_full_validation(traces, controllers)

        assert "by_workload" in results
        assert "mini_chat" in results["by_workload"]
        assert "summary" in results


class TestQuickValidation:
    """Tests for quick validation function."""

    def test_quick_validation_runs(self):
        """Test that quick validation completes."""
        results = run_quick_validation(seed=42, verbose=False)

        assert "by_workload" in results
        assert "summary" in results
        assert "acceptance_gates" in results

    def test_quick_validation_has_workloads(self):
        """Test that quick validation covers multiple workloads."""
        results = run_quick_validation(seed=42, verbose=False)

        workloads = results["by_workload"].keys()
        assert len(workloads) >= 2  # At least chat and one other


class TestIntegration:
    """Integration tests for the full PCAM framework."""

    def test_end_to_end_chat_workload(self):
        """Test end-to-end with chat workload."""
        trace = generate_chat_trace(num_turns=5, tokens_per_turn=(20, 40))

        simulator = PCAMSimulator(verbose=False)

        config = ControllerConfig(cache_capacity=64, num_sinks=4, recent_window=16, top_k=32)
        controllers = [
            SinkLRUController(config),
            H2OController(config),
            IndustryStyleController(config),
        ]

        # Run all
        results = [simulator.run_pcam(trace, "chat")]
        for ctrl in controllers:
            results.append(simulator.run_baseline(trace, ctrl, "chat"))

        # Compare
        comparison = simulator.compare_results(results)

        # Should have results for all controllers
        assert len(comparison["results"]) == 4

        # PCAM should have acceptance gates
        if "acceptance_gates" in comparison:
            assert isinstance(comparison["acceptance_gates"], dict)

    def test_end_to_end_long_context(self):
        """Test end-to-end with long context workload."""
        trace = generate_long_context_trace(context_length=2048, num_queries=30)

        simulator = PCAMSimulator(verbose=False)

        result = simulator.run_pcam(trace, "long_context")

        # Should complete successfully
        assert result.metrics.throughput.total_tokens == 30
        assert result.metrics.attend_latency.count == 30

    def test_metrics_are_reasonable(self):
        """Test that metrics are in reasonable ranges."""
        trace = generate_chat_trace(num_turns=3, tokens_per_turn=(10, 20))

        simulator = PCAMSimulator(verbose=False)
        result = simulator.run_pcam(trace, "chat")

        # Latencies should be positive and reasonable
        assert result.metrics.attend_latency.p50 > 0
        assert result.metrics.attend_latency.p50 < 10000  # Under 10us

        # Coverage should be between 0 and 1
        if result.metrics.quality.candidate_coverage_samples:
            assert 0 <= result.metrics.quality.mean_coverage <= 1

        # Throughput should be positive
        assert result.metrics.throughput.tokens_per_second >= 0
