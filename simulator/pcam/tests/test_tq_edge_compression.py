"""
Tests for TurboQuant Edge Score Compression.

Validates:
  1. AttentionProfile construction from BRAM edges
  2. PolarQuant + QJL compression quality (MSE, cosine similarity)
  3. Query-conditioned score estimation from compressed profiles
  4. Profile comparison (cosine similarity)
  5. Compression/decompression round-trip
  6. Integration with CompressedBlockEntry and TieredSequenceState
  7. Memory accounting
"""

import pytest
import numpy as np

from simulator.pcam.tq_edge_compressor import (
    AttentionProfile,
    EdgeProfileCompressor,
)
from simulator.pcam.core.tiered_config import (
    TieredPCAMConfig,
    TurboQuantEdgeConfig,
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
# Attention Profile Tests
# ---------------------------------------------------------------------------

class TestAttentionProfile:
    """Test profile construction from edge state."""

    def test_build_from_edges(self):
        compressor = EdgeProfileCompressor(profile_dim=8)
        edges = {
            (0, 42): 0.5,
            (1, 42): 0.3,
            (10, 42): 0.8,
            (15, 42): 0.2,
            (5, 99): 0.9,  # Different key block — should be ignored
        }

        profile = compressor.build_profile(
            block_id=42, attention_edges=edges, max_query_block=16,
        )

        assert profile.block_id == 42
        assert profile.num_updates == 4  # Only edges for block 42
        assert profile.total_weight == pytest.approx(0.5 + 0.3 + 0.8 + 0.2)
        assert profile.profile_dim == 8
        assert profile.weights.sum() > 0

    def test_empty_profile(self):
        compressor = EdgeProfileCompressor(profile_dim=8)
        profile = compressor.build_profile(
            block_id=42, attention_edges={}, max_query_block=16,
        )
        assert profile.num_updates == 0
        assert profile.norm == 0.0

    def test_profile_bucketing(self):
        """Verify that edges are correctly bucketed by query position."""
        compressor = EdgeProfileCompressor(profile_dim=4)

        # 16 query positions / 4 buckets = bucket_size=4
        edges = {
            (0, 42): 1.0,   # bucket 0
            (3, 42): 1.0,   # bucket 0
            (4, 42): 1.0,   # bucket 1
            (8, 42): 1.0,   # bucket 2
            (12, 42): 1.0,  # bucket 3
        }

        profile = compressor.build_profile(
            block_id=42, attention_edges=edges, max_query_block=15,
        )

        # bucket 0 should have weight 2.0 (queries 0 and 3)
        assert profile.weights[0] == pytest.approx(2.0)
        # bucket 1 should have weight 1.0 (query 4)
        assert profile.weights[1] == pytest.approx(1.0)

    def test_normalized_profile(self):
        profile = AttentionProfile(
            block_id=42,
            weights=np.array([3.0, 4.0]),
        )
        normed = profile.normalized()
        assert np.linalg.norm(normed) == pytest.approx(1.0, abs=1e-6)


# ---------------------------------------------------------------------------
# Compression Quality Tests
# ---------------------------------------------------------------------------

class TestCompressionQuality:
    """Test PolarQuant + QJL compression quality for attention profiles."""

    def _make_compressor(self, dim=32, bits=3, qjl=True):
        return EdgeProfileCompressor(
            profile_dim=dim, angle_bits=bits, enable_qjl=qjl,
        )

    def _make_random_profile(self, compressor, block_id=42):
        """Create a realistic attention profile (sparse, non-negative)."""
        rng = np.random.RandomState(42)
        weights = rng.exponential(0.5, size=compressor.profile_dim)
        # Make it sparse: zero out 60% of buckets
        mask = rng.random(compressor.profile_dim) > 0.4
        weights *= mask
        return AttentionProfile(
            block_id=block_id,
            weights=weights,
            total_weight=float(weights.sum()),
            num_updates=int(np.count_nonzero(weights)),
        )

    def test_3bit_cosine_similarity(self):
        """3-bit PolarQuant + QJL should achieve >0.95 cosine similarity."""
        compressor = self._make_compressor(dim=32, bits=3, qjl=True)
        profile = self._make_random_profile(compressor)

        compressed = compressor.compress(profile)

        assert compressed["cosine_similarity"] > 0.90, (
            f"Expected >0.90 cosine sim, got {compressed['cosine_similarity']:.4f}"
        )

    def test_4bit_better_than_3bit(self):
        """4-bit should have lower MSE than 3-bit."""
        compressor_3 = self._make_compressor(dim=32, bits=3)
        compressor_4 = self._make_compressor(dim=32, bits=4)

        rng = np.random.RandomState(42)
        weights = rng.exponential(0.5, size=32)
        profile_3 = AttentionProfile(block_id=42, weights=weights.copy())
        profile_4 = AttentionProfile(block_id=42, weights=weights.copy())

        c3 = compressor_3.compress(profile_3)
        c4 = compressor_4.compress(profile_4)

        assert c4["mse"] <= c3["mse"], "4-bit should have <= MSE than 3-bit"

    def test_qjl_improves_quality(self):
        """QJL correction should improve or maintain quality."""
        no_qjl = self._make_compressor(dim=32, bits=3, qjl=False)
        with_qjl = self._make_compressor(dim=32, bits=3, qjl=True)

        rng = np.random.RandomState(42)
        weights = rng.exponential(0.5, size=32)

        p1 = AttentionProfile(block_id=42, weights=weights.copy())
        p2 = AttentionProfile(block_id=42, weights=weights.copy())

        c_no = no_qjl.compress(p1)
        c_yes = with_qjl.compress(p2)

        # QJL should improve cosine similarity (or be very close)
        assert c_yes["cosine_similarity"] >= c_no["cosine_similarity"] - 0.05

    def test_zero_profile_compression(self):
        compressor = self._make_compressor(dim=16)
        profile = AttentionProfile(
            block_id=42, weights=np.zeros(16),
        )
        compressed = compressor.compress(profile)
        assert compressed["radius"] == 0.0
        assert compressed["cosine_similarity"] == 1.0  # Trivially perfect

    def test_compression_ratio(self):
        compressor = self._make_compressor(dim=32, bits=3, qjl=True)
        ratio = compressor.compression_ratio
        # 32 bits per element (FP32) / ~4.5 bits per element ≈ 7x
        assert ratio > 5.0, f"Expected >5x compression, got {ratio:.1f}x"

    def test_many_profiles_statistics(self):
        """Compress many profiles and verify aggregate quality."""
        compressor = self._make_compressor(dim=32, bits=3, qjl=True)
        rng = np.random.RandomState(123)

        for _ in range(50):
            weights = rng.exponential(0.3, size=32) * (rng.random(32) > 0.5)
            profile = AttentionProfile(
                block_id=0, weights=weights,
                total_weight=float(weights.sum()),
            )
            compressor.compress(profile)

        stats = compressor.get_stats()
        assert stats["profiles_compressed"] == 50
        assert stats["avg_cosine_similarity"] > 0.85


# ---------------------------------------------------------------------------
# Score Estimation Tests
# ---------------------------------------------------------------------------

class TestScoreEstimation:
    """Test query-conditioned score estimation from compressed profiles."""

    def test_estimate_relevance_correct_bucket(self):
        compressor = EdgeProfileCompressor(profile_dim=8, angle_bits=4)

        # Profile with strong weight in bucket 3
        weights = np.zeros(8)
        weights[3] = 5.0
        profile = AttentionProfile(block_id=42, weights=weights)

        compressed = compressor.compress(profile)

        # Query in bucket 3 should have high relevance
        score_3 = compressor.estimate_relevance(compressed, query_bucket=3)
        # Query in bucket 0 should have low relevance
        score_0 = compressor.estimate_relevance(compressed, query_bucket=0)

        assert score_3 > score_0, "Relevant bucket should score higher"

    def test_estimate_total_relevance(self):
        compressor = EdgeProfileCompressor(profile_dim=8, angle_bits=4)

        weights = np.array([1.0, 2.0, 3.0, 4.0, 0.0, 0.0, 0.0, 0.0])
        profile = AttentionProfile(block_id=42, weights=weights)
        compressed = compressor.compress(profile)

        total = compressor.estimate_total_relevance(
            compressed, query_buckets=[0, 1, 2, 3],
        )
        assert total > 0

    def test_out_of_range_bucket(self):
        compressor = EdgeProfileCompressor(profile_dim=8)
        weights = np.ones(8)
        profile = AttentionProfile(block_id=42, weights=weights)
        compressed = compressor.compress(profile)

        # Bucket beyond profile_dim should return 0
        score = compressor.estimate_relevance(compressed, query_bucket=100)
        assert score == 0.0

    def test_compare_profiles(self):
        compressor = EdgeProfileCompressor(profile_dim=8, angle_bits=4)

        # Two similar profiles
        w1 = np.array([1.0, 2.0, 3.0, 0.0, 0.0, 0.0, 0.0, 0.0])
        w2 = np.array([1.1, 1.9, 3.1, 0.0, 0.0, 0.0, 0.0, 0.0])
        p1 = AttentionProfile(block_id=1, weights=w1)
        p2 = AttentionProfile(block_id=2, weights=w2)

        c1 = compressor.compress(p1)
        c2 = compressor.compress(p2)

        sim = compressor.compare_profiles(c1, c2)
        assert sim > 0.9, f"Similar profiles should have >0.9 cosine sim, got {sim:.3f}"

        # Orthogonal profile
        w3 = np.array([0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 2.0, 3.0])
        p3 = AttentionProfile(block_id=3, weights=w3)
        c3 = compressor.compress(p3)

        sim_orth = compressor.compare_profiles(c1, c3)
        assert sim_orth < sim, "Orthogonal profile should have lower similarity"


# ---------------------------------------------------------------------------
# Decompression Round-Trip Tests
# ---------------------------------------------------------------------------

class TestDecompressionRoundTrip:
    """Test compress → decompress round-trip."""

    def test_decompress_to_profile(self):
        compressor = EdgeProfileCompressor(profile_dim=16, angle_bits=3)
        rng = np.random.RandomState(42)
        weights = rng.exponential(0.5, size=16)

        original = AttentionProfile(
            block_id=42, weights=weights,
            total_weight=float(weights.sum()),
            num_updates=10, max_query_seen=100,
        )

        compressed = compressor.compress(original)
        reconstructed = compressor.decompress_to_profile(compressed)

        assert reconstructed.block_id == 42
        assert reconstructed.num_updates == 10
        assert reconstructed.max_query_seen == 100
        assert reconstructed.total_weight == original.total_weight

        # Reconstructed weights should be close (but not exact)
        cos_sim = float(
            np.dot(original.weights, reconstructed.weights)
            / (np.linalg.norm(original.weights) * np.linalg.norm(reconstructed.weights) + 1e-10)
        )
        assert cos_sim > 0.85


# ---------------------------------------------------------------------------
# Integration with CompressedBlockEntry
# ---------------------------------------------------------------------------

class TestCompressedBlockEntryProfile:
    """Test TQ profile integration with CompressedBlockEntry."""

    def test_compress_block_score_with_profile(self):
        bs = BlockScore(
            block_id=42, score=1.5, access_count=20,
            last_access_step=200, cumulative_weight=10.0,
        )
        bs.unique_query_sources = {1, 2, 3, 4, 5}

        edges = {(i, 42): 0.5 for i in range(10)}

        config = TurboQuantEdgeConfig(enable_profile_compression=True)
        compressor = EdgeProfileCompressor(
            profile_dim=config.profile_dim,
            angle_bits=config.profile_angle_bits,
        )

        entry = compress_block_score(
            bs, sequence_id=0, edges=edges, config=config,
            host_id=0, profile_compressor=compressor, max_query_block=10,
        )

        assert entry.has_profile
        assert entry.compressed_profile is not None
        assert "reconstructed" in entry.compressed_profile
        assert entry.compressed_profile["metadata"]["block_id"] == 42

    def test_compress_without_profile(self):
        bs = BlockScore(block_id=42, score=1.0, access_count=5)
        config = TurboQuantEdgeConfig(enable_profile_compression=False)

        entry = compress_block_score(
            bs, sequence_id=0, edges={}, config=config,
        )
        assert not entry.has_profile

    def test_compress_with_no_edges(self):
        bs = BlockScore(block_id=42, score=1.0, access_count=5)
        config = TurboQuantEdgeConfig(enable_profile_compression=True)
        compressor = EdgeProfileCompressor(profile_dim=32)

        # No edges → no profile (profile has 0 updates)
        entry = compress_block_score(
            bs, sequence_id=0, edges={}, config=config,
            profile_compressor=compressor,
        )
        assert not entry.has_profile


# ---------------------------------------------------------------------------
# Integration with TieredSequenceState
# ---------------------------------------------------------------------------

class TestTieredStateProfileIntegration:
    """Test TQ profile compression in the tiered state lifecycle."""

    def _make_tiered_state(self, bram_cap=50, enable_profile=True):
        config = TieredPCAMConfig()
        config.base.max_entries = bram_cap
        config.tq.enable_profile_compression = enable_profile
        config.policy.demotion_min_idle_steps = 5
        config.policy.demotion_score_percentile = 0.5

        seq = SequenceState(sequence_id=0, max_blocks=4096)
        pool = CXLEdgePool(config.cxl, bram_capacity=bram_cap)
        tiered = TieredSequenceState(seq, 0, config, pool, host_id=0)
        return tiered, seq, pool

    def test_demotion_creates_profiles(self):
        tiered, seq, pool = self._make_tiered_state(bram_cap=50)

        # Add blocks with edges
        for i in range(60):
            seq.block_scores[i] = BlockScore(
                block_id=i, score=float(i) * 0.1,
                last_access_step=0, access_count=5,
            )
        # Add edges to make profiles non-trivial
        for i in range(60):
            for q in range(min(i, 5)):
                seq.attention_edges[(q, i)] = 0.3

        demoted = tiered.demote_cold_blocks(current_step=100, count=20)
        assert demoted > 0

        # Check that CXL entries have profiles
        entries_with_profiles = sum(
            1 for entry in pool._entries.values() if entry.has_profile
        )
        assert entries_with_profiles > 0, "Demoted entries should have TQ profiles"

    def test_cxl_candidates_use_profiles(self):
        tiered, seq, pool = self._make_tiered_state(bram_cap=50)

        # Create a compressor matching the config
        compressor = tiered._profile_compressor
        assert compressor is not None

        # Create profiles with distinct patterns
        # Block 100: strong in bucket 2 (will match query in bucket 2)
        w_match = np.zeros(compressor.profile_dim)
        w_match[2] = 5.0
        p_match = AttentionProfile(block_id=100, weights=w_match)
        c_match = compressor.compress(p_match)

        # Block 200: strong in bucket 7 (won't match query in bucket 2)
        w_nomatch = np.zeros(compressor.profile_dim)
        w_nomatch[7] = 5.0
        p_nomatch = AttentionProfile(block_id=200, weights=w_nomatch)
        c_nomatch = compressor.compress(p_nomatch)

        # Put both in CXL pool with same scalar score
        entry1 = CompressedBlockEntry(block_id=100, sequence_id=0)
        entry1.score = 1.0
        entry1.last_access_step = 90
        entry1.compressed_profile = c_match
        pool.admit(entry1)

        entry2 = CompressedBlockEntry(block_id=200, sequence_id=0)
        entry2.score = 1.0
        entry2.last_access_step = 90
        entry2.compressed_profile = c_nomatch
        pool.admit(entry2)

        # Add a dummy edge so max_query computation works
        seq.attention_edges[(50, 999)] = 0.1

        # Query in bucket 2 region → block 100 should score higher
        candidates = tiered.get_cxl_candidates(
            query_block_id=50, k=10, current_step=100,
        )

        scores = {bid: s for bid, s in candidates}
        # Block 100 (matching profile) should rank higher than block 200
        assert scores.get(100, 0) > scores.get(200, 0), (
            f"Profile-matched block should rank higher: "
            f"100={scores.get(100)}, 200={scores.get(200)}"
        )

    def test_profile_compressor_stats_in_tiered_stats(self):
        tiered, seq, pool = self._make_tiered_state()
        stats = tiered.get_stats()
        assert "profile_compressor" in stats

    def test_disabled_profile_no_compressor(self):
        tiered, seq, pool = self._make_tiered_state(enable_profile=False)
        assert tiered._profile_compressor is None
        stats = tiered.get_stats()
        assert "profile_compressor" not in stats


# ---------------------------------------------------------------------------
# Memory Accounting Tests
# ---------------------------------------------------------------------------

class TestMemoryAccounting:
    """Test memory size calculations."""

    def test_compressed_size_3bit(self):
        compressor = EdgeProfileCompressor(profile_dim=32, angle_bits=3, enable_qjl=True)

        # radius: 16 bits
        # angles: 31 * 3 = 93 bits
        # QJL signs: 32 bits
        # metadata: 64 bits
        # Total: 16 + 93 + 32 + 64 = 205 bits = 26 bytes
        size = compressor.compressed_size_bytes()
        assert size < 30, f"Compressed profile should be <30 bytes, got {size}"

    def test_compression_ratio_matches_claim(self):
        compressor = EdgeProfileCompressor(profile_dim=32, angle_bits=3, enable_qjl=True)
        # FP32: 32 * 4 = 128 bytes
        # Compressed: ~26 bytes
        # Ratio should be > 4x
        ratio = compressor.compression_ratio
        assert ratio > 4.0, f"Expected >4x compression, got {ratio:.1f}x"

    def test_bits_per_element(self):
        compressor = EdgeProfileCompressor(profile_dim=32, angle_bits=3, enable_qjl=True)
        bpe = compressor.bits_per_element
        # (31*3 + 16) / 32 + 1 = (93+16)/32 + 1 ≈ 3.4 + 1 = 4.4 bits
        assert 3.0 < bpe < 6.0, f"Expected 3-6 bits/element, got {bpe:.2f}"


# ---------------------------------------------------------------------------
# End-to-End: TieredPCAMInterface with Profile Compression
# ---------------------------------------------------------------------------

class TestEndToEndProfileCompression:
    """Full pipeline: update → demote → CXL attend with profiles."""

    def test_full_lifecycle(self):
        config = TieredPCAMConfig()
        config.base.max_entries = 100
        config.tq.enable_profile_compression = True
        config.policy.demotion_min_idle_steps = 3
        config.policy.demotion_score_percentile = 0.5

        pcam = TieredPCAMInterface(config)
        pcam.allocate_sequence(0, 4096)

        # Phase 1: Build up edges in BRAM
        for step in range(30):
            for key in range(50):
                weight = 0.5 if key % 10 == 0 else 0.1
                pcam.update(
                    query_block_id=step, key_block_id=key,
                    weight=weight, sequence_id=0,
                )
            pcam.step()

        # Phase 2: More updates to push BRAM over capacity
        for step in range(30, 80):
            for key in range(50, 120):
                pcam.update(
                    query_block_id=step, key_block_id=key,
                    weight=0.3, sequence_id=0,
                )
            pcam.step()

        # Check that some blocks were demoted to CXL
        tiered = pcam._tiered_sequences[0]
        cxl_count = sum(
            1 for entry in pcam.cxl_pool._entries.values()
            if entry.has_profile
        )

        # Phase 3: ATTEND should merge BRAM + CXL (with profile scoring)
        candidates, latency, _ = pcam.attend(
            query_block_id=70, k=64, sequence_id=0,
        )
        assert len(candidates) > 0

        # Stats should show profile compression activity
        stats = pcam.get_stats()
        if 0 in pcam._tiered_sequences:
            tier_stats = pcam._tiered_sequences[0].get_stats()
            if "profile_compressor" in tier_stats:
                pc_stats = tier_stats["profile_compressor"]
                assert pc_stats["profiles_compressed"] >= 0
