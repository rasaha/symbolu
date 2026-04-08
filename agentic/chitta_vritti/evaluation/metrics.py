"""Metrics computation for Chitta-Vṛtti evaluation.

Provides calibration, detection, and correlation metrics to quantify
the relationship between Chitta-Vṛtti signals and reasoning quality.
"""

import math
from typing import Optional
import numpy as np

from agentic.chitta_vritti.evaluation.types import (
    EvaluationSample,
    EvaluationBatch,
    CalibrationResult,
    DetectionResult,
    CorrelationResult,
)


class MetricsComputer:
    """Computes evaluation metrics from labeled samples.

    Provides three categories of metrics:
    1. Calibration: How well does score predict correctness probability?
    2. Detection: How well does viparyaya detect errors?
    3. Correlation: Linear/rank relationships between signals and outcomes
    """

    def __init__(self, num_calibration_bins: int = 10) -> None:
        """Initialize metrics computer.

        Args:
            num_calibration_bins: Number of bins for calibration analysis
        """
        self._num_bins = num_calibration_bins

    def compute_calibration(
        self,
        samples: list[EvaluationSample],
        score_field: str = "score",
    ) -> CalibrationResult:
        """Compute calibration metrics.

        Calibration measures P(correct | predicted_score).
        A well-calibrated system has accuracy matching the score.

        Args:
            samples: Labeled evaluation samples
            score_field: Which field to use as prediction ("score" or "coherence")

        Returns:
            CalibrationResult with ECE, MCE, Brier score
        """
        labeled = [s for s in samples if s.is_labeled()]
        if not labeled:
            return CalibrationResult()

        # Extract scores and outcomes
        scores = []
        outcomes = []
        for s in labeled:
            score = getattr(s, score_field, s.score)
            scores.append(score)
            outcomes.append(1.0 if s.is_correct() else 0.0)

        scores = np.array(scores)
        outcomes = np.array(outcomes)

        # Bin samples by score
        bin_edges = np.linspace(0, 1, self._num_bins + 1)
        bin_indices = np.digitize(scores, bin_edges[1:-1])

        threshold_accuracy = {}
        bin_counts = {}
        calibration_errors = []
        weights = []

        for bin_idx in range(self._num_bins):
            mask = bin_indices == bin_idx
            bin_size = mask.sum()

            if bin_size == 0:
                continue

            bin_scores = scores[mask]
            bin_outcomes = outcomes[mask]

            # Average score and accuracy in this bin
            avg_score = bin_scores.mean()
            accuracy = bin_outcomes.mean()

            # Store threshold → accuracy mapping
            threshold = bin_edges[bin_idx]
            threshold_accuracy[float(threshold)] = float(accuracy)
            bin_counts[float(threshold)] = int(bin_size)

            # Calibration error for this bin
            error = abs(accuracy - avg_score)
            calibration_errors.append(error)
            weights.append(bin_size)

        # Compute summary metrics
        if calibration_errors:
            weights = np.array(weights)
            calibration_errors = np.array(calibration_errors)

            ece = float(np.average(calibration_errors, weights=weights))
            mce = float(np.max(calibration_errors))
        else:
            ece = 0.0
            mce = 0.0

        # Brier score: mean squared error of probabilistic predictions
        brier = float(np.mean((scores - outcomes) ** 2))

        return CalibrationResult(
            threshold_accuracy=threshold_accuracy,
            expected_calibration_error=ece,
            max_calibration_error=mce,
            brier_score=brier,
            bin_counts=bin_counts,
        )

    def compute_detection(
        self,
        samples: list[EvaluationSample],
        viparyaya_threshold: float = 0.3,
    ) -> DetectionResult:
        """Compute error detection metrics.

        Evaluates viparyaya as a binary classifier for errors.

        Args:
            samples: Labeled evaluation samples
            viparyaya_threshold: Threshold for "high viparyaya"

        Returns:
            DetectionResult with TPR, FPR, precision, recall, F1, AUC
        """
        labeled = [s for s in samples if s.is_labeled()]
        if not labeled:
            return DetectionResult(viparyaya_threshold=viparyaya_threshold)

        # Extract viparyaya values and error labels
        viparyaya_values = []
        is_error = []

        for s in labeled:
            vip = s.vritti.get("viparyaya", 0.0)
            viparyaya_values.append(vip)
            is_error.append(s.is_error())

        viparyaya_values = np.array(viparyaya_values)
        is_error = np.array(is_error)

        # Binary predictions
        predicted_error = viparyaya_values >= viparyaya_threshold

        # Confusion matrix
        tp = int(np.sum(predicted_error & is_error))
        fp = int(np.sum(predicted_error & ~is_error))
        tn = int(np.sum(~predicted_error & ~is_error))
        fn = int(np.sum(~predicted_error & is_error))

        # Metrics
        tpr = tp / max(1, tp + fn)  # Recall / Sensitivity
        fpr = fp / max(1, fp + tn)  # Fall-out
        precision = tp / max(1, tp + fp)
        recall = tpr

        if precision + recall > 0:
            f1 = 2 * precision * recall / (precision + recall)
        else:
            f1 = 0.0

        # AUC-ROC computation (trapezoidal rule)
        auc = self._compute_auc(viparyaya_values, is_error)

        return DetectionResult(
            viparyaya_threshold=viparyaya_threshold,
            true_positive_rate=float(tpr),
            false_positive_rate=float(fpr),
            precision=float(precision),
            recall=float(recall),
            f1_score=float(f1),
            auc_roc=float(auc),
            true_positives=tp,
            false_positives=fp,
            true_negatives=tn,
            false_negatives=fn,
        )

    def compute_correlation(
        self,
        samples: list[EvaluationSample],
    ) -> CorrelationResult:
        """Compute correlation metrics.

        Measures linear and rank correlations between CV signals
        and correctness/error outcomes.

        Args:
            samples: Labeled evaluation samples

        Returns:
            CorrelationResult with Pearson/Spearman correlations and p-values
        """
        labeled = [s for s in samples if s.is_labeled()]
        if len(labeled) < 3:  # Need minimum samples for correlation
            return CorrelationResult()

        # Extract values
        coherence = np.array([s.coherence for s in labeled])
        score = np.array([s.score for s in labeled])
        correct = np.array([1.0 if s.is_correct() else 0.0 for s in labeled])
        error = np.array([1.0 if s.is_error() else 0.0 for s in labeled])

        # Viparyaya values
        viparyaya = np.array([s.vritti.get("viparyaya", 0.0) for s in labeled])

        # Pearson correlations
        coh_corr, coh_p = self._pearson_with_pvalue(coherence, correct)
        score_corr, score_p = self._pearson_with_pvalue(score, correct)
        vip_corr, vip_p = self._pearson_with_pvalue(viparyaya, error)

        # Spearman correlations
        coh_spearman = self._spearman(coherence, correct)
        score_spearman = self._spearman(score, correct)
        vip_spearman = self._spearman(viparyaya, error)

        # Per-vṛtti correlations with error
        vritti_correlations = {}
        for mode in ["pramana", "viparyaya", "vikalpa", "smrti", "nidra"]:
            values = np.array([s.vritti.get(mode, 0.0) for s in labeled])
            corr, _ = self._pearson_with_pvalue(values, error)
            vritti_correlations[mode] = float(corr)

        return CorrelationResult(
            coherence_vs_correct=float(coh_corr),
            score_vs_correct=float(score_corr),
            viparyaya_vs_error=float(vip_corr),
            coherence_vs_correct_spearman=float(coh_spearman),
            score_vs_correct_spearman=float(score_spearman),
            viparyaya_vs_error_spearman=float(vip_spearman),
            coherence_pvalue=float(coh_p),
            score_pvalue=float(score_p),
            viparyaya_pvalue=float(vip_p),
            vritti_correlations=vritti_correlations,
        )

    def compute_vritti_distribution(
        self,
        samples: list[EvaluationSample],
    ) -> tuple[dict[str, float], dict[str, float]]:
        """Compute average vṛtti distribution for errors vs correct.

        Args:
            samples: Labeled evaluation samples

        Returns:
            Tuple of (vritti_in_errors, vritti_in_correct)
        """
        correct_samples = [s for s in samples if s.is_correct()]
        error_samples = [s for s in samples if s.is_error()]

        vritti_in_correct = self._average_vritti(correct_samples)
        vritti_in_errors = self._average_vritti(error_samples)

        return vritti_in_errors, vritti_in_correct

    def _average_vritti(self, samples: list[EvaluationSample]) -> dict[str, float]:
        """Compute average vṛtti distribution across samples."""
        if not samples:
            return {}

        modes = ["pramana", "viparyaya", "vikalpa", "smrti", "nidra"]
        totals = {m: 0.0 for m in modes}

        for s in samples:
            for m in modes:
                totals[m] += s.vritti.get(m, 0.0)

        n = len(samples)
        return {m: totals[m] / n for m in modes}

    def _compute_auc(self, scores: np.ndarray, labels: np.ndarray) -> float:
        """Compute AUC-ROC using trapezoidal rule."""
        if len(scores) < 2:
            return 0.5

        # Sort by score descending
        order = np.argsort(-scores)
        sorted_labels = labels[order]
        sorted_scores = scores[order]

        # Compute TPR and FPR at each threshold
        n_pos = labels.sum()
        n_neg = len(labels) - n_pos

        if n_pos == 0 or n_neg == 0:
            return 0.5

        tpr_list = [0.0]
        fpr_list = [0.0]

        tp = 0
        fp = 0

        for i, label in enumerate(sorted_labels):
            if label:
                tp += 1
            else:
                fp += 1

            tpr_list.append(tp / n_pos)
            fpr_list.append(fp / n_neg)

        # Trapezoidal AUC
        auc = 0.0
        for i in range(1, len(fpr_list)):
            auc += (fpr_list[i] - fpr_list[i - 1]) * (tpr_list[i] + tpr_list[i - 1]) / 2

        return auc

    def _pearson_with_pvalue(
        self, x: np.ndarray, y: np.ndarray
    ) -> tuple[float, float]:
        """Compute Pearson correlation with p-value."""
        n = len(x)
        if n < 3:
            return 0.0, 1.0

        # Correlation coefficient
        x_mean = x.mean()
        y_mean = y.mean()

        x_centered = x - x_mean
        y_centered = y - y_mean

        numerator = np.sum(x_centered * y_centered)
        denominator = np.sqrt(np.sum(x_centered**2) * np.sum(y_centered**2))

        if denominator < 1e-10:
            return 0.0, 1.0

        r = numerator / denominator
        r = np.clip(r, -1.0, 1.0)

        # t-statistic and p-value
        if abs(r) >= 1.0:
            return float(r), 0.0

        t = r * np.sqrt((n - 2) / (1 - r**2))
        # Approximate p-value using normal distribution for large n
        p = 2 * (1 - self._normal_cdf(abs(t)))

        return float(r), float(p)

    def _spearman(self, x: np.ndarray, y: np.ndarray) -> float:
        """Compute Spearman rank correlation."""
        n = len(x)
        if n < 3:
            return 0.0

        # Convert to ranks
        x_ranks = self._rank(x)
        y_ranks = self._rank(y)

        # Pearson on ranks
        corr, _ = self._pearson_with_pvalue(x_ranks, y_ranks)
        return corr

    def _rank(self, x: np.ndarray) -> np.ndarray:
        """Convert values to ranks (average rank for ties)."""
        order = np.argsort(x)
        ranks = np.zeros_like(x, dtype=float)

        i = 0
        while i < len(x):
            j = i
            while j < len(x) and x[order[j]] == x[order[i]]:
                j += 1
            avg_rank = (i + j + 1) / 2.0
            for k in range(i, j):
                ranks[order[k]] = avg_rank
            i = j

        return ranks

    def _normal_cdf(self, x: float) -> float:
        """Approximate standard normal CDF."""
        return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def find_optimal_threshold(
    samples: list[EvaluationSample],
    metric: str = "f1",
    thresholds: Optional[list[float]] = None,
) -> tuple[float, float]:
    """Find optimal viparyaya threshold for error detection.

    Args:
        samples: Labeled evaluation samples
        metric: Metric to optimize ("f1", "precision", "recall", "balanced")
        thresholds: List of thresholds to try (default: 0.05 to 0.5)

    Returns:
        Tuple of (optimal_threshold, metric_value)
    """
    if thresholds is None:
        thresholds = [i * 0.05 for i in range(1, 11)]  # 0.05 to 0.5

    computer = MetricsComputer()
    best_threshold = 0.3
    best_value = 0.0

    for threshold in thresholds:
        result = computer.compute_detection(samples, threshold)

        if metric == "f1":
            value = result.f1_score
        elif metric == "precision":
            value = result.precision
        elif metric == "recall":
            value = result.recall
        elif metric == "balanced":
            # Balanced accuracy: (TPR + TNR) / 2
            value = (result.true_positive_rate + result.specificity()) / 2
        else:
            value = result.f1_score

        if value > best_value:
            best_value = value
            best_threshold = threshold

    return best_threshold, best_value
