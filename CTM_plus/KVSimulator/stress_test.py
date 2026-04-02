#!/usr/bin/env python3
"""
Stress-test scenarios for KV cache eviction policies.

Validates whether KVPolicy advantages hold under realistic, high-pressure
conditions compared to LRU, FIFO, and Random baselines.

Usage:
    python -m CTM_plus.KVSimulator.stress_test
"""

import sys
import time

from CTM_plus.KVSimulator.kv_simulator.buffer_pool import (
    compare_policies,
    entity_focused_attention,
    mixed_multihead_attention,
    sink_and_recent_attention,
    uniform_attention,
)

SEED = 42
BLOCK_SIZE = 16


def print_table(title, results, extra_fields=None):
    """Print a formatted results table."""
    print(f"\n{'=' * 70}")
    print(f"  {title}")
    print(f"{'=' * 70}")

    fields = [
        ("Policy", 12, "s"),
        ("Recompute", 10, "d"),
        ("Evicted", 8, "d"),
        ("Accuracy", 9, ".2%"),
        ("Imp.Evict", 10, "d"),
    ]
    if extra_fields:
        fields.extend(extra_fields)

    header = "".join(f"{'':>2}{name:<{w}}" for name, w, _ in fields)
    print(header)
    print("-" * 70)

    for name, m in results.items():
        evictions = m["blocks_evicted"]
        important = m["important_evictions"]
        accuracy = 1.0 - (important / max(1, evictions))
        row = f"  {name:<12}{m['recompute_cost']:<10d}{evictions:<8d}{accuracy:<9.2%}{important:<10d}"
        if extra_fields:
            for fname, fw, ffmt in extra_fields:
                val = m.get(fname.lower().replace(".", "_"), "")
                row += f"{val:<{fw}}"
        print(row)


def scenario_1_long_context():
    """
    SCENARIO 1 -- Long Context Pressure

    4 sequences, context 8K -> 32K tokens, tight memory budget.
    Tests if policy protects important blocks as context grows.
    """
    print("\n" + "#" * 70)
    print("# SCENARIO 1 -- Long Context Pressure")
    print("#" * 70)

    configs = [
        ("8K context, 256 blocks",  8192, 256, 128),
        ("16K context, 256 blocks", 16384, 256, 128),
        ("32K context, 512 blocks", 32768, 512, 128),
    ]

    for label, ctx_len, max_blocks, decode_steps in configs:
        t0 = time.perf_counter()
        results = compare_policies(
            max_blocks=max_blocks,
            block_size=BLOCK_SIZE,
            num_sequences=4,
            context_length=ctx_len,
            decode_steps=decode_steps,
            seed=SEED,
        )
        elapsed = time.perf_counter() - t0
        print_table(f"Scenario 1: {label}  ({elapsed:.1f}s)", results)


def scenario_2_multi_sequence_contention():
    """
    SCENARIO 2 -- Multi-Sequence Contention

    8-16 concurrent sequences with staggered arrival and mixed context lengths.
    Tests eviction fairness under scheduling pressure.
    """
    print("\n" + "#" * 70)
    print("# SCENARIO 2 -- Multi-Sequence Contention")
    print("#" * 70)

    # 8 sequences, mixed context: 512, 1K, 2K, 4K, 512, 1K, 2K, 8K
    mixed_8_seqs = [
        (0, 512), (1, 1024), (2, 2048), (3, 4096),
        (4, 512), (5, 1024), (6, 2048), (7, 8192),
    ]

    t0 = time.perf_counter()
    results = compare_policies(
        max_blocks=256,
        block_size=BLOCK_SIZE,
        sequences=mixed_8_seqs,
        decode_steps=128,
        seed=SEED,
    )
    elapsed = time.perf_counter() - t0
    print_table(f"Scenario 2a: 8 mixed sequences, 256 blocks  ({elapsed:.1f}s)", results)

    # 16 sequences, all 2K, very tight memory (128 blocks)
    many_seqs = [(i, 2048) for i in range(16)]

    t0 = time.perf_counter()
    results = compare_policies(
        max_blocks=128,
        block_size=BLOCK_SIZE,
        sequences=many_seqs,
        decode_steps=64,
        seed=SEED,
    )
    elapsed = time.perf_counter() - t0
    print_table(f"Scenario 2b: 16 sequences x 2K, 128 blocks  ({elapsed:.1f}s)", results)


def scenario_3_attention_patterns():
    """
    SCENARIO 3 -- Attention Pattern Variation

    Same workload under different attention distributions:
    1. Entity-focused: few tokens get high attention
    2. Uniform/diffuse: attention spread evenly
    3. Mixed multi-head: combination of all patterns
    4. Sink+recent (baseline): default pattern

    Tests if KVPolicy still outperforms when attention is less predictable.
    """
    print("\n" + "#" * 70)
    print("# SCENARIO 3 -- Attention Pattern Variation")
    print("#" * 70)

    patterns = [
        ("Sink+Recent (baseline)", sink_and_recent_attention),
        ("Entity-focused",         entity_focused_attention),
        ("Uniform / diffuse",      uniform_attention),
        ("Mixed multi-head",       mixed_multihead_attention),
    ]

    # Moderate pressure: 4 sequences x 4K, 128 blocks
    for label, attn_fn in patterns:
        t0 = time.perf_counter()
        results = compare_policies(
            max_blocks=128,
            block_size=BLOCK_SIZE,
            num_sequences=4,
            context_length=4096,
            decode_steps=128,
            seed=SEED,
            attention_fn=attn_fn,
        )
        elapsed = time.perf_counter() - t0
        print_table(f"Scenario 3: {label}  ({elapsed:.1f}s)", results)


def main():
    print("KV Cache Eviction Policy Stress Test")
    print(f"Block size: {BLOCK_SIZE}, Seed: {SEED}")

    total_start = time.perf_counter()

    scenario_1_long_context()
    scenario_2_multi_sequence_contention()
    scenario_3_attention_patterns()

    total_elapsed = time.perf_counter() - total_start
    print(f"\n{'=' * 70}")
    print(f"  Total elapsed: {total_elapsed:.1f}s")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    main()
