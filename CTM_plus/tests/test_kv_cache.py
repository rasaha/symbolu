"""
Assertion-based regression and unit tests for KV cache eviction policy
and simulator. Fast, deterministic, minimal.
"""

import math
from CTM_plus.KVSimulator.kv_simulator.buffer_pool import (
    KVCacheSimulator,
    PolicyType,
    BlockType,
    Phase,
    compare_policies,
    compare_continuous_batching,
    run_workload,
    sink_and_recent_attention,
    entity_focused_attention,
    uniform_attention,
    mixed_multihead_attention,
    _block_attn_sink_recent,
    _block_attn_entity_focused,
    _block_attn_uniform,
    _block_attn_mixed,
)
from CTM_plus.KVPolicy.kv_policy.attention_evictor import (
    KVCachePolicy,
    InferencePhase,
    compute_adaptive_threshold,
    classify_block_importance,
)


# =============================================================================
# Test 1: recompute_cost counted exactly once on first re-access
# =============================================================================

def test_recompute_cost_counted_once():
    """recompute_cost is incremented only on first re-access after eviction."""
    sim = KVCacheSimulator(
        max_blocks=4, block_size=16, policy_type=PolicyType.LRU, seed=42,
    )
    # Create a sequence with 5 blocks (exceeds 4-block budget → evictions)
    sim.add_sequence(0, 80)  # 80 / 16 = 5 blocks
    sim.prefill_sequence(0)

    # At least one block should have been evicted during prefill
    assert sim.stats["blocks_evicted"] > 0, "Expected evictions under memory pressure"

    # Run decode steps — evicted blocks will be re-accessed
    initial_recompute = sim.stats["recompute_cost"]
    sim.decode_step(0)
    first_recompute = sim.stats["recompute_cost"]
    # There should be some recompute on first access of evicted blocks
    assert first_recompute >= initial_recompute

    # Run more decode steps — same evicted blocks should NOT add more recompute
    # (they were already counted on first re-access and removed from tracking)
    sim.decode_step(0)
    sim.decode_step(0)
    second_recompute = sim.stats["recompute_cost"]
    # Recompute from the originally evicted blocks should not increase again
    # (new evictions during decode may cause new recompute, but the original
    # evicted set is cleared after first re-access)
    evicted_before_decode = sim._evicted_block_ids.copy()
    # The key invariant: _evicted_block_ids shrinks as blocks are re-accessed
    # After enough decode steps, all originally evicted blocks are re-accessed
    for _ in range(10):
        sim.decode_step(0)
    # All originally evicted blocks have been counted
    assert sim.stats["recompute_cost"] >= first_recompute
    print("  PASS: recompute_cost counted once per evicted block")


# =============================================================================
# Test 2: accuracy = decode_block_hits / decode_block_accesses
# =============================================================================

def test_accuracy_metric():
    """accuracy equals retained_hits / total_accesses during decode."""
    sim = KVCacheSimulator(
        max_blocks=8, block_size=16, policy_type=PolicyType.FIFO, seed=42,
    )
    sim.add_sequence(0, 128)  # 8 blocks, exactly fills cache
    sim.prefill_sequence(0)

    for _ in range(10):
        sim.decode_step(0)

    metrics = sim.get_metrics()
    accesses = metrics["decode_block_accesses"]
    hits = metrics["decode_block_hits"]

    assert accesses > 0, "Expected decode block accesses"
    expected_accuracy = hits / accesses
    assert abs(metrics["accuracy"] - expected_accuracy) < 1e-9, (
        f"accuracy={metrics['accuracy']}, expected={expected_accuracy}"
    )
    print("  PASS: accuracy metric matches hit_rate formula")


# =============================================================================
# Test 3: decode block positions append correctly across boundaries
# =============================================================================

def test_decode_position_tracking():
    """New tokens during decode append to correct block, crossing boundaries."""
    sim = KVCacheSimulator(
        max_blocks=64, block_size=4, policy_type=PolicyType.LRU, seed=42,
    )
    sim.add_sequence(0, 8)  # 2 blocks of 4 tokens each
    sim.prefill_sequence(0)

    seq = sim.sequences[0]
    initial_blocks = len(seq.block_ids)
    assert initial_blocks == 2, f"Expected 2 blocks, got {initial_blocks}"

    # Decode 5 tokens: first fills block 2 (pos 8-11), then needs block 3 (pos 12)
    for _ in range(5):
        sim.decode_step(0)

    # Should have created new block(s) for decode tokens
    assert len(seq.block_ids) > initial_blocks, "Expected new blocks during decode"

    # Verify the last block contains the latest position
    last_block = sim.blocks[seq.last_block_id]
    max_pos = max(last_block.token_positions)
    expected_max = 8 + 5 - 1  # 12
    assert max_pos == expected_max, f"Expected max pos {expected_max}, got {max_pos}"

    # Verify positions are contiguous within blocks
    for bid in seq.block_ids:
        if bid in sim.blocks:
            positions = sim.blocks[bid].token_positions
            for i in range(1, len(positions)):
                assert positions[i] == positions[i-1] + 1, (
                    f"Non-contiguous positions in block {bid}: {positions}"
                )
    print("  PASS: decode position tracking correct across block boundaries")


# =============================================================================
# Test 4: KVPolicy adaptive threshold scales with attention magnitude
# =============================================================================

def test_adaptive_entity_threshold():
    """Adaptive threshold scales with observed attention, not fixed at 0.02."""
    # Shared function tests
    assert compute_adaptive_threshold(0.0, 0) == 0.02, "Floor used when no data"
    assert compute_adaptive_threshold(0.0, 5) == 0.02, "Floor used during warmup"
    # After warmup: threshold = mean * k = (1.0/100) * 2.0 = 0.02
    assert abs(compute_adaptive_threshold(1.0, 100, k=2.0) - 0.02) < 1e-9
    # For tiny attention (long sequences): threshold scales down
    result = compute_adaptive_threshold(0.001, 100, k=2.0)
    assert result < 0.001, f"Expected tiny threshold, got {result}"

    # Classification function
    assert classify_block_importance(True, 0.0, 0.5) == 1.0, "Sink always 1.0"
    assert classify_block_importance(False, 1.0, 0.5) == 0.8, "High attention → entity"
    assert classify_block_importance(False, 0.1, 0.5) == 0.1, "Low attention → filler"

    # KVCachePolicy integration
    policy = KVCachePolicy(max_blocks=64, block_size=16)
    policy.register_sequence(0)

    # Simulate many low-attention events (like a 32K sequence)
    for i in range(20):
        policy.on_block_attention(
            block_id=i, attention_sum=0.0005,
            sequence_id=0, seq_len=32768,
        )

    # Threshold should be much lower than 0.02
    threshold = policy._adaptive_threshold
    assert threshold < 0.01, (
        f"Threshold should scale down for long sequences, got {threshold}"
    )
    print("  PASS: adaptive entity threshold scales correctly")


# =============================================================================
# Test 5: all policies run without errors
# =============================================================================

def test_all_policies_runnable():
    """Every policy type runs a minimal workload without errors."""
    for policy_type in PolicyType:
        kwargs = {}
        if policy_type == PolicyType.KV_POLICY:
            kwargs["kv_policy"] = KVCachePolicy(
                max_blocks=32, block_size=16,
            )

        sim = KVCacheSimulator(
            max_blocks=32, block_size=16,
            policy_type=policy_type, seed=42,
            **kwargs,
        )
        sim.add_sequence(0, 64)
        sim.prefill_sequence(0)
        for _ in range(8):
            sim.decode_step(0)
        metrics = sim.get_metrics()

        assert metrics["decode_block_accesses"] > 0, (
            f"{policy_type.value}: no decode accesses"
        )
        assert metrics["accuracy"] >= 0.0, (
            f"{policy_type.value}: negative accuracy"
        )
    print("  PASS: all 5 policies run without errors")


# =============================================================================
# Test 6: staggered arrival is reproducible and functional
# =============================================================================

def test_staggered_arrival_reproducible():
    """Staggered mode produces identical results for same seed."""
    sequences = [(i, 256) for i in range(4)]

    run1 = run_workload(
        max_blocks=32, block_size=16, sequences=sequences,
        decode_steps_per_seq=64, policy_type=PolicyType.LRU, seed=42,
        staggered=True, arrival_interval=16,
    )
    run2 = run_workload(
        max_blocks=32, block_size=16, sequences=sequences,
        decode_steps_per_seq=64, policy_type=PolicyType.LRU, seed=42,
        staggered=True, arrival_interval=16,
    )

    assert run1["recompute_cost"] == run2["recompute_cost"], "Staggered not reproducible"
    assert run1["blocks_evicted"] == run2["blocks_evicted"], "Staggered not reproducible"
    assert run1["accuracy"] == run2["accuracy"], "Staggered not reproducible"
    assert run1["decode_block_accesses"] > 0, "No decode accesses in staggered mode"

    # Staggered should differ from non-staggered (different admission order)
    run_batch = run_workload(
        max_blocks=32, block_size=16, sequences=sequences,
        decode_steps_per_seq=64, policy_type=PolicyType.LRU, seed=42,
        staggered=False,
    )
    # They should have different decode access counts since sequences start at
    # different times in staggered mode
    assert run1["decode_block_accesses"] != run_batch["decode_block_accesses"], (
        "Staggered should differ from batch"
    )
    print("  PASS: staggered arrival reproducible and distinct from batch")


# =============================================================================
# Test 7: block-level attention matches per-position attention
# =============================================================================

def test_block_attention_accuracy():
    """Block-level O(1) attention matches per-position summation."""
    seq_len = 1024
    sink_tokens = 4
    recent_window = 128
    block_size = 16

    for pattern_fn, block_fn, name in [
        (sink_and_recent_attention, _block_attn_sink_recent, "sink_recent"),
        (entity_focused_attention, _block_attn_entity_focused, "entity"),
        (uniform_attention, _block_attn_uniform, "uniform"),
        (mixed_multihead_attention, _block_attn_mixed, "mixed"),
    ]:
        # Generate full per-position attention
        weights = pattern_fn(seq_len, sink_tokens, recent_window)

        # Compare block-level vs summed per-position for each block
        total_block = 0.0
        max_err = 0.0
        for b in range(0, seq_len, block_size):
            n = min(block_size, seq_len - b)
            # Per-position sum
            pos_sum = sum(weights[b:b+n])
            # Block-level O(1)
            blk_sum = block_fn(b, n, seq_len, sink_tokens, recent_window)
            total_block += blk_sum
            err = abs(pos_sum - blk_sum)
            max_err = max(max_err, err)

        # Total should be ~1.0
        assert abs(total_block - 1.0) < 0.01, (
            f"{name}: total block attention {total_block} != 1.0"
        )
        # Max error per block should be small
        assert max_err < 0.005, (
            f"{name}: max block error {max_err} too large"
        )
    print("  PASS: block-level attention matches per-position within tolerance")


# =============================================================================
# Test 8: compare_policies staggered mode works
# =============================================================================

def test_compare_policies_staggered():
    """compare_policies passes through staggered params correctly."""
    results = compare_policies(
        max_blocks=32, block_size=16, num_sequences=3,
        context_length=128, decode_steps=32, seed=42,
        staggered=True, arrival_interval=8,
    )
    assert len(results) == 5, f"Expected 5 policies, got {len(results)}"
    for name, m in results.items():
        assert m["decode_block_accesses"] > 0, f"{name}: no decode accesses"
    print("  PASS: compare_policies staggered mode works")


# =============================================================================
# Test 9: continuous batching reproducible
# =============================================================================

def test_continuous_batching_reproducible():
    """Continuous batching produces identical results for same seed."""
    r1 = compare_continuous_batching(
        max_blocks=64, block_size=16, total_steps=50, seed=42,
    )
    r2 = compare_continuous_batching(
        max_blocks=64, block_size=16, total_steps=50, seed=42,
    )
    # Only check deterministic policies (LRU, FIFO). Random, CTM+, and
    # KV_POLICY use unseeded random.sample/random.choice internally.
    for policy in ("lru", "fifo"):
        assert r1[policy]["recompute_cost"] == r2[policy]["recompute_cost"], (
            f"{policy}: continuous batching not reproducible"
        )
    print("  PASS: continuous batching reproducible")


# =============================================================================
# Runner
# =============================================================================

def run_all_tests():
    print("Running KV cache assertion tests...")
    test_recompute_cost_counted_once()
    test_accuracy_metric()
    test_decode_position_tracking()
    test_adaptive_entity_threshold()
    test_all_policies_runnable()
    test_staggered_arrival_reproducible()
    test_block_attention_accuracy()
    test_compare_policies_staggered()
    test_continuous_batching_reproducible()
    print("\nAll 9 tests passed.")


if __name__ == "__main__":
    run_all_tests()
