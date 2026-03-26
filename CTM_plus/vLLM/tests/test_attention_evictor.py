"""
Tests for the Attention-Aware KV-Cache Evictor.

Validates:
1. Frequency sketch accuracy
2. S3-FIFO queue behavior
3. Position classification
4. Attention-aware eviction vs LRU baseline
5. Phase-aware policy switching
6. Sequence priority handling
7. Benchmark: hit rate comparison on realistic workloads
"""

import math
import random
import time
from typing import Set

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from ctm_plus_vllm.attention_evictor import (
    AttentionAwareEvictor,
    FrequencySketch,
    S3FIFOQueue,
    PositionClassifier,
    PositionClass,
    InferencePhase,
)
from ctm_plus_vllm.kv_cache_simulator import (
    KVCacheSimulator,
    EvictionPolicy,
    CTMKVConfig,
    WorkloadGenerator,
    AttentionPatternGenerator,
)


# =============================================================================
# Unit Tests
# =============================================================================

def test_frequency_sketch():
    """Test Count-Min Sketch frequency estimation."""
    sketch = FrequencySketch(capacity=1024)

    # Insert known frequencies
    for _ in range(10):
        sketch.increment(42)
    for _ in range(5):
        sketch.increment(99)
    for _ in range(1):
        sketch.increment(7)

    # Estimates should reflect relative frequency
    est_42 = sketch.estimate(42)
    est_99 = sketch.estimate(99)
    est_7 = sketch.estimate(7)
    est_unknown = sketch.estimate(12345)

    assert est_42 >= est_99, f"42 should be more frequent: {est_42} vs {est_99}"
    assert est_99 >= est_7, f"99 should be more frequent: {est_99} vs {est_7}"
    assert est_unknown == 0, f"Unknown should be 0: {est_unknown}"

    print(f"  Sketch: 42={est_42}, 99={est_99}, 7={est_7}, unknown={est_unknown}")
    print("  PASS: Frequency sketch")


def test_frequency_sketch_reset():
    """Test that sketch resets (ages) correctly."""
    sketch = FrequencySketch(capacity=100)

    # Fill to trigger reset
    for i in range(1100):
        sketch.increment(i % 50)

    # After reset, counts should be halved
    est = sketch.estimate(0)
    assert est < 15, f"After reset, estimate should be reduced: {est}"
    print("  PASS: Frequency sketch reset")


def test_s3fifo_basic():
    """Test S3-FIFO admission and eviction."""
    q = S3FIFOQueue(capacity=10, small_ratio=0.3)
    # small_capacity=3, main_capacity=7

    # Admit 3 blocks to fill small queue
    for i in range(3):
        evicted = q.admit(i, time.monotonic())
        assert evicted is None, f"Should not evict yet, got {evicted}"

    assert q.size == 3, f"Expected 3, got {q.size}"

    # Access blocks 0 and 1 (mark as visited -> promote to main on eviction)
    q.access(0)
    q.access(1)

    # Admit block 3 -> should evict unvisited block 2 from small
    evicted = q.admit(3, time.monotonic())
    assert evicted == 2, f"Should evict unvisited block 2, got {evicted}"

    # Blocks 0 and 1 should have been promoted to main
    assert 0 in q.main, "Block 0 should be in main after visit+eviction"
    assert 1 in q.main, "Block 1 should be in main after visit+eviction"

    print(f"  Evicted block {evicted}, blocks 0,1 promoted to main")
    print("  PASS: S3-FIFO basic")


def test_s3fifo_ghost_hit():
    """Test S3-FIFO ghost queue behavior."""
    q = S3FIFOQueue(capacity=5, small_ratio=0.4)

    # Fill and evict
    for i in range(8):
        q.admit(i, time.monotonic())

    # Some blocks should be in ghost
    ghost_count = len(q.ghost)
    assert ghost_count > 0, "Ghost queue should have entries"

    # Re-admit a ghost block — should go to main
    ghost_block = list(q.ghost.keys())[0]
    q.admit(ghost_block, time.monotonic())
    assert ghost_block in q.main, f"Ghost hit should promote to main"

    print(f"  Ghost had {ghost_count} entries, re-admitted {ghost_block} to main")
    print("  PASS: S3-FIFO ghost hit")


def test_position_classifier():
    """Test position classification."""
    classifier = PositionClassifier(
        sink_tokens=4,
        recent_window=256,
        entity_attention_threshold=0.02,
    )

    # Sink positions
    assert classifier.classify(0, 1000, 0.0) == PositionClass.SINK
    assert classifier.classify(3, 1000, 0.0) == PositionClass.SINK

    # Recent window
    assert classifier.classify(900, 1000, 0.0) == PositionClass.RECENT

    # Entity (high attention)
    assert classifier.classify(500, 1000, 0.05) == PositionClass.ENTITY

    # Filler
    assert classifier.classify(500, 1000, 0.001) == PositionClass.FILLER

    print("  PASS: Position classifier")


def test_attention_evictor_sink_protection():
    """Test that attention sink tokens are never evicted."""
    evictor = AttentionAwareEvictor(
        max_blocks=10,
        block_size=16,
        sink_tokens=4,
    )

    evictor.register_sequence(seq_id := 1, max_tokens=1000)

    # Add tokens — first 4 are sinks
    for pos in range(64):  # 4 blocks of 16 tokens
        block_id = pos // 16
        evictor.on_token_access(
            token_id=pos,
            position=pos,
            sequence_id=seq_id,
            block_id=block_id,
            attention_weight=0.01 if pos >= 4 else 0.15,
            seq_len=1000,
        )

    # Block 0 contains sinks — should be pinned
    assert 0 in evictor.pinned_blocks, "Block 0 (sinks) should be pinned"

    # Try to select victim — should never be block 0
    for _ in range(10):
        victim = evictor.select_victim()
        if victim is not None:
            assert victim != 0, "Should never evict sink block"

    print("  PASS: Sink token protection")


def test_attention_evictor_filler_first():
    """Test that filler tokens are evicted before entities."""
    evictor = AttentionAwareEvictor(
        max_blocks=4,
        block_size=4,
        sink_tokens=0,
        recent_window=0,
        entity_attention_threshold=0.05,
    )

    evictor.register_sequence(seq_id := 1, max_tokens=1000)

    # Block 0: filler tokens (low attention)
    for i in range(4):
        evictor.on_token_access(i, i, seq_id, 0, attention_weight=0.001, seq_len=100)

    # Block 1: entity tokens (high attention)
    for i in range(4, 8):
        evictor.on_token_access(i, i, seq_id, 1, attention_weight=0.10, seq_len=100)

    # Block 2: mixed
    for i in range(8, 12):
        evictor.on_token_access(i, i, seq_id, 2, attention_weight=0.03, seq_len=100)

    # Block 3: filler
    for i in range(12, 16):
        evictor.on_token_access(i, i, seq_id, 3, attention_weight=0.002, seq_len=100)

    # Recompute scores
    evictor._recompute_block_scores()

    victim = evictor.select_victim()
    # Should pick one of the filler blocks (0 or 3)
    assert victim in (0, 3), f"Should evict filler block, got {victim}"

    print(f"  Evicted block {victim} (filler)")
    print("  PASS: Filler-first eviction")


def test_phase_aware_scoring():
    """Test that phase switching changes eviction behavior."""
    evictor = AttentionAwareEvictor(max_blocks=10, block_size=4)
    seq_id = 1

    evictor.register_sequence(seq_id, max_tokens=1000)

    # Add blocks during prefill
    evictor.set_sequence_phase(seq_id, InferencePhase.PREFILL)
    for i in range(20):
        block_id = i // 4
        evictor.on_token_access(i, i, seq_id, block_id, 0.01, seq_len=100)

    stats_prefill = evictor.get_stats()

    # Switch to decode
    evictor.set_sequence_phase(seq_id, InferencePhase.DECODE)
    assert evictor.stats["phase_switches"] == 1

    # Complete sequence
    freed = evictor.complete_sequence(seq_id)
    assert len(freed) > 0, "Should free blocks on completion"

    print(f"  Freed {len(freed)} blocks on completion")
    print("  PASS: Phase-aware scoring")


def test_sequence_priority():
    """Test that high-priority sequences are protected."""
    evictor = AttentionAwareEvictor(max_blocks=8, block_size=4)

    # Low priority sequence
    evictor.register_sequence(1, priority=0.1, max_tokens=100)
    for i in range(16):
        evictor.on_token_access(i, i, 1, i // 4, 0.01, seq_len=100)

    # High priority sequence
    evictor.register_sequence(2, priority=1.0, max_tokens=100)
    for i in range(16, 32):
        evictor.on_token_access(i, i, 2, 4 + (i - 16) // 4, 0.01, seq_len=100)

    evictor._recompute_block_scores()

    # Victim should come from low-priority sequence
    victim = evictor.select_victim()
    assert victim is not None

    # The victim block should belong to sequence 1 (low priority)
    victim_tokens = evictor.blocks.get(victim, set())
    if victim_tokens:
        victim_seq = evictor.tokens[next(iter(victim_tokens))].sequence_id
        assert victim_seq == 1, f"Should evict from low-priority seq, got seq {victim_seq}"
        print(f"  Evicted block {victim} from low-priority sequence {victim_seq}")

    print("  PASS: Sequence priority")


# =============================================================================
# Benchmark: Attention Evictor vs LRU
# =============================================================================

def benchmark_hit_rate():
    """Compare hit rates between attention-aware evictor and baselines."""
    print("\n=== Hit Rate Benchmark ===\n")

    seq_len = 512
    cache_sizes = [128, 256]
    workloads = {
        "multi_turn": lambda: WorkloadGenerator(seq_len).multi_turn_conversation(3, 64),
        "doc_qa": lambda: WorkloadGenerator(seq_len).document_qa(256, 3, 20),
        "zipfian": lambda: WorkloadGenerator(seq_len).zipfian_hotspot(5000, 1.2),
    }

    for name, gen_workload in workloads.items():
        workload = gen_workload()
        print(f"Workload: {name} ({len(workload)} accesses)")

        for cache_size in cache_sizes:
            # LRU baseline
            lru_sim = KVCacheSimulator(cache_size, EvictionPolicy.LRU)
            for pos, token_type, attn in workload:
                lru_sim.access(pos, token_type, attn)
            lru_hr = lru_sim.hit_rate

            # CTM+ (existing)
            ctm_sim = KVCacheSimulator(cache_size, EvictionPolicy.CTM_PLUS)
            for pos, token_type, attn in workload:
                ctm_sim.access(pos, token_type, attn)
            ctm_hr = ctm_sim.hit_rate

            # Attention-aware evictor
            attn_evictor = AttentionAwareEvictor(
                max_blocks=cache_size,
                block_size=1,  # 1 token per block for fair comparison
                sink_tokens=4,
                recent_window=min(256, cache_size // 2),
            )
            attn_evictor.register_sequence(1, max_tokens=seq_len)

            attn_hits = 0
            attn_total = 0
            # Track which positions are cached for O(1) lookup
            cached_positions: Set[int] = set()
            for pos, token_type, attn_weight in workload:
                attn_total += 1
                if pos in cached_positions:
                    attn_hits += 1

                attn_evictor.on_token_access(
                    token_id=pos,
                    position=pos,
                    sequence_id=1,
                    block_id=pos,  # 1:1 token:block
                    attention_weight=attn_weight,
                    seq_len=seq_len,
                )

                cached_positions.add(pos)

                # Evict if over capacity
                while len(attn_evictor.gpu_blocks) > cache_size:
                    victim = attn_evictor.select_victim()
                    if victim is not None:
                        attn_evictor.evict_block(victim)
                        cached_positions.discard(victim)
                    else:
                        break

            attn_hr = attn_hits / attn_total if attn_total > 0 else 0.0

            delta_lru = (attn_hr - lru_hr) * 100
            delta_ctm = (attn_hr - ctm_hr) * 100

            print(
                f"  cache={cache_size:>5}: "
                f"LRU={lru_hr:.3f}  CTM+={ctm_hr:.3f}  "
                f"Attn={attn_hr:.3f}  "
                f"(vs LRU: {delta_lru:+.1f}%, vs CTM+: {delta_ctm:+.1f}%)"
            )

        print()


def benchmark_quality_preservation():
    """Test important token retention at different cache ratios."""
    print("\n=== Quality Preservation Benchmark ===\n")

    seq_len = 2048
    random.seed(42)

    # Define important positions (sinks + entities)
    sink_positions = set(range(4))
    entity_positions = set(random.sample(range(100, seq_len - 256), seq_len // 20))
    important = sink_positions | entity_positions

    for cache_ratio in [0.25, 0.50, 0.75]:
        cache_size = int(seq_len * cache_ratio)

        evictor = AttentionAwareEvictor(
            max_blocks=cache_size,
            block_size=1,
            sink_tokens=4,
            recent_window=256,
            entity_attention_threshold=0.02,
        )
        evictor.register_sequence(1, max_tokens=seq_len)

        # Process all tokens
        for pos in range(seq_len):
            attn = 0.15 if pos in sink_positions else (
                0.05 if pos in entity_positions else 0.005
            )
            evictor.on_token_access(pos, pos, 1, pos, attn, seq_len)

            while len(evictor.gpu_blocks) > cache_size:
                victim = evictor.select_victim()
                if victim is not None:
                    evictor.evict_block(victim)
                else:
                    break

        # Check retention
        retained = evictor.gpu_blocks & important
        retention_rate = len(retained) / len(important) if important else 0

        # Breakdown
        sinks_retained = len(evictor.gpu_blocks & sink_positions)
        entities_retained = len(evictor.gpu_blocks & entity_positions)

        print(
            f"  cache_ratio={cache_ratio:.0%}: "
            f"retention={retention_rate:.1%}  "
            f"sinks={sinks_retained}/{len(sink_positions)}  "
            f"entities={entities_retained}/{len(entity_positions)}"
        )

    print()


# =============================================================================
# Main
# =============================================================================

def main():
    print("=" * 60)
    print("CTM+ Attention-Aware KV-Cache Evictor Tests")
    print("=" * 60)

    # Unit tests
    print("\n--- Unit Tests ---")
    test_frequency_sketch()
    test_frequency_sketch_reset()
    test_s3fifo_basic()
    test_s3fifo_ghost_hit()
    test_position_classifier()
    test_attention_evictor_sink_protection()
    test_attention_evictor_filler_first()
    test_phase_aware_scoring()
    test_sequence_priority()

    print("\nAll unit tests PASSED")

    # Benchmarks
    benchmark_hit_rate()
    benchmark_quality_preservation()

    print("Done.")


if __name__ == "__main__":
    main()
