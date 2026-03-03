"""
Hierarchical Phase-Quad (HP-Quad) Benchmarks (V10.7)

Tests multi-timescale processing inspired by HM-RNN:
    1. Throughput comparison (standard vs hierarchical)
    2. Boundary detection quality
    3. Memory efficiency
    4. Long-range dependency handling
    5. Ablation studies

CLI Usage::

    python train_hard_probes.py --test-hp-quad
    python train_hard_probes.py --test-hp-quad --hp-num-levels 3 --hp-boundary-ablation
"""

import time
import torch
import torch.nn as nn
from typing import Dict, Optional

from ..imports import HP_QUAD_AVAILABLE
if HP_QUAD_AVAILABLE:
    from symbolu.hp_quad import (
        HPQuadBlock, HPQuadConfig, HPQuadBenchmark,
        HierarchicalPhaseIntegrator, HierarchicalQuadProposal,
        BoundaryDetector, create_hp_quad,
    )

# =============================================================================
# V10.7: HIERARCHICAL PHASE-QUAD (HP-QUAD) BENCHMARKS
# =============================================================================
# Tests multi-timescale processing based on HM-RNN (Chung et al., 2016).


def run_hp_quad_benchmarks(
    args,
    config,
    device: str,
) -> Dict[str, any]:
    """
    Run comprehensive HP-Quad benchmarks.

    Tests:
    1. Throughput comparison (standard vs hierarchical)
    2. Boundary detection quality
    3. Memory efficiency
    4. Long-range dependency handling
    5. Ablation studies (boundary thresholds)

    Args:
        args: CLI arguments
        config: Config object
        device: torch device

    Returns:
        Dictionary with benchmark results
    """
    print("\n" + "=" * 70)
    print("V10.7: HIERARCHICAL PHASE-QUAD (HP-QUAD) BENCHMARKS")
    print("=" * 70)

    if not HP_QUAD_AVAILABLE:
        print("\n  ERROR: HP-Quad module not available.")
        print("  Ensure symbolu.hp_quad is importable.")
        return {"error": "Module not available"}

    results = {
        "throughput": {},
        "boundary": {},
        "memory": {},
        "long_range": {},
        "ablation": {},
    }

    d_model = config.d_model

    # Parse configuration from args
    d_phase_levels = tuple(map(int, args.hp_d_phase_levels.split(",")))
    chunk_sizes = tuple(map(int, args.hp_chunk_sizes.split(",")))
    num_levels = min(args.hp_num_levels, len(d_phase_levels), len(chunk_sizes))

    print(f"\n  Configuration:")
    print(f"    d_model: {d_model}")
    print(f"    num_levels: {num_levels}")
    print(f"    d_phase_levels: {d_phase_levels[:num_levels]}")
    print(f"    chunk_sizes: {chunk_sizes[:num_levels]}")
    print(f"    boundary_threshold: {args.hp_boundary_threshold}")
    print(f"    target_boundary_rate: {args.hp_target_boundary_rate}")
    print(f"    device: {device}")

    # -------------------------------------------------------------------------
    # TEST 1: Throughput Comparison
    # -------------------------------------------------------------------------
    print("\n--- TEST 1: Throughput Comparison ---")
    print("  Comparing standard single-level vs hierarchical HP-Quad.")

    # Create standard single-level model (baseline)
    standard_model = HPQuadBlock(
        d_model=d_model,
        d_phase_levels=(256,),
        num_levels=1,
        chunk_sizes=(1,),
        boundary_threshold=args.hp_boundary_threshold,
    ).to(device)

    # Create hierarchical HP-Quad
    hp_model = HPQuadBlock(
        d_model=d_model,
        d_phase_levels=d_phase_levels[:num_levels],
        num_levels=num_levels,
        chunk_sizes=chunk_sizes[:num_levels],
        boundary_threshold=args.hp_boundary_threshold,
    ).to(device)

    # Parameter counts
    standard_params = sum(p.numel() for p in standard_model.parameters())
    hp_params = sum(p.numel() for p in hp_model.parameters())

    print(f"\n  Parameter counts:")
    print(f"    Standard (1-level): {standard_params:,}")
    print(f"    HP-Quad ({num_levels}-level): {hp_params:,} ({hp_params/standard_params:.1f}x)")

    results["params"] = {
        "standard": standard_params,
        "hp_quad": hp_params,
        "ratio": hp_params / standard_params,
    }

    # Throughput benchmark
    import time

    B, N = 32, 512
    x = torch.randn(B, N, d_model, device=device)
    num_iters = 30
    warmup = 10

    # Standard throughput
    standard_model.eval()
    with torch.no_grad():
        for _ in range(warmup):
            _, _, _ = standard_model(x)
        if device == "cuda":
            torch.cuda.synchronize()

        start = time.perf_counter()
        for _ in range(num_iters):
            _, _, _ = standard_model(x)
        if device == "cuda":
            torch.cuda.synchronize()
        standard_time = time.perf_counter() - start

    # HP-Quad throughput
    hp_model.eval()
    with torch.no_grad():
        for _ in range(warmup):
            _, _, _ = hp_model(x)
        if device == "cuda":
            torch.cuda.synchronize()

        start = time.perf_counter()
        for _ in range(num_iters):
            _, _, _ = hp_model(x)
        if device == "cuda":
            torch.cuda.synchronize()
        hp_time = time.perf_counter() - start

    total_tokens = B * N * num_iters
    standard_throughput = total_tokens / standard_time
    hp_throughput = total_tokens / hp_time

    print(f"\n  Throughput (tokens/sec):")
    print(f"    Standard: {standard_throughput:,.0f}")
    print(f"    HP-Quad:  {hp_throughput:,.0f}")
    print(f"    Ratio:    {hp_throughput/standard_throughput:.2f}x")

    results["throughput"] = {
        "standard_tokens_per_sec": standard_throughput,
        "hp_tokens_per_sec": hp_throughput,
        "ratio": hp_throughput / standard_throughput,
        "standard_time_sec": standard_time,
        "hp_time_sec": hp_time,
    }

    # -------------------------------------------------------------------------
    # TEST 2: Boundary Detection Quality
    # -------------------------------------------------------------------------
    print("\n--- TEST 2: Boundary Detection Quality ---")
    print("  Analyzing boundary detection behavior.")

    hp_model.eval()
    x_boundary = torch.randn(16, 256, d_model, device=device)

    with torch.no_grad():
        _, phase_states, aux = hp_model(x_boundary)

    boundary_rate = aux.get("boundary_rate", torch.tensor(0.0)).item()

    print(f"\n  Boundary statistics:")
    print(f"    Overall boundary rate: {boundary_rate:.3f}")
    print(f"    Target rate:           {args.hp_target_boundary_rate:.3f}")
    print(f"    Within 10% of target:  {abs(boundary_rate - args.hp_target_boundary_rate) < 0.1}")

    results["boundary"] = {
        "boundary_rate": boundary_rate,
        "target_rate": args.hp_target_boundary_rate,
        "within_target": abs(boundary_rate - args.hp_target_boundary_rate) < 0.1,
    }

    # Per-level boundary rates
    for i in range(num_levels - 1):
        key = f"boundary_rate_level_{i}"
        if key in aux:
            level_rate = aux[key].item()
            print(f"    Level {i}→{i+1} boundary rate: {level_rate:.3f}")
            results["boundary"][key] = level_rate

    # -------------------------------------------------------------------------
    # TEST 3: Memory Efficiency
    # -------------------------------------------------------------------------
    print("\n--- TEST 3: Memory Efficiency ---")

    if device == "cuda":
        torch.cuda.reset_peak_memory_stats()

        # Standard forward
        with torch.no_grad():
            _, _, _ = standard_model(x)
        standard_mem = torch.cuda.max_memory_allocated() / 1024**2

        torch.cuda.reset_peak_memory_stats()

        # HP-Quad forward
        with torch.no_grad():
            _, _, _ = hp_model(x)
        hp_mem = torch.cuda.max_memory_allocated() / 1024**2

        print(f"\n  Peak memory (MB):")
        print(f"    Standard: {standard_mem:.1f}")
        print(f"    HP-Quad:  {hp_mem:.1f}")
        print(f"    Overhead: {hp_mem/standard_mem:.2f}x")

        results["memory"] = {
            "standard_mb": standard_mem,
            "hp_mb": hp_mem,
            "overhead": hp_mem / standard_mem,
        }
    else:
        print("  (Memory benchmark requires CUDA)")
        results["memory"] = {"note": "Requires CUDA"}

    # -------------------------------------------------------------------------
    # TEST 4: Long-Range Dependency Handling
    # -------------------------------------------------------------------------
    print("\n--- TEST 4: Long-Range Dependency Handling ---")
    print("  Testing with varying sequence lengths.")

    for seq_len in [256, 512, 1024, 2048]:
        x_long = torch.randn(8, seq_len, d_model, device=device)

        try:
            with torch.no_grad():
                output, _, aux = hp_model(x_long)

            boundary_rate = aux.get("boundary_rate", torch.tensor(0.0)).item()
            print(f"    Seq len {seq_len}: boundary_rate={boundary_rate:.3f}, output_shape={output.shape}")

            results["long_range"][f"seq_{seq_len}"] = {
                "boundary_rate": boundary_rate,
                "success": True,
            }
        except RuntimeError as e:
            print(f"    Seq len {seq_len}: FAILED - {str(e)[:50]}")
            results["long_range"][f"seq_{seq_len}"] = {
                "success": False,
                "error": str(e)[:100],
            }

    # -------------------------------------------------------------------------
    # TEST 5: Ablation Study (optional)
    # -------------------------------------------------------------------------
    if args.hp_boundary_ablation:
        print("\n--- TEST 5: Boundary Threshold Ablation ---")
        print("  Testing different boundary thresholds.")

        ablation_results = {}
        original_threshold = hp_model.phase_integrator.boundary_detectors[0].threshold

        for threshold in [0.3, 0.5, 0.7]:
            # Update all boundary detectors
            for bd in hp_model.phase_integrator.boundary_detectors:
                bd.threshold = threshold

            with torch.no_grad():
                _, _, aux = hp_model(x_boundary)

            boundary_rate = aux.get("boundary_rate", torch.tensor(0.0)).item()
            print(f"    Threshold {threshold}: boundary_rate={boundary_rate:.3f}")

            ablation_results[f"threshold_{threshold}"] = {
                "boundary_rate": boundary_rate,
            }

        # Restore original threshold
        for bd in hp_model.phase_integrator.boundary_detectors:
            bd.threshold = original_threshold

        results["ablation"]["boundary_thresholds"] = ablation_results

        # Test different number of levels
        print("\n  Testing different hierarchy depths.")

        for test_levels in [1, 2, 3]:
            if test_levels > len(d_phase_levels):
                continue

            test_model = HPQuadBlock(
                d_model=d_model,
                d_phase_levels=d_phase_levels[:test_levels],
                num_levels=test_levels,
                chunk_sizes=chunk_sizes[:test_levels],
            ).to(device)

            test_params = sum(p.numel() for p in test_model.parameters())

            with torch.no_grad():
                _, _, aux = test_model(x_boundary)

            boundary_rate = aux.get("boundary_rate", torch.tensor(0.0)).item() if test_levels > 1 else 0.0
            print(f"    {test_levels} levels: params={test_params:,}, boundary_rate={boundary_rate:.3f}")

            ablation_results[f"levels_{test_levels}"] = {
                "params": test_params,
                "boundary_rate": boundary_rate,
            }

        results["ablation"]["hierarchy_depth"] = ablation_results

    # -------------------------------------------------------------------------
    # Summary
    # -------------------------------------------------------------------------
    print("\n" + "=" * 70)
    print("HP-QUAD BENCHMARK SUMMARY")
    print("=" * 70)

    print(f"""
  Throughput:
    - Standard (1-level): {results['throughput']['standard_tokens_per_sec']:,.0f} tokens/sec
    - HP-Quad ({num_levels}-level): {results['throughput']['hp_tokens_per_sec']:,.0f} tokens/sec
    - Performance ratio: {results['throughput']['ratio']:.2f}x

  Parameters:
    - Standard: {results['params']['standard']:,}
    - HP-Quad: {results['params']['hp_quad']:,} ({results['params']['ratio']:.1f}x)

  Boundary Detection:
    - Actual rate: {results['boundary']['boundary_rate']:.3f}
    - Target rate: {results['boundary']['target_rate']:.3f}
    - Within target: {results['boundary']['within_target']}

  Recommendation:
    HP-Quad adds multi-timescale processing with learned boundary detection.
    Best for tasks requiring:
      - Long-range dependencies (document understanding)
      - Semantic chunking (hierarchical structure)
      - Adaptive compute (more processing at transitions)
""")

    return results


def run_hp_quad_benchmark_integration(args, config):
    """
    Integration entry point for HP-Quad benchmarks.

    Called from main() when --test-hp-quad is specified.
    """
    print("\n" + "=" * 70)
    print("HP-QUAD BENCHMARK: Integration Mode")
    print("=" * 70)

    results = run_hp_quad_benchmarks(args, config, config.device)

    if "error" in results:
        print(f"\nBenchmark failed: {results['error']}")
        return

    # Print CLI usage
    print("\n" + "-" * 70)
    print("CLI USAGE:")
    print("-" * 70)
    print("""
  # Run HP-Quad benchmarks
  python train_hard_probes.py --test-hp-quad

  # Custom hierarchy configuration
  python train_hard_probes.py --test-hp-quad --hp-num-levels 3 \\
      --hp-d-phase-levels 128,256,512 --hp-chunk-sizes 1,8,64

  # With boundary ablation
  python train_hard_probes.py --test-hp-quad --hp-boundary-ablation

  # Custom boundary threshold
  python train_hard_probes.py --test-hp-quad --hp-boundary-threshold 0.3 \\
      --hp-target-boundary-rate 0.2

  # Full benchmark suite
  python train_hard_probes.py --test-hp-quad --hp-boundary-ablation \\
      --hp-num-levels 3 --hp-d-phase-levels 128,256,512
""")

    return results


# =============================================================================
# V10.8: RLM-PHASE-QUAD INTEGRATION BENCHMARKS
# =============================================================================
