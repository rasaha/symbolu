"""
Tests for Tiered PCAM with TurboQuant compression and CXL shared pool.

Validates:
  1. TieredPCAMConfig capacity calculations
  2. CompressedBlockEntry score quantization round-trip
  3. CXLEdgePool admission, lookup, eviction, cross-host sharing
  4. TieredSequenceState demotion/promotion lifecycle
  5. TieredPCAMInterface end-to-end ATTEND/UPDATE with tier management
  6. Multi-GPU shared edge pool coherence
"""

import pytest
from simulator.pcam.core.tiered_config import (
    TieredPCAMConfig,
    TierType,
    CXLPoolConfig,
    TurboQuantEdgeConfig,
    TierPolicy,
)
from simulator.pcam.tiered_pcam import (
    CompressedBlockEntry,
    compress_block_score,
    CXLEdgePool,
    TieredSequenceState,
    TieredPCAMInterface,
)
from simulator.pcam.core.state import BlockScore, SequenceState


# ---------------------------------------------------------------------------
# Configuration Tests
# ---------------------------------------------------------------------------

class TestTieredPCAMConfig:
    """Test configuration and capacity calculations."""

    def test_default_capacities(self):
        config = TieredPCAMConfig()
        assert config.bram_capacity == 1_000_000
        # CXL raw = 1M * 1.5 = 1.5M, effective = 1.5M * 4.0 = 6M
        assert config.cxl_raw_capacity == 1_500_000
        assert config.cxl_effective_capacity == 6_000_000
        assert config.total_effective_capacity == 7_000_000

    def test_single_gpu_preset(self):
        config = TieredPCAMConfig.single_gpu()
        assert config.cxl.num_hosts == 1
        assert config.cxl.enabled

    def test_multi_gpu_preset(self):
        config = TieredPCAMConfig.multi_gpu(num_gpus=4)
        assert config.cxl.num_hosts == 4
        assert config.cxl.pool_capacity_multiplier == 2.0

    def test_long_context_preset(self):
        config = TieredPCAMConfig.long_context()
        assert config.tq.compression_ratio == 5.3
        assert config.tq.store_edges_in_cxl
        assert config.cxl.pool_capacity_multiplier == 3.0

    def test_summary_output(self):
        config = TieredPCAMConfig()
        summary = config.summary()
        assert "BRAM tier" in summary
        assert "CXL tier" in summary
        assert "7,000,000" in summary


# ---------------------------------------------------------------------------
# Compressed Entry Tests
# ---------------------------------------------------------------------------

class TestCompressedBlockEntry:
    """Test Q4.4 score quantization and decompression."""

    def test_score_round_trip(self):
        entry = CompressedBlockEntry(block_id=42, sequence_id=0)
        entry.score = 1.5
        # Q4.4: 1.5 * 16 = 24, 24 / 16 = 1.5 (exact)
        assert entry.score == 1.5

    def test_score_quantization_loss(self):
        entry = CompressedBlockEntry(block_id=42, sequence_id=0)
        entry.score = 0.123
        # Q4.4: 0.123 * 16 = 1.968 → 1, 1 / 16 = 0.0625
        # Small quantization error is expected
        assert abs(entry.score - 0.123) < 0.1

    def test_score_clamping(self):
        entry = CompressedBlockEntry(block_id=42, sequence_id=0)
        entry.score = -1.0
        assert entry.quantized_score == 0  # Clamped to 0
        entry.score = 20.0
        assert entry.quantized_score == 255  # Clamped to max

    def test_to_block_score(self):
        entry = CompressedBlockEntry(
            block_id=42,
            sequence_id=0,
            access_count=10,
            last_access_step=100,
            cumulative_weight=5.0,
        )
        entry.score = 2.0

        bs = entry.to_block_score()
        assert bs.block_id == 42
        assert bs.score == 2.0
        assert bs.access_count == 10
        assert bs.last_access_step == 100
        assert bs.cumulative_weight == 5.0

    def test_compress_block_score(self):
        bs = BlockScore(
            block_id=42,
            score=1.5,
            access_count=20,
            last_access_step=200,
            cumulative_weight=10.0,
        )
        bs.unique_query_sources = {1, 2, 3, 4, 5}

        config = TurboQuantEdgeConfig()
        entry = compress_block_score(bs, sequence_id=0, edges={}, config=config)

        assert entry.block_id == 42
        assert entry.access_count == 20
        assert entry.query_source_count == 5
        assert abs(entry.score - 1.5) < 0.1

    def test_compress_with_edges(self):
        bs = BlockScore(block_id=10, score=1.0, access_count=5)
        edges = {
            (10, 20): 0.5,
            (10, 30): 0.3,
            (10, 40): 0.8,
            (5, 10): 0.2,  # Reverse edge
        }
        config = TurboQuantEdgeConfig(store_edges_in_cxl=True, max_edges_per_block_cxl=2)
        entry = compress_block_score(bs, 0, edges, config)

        # Should keep top-2 edges by weight
        assert len(entry.compressed_edges) == 2


# ---------------------------------------------------------------------------
# CXL Edge Pool Tests
# ---------------------------------------------------------------------------

class TestCXLEdgePool:
    """Test the CXL shared memory pool for PCAM edges."""

    def _make_pool(self, capacity_mult=1.5, num_hosts=1):
        config = CXLPoolConfig(
            pool_capacity_multiplier=capacity_mult,
            num_hosts=num_hosts,
        )
        return CXLEdgePool(config, bram_capacity=100)  # Small for testing

    def _make_entry(self, block_id, score=1.0, seq_id=0):
        entry = CompressedBlockEntry(block_id=block_id, sequence_id=seq_id)
        entry.score = score
        return entry

    def test_admit_and_lookup(self):
        pool = self._make_pool()
        entry = self._make_entry(42, score=1.5)

        assert pool.admit(entry, host_id=0)
        assert pool.size == 1

        found = pool.lookup(0, 42, accessor_host=0)
        assert found is not None
        assert found.block_id == 42
        assert found.cxl_access_count == 1

    def test_lookup_miss(self):
        pool = self._make_pool()
        found = pool.lookup(0, 999, accessor_host=0)
        assert found is None
        assert pool.stats["misses"] == 1

    def test_capacity_eviction(self):
        config = CXLPoolConfig(pool_capacity_multiplier=0.05)
        pool = CXLEdgePool(config, bram_capacity=100)  # capacity = 5

        # Fill pool
        for i in range(5):
            entry = self._make_entry(i, score=float(i + 1))
            assert pool.admit(entry)

        assert pool.size == 5

        # Admit one more — should evict lowest score (block 0)
        entry = self._make_entry(99, score=10.0)
        assert pool.admit(entry)
        assert pool.size == 5
        assert pool.stats["evictions"] == 1

        # Block 0 (lowest score) should have been evicted
        assert pool.lookup(0, 0) is None

    def test_remove_for_promotion(self):
        pool = self._make_pool()
        entry = self._make_entry(42, score=1.5)
        pool.admit(entry, host_id=0)

        removed = pool.remove(0, 42)
        assert removed is not None
        assert removed.block_id == 42
        assert pool.size == 0
        assert pool.stats["promotions"] == 1

    def test_cross_host_sharing(self):
        pool = self._make_pool(num_hosts=4)
        entry = self._make_entry(42, score=1.5)
        pool.admit(entry, host_id=0)

        # Host 1 accesses the entry
        found = pool.lookup(0, 42, accessor_host=1)
        assert found is not None
        assert pool.stats["cross_host_hits"] == 1
        assert 1 in found.sharer_hosts

        # Host 2 also accesses
        pool.lookup(0, 42, accessor_host=2)
        assert pool.stats["cross_host_hits"] == 2

    def test_sharer_limit(self):
        pool = self._make_pool(num_hosts=8)
        pool.config.max_sharers_per_entry = 3
        entry = self._make_entry(42, score=1.5)
        pool.admit(entry, host_id=0)

        # Access from 5 different hosts
        for host in range(1, 6):
            pool.lookup(0, 42, accessor_host=host)

        # Sharers should be capped at 3 (owner + 2 more)
        found = pool.lookup(0, 42, accessor_host=0)
        assert len(found.sharer_hosts) <= 3

    def test_eviction_penalizes_shared(self):
        """Shared entries should be harder to evict."""
        config = CXLPoolConfig(pool_capacity_multiplier=0.03, num_hosts=4)
        pool = CXLEdgePool(config, bram_capacity=100)  # capacity = 3

        # Entry A: low score, shared by 3 hosts
        a = self._make_entry(1, score=0.5)
        pool.admit(a, host_id=0)
        pool.lookup(0, 1, accessor_host=1)
        pool.lookup(0, 1, accessor_host=2)

        # Entry B: slightly higher score, not shared
        b = self._make_entry(2, score=0.6)
        pool.admit(b, host_id=0)

        # Entry C: lowest score, not shared
        c = self._make_entry(3, score=0.4)
        pool.admit(c, host_id=0)

        # Admit one more — should evict C (lowest effective score)
        d = self._make_entry(4, score=2.0)
        pool.admit(d, host_id=0)

        # C should be evicted (lowest score, no sharing penalty protection)
        assert pool.lookup(0, 3) is None
        # A should survive (shared, penalty makes it harder to evict)
        assert pool.lookup(0, 1) is not None

    def test_get_stats(self):
        pool = self._make_pool()
        entry = self._make_entry(42, score=1.5)
        pool.admit(entry)
        pool.lookup(0, 42)

        stats = pool.get_stats()
        assert stats["size"] == 1
        assert stats["admissions"] == 1
        assert stats["hits"] == 1


# ---------------------------------------------------------------------------
# Tiered Sequence State Tests
# ---------------------------------------------------------------------------

class TestTieredSequenceState:
    """Test demotion/promotion lifecycle."""

    def _make_tiered_state(self, bram_cap=50):
        config = TieredPCAMConfig()
        config.base.max_entries = bram_cap
        config.policy.demotion_min_idle_steps = 5
        config.policy.demotion_score_percentile = 0.5

        seq = SequenceState(sequence_id=0, max_blocks=4096)
        pool = CXLEdgePool(config.cxl, bram_capacity=bram_cap)
        tiered = TieredSequenceState(seq, 0, config, pool, host_id=0)
        return tiered, seq, pool

    def test_demotion_moves_cold_blocks(self):
        tiered, seq, pool = self._make_tiered_state(bram_cap=50)

        # Add blocks with varying scores and access steps
        for i in range(60):
            seq.block_scores[i] = BlockScore(
                block_id=i,
                score=float(i) * 0.1,
                last_access_step=0,  # All idle since step 0
                access_count=i,
            )

        # Demote at step 100 (all blocks idle for 100 steps > min_idle 5)
        demoted = tiered.demote_cold_blocks(current_step=100, count=20)
        assert demoted > 0

        # Demoted blocks should be in CXL pool
        assert pool.size > 0

        # Low-score blocks should have been demoted first
        for i in range(demoted):
            assert tiered.get_tier(i) in (TierType.CXL_POOL, TierType.EVICTED)

    def test_promotion_on_access(self):
        tiered, seq, pool = self._make_tiered_state(bram_cap=100)

        # Manually put a block in CXL
        entry = CompressedBlockEntry(block_id=42, sequence_id=0, access_count=5)
        entry.score = 1.0
        entry.cxl_access_count = 2  # Already accessed twice
        pool.admit(entry, host_id=0)
        tiered._block_tier[42] = TierType.CXL_POOL

        # Promote it
        bs = tiered.try_promote(42, current_step=200)
        assert bs is not None
        assert bs.block_id == 42
        assert 42 in seq.block_scores
        assert tiered.get_tier(42) == TierType.BRAM

    def test_promotion_requires_min_access(self):
        tiered, seq, pool = self._make_tiered_state()

        entry = CompressedBlockEntry(block_id=42, sequence_id=0)
        entry.score = 1.0
        entry.cxl_access_count = 0  # Not accessed yet
        pool.admit(entry, host_id=0)
        tiered._block_tier[42] = TierType.CXL_POOL

        # Should NOT promote (access count < min)
        bs = tiered.try_promote(42, current_step=200)
        assert bs is None

    def test_skip_protected_blocks_on_demotion(self):
        tiered, seq, pool = self._make_tiered_state(bram_cap=10)

        for i in range(15):
            seq.block_scores[i] = BlockScore(
                block_id=i, score=0.01, last_access_step=0, access_count=1,
            )

        # Protect block 0 (sink)
        seq.protected_blocks.add(0)

        demoted = tiered.demote_cold_blocks(current_step=100, count=10)
        # Block 0 should still be in BRAM
        assert 0 in seq.block_scores

    def test_get_cxl_candidates(self):
        tiered, seq, pool = self._make_tiered_state()

        # Put entries in CXL
        for i in range(10):
            entry = CompressedBlockEntry(block_id=i, sequence_id=0)
            entry.score = float(10 - i) * 0.5
            entry.last_access_step = 50
            pool.admit(entry, host_id=0)

        candidates = tiered.get_cxl_candidates(
            query_block_id=100, k=5, current_step=100,
        )
        assert len(candidates) == 5
        # Should be sorted by score descending
        scores = [s for _, s in candidates]
        assert scores == sorted(scores, reverse=True)

    def test_stats(self):
        tiered, seq, pool = self._make_tiered_state(bram_cap=20)

        for i in range(25):
            seq.block_scores[i] = BlockScore(
                block_id=i, score=float(i) * 0.1,
                last_access_step=0, access_count=1,
            )

        tiered.demote_cold_blocks(current_step=100, count=10)
        stats = tiered.get_stats()

        assert stats["total_demotions"] > 0
        assert stats["bram_blocks"] < 25


# ---------------------------------------------------------------------------
# Tiered PCAM Interface End-to-End Tests
# ---------------------------------------------------------------------------

class TestTieredPCAMInterface:
    """End-to-end tests for the tiered PCAM interface."""

    def _make_pcam(self, bram_cap=200, cxl_mult=1.5):
        config = TieredPCAMConfig()
        config.base.max_entries = bram_cap
        config.cxl.pool_capacity_multiplier = cxl_mult
        config.policy.demotion_min_idle_steps = 5
        config.policy.demotion_score_percentile = 0.5
        return TieredPCAMInterface(config)

    def test_basic_attend_update(self):
        pcam = self._make_pcam()
        pcam.allocate_sequence(0, 4096)

        # Update some edges
        for i in range(10):
            pcam.update(query_block_id=50, key_block_id=i, weight=0.5, sequence_id=0)
            pcam.step()

        # Attend should return candidates
        candidates, latency, conflicts = pcam.attend(
            query_block_id=50, k=16, sequence_id=0,
        )
        assert len(candidates) > 0
        assert latency > 0

    def test_cxl_augmented_attend(self):
        """Verify ATTEND merges BRAM + CXL candidates."""
        config = TieredPCAMConfig()
        config.base.max_entries = 100
        config.cxl.pool_capacity_multiplier = 1.0
        config.policy.demotion_min_idle_steps = 2

        pcam = TieredPCAMInterface(config)
        pcam.allocate_sequence(0, 4096)

        # Fill BRAM with edges
        for i in range(50):
            pcam.update(query_block_id=100, key_block_id=i, weight=float(i) * 0.1)
            pcam.step()

        # Manually place high-score entries in CXL pool
        for i in range(200, 210):
            entry = CompressedBlockEntry(block_id=i, sequence_id=0)
            entry.score = 5.0  # High score
            entry.last_access_step = pcam._step - 10
            entry.cxl_access_count = 3
            pcam.cxl_pool.admit(entry, host_id=0)

        # Mark them as CXL-tier
        tiered = pcam._tiered_sequences[0]
        for i in range(200, 210):
            tiered._block_tier[i] = TierType.CXL_POOL

        # ATTEND should include CXL candidates
        candidates, latency, _ = pcam.attend(
            query_block_id=100, k=64, sequence_id=0,
        )
        candidate_ids = {bid for bid, _ in candidates}

        # At least some CXL entries should appear in candidates
        cxl_in_result = candidate_ids & set(range(200, 210))
        assert len(cxl_in_result) > 0, "CXL candidates should be merged into ATTEND results"

    def test_update_routes_to_cxl_tier(self):
        """UPDATE should route to CXL for blocks in CXL tier.

        When a CXL-tier block is updated, the update goes to CXL.
        If the block accumulates enough accesses, it auto-promotes to BRAM.
        """
        pcam = self._make_pcam()
        # Raise promotion threshold so the block stays in CXL after one update
        pcam.config.policy.promotion_min_access_count = 5
        pcam.allocate_sequence(0, 4096)

        # Put a block in CXL
        entry = CompressedBlockEntry(block_id=42, sequence_id=0, access_count=1)
        entry.score = 0.5
        entry.cxl_access_count = 0
        pcam.cxl_pool.admit(entry, host_id=0)
        pcam._tiered_sequences[0]._block_tier[42] = TierType.CXL_POOL

        # Update should go to CXL tier (not BRAM)
        success, latency = pcam.update(
            query_block_id=100, key_block_id=42, weight=2.0, sequence_id=0,
        )
        assert success
        assert latency == pcam.config.cxl.access_latency_ns

        # Block should still be in CXL (access_count < promotion threshold 5)
        updated = pcam.cxl_pool.lookup(0, 42)
        assert updated is not None
        assert updated.score > 0.5  # EMA should increase score

    def test_decay_both_tiers(self):
        pcam = self._make_pcam()
        pcam.allocate_sequence(0, 4096)

        # Put edge in BRAM
        pcam.update(query_block_id=10, key_block_id=5, weight=1.0, sequence_id=0)

        # Put edge in CXL
        entry = CompressedBlockEntry(block_id=42, sequence_id=0)
        entry.score = 2.0
        pcam.cxl_pool.admit(entry)

        # Decay
        pcam.decay(rate=0.5)

        # BRAM score should be halved
        scores = pcam.state.get_block_scores(0, [5])
        assert scores[5] < 1.0

        # CXL score should also be decayed
        cxl_entry = pcam.cxl_pool.lookup(0, 42)
        assert cxl_entry.score < 2.0

    def test_free_sequence_cleans_cxl(self):
        pcam = self._make_pcam()
        pcam.allocate_sequence(0, 4096)

        # Add CXL entries
        for i in range(5):
            entry = CompressedBlockEntry(block_id=i, sequence_id=0)
            entry.score = 1.0
            pcam.cxl_pool.admit(entry)

        assert pcam.cxl_pool.size == 5

        pcam.free_sequence(0)
        assert pcam.cxl_pool.size == 0

    def test_get_block_scores_both_tiers(self):
        pcam = self._make_pcam()
        pcam.allocate_sequence(0, 4096)

        # BRAM block
        pcam.update(query_block_id=10, key_block_id=5, weight=1.0, sequence_id=0)

        # CXL block
        entry = CompressedBlockEntry(block_id=42, sequence_id=0)
        entry.score = 2.0
        pcam.cxl_pool.admit(entry)

        scores = pcam.get_block_scores(0, [5, 42, 999])
        assert scores[5] > 0
        assert scores[42] > 0
        assert scores[999] == 0.0

    def test_batch_update(self):
        pcam = self._make_pcam()
        pcam.allocate_sequence(0, 4096)

        count, latency = pcam.update_batch(
            sequence_id=0,
            block_ids=[1, 2, 3, 4, 5],
            weights=[0.5, 0.3, 0.8, 0.2, 0.6],
            query_block_id=100,
        )
        assert count == 5
        assert latency > 0

    def test_get_stats(self):
        pcam = self._make_pcam()
        pcam.allocate_sequence(0, 4096)

        pcam.update(query_block_id=10, key_block_id=5, weight=1.0, sequence_id=0)
        pcam.step()

        stats = pcam.get_stats()
        assert "cxl_pool" in stats
        assert "config_summary" in stats
        assert stats["cxl_pool"]["capacity"] > 0


# ---------------------------------------------------------------------------
# Multi-GPU Shared Pool Tests
# ---------------------------------------------------------------------------

class TestMultiGPUSharing:
    """Test cross-GPU edge sharing via CXL pool."""

    def test_two_gpus_share_edges(self):
        config = TieredPCAMConfig.multi_gpu(num_gpus=2)
        config.base.max_entries = 100

        # Create two PCAM instances sharing the same CXL pool
        shared_pool = CXLEdgePool(config.cxl, bram_capacity=100)

        gpu0 = TieredPCAMInterface(config, host_id=0)
        gpu0.cxl_pool = shared_pool  # Share pool
        gpu0.allocate_sequence(0, 4096)

        gpu1 = TieredPCAMInterface(config, host_id=1)
        gpu1.cxl_pool = shared_pool  # Share pool
        gpu1.allocate_sequence(0, 4096)

        # GPU 0 adds an edge to CXL
        entry = CompressedBlockEntry(block_id=42, sequence_id=0)
        entry.score = 3.0
        shared_pool.admit(entry, host_id=0)

        # GPU 1 can read it
        found = shared_pool.lookup(0, 42, accessor_host=1)
        assert found is not None
        assert found.score == 3.0
        assert shared_pool.stats["cross_host_hits"] == 1

    def test_multi_gpu_eviction_prefers_unshared(self):
        """With limited pool, unshared entries should be evicted first."""
        config = CXLPoolConfig(
            pool_capacity_multiplier=0.03,  # Very small pool
            num_hosts=2,
        )
        pool = CXLEdgePool(config, bram_capacity=100)  # capacity = 3

        # Entry shared by both GPUs
        shared = CompressedBlockEntry(block_id=1, sequence_id=0)
        shared.score = 0.5
        pool.admit(shared, host_id=0)
        pool.lookup(0, 1, accessor_host=1)  # Host 1 also accesses

        # Two unshared entries
        for i in [2, 3]:
            entry = CompressedBlockEntry(block_id=i, sequence_id=0)
            entry.score = 0.4
            pool.admit(entry, host_id=0)

        # Pool is full (3 entries). Admit one more.
        new = CompressedBlockEntry(block_id=99, sequence_id=0)
        new.score = 5.0
        pool.admit(new, host_id=0)

        # Shared entry (block 1) should survive over unshared ones
        assert pool.lookup(0, 1) is not None


# ---------------------------------------------------------------------------
# Integration: Capacity Scaling Test
# ---------------------------------------------------------------------------

class TestCapacityScaling:
    """Verify that tiered PCAM provides promised capacity expansion."""

    def test_6x_capacity_expansion(self):
        config = TieredPCAMConfig()
        # Default: 1M BRAM + 1.5M * 4.0 TQ = 6M CXL effective
        assert config.total_effective_capacity == 7_000_000
        ratio = config.total_effective_capacity / config.bram_capacity
        assert ratio == 7.0, f"Expected 7x capacity, got {ratio}x"

    def test_long_context_16x_capacity(self):
        config = TieredPCAMConfig.long_context()
        # 1M BRAM + 3M * 5.3 TQ = 15.9M CXL effective
        ratio = config.total_effective_capacity / config.bram_capacity
        assert ratio > 15.0, f"Expected >15x capacity for long-context, got {ratio:.1f}x"
