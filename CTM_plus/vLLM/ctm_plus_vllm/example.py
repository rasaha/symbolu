#!/usr/bin/env python3
"""
Example: CTM+ Block Manager for vLLM

Demonstrates how to use CTM+ for KV cache block management
in LLM inference scenarios.
"""

import random
import time
from typing import List, Tuple

from ctm_plus_vllm import CTMBlockSpaceManager, CTMvLLMConfig


def simulate_llm_inference(
    manager: CTMBlockSpaceManager,
    num_sequences: int = 100,
    avg_sequence_length: int = 50,
    block_size: int = 16,
) -> dict:
    """
    Simulate LLM inference workload.

    Simulates multiple sequences being processed with:
    - Prefill phase (initial prompt)
    - Decode phase (token generation)
    - Sequence completion
    """
    active_sequences: dict = {}  # seq_id -> (num_blocks, current_step)
    completed = 0
    total_accesses = 0

    for step in range(num_sequences * avg_sequence_length):
        # Start new sequences
        if len(active_sequences) < 32 and random.random() < 0.1:
            seq_id = step
            seq_length = max(10, int(random.gauss(avg_sequence_length, 20)))
            num_blocks = (seq_length + block_size - 1) // block_size

            # Allocate blocks (prefill)
            allocated = manager.allocate(seq_id, num_blocks)
            if allocated:
                active_sequences[seq_id] = (len(allocated), 0)

        # Process active sequences (decode)
        to_remove = []
        for seq_id, (num_blocks, current_step) in active_sequences.items():
            # Access recent blocks (typical decode pattern)
            recent_blocks = list(range(max(0, num_blocks - 4), num_blocks))
            manager.access(seq_id, recent_blocks)
            total_accesses += len(recent_blocks)

            # Advance sequence
            new_step = current_step + 1
            active_sequences[seq_id] = (num_blocks, new_step)

            # Complete sequence
            if new_step >= avg_sequence_length or random.random() < 0.02:
                manager.free(seq_id)
                to_remove.append(seq_id)
                completed += 1

        for seq_id in to_remove:
            del active_sequences[seq_id]

    # Cleanup remaining
    for seq_id in list(active_sequences.keys()):
        manager.free(seq_id)
        completed += 1

    stats = manager.get_stats()
    stats["completed_sequences"] = completed
    stats["total_accesses"] = total_accesses
    return stats


def simulate_batch_inference(
    manager: CTMBlockSpaceManager,
    batch_size: int = 32,
    num_batches: int = 50,
    sequence_length: int = 64,
    block_size: int = 16,
) -> dict:
    """
    Simulate batch inference workload.

    Processes fixed-size batches of sequences together.
    """
    total_accesses = 0
    completed = 0

    for batch_idx in range(num_batches):
        seq_ids = list(range(batch_idx * batch_size, (batch_idx + 1) * batch_size))
        num_blocks = (sequence_length + block_size - 1) // block_size

        # Allocate for entire batch
        for seq_id in seq_ids:
            manager.allocate(seq_id, num_blocks)

        # Process batch (decode steps)
        for step in range(sequence_length // block_size):
            for seq_id in seq_ids:
                manager.access(seq_id, [step])
                total_accesses += 1

        # Free batch
        for seq_id in seq_ids:
            manager.free(seq_id)
            completed += 1

    stats = manager.get_stats()
    stats["completed_sequences"] = completed
    stats["total_accesses"] = total_accesses
    return stats


def compare_configs():
    """Compare different CTM+ configurations."""
    configs = [
        ("Default", CTMvLLMConfig()),
        ("LLM Inference", CTMvLLMConfig.for_llm_inference()),
        ("Batch Inference", CTMvLLMConfig.for_batch_inference()),
        ("Streaming", CTMvLLMConfig.for_streaming()),
    ]

    print("=" * 70)
    print("CTM+ Configuration Comparison for vLLM")
    print("=" * 70)

    for name, config in configs:
        manager = CTMBlockSpaceManager(
            block_size=16,
            num_gpu_blocks=500,
            num_cpu_blocks=5000,
            ctm_config=config,
        )

        start = time.time()
        stats = simulate_llm_inference(manager, num_sequences=200)
        elapsed = time.time() - start

        print(f"\n{name}:")
        print(f"  GPU Hit Rate: {stats['gpu_hit_rate']:.2%}")
        print(f"  Evictions: {stats['num_evictions']}")
        print(f"  Promotions: {stats['num_promotions']}")
        print(f"  Smart Selections: {stats['smart_selections']}")
        print(f"  Adaptive p: {stats['adaptive_p']:.3f}")
        print(f"  Time: {elapsed:.2f}s")


def main():
    print("CTM+ Block Manager for vLLM - Example")
    print("=" * 50)

    # Create block manager with CTM+
    config = CTMvLLMConfig.for_llm_inference()
    manager = CTMBlockSpaceManager(
        block_size=16,
        num_gpu_blocks=1000,
        num_cpu_blocks=10000,
        ctm_config=config,
    )

    print(f"\nBlock Manager Configuration:")
    print(f"  GPU Blocks: {manager.num_gpu_blocks}")
    print(f"  CPU Blocks: {manager.num_cpu_blocks}")
    print(f"  Block Size: {manager.block_size} tokens")

    # Simulate workload
    print("\n" + "-" * 50)
    print("Running LLM inference simulation...")
    start = time.time()
    stats = simulate_llm_inference(manager, num_sequences=500)
    elapsed = time.time() - start

    print(f"\nResults:")
    print(f"  Completed Sequences: {stats['completed_sequences']}")
    print(f"  Total Accesses: {stats['total_accesses']}")
    print(f"  GPU Hit Rate: {stats['gpu_hit_rate']:.2%}")
    print(f"  CPU Hit Rate: {stats['cpu_hits'] / stats['total_accesses']:.2%}")
    print(f"  Evictions: {stats['num_evictions']}")
    print(f"  Promotions: {stats['num_promotions']}")
    print(f"  Smart Selections: {stats['smart_selections']}")
    print(f"  Adaptive p: {stats['adaptive_p']:.3f}")
    print(f"  Simulation Time: {elapsed:.2f}s")

    # Compare configurations
    print("\n")
    compare_configs()


if __name__ == "__main__":
    main()
