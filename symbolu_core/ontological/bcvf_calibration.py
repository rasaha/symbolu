#!/usr/bin/env python3
"""
BCVF Calibration Metrics
=========================

Proper calibration metrics for evaluating the controlled decoding
pipeline.  A well-calibrated model predicts "80% confident" and is
correct ~80% of the time.

Metrics implemented:

    ECE  – Expected Calibration Error (lower is better).
           Weighted average of |accuracy − confidence| across bins.

    Brier – Brier Score (lower is better).
            Mean squared error between predicted confidence and binary
            correctness.

    Reliability bins – Raw (confidence, accuracy, count) triples for
                       reliability diagram plotting.

    Confidence–correctness correlation – Spearman rank correlation
                                         between confidence and
                                         correctness.

Usage::

    from symbolu_core.ontological.bcvf_calibration import (
        compute_ece,
        compute_brier,
        reliability_bins,
        CalibrationTracker,
    )

    tracker = CalibrationTracker()
    for sample in dataset:
        tracker.update(confidence=0.85, correct=True)

    report = tracker.report()
    print(report)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

try:
    import torch

    PYTORCH_AVAILABLE = True
except ImportError:
    PYTORCH_AVAILABLE = False

import numpy as np


# =========================================================================
# Core metric functions (numpy-based, framework-agnostic)
# =========================================================================


def _rank_with_ties(arr: np.ndarray) -> np.ndarray:
    """
    Compute average ranks for array elements, handling ties.

    Equivalent to scipy.stats.rankdata(arr, method='average').
    """
    arr = np.asarray(arr, dtype=np.float64)
    n = len(arr)
    order = np.argsort(arr, kind="mergesort")
    ranks = np.empty(n, dtype=np.float64)
    i = 0
    while i < n:
        j = i
        while j < n - 1 and arr[order[j + 1]] == arr[order[j]]:
            j += 1
        avg_rank = 0.5 * (i + j) + 1.0  # 1-based average
        for k in range(i, j + 1):
            ranks[order[k]] = avg_rank
        i = j + 1
    return ranks


def spearman_rank_correlation(
    x: np.ndarray,
    y: np.ndarray,
) -> float:
    """
    Spearman rank correlation between two arrays (pure numpy, no scipy).

    Computes Pearson correlation of the rank-transformed arrays,
    handling ties via average-rank assignment.

    Args:
        x: 1-D numeric array.
        y: 1-D numeric array of same length.

    Returns:
        Spearman rho in [-1, 1].  Returns 0.0 if input is too
        short (< 3) or either array is constant.
    """
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    if len(x) < 3 or len(x) != len(y):
        return 0.0
    if np.std(x) < 1e-8 or np.std(y) < 1e-8:
        return 0.0

    rx = _rank_with_ties(x)
    ry = _rank_with_ties(y)

    # Pearson of ranks
    rx_centered = rx - rx.mean()
    ry_centered = ry - ry.mean()
    num = np.dot(rx_centered, ry_centered)
    denom = np.sqrt(np.dot(rx_centered, rx_centered) * np.dot(ry_centered, ry_centered))
    if denom < 1e-12:
        return 0.0
    return float(num / denom)


def compute_ece(
    confidences: np.ndarray,
    correctness: np.ndarray,
    n_bins: int = 10,
) -> float:
    """
    Expected Calibration Error.

    Partitions predictions into ``n_bins`` equal-width confidence bins
    and computes the weighted average of |accuracy − confidence|.

    Args:
        confidences: 1-D array of predicted confidences in [0, 1].
        correctness: 1-D binary array (1 = correct, 0 = wrong).
        n_bins: Number of equal-width bins.

    Returns:
        ECE value in [0, 1].  Lower is better.
    """
    confidences = np.asarray(confidences, dtype=np.float64)
    correctness = np.asarray(correctness, dtype=np.float64)
    N = len(confidences)
    if N == 0:
        return 0.0

    bin_edges = np.linspace(0.0, 1.0, n_bins + 1)
    ece = 0.0

    for idx, (lo, hi) in enumerate(zip(bin_edges[:-1], bin_edges[1:])):
        if idx == n_bins - 1:
            # Last bin is closed on both sides to include 1.0
            mask = (confidences >= lo) & (confidences <= hi)
        else:
            mask = (confidences >= lo) & (confidences < hi)
        count = mask.sum()
        if count == 0:
            continue
        acc = correctness[mask].mean()
        conf = confidences[mask].mean()
        ece += (count / N) * abs(acc - conf)

    return float(ece)


def compute_brier(
    confidences: np.ndarray,
    correctness: np.ndarray,
) -> float:
    """
    Brier Score – mean squared error between confidence and correctness.

    Args:
        confidences: 1-D array in [0, 1].
        correctness: 1-D binary array (1 = correct, 0 = wrong).

    Returns:
        Brier score in [0, 1].  Lower is better.
    """
    confidences = np.asarray(confidences, dtype=np.float64)
    correctness = np.asarray(correctness, dtype=np.float64)
    if len(confidences) == 0:
        return 0.0
    return float(np.mean((confidences - correctness) ** 2))


def reliability_bins(
    confidences: np.ndarray,
    correctness: np.ndarray,
    n_bins: int = 10,
) -> List[Tuple[float, float, int]]:
    """
    Raw reliability diagram data.

    Returns a list of ``(mean_confidence, accuracy, count)`` tuples,
    one per non-empty bin.  Plot ``mean_confidence`` on the x-axis and
    ``accuracy`` on the y-axis for a reliability diagram.

    Args:
        confidences: 1-D array in [0, 1].
        correctness: 1-D binary array.
        n_bins: Number of equal-width bins.

    Returns:
        List of (confidence, accuracy, count) tuples.
    """
    confidences = np.asarray(confidences, dtype=np.float64)
    correctness = np.asarray(correctness, dtype=np.float64)
    bin_edges = np.linspace(0.0, 1.0, n_bins + 1)
    results: List[Tuple[float, float, int]] = []

    for idx, (lo, hi) in enumerate(zip(bin_edges[:-1], bin_edges[1:])):
        if idx == n_bins - 1:
            mask = (confidences >= lo) & (confidences <= hi)
        else:
            mask = (confidences >= lo) & (confidences < hi)
        count = int(mask.sum())
        if count > 0:
            acc = float(correctness[mask].mean())
            conf = float(confidences[mask].mean())
            results.append((conf, acc, count))

    return results


def compute_auroc(
    scores: np.ndarray,
    labels: np.ndarray,
) -> float:
    """
    Area Under the ROC Curve (pure numpy, no sklearn).

    Computes AUROC using the Mann-Whitney U statistic formulation:

        AUROC = U / (n_pos * n_neg)

    where U counts the number of (positive, negative) pairs where
    the positive sample has a higher score than the negative sample,
    with ties counting as 0.5.

    Args:
        scores: 1-D array of real-valued scores (higher = more likely positive).
        labels: 1-D binary array (1 = positive, 0 = negative).

    Returns:
        AUROC in [0, 1].  Returns 0.5 if input is degenerate
        (all-same labels, empty, or all-same scores).
    """
    scores = np.asarray(scores, dtype=np.float64)
    labels = np.asarray(labels, dtype=np.float64)
    if len(scores) < 2 or len(scores) != len(labels):
        return 0.5
    n_pos = labels.sum()
    n_neg = len(labels) - n_pos
    if n_pos == 0 or n_neg == 0:
        return 0.5

    # Sort by score descending
    order = np.argsort(-scores)
    sorted_labels = labels[order]

    # Compute via trapezoidal ROC integration
    # Walk through sorted scores, accumulate TPR/FPR
    tp = 0.0
    fp = 0.0
    auc = 0.0
    prev_tp = 0.0
    prev_fp = 0.0

    sorted_scores = scores[order]
    i = 0
    n = len(sorted_scores)
    while i < n:
        # Find block of tied scores
        j = i
        while j < n and sorted_scores[j] == sorted_scores[i]:
            if sorted_labels[j] == 1.0:
                tp += 1.0
            else:
                fp += 1.0
            j += 1
        # Trapezoidal area for this block
        auc += (fp - prev_fp) * (tp + prev_tp) / 2.0
        prev_tp = tp
        prev_fp = fp
        i = j

    # Normalize
    if n_pos * n_neg == 0:
        return 0.5
    return float(auc / (n_pos * n_neg))


def compute_auroc_combined(
    scores_a: np.ndarray,
    scores_b: np.ndarray,
    labels: np.ndarray,
) -> float:
    """
    AUROC of a combined linear model: w*scores_a + (1-w)*scores_b.

    Finds the optimal weight w in [0, 1] by grid search (21 points)
    and returns the best AUROC.  This tests whether the two score
    sources contain orthogonal signal.

    If AUROC(combined) > max(AUROC(a), AUROC(b)), the signals are
    complementary and combining them is justified.

    Args:
        scores_a: 1-D array (e.g. logit confidence).
        scores_b: 1-D array (e.g. sb score).
        labels: 1-D binary array (1 = correct, 0 = wrong).

    Returns:
        Best AUROC achievable by the linear combination.
    """
    scores_a = np.asarray(scores_a, dtype=np.float64)
    scores_b = np.asarray(scores_b, dtype=np.float64)
    labels = np.asarray(labels, dtype=np.float64)

    if len(scores_a) < 2:
        return 0.5

    # Normalize each to [0, 1] for fair combination
    def _normalize(x: np.ndarray) -> np.ndarray:
        r = x.max() - x.min()
        if r < 1e-12:
            return np.full_like(x, 0.5)
        return (x - x.min()) / r

    a_norm = _normalize(scores_a)
    b_norm = _normalize(scores_b)

    best_auroc = 0.5
    for w_int in range(21):  # w = 0.0, 0.05, ..., 1.0
        w = w_int / 20.0
        combined = w * a_norm + (1.0 - w) * b_norm
        auc = compute_auroc(combined, labels)
        if auc > best_auroc:
            best_auroc = auc

    return best_auroc


def confidence_correctness_correlation(
    confidences: np.ndarray,
    correctness: np.ndarray,
) -> float:
    """
    Spearman rank correlation between confidence and correctness.

    A positive value means higher confidence correlates with being
    correct — which is what a well-calibrated model should show.

    Returns 0.0 if input is too short or constant.
    """
    return spearman_rank_correlation(confidences, correctness)


# =========================================================================
# PyTorch-native wrappers
# =========================================================================

if PYTORCH_AVAILABLE:

    def compute_ece_torch(
        confidences: torch.Tensor,
        correctness: torch.Tensor,
        n_bins: int = 10,
    ) -> float:
        """ECE from PyTorch tensors (detached to numpy internally)."""
        return compute_ece(
            confidences.detach().cpu().numpy(),
            correctness.detach().cpu().numpy(),
            n_bins,
        )

    def compute_brier_torch(
        confidences: torch.Tensor,
        correctness: torch.Tensor,
    ) -> float:
        """Brier score from PyTorch tensors."""
        return compute_brier(
            confidences.detach().cpu().numpy(),
            correctness.detach().cpu().numpy(),
        )

    def reliability_bins_torch(
        confidences: torch.Tensor,
        correctness: torch.Tensor,
        n_bins: int = 10,
    ) -> List[Tuple[float, float, int]]:
        """Reliability bins from PyTorch tensors."""
        return reliability_bins(
            confidences.detach().cpu().numpy(),
            correctness.detach().cpu().numpy(),
            n_bins,
        )


# =========================================================================
# Stateful Tracker
# =========================================================================


@dataclass
class CalibrationTracker:
    """
    Accumulates predictions over an evaluation run and computes
    calibration metrics on demand.

    Usage::

        tracker = CalibrationTracker()
        for pred in predictions:
            tracker.update(confidence=pred.conf, correct=pred.ok)
        print(tracker.report())
    """

    confidences: List[float] = field(default_factory=list)
    correctness: List[int] = field(default_factory=list)
    # Per-tier tracking
    tier_counts: Dict[str, int] = field(
        default_factory=lambda: {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
    )
    tier_correct: Dict[str, int] = field(
        default_factory=lambda: {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
    )

    def update(
        self,
        confidence: float,
        correct: bool,
        confidence_level: Optional[str] = None,
    ) -> None:
        """Record one prediction."""
        self.confidences.append(float(confidence))
        self.correctness.append(1 if correct else 0)

        if confidence_level is not None:
            tier = confidence_level.upper()
            if tier in self.tier_counts:
                self.tier_counts[tier] += 1
                if correct:
                    self.tier_correct[tier] += 1

    def ece(self, n_bins: int = 10) -> float:
        return compute_ece(
            np.array(self.confidences),
            np.array(self.correctness),
            n_bins,
        )

    def brier(self) -> float:
        return compute_brier(
            np.array(self.confidences),
            np.array(self.correctness),
        )

    def reliability(self, n_bins: int = 10) -> List[Tuple[float, float, int]]:
        return reliability_bins(
            np.array(self.confidences),
            np.array(self.correctness),
            n_bins,
        )

    def accuracy(self) -> float:
        if not self.correctness:
            return 0.0
        return sum(self.correctness) / len(self.correctness)

    def tier_accuracy(self) -> Dict[str, float]:
        """Per-tier accuracy (HIGH/MEDIUM/LOW)."""
        result: Dict[str, float] = {}
        for tier in ("HIGH", "MEDIUM", "LOW"):
            total = self.tier_counts[tier]
            if total > 0:
                result[tier] = self.tier_correct[tier] / total
            else:
                result[tier] = 0.0
        return result

    def report(self, n_bins: int = 10) -> Dict[str, object]:
        """
        Produce a full calibration report.

        Returns dict with keys:
            n, accuracy, ece, brier, tier_accuracy,
            tier_distribution, reliability_bins
        """
        n = len(self.confidences)
        total = sum(self.tier_counts.values())
        tier_dist = {
            k: v / total if total > 0 else 0.0
            for k, v in self.tier_counts.items()
        }
        return {
            "n": n,
            "accuracy": self.accuracy(),
            "ece": self.ece(n_bins),
            "brier": self.brier(),
            "tier_accuracy": self.tier_accuracy(),
            "tier_distribution": tier_dist,
            "reliability_bins": self.reliability(n_bins),
        }

    def reset(self) -> None:
        self.confidences.clear()
        self.correctness.clear()
        for k in self.tier_counts:
            self.tier_counts[k] = 0
            self.tier_correct[k] = 0
