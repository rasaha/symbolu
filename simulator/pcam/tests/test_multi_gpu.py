"""
Tests for Multi-GPU CXL Shared Edge Pool.

Validates:
  1. CXLCoherenceTracker: MESI states, invalidation, exclusive access
  2. CXLCapacityManager: expansion, contraction, rebalancing
  3. EdgeDiscoveryService: cross-host edge discovery
  4. MultiGPUPCAMCoordinator: end-to-end multi-GPU orchestration
  5. Per-host quota management
  6. Cross-host edge sharing and coherence correctness
"""

import pytest
from simulator.pcam.core.tiered_config import (
    TieredPCAMConfig,
    CXLPoolConfig,
    TierType,
)
from simulator.pcam.tiered_pcam import (
    CXLEdgePool,
    CompressedBlockEntry,
    TieredPCAMInterface,
)
from simulator.pcam.multi_gpu import (
    CoherenceState,
    CXLCoherenceTracker,
    CXLCapacityManager,
    EdgeDiscoveryService,
    MultiGPUPCAMCoordinator,
)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _make_entry(block_id, score=1.0, seq_id=0, owner=0):
    entry = CompressedBlockEntry(block_id=block_id, sequence_id=seq_id)
    entry.score = score
    entry.owner_host = owner
    return entry


# ---------------------------------------------------------------------------
# CXL Coherence Tracker Tests
# ---------------------------------------------------------------------------

class TestCXLCoherenceTracker:
    """Test MESI coherence protocol for PCAM edges."""

    def _make_tracker(self, num_hosts=4):
        config = CXLPoolConfig(num_hosts=num_hosts, max_sharers_per_entry=4)
        return CXLCoherenceTracker(config)

    def test_first_sharer_gets_exclusive(self):
        tracker = self._make_tracker()
        key = (0, 42)

        tracker.add_sharer(key, host_id=0)
        assert tracker.get_state(key) == CoherenceState.EXCLUSIVE
        assert tracker.get_sharer_count(key) == 1

    def test_second_sharer_transitions_to_shared(self):
        tracker = self._make_tracker()
        key = (0, 42)

        tracker.add_sharer(key, host_id=0)
        tracker.add_sharer(key, host_id=1)

        assert tracker.get_state(key) == CoherenceState.SHARED
        assert tracker.get_sharer_count(key) == 2
        assert tracker.get_sharers(key) == {0, 1}

    def test_request_exclusive_invalidates_others(self):
        tracker = self._make_tracker()
        key = (0, 42)

        # Three hosts share the entry
        tracker.add_sharer(key, 0)
        tracker.add_sharer(key, 1)
        tracker.add_sharer(key, 2)
        assert tracker.get_state(key) == CoherenceState.SHARED

        # Host 0 requests exclusive (write)
        num_inv, latency = tracker.request_exclusive(key, host_id=0)

        assert num_inv == 2  # Hosts 1 and 2 invalidated
        assert latency > 0   # Invalidation has latency cost
        assert tracker.get_state(key) == CoherenceState.MODIFIED
        assert tracker.get_sharers(key) == {0}  # Only host 0 remains
        assert tracker.invalidations_sent == 2

    def test_exclusive_to_modified_no_invalidation(self):
        tracker = self._make_tracker()
        key = (0, 42)

        tracker.add_sharer(key, host_id=0)
        assert tracker.get_state(key) == CoherenceState.EXCLUSIVE

        # Request exclusive when already exclusive — should still work
        num_inv, latency = tracker.request_exclusive(key, host_id=0)
        assert num_inv == 0
        assert latency == 0
        assert tracker.get_state(key) == CoherenceState.MODIFIED

    def test_sharer_limit_enforced(self):
        config = CXLPoolConfig(num_hosts=8, max_sharers_per_entry=3)
        tracker = CXLCoherenceTracker(config)
        key = (0, 42)

        for host in range(6):
            tracker.add_sharer(key, host)

        # Should be capped at 3
        assert tracker.get_sharer_count(key) == 3

    def test_remove_sharer_cleans_state(self):
        tracker = self._make_tracker()
        key = (0, 42)

        tracker.add_sharer(key, 0)
        tracker.add_sharer(key, 1)
        tracker.remove_sharer(key, 0)
        tracker.remove_sharer(key, 1)

        # State should be cleaned up when all sharers removed
        assert tracker.get_state(key) == CoherenceState.INVALID
        assert tracker.get_sharer_count(key) == 0

    def test_on_eviction_removes_sharer(self):
        tracker = self._make_tracker()
        key = (0, 42)

        tracker.add_sharer(key, 0)
        tracker.add_sharer(key, 1)
        tracker.on_eviction(key, 0)

        assert 0 not in tracker.get_sharers(key)
        assert tracker.get_sharer_count(key) == 1

    def test_eviction_penalty_scales_with_sharers(self):
        tracker = self._make_tracker()
        key = (0, 42)

        # No sharers — no penalty
        assert tracker.get_eviction_penalty(key) == 0.0

        tracker.add_sharer(key, 0)
        assert tracker.get_eviction_penalty(key) == 0.0  # 1 sharer, no penalty

        tracker.add_sharer(key, 1)
        penalty_2 = tracker.get_eviction_penalty(key)
        assert penalty_2 > 0  # 2 sharers

        tracker.add_sharer(key, 2)
        penalty_3 = tracker.get_eviction_penalty(key)
        assert penalty_3 > penalty_2  # More sharers = higher penalty

    def test_invalidation_cost_batching(self):
        config = CXLPoolConfig(
            invalidation_batch_size=2,
            invalidation_latency_ns=100.0,
        )
        tracker = CXLCoherenceTracker(config)

        # 3 invalidations in batches of 2 = 2 batches = 200ns
        cost = tracker.compute_invalidation_cost_ns(3)
        assert cost == 200.0

        # 1 invalidation = 1 batch = 100ns
        assert tracker.compute_invalidation_cost_ns(1) == 100.0

        # 0 invalidations = 0 cost
        assert tracker.compute_invalidation_cost_ns(0) == 0.0

    def test_get_stats(self):
        tracker = self._make_tracker()
        key = (0, 42)

        tracker.add_sharer(key, 0)
        tracker.add_sharer(key, 1)
        tracker.request_exclusive(key, 0)

        stats = tracker.get_stats()
        assert stats["sharers_added"] == 2
        assert stats["exclusive_grants"] == 1
        assert stats["invalidations_sent"] == 1
        assert "state_distribution" in stats


# ---------------------------------------------------------------------------
# CXL Capacity Manager Tests
# ---------------------------------------------------------------------------

class TestCXLCapacityManager:
    """Test dynamic pool expansion and contraction."""

    def _make_manager(self, pool_capacity=100, num_hosts=2):
        config = CXLPoolConfig(
            pool_capacity_multiplier=1.0,
            num_hosts=num_hosts,
            per_host_max_share=0.95,  # High quota for capacity tests
            expansion_threshold=0.85,
            contraction_threshold=0.30,
            rebalance_interval=10,
            capacity_step=20,
        )
        pool = CXLEdgePool(config, bram_capacity=pool_capacity)
        manager = CXLCapacityManager(config, pool)
        return manager, pool

    def test_expansion_on_high_utilization(self):
        manager, pool = self._make_manager(pool_capacity=100)

        # Fill pool to 90% (above 85% threshold)
        for i in range(90):
            entry = _make_entry(i, score=1.0)
            pool.admit(entry, host_id=0)

        assert pool.size == 90

        # Trigger rebalance
        for _ in range(10):
            manager.record_demand(0)

        assert manager.should_rebalance()
        result = manager.rebalance()

        assert result["action"] == "expand"
        assert manager.current_capacity == 120  # 100 + 20 step
        assert manager.expansions == 1

    def test_contraction_on_low_utilization(self):
        manager, pool = self._make_manager(pool_capacity=100)

        # Fill pool to only 10% (below 30% threshold)
        for i in range(10):
            entry = _make_entry(i, score=1.0)
            pool.admit(entry)

        # Trigger rebalance
        for _ in range(10):
            manager.record_demand(0)

        result = manager.rebalance()
        assert result["action"] == "contract"
        assert manager.current_capacity == 80  # 100 - 20 step
        assert manager.contractions == 1

    def test_contraction_respects_current_usage(self):
        manager, pool = self._make_manager(pool_capacity=100)

        # Fill pool to 25 entries, then try to contract by 20
        # Should not shrink below 26 (current usage + 1)
        for i in range(25):
            entry = _make_entry(i, score=1.0)
            pool.admit(entry)

        for _ in range(10):
            manager.record_demand(0)

        result = manager.rebalance()
        assert result["action"] == "contract"
        assert manager.current_capacity >= pool.size + 1

    def test_no_action_on_moderate_utilization(self):
        manager, pool = self._make_manager(pool_capacity=100)

        # Fill to 50% (between 30% and 85%)
        for i in range(50):
            entry = _make_entry(i, score=1.0)
            pool.admit(entry)

        for _ in range(10):
            manager.record_demand(0)

        result = manager.rebalance()
        assert result["action"] == "none"

    def test_host_demand_tracking(self):
        manager, pool = self._make_manager(num_hosts=2)

        # Host 0 makes 7 requests, host 1 makes 3
        for _ in range(7):
            manager.record_demand(0)
        for _ in range(3):
            manager.record_demand(1)

        assert manager.get_host_demand_share(0) == 0.7
        assert manager.get_host_demand_share(1) == 0.3

    def test_rebalance_interval(self):
        manager, _ = self._make_manager()

        # Not enough accesses yet
        for _ in range(5):
            manager.record_demand(0)
        assert not manager.should_rebalance()

        # Enough accesses
        for _ in range(5):
            manager.record_demand(0)
        assert manager.should_rebalance()

    def test_get_stats(self):
        manager, pool = self._make_manager()
        stats = manager.get_stats()
        assert "current_capacity" in stats
        assert "expansions" in stats
        assert "host_demand" in stats


# ---------------------------------------------------------------------------
# Edge Discovery Service Tests
# ---------------------------------------------------------------------------

class TestEdgeDiscoveryService:
    """Test cross-host edge discovery."""

    def _make_discovery(self):
        config = CXLPoolConfig(
            num_hosts=4,
            discovery_enabled=True,
            discovery_min_score=0.05,
            discovery_boost=0.15,
        )
        pool = CXLEdgePool(config, bram_capacity=100)
        discovery = EdgeDiscoveryService(config)
        return discovery, pool, config

    def test_discovers_other_hosts_edges(self):
        discovery, pool, _ = self._make_discovery()

        # GPU 0 puts edges in pool
        for i in range(10):
            entry = _make_entry(i, score=0.5, owner=0)
            pool.admit(entry, host_id=0)

        # GPU 1 discovers them
        found = discovery.discover_cross_host_edges(
            pool=pool, sequence_id=0, requesting_host=1, k=5, current_step=100,
        )

        assert len(found) == 5
        assert discovery.discoveries == 5

    def test_skips_own_entries(self):
        discovery, pool, _ = self._make_discovery()

        # GPU 0 puts edges in pool
        for i in range(5):
            entry = _make_entry(i, score=0.5, owner=0)
            pool.admit(entry, host_id=0)

        # GPU 0 should not discover its own entries
        found = discovery.discover_cross_host_edges(
            pool=pool, sequence_id=0, requesting_host=0, k=10, current_step=100,
        )
        assert len(found) == 0

    def test_skips_low_score_entries(self):
        discovery, pool, _ = self._make_discovery()

        # Entries below min_score (0.05)
        for i in range(5):
            entry = _make_entry(i, score=0.01, owner=0)
            pool.admit(entry, host_id=0)

        found = discovery.discover_cross_host_edges(
            pool=pool, sequence_id=0, requesting_host=1, k=10, current_step=100,
        )
        assert len(found) == 0

    def test_cross_host_validation_boost(self):
        discovery, pool, _ = self._make_discovery()

        # Entry shared by 3 hosts (well-validated)
        entry = _make_entry(42, score=1.0, owner=0)
        entry.sharer_hosts = {0, 1, 2}
        pool.admit(entry, host_id=0)

        found = discovery.discover_cross_host_edges(
            pool=pool, sequence_id=0, requesting_host=3, k=1, current_step=100,
        )

        assert len(found) == 1
        block_id, boosted_score = found[0]
        assert block_id == 42
        # Score should be boosted by validation: 1.0 * (1 + 0.15 * 3) = 1.45
        assert boosted_score > 1.0

    def test_discovery_cooldown(self):
        discovery, pool, _ = self._make_discovery()

        entry = _make_entry(42, score=0.5, owner=0)
        pool.admit(entry, host_id=0)

        # First discovery
        found1 = discovery.discover_cross_host_edges(
            pool=pool, sequence_id=0, requesting_host=1, k=5, current_step=100,
        )
        assert len(found1) == 1

        # Immediate re-discovery should be suppressed (cooldown)
        found2 = discovery.discover_cross_host_edges(
            pool=pool, sequence_id=0, requesting_host=1, k=5, current_step=110,
        )
        assert len(found2) == 0

        # After cooldown (50 steps), should discover again
        found3 = discovery.discover_cross_host_edges(
            pool=pool, sequence_id=0, requesting_host=1, k=5, current_step=160,
        )
        assert len(found3) == 1

    def test_disabled_discovery(self):
        config = CXLPoolConfig(discovery_enabled=False)
        pool = CXLEdgePool(config, bram_capacity=100)
        discovery = EdgeDiscoveryService(config)

        entry = _make_entry(42, score=0.5, owner=0)
        pool.admit(entry, host_id=0)

        found = discovery.discover_cross_host_edges(
            pool=pool, sequence_id=0, requesting_host=1, k=5, current_step=100,
        )
        assert len(found) == 0

    def test_get_stats(self):
        discovery, pool, _ = self._make_discovery()
        entry = _make_entry(42, score=0.5, owner=0)
        pool.admit(entry, host_id=0)

        discovery.discover_cross_host_edges(
            pool=pool, sequence_id=0, requesting_host=1, k=5, current_step=100,
        )

        stats = discovery.get_stats()
        assert stats["discoveries"] == 1
        assert "discovery_hit_rate" in stats


# ---------------------------------------------------------------------------
# Per-Host Quota Tests
# ---------------------------------------------------------------------------

class TestPerHostQuota:
    """Test per-host quota enforcement in CXLEdgePool."""

    def test_max_share_enforcement(self):
        config = CXLPoolConfig(
            pool_capacity_multiplier=0.1,  # 10 entries
            num_hosts=2,
            per_host_max_share=0.6,  # Max 60% per host
        )
        pool = CXLEdgePool(config, bram_capacity=100)

        # Host 0 fills up to 60% quota (6 entries)
        for i in range(10):
            entry = _make_entry(i, score=1.0)
            pool.admit(entry, host_id=0)

        # Host 0 should be at or near quota
        host0_entries = pool.get_host_usage(0)
        assert host0_entries <= 6  # 60% of 10

    def test_can_admit_respects_quota(self):
        config = CXLPoolConfig(
            pool_capacity_multiplier=0.1,
            num_hosts=2,
            per_host_max_share=0.5,
        )
        pool = CXLEdgePool(config, bram_capacity=100)

        # Fill 5 entries for host 0 (50% of 10)
        for i in range(5):
            entry = _make_entry(i, score=1.0)
            pool.admit(entry, host_id=0)

        # Host 0 should be at quota
        assert not pool.can_admit(0)

        # Host 1 should still have room
        assert pool.can_admit(1)

    def test_single_gpu_no_quota_restriction(self):
        """Single GPU mode should not enforce per-host quota."""
        config = CXLPoolConfig(
            pool_capacity_multiplier=0.1,
            num_hosts=1,
            per_host_max_share=0.8,
        )
        pool = CXLEdgePool(config, bram_capacity=100)

        # Should be able to fill entire pool
        for i in range(10):
            entry = _make_entry(i, score=1.0)
            assert pool.admit(entry, host_id=0)

        assert pool.size == 10

    def test_host_share_calculation(self):
        config = CXLPoolConfig(
            pool_capacity_multiplier=0.1,
            num_hosts=2,
            per_host_max_share=0.8,
        )
        pool = CXLEdgePool(config, bram_capacity=100)

        for i in range(3):
            pool.admit(_make_entry(i, score=1.0), host_id=0)
        for i in range(3, 5):
            pool.admit(_make_entry(i, score=1.0), host_id=1)

        assert pool.get_host_share(0) == 0.3  # 3/10
        assert pool.get_host_share(1) == 0.2  # 2/10


# ---------------------------------------------------------------------------
# MultiGPU Coordinator End-to-End Tests
# ---------------------------------------------------------------------------

class TestMultiGPUPCAMCoordinator:
    """End-to-end tests for the multi-GPU coordinator."""

    def _make_coordinator(self, num_gpus=2, bram_cap=100):
        config = TieredPCAMConfig.multi_gpu(num_gpus=num_gpus)
        config.base.max_entries = bram_cap
        config.cxl.per_host_max_share = 0.8
        config.policy.demotion_min_idle_steps = 5
        return MultiGPUPCAMCoordinator(config)

    def test_create_multi_gpu(self):
        coord = self._make_coordinator(num_gpus=4)
        assert coord.num_hosts == 4
        for i in range(4):
            gpu = coord.get_gpu(i)
            assert gpu is not None
            assert gpu.host_id == i

    def test_invalid_gpu_id_raises(self):
        coord = self._make_coordinator(num_gpus=2)
        with pytest.raises(ValueError):
            coord.get_gpu(5)

    def test_shared_pool_reference(self):
        coord = self._make_coordinator(num_gpus=2)
        gpu0 = coord.get_gpu(0)
        gpu1 = coord.get_gpu(1)

        # Both GPUs share the same CXL pool
        assert gpu0.cxl_pool is gpu1.cxl_pool
        assert gpu0.cxl_pool is coord.shared_pool

    def test_gpu0_edges_visible_to_gpu1(self):
        coord = self._make_coordinator(num_gpus=2)
        coord.allocate_sequence(0, 4096)

        # GPU 0 learns attention patterns
        gpu0 = coord.get_gpu(0)
        for i in range(20):
            gpu0.update(query_block_id=100, key_block_id=i, weight=0.5)
            gpu0.step()

        # Demote some edges to CXL
        tiered0 = gpu0._tiered_sequences.get(0)
        if tiered0:
            # Manually add some entries to CXL from GPU 0
            for i in range(5):
                entry = _make_entry(i + 1000, score=2.0, owner=0)
                entry.last_access_step = gpu0._step - 10
                coord.shared_pool.admit(entry, host_id=0)

        # GPU 1 should discover GPU 0's CXL edges
        discovered = coord.discovery.discover_cross_host_edges(
            pool=coord.shared_pool,
            sequence_id=0,
            requesting_host=1,
            k=10,
            current_step=gpu0._step,
        )
        assert len(discovered) > 0

    def test_attend_with_discovery(self):
        coord = self._make_coordinator(num_gpus=2)
        coord.allocate_sequence(0, 4096)

        gpu0 = coord.get_gpu(0)
        gpu1 = coord.get_gpu(1)

        # GPU 0 puts high-score entries in CXL
        for i in range(500, 510):
            entry = _make_entry(i, score=3.0, owner=0)
            entry.last_access_step = 50
            coord.shared_pool.admit(entry, host_id=0)

        # GPU 1 also updates some local edges
        for i in range(10):
            gpu1.update(query_block_id=100, key_block_id=i, weight=0.5)
            gpu1.step()

        # GPU 1 ATTEND with discovery should find GPU 0's edges
        candidates, latency, conflicts = coord.attend_with_discovery(
            host_id=1, query_block_id=100, k=64, sequence_id=0,
        )

        candidate_ids = {bid for bid, _ in candidates}
        # At least some of GPU 0's CXL entries should be discovered
        discovered_from_gpu0 = candidate_ids & set(range(500, 510))
        assert len(discovered_from_gpu0) > 0

    def test_update_with_coherence_invalidation(self):
        coord = self._make_coordinator(num_gpus=2)
        coord.allocate_sequence(0, 4096)

        # Put a shared entry in CXL (owned by GPU 0, shared by GPU 1)
        entry = _make_entry(42, score=1.0, owner=0)
        coord.shared_pool.admit(entry, host_id=0)
        coord.coherence.add_sharer((0, 42), host_id=0)
        coord.coherence.add_sharer((0, 42), host_id=1)

        assert coord.coherence.get_state((0, 42)) == CoherenceState.SHARED

        # GPU 1 updates the shared entry — should trigger invalidation
        success, latency = coord.update_with_coherence(
            host_id=1, query_block_id=100, key_block_id=42,
            weight=2.0, sequence_id=0,
        )
        assert success

        # Coherence should show invalidation
        assert coord.coherence.invalidations_sent >= 1
        assert coord.coherence.get_state((0, 42)) == CoherenceState.MODIFIED

    def test_capacity_rebalance_during_attend(self):
        config = TieredPCAMConfig.multi_gpu(num_gpus=2)
        config.base.max_entries = 50
        config.cxl.rebalance_interval = 5  # Very frequent rebalancing
        config.cxl.capacity_step = 10
        coord = MultiGPUPCAMCoordinator(config)
        coord.allocate_sequence(0, 4096)

        gpu0 = coord.get_gpu(0)
        for i in range(10):
            gpu0.update(query_block_id=50, key_block_id=i, weight=0.5)
            gpu0.step()

        # Trigger enough attend_with_discovery calls to trigger rebalance
        for _ in range(10):
            coord.attend_with_discovery(
                host_id=0, query_block_id=50, k=16, sequence_id=0,
            )

        assert coord.capacity_manager.rebalances >= 1

    def test_free_sequence_all_gpus(self):
        coord = self._make_coordinator(num_gpus=2)
        coord.allocate_sequence(0, 4096)

        # Add some data
        gpu0 = coord.get_gpu(0)
        gpu0.update(query_block_id=10, key_block_id=5, weight=1.0)

        # Add CXL entries
        entry = _make_entry(42, score=1.0, owner=0)
        coord.shared_pool.admit(entry, host_id=0)

        # Free should clean up everything
        coord.free_sequence(0)
        assert coord.shared_pool.size == 0

    def test_step_all_advances_all_gpus(self):
        coord = self._make_coordinator(num_gpus=3)

        coord.step_all()
        coord.step_all()

        for i in range(3):
            assert coord.get_gpu(i)._step == 2

    def test_per_host_quota_in_coordinator(self):
        coord = self._make_coordinator(num_gpus=2)
        coord.allocate_sequence(0, 4096)

        quota = coord.get_per_host_quota(0)
        assert quota["host_id"] == 0
        assert "pool_share" in quota
        assert "min_share" in quota
        assert "max_share" in quota
        assert "demand_share" in quota

    def test_comprehensive_stats(self):
        coord = self._make_coordinator(num_gpus=2)
        coord.allocate_sequence(0, 4096)

        gpu0 = coord.get_gpu(0)
        gpu0.update(query_block_id=10, key_block_id=5, weight=1.0)
        gpu0.step()

        stats = coord.get_stats()
        assert stats["num_hosts"] == 2
        assert "shared_pool" in stats
        assert "coherence" in stats
        assert "capacity" in stats
        assert "discovery" in stats
        assert "per_gpu" in stats
        assert 0 in stats["per_gpu"]
        assert 1 in stats["per_gpu"]


# ---------------------------------------------------------------------------
# Cross-Host Edge Sharing Scenario Tests
# ---------------------------------------------------------------------------

class TestCrossHostScenarios:
    """Realistic multi-GPU scenarios."""

    def test_tensor_parallel_pattern_sharing(self):
        """Two GPUs processing different layers share attention patterns.

        GPU 0 processes layers 0-15, GPU 1 processes layers 16-31.
        Both observe the same sequence. Attention patterns from layer 0-15
        are useful for layer 16-31 (similar query structure).
        """
        coord = MultiGPUPCAMCoordinator(
            TieredPCAMConfig.multi_gpu(num_gpus=2),
        )
        coord.allocate_sequence(0, 4096)

        gpu0 = coord.get_gpu(0)
        gpu1 = coord.get_gpu(1)

        # GPU 0 learns strong attention to blocks 50-55 (important anchors)
        for step in range(50):
            for anchor in range(50, 56):
                gpu0.update(
                    query_block_id=step, key_block_id=anchor,
                    weight=0.5, sequence_id=0,
                )
            gpu0.step()

        # GPU 0 demotes some edges to CXL
        for anchor in range(50, 56):
            entry = _make_entry(anchor, score=2.5, owner=0)
            entry.last_access_step = 30
            entry.cxl_access_count = 5
            coord.shared_pool.admit(entry, host_id=0)

        # GPU 1 has NOT seen these patterns yet
        # But ATTEND with discovery should find GPU 0's anchors
        candidates, _, _ = coord.attend_with_discovery(
            host_id=1, query_block_id=40, k=64, sequence_id=0,
        )

        candidate_ids = {bid for bid, _ in candidates}
        shared_anchors = candidate_ids & set(range(50, 56))

        # GPU 1 should discover at least some of GPU 0's anchor patterns
        assert len(shared_anchors) > 0, (
            "Tensor parallel GPUs should share attention pattern anchors"
        )

    def test_data_parallel_workload_diversity(self):
        """Four GPUs processing different requests share common patterns.

        Common attention sinks (positions 0-3) should be validated by
        all GPUs, making them high-confidence candidates for everyone.
        """
        coord = MultiGPUPCAMCoordinator(
            TieredPCAMConfig.multi_gpu(num_gpus=4),
        )
        coord.allocate_sequence(0, 4096)

        # All GPUs attend to sinks (blocks 0-3) — universal pattern
        for gpu_id in range(4):
            gpu = coord.get_gpu(gpu_id)
            for step in range(20):
                for sink in range(4):
                    gpu.update(
                        query_block_id=step + gpu_id * 100,
                        key_block_id=sink,
                        weight=0.8,
                        sequence_id=0,
                    )
                gpu.step()

        # Put sink entries in CXL from GPU 0
        for sink in range(4):
            entry = _make_entry(sink, score=3.0, owner=0)
            entry.sharer_hosts = {0, 1, 2, 3}  # All GPUs validate
            coord.shared_pool.admit(entry, host_id=0)
            for gpu_id in range(4):
                coord.coherence.add_sharer((0, sink), gpu_id)

        # Discovery from any GPU should give high scores to sinks
        found = coord.discovery.discover_cross_host_edges(
            pool=coord.shared_pool,
            sequence_id=0,
            requesting_host=3,  # GPU 3 discovers
            k=10,
            current_step=100,
        )

        # Sinks validated by 4 GPUs should have higher boosted scores
        if found:
            # All found entries should have validation boost
            for _, score in found:
                assert score > 3.0, "Cross-host validated entries should be boosted"
