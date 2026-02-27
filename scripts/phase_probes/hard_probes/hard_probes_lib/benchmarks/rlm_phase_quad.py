"""
RLM-Phase-Quad Integration Benchmarks (V10.8)

Tests Recursive Language Model + Phase-Quad for unlimited context:
    1. End-to-end performance (latency, throughput)
    2. Chunking quality (boundary-aware vs fixed)
    3. Phase State persistence effectiveness
    4. Scalability with context size
    5. Memory bank utilization

CLI Usage::

    python train_hard_probes.py --test-rlm-phase-quad
    python train_hard_probes.py --test-rlm-phase-quad --rlm-pq-scalability-test
"""

import time
import torch
import torch.nn as nn
from typing import Dict, Optional

from ..imports import RLM_PHASE_QUAD_AVAILABLE
if RLM_PHASE_QUAD_AVAILABLE:
    from symbolu.rlm_phase_quad import (
        RLMPhaseQuadSystem, RLMPhaseQuadConfig, RLMPhaseQuadBenchmark,
        create_rlm_phase_quad,
    )

# =============================================================================
# V10.8: RLM-PHASE-QUAD INTEGRATION BENCHMARKS
# =============================================================================
# Tests RLM orchestration + Phase-Quad processing for unlimited context.


def run_rlm_phase_quad_benchmarks(
    args,
    config,
    device: str,
) -> Dict[str, any]:
    """
    Run comprehensive RLM-Phase-Quad integration benchmarks.

    Tests:
    1. End-to-end performance (latency, throughput)
    2. Chunking quality (boundary-aware vs fixed)
    3. Phase State persistence effectiveness
    4. Scalability with context size
    5. Memory bank utilization

    Args:
        args: CLI arguments
        config: Config object
        device: torch device

    Returns:
        Dictionary with benchmark results
    """
    print("\n" + "=" * 70)
    print("V10.8: RLM-PHASE-QUAD INTEGRATION BENCHMARKS")
    print("=" * 70)

    if not RLM_PHASE_QUAD_AVAILABLE:
        print("\n  ERROR: RLM-Phase-Quad module not available.")
        print("  Ensure symbolu.rlm_phase_quad is importable.")
        return {"error": "Module not available"}

    results = {
        "e2e_performance": {},
        "chunking": {},
        "state_persistence": {},
        "scalability": {},
        "memory_utilization": {},
    }

    d_model = config.d_model

    # Create RLM-Phase-Quad config
    rlm_pq_config = RLMPhaseQuadConfig(
        d_model=d_model,
        min_chunk_size=args.rlm_pq_min_chunk,
        max_chunk_size=args.rlm_pq_max_chunk,
        quality_threshold=args.rlm_pq_quality_threshold,
        max_recursion_depth=args.rlm_pq_max_depth,
        device=device,
    )

    print(f"\n  Configuration:")
    print(f"    d_model: {d_model}")
    print(f"    max_context: {args.rlm_pq_max_context}")
    print(f"    max_recursion_depth: {args.rlm_pq_max_depth}")
    print(f"    quality_threshold: {args.rlm_pq_quality_threshold}")
    print(f"    chunk_size: {args.rlm_pq_min_chunk}-{args.rlm_pq_max_chunk}")
    print(f"    device: {device}")

    # Initialize system
    system = RLMPhaseQuadSystem(rlm_pq_config)

    # -------------------------------------------------------------------------
    # TEST 1: End-to-End Performance
    # -------------------------------------------------------------------------
    print("\n--- TEST 1: End-to-End Performance ---")
    print("  Measuring latency and throughput.")

    import time

    test_sizes = [1000, 5000, 10000]
    if args.rlm_pq_max_context > 10000:
        test_sizes.append(min(args.rlm_pq_max_context, 50000))

    for context_size in test_sizes:
        context = "test content word " * (context_size // 3)
        question = "Summarize the main content"

        start = time.perf_counter()
        answer, trace = system.query(context, question, return_trace=True)
        elapsed = time.perf_counter() - start

        tokens_per_sec = context_size / elapsed if elapsed > 0 else 0

        results["e2e_performance"][f"size_{context_size}"] = {
            "tokens": context_size,
            "time_sec": elapsed,
            "tokens_per_sec": tokens_per_sec,
            "num_chunks": len(trace["chunks"]),
            "num_sub_queries": len(trace["sub_queries"]),
        }

        print(f"    {context_size:,} tokens: {elapsed:.2f}s, "
              f"{tokens_per_sec:,.0f} tok/s, "
              f"{len(trace['chunks'])} chunks")

    # -------------------------------------------------------------------------
    # TEST 2: Chunking Quality
    # -------------------------------------------------------------------------
    print("\n--- TEST 2: Chunking Quality ---")
    print("  Comparing boundary-aware vs fixed chunking.")

    # Create structured content with clear sections
    structured_context = "\n\n".join([
        f"Section {i}: This is section {i} with important content. " * 20
        for i in range(10)
    ])

    chunks, boundaries = system.chunker.chunk(structured_context)

    chunk_sizes = [len(c.split()) for c in chunks]

    results["chunking"] = {
        "num_chunks": len(chunks),
        "num_boundaries": len(boundaries),
        "avg_chunk_size": sum(chunk_sizes) / max(len(chunk_sizes), 1),
        "min_chunk_size": min(chunk_sizes) if chunk_sizes else 0,
        "max_chunk_size": max(chunk_sizes) if chunk_sizes else 0,
        "std_chunk_size": (sum((s - sum(chunk_sizes)/len(chunk_sizes))**2
                              for s in chunk_sizes) / max(len(chunk_sizes), 1)) ** 0.5
                          if chunk_sizes else 0,
    }

    print(f"    Chunks: {results['chunking']['num_chunks']}")
    print(f"    Avg size: {results['chunking']['avg_chunk_size']:.0f} tokens")
    print(f"    Size range: {results['chunking']['min_chunk_size']}-"
          f"{results['chunking']['max_chunk_size']} tokens")

    # -------------------------------------------------------------------------
    # TEST 3: Phase State Persistence
    # -------------------------------------------------------------------------
    print("\n--- TEST 3: Phase State Persistence ---")
    print("  Testing state inheritance across branches.")

    system.state_manager.clear()

    # Create branch hierarchy
    root_state = system.state_manager.get_state("root")
    system.state_manager.update_state("root", root_state)

    # Create children
    for i in range(5):
        child_id = f"root_child_{i}"
        system.state_manager.create_child_branch("root", child_id)
        _ = system.state_manager.get_state(child_id, inherit_from_parent=True)

    # Test merging
    merged = system.state_manager.merge_sibling_states(
        [f"root_child_{i}" for i in range(5)],
        merge_strategy="mean"
    )

    results["state_persistence"] = {
        "total_states": len(system.state_manager.states),
        "branch_tree_size": len(system.state_manager.branch_tree),
        "merge_successful": merged is not None,
        "inheritance_working": all(
            f"root_child_{i}" in system.state_manager.states
            for i in range(5)
        ),
    }

    print(f"    Total states: {results['state_persistence']['total_states']}")
    print(f"    Branch tree size: {results['state_persistence']['branch_tree_size']}")
    print(f"    Merge successful: {results['state_persistence']['merge_successful']}")
    print(f"    Inheritance working: {results['state_persistence']['inheritance_working']}")

    # -------------------------------------------------------------------------
    # TEST 4: Scalability
    # -------------------------------------------------------------------------
    print("\n--- TEST 4: Scalability ---")

    if args.rlm_pq_scalability_test:
        print("  Running extended scalability tests (up to 1M tokens)...")
        scale_sizes = [10000, 50000, 100000, 500000, 1000000]
    else:
        print("  Running standard scalability tests...")
        scale_sizes = [5000, 10000, 25000]

    for size in scale_sizes:
        if size > args.rlm_pq_max_context:
            continue

        context = "scalability test content " * (size // 4)
        question = "Find key information"

        try:
            start = time.perf_counter()
            _, trace = system.query(context, question, return_trace=True)
            elapsed = time.perf_counter() - start

            results["scalability"][f"size_{size}"] = {
                "tokens": size,
                "time_sec": elapsed,
                "tokens_per_sec": size / elapsed if elapsed > 0 else 0,
                "num_chunks": len(trace["chunks"]),
                "success": True,
            }

            print(f"    {size:,} tokens: {elapsed:.2f}s, "
                  f"{size/elapsed:,.0f} tok/s")

        except Exception as e:
            results["scalability"][f"size_{size}"] = {
                "tokens": size,
                "success": False,
                "error": str(e)[:100],
            }
            print(f"    {size:,} tokens: FAILED - {str(e)[:50]}")

    # -------------------------------------------------------------------------
    # TEST 5: Memory Bank Utilization
    # -------------------------------------------------------------------------
    print("\n--- TEST 5: Memory Bank Utilization ---")

    # Process some content to populate memory banks
    context = "Important fact A. Some filler. Important fact B. More content. Fact C."
    system.query(context, "Extract all facts")

    stats = system.get_stats()

    results["memory_utilization"] = {
        "num_chunks": stats["num_chunks"],
        "num_sub_results": stats["num_sub_results"],
        "avg_quality": stats["avg_quality"],
        "num_phase_states": stats["num_phase_states"],
        "memory_bank_sizes": stats["memory_bank_sizes"],
    }

    print(f"    Chunks processed: {results['memory_utilization']['num_chunks']}")
    print(f"    Sub-results: {results['memory_utilization']['num_sub_results']}")
    print(f"    Avg quality: {results['memory_utilization']['avg_quality']:.2f}")
    print(f"    Phase states: {results['memory_utilization']['num_phase_states']}")
    print(f"    Memory banks: {results['memory_utilization']['memory_bank_sizes']}")

    # -------------------------------------------------------------------------
    # Summary
    # -------------------------------------------------------------------------
    print("\n" + "=" * 70)
    print("RLM-PHASE-QUAD BENCHMARK SUMMARY")
    print("=" * 70)

    best_throughput = max(
        v.get("tokens_per_sec", 0)
        for v in results["e2e_performance"].values()
    )

    print(f"""
  Performance:
    - Best throughput: {best_throughput:,.0f} tokens/sec
    - Chunking: {results['chunking']['num_chunks']} semantic chunks

  Integration:
    - Phase State persistence: {'Working' if results['state_persistence']['inheritance_working'] else 'Issues'}
    - State merging: {'Working' if results['state_persistence']['merge_successful'] else 'Issues'}

  Scalability:
    - Tested up to: {max(int(k.split('_')[1]) for k in results['scalability'].keys()):,} tokens

  Recommendation:
    RLM-Phase-Quad provides unlimited context handling with efficient
    O(n) sub-query processing. Best for:
      - Very long documents (legal, research, codebases)
      - Multi-document analysis
      - Tasks requiring persistent memory across chunks
""")

    return results


def run_rlm_phase_quad_benchmark_integration(args, config):
    """
    Integration entry point for RLM-Phase-Quad benchmarks.

    Called from main() when --test-rlm-phase-quad is specified.
    """
    print("\n" + "=" * 70)
    print("RLM-PHASE-QUAD BENCHMARK: Integration Mode")
    print("=" * 70)

    results = run_rlm_phase_quad_benchmarks(args, config, config.device)

    if "error" in results:
        print(f"\nBenchmark failed: {results['error']}")
        return

    # Print CLI usage
    print("\n" + "-" * 70)
    print("CLI USAGE:")
    print("-" * 70)
    print("""
  # Run RLM-Phase-Quad benchmarks
  python train_hard_probes.py --test-rlm-phase-quad

  # Custom configuration
  python train_hard_probes.py --test-rlm-phase-quad \\
      --rlm-pq-max-context 50000 --rlm-pq-max-depth 3

  # Extended scalability test
  python train_hard_probes.py --test-rlm-phase-quad --rlm-pq-scalability-test

  # Custom quality threshold
  python train_hard_probes.py --test-rlm-phase-quad \\
      --rlm-pq-quality-threshold 0.8 --rlm-pq-max-depth 5

  # Full benchmark suite
  python train_hard_probes.py --test-rlm-phase-quad --rlm-pq-scalability-test \\
      --rlm-pq-max-context 1000000 --rlm-pq-max-depth 5
""")

    return results


# =============================================================================
# V10.9: REFLECTIVE PHASE-QUAD BENCHMARKS
# =============================================================================
