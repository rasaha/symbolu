#!/usr/bin/env python3
"""
Cross-Task Validation Protocol
================================

Runs the minimal validation protocol to determine if quadratic
attention solves a structural limitation:

  Benchmark A: Harder Binding Stress Test
    - 3 difficulty tiers (easy, medium, hard)
    - Tests if quadratic advantage scales with difficulty

  Benchmark B: SCAN-style Compositional Generalization
    - Train on known compositions, test on novel combos
    - Tests if quadratic helps systematic generalization

Both benchmarks run across 3 seeds for stability.

Decision criteria:
  - Quadratic wins both  -> structural pattern (publishable)
  - Quadratic wins only A -> narrow but real binding effect
  - Quadratic wins neither -> overfitting / artifact

Usage:
    python -m resonant_model.run_cross_task_validation
    python -m resonant_model.run_cross_task_validation --seeds 42 123 7
    python -m resonant_model.run_cross_task_validation --benchmark-a-only
    python -m resonant_model.run_cross_task_validation --benchmark-b-only
"""

import argparse
import json
import time
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple

import torch

from resonant_model.heads import (
    HeadConfig,
    SoftmaxBindingHead,
    QuadraticBindingHead,
    ScalableQuadraticBindingHead,
    ScalableQuadraticConfig,
    count_parameters,
)
from resonant_model.evaluator import train_and_evaluate, EvaluationResult
from resonant_model.statistics import BindingStatistics, format_report
from resonant_model.harder_binding import (
    DifficultyTier,
    generate_harder_dataset,
)
from resonant_model.scan_benchmark import (
    generate_scan_dataset,
    SCANSplitDataset,
)


# ─── Result Data Structures ─────────────────────────────────────────────────

@dataclass
class SingleRunResult:
    """Result of a single benchmark run (one seed, one config)."""
    seed: int
    softmax_accuracy: float
    quadratic_accuracy: float
    advantage: float  # quadratic - softmax
    softmax_correct: int
    quadratic_correct: int
    total_examples: int


@dataclass
class DifficultyResult:
    """Results across seeds for one difficulty tier."""
    difficulty: str
    runs: List[SingleRunResult]
    mean_softmax_accuracy: float = 0.0
    mean_quadratic_accuracy: float = 0.0
    mean_advantage: float = 0.0
    advantage_consistent: bool = False  # True if advantage > 0 in all seeds

    def compute_stats(self):
        if not self.runs:
            return
        self.mean_softmax_accuracy = sum(r.softmax_accuracy for r in self.runs) / len(self.runs)
        self.mean_quadratic_accuracy = sum(r.quadratic_accuracy for r in self.runs) / len(self.runs)
        self.mean_advantage = sum(r.advantage for r in self.runs) / len(self.runs)
        self.advantage_consistent = all(r.advantage > 0 for r in self.runs)


@dataclass
class BenchmarkAResults:
    """Full results for Benchmark A (harder binding)."""
    difficulty_results: Dict[str, DifficultyResult] = field(default_factory=dict)
    advantage_scales_with_difficulty: bool = False
    verdict: str = ""

    def analyze(self):
        """Determine if advantage scales with difficulty."""
        tiers = ["easy", "medium", "hard"]
        advantages = []
        for tier in tiers:
            if tier in self.difficulty_results:
                self.difficulty_results[tier].compute_stats()
                advantages.append(self.difficulty_results[tier].mean_advantage)

        if len(advantages) >= 2:
            # Check if advantage increases with difficulty
            self.advantage_scales_with_difficulty = all(
                advantages[i] <= advantages[i + 1]
                for i in range(len(advantages) - 1)
            )

        # Verdict
        all_positive = all(
            dr.mean_advantage > 0
            for dr in self.difficulty_results.values()
        )
        all_consistent = all(
            dr.advantage_consistent
            for dr in self.difficulty_results.values()
        )

        if self.advantage_scales_with_difficulty and all_consistent:
            self.verdict = "STRONG: Quadratic advantage scales with difficulty (consistent across seeds)"
        elif all_positive and self.advantage_scales_with_difficulty:
            self.verdict = "MODERATE: Advantage scales but not consistent across all seeds"
        elif all_positive:
            self.verdict = "PRESENT: Quadratic advantage exists but doesn't scale with difficulty"
        else:
            self.verdict = "WEAK: No consistent quadratic advantage"


@dataclass
class BenchmarkBResults:
    """Full results for Benchmark B (SCAN compositional)."""
    train_results: List[SingleRunResult] = field(default_factory=list)
    test_results: List[SingleRunResult] = field(default_factory=list)
    mean_train_advantage: float = 0.0
    mean_test_advantage: float = 0.0
    generalizes: bool = False
    verdict: str = ""

    def analyze(self):
        if self.train_results:
            self.mean_train_advantage = sum(
                r.advantage for r in self.train_results
            ) / len(self.train_results)
        if self.test_results:
            self.mean_test_advantage = sum(
                r.advantage for r in self.test_results
            ) / len(self.test_results)

        train_positive = self.mean_train_advantage > 0
        test_positive = self.mean_test_advantage > 0
        test_consistent = all(r.advantage > 0 for r in self.test_results) if self.test_results else False

        if test_positive and test_consistent:
            self.generalizes = True
            self.verdict = "STRONG: Quadratic improves held-out compositions (consistent)"
        elif test_positive:
            self.generalizes = True
            self.verdict = "MODERATE: Quadratic helps generalization (not all seeds)"
        elif train_positive:
            self.generalizes = False
            self.verdict = "NARROW: Quadratic helps training compositions only"
        else:
            self.generalizes = False
            self.verdict = "NONE: No quadratic advantage on compositional task"


@dataclass
class CrossTaskVerdict:
    """Final cross-task determination."""
    benchmark_a: BenchmarkAResults
    benchmark_b: BenchmarkBResults
    pattern: str = ""
    confidence: str = ""

    def determine(self):
        a_wins = self.benchmark_a.verdict.startswith("STRONG") or \
                 self.benchmark_a.verdict.startswith("MODERATE")
        b_wins = self.benchmark_b.generalizes

        if a_wins and b_wins:
            self.pattern = "STRUCTURAL"
            self.confidence = (
                "Quadratic solves a structural limitation. "
                "Advantage scales with difficulty AND generalizes across tasks. "
                "This is publishable evidence."
            )
        elif a_wins and not b_wins:
            self.pattern = "BINDING-SPECIFIC"
            self.confidence = (
                "Quadratic advantage is real but narrow. "
                "Helps binding specifically, not general composition. "
                "Still a valid contribution to binding literature."
            )
        elif not a_wins and b_wins:
            self.pattern = "COMPOSITION-SPECIFIC"
            self.confidence = (
                "Quadratic helps composition but not harder binding. "
                "Unexpected — worth investigating further."
            )
        else:
            self.pattern = "INSUFFICIENT"
            self.confidence = (
                "No cross-task evidence for quadratic advantage. "
                "Earlier binding results may be task-specific or artifact."
            )


# ─── Benchmark Runners ───────────────────────────────────────────────────────

def _run_single_binding(
    difficulty: DifficultyTier,
    seed: int,
    config: HeadConfig,
    scale_config: ScalableQuadraticConfig,
    epochs: int,
    lr: float,
    device: torch.device,
    num_examples: int,
) -> SingleRunResult:
    """Run softmax vs quadratic on one difficulty/seed combo."""
    dataset = generate_harder_dataset(
        num_examples=num_examples, seed=seed, difficulty=difficulty,
    )

    # Softmax baseline
    model_a = SoftmaxBindingHead(config)
    result_a = train_and_evaluate(
        model_a, dataset, model_name="softmax",
        epochs=epochs, lr=lr, device=device, config=config,
    )

    # Quadratic (scalable)
    model_b = ScalableQuadraticBindingHead(config, scale_config)
    result_b = train_and_evaluate(
        model_b, dataset, model_name="quadratic",
        epochs=epochs, lr=lr, device=device, config=config,
    )

    return SingleRunResult(
        seed=seed,
        softmax_accuracy=result_a.accuracy,
        quadratic_accuracy=result_b.accuracy,
        advantage=result_b.accuracy - result_a.accuracy,
        softmax_correct=result_a.correct,
        quadratic_correct=result_b.correct,
        total_examples=result_a.total_examples,
    )


def _run_single_scan(
    seed: int,
    config: HeadConfig,
    scale_config: ScalableQuadraticConfig,
    epochs: int,
    lr: float,
    device: torch.device,
    num_train: int,
    num_test: int,
) -> Tuple[SingleRunResult, SingleRunResult]:
    """Run softmax vs quadratic on SCAN split (returns train_result, test_result)."""
    scan_data = generate_scan_dataset(
        num_train=num_train, num_test=num_test, seed=seed,
    )

    # Train both models on training split
    model_a = SoftmaxBindingHead(config)
    train_result_a = train_and_evaluate(
        model_a, scan_data.train, model_name="softmax",
        epochs=epochs, lr=lr, device=device, config=config,
    )

    model_b = ScalableQuadraticBindingHead(config, scale_config)
    train_result_b = train_and_evaluate(
        model_b, scan_data.train, model_name="quadratic",
        epochs=epochs, lr=lr, device=device, config=config,
    )

    # Evaluate on train split (in-distribution)
    from resonant_model.evaluator import BindingEvaluator
    evaluator = BindingEvaluator(config=config, device=device)

    train_eval_a = evaluator.evaluate(model_a, scan_data.train, "softmax_train")
    train_eval_b = evaluator.evaluate(model_b, scan_data.train, "quadratic_train")

    train_result = SingleRunResult(
        seed=seed,
        softmax_accuracy=train_eval_a.accuracy,
        quadratic_accuracy=train_eval_b.accuracy,
        advantage=train_eval_b.accuracy - train_eval_a.accuracy,
        softmax_correct=train_eval_a.correct,
        quadratic_correct=train_eval_b.correct,
        total_examples=train_eval_a.total_examples,
    )

    # Evaluate on test split (novel compositions)
    test_eval_a = evaluator.evaluate(model_a, scan_data.test, "softmax_test")
    test_eval_b = evaluator.evaluate(model_b, scan_data.test, "quadratic_test")

    test_result = SingleRunResult(
        seed=seed,
        softmax_accuracy=test_eval_a.accuracy,
        quadratic_accuracy=test_eval_b.accuracy,
        advantage=test_eval_b.accuracy - test_eval_a.accuracy,
        softmax_correct=test_eval_a.correct,
        quadratic_correct=test_eval_b.correct,
        total_examples=test_eval_a.total_examples,
    )

    return train_result, test_result


# ─── Report Formatting ──────────────────────────────────────────────────────

def format_cross_task_report(verdict: CrossTaskVerdict) -> str:
    """Format the full cross-task validation report."""
    lines = []
    lines.append("=" * 72)
    lines.append("CROSS-TASK VALIDATION PROTOCOL REPORT")
    lines.append("=" * 72)
    lines.append("")

    # Benchmark A
    lines.append("-" * 72)
    lines.append("BENCHMARK A: HARDER BINDING STRESS TEST")
    lines.append("-" * 72)
    lines.append("")
    lines.append(f"  {'Difficulty':<10s} {'Softmax':>10s} {'Quadratic':>10s} {'Advantage':>10s} {'Consistent':>10s}")
    lines.append(f"  {'─'*10} {'─'*10} {'─'*10} {'─'*10} {'─'*10}")

    for tier in ["easy", "medium", "hard"]:
        dr = verdict.benchmark_a.difficulty_results.get(tier)
        if dr:
            consistent_str = "Yes" if dr.advantage_consistent else "No"
            lines.append(
                f"  {tier:<10s} {dr.mean_softmax_accuracy:>9.1%} {dr.mean_quadratic_accuracy:>10.1%} "
                f"{dr.mean_advantage:>+9.1%} {consistent_str:>10s}"
            )
            for run in dr.runs:
                lines.append(
                    f"    seed={run.seed}: "
                    f"softmax={run.softmax_accuracy:.1%} "
                    f"quad={run.quadratic_accuracy:.1%} "
                    f"adv={run.advantage:+.1%}"
                )
    lines.append("")
    lines.append(f"  Advantage scales with difficulty: "
                 f"{'Yes' if verdict.benchmark_a.advantage_scales_with_difficulty else 'No'}")
    lines.append(f"  Verdict: {verdict.benchmark_a.verdict}")
    lines.append("")

    # Benchmark B
    lines.append("-" * 72)
    lines.append("BENCHMARK B: SCAN-STYLE COMPOSITIONAL GENERALIZATION")
    lines.append("-" * 72)
    lines.append("")

    lines.append("  Training compositions (in-distribution):")
    for run in verdict.benchmark_b.train_results:
        lines.append(
            f"    seed={run.seed}: "
            f"softmax={run.softmax_accuracy:.1%} "
            f"quad={run.quadratic_accuracy:.1%} "
            f"adv={run.advantage:+.1%}"
        )
    lines.append(f"    Mean advantage: {verdict.benchmark_b.mean_train_advantage:+.1%}")
    lines.append("")

    lines.append("  Novel compositions (held-out, generalization test):")
    for run in verdict.benchmark_b.test_results:
        lines.append(
            f"    seed={run.seed}: "
            f"softmax={run.softmax_accuracy:.1%} "
            f"quad={run.quadratic_accuracy:.1%} "
            f"adv={run.advantage:+.1%}"
        )
    lines.append(f"    Mean advantage: {verdict.benchmark_b.mean_test_advantage:+.1%}")
    lines.append("")
    lines.append(f"  Generalizes to novel compositions: "
                 f"{'Yes' if verdict.benchmark_b.generalizes else 'No'}")
    lines.append(f"  Verdict: {verdict.benchmark_b.verdict}")
    lines.append("")

    # Cross-task verdict
    lines.append("=" * 72)
    lines.append("CROSS-TASK VERDICT")
    lines.append("=" * 72)
    lines.append("")
    lines.append(f"  Pattern: {verdict.pattern}")
    lines.append(f"  {verdict.confidence}")
    lines.append("")
    lines.append("=" * 72)

    return "\n".join(lines)


# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Cross-task validation protocol")
    parser.add_argument("--seeds", type=int, nargs="+", default=[42, 123, 7])
    parser.add_argument("--epochs", type=int, default=10)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--embed-dim", type=int, default=128)
    parser.add_argument("--num-heads", type=int, default=4)
    parser.add_argument("--num-layers", type=int, default=2)
    parser.add_argument("--bilinear-rank", type=int, default=32)
    parser.add_argument("--bilinear-channels", type=int, default=4)
    parser.add_argument("--spectral-norm", action="store_true")
    parser.add_argument("--bilinear-dropout", type=float, default=0.1)
    parser.add_argument("--num-examples-a", type=int, default=200,
                        help="Examples per difficulty tier in Benchmark A")
    parser.add_argument("--num-train-b", type=int, default=300,
                        help="Training examples for Benchmark B")
    parser.add_argument("--num-test-b", type=int, default=100,
                        help="Test examples for Benchmark B")
    parser.add_argument("--benchmark-a-only", action="store_true")
    parser.add_argument("--benchmark-b-only", action="store_true")
    parser.add_argument("--device", type=str, default="cpu")
    parser.add_argument("--output", type=str, default=None,
                        help="Path to write JSON results")
    args = parser.parse_args()

    device = torch.device(args.device)
    config = HeadConfig(
        embed_dim=args.embed_dim,
        num_heads=args.num_heads,
        num_layers=args.num_layers,
    )
    scale_config = ScalableQuadraticConfig(
        num_channels=args.bilinear_channels,
        rank=args.bilinear_rank,
        use_spectral_norm=args.spectral_norm,
        bilinear_dropout=args.bilinear_dropout,
    )

    run_a = not args.benchmark_b_only
    run_b = not args.benchmark_a_only

    print("=" * 72)
    print("CROSS-TASK VALIDATION PROTOCOL")
    print(f"  Seeds: {args.seeds}")
    print(f"  Quadratic config: rank={args.bilinear_rank}, "
          f"channels={args.bilinear_channels}, "
          f"spectral_norm={args.spectral_norm}, "
          f"dropout={args.bilinear_dropout}")
    print(f"  Benchmark A: {'ON' if run_a else 'OFF'}")
    print(f"  Benchmark B: {'ON' if run_b else 'OFF'}")
    print("=" * 72)
    print()

    # Model parameter counts
    model_a_ref = SoftmaxBindingHead(config)
    model_b_ref = ScalableQuadraticBindingHead(config, scale_config)
    print(f"  Softmax params:   {count_parameters(model_a_ref):,}")
    print(f"  Quadratic params: {count_parameters(model_b_ref):,}")
    print()
    del model_a_ref, model_b_ref

    benchmark_a_results = BenchmarkAResults()
    benchmark_b_results = BenchmarkBResults()

    # ── Benchmark A ──────────────────────────────────────────────────────
    if run_a:
        print("-" * 72)
        print("BENCHMARK A: HARDER BINDING STRESS TEST")
        print("-" * 72)
        print()

        for difficulty in [DifficultyTier.EASY, DifficultyTier.MEDIUM, DifficultyTier.HARD]:
            tier_name = difficulty.value
            print(f"  Difficulty: {tier_name.upper()}")
            dr = DifficultyResult(difficulty=tier_name, runs=[])

            for seed in args.seeds:
                t0 = time.time()
                print(f"    Seed {seed}...", end=" ", flush=True)
                result = _run_single_binding(
                    difficulty=difficulty,
                    seed=seed,
                    config=config,
                    scale_config=scale_config,
                    epochs=args.epochs,
                    lr=args.lr,
                    device=device,
                    num_examples=args.num_examples_a,
                )
                elapsed = time.time() - t0
                print(
                    f"softmax={result.softmax_accuracy:.1%} "
                    f"quad={result.quadratic_accuracy:.1%} "
                    f"adv={result.advantage:+.1%} "
                    f"({elapsed:.1f}s)"
                )
                dr.runs.append(result)

            dr.compute_stats()
            print(f"    Mean: softmax={dr.mean_softmax_accuracy:.1%} "
                  f"quad={dr.mean_quadratic_accuracy:.1%} "
                  f"adv={dr.mean_advantage:+.1%} "
                  f"consistent={'Yes' if dr.advantage_consistent else 'No'}")
            print()

            benchmark_a_results.difficulty_results[tier_name] = dr

        benchmark_a_results.analyze()
        print(f"  Benchmark A verdict: {benchmark_a_results.verdict}")
        print()

    # ── Benchmark B ──────────────────────────────────────────────────────
    if run_b:
        print("-" * 72)
        print("BENCHMARK B: SCAN-STYLE COMPOSITIONAL GENERALIZATION")
        print("-" * 72)
        print()

        for seed in args.seeds:
            t0 = time.time()
            print(f"  Seed {seed}...", end=" ", flush=True)
            train_result, test_result = _run_single_scan(
                seed=seed,
                config=config,
                scale_config=scale_config,
                epochs=args.epochs,
                lr=args.lr,
                device=device,
                num_train=args.num_train_b,
                num_test=args.num_test_b,
            )
            elapsed = time.time() - t0
            print(
                f"train_adv={train_result.advantage:+.1%} "
                f"test_adv={test_result.advantage:+.1%} "
                f"({elapsed:.1f}s)"
            )
            benchmark_b_results.train_results.append(train_result)
            benchmark_b_results.test_results.append(test_result)

        benchmark_b_results.analyze()
        print()
        print(f"  Mean train advantage: {benchmark_b_results.mean_train_advantage:+.1%}")
        print(f"  Mean test advantage:  {benchmark_b_results.mean_test_advantage:+.1%}")
        print(f"  Benchmark B verdict: {benchmark_b_results.verdict}")
        print()

    # ── Cross-task verdict ───────────────────────────────────────────────
    verdict = CrossTaskVerdict(
        benchmark_a=benchmark_a_results,
        benchmark_b=benchmark_b_results,
    )
    verdict.determine()

    print()
    print(format_cross_task_report(verdict))

    # Save JSON results if requested
    if args.output:
        results_dict = {
            "benchmark_a": {
                tier: {
                    "mean_softmax": dr.mean_softmax_accuracy,
                    "mean_quadratic": dr.mean_quadratic_accuracy,
                    "mean_advantage": dr.mean_advantage,
                    "consistent": dr.advantage_consistent,
                    "runs": [
                        {
                            "seed": r.seed,
                            "softmax": r.softmax_accuracy,
                            "quadratic": r.quadratic_accuracy,
                            "advantage": r.advantage,
                        }
                        for r in dr.runs
                    ],
                }
                for tier, dr in benchmark_a_results.difficulty_results.items()
            },
            "benchmark_a_verdict": benchmark_a_results.verdict,
            "benchmark_a_scales": benchmark_a_results.advantage_scales_with_difficulty,
            "benchmark_b": {
                "train_runs": [
                    {
                        "seed": r.seed,
                        "softmax": r.softmax_accuracy,
                        "quadratic": r.quadratic_accuracy,
                        "advantage": r.advantage,
                    }
                    for r in benchmark_b_results.train_results
                ],
                "test_runs": [
                    {
                        "seed": r.seed,
                        "softmax": r.softmax_accuracy,
                        "quadratic": r.quadratic_accuracy,
                        "advantage": r.advantage,
                    }
                    for r in benchmark_b_results.test_results
                ],
                "mean_train_advantage": benchmark_b_results.mean_train_advantage,
                "mean_test_advantage": benchmark_b_results.mean_test_advantage,
                "generalizes": benchmark_b_results.generalizes,
            },
            "benchmark_b_verdict": benchmark_b_results.verdict,
            "cross_task_pattern": verdict.pattern,
            "cross_task_confidence": verdict.confidence,
        }

        with open(args.output, "w") as f:
            json.dump(results_dict, f, indent=2)
        print(f"\nResults saved to: {args.output}")

    return verdict


if __name__ == "__main__":
    main()
