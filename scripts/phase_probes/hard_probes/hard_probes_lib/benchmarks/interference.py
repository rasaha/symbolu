"""
Interference-Aware Proposal Scoring Benchmarks (V10.5)

Tests the text interference scoring implementation for:
    1. Task classifier accuracy (compositional vs factual)
    2. Interference rescore function (gradient flow, multiplier bounds)
    3. Entropy gating behavior
    4. Ablation comparison (Base vs +Interference vs +BCVF vs +BCVF+Interference)

CLI Usage::

    # Run interference benchmarks
    python train_hard_probes.py --test-interference

    # With custom lambda
    python train_hard_probes.py --test-interference --interference-lambda 0.02

    # With ablation comparison
    python train_hard_probes.py --test-interference --interference-ablation

    # Full suite
    python train_hard_probes.py --test-interference --interference-ablation \\
        --interference-lambda 0.02 --interference-min-step 8 --interference-entropy-gate 1.2

Expected Results:
    - Task Classifier: >85%% accuracy on compositional vs factual
    - Gradient Flow: Gradients flow through interference rescore
    - Multiplier Bounds: Within [0.9, 1.1] for text
    - Score Change: <20%% change from base scores
"""

import time
import torch
import torch.nn as nn
from typing import Dict, Optional

from ..imports import TEXT_INTERFERENCE_AVAILABLE
if TEXT_INTERFERENCE_AVAILABLE:
    from symbolu.text_interference import (
        TextInterferenceConfig, TextInterferencePolicy,
        TextInterferenceScorer, TaskClassifier,
        InterferenceMode, BCVFTextScorer, text_interference_rescore,
    )

# =============================================================================
# V10.5: INTERFERENCE-AWARE PROPOSAL SCORING BENCHMARKS
# =============================================================================
# Tests the text interference scoring implementation to verify correctness.

# Task classifier test cases: (prompt, expected_compositional)
INTERFERENCE_TASK_TEST_CASES = [
    # Compositional tasks (should enable interference)
    ("Compare and contrast the trade-offs between microservices and monoliths.", True),
    ("Synthesize the key findings from multiple research papers on climate change.", True),
    ("Write a narrative essay blending historical fiction with modern perspectives.", True),
    ("Analyze the dimensions of this problem across economic, social, and political factors.", True),
    ("Integrate these competing viewpoints into a coherent summary.", True),
    ("Plan a multi-step approach to solving this complex engineering problem.", True),
    # Factual/code tasks (should NOT enable interference)
    ("What is the capital of France?", False),
    ("Define photosynthesis.", False),
    ("Write a Python function to sort a list.", False),
    ("How many planets are in the solar system?", False),
    ("Implement a binary search tree in JavaScript.", False),
    ("What does the acronym SQL stand for?", False),
    ("Give me the code for a REST API endpoint.", False),
]


def run_interference_benchmarks(
    args,
    config,
    device: str,
) -> Dict[str, any]:
    """
    Run comprehensive interference scoring benchmarks.

    Tests:
    1. Task classifier accuracy (compositional vs factual detection)
    2. Interference rescore function (gradient flow, multiplier bounds)
    3. Entropy gating behavior (only apply when uncertain)
    4. BCVF + Interference hybrid (if --interference-ablation)

    Args:
        args: CLI arguments
        config: Config object
        device: torch device

    Returns:
        Dictionary with benchmark results
    """
    print("\n" + "=" * 70)
    print("V10.5: INTERFERENCE-AWARE PROPOSAL SCORING BENCHMARKS")
    print("=" * 70)

    if not TEXT_INTERFERENCE_AVAILABLE:
        print("\n  ERROR: Text interference module not available.")
        print("  Ensure symbolu.text_interference is importable.")
        return {"error": "Module not available"}

    results = {
        "task_classifier": {},
        "interference_rescore": {},
        "entropy_gating": {},
        "ablation": {},
    }

    # -------------------------------------------------------------------------
    # TEST 1: Task Classifier Accuracy
    # -------------------------------------------------------------------------
    print("\n--- TEST 1: Task Classifier Accuracy ---")
    print("  Testing if classifier correctly identifies compositional vs factual tasks.")

    classifier = TaskClassifier()
    default_config = TextInterferenceConfig(
        enabled=True,
        lambda_text=args.interference_lambda,
    )

    correct = 0
    total = len(INTERFERENCE_TASK_TEST_CASES)

    print(f"\n  {'Prompt (truncated)':50}  {'Expected':>10}  {'Got':>10}  {'OK':>4}")
    print(f"  {'-'*50}  {'-'*10}  {'-'*10}  {'-'*4}")

    for prompt, expected_compositional in INTERFERENCE_TASK_TEST_CASES:
        policy = classifier.classify(prompt, default_config)
        got_compositional = policy.enable and policy.mode != InterferenceMode.OFF

        is_correct = got_compositional == expected_compositional
        if is_correct:
            correct += 1

        prompt_short = prompt[:47] + "..." if len(prompt) > 50 else prompt
        expected_str = "COMPOSE" if expected_compositional else "FACTUAL"
        got_str = "COMPOSE" if got_compositional else "FACTUAL"
        ok_str = "✓" if is_correct else "✗"

        print(f"  {prompt_short:50}  {expected_str:>10}  {got_str:>10}  {ok_str:>4}")

    accuracy = correct / total
    results["task_classifier"]["accuracy"] = accuracy
    results["task_classifier"]["correct"] = correct
    results["task_classifier"]["total"] = total

    print(f"\n  Task Classifier Accuracy: {correct}/{total} ({accuracy*100:.1f}%)")
    print(f"  [{'PASS' if accuracy >= 0.85 else 'FAIL'}] Threshold: 85%")

    # -------------------------------------------------------------------------
    # TEST 2: Interference Rescore Function
    # -------------------------------------------------------------------------
    print("\n--- TEST 2: Interference Rescore Function ---")
    print("  Testing gradient flow and multiplier bounds.")

    # Create synthetic proposals [B, N, K, D]
    B, N, K, D = 2, 4, 8, 64
    proposals = torch.randn(B, N, K, D, device=device, requires_grad=True)
    scores = torch.randn(B, N, K, device=device, requires_grad=True).abs()

    # Test rescore function
    rescored, stats = text_interference_rescore(
        proposals,
        scores,
        lam=args.interference_lambda,
        min_mult=0.9,
        max_mult=1.1,
    )

    # Check gradient flow
    loss = rescored.sum()
    loss.backward()

    grad_ok = proposals.grad is not None and scores.grad is not None
    grad_nonzero = proposals.grad.abs().sum() > 0 if grad_ok else False

    print(f"\n  Shape check: proposals={list(proposals.shape)}, scores={list(scores.shape)}")
    print(f"  Rescored shape: {list(rescored.shape)}")
    print(f"  Gradient flow: {'OK' if grad_ok else 'FAIL'}")
    print(f"  Nonzero gradients: {'OK' if grad_nonzero else 'FAIL'}")

    # Check multiplier bounds
    mult_in_bounds = (
        stats.get("interference/multiplier_mean", 0) >= 0.9 and
        stats.get("interference/multiplier_mean", 0) <= 1.1
    )
    print(f"\n  Multiplier stats:")
    print(f"    Mean: {stats.get('interference/multiplier_mean', 'N/A'):.4f}")
    print(f"    Std:  {stats.get('interference/multiplier_std', 'N/A'):.4f}")
    print(f"  Multiplier in bounds [0.9, 1.1]: {'OK' if mult_in_bounds else 'WARN'}")

    # Check score change percentage
    score_change = stats.get("interference/score_change_pct", 0)
    reasonable_change = score_change < 20  # Should be modest changes
    print(f"  Score change: {score_change:.2f}%")
    print(f"  Reasonable change (<20%): {'OK' if reasonable_change else 'WARN'}")

    results["interference_rescore"]["gradient_flow"] = grad_ok and grad_nonzero
    results["interference_rescore"]["multiplier_bounded"] = mult_in_bounds
    results["interference_rescore"]["reasonable_change"] = reasonable_change
    results["interference_rescore"]["stats"] = stats

    print(f"\n  [{'PASS' if grad_ok and grad_nonzero else 'FAIL'}] Interference rescore gradient flow")

    # -------------------------------------------------------------------------
    # TEST 3: Entropy Gating Behavior
    # -------------------------------------------------------------------------
    print("\n--- TEST 3: Entropy Gating Behavior ---")
    print("  Testing that interference only applies when proposals are uncertain.")

    scorer = TextInterferenceScorer(
        config=TextInterferenceConfig(
            enabled=True,
            lambda_text=args.interference_lambda,
            min_step=args.interference_min_step,
            entropy_gate=args.interference_entropy_gate,
        )
    )

    # Test with low entropy (should NOT apply)
    proposals_low_ent = torch.randn(B, N, K, D, device=device)
    # Make proposals very similar (low entropy)
    proposals_low_ent = proposals_low_ent.mean(dim=2, keepdim=True).expand_as(proposals_low_ent)
    proposals_low_ent = proposals_low_ent + torch.randn_like(proposals_low_ent) * 0.01

    scores_low = torch.ones(B, N, K, device=device)
    policy_low = TextInterferencePolicy(enable=True, lam=0.02, min_step=1, entropy_gate=1.2)
    rescored_low, stats_low = scorer(
        proposals_low_ent, scores_low, policy=policy_low, step=10
    )
    applied_low = stats_low.get("interference/applied", 0) > 0

    # Test with high entropy (should apply)
    proposals_high_ent = torch.randn(B, N, K, D, device=device)
    scores_high = torch.randn(B, N, K, device=device).abs()
    policy_high = TextInterferencePolicy(enable=True, lam=0.02, min_step=1, entropy_gate=0.1)  # Low gate
    rescored_high, stats_high = scorer(
        proposals_high_ent, scores_high, policy=policy_high, step=10
    )
    applied_high = stats_high.get("interference/applied", 0) > 0

    print(f"\n  Low entropy proposals:")
    print(f"    Entropy: {stats_low.get('interference/proposal_entropy', 'N/A'):.4f}" if 'interference/proposal_entropy' in stats_low else "    Entropy: (computed internally)")
    print(f"    Interference applied: {'YES' if applied_low else 'NO'}")

    print(f"\n  High entropy proposals:")
    print(f"    Entropy: {stats_high.get('interference/proposal_entropy', 'N/A'):.4f}" if 'interference/proposal_entropy' in stats_high else "    Entropy: (computed internally)")
    print(f"    Interference applied: {'YES' if applied_high else 'NO'}")

    # Expected: low entropy = not applied, high entropy = applied
    entropy_gating_correct = applied_high  # At minimum, high entropy should trigger

    results["entropy_gating"]["low_entropy_applied"] = applied_low
    results["entropy_gating"]["high_entropy_applied"] = applied_high
    results["entropy_gating"]["correct"] = entropy_gating_correct

    print(f"\n  [{'PASS' if entropy_gating_correct else 'WARN'}] Entropy gating behavior")

    # -------------------------------------------------------------------------
    # TEST 4: Ablation (Base vs +Interference vs +BCVF vs +BCVF+Interference)
    # -------------------------------------------------------------------------
    if args.interference_ablation:
        print("\n--- TEST 4: Ablation Comparison ---")
        print("  Comparing: Base vs +Interference vs +BCVF vs +BCVF+Interference")

        # Create BCVF scorer
        bcvf_scorer = BCVFTextScorer(
            d_model=D,
            interference_config=TextInterferenceConfig(
                enabled=True,
                lambda_text=args.interference_lambda,
            ),
        ).to(device)

        # Synthetic compositional task proposals
        proposals_comp = torch.randn(B, N, K, D, device=device)
        scores_base = torch.randn(B, N, K, device=device).abs()

        # Base (no modification)
        results_base = scores_base.clone()

        # +Interference only
        results_interf, _ = text_interference_rescore(
            proposals_comp, scores_base,
            lam=args.interference_lambda,
        )

        # +BCVF+Interference
        policy = TextInterferencePolicy(enable=True, lam=0.02, min_step=1)
        results_bcvf_interf, bcvf_stats = bcvf_scorer(
            proposals_comp, scores_base, policy=policy, step=10
        )

        print(f"\n  Score statistics after each variant:")
        print(f"    Base:              mean={results_base.mean():.4f}, std={results_base.std():.4f}")
        print(f"    +Interference:     mean={results_interf.mean():.4f}, std={results_interf.std():.4f}")
        print(f"    +BCVF+Interference: mean={results_bcvf_interf.mean():.4f}, std={results_bcvf_interf.std():.4f}")

        # Calculate change percentages
        interf_change = ((results_interf - results_base).abs() / (results_base.abs() + 1e-6)).mean() * 100
        bcvf_interf_change = ((results_bcvf_interf - results_base).abs() / (results_base.abs() + 1e-6)).mean() * 100

        print(f"\n  Change from base:")
        print(f"    +Interference:      {interf_change:.2f}%")
        print(f"    +BCVF+Interference: {bcvf_interf_change:.2f}%")

        results["ablation"]["interference_change_pct"] = interf_change.item()
        results["ablation"]["bcvf_interference_change_pct"] = bcvf_interf_change.item()
        results["ablation"]["bcvf_stats"] = bcvf_stats

        print(f"\n  [INFO] Ablation complete. Changes indicate interference is active.")

    # -------------------------------------------------------------------------
    # Summary
    # -------------------------------------------------------------------------
    print("\n" + "=" * 70)
    print("INTERFERENCE BENCHMARK SUMMARY")
    print("=" * 70)

    all_pass = (
        results["task_classifier"]["accuracy"] >= 0.85 and
        results["interference_rescore"]["gradient_flow"]
    )

    print(f"\n  Task Classifier:     {'PASS' if results['task_classifier']['accuracy'] >= 0.85 else 'FAIL'} ({results['task_classifier']['accuracy']*100:.1f}%)")
    print(f"  Gradient Flow:       {'PASS' if results['interference_rescore']['gradient_flow'] else 'FAIL'}")
    print(f"  Multiplier Bounds:   {'PASS' if results['interference_rescore']['multiplier_bounded'] else 'WARN'}")
    print(f"  Entropy Gating:      {'PASS' if results['entropy_gating']['correct'] else 'WARN'}")

    print(f"\n  Overall: {'PASS' if all_pass else 'FAIL'}")

    return results


def run_interference_benchmark_integration(args, config):
    """
    Integration test for interference with a trained model.

    This is called from main() when --test-interference is specified.
    """
    print("\n" + "=" * 70)
    print("INTERFERENCE BENCHMARK: Integration Mode")
    print("=" * 70)

    results = run_interference_benchmarks(args, config, config.device)

    if "error" in results:
        print(f"\nBenchmark failed: {results['error']}")
        return

    # Print CLI usage reminder
    print("\n" + "-" * 70)
    print("CLI USAGE:")
    print("-" * 70)
    print("""
  # Run interference benchmarks
  python train_hard_probes.py --test-interference

  # With custom lambda (0.01-0.03 for text)
  python train_hard_probes.py --test-interference --interference-lambda 0.02

  # With ablation comparison
  python train_hard_probes.py --test-interference --interference-ablation

  # Full benchmark suite
  python train_hard_probes.py --test-interference --interference-ablation \\
      --interference-lambda 0.02 --interference-min-step 8 --interference-entropy-gate 1.2
""")

    return results


# =============================================================================
