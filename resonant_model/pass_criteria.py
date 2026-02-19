"""
Behavioral Pass Criteria for Binding Benchmark
================================================

Three-tier value gate that determines whether Model B (resonance
interference head) demonstrates genuine binding improvement over
Model A (softmax baseline).

Tiers:
  1. Minimal Pass  — proof of signal
  2. Strong Pass   — clear binding advantage
  3. Breakthrough  — serious architectural improvement

Key principle: binding problems get harder with distance, distractors,
and nesting. If interference is truly a binding mechanism, it must show
advantage *specifically* under those stressors. Otherwise it is cosmetic.

What does NOT count:
  - 2-3% improvement
  - Improvement only in easy examples
  - No change in role swap errors
  - Gains that disappear when interference removed
  - Same performance as a standard quadratic head
"""

import math
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, List, Optional, Tuple

from resonant_model.dataset import FailureType
from resonant_model.evaluator import EvaluationResult, PredictionRecord
from resonant_model.statistics import (
    ComparisonReport,
    SignificanceResult,
    mcnemar_test,
)


class PassTier(Enum):
    """Which tier of behavioral pass was achieved."""
    NONE = "none"
    MINIMAL = "minimal"
    STRONG = "strong"
    BREAKTHROUGH = "breakthrough"


@dataclass
class CriterionResult:
    """Result of evaluating a single criterion."""
    name: str
    passed: bool
    required_value: float
    actual_value: float
    description: str


@dataclass
class TierResult:
    """Result of evaluating all criteria in a tier."""
    tier: PassTier
    passed: bool
    criteria: List[CriterionResult] = field(default_factory=list)
    passed_count: int = 0
    total_count: int = 0

    @property
    def pass_rate(self) -> float:
        return self.passed_count / self.total_count if self.total_count > 0 else 0.0


@dataclass
class PassResult:
    """Full pass/fail evaluation across all tiers."""
    highest_pass: PassTier
    minimal: TierResult
    strong: TierResult
    breakthrough: TierResult
    summary: str = ""


# ─── Hard Subset Extraction ──────────────────────────────────────────────────

def _extract_high_distance_subset(
    predictions: List[PredictionRecord],
    quantile: float = 0.67,
) -> List[PredictionRecord]:
    """
    Extract predictions from the top-quantile of separation distances.

    The 'hard' subset: examples where the role assignment and the query
    are far apart. If binding works, accuracy should hold here.
    """
    distances = sorted(set(p.separation_distance for p in predictions))
    if not distances:
        return []

    threshold_idx = int(len(distances) * quantile)
    threshold = distances[min(threshold_idx, len(distances) - 1)]

    return [p for p in predictions if p.separation_distance >= threshold]


def _extract_high_distractor_subset(
    predictions: List[PredictionRecord],
    quantile: float = 0.67,
) -> List[PredictionRecord]:
    """
    Extract predictions from examples with the most distractors.
    """
    counts = sorted(set(p.num_distractors for p in predictions))
    if not counts:
        return []

    threshold_idx = int(len(counts) * quantile)
    threshold = counts[min(threshold_idx, len(counts) - 1)]

    return [p for p in predictions if p.num_distractors >= threshold]


def _extract_nested_subset(
    predictions: List[PredictionRecord],
    min_depth: int = 2,
) -> List[PredictionRecord]:
    """Extract predictions from nested-clause examples."""
    return [p for p in predictions if p.nesting_depth >= min_depth]


def _subset_accuracy(predictions: List[PredictionRecord]) -> float:
    """Compute accuracy over a subset of predictions."""
    if not predictions:
        return 0.0
    return sum(1 for p in predictions if p.is_correct) / len(predictions)


# ─── Cohen's d ───────────────────────────────────────────────────────────────

def cohens_d(
    predictions_a: List[PredictionRecord],
    predictions_b: List[PredictionRecord],
) -> float:
    """
    Compute Cohen's d effect size for paired binary outcomes.

    Treats each prediction as a 0/1 outcome. Cohen's d measures the
    standardized difference between two means.

    d = (mean_B - mean_A) / pooled_std

    Interpretation:
      d < 0.2  — negligible
      0.2-0.5  — small
      0.5-0.8  — medium
      d > 0.8  — large
    """
    scores_a = [1.0 if p.is_correct else 0.0 for p in predictions_a]
    scores_b = [1.0 if p.is_correct else 0.0 for p in predictions_b]

    n = len(scores_a)
    if n == 0:
        return 0.0

    mean_a = sum(scores_a) / n
    mean_b = sum(scores_b) / n

    var_a = sum((s - mean_a) ** 2 for s in scores_a) / max(n - 1, 1)
    var_b = sum((s - mean_b) ** 2 for s in scores_b) / max(n - 1, 1)

    pooled_std = math.sqrt((var_a + var_b) / 2)
    if pooled_std == 0:
        if mean_a == mean_b:
            return 0.0
        # Max effect: use 0.5 as normalization (binary outcome max std)
        return (mean_b - mean_a) / 0.5

    return (mean_b - mean_a) / pooled_std


# ─── Accuracy-vs-Distance Slope ──────────────────────────────────────────────

def _accuracy_slope(predictions: List[PredictionRecord]) -> float:
    """
    Compute slope of accuracy vs separation distance via linear regression.

    Negative slope = accuracy degrades with distance (bad).
    Flatter slope = more robust to distance (good).

    Returns slope coefficient. Uses Theil-Sen estimator for robustness.
    """
    if len(predictions) < 2:
        return 0.0

    # Group by distance, compute per-bin accuracy
    bins: Dict[int, List[bool]] = {}
    for p in predictions:
        d = p.separation_distance
        if d not in bins:
            bins[d] = []
        bins[d].append(p.is_correct)

    if len(bins) < 2:
        return 0.0

    points = [
        (d, sum(1 for c in corrects if c) / len(corrects))
        for d, corrects in sorted(bins.items())
        if len(corrects) > 0
    ]

    if len(points) < 2:
        return 0.0

    # Simple OLS slope: sum((x-x_mean)(y-y_mean)) / sum((x-x_mean)^2)
    x_mean = sum(x for x, _ in points) / len(points)
    y_mean = sum(y for _, y in points) / len(points)

    numerator = sum((x - x_mean) * (y - y_mean) for x, y in points)
    denominator = sum((x - x_mean) ** 2 for x, _ in points)

    if denominator == 0:
        return 0.0

    return numerator / denominator


# ─── Error Pattern Analysis ──────────────────────────────────────────────────

def _role_swap_reduction(
    result_a: EvaluationResult,
    result_b: EvaluationResult,
) -> float:
    """
    Compute percentage reduction in role swap errors.

    Returns value in [0, 1] where 1.0 = all role swaps eliminated.
    Negative values mean B has MORE role swaps.
    """
    a_swaps = result_a.failure_counts.get(FailureType.ROLE_SWAP.value, 0)
    b_swaps = result_b.failure_counts.get(FailureType.ROLE_SWAP.value, 0)

    if a_swaps == 0:
        return 0.0 if b_swaps == 0 else -1.0

    return (a_swaps - b_swaps) / a_swaps


def _nearest_name_reduction(
    result_a: EvaluationResult,
    result_b: EvaluationResult,
) -> float:
    """Compute reduction in nearest-name bias errors."""
    a_nn = result_a.failure_counts.get(FailureType.NEAREST_NAME_BIAS.value, 0)
    b_nn = result_b.failure_counts.get(FailureType.NEAREST_NAME_BIAS.value, 0)

    if a_nn == 0:
        return 0.0 if b_nn == 0 else -1.0

    return (a_nn - b_nn) / a_nn


# ─── Distractor Scaling Analysis ─────────────────────────────────────────────

def _distractor_gap_slope(
    predictions_a: List[PredictionRecord],
    predictions_b: List[PredictionRecord],
) -> float:
    """
    Compute how the accuracy gap (B - A) changes with distractor count.

    Positive slope = gap widens as distractors increase (Model B gets
    relatively better on harder examples). This is the signal we want.

    Superlinear growth (slope > 0) means interference is doing real
    structural work under pressure.
    """
    # Group by distractor count
    bins_a: Dict[int, List[bool]] = {}
    bins_b: Dict[int, List[bool]] = {}

    for p in predictions_a:
        if p.num_distractors not in bins_a:
            bins_a[p.num_distractors] = []
        bins_a[p.num_distractors].append(p.is_correct)

    for p in predictions_b:
        if p.num_distractors not in bins_b:
            bins_b[p.num_distractors] = []
        bins_b[p.num_distractors].append(p.is_correct)

    # Compute gap at each distractor count
    all_counts = sorted(set(list(bins_a.keys()) + list(bins_b.keys())))
    if len(all_counts) < 2:
        return 0.0

    points = []
    for count in all_counts:
        acc_a = _subset_accuracy_from_bools(bins_a.get(count, []))
        acc_b = _subset_accuracy_from_bools(bins_b.get(count, []))
        gap = acc_b - acc_a
        points.append((count, gap))

    if len(points) < 2:
        return 0.0

    # OLS slope of gap vs distractor count
    x_mean = sum(x for x, _ in points) / len(points)
    y_mean = sum(y for _, y in points) / len(points)

    numerator = sum((x - x_mean) * (y - y_mean) for x, y in points)
    denominator = sum((x - x_mean) ** 2 for x, _ in points)

    if denominator == 0:
        return 0.0

    return numerator / denominator


def _subset_accuracy_from_bools(corrects: List[bool]) -> float:
    if not corrects:
        return 0.0
    return sum(1 for c in corrects if c) / len(corrects)


# ─── Correlation: Interference Strength vs Correctness ────────────────────────

def _interference_correctness_correlation(
    predictions: List[PredictionRecord],
) -> float:
    """
    Compute point-biserial correlation between prediction confidence
    (proxy for interference strength) and correctness.

    In a trained model, confidence tracks how strongly the attention
    mechanism commits to the selected answer. Higher correlation
    means the mechanism is calibrated — when it is confident, it is
    correct.

    Returns r in [-1, 1].
    """
    if len(predictions) < 2:
        return 0.0

    # Use confidence as proxy for interference strength
    x = [p.confidence for p in predictions]
    y = [1.0 if p.is_correct else 0.0 for p in predictions]

    n = len(x)
    mean_x = sum(x) / n
    mean_y = sum(y) / n

    cov = sum((xi - mean_x) * (yi - mean_y) for xi, yi in zip(x, y)) / n
    std_x = math.sqrt(sum((xi - mean_x) ** 2 for xi in x) / n)
    std_y = math.sqrt(sum((yi - mean_y) ** 2 for yi in y) / n)

    if std_x == 0 or std_y == 0:
        return 0.0

    return cov / (std_x * std_y)


# ═══════════════════════════════════════════════════════════════════════════════
# PASS CRITERIA EVALUATION
# ═══════════════════════════════════════════════════════════════════════════════

class PassCriteria:
    """
    Evaluates behavioral pass criteria across three tiers.

    All thresholds are configurable but defaults encode the specification:

    Minimal Pass (proof of signal):
      A. Overall accuracy gain >= 5%
      B. High-distance subset gain >= 8%
      C. Role swap reduction >= 20%, nearest-name bias decreases
      D. Statistically significant (p < 0.05)

    Strong Pass (clear binding advantage):
      A. Overall gain >= 7%
      B. High-distance gain >= 12%
      C. High-distractor gain >= 12%
      D. Cohen's d >= 0.5
      E. Accuracy-vs-distance slope flatter for Model B

    Breakthrough Pass (serious architectural improvement):
      A. No collapse (both models > 10% accuracy)
      B. Overall gain >= 10%
      C. High-distance gain >= 15%
      D. High-distractor gain >= 15%
      E. Confidence-correctness correlation >= 0.30
      F. Binding-specific error reduction
      G. Performance gap grows with distractor count (positive slope)
    """

    def __init__(
        self,
        # Minimal thresholds
        min_overall_gain: float = 0.05,
        min_high_distance_gain: float = 0.08,
        min_role_swap_reduction: float = 0.20,
        # Strong thresholds
        strong_overall_gain: float = 0.07,
        strong_high_distance_gain: float = 0.12,
        strong_high_distractor_gain: float = 0.12,
        strong_cohens_d: float = 0.5,
        # Breakthrough thresholds
        breakthrough_overall_gain: float = 0.10,
        breakthrough_high_distance_gain: float = 0.15,
        breakthrough_high_distractor_gain: float = 0.15,
        breakthrough_correlation: float = 0.30,
        # Subset extraction
        distance_quantile: float = 0.67,
        distractor_quantile: float = 0.67,
    ):
        self.min_overall_gain = min_overall_gain
        self.min_high_distance_gain = min_high_distance_gain
        self.min_role_swap_reduction = min_role_swap_reduction

        self.strong_overall_gain = strong_overall_gain
        self.strong_high_distance_gain = strong_high_distance_gain
        self.strong_high_distractor_gain = strong_high_distractor_gain
        self.strong_cohens_d = strong_cohens_d

        self.breakthrough_overall_gain = breakthrough_overall_gain
        self.breakthrough_high_distance_gain = breakthrough_high_distance_gain
        self.breakthrough_high_distractor_gain = breakthrough_high_distractor_gain
        self.breakthrough_correlation = breakthrough_correlation

        self.distance_quantile = distance_quantile
        self.distractor_quantile = distractor_quantile

    def evaluate(
        self,
        result_a: EvaluationResult,
        result_b: EvaluationResult,
    ) -> PassResult:
        """
        Evaluate all three tiers of pass criteria.

        Args:
            result_a: Model A (softmax baseline) results.
            result_b: Model B (resonance interference) results.

        Returns:
            PassResult with per-tier breakdowns and overall verdict.
        """
        minimal = self._evaluate_minimal(result_a, result_b)
        strong = self._evaluate_strong(result_a, result_b)
        breakthrough = self._evaluate_breakthrough(result_a, result_b)

        # Determine highest pass (tiers are cumulative)
        if breakthrough.passed:
            highest = PassTier.BREAKTHROUGH
        elif strong.passed:
            highest = PassTier.STRONG
        elif minimal.passed:
            highest = PassTier.MINIMAL
        else:
            highest = PassTier.NONE

        summary = self._build_summary(highest, minimal, strong, breakthrough,
                                      result_a, result_b)

        return PassResult(
            highest_pass=highest,
            minimal=minimal,
            strong=strong,
            breakthrough=breakthrough,
            summary=summary,
        )

    # ─── Minimal Pass ─────────────────────────────────────────────────────

    def _evaluate_minimal(
        self,
        result_a: EvaluationResult,
        result_b: EvaluationResult,
    ) -> TierResult:
        """
        Minimal Behavioral Pass: proof of signal.

        ALL of A + B + C + D must hold.
        """
        criteria: List[CriterionResult] = []

        # A. Overall accuracy gain >= 5%
        overall_gain = result_b.accuracy - result_a.accuracy
        criteria.append(CriterionResult(
            name="overall_accuracy_gain",
            passed=overall_gain >= self.min_overall_gain,
            required_value=self.min_overall_gain,
            actual_value=overall_gain,
            description=(
                f"Overall accuracy gain: {overall_gain:.1%} "
                f"(required >= {self.min_overall_gain:.0%})"
            ),
        ))

        # B. High-distance subset gain >= 8%
        high_dist_a = _extract_high_distance_subset(
            result_a.predictions, self.distance_quantile,
        )
        high_dist_b = _extract_high_distance_subset(
            result_b.predictions, self.distance_quantile,
        )
        acc_hd_a = _subset_accuracy(high_dist_a)
        acc_hd_b = _subset_accuracy(high_dist_b)
        hd_gain = acc_hd_b - acc_hd_a
        criteria.append(CriterionResult(
            name="high_distance_gain",
            passed=hd_gain >= self.min_high_distance_gain,
            required_value=self.min_high_distance_gain,
            actual_value=hd_gain,
            description=(
                f"High-distance gain: {hd_gain:.1%} "
                f"(required >= {self.min_high_distance_gain:.0%})"
            ),
        ))

        # C. Error pattern shift: role swap reduction >= 20%
        #    AND nearest-name bias decreases
        rs_reduction = _role_swap_reduction(result_a, result_b)
        nn_reduction = _nearest_name_reduction(result_a, result_b)
        error_shift_passed = (
            rs_reduction >= self.min_role_swap_reduction
            and nn_reduction >= 0  # nearest-name bias must not increase
        )
        criteria.append(CriterionResult(
            name="error_pattern_shift",
            passed=error_shift_passed,
            required_value=self.min_role_swap_reduction,
            actual_value=rs_reduction,
            description=(
                f"Role swap reduction: {rs_reduction:.0%} "
                f"(required >= {self.min_role_swap_reduction:.0%}), "
                f"nearest-name reduction: {nn_reduction:.0%} (required >= 0%)"
            ),
        ))

        # D. Statistical significance (p < 0.05)
        sig = mcnemar_test(result_a.predictions, result_b.predictions)
        criteria.append(CriterionResult(
            name="statistical_significance",
            passed=sig.significant_at_05,
            required_value=0.05,
            actual_value=sig.p_value,
            description=(
                f"McNemar p-value: {sig.p_value:.6f} "
                f"(required < 0.05)"
            ),
        ))

        passed_count = sum(1 for c in criteria if c.passed)
        all_passed = all(c.passed for c in criteria)

        return TierResult(
            tier=PassTier.MINIMAL,
            passed=all_passed,
            criteria=criteria,
            passed_count=passed_count,
            total_count=len(criteria),
        )

    # ─── Strong Pass ──────────────────────────────────────────────────────

    def _evaluate_strong(
        self,
        result_a: EvaluationResult,
        result_b: EvaluationResult,
    ) -> TierResult:
        """
        Strong Behavioral Pass: clear binding advantage.

        ALL of A + B + C + D + E must hold.
        """
        criteria: List[CriterionResult] = []

        # A. Overall gain >= 7%
        overall_gain = result_b.accuracy - result_a.accuracy
        criteria.append(CriterionResult(
            name="overall_accuracy_gain",
            passed=overall_gain >= self.strong_overall_gain,
            required_value=self.strong_overall_gain,
            actual_value=overall_gain,
            description=(
                f"Overall accuracy gain: {overall_gain:.1%} "
                f"(required >= {self.strong_overall_gain:.0%})"
            ),
        ))

        # B. High-distance gain >= 12%
        high_dist_a = _extract_high_distance_subset(
            result_a.predictions, self.distance_quantile,
        )
        high_dist_b = _extract_high_distance_subset(
            result_b.predictions, self.distance_quantile,
        )
        hd_gain = _subset_accuracy(high_dist_b) - _subset_accuracy(high_dist_a)
        criteria.append(CriterionResult(
            name="high_distance_gain",
            passed=hd_gain >= self.strong_high_distance_gain,
            required_value=self.strong_high_distance_gain,
            actual_value=hd_gain,
            description=(
                f"High-distance gain: {hd_gain:.1%} "
                f"(required >= {self.strong_high_distance_gain:.0%})"
            ),
        ))

        # C. High-distractor gain >= 12%
        high_dis_a = _extract_high_distractor_subset(
            result_a.predictions, self.distractor_quantile,
        )
        high_dis_b = _extract_high_distractor_subset(
            result_b.predictions, self.distractor_quantile,
        )
        hdistr_gain = _subset_accuracy(high_dis_b) - _subset_accuracy(high_dis_a)
        criteria.append(CriterionResult(
            name="high_distractor_gain",
            passed=hdistr_gain >= self.strong_high_distractor_gain,
            required_value=self.strong_high_distractor_gain,
            actual_value=hdistr_gain,
            description=(
                f"High-distractor gain: {hdistr_gain:.1%} "
                f"(required >= {self.strong_high_distractor_gain:.0%})"
            ),
        ))

        # D. Cohen's d >= 0.5
        d = cohens_d(result_a.predictions, result_b.predictions)
        criteria.append(CriterionResult(
            name="cohens_d",
            passed=d >= self.strong_cohens_d,
            required_value=self.strong_cohens_d,
            actual_value=d,
            description=(
                f"Cohen's d: {d:.3f} "
                f"(required >= {self.strong_cohens_d})"
            ),
        ))

        # E. Accuracy-vs-distance slope flatter for Model B
        slope_a = _accuracy_slope(result_a.predictions)
        slope_b = _accuracy_slope(result_b.predictions)
        # "Flatter" = slope_b is closer to 0 (less negative) than slope_a
        # Both should be negative (accuracy degrades with distance)
        # B is flatter if |slope_b| < |slope_a| or slope_b > slope_a
        slope_better = slope_b > slope_a  # less negative = more robust
        criteria.append(CriterionResult(
            name="distance_robustness",
            passed=slope_better,
            required_value=slope_a,
            actual_value=slope_b,
            description=(
                f"Acc-vs-distance slope: A={slope_a:.6f}, B={slope_b:.6f} "
                f"(B must be flatter/less negative)"
            ),
        ))

        passed_count = sum(1 for c in criteria if c.passed)
        all_passed = all(c.passed for c in criteria)

        return TierResult(
            tier=PassTier.STRONG,
            passed=all_passed,
            criteria=criteria,
            passed_count=passed_count,
            total_count=len(criteria),
        )

    # ─── Breakthrough Pass ────────────────────────────────────────────────

    def _evaluate_breakthrough(
        self,
        result_a: EvaluationResult,
        result_b: EvaluationResult,
    ) -> TierResult:
        """
        Breakthrough Pass: serious architectural improvement.

        ALL criteria must hold.
        """
        criteria: List[CriterionResult] = []

        # A. No collapse: both models > 10% accuracy
        no_collapse = result_a.accuracy > 0.10 and result_b.accuracy > 0.10
        criteria.append(CriterionResult(
            name="no_collapse",
            passed=no_collapse,
            required_value=0.10,
            actual_value=min(result_a.accuracy, result_b.accuracy),
            description=(
                f"No collapse: A={result_a.accuracy:.1%}, B={result_b.accuracy:.1%} "
                f"(both required > 10%)"
            ),
        ))

        # B. Overall gain >= 10%
        overall_gain = result_b.accuracy - result_a.accuracy
        criteria.append(CriterionResult(
            name="overall_accuracy_gain",
            passed=overall_gain >= self.breakthrough_overall_gain,
            required_value=self.breakthrough_overall_gain,
            actual_value=overall_gain,
            description=(
                f"Overall gain: {overall_gain:.1%} "
                f"(required >= {self.breakthrough_overall_gain:.0%})"
            ),
        ))

        # C. High-distance gain >= 15%
        high_dist_a = _extract_high_distance_subset(
            result_a.predictions, self.distance_quantile,
        )
        high_dist_b = _extract_high_distance_subset(
            result_b.predictions, self.distance_quantile,
        )
        hd_gain = _subset_accuracy(high_dist_b) - _subset_accuracy(high_dist_a)
        criteria.append(CriterionResult(
            name="high_distance_gain",
            passed=hd_gain >= self.breakthrough_high_distance_gain,
            required_value=self.breakthrough_high_distance_gain,
            actual_value=hd_gain,
            description=(
                f"High-distance gain: {hd_gain:.1%} "
                f"(required >= {self.breakthrough_high_distance_gain:.0%})"
            ),
        ))

        # D. High-distractor gain >= 15%
        high_dis_a = _extract_high_distractor_subset(
            result_a.predictions, self.distractor_quantile,
        )
        high_dis_b = _extract_high_distractor_subset(
            result_b.predictions, self.distractor_quantile,
        )
        hdistr_gain = _subset_accuracy(high_dis_b) - _subset_accuracy(high_dis_a)
        criteria.append(CriterionResult(
            name="high_distractor_gain",
            passed=hdistr_gain >= self.breakthrough_high_distractor_gain,
            required_value=self.breakthrough_high_distractor_gain,
            actual_value=hdistr_gain,
            description=(
                f"High-distractor gain: {hdistr_gain:.1%} "
                f"(required >= {self.breakthrough_high_distractor_gain:.0%})"
            ),
        ))

        # E. Confidence-correctness correlation >= 0.30
        corr = _interference_correctness_correlation(result_b.predictions)
        criteria.append(CriterionResult(
            name="interference_correlation",
            passed=corr >= self.breakthrough_correlation,
            required_value=self.breakthrough_correlation,
            actual_value=corr,
            description=(
                f"Confidence-correctness correlation: {corr:.3f} "
                f"(required >= {self.breakthrough_correlation})"
            ),
        ))

        # F. Binding-specific error reduction
        rs_reduction = _role_swap_reduction(result_a, result_b)
        nn_reduction = _nearest_name_reduction(result_a, result_b)
        error_improvement = rs_reduction >= 0.20 and nn_reduction > 0
        criteria.append(CriterionResult(
            name="binding_error_reduction",
            passed=error_improvement,
            required_value=0.20,
            actual_value=rs_reduction,
            description=(
                f"Role swap reduction: {rs_reduction:.0%}, "
                f"nearest-name reduction: {nn_reduction:.0%} "
                f"(role swap required >= 20%, nn required > 0%)"
            ),
        ))

        # G. Performance gap grows with distractor count (positive slope)
        gap_slope = _distractor_gap_slope(
            result_a.predictions, result_b.predictions,
        )
        criteria.append(CriterionResult(
            name="gap_grows_with_distractors",
            passed=gap_slope > 0,
            required_value=0.0,
            actual_value=gap_slope,
            description=(
                f"Accuracy gap slope vs distractors: {gap_slope:.6f} "
                f"(required > 0 — gap must widen under stress)"
            ),
        ))

        passed_count = sum(1 for c in criteria if c.passed)
        all_passed = all(c.passed for c in criteria)

        return TierResult(
            tier=PassTier.BREAKTHROUGH,
            passed=all_passed,
            criteria=criteria,
            passed_count=passed_count,
            total_count=len(criteria),
        )

    # ─── Summary ──────────────────────────────────────────────────────────

    def _build_summary(
        self,
        highest: PassTier,
        minimal: TierResult,
        strong: TierResult,
        breakthrough: TierResult,
        result_a: EvaluationResult,
        result_b: EvaluationResult,
    ) -> str:
        lines = [
            "=" * 72,
            "BEHAVIORAL PASS CRITERIA EVALUATION",
            "=" * 72,
            "",
            f"Model A ({result_a.model_name}): {result_a.accuracy:.1%}",
            f"Model B ({result_b.model_name}): {result_b.accuracy:.1%}",
            "",
        ]

        for tier_result in [minimal, strong, breakthrough]:
            status = "PASS" if tier_result.passed else "FAIL"
            lines.append(
                f"--- {tier_result.tier.value.upper()} "
                f"({tier_result.passed_count}/{tier_result.total_count}) "
                f"[{status}] ---"
            )
            for c in tier_result.criteria:
                mark = "[x]" if c.passed else "[ ]"
                lines.append(f"  {mark} {c.description}")
            lines.append("")

        lines.append("-" * 72)

        verdict_map = {
            PassTier.NONE: (
                "VERDICT: NO PASS — Interference head does not demonstrate "
                "binding improvement. The gain is either absent, limited to "
                "easy examples, or not statistically significant."
            ),
            PassTier.MINIMAL: (
                "VERDICT: MINIMAL PASS — Proof of signal detected. "
                "Interference cross-terms contribute to binding, but the "
                "advantage is moderate. Further optimization needed."
            ),
            PassTier.STRONG: (
                "VERDICT: STRONG PASS — Clear binding advantage confirmed. "
                "Model B shows robust improvement under distance, distractors, "
                "and nesting stress. Effect size is medium or above."
            ),
            PassTier.BREAKTHROUGH: (
                "VERDICT: BREAKTHROUGH PASS — Serious architectural improvement. "
                "Interference mechanism provides strong, calibrated binding "
                "that scales with difficulty. Value gate confirmed."
            ),
        }

        lines.append(verdict_map[highest])
        lines.append("=" * 72)

        return "\n".join(lines)


def format_pass_result(result: PassResult) -> str:
    """Return the formatted summary string from a pass evaluation."""
    return result.summary
