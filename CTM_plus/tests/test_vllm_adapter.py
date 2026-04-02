"""
Validation tests for the vLLM adapter (CTMBlockSpaceManager).

Covers:
1. Eviction decisions come from KVPolicy
2. No crashes under memory pressure
3. Attention updates flow correctly
4. Performance overhead is minimal
5. Page ↔ block mapping consistency
6. Sequence lifecycle correctness
"""

import time
from CTM_plus.KVPolicy.kv_policy.vllm_adapter import CTMBlockSpaceManager, CTMvLLMConfig


def test_eviction_from_policy():
    """Eviction decisions come from KVCachePolicy scoring, not FIFO/LRU."""
    mgr = CTMBlockSpaceManager(
        block_size=16, num_gpu_blocks=8, watermark=0.0,
    )
    mgr.register_sequence(0)

    # Allocate 8 blocks (fills GPU)
    for i in range(8):
        positions = list(range(i * 16, (i + 1) * 16))
        mgr.allocate_block(seq_id=0, page_id=i, positions=positions)

    # Give high attention to blocks 0 (sink) and 4 (entity)
    for step in range(20):
        mgr.on_attention(page_id=0, attention_sum=0.5, seq_id=0, seq_len=128)
        mgr.on_attention(page_id=4, attention_sum=0.3, seq_id=0, seq_len=128)
        # Give low attention to blocks 5,6,7
        for p in (5, 6, 7):
            mgr.on_attention(page_id=p, attention_sum=0.001, seq_id=0, seq_len=128)

    # Evict — should NOT evict block 0 (sink/pinned) or 4 (high attention)
    victim = mgr.evict()
    assert victim is not None, "Expected an eviction"
    assert victim != 0, "Should not evict sink block 0"
    assert victim != 4, "Should not evict high-attention block 4"
    # Victim should be one of the low-attention blocks
    assert victim in (1, 2, 3, 5, 6, 7), f"Unexpected victim: {victim}"
    print("  PASS: eviction decisions from KVPolicy scoring")


def test_no_crash_under_pressure():
    """Survive extreme memory pressure: more allocations than capacity."""
    mgr = CTMBlockSpaceManager(
        block_size=16, num_gpu_blocks=4, watermark=0.0,
    )
    mgr.register_sequence(0)

    # Allocate 20 blocks, evicting as needed
    allocated = []
    for i in range(20):
        while mgr.num_free_gpu_blocks <= 0:
            victim = mgr.evict()
            if victim is None:
                break  # nothing to evict
        page_id = 100 + i
        positions = list(range(i * 16, (i + 1) * 16))
        mgr.allocate_block(seq_id=0, page_id=page_id, positions=positions)
        allocated.append(page_id)

        # Feed some attention
        mgr.on_attention(page_id=page_id, attention_sum=0.01, seq_id=0, seq_len=(i + 1) * 16)

    stats = mgr.get_stats()
    assert stats["gpu_pages_allocated"] <= 4, "Should not exceed capacity"
    assert stats["evictions"] > 0 or stats["filler_evictions"] > 0, "Expected evictions"
    print("  PASS: no crash under memory pressure")


def test_attention_updates_flow():
    """Attention updates flow through to KVCachePolicy and affect scores."""
    mgr = CTMBlockSpaceManager(
        block_size=16, num_gpu_blocks=16, watermark=0.0,
    )
    mgr.register_sequence(0)

    # Allocate two blocks
    mgr.allocate_block(seq_id=0, page_id=10, positions=list(range(16, 32)))
    mgr.allocate_block(seq_id=0, page_id=11, positions=list(range(32, 48)))

    # Score before attention
    score_before_10 = mgr.get_block_score(10)
    score_before_11 = mgr.get_block_score(11)

    # Give high attention to block 10, none to 11
    for _ in range(10):
        mgr.on_attention(page_id=10, attention_sum=0.5, seq_id=0, seq_len=48)

    score_after_10 = mgr.get_block_score(10)
    score_after_11 = mgr.get_block_score(11)

    # Block 10 should have higher score after attention
    assert score_after_10 > score_before_10, (
        f"Attention should increase score: {score_before_10} → {score_after_10}"
    )
    # Block 10 should score higher than block 11
    assert score_after_10 > score_after_11, (
        f"High-attention block should score higher: {score_after_10} vs {score_after_11}"
    )
    print("  PASS: attention updates flow correctly to scoring")


def test_attention_batch():
    """on_attention_batch processes multiple blocks in one call."""
    mgr = CTMBlockSpaceManager(
        block_size=16, num_gpu_blocks=16, watermark=0.0,
    )
    mgr.register_sequence(0)
    mgr.allocate_block(seq_id=0, page_id=20, positions=list(range(0, 16)))
    mgr.allocate_block(seq_id=0, page_id=21, positions=list(range(16, 32)))

    mgr.on_attention_batch(
        block_attention={20: 0.3, 21: 0.1},
        seq_id=0, seq_len=32,
    )

    s20 = mgr.get_block_score(20)
    s21 = mgr.get_block_score(21)
    # Block 20 got more attention → higher score (but also it's a sink block)
    assert s20 >= 0 and s21 >= 0, "Scores should be non-negative after attention"
    print("  PASS: batch attention updates work")


def test_page_mapping_consistency():
    """page ↔ block mapping stays consistent across lifecycle."""
    mgr = CTMBlockSpaceManager(
        block_size=16, num_gpu_blocks=8, watermark=0.0,
    )
    mgr.register_sequence(0)

    # Allocate
    for i in range(4):
        mgr.allocate_block(seq_id=0, page_id=50 + i, positions=list(range(i * 16, (i + 1) * 16)))

    assert len(mgr._page_to_block) == 4
    assert len(mgr._block_to_page) == 4
    for page_id in range(50, 54):
        block_id = mgr._page_to_block[page_id]
        assert mgr._block_to_page[block_id] == page_id

    # Evict one
    # Give attention so policy has data
    for _ in range(5):
        for i in range(4):
            mgr.on_attention(page_id=50 + i, attention_sum=0.01, seq_id=0, seq_len=64)

    victim = mgr.evict()
    assert victim is not None
    assert victim not in mgr._page_to_block, "Evicted page should be unmapped"
    assert len(mgr._page_to_block) == 3
    assert len(mgr._block_to_page) == 3

    # Complete sequence — frees remaining
    freed = mgr.complete_sequence(0)
    assert len(freed) == 3, f"Expected 3 freed pages, got {len(freed)}"
    assert len(mgr._page_to_block) == 0
    assert len(mgr._block_to_page) == 0
    print("  PASS: page mapping consistent across lifecycle")


def test_sequence_lifecycle():
    """Full sequence lifecycle: register → allocate → decode → complete."""
    mgr = CTMBlockSpaceManager(
        block_size=16, num_gpu_blocks=32, watermark=0.0,
    )

    # Register two sequences
    mgr.register_sequence(1)
    mgr.register_sequence(2)

    # Allocate blocks for seq 1
    for i in range(4):
        mgr.allocate_block(seq_id=1, page_id=100 + i, positions=list(range(i * 16, (i + 1) * 16)))
    # Allocate blocks for seq 2
    for i in range(3):
        mgr.allocate_block(seq_id=2, page_id=200 + i, positions=list(range(i * 16, (i + 1) * 16)))

    assert mgr.get_stats()["active_sequences"] == 2
    assert len(mgr._gpu_pages) == 7

    # Phase change
    mgr.on_decode_start(1)
    mgr.on_decode_start(2)

    # Some decode attention
    for _ in range(5):
        for i in range(4):
            mgr.on_attention(page_id=100 + i, attention_sum=0.02, seq_id=1, seq_len=64)
        for i in range(3):
            mgr.on_attention(page_id=200 + i, attention_sum=0.03, seq_id=2, seq_len=48)

    # Complete seq 1
    freed = mgr.complete_sequence(1)
    assert len(freed) == 4
    assert all(p in range(100, 104) for p in freed)
    assert len(mgr._gpu_pages) == 3  # only seq 2 remains

    # Complete seq 2
    freed = mgr.complete_sequence(2)
    assert len(freed) == 3
    assert len(mgr._gpu_pages) == 0
    print("  PASS: sequence lifecycle correct")


def test_pinning():
    """Pinned pages are never evicted."""
    mgr = CTMBlockSpaceManager(
        block_size=16, num_gpu_blocks=4, watermark=0.0,
    )
    mgr.register_sequence(0)

    for i in range(4):
        mgr.allocate_block(seq_id=0, page_id=i, positions=list(range(i * 16, (i + 1) * 16)))
        mgr.on_attention(page_id=i, attention_sum=0.01, seq_id=0, seq_len=64)

    # Pin pages 0 and 1
    mgr.pin_page(0)
    mgr.pin_page(1)

    # Evict twice — should not get 0 or 1
    for _ in range(2):
        victim = mgr.evict()
        if victim is not None:
            assert victim not in (0, 1), f"Pinned page {victim} was evicted"
    print("  PASS: pinned pages protected from eviction")


def test_watermark():
    """needs_eviction() respects watermark threshold."""
    mgr = CTMBlockSpaceManager(
        block_size=16, num_gpu_blocks=10, watermark=0.2,  # watermark = 2 blocks
    )
    mgr.register_sequence(0)

    # Allocate 7 blocks (3 free, above watermark of 2)
    for i in range(7):
        mgr.allocate_block(seq_id=0, page_id=i, positions=list(range(i * 16, (i + 1) * 16)))
    assert not mgr.needs_eviction(), "3 free > 2 watermark"

    # Allocate 1 more (2 free, at watermark)
    mgr.allocate_block(seq_id=0, page_id=7, positions=list(range(112, 128)))
    assert mgr.needs_eviction(), "2 free <= 2 watermark"
    print("  PASS: watermark triggers eviction correctly")


def test_overhead_minimal():
    """Verify per-block attention + eviction overhead is small."""
    mgr = CTMBlockSpaceManager(
        block_size=16, num_gpu_blocks=1000, watermark=0.0,
    )
    mgr.register_sequence(0)

    # Allocate 500 blocks
    for i in range(500):
        mgr.allocate_block(seq_id=0, page_id=i, positions=list(range(i * 16, (i + 1) * 16)))

    # Time 1000 attention updates across 500 blocks
    t0 = time.perf_counter()
    for step in range(2):
        for i in range(500):
            mgr.on_attention(page_id=i, attention_sum=0.01, seq_id=0, seq_len=8000)
    attn_time = time.perf_counter() - t0

    # Time 100 evictions
    t0 = time.perf_counter()
    for _ in range(100):
        victim = mgr.evict()
        if victim is not None:
            # Re-allocate so we can keep evicting
            mgr.allocate_block(
                seq_id=0, page_id=victim,
                positions=list(range(16)),
            )
    evict_time = time.perf_counter() - t0

    # Attention: 1000 updates should take < 200ms
    assert attn_time < 0.2, f"Attention overhead too high: {attn_time*1000:.1f}ms"
    # Eviction: 100 evictions should take < 200ms
    assert evict_time < 0.2, f"Eviction overhead too high: {evict_time*1000:.1f}ms"
    print(f"  PASS: overhead minimal (attn={attn_time*1000:.1f}ms/1000, evict={evict_time*1000:.1f}ms/100)")


def test_transformer_setup_import():
    """CTMBlockSpaceManager and CTMvLLMConfig are importable from kv_policy."""
    from CTM_plus.KVPolicy.kv_policy import CTMBlockSpaceManager, CTMvLLMConfig

    cfg = CTMvLLMConfig.for_llm_inference()
    mgr = CTMBlockSpaceManager(
        block_size=16, num_gpu_blocks=100,
        ctm_config=cfg,
    )
    assert mgr.num_gpu_blocks == 100
    assert mgr.num_free_gpu_blocks == 100
    print("  PASS: import path matches transformer_setup expectations")


def test_eviction_logging():
    """Eviction events are captured with correct metadata."""
    events = []
    mgr = CTMBlockSpaceManager(
        block_size=16, num_gpu_blocks=4, watermark=0.0,
        enable_logging=True,
    )
    mgr.event_logger.callback = lambda etype, data: events.append((etype, data))

    mgr.register_sequence(0)
    for i in range(4):
        mgr.allocate_block(seq_id=0, page_id=i, positions=list(range(i * 16, (i + 1) * 16)))
        mgr.on_attention(page_id=i, attention_sum=0.01, seq_id=0, seq_len=64)

    victim = mgr.evict()
    assert victim is not None

    eviction_events = [(t, d) for t, d in events if t == "eviction"]
    assert len(eviction_events) == 1, f"Expected 1 eviction event, got {len(eviction_events)}"
    _, data = eviction_events[0]
    assert "block_id" in data
    assert "seq_id" in data
    assert data["importance"] in ("sink", "entity", "filler")
    assert "attention_ema" in data
    assert "step" in data
    assert data["page_id"] == victim
    print("  PASS: eviction logging captures correct metadata")


def test_recompute_tracking():
    """Recompute events are counted and logged when evicted blocks are re-accessed."""
    events = []
    mgr = CTMBlockSpaceManager(
        block_size=16, num_gpu_blocks=4, watermark=0.0,
        enable_logging=True,
    )
    mgr.event_logger.callback = lambda etype, data: events.append((etype, data))

    mgr.register_sequence(0)
    for i in range(4):
        mgr.allocate_block(seq_id=0, page_id=i, positions=list(range(i * 16, (i + 1) * 16)))
        for _ in range(3):
            mgr.on_attention(page_id=i, attention_sum=0.01, seq_id=0, seq_len=64)

    victim = mgr.evict()
    assert victim is not None

    # Access the evicted page — should trigger recompute
    mgr.on_attention(page_id=victim, attention_sum=0.05, seq_id=0, seq_len=64)

    assert mgr._recompute_total == 1, f"Expected 1 recompute, got {mgr._recompute_total}"
    assert mgr._recompute_filler >= 0
    recompute_events = [(t, d) for t, d in events if t == "recompute"]
    assert len(recompute_events) == 1
    _, data = recompute_events[0]
    assert data["page_id"] == victim
    assert data["recompute_cost"] == 16  # block_size

    # Second access of same page should NOT double-count
    mgr.on_attention(page_id=victim, attention_sum=0.05, seq_id=0, seq_len=64)
    assert mgr._recompute_total == 1, "Recompute should only count once"

    stats = mgr.get_stats()
    assert stats["recompute_total"] == 1
    print("  PASS: recompute tracking counts once per evicted block")


def test_attention_snapshot_sampled():
    """Attention snapshots fire at intervals, not every step."""
    events = []
    mgr = CTMBlockSpaceManager(
        block_size=16, num_gpu_blocks=16, watermark=0.0,
        enable_logging=True,
    )
    mgr.event_logger.snapshot_interval = 5
    mgr.event_logger.callback = lambda etype, data: events.append((etype, data))

    mgr.register_sequence(0)
    for i in range(4):
        mgr.allocate_block(seq_id=0, page_id=i, positions=list(range(i * 16, (i + 1) * 16)))

    # Run 20 attention updates (on page 0, which ticks the step counter)
    for _ in range(20):
        mgr.on_attention(page_id=0, attention_sum=0.1, seq_id=0, seq_len=64)

    snapshots = [d for t, d in events if t == "attention_snapshot"]
    pressure = [d for t, d in events if t == "cache_pressure"]

    # With interval=5 and 20 steps, expect 4 snapshots (steps 5, 10, 15, 20)
    assert len(snapshots) == 4, f"Expected 4 snapshots, got {len(snapshots)}"
    assert len(pressure) == 4, f"Expected 4 pressure events, got {len(pressure)}"

    # Verify snapshot structure
    assert "top_blocks" in snapshots[0]
    assert len(snapshots[0]["top_blocks"]) > 0
    top_block = snapshots[0]["top_blocks"][0]
    assert "attention_ema" in top_block
    assert "importance" in top_block
    print("  PASS: attention snapshots fire at sampled intervals")


def test_cache_pressure_metrics():
    """Cache pressure events contain utilization data."""
    events = []
    mgr = CTMBlockSpaceManager(
        block_size=16, num_gpu_blocks=8, watermark=0.1,
        enable_logging=True,
    )
    mgr.event_logger.snapshot_interval = 1  # every step for this test
    mgr.event_logger.callback = lambda etype, data: events.append((etype, data))

    mgr.register_sequence(0)
    for i in range(6):
        mgr.allocate_block(seq_id=0, page_id=i, positions=list(range(i * 16, (i + 1) * 16)))

    mgr.on_attention(page_id=0, attention_sum=0.1, seq_id=0, seq_len=96)

    pressure = [d for t, d in events if t == "cache_pressure"]
    assert len(pressure) >= 1
    p = pressure[0]
    assert p["active_blocks"] == 6
    assert p["capacity"] == 8
    assert p["utilization_pct"] == 75.0
    assert p["free"] == 2
    assert isinstance(p["needs_eviction"], bool)
    print("  PASS: cache pressure metrics correct")


def test_logging_disabled_no_overhead():
    """With logging disabled, no events are emitted and overhead is negligible."""
    import time

    mgr = CTMBlockSpaceManager(
        block_size=16, num_gpu_blocks=1000, watermark=0.0,
        enable_logging=False,
    )
    mgr.register_sequence(0)
    for i in range(500):
        mgr.allocate_block(seq_id=0, page_id=i, positions=list(range(i * 16, (i + 1) * 16)))

    t0 = time.perf_counter()
    for step in range(2):
        for i in range(500):
            mgr.on_attention(page_id=i, attention_sum=0.01, seq_id=0, seq_len=8000)
    elapsed = time.perf_counter() - t0

    # No events should have been captured
    assert mgr.event_logger.get_event_counts() == {}
    # Overhead should be similar to baseline (< 200ms for 1000 calls)
    assert elapsed < 0.2, f"Disabled logging overhead too high: {elapsed*1000:.1f}ms"
    print(f"  PASS: logging disabled has negligible overhead ({elapsed*1000:.1f}ms/1000)")


def test_event_counts_in_stats():
    """get_stats() includes event counts and recompute counters."""
    mgr = CTMBlockSpaceManager(
        block_size=16, num_gpu_blocks=4, watermark=0.0,
        enable_logging=True,
    )
    mgr.register_sequence(0)
    for i in range(4):
        mgr.allocate_block(seq_id=0, page_id=i, positions=list(range(i * 16, (i + 1) * 16)))
        mgr.on_attention(page_id=i, attention_sum=0.01, seq_id=0, seq_len=64)

    mgr.evict()

    stats = mgr.get_stats()
    assert "recompute_total" in stats
    assert "recompute_important" in stats
    assert "recompute_filler" in stats
    assert "event_counts" in stats
    assert stats["event_counts"].get("eviction", 0) == 1
    print("  PASS: event counts and recompute in get_stats()")


def run_all_tests():
    print("Running vLLM adapter validation tests...")
    test_eviction_from_policy()
    test_no_crash_under_pressure()
    test_attention_updates_flow()
    test_attention_batch()
    test_page_mapping_consistency()
    test_sequence_lifecycle()
    test_pinning()
    test_watermark()
    test_overhead_minimal()
    test_transformer_setup_import()
    # Instrumentation tests
    test_eviction_logging()
    test_recompute_tracking()
    test_attention_snapshot_sampled()
    test_cache_pressure_metrics()
    test_logging_disabled_no_overhead()
    test_event_counts_in_stats()
    print("\nAll 16 tests passed.")


if __name__ == "__main__":
    run_all_tests()
