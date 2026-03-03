"""
Reflective Phase-Quad Benchmarks (V10.9)

Tests self-reflective latent-space revision with neural critic:
    1. Critic performance (quality estimation)
    2. Decision gate behavior (threshold calibration)
    3. Revision encoder effectiveness
    4. Full block with revision loop
    5. Reflective vs Single-Pass comparison
    6. Quality trajectory analysis

CLI Usage::

    python train_hard_probes.py --test-reflective-phase-quad
    python train_hard_probes.py --test-reflective-phase-quad --rpq-ablation
"""

import time
import torch
import torch.nn as nn
from typing import Dict, Optional

from ..imports import REFLECTIVE_PHASE_QUAD_AVAILABLE
if REFLECTIVE_PHASE_QUAD_AVAILABLE:
    from symbolu.reflective_phase_quad import (
        ReflectivePhaseQuadBlock, ReflectivePhaseQuadModel,
        ReflectivePhaseQuadConfig, ReflectivePhaseQuadBenchmark,
        create_reflective_phase_quad, create_reflective_model,
    )

# =============================================================================
# V10.9: REFLECTIVE PHASE-QUAD BENCHMARKS
# =============================================================================
# Tests self-reflective latent-space revision with neural critic.


def run_reflective_phase_quad_benchmarks(
    args,
    config,
    device: str,
) -> Dict[str, any]:
    """
    Run comprehensive Reflective Phase-Quad benchmarks.

    Tests:
    1. Critic performance (quality estimation accuracy)
    2. Decision gate behavior (threshold calibration)
    3. Revision encoder effectiveness
    4. Full block with revision loop
    5. Comparison: Reflective vs Single-Pass
    6. Quality trajectory analysis

    Args:
        args: CLI arguments
        config: Config object
        device: torch device

    Returns:
        Dictionary with benchmark results
    """
    print("\n" + "=" * 70)
    print("V10.9: REFLECTIVE PHASE-QUAD BENCHMARKS")
    print("=" * 70)

    if not REFLECTIVE_PHASE_QUAD_AVAILABLE:
        print("\n  ERROR: Reflective Phase-Quad module not available.")
        print("  Ensure symbolu.reflective_phase_quad is importable.")
        return {"error": "Module not available"}

    results = {
        "critic_benchmark": {},
        "decision_gate_benchmark": {},
        "revision_encoder_benchmark": {},
        "full_block_benchmark": {},
        "comparison": {},
        "quality_trajectory": {},
    }

    d_model = config.d_model

    # Create config
    rpq_config = ReflectivePhaseQuadConfig(
        d_model=d_model,
        num_heads=config.num_heads,
        max_revisions=args.rpq_max_revisions,
        threshold_high=args.rpq_threshold_high,
        threshold_low=args.rpq_threshold_low,
        device=device,
    )

    print(f"\n  Configuration:")
    print(f"    d_model: {d_model}")
    print(f"    num_heads: {config.num_heads}")
    print(f"    max_revisions: {args.rpq_max_revisions}")
    print(f"    threshold_high: {args.rpq_threshold_high}")
    print(f"    threshold_low: {args.rpq_threshold_low}")
    print(f"    device: {device}")

    # Initialize benchmark suite
    benchmark = ReflectivePhaseQuadBenchmark(rpq_config)

    # -------------------------------------------------------------------------
    # TEST 1: Critic Benchmark
    # -------------------------------------------------------------------------
    print("\n--- TEST 1: Critic Performance ---")
    print("  Benchmarking neural quality estimator.")

    critic_results = benchmark.benchmark_critic(
        batch_size=args.rpq_batch_size,
        seq_len=args.rpq_seq_len,
        num_iterations=100,
    )

    results["critic_benchmark"] = critic_results

    print(f"    Per-iteration: {critic_results['per_iteration_ms']:.2f}ms")
    print(f"    Throughput: {critic_results['iterations_per_sec']:.0f} it/sec")

    # -------------------------------------------------------------------------
    # TEST 2: Decision Gate Benchmark
    # -------------------------------------------------------------------------
    print("\n--- TEST 2: Decision Gate Behavior ---")
    print("  Testing threshold calibration.")

    gate_results = benchmark.benchmark_decision_gate(
        batch_size=64,
        num_iterations=1000,
    )

    results["decision_gate_benchmark"] = gate_results

    print(f"    Per-iteration: {gate_results['per_iteration_ms']:.4f}ms")
    print(f"    Throughput: {gate_results['iterations_per_sec']:.0f} it/sec")

    # Test decision distribution
    gate = DecisionGate(
        threshold_high=args.rpq_threshold_high,
        threshold_low=args.rpq_threshold_low,
        max_revisions=args.rpq_max_revisions,
    ).to(device)

    # Test with various quality scores
    test_qualities = torch.tensor([0.2, 0.4, 0.6, 0.8, 0.95], device=device).unsqueeze(1)
    test_revisions = torch.zeros(5, 1, dtype=torch.long, device=device)

    decisions = gate(test_qualities, test_revisions)

    print("\n    Quality → Decision mapping:")
    action_names = ["OUTPUT", "MINOR_REVISE", "MAJOR_REVISE", "OUTPUT+FLAG"]
    for i, q in enumerate([0.2, 0.4, 0.6, 0.8, 0.95]):
        action_idx = decisions["action"][i].item()
        print(f"      Q={q:.2f} → {action_names[action_idx]}")

    # -------------------------------------------------------------------------
    # TEST 3: Revision Encoder Benchmark
    # -------------------------------------------------------------------------
    print("\n--- TEST 3: Revision Encoder ---")
    print("  Testing revision context encoding.")

    encoder = RevisionEncoder(
        d_model=d_model,
        num_heads=config.num_heads,
    ).to(device)

    B, N = args.rpq_batch_size, args.rpq_seq_len
    original_input = torch.randn(B, N, d_model, device=device)
    previous_output = torch.randn(B, N, d_model, device=device)
    quality_dims = torch.rand(B, 3, device=device)
    quality_score = torch.rand(B, 1, device=device)
    focus_mask = torch.rand(B, N, device=device)

    import time
    start = time.perf_counter()
    for _ in range(100):
        _ = encoder(original_input, previous_output, quality_dims, quality_score, focus_mask, 1)
    elapsed = time.perf_counter() - start

    results["revision_encoder_benchmark"] = {
        "per_iteration_ms": (elapsed / 100) * 1000,
        "iterations_per_sec": 100 / elapsed,
    }

    print(f"    Per-iteration: {(elapsed / 100) * 1000:.2f}ms")

    # -------------------------------------------------------------------------
    # TEST 4: Full Block Benchmark
    # -------------------------------------------------------------------------
    print("\n--- TEST 4: Full Block with Revision Loop ---")
    print("  Testing complete reflective generation.")

    block_results = benchmark.benchmark_full_block(
        batch_size=args.rpq_batch_size,
        seq_len=args.rpq_seq_len,
        num_iterations=50,
    )

    results["full_block_benchmark"] = block_results

    print(f"\n    With Revision:")
    print(f"      Per-iteration: {block_results['with_revision']['per_iteration_ms']:.2f}ms")
    print(f"      Avg revisions: {block_results['with_revision']['avg_revisions']:.2f}")
    print(f"      Avg quality improvement: {block_results['with_revision']['avg_quality_improvement']:.4f}")

    print(f"\n    Single Pass:")
    print(f"      Per-iteration: {block_results['single_pass']['per_iteration_ms']:.2f}ms")

    print(f"\n    Overhead ratio: {block_results['overhead_ratio']:.2f}x")

    # -------------------------------------------------------------------------
    # TEST 5: Comparison - Reflective vs Single-Pass
    # -------------------------------------------------------------------------
    print("\n--- TEST 5: Reflective vs Single-Pass Comparison ---")

    block = ReflectivePhaseQuadBlock(
        d_model=d_model,
        num_heads=config.num_heads,
        max_revisions=args.rpq_max_revisions,
        threshold_high=args.rpq_threshold_high,
        threshold_low=args.rpq_threshold_low,
    ).to(device)

    # Run multiple trials
    num_trials = 20
    reflective_qualities = []
    single_pass_qualities = []

    x = torch.randn(4, args.rpq_seq_len, d_model, device=device)

    for _ in range(num_trials):
        # Reflective
        _, _, stats_r = block(x, allow_revision=True)
        reflective_qualities.append(stats_r["final_quality"])

        # Single-pass
        _, _, stats_s = block(x, allow_revision=False)
        single_pass_qualities.append(stats_s["final_quality"])

    avg_reflective = sum(reflective_qualities) / len(reflective_qualities)
    avg_single = sum(single_pass_qualities) / len(single_pass_qualities)

    results["comparison"] = {
        "avg_reflective_quality": avg_reflective,
        "avg_single_pass_quality": avg_single,
        "quality_improvement": avg_reflective - avg_single,
        "improvement_percent": ((avg_reflective - avg_single) / avg_single) * 100 if avg_single > 0 else 0,
    }

    print(f"    Avg Reflective Quality: {avg_reflective:.4f}")
    print(f"    Avg Single-Pass Quality: {avg_single:.4f}")
    print(f"    Quality Improvement: {avg_reflective - avg_single:.4f} ({results['comparison']['improvement_percent']:.1f}%)")

    # -------------------------------------------------------------------------
    # TEST 6: Quality Trajectory Analysis
    # -------------------------------------------------------------------------
    print("\n--- TEST 6: Quality Trajectory Analysis ---")

    # Generate a few samples and track quality over revisions
    trajectories = []
    for trial in range(5):
        x_trial = torch.randn(1, args.rpq_seq_len, d_model, device=device)
        _, _, stats = block(x_trial, allow_revision=True)
        trajectories.append(stats["quality_scores"])

    # Analyze trajectories
    max_steps = max(len(t) for t in trajectories)
    avg_trajectory = []
    for step in range(max_steps):
        step_qualities = [t[step] for t in trajectories if step < len(t)]
        avg_trajectory.append(sum(step_qualities) / len(step_qualities))

    results["quality_trajectory"] = {
        "avg_trajectory": avg_trajectory,
        "max_steps": max_steps,
        "final_vs_initial": avg_trajectory[-1] - avg_trajectory[0] if len(avg_trajectory) > 1 else 0,
    }

    print(f"    Avg trajectory: {' → '.join(f'{q:.3f}' for q in avg_trajectory)}")
    print(f"    Improvement per step: {results['quality_trajectory']['final_vs_initial'] / max(1, max_steps-1):.4f}")

    # -------------------------------------------------------------------------
    # Summary
    # -------------------------------------------------------------------------
    print("\n" + "=" * 70)
    print("REFLECTIVE PHASE-QUAD BENCHMARK SUMMARY")
    print("=" * 70)

    print(f"""
  Performance:
    - Critic: {critic_results['per_iteration_ms']:.2f}ms per evaluation
    - Decision Gate: {gate_results['per_iteration_ms']:.4f}ms per decision
    - Full Block: {block_results['with_revision']['per_iteration_ms']:.2f}ms with revision

  Quality:
    - Avg revisions needed: {block_results['with_revision']['avg_revisions']:.2f}
    - Quality improvement: {results['comparison']['improvement_percent']:.1f}%

  Overhead:
    - Revision overhead: {block_results['overhead_ratio']:.2f}x vs single-pass

  Recommendation:
    - Use reflective mode for quality-critical tasks
    - Use single-pass mode for latency-critical tasks
    - Threshold calibration: high={args.rpq_threshold_high}, low={args.rpq_threshold_low}
""")

    return results


def run_reflective_phase_quad_benchmark_integration(args, config):
    """
    Integration entry point for Reflective Phase-Quad benchmarks.

    Called from main() when --test-reflective-phase-quad is specified.
    """
    print("\n" + "=" * 70)
    print("REFLECTIVE PHASE-QUAD BENCHMARK: Integration Mode")
    print("=" * 70)

    results = run_reflective_phase_quad_benchmarks(args, config, config.device)

    if "error" in results:
        print(f"\nBenchmark failed: {results['error']}")
        return

    # Print CLI usage
    print("\n" + "-" * 70)
    print("CLI USAGE:")
    print("-" * 70)
    print("""
  # Run Reflective Phase-Quad benchmarks
  python train_hard_probes.py --test-reflective-phase-quad

  # Custom thresholds
  python train_hard_probes.py --test-reflective-phase-quad \\
      --rpq-threshold-high 0.9 --rpq-threshold-low 0.6

  # More revisions allowed
  python train_hard_probes.py --test-reflective-phase-quad \\
      --rpq-max-revisions 5

  # Full benchmark with ablation
  python train_hard_probes.py --test-reflective-phase-quad --rpq-ablation

  # Compare with RLM-Phase-Quad (both benchmarks)
  python train_hard_probes.py --test-reflective-phase-quad --test-rlm-phase-quad
""")

    return results


# =============================================================================
# V10.10: CAUSAL WORLD MODEL BENCHMARKS
# =============================================================================
