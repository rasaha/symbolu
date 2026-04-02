#!/usr/bin/env python3
"""
Stress-test scenarios for KV cache eviction policies.

Validates whether KVPolicy advantages hold under realistic, high-pressure
conditions compared to LRU, FIFO, and Random baselines.

Usage:
    python -m CTM_plus.KVSimulator.stress_test
"""

import time

from CTM_plus.KVSimulator.kv_simulator.buffer_pool import (
    compare_continuous_batching,
    compare_policies,
    entity_focused_attention,
    mixed_multihead_attention,
    sink_and_recent_attention,
    uniform_attention,
)

SEEDS = [42, 137, 271, 389, 503]
BLOCK_SIZE = 16


def print_table(title, results):
    """Print a formatted results table."""
    print(f"\n{'=' * 78}")
    print(f"  {title}")
    print(f"{'=' * 78}")

    # Check if continuous-batching metrics are present
    has_cb = "avg_utilization" in next(iter(results.values()))

    header = f"  {'Policy':<12}{'Recomp':>8}{'Evict':>8}{'Acc%':>8}{'ImpEv':>7}"
    if has_cb:
        header += f"{'AvgUtil':>9}{'HiPres%':>9}{'SeqDone':>8}"
    print(header)
    print("-" * 78)

    for name, m in results.items():
        accuracy = m["accuracy"]
        row = (
            f"  {name:<12}"
            f"{m['recompute_cost']:>8d}"
            f"{m['blocks_evicted']:>8d}"
            f"{accuracy:>7.1%}"
            f"{m['important_evictions']:>7d}"
        )
        if has_cb:
            row += (
                f"{m['avg_utilization']:>8.1%}"
                f"{m['pct_high_pressure']:>8.1%}"
                f"{m.get('sequences_completed', 0):>8d}"
            )
        print(row)


def aggregate_multi_seed(runner, seeds, **kwargs):
    """Run a workload across multiple seeds and aggregate results."""
    all_results = {}
    for seed in seeds:
        results = runner(seed=seed, **kwargs)
        for policy, metrics in results.items():
            if policy not in all_results:
                all_results[policy] = []
            all_results[policy].append(metrics)

    # Aggregate: sum numeric fields, average rates
    aggregated = {}
    for policy, runs in all_results.items():
        agg = {}
        for key in runs[0]:
            vals = [r[key] for r in runs]
            if isinstance(vals[0], (int, float)):
                agg[key] = sum(vals) / len(vals)
                # Keep ints as ints for counts
                if isinstance(vals[0], int):
                    agg[key] = round(agg[key])
            elif isinstance(vals[0], dict):
                # Average dicts (block_type_distribution)
                agg[key] = {}
                for k in vals[0]:
                    agg[key][k] = sum(v[k] for v in vals) / len(vals)
            else:
                agg[key] = vals[0]  # strings etc
        aggregated[policy] = agg
    return aggregated


# =============================================================================
# SCENARIO 4 — Staggered Arrival (Continuous Batching)
# =============================================================================

def scenario_4_staggered_arrival():
    """
    Sequences arrive and depart asynchronously. Memory pressure fluctuates.
    Tests eviction under realistic serving dynamics.
    """
    print("\n" + "#" * 78)
    print("# SCENARIO 4 -- Staggered Arrival (Continuous Batching)")
    print("#" * 78)

    # 4a: Moderate load — steady state
    t0 = time.perf_counter()
    results = aggregate_multi_seed(
        compare_continuous_batching, SEEDS,
        max_blocks=128, block_size=BLOCK_SIZE,
        total_steps=400, arrival_rate=0.12, completion_rate=0.06,
        max_concurrent=8,
    )
    elapsed = time.perf_counter() - t0
    print_table(f"4a: Moderate load, 128 blocks, 8 max concurrent  ({elapsed:.1f}s, {len(SEEDS)} seeds)", results)

    # 4b: High load — bursty arrivals, slow completions
    t0 = time.perf_counter()
    results = aggregate_multi_seed(
        compare_continuous_batching, SEEDS,
        max_blocks=128, block_size=BLOCK_SIZE,
        total_steps=400, arrival_rate=0.25, completion_rate=0.04,
        max_concurrent=12,
    )
    elapsed = time.perf_counter() - t0
    print_table(f"4b: High load, 128 blocks, 12 max concurrent  ({elapsed:.1f}s, {len(SEEDS)} seeds)", results)

    # 4c: Extreme — tiny cache, many sequences
    t0 = time.perf_counter()
    results = aggregate_multi_seed(
        compare_continuous_batching, SEEDS,
        max_blocks=64, block_size=BLOCK_SIZE,
        total_steps=300, arrival_rate=0.20, completion_rate=0.05,
        max_concurrent=16,
    )
    elapsed = time.perf_counter() - t0
    print_table(f"4c: Extreme, 64 blocks, 16 max concurrent  ({elapsed:.1f}s, {len(SEEDS)} seeds)", results)


# =============================================================================
# SCENARIO 5 — Variable Sequence Lengths
# =============================================================================

def scenario_5_variable_lengths():
    """
    Context lengths sampled from realistic distribution.
    Tests if policy handles mixed-size sequences fairly.
    """
    print("\n" + "#" * 78)
    print("# SCENARIO 5 -- Variable Sequence Lengths")
    print("#" * 78)

    # 5a: Bimodal — mostly short + some very long
    bimodal = [
        (0.70, 128, 512),
        (0.10, 1024, 2048),
        (0.15, 8192, 16384),
        (0.05, 16384, 32768),
    ]
    t0 = time.perf_counter()
    results = aggregate_multi_seed(
        compare_continuous_batching, SEEDS,
        max_blocks=256, block_size=BLOCK_SIZE,
        total_steps=400, arrival_rate=0.15, completion_rate=0.06,
        max_concurrent=10, length_distribution=bimodal,
    )
    elapsed = time.perf_counter() - t0
    print_table(f"5a: Bimodal lengths, 256 blocks  ({elapsed:.1f}s, {len(SEEDS)} seeds)", results)

    # 5b: Heavy long — code generation / document QA
    heavy_long = [
        (0.10, 256, 512),
        (0.20, 2048, 4096),
        (0.40, 8192, 16384),
        (0.30, 16384, 32768),
    ]
    t0 = time.perf_counter()
    results = aggregate_multi_seed(
        compare_continuous_batching, SEEDS,
        max_blocks=512, block_size=BLOCK_SIZE,
        total_steps=300, arrival_rate=0.10, completion_rate=0.05,
        max_concurrent=6, length_distribution=heavy_long,
    )
    elapsed = time.perf_counter() - t0
    print_table(f"5b: Heavy-long lengths, 512 blocks  ({elapsed:.1f}s, {len(SEEDS)} seeds)", results)


# =============================================================================
# SCENARIO 6 — Mixed Attention Patterns (Continuous Batching)
# =============================================================================

def scenario_6_mixed_attention():
    """
    Each sequence gets a random attention pattern (recent-heavy, entity-focused,
    distributed, mixed). Tests robustness when attention is unpredictable.
    """
    print("\n" + "#" * 78)
    print("# SCENARIO 6 -- Mixed Attention Patterns (Continuous Batching)")
    print("#" * 78)

    # Already built into run_continuous_batching — each sequence gets
    # a random pattern from ATTENTION_PATTERNS. Just run at various scales.

    t0 = time.perf_counter()
    results = aggregate_multi_seed(
        compare_continuous_batching, SEEDS,
        max_blocks=128, block_size=BLOCK_SIZE,
        total_steps=400, arrival_rate=0.15, completion_rate=0.05,
        max_concurrent=10,
    )
    elapsed = time.perf_counter() - t0
    print_table(f"6a: Mixed patterns, 128 blocks, 10 concurrent  ({elapsed:.1f}s, {len(SEEDS)} seeds)", results)


# =============================================================================
# SCENARIO 7 — Memory Pressure Phases
# =============================================================================

def scenario_7_pressure_phases():
    """
    Simulate pressure transitions: low → high → low.
    Burst of arrivals pushes to 90%+ utilization, then drains.
    """
    print("\n" + "#" * 78)
    print("# SCENARIO 7 -- Memory Pressure Phases")
    print("#" * 78)

    # Phase 1: low pressure with slow arrivals
    # Phase 2: burst — high arrival rate saturates cache
    # Phase 3: drain — high completion rate
    # We simulate this by using high arrival_rate + low completion_rate
    # on a tight cache, which naturally creates pressure cycles.

    t0 = time.perf_counter()
    results = aggregate_multi_seed(
        compare_continuous_batching, SEEDS,
        max_blocks=96, block_size=BLOCK_SIZE,
        total_steps=500, arrival_rate=0.20, completion_rate=0.03,
        max_concurrent=14,
        length_distribution=[
            (0.40, 512, 2048),
            (0.30, 2048, 8192),
            (0.20, 8192, 16384),
            (0.10, 16384, 32768),
        ],
    )
    elapsed = time.perf_counter() - t0
    print_table(f"7: Pressure phases, 96 blocks, 14 max  ({elapsed:.1f}s, {len(SEEDS)} seeds)", results)


# =============================================================================
# Legacy Scenarios (kept for regression)
# =============================================================================

def scenario_1_long_context():
    print("\n" + "#" * 78)
    print("# SCENARIO 1 -- Long Context Pressure (legacy)")
    print("#" * 78)

    for label, ctx_len, max_blocks, decode_steps in [
        ("8K ctx, 256 blk",  8192, 256, 128),
        ("16K ctx, 256 blk", 16384, 256, 128),
    ]:
        t0 = time.perf_counter()
        results = compare_policies(
            max_blocks=max_blocks, block_size=BLOCK_SIZE,
            num_sequences=4, context_length=ctx_len,
            decode_steps=decode_steps, seed=SEEDS[0],
        )
        elapsed = time.perf_counter() - t0
        print_table(f"1: {label}  ({elapsed:.1f}s)", results)


def scenario_2_static_contention():
    print("\n" + "#" * 78)
    print("# SCENARIO 2 -- Static Contention (legacy)")
    print("#" * 78)

    mixed_seqs = [
        (0, 512), (1, 1024), (2, 2048), (3, 4096),
        (4, 512), (5, 1024), (6, 2048), (7, 8192),
    ]
    t0 = time.perf_counter()
    results = compare_policies(
        max_blocks=256, block_size=BLOCK_SIZE,
        sequences=mixed_seqs, decode_steps=128, seed=SEEDS[0],
    )
    elapsed = time.perf_counter() - t0
    print_table(f"2: 8 mixed seqs, 256 blocks  ({elapsed:.1f}s)", results)


def scenario_3_attention_patterns():
    print("\n" + "#" * 78)
    print("# SCENARIO 3 -- Attention Patterns (legacy)")
    print("#" * 78)

    for label, attn_fn in [
        ("Sink+Recent", sink_and_recent_attention),
        ("Entity-focused", entity_focused_attention),
        ("Uniform", uniform_attention),
    ]:
        t0 = time.perf_counter()
        results = compare_policies(
            max_blocks=128, block_size=BLOCK_SIZE,
            num_sequences=4, context_length=4096,
            decode_steps=128, seed=SEEDS[0], attention_fn=attn_fn,
        )
        elapsed = time.perf_counter() - t0
        print_table(f"3: {label}  ({elapsed:.1f}s)", results)


# =============================================================================
# Main
# =============================================================================

def main():
    print("KV Cache Eviction Policy Stress Test")
    print(f"Block size: {BLOCK_SIZE}, Seeds: {SEEDS}")
    total_start = time.perf_counter()

    # New continuous-batching scenarios
    scenario_4_staggered_arrival()
    scenario_5_variable_lengths()
    scenario_6_mixed_attention()
    scenario_7_pressure_phases()

    # Legacy static scenarios (faster, kept for regression)
    scenario_1_long_context()
    scenario_2_static_contention()
    scenario_3_attention_patterns()

    total_elapsed = time.perf_counter() - total_start
    print(f"\n{'=' * 78}")
    print(f"  Total elapsed: {total_elapsed:.1f}s")
    print(f"{'=' * 78}")


if __name__ == "__main__":
    main()
