#!/usr/bin/env python3
"""
Logit Modulation Benchmark Suite
==================================

Evaluation framework for comparing the modified decoding rule:

    P(y | x) = softmax(z_y + α·R_y − β·C_y)

against baseline softmax across four experimental conditions:

1. Baseline (pure softmax)
2. Retrieval only (α > 0, β = 0)
3. Penalty only (α = 0, β > 0)
4. Retrieval + Penalty (α > 0, β > 0)

Metrics computed:
    - pass@1 (accuracy on greedy decode)
    - ECE (Expected Calibration Error)
    - Brier score
    - Spearman rank correlation with correctness
    - Hallucination rate (optional)

Author: Sovereign-1 Training Initiative
Date: February 2026
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

try:
    import torch
    import torch.nn.functional as F

    PYTORCH_AVAILABLE = True
except ImportError:
    PYTORCH_AVAILABLE = False

from .logit_modulation import LogitModulationConfig, LogitModulator, ModulationMode


# =========================================================================
# Metric Functions
# =========================================================================


def compute_pass_at_1(predictions: np.ndarray, targets: np.ndarray) -> float:
    """Compute pass@1 (exact-match accuracy on greedy decode).

    Args:
        predictions: [N] predicted token IDs.
        targets: [N] ground-truth token IDs.

    Returns:
        Accuracy in [0, 1].
    """
    return float(np.mean(predictions == targets))


def compute_ece(
    confidences: np.ndarray,
    correctness: np.ndarray,
    n_bins: int = 15,
) -> float:
    """Compute Expected Calibration Error.

    Args:
        confidences: [N] confidence (max probability) per sample.
        correctness: [N] binary correctness per sample.
        n_bins: Number of equal-width bins.

    Returns:
        ECE value in [0, 1].
    """
    bin_boundaries = np.linspace(0.0, 1.0, n_bins + 1)
    ece = 0.0
    total = len(confidences)
    if total == 0:
        return 0.0

    for i in range(n_bins):
        lo, hi = bin_boundaries[i], bin_boundaries[i + 1]
        mask = (confidences > lo) & (confidences <= hi)
        count = mask.sum()
        if count == 0:
            continue
        avg_conf = confidences[mask].mean()
        avg_acc = correctness[mask].mean()
        ece += (count / total) * abs(avg_acc - avg_conf)

    return float(ece)


def compute_brier_score(
    confidences: np.ndarray, correctness: np.ndarray
) -> float:
    """Compute Brier score.

    Args:
        confidences: [N] confidence per sample.
        correctness: [N] binary correctness per sample.

    Returns:
        Brier score (lower is better).
    """
    return float(np.mean((confidences - correctness) ** 2))


def compute_spearman(
    confidences: np.ndarray, correctness: np.ndarray
) -> float:
    """Compute Spearman rank correlation between confidence and correctness.

    Args:
        confidences: [N] confidence scores.
        correctness: [N] binary correctness labels.

    Returns:
        Spearman rho in [-1, 1].
    """
    n = len(confidences)
    if n < 2:
        return 0.0

    def _rankdata(x: np.ndarray) -> np.ndarray:
        order = x.argsort()
        ranks = np.empty_like(order, dtype=float)
        ranks[order] = np.arange(1, len(x) + 1, dtype=float)
        return ranks

    rank_c = _rankdata(confidences)
    rank_y = _rankdata(correctness)

    d = rank_c - rank_y
    rho = 1.0 - (6.0 * np.sum(d ** 2)) / (n * (n ** 2 - 1))
    return float(rho)


# =========================================================================
# Data Structures
# =========================================================================


@dataclass
class BenchmarkMetrics:
    """Aggregated metrics for one experimental condition."""

    condition: str
    alpha: float
    beta: float
    pass_at_1: float = 0.0
    ece: float = 0.0
    brier: float = 0.0
    spearman: float = 0.0
    hallucination_rate: Optional[float] = None
    n_samples: int = 0

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "condition": self.condition,
            "alpha": self.alpha,
            "beta": self.beta,
            "pass_at_1": self.pass_at_1,
            "ece": self.ece,
            "brier": self.brier,
            "spearman": self.spearman,
            "n_samples": self.n_samples,
        }
        if self.hallucination_rate is not None:
            d["hallucination_rate"] = self.hallucination_rate
        return d


@dataclass
class SweepResult:
    """Result of an alpha/beta hyperparameter sweep."""

    condition: str
    alpha_values: List[float]
    beta_values: List[float]
    results: List[BenchmarkMetrics] = field(default_factory=list)

    def best_by_pass_at_1(self) -> Optional[BenchmarkMetrics]:
        if not self.results:
            return None
        return max(self.results, key=lambda r: r.pass_at_1)

    def best_by_ece(self) -> Optional[BenchmarkMetrics]:
        if not self.results:
            return None
        return min(self.results, key=lambda r: r.ece)

    def best_by_brier(self) -> Optional[BenchmarkMetrics]:
        if not self.results:
            return None
        return min(self.results, key=lambda r: r.brier)


# =========================================================================
# Benchmark Runner
# =========================================================================

if PYTORCH_AVAILABLE:

    class LogitModulationBenchmark:
        """Runs evaluation for logit modulation decoding.

        Compares four conditions:
        1. Baseline (pure softmax)
        2. Retrieval only (α > 0, β = 0)
        3. Penalty only (α = 0, β > 0)
        4. Retrieval + Penalty (α > 0, β > 0)

        Works with pre-collected logit data (offline evaluation) or
        can be used in online mode with a model.
        """

        def __init__(self, device: str = "cpu"):
            self.device = torch.device(device)

        def evaluate_condition(
            self,
            base_logits: torch.Tensor,
            target_ids: torch.Tensor,
            config: LogitModulationConfig,
            retrieval_scores: Optional[torch.Tensor] = None,
            penalty_scores: Optional[torch.Tensor] = None,
            condition_name: str = "unknown",
        ) -> BenchmarkMetrics:
            """Evaluate one experimental condition.

            Args:
                base_logits: [N, V] base logits for N samples.
                target_ids: [N] ground-truth token IDs.
                config: Logit modulation configuration.
                retrieval_scores: [N, V] retrieval scores.
                penalty_scores: [N, V] penalty scores.
                condition_name: Label for this condition.

            Returns:
                metrics: Aggregated benchmark metrics.
            """
            modulator = LogitModulator(config)
            N = base_logits.size(0)

            # Apply modulation
            modified = modulator.modulate(
                base_logits, retrieval_scores, penalty_scores
            )

            # Get probabilities and predictions
            probs = F.softmax(modified, dim=-1)
            predictions = torch.argmax(modified, dim=-1)  # greedy
            confidences = probs.max(dim=-1)[0]

            # Convert to numpy
            pred_np = predictions.cpu().numpy()
            target_np = target_ids.cpu().numpy()
            conf_np = confidences.cpu().detach().numpy()
            correct_np = (pred_np == target_np).astype(float)

            return BenchmarkMetrics(
                condition=condition_name,
                alpha=config.alpha,
                beta=config.beta,
                pass_at_1=compute_pass_at_1(pred_np, target_np),
                ece=compute_ece(conf_np, correct_np),
                brier=compute_brier_score(conf_np, correct_np),
                spearman=compute_spearman(conf_np, correct_np),
                n_samples=N,
            )

        def run_ablation(
            self,
            base_logits: torch.Tensor,
            target_ids: torch.Tensor,
            retrieval_scores: Optional[torch.Tensor] = None,
            penalty_scores: Optional[torch.Tensor] = None,
            alpha: float = 1.0,
            beta: float = 1.0,
        ) -> Dict[str, BenchmarkMetrics]:
            """Run full 4-condition ablation.

            Args:
                base_logits: [N, V] base logits.
                target_ids: [N] ground-truth.
                retrieval_scores: [N, V] retrieval scores.
                penalty_scores: [N, V] penalty scores.
                alpha: Retrieval weight.
                beta: Penalty weight.

            Returns:
                results: Dict mapping condition name to metrics.
            """
            results = {}

            for mode in ModulationMode.all_modes():
                config = ModulationMode.get_config(mode, alpha=alpha, beta=beta)

                r_scores = retrieval_scores if config.enable_retrieval else None
                p_scores = penalty_scores if config.enable_penalty else None

                metrics = self.evaluate_condition(
                    base_logits=base_logits,
                    target_ids=target_ids,
                    config=config,
                    retrieval_scores=r_scores,
                    penalty_scores=p_scores,
                    condition_name=mode,
                )
                results[mode] = metrics

            return results

        def run_alpha_beta_sweep(
            self,
            base_logits: torch.Tensor,
            target_ids: torch.Tensor,
            retrieval_scores: Optional[torch.Tensor] = None,
            penalty_scores: Optional[torch.Tensor] = None,
            alpha_values: Optional[List[float]] = None,
            beta_values: Optional[List[float]] = None,
        ) -> SweepResult:
            """Run hyperparameter sweep over alpha and beta.

            Args:
                base_logits: [N, V] base logits.
                target_ids: [N] ground-truth.
                retrieval_scores: [N, V] retrieval scores.
                penalty_scores: [N, V] penalty scores.
                alpha_values: List of alpha values to try.
                beta_values: List of beta values to try.

            Returns:
                sweep: SweepResult with all (alpha, beta) combinations.
            """
            if alpha_values is None:
                alpha_values = [0.0, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0]
            if beta_values is None:
                beta_values = [0.0, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0]

            sweep = SweepResult(
                condition="retrieval_penalty",
                alpha_values=alpha_values,
                beta_values=beta_values,
            )

            for alpha in alpha_values:
                for beta in beta_values:
                    config = LogitModulationConfig(
                        alpha=alpha,
                        beta=beta,
                        enable_retrieval=(alpha > 0 and retrieval_scores is not None),
                        enable_penalty=(beta > 0 and penalty_scores is not None),
                    )

                    r_scores = retrieval_scores if config.enable_retrieval else None
                    p_scores = penalty_scores if config.enable_penalty else None

                    metrics = self.evaluate_condition(
                        base_logits=base_logits,
                        target_ids=target_ids,
                        config=config,
                        retrieval_scores=r_scores,
                        penalty_scores=p_scores,
                        condition_name=f"a={alpha:.2f}_b={beta:.2f}",
                    )
                    sweep.results.append(metrics)

            return sweep

        def generate_report(
            self, ablation: Dict[str, BenchmarkMetrics]
        ) -> str:
            """Generate a human-readable comparison report.

            Args:
                ablation: Dict from run_ablation().

            Returns:
                report: Formatted multi-line string.
            """
            lines = [
                "=" * 72,
                "LOGIT MODULATION BENCHMARK REPORT",
                "=" * 72,
                "",
                f"{'Condition':<25} {'pass@1':>8} {'ECE':>8} {'Brier':>8} {'Spearman':>9} {'N':>6}",
                "-" * 72,
            ]

            baseline_pass1 = None
            for name, m in ablation.items():
                if name == ModulationMode.BASELINE:
                    baseline_pass1 = m.pass_at_1
                lines.append(
                    f"{m.condition:<25} {m.pass_at_1:>8.4f} {m.ece:>8.4f} "
                    f"{m.brier:>8.4f} {m.spearman:>9.4f} {m.n_samples:>6d}"
                )

            lines.append("-" * 72)

            # Verdict
            if baseline_pass1 is not None:
                best_name = None
                best_pass1 = baseline_pass1
                for name, m in ablation.items():
                    if m.pass_at_1 > best_pass1:
                        best_pass1 = m.pass_at_1
                        best_name = name

                if best_name is not None:
                    delta = best_pass1 - baseline_pass1
                    lines.append(
                        f"\nVERDICT: {best_name} IMPROVES over baseline "
                        f"by +{delta:.4f} pass@1"
                    )
                else:
                    lines.append(
                        "\nVERDICT: Logit modulation does NOT improve "
                        "over baseline on this dataset."
                    )

            # ECE comparison
            best_ece_name = min(ablation.items(), key=lambda x: x[1].ece)
            lines.append(
                f"Best calibration: {best_ece_name[0]} "
                f"(ECE={best_ece_name[1].ece:.4f})"
            )

            lines.append("=" * 72)
            return "\n".join(lines)

        def generate_sweep_report(self, sweep: SweepResult) -> str:
            """Generate report for alpha/beta sweep.

            Args:
                sweep: SweepResult from run_alpha_beta_sweep().

            Returns:
                report: Formatted string.
            """
            lines = [
                "=" * 72,
                "ALPHA/BETA SWEEP RESULTS",
                "=" * 72,
                "",
                f"{'alpha':>8} {'beta':>8} {'pass@1':>8} {'ECE':>8} {'Brier':>8} {'Spearman':>9}",
                "-" * 72,
            ]

            for m in sweep.results:
                lines.append(
                    f"{m.alpha:>8.2f} {m.beta:>8.2f} {m.pass_at_1:>8.4f} "
                    f"{m.ece:>8.4f} {m.brier:>8.4f} {m.spearman:>9.4f}"
                )

            lines.append("-" * 72)

            best = sweep.best_by_pass_at_1()
            if best:
                lines.append(
                    f"Best pass@1: α={best.alpha:.2f}, β={best.beta:.2f} "
                    f"→ {best.pass_at_1:.4f}"
                )

            best_ece = sweep.best_by_ece()
            if best_ece:
                lines.append(
                    f"Best ECE: α={best_ece.alpha:.2f}, β={best_ece.beta:.2f} "
                    f"→ {best_ece.ece:.4f}"
                )

            lines.append("=" * 72)
            return "\n".join(lines)

        def save_results(
            self,
            ablation: Dict[str, BenchmarkMetrics],
            path: str,
            sweep: Optional[SweepResult] = None,
        ) -> None:
            """Save results to JSON.

            Args:
                ablation: Dict from run_ablation().
                path: Output file path.
                sweep: Optional SweepResult.
            """
            data: Dict[str, Any] = {
                "ablation": {k: v.to_dict() for k, v in ablation.items()},
            }
            if sweep is not None:
                data["sweep"] = [m.to_dict() for m in sweep.results]
                best = sweep.best_by_pass_at_1()
                if best:
                    data["sweep_best_pass_at_1"] = best.to_dict()

            Path(path).write_text(json.dumps(data, indent=2))

else:

    class LogitModulationBenchmark:  # type: ignore[no-redef]
        pass
