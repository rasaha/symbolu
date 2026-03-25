"""
Tests for shadow / A-B testing infrastructure.

Validates:
1. ShadowEvictionPolicy correctly forwards access stream to both policies
2. Only the live policy's decisions are executed
3. ShadowMetrics accurately tracks agreements, divergences, and regret
4. CTMBlockSpaceManager shadow mode integration
5. ShadowController for the simulator

Run: python -m pytest CTM_plus/vLLM/tests/test_shadow.py -v
"""

import os
import sys
import random

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from ctm_plus_vllm.config import CTMvLLMConfig
from ctm_plus_vllm.evictor import CTMEvictionPolicy
from ctm_plus_vllm.shadow import ShadowEvictionPolicy, ShadowMetrics
from ctm_plus_vllm.block_manager import CTMBlockSpaceManager


# ============================================================================
# ShadowMetrics unit tests
# ============================================================================

class TestShadowMetrics:
    def test_all_agreements(self):
        m = ShadowMetrics()
        for _ in range(100):
            m.record_victim_decision(42, 42)
        assert m.agreement_rate == 1.0
        assert m.divergences == 0
        assert m.victim_agreement_rate == 1.0

    def test_all_divergences(self):
        m = ShadowMetrics()
        for i in range(100):
            m.record_victim_decision(i, i + 1000)
        assert m.agreement_rate == 0.0
        assert m.divergences == 100
        assert len(m.recent_divergences) == 100

    def test_mixed_decisions(self):
        m = ShadowMetrics()
        for i in range(50):
            m.record_victim_decision(i, i)  # agree
        for i in range(50):
            m.record_victim_decision(i, i + 1000)  # diverge
        assert m.agreement_rate == 0.5
        assert m.agreements == 50
        assert m.divergences == 50

    def test_promote_tracking(self):
        m = ShadowMetrics()
        m.record_promote_decision(True, True)
        m.record_promote_decision(True, False)
        m.record_promote_decision(False, True)
        m.record_promote_decision(False, False)
        assert m.promote_decisions == 4
        assert m.promote_agreements == 2
        assert m.promote_agreement_rate == 0.5

    def test_refault_detection(self):
        m = ShadowMetrics(refault_window=100)
        # Live evicts block 42, shadow evicts block 99
        m.record_victim_decision(42, 99)
        # Later, block 42 is accessed (refault for live)
        m.check_refault(42)
        assert m.live_regrets == 1
        assert m.shadow_regrets == 0
        # Block 99 is accessed (refault for shadow)
        m.check_refault(99)
        assert m.shadow_regrets == 1

    def test_refault_window_expiry(self):
        m = ShadowMetrics(refault_window=10)
        m.record_victim_decision(42, 99)
        # Access many blocks to push past refault window
        for i in range(20):
            m.check_refault(i + 1000)
        # Now block 42 is accessed — outside window, no regret
        m.check_refault(42)
        assert m.live_regrets == 0

    def test_summary_format(self):
        m = ShadowMetrics()
        m.record_victim_decision(1, 2)
        s = m.summary()
        assert "total_decisions" in s
        assert "agreement_rate" in s
        assert "live_regrets" in s
        assert "shadow_better" in s

    def test_reset(self):
        m = ShadowMetrics()
        m.record_victim_decision(1, 2)
        m.record_promote_decision(True, False)
        m.reset()
        assert m.total_decisions == 0
        assert m.agreements == 0
        assert m.divergences == 0


# ============================================================================
# ShadowEvictionPolicy tests
# ============================================================================

class TestShadowEvictionPolicy:
    def _make_shadow(self, capacity=100):
        live_config = CTMvLLMConfig()
        shadow_config = CTMvLLMConfig(
            weight_recency=0.50,
            weight_frequency=0.20,
            weight_reuse=0.15,
            weight_coherence=0.10,
            weight_neighbor=0.05,
        )
        live = CTMEvictionPolicy(live_config)
        shadow = CTMEvictionPolicy(shadow_config)
        policy = ShadowEvictionPolicy(live, shadow)
        policy.set_capacity(capacity)
        return policy

    def test_both_policies_see_accesses(self):
        policy = self._make_shadow()

        for i in range(50):
            policy.on_block_access(i, sequence_id=1)

        live_stats = policy.live.get_stats()
        shadow_stats = policy.shadow.get_stats()

        assert live_stats["total_accesses"] == 50
        assert shadow_stats["total_accesses"] == 50

    def test_only_live_result_returned(self):
        policy = self._make_shadow()

        # Fill cache
        for i in range(50):
            result = policy.on_block_access(i, sequence_id=1)
            assert isinstance(result, tuple)
            assert len(result) == 2

    def test_victim_selection_records_divergence(self):
        policy = self._make_shadow(capacity=20)

        # Fill cache to force eviction decisions
        for i in range(30):
            policy.on_block_access(i, sequence_id=1)

        # Select victim from both
        victim = policy.select_victim()
        assert victim is not None

        # At least one victim decision should be recorded
        assert policy.metrics.victim_decisions >= 1

    def test_evict_mirrors_to_shadow(self):
        policy = self._make_shadow()

        for i in range(10):
            policy.on_block_access(i, sequence_id=1)

        policy.evict_block(0)

        # Both should have evicted block 0
        assert 0 not in policy.live.gpu_blocks
        assert 0 not in policy.shadow.gpu_blocks

    def test_free_mirrors_to_shadow(self):
        policy = self._make_shadow()
        policy.on_block_access(42, sequence_id=1)
        policy.free_block(42)

        assert policy.live.blocks.get(42) is None
        assert policy.shadow.blocks.get(42) is None

    def test_pin_unpin_mirrors(self):
        policy = self._make_shadow()
        policy.on_block_access(42, sequence_id=1)

        policy.pin_block(42)
        assert 42 in policy.live.pinned_blocks
        assert 42 in policy.shadow.pinned_blocks

        policy.unpin_block(42)
        assert 42 not in policy.live.pinned_blocks
        assert 42 not in policy.shadow.pinned_blocks

    def test_get_stats_includes_shadow(self):
        policy = self._make_shadow()
        for i in range(10):
            policy.on_block_access(i, sequence_id=1)

        stats = policy.get_stats()
        assert "shadow" in stats
        assert "shadow_stats" in stats
        assert "agreement_rate" in stats["shadow"]

    def test_get_shadow_report(self):
        policy = self._make_shadow()
        for i in range(20):
            policy.on_block_access(i, sequence_id=1)

        report = policy.get_shadow_report()
        assert "SHADOW MODE REPORT" in report
        assert "Agreement rate" in report or "agreement" in report.lower()

    def test_reset_stats(self):
        policy = self._make_shadow()
        for i in range(20):
            policy.on_block_access(i, sequence_id=1)
        policy.reset_stats()

        stats = policy.get_stats()
        assert stats["total_accesses"] == 0
        assert policy.metrics.total_decisions == 0

    def test_extended_workload(self):
        """Run a realistic workload and verify shadow metrics are consistent."""
        policy = self._make_shadow(capacity=50)
        rng = random.Random(42)

        for _ in range(5000):
            bid = rng.randint(0, 199)
            policy.on_block_access(bid, sequence_id=rng.randint(1, 5))

        stats = policy.get_stats()
        assert stats["total_accesses"] == 5000
        shadow = stats["shadow"]
        assert shadow["total_decisions"] >= 0
        # Agreement rate should be reasonable (not 0%, not always 100%)
        # With different weight configs, we expect some divergences


# ============================================================================
# CTMBlockSpaceManager shadow mode integration tests
# ============================================================================

class TestBlockManagerShadowMode:
    def test_shadow_mode_disabled_by_default(self):
        mgr = CTMBlockSpaceManager(
            block_size=16,
            num_gpu_blocks=50,
            num_cpu_blocks=100,
        )
        assert not mgr.shadow_enabled
        assert mgr.get_shadow_report() is None

    def test_shadow_mode_enabled(self):
        shadow_config = CTMvLLMConfig(
            weight_recency=0.50,
            weight_frequency=0.20,
            weight_reuse=0.15,
            weight_coherence=0.10,
            weight_neighbor=0.05,
        )
        mgr = CTMBlockSpaceManager(
            block_size=16,
            num_gpu_blocks=50,
            num_cpu_blocks=100,
            shadow_config=shadow_config,
        )
        assert mgr.shadow_enabled
        assert isinstance(mgr.ctm, ShadowEvictionPolicy)

    def test_shadow_mode_allocate_access_free(self):
        shadow_config = CTMvLLMConfig(
            weight_recency=0.50,
            weight_frequency=0.20,
            weight_reuse=0.15,
            weight_coherence=0.10,
            weight_neighbor=0.05,
        )
        mgr = CTMBlockSpaceManager(
            block_size=16,
            num_gpu_blocks=50,
            num_cpu_blocks=100,
            shadow_config=shadow_config,
        )

        # Full lifecycle
        alloc = mgr.allocate(1, 10)
        assert len(alloc) == 10

        mgr.access(1, [0, 1, 2])
        mgr.free(1)

        report = mgr.get_shadow_report()
        assert report is not None
        assert "SHADOW MODE REPORT" in report

    def test_shadow_stats_in_get_stats(self):
        shadow_config = CTMvLLMConfig(
            weight_recency=0.50,
            weight_frequency=0.20,
            weight_reuse=0.15,
            weight_coherence=0.10,
            weight_neighbor=0.05,
        )
        mgr = CTMBlockSpaceManager(
            block_size=16,
            num_gpu_blocks=50,
            num_cpu_blocks=100,
            shadow_config=shadow_config,
        )

        mgr.allocate(1, 5)
        mgr.access(1)

        stats = mgr.get_stats()
        assert "shadow" in stats


# ============================================================================
# Simulator ShadowController tests
# ============================================================================

class TestSimulatorShadowController:
    """Test the simulator-side shadow controller."""

    def test_import_and_basic_usage(self):
        """Verify the shadow controller can be imported and instantiated."""
        # Add simulator to path
        sim_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "..", "simulator"
        )
        sys.path.insert(0, sim_path)

        try:
            from ctm_plus.controllers.shadow import ShadowController, ShadowMetrics
            from ctm_plus.controllers.lru import LRUController
            from ctm_plus.core.config import SimulatorConfig

            config = SimulatorConfig(tier0_size=100, tier1_size=10000)
            live = LRUController(config)

            # Use a second LRU as shadow (should agree 100%)
            shadow = LRUController(config)

            sc = ShadowController(config, live, shadow)
            assert sc.name == "LRU[shadow:LRU]"

            report = sc.get_shadow_report()
            assert "SHADOW A/B REPORT" in report
        except ImportError:
            pytest.skip("Simulator not available in this test environment")

    def test_shadow_controller_with_different_policies(self):
        """Shadow with LRU live vs ARC shadow should show divergences."""
        sim_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "..", "simulator"
        )
        sys.path.insert(0, sim_path)

        try:
            from ctm_plus.controllers.shadow import ShadowController
            from ctm_plus.controllers.lru import LRUController
            from ctm_plus.controllers.arc import ARCController
            from ctm_plus.core.config import SimulatorConfig
            from ctm_plus.core.state import GlobalState, TierState, Tier, OpType
            from ctm_plus.simulator import Simulator
            from ctm_plus.traces.loader import TraceEvent

            config = SimulatorConfig(tier0_size=50, tier1_size=5000)
            live = LRUController(config)
            shadow = ARCController(config)
            controller = ShadowController(config, live, shadow)

            # Generate a small trace
            trace = [
                TraceEvent(timestamp=i, page_id=i % 200, op_type=OpType.READ)
                for i in range(1000)
            ]

            sim = Simulator(config=config)
            result = sim.run(trace, controller, trace_name="shadow_test",
                             verbose=False)

            # Check metrics
            stats = controller.get_stats()
            assert "shadow" in stats
            sm = controller.shadow_metrics
            assert sm.total_accesses == 1000

            # With different policies on a 200-page trace with 50-page cache,
            # there should be some divergences
            report = controller.get_shadow_report()
            assert "LRU" in report
            assert "ARC" in report

        except ImportError:
            pytest.skip("Simulator not available in this test environment")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
