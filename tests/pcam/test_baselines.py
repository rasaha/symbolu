"""
Tests for PCAM baseline controllers.
"""

import pytest
from simulator.pcam.baselines.base import BaselineController, ControllerConfig
from simulator.pcam.baselines.sink_lru import SinkLRUController
from simulator.pcam.baselines.h2o import H2OController
from simulator.pcam.baselines.industry_style import IndustryStyleController


class TestControllerConfig:
    """Tests for controller configuration."""

    def test_default_config(self):
        """Test default configuration values."""
        config = ControllerConfig()
        assert config.cache_capacity == 256
        assert config.num_sinks == 4
        assert config.recent_window == 32
        assert config.top_k == 64

    def test_custom_config(self):
        """Test custom configuration."""
        config = ControllerConfig(
            cache_capacity=128,
            num_sinks=8,
            recent_window=64,
            top_k=32,
        )
        assert config.cache_capacity == 128
        assert config.num_sinks == 8


class TestSinkLRUController:
    """Tests for Sink+LRU baseline."""

    @pytest.fixture
    def controller(self):
        config = ControllerConfig(cache_capacity=16, num_sinks=2, recent_window=4, top_k=8)
        return SinkLRUController(config)

    def test_name(self, controller):
        """Test controller name."""
        assert controller.name == "sink_lru"

    def test_get_candidates_empty(self, controller):
        """Test getting candidates with empty state."""
        candidates = controller.get_candidates(query_block=0, k=8)
        # Should return sinks at minimum
        assert len(candidates) >= 2  # num_sinks

    def test_record_access(self, controller):
        """Test recording block access."""
        controller.record_access(
            query_block=5,
            accessed_blocks=[0, 1, 5, 6],
            attention_scores={0: 0.1, 1: 0.2, 5: 0.4, 6: 0.3},
        )

        # Check that blocks are tracked
        assert 5 in controller.state.cached_blocks
        assert 6 in controller.state.cached_blocks

    def test_lru_eviction(self, controller):
        """Test LRU eviction behavior."""
        # Fill cache beyond capacity
        for i in range(20):
            controller.record_access(
                query_block=i,
                accessed_blocks=[i],
                attention_scores={i: 0.5},
            )

        # Cache should be at or near capacity
        assert len(controller.state.cached_blocks) <= controller.config.cache_capacity

        # Sinks should still be present
        assert 0 in controller.state.cached_blocks
        assert 1 in controller.state.cached_blocks

    def test_sink_protection(self, controller):
        """Test that sinks are never evicted."""
        # Access sink blocks
        controller.record_access(
            query_block=0,
            accessed_blocks=[0, 1],
            attention_scores={0: 0.5, 1: 0.5},
        )

        # Try to evict
        evicted = controller.select_evictions(num_to_evict=10)

        # Sinks should not be in evicted list
        assert 0 not in evicted
        assert 1 not in evicted

    def test_reset(self, controller):
        """Test controller reset."""
        controller.record_access(
            query_block=5,
            accessed_blocks=[5, 6],
            attention_scores={5: 0.5, 6: 0.5},
        )

        controller.reset()

        assert len(controller.state.cached_blocks) == 0
        assert controller.state.hits == 0
        assert controller.state.misses == 0


class TestH2OController:
    """Tests for H2O baseline."""

    @pytest.fixture
    def controller(self):
        config = ControllerConfig(cache_capacity=16, num_sinks=2, recent_window=4, top_k=8)
        return H2OController(config)

    def test_name(self, controller):
        """Test controller name."""
        assert controller.name == "h2o"

    def test_attention_accumulation(self, controller):
        """Test that attention mass accumulates."""
        # Access same block multiple times with high attention
        for _ in range(5):
            controller.record_access(
                query_block=10,
                accessed_blocks=[5],
                attention_scores={5: 0.9},
            )

        # Block 5 should have high accumulated attention
        candidates = controller.get_candidates(query_block=10, k=8)
        candidate_ids = [c[0] for c in candidates]
        assert 5 in candidate_ids

    def test_heavy_hitter_priority(self, controller):
        """Test that heavy hitters are prioritized."""
        # Create a heavy hitter
        for _ in range(10):
            controller.record_access(
                query_block=20,
                accessed_blocks=[7],
                attention_scores={7: 0.8},
            )

        # Access many other blocks with lower attention
        for i in range(10, 20):
            controller.record_access(
                query_block=i,
                accessed_blocks=[i],
                attention_scores={i: 0.1},
            )

        candidates = controller.get_candidates(query_block=20, k=8)
        candidate_ids = [c[0] for c in candidates]

        # Heavy hitter should be in candidates
        assert 7 in candidate_ids

    def test_decay_application(self, controller):
        """Test that decay reduces old attention."""
        controller.record_access(
            query_block=5,
            accessed_blocks=[5],
            attention_scores={5: 1.0},
        )

        initial_mass = controller._attention_mass[5]

        # Record more accesses (which trigger decay)
        for i in range(10, 20):
            controller.record_access(
                query_block=i,
                accessed_blocks=[i],
                attention_scores={i: 0.1},
            )

        # Mass should have decayed
        assert controller._attention_mass[5] < initial_mass


class TestIndustryStyleController:
    """Tests for Industry-Style baseline."""

    @pytest.fixture
    def controller(self):
        config = ControllerConfig(cache_capacity=16, num_sinks=2, recent_window=4, top_k=8)
        return IndustryStyleController(config)

    def test_name(self, controller):
        """Test controller name."""
        assert controller.name == "industry_style"

    def test_ema_scoring(self, controller):
        """Test EMA score updates."""
        # High attention should lead to high EMA score
        controller.record_access(
            query_block=5,
            accessed_blocks=[5],
            attention_scores={5: 0.9},
        )

        assert 5 in controller._ema_scores
        assert controller._ema_scores[5] > 0

    def test_ghost_buffer(self, controller):
        """Test ghost buffer functionality."""
        # Fill cache to trigger evictions
        for i in range(20):
            controller.record_access(
                query_block=i,
                accessed_blocks=[i],
                attention_scores={i: 0.1},
            )
            controller.step()

        # Some blocks should be in ghost buffer
        assert len(controller._ghost_buffer) > 0

    def test_adaptive_hit_rate(self, controller):
        """Test adaptive hit rate tracking."""
        # Generate some accesses
        for i in range(10):
            controller.record_access(
                query_block=i,
                accessed_blocks=[i],
                attention_scores={i: 0.5},
            )

        # Hit rate should be tracked
        assert len(controller._hit_history) > 0

    def test_multi_strategy_candidates(self, controller):
        """Test that candidates come from multiple strategies."""
        # Set up different types of blocks
        # Sinks (0, 1)
        controller.record_access(
            query_block=0,
            accessed_blocks=[0, 1],
            attention_scores={0: 0.5, 1: 0.5},
        )

        # High EMA blocks
        for _ in range(5):
            controller.record_access(
                query_block=10,
                accessed_blocks=[5],
                attention_scores={5: 0.9},
            )
            controller.step()

        # Get candidates
        candidates = controller.get_candidates(query_block=10, k=8)
        candidate_ids = [c[0] for c in candidates]

        # Should include sinks
        assert 0 in candidate_ids
        assert 1 in candidate_ids

        # Should include high EMA block
        assert 5 in candidate_ids

    def test_stats(self, controller):
        """Test extended stats."""
        controller.record_access(
            query_block=5,
            accessed_blocks=[5, 6],
            attention_scores={5: 0.5, 6: 0.5},
        )

        stats = controller.get_stats()

        assert "ghost_buffer_size" in stats
        assert "recent_hit_rate" in stats
        assert "tracked_blocks" in stats


class TestControllerComparison:
    """Tests comparing all controllers."""

    @pytest.fixture
    def controllers(self):
        config = ControllerConfig(cache_capacity=32, num_sinks=4, recent_window=8, top_k=16)
        return [
            SinkLRUController(config),
            H2OController(config),
            IndustryStyleController(config),
        ]

    def test_all_return_candidates(self, controllers):
        """Test that all controllers return candidates."""
        for controller in controllers:
            candidates = controller.get_candidates(query_block=10, k=16)
            assert len(candidates) > 0

    def test_all_handle_access(self, controllers):
        """Test that all controllers handle access recording."""
        for controller in controllers:
            controller.record_access(
                query_block=5,
                accessed_blocks=[3, 4, 5],
                attention_scores={3: 0.3, 4: 0.3, 5: 0.4},
            )
            # Should not raise

    def test_all_support_eviction(self, controllers):
        """Test that all controllers support eviction."""
        for controller in controllers:
            # Add some blocks
            for i in range(50):
                controller.record_access(
                    query_block=i,
                    accessed_blocks=[i],
                    attention_scores={i: 0.5},
                )
                controller.step()

            # Should have evicted some blocks
            assert controller.state.evictions > 0

    def test_all_provide_stats(self, controllers):
        """Test that all controllers provide stats."""
        for controller in controllers:
            controller.record_access(
                query_block=5,
                accessed_blocks=[5],
                attention_scores={5: 0.5},
            )

            stats = controller.get_stats()

            assert "name" in stats
            assert "hits" in stats
            assert "misses" in stats
            assert "evictions" in stats
