"""
Binding Benchmark Statistical Analysis
========================================

Compares Model A (softmax) vs Model B (resonance) with:
  - McNemar's test for paired binary outcomes
  - Accuracy difference with confidence intervals
  - Per-condition breakdown (distractor count, distance, nesting)
  - Error pattern analysis
  - Structured comparison report
"""

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from resonant_model.dataset import FailureType
from resonant_model.evaluator import EvaluationResult, PredictionRecord


@dataclass
class SignificanceResult:
    """Result of a statistical significance test."""
    test_name: str
    statistic: float
    p_value: float
    significant_at_05: bool
    significant_at_01: bool
    effect_size: float
    interpretation: str


@dataclass
class ConditionComparison:
    """Comparison of two models on a specific condition."""
    condition_name: str
    condition_value: str
    model_a_accuracy: float
    model_b_accuracy: float
    difference: float  # B - A (positive = B better)
    model_a_count: int
    model_b_count: int


@dataclass
class ComparisonReport:
    """Full structured comparison report between two models."""
    model_a_name: str
    model_b_name: str

    # Overall
    model_a_accuracy: float
    model_b_accuracy: float
    accuracy_difference: float
    confidence_interval_95: Tuple[float, float]

    # Significance
    significance: SignificanceResult

    # Per-condition comparisons
    distractor_comparisons: List[ConditionComparison] = field(default_factory=list)
    distance_comparisons: List[ConditionComparison] = field(default_factory=list)
    nesting_comparisons: List[ConditionComparison] = field(default_factory=list)
    template_comparisons: List[ConditionComparison] = field(default_factory=list)

    # Error patterns
    model_a_failures: Dict[str, int] = field(default_factory=dict)
    model_b_failures: Dict[str, int] = field(default_factory=dict)

    # Summary
    hypothesis_supported: bool = False
    summary: str = ""


# ─── Statistical Tests ───────────────────────────────────────────────────────

def _normal_cdf(x: float) -> float:
    """Approximate CDF of standard normal distribution."""
    # Using the Abramowitz and Stegun approximation
    a1 = 0.254829592
    a2 = -0.284496736
    a3 = 1.421413741
    a4 = -1.453152027
    a5 = 1.061405429
    p = 0.3275911

    sign = 1.0 if x >= 0 else -1.0
    x = abs(x)

    t = 1.0 / (1.0 + p * x)
    y = 1.0 - (((((a5 * t + a4) * t) + a3) * t + a2) * t + a1) * t * math.exp(-x * x / 2.0)

    return 0.5 * (1.0 + sign * y)


def _chi2_sf(x: float, df: int = 1) -> float:
    """Survival function (1 - CDF) for chi-squared distribution with df=1."""
    if x <= 0:
        return 1.0
    # For df=1, chi2 = z^2, so P(chi2 > x) = 2 * (1 - Phi(sqrt(x)))
    z = math.sqrt(x)
    return 2.0 * (1.0 - _normal_cdf(z))


def mcnemar_test(
    predictions_a: List[PredictionRecord],
    predictions_b: List[PredictionRecord],
) -> SignificanceResult:
    """
    McNemar's test for paired binary outcomes.

    Tests whether the two models have significantly different error rates.

    The test uses a 2x2 contingency table:
        | B correct | B wrong |
    A correct |    a     |   b    |
    A wrong   |    c     |   d    |

    Under H0 (no difference): b = c
    Test statistic: chi2 = (|b - c| - 1)^2 / (b + c)

    Args:
        predictions_a: Predictions from Model A.
        predictions_b: Predictions from Model B.

    Returns:
        SignificanceResult with test details.
    """
    assert len(predictions_a) == len(predictions_b), "Must have same number of predictions"

    # Build contingency table
    # b = A correct, B wrong
    # c = A wrong, B correct
    b = 0  # A right, B wrong
    c = 0  # A wrong, B right

    for pa, pb in zip(predictions_a, predictions_b):
        if pa.is_correct and not pb.is_correct:
            b += 1
        elif not pa.is_correct and pb.is_correct:
            c += 1

    n_discordant = b + c

    if n_discordant == 0:
        return SignificanceResult(
            test_name="McNemar's test",
            statistic=0.0,
            p_value=1.0,
            significant_at_05=False,
            significant_at_01=False,
            effect_size=0.0,
            interpretation="No discordant pairs — models have identical performance.",
        )

    # McNemar's test with continuity correction
    chi2 = (abs(b - c) - 1) ** 2 / n_discordant
    p_value = _chi2_sf(chi2, df=1)

    # Effect size: odds ratio
    effect_size = (c - b) / n_discordant if n_discordant > 0 else 0.0

    # Interpretation
    if p_value < 0.01:
        if c > b:
            interp = "Model B significantly outperforms Model A (p < 0.01)."
        else:
            interp = "Model A significantly outperforms Model B (p < 0.01)."
    elif p_value < 0.05:
        if c > b:
            interp = "Model B outperforms Model A (p < 0.05)."
        else:
            interp = "Model A outperforms Model B (p < 0.05)."
    else:
        interp = "No significant difference between models."

    return SignificanceResult(
        test_name="McNemar's test (continuity-corrected)",
        statistic=chi2,
        p_value=p_value,
        significant_at_05=p_value < 0.05,
        significant_at_01=p_value < 0.01,
        effect_size=effect_size,
        interpretation=interp,
    )


def accuracy_confidence_interval(
    accuracy_a: float,
    accuracy_b: float,
    n: int,
    confidence: float = 0.95,
) -> Tuple[float, float]:
    """
    Compute confidence interval for the difference in accuracy (B - A).

    Uses the Wald interval for the difference of two proportions
    on paired data.

    Args:
        accuracy_a: Accuracy of Model A.
        accuracy_b: Accuracy of Model B.
        n: Number of examples.
        confidence: Confidence level (default 0.95).

    Returns:
        (lower, upper) bounds of the confidence interval.
    """
    diff = accuracy_b - accuracy_a

    # Standard error for paired proportion difference
    # SE = sqrt((p_a(1-p_a) + p_b(1-p_b) + 2*p_a*p_b) / n)
    # Simplified: SE = sqrt((p_a + p_b - (p_a - p_b)^2) / n)
    se_term = accuracy_a * (1 - accuracy_a) + accuracy_b * (1 - accuracy_b)
    se = math.sqrt(se_term / n) if n > 0 and se_term > 0 else 0.0

    # Z-score for confidence level
    if confidence == 0.95:
        z = 1.96
    elif confidence == 0.99:
        z = 2.576
    else:
        z = 1.96  # default to 95%

    return (diff - z * se, diff + z * se)


# ─── Comparison Engine ────────────────────────────────────────────────────────

class BindingStatistics:
    """
    Compares two evaluation results and produces a structured report.
    """

    def compare(
        self,
        result_a: EvaluationResult,
        result_b: EvaluationResult,
    ) -> ComparisonReport:
        """
        Compare Model A vs Model B results.

        Args:
            result_a: Evaluation results for Model A (softmax baseline).
            result_b: Evaluation results for Model B (resonance interference).

        Returns:
            ComparisonReport with full analysis.
        """
        # Significance test
        significance = mcnemar_test(result_a.predictions, result_b.predictions)

        # Confidence interval
        ci = accuracy_confidence_interval(
            result_a.accuracy, result_b.accuracy, result_a.total_examples,
        )

        # Per-distractor-count comparison
        distractor_comps = self._compare_condition(
            result_a.distractor_accuracy,
            result_b.distractor_accuracy,
            "distractor_count",
        )

        # Per-distance comparison
        distance_comps = self._compare_condition(
            result_a.distance_accuracy,
            result_b.distance_accuracy,
            "separation_distance",
        )

        # Per-nesting comparison
        nesting_comps = self._compare_condition(
            result_a.nesting_accuracy,
            result_b.nesting_accuracy,
            "nesting_depth",
        )

        # Per-template comparison
        template_comps = self._compare_condition(
            result_a.template_accuracy,
            result_b.template_accuracy,
            "template_type",
        )

        # Determine hypothesis support
        diff = result_b.accuracy - result_a.accuracy
        hypothesis_supported = (
            diff > 0
            and significance.significant_at_05
        )

        # Build summary
        summary = self._build_summary(
            result_a, result_b, significance, diff, ci, hypothesis_supported,
            distractor_comps, distance_comps, nesting_comps,
        )

        return ComparisonReport(
            model_a_name=result_a.model_name,
            model_b_name=result_b.model_name,
            model_a_accuracy=result_a.accuracy,
            model_b_accuracy=result_b.accuracy,
            accuracy_difference=diff,
            confidence_interval_95=ci,
            significance=significance,
            distractor_comparisons=distractor_comps,
            distance_comparisons=distance_comps,
            nesting_comparisons=nesting_comps,
            template_comparisons=template_comps,
            model_a_failures=result_a.failure_counts,
            model_b_failures=result_b.failure_counts,
            hypothesis_supported=hypothesis_supported,
            summary=summary,
        )

    def _compare_condition(
        self,
        acc_a: Dict,
        acc_b: Dict,
        condition_name: str,
    ) -> List[ConditionComparison]:
        """Compare accuracy across conditions between two models."""
        all_keys = sorted(set(list(acc_a.keys()) + list(acc_b.keys())), key=str)
        comparisons = []
        for key in all_keys:
            a_acc = acc_a.get(key, 0.0)
            b_acc = acc_b.get(key, 0.0)
            comparisons.append(ConditionComparison(
                condition_name=condition_name,
                condition_value=str(key),
                model_a_accuracy=a_acc,
                model_b_accuracy=b_acc,
                difference=b_acc - a_acc,
                model_a_count=1,  # placeholder
                model_b_count=1,
            ))
        return comparisons

    def _build_summary(
        self,
        result_a: EvaluationResult,
        result_b: EvaluationResult,
        significance: SignificanceResult,
        diff: float,
        ci: Tuple[float, float],
        hypothesis_supported: bool,
        distractor_comps: List[ConditionComparison],
        distance_comps: List[ConditionComparison],
        nesting_comps: List[ConditionComparison],
    ) -> str:
        """Build a human-readable summary of the comparison."""
        lines = [
            "=" * 72,
            "BINDING BENCHMARK COMPARISON REPORT",
            "=" * 72,
            "",
            f"Model A ({result_a.model_name}): {result_a.accuracy:.1%} accuracy "
            f"({result_a.correct}/{result_a.total_examples})",
            f"Model B ({result_b.model_name}): {result_b.accuracy:.1%} accuracy "
            f"({result_b.correct}/{result_b.total_examples})",
            f"Difference (B - A): {diff:+.1%}",
            f"95% CI: [{ci[0]:+.1%}, {ci[1]:+.1%}]",
            "",
            f"Statistical Test: {significance.test_name}",
            f"  chi2 = {significance.statistic:.4f}, p = {significance.p_value:.6f}",
            f"  {significance.interpretation}",
            "",
            "-" * 72,
            "FAILURE PATTERN ANALYSIS",
            "-" * 72,
            "",
            f"  {'Failure Type':<25s} {'Model A':>10s} {'Model B':>10s} {'Delta':>10s}",
        ]

        for ft in FailureType:
            if ft == FailureType.CORRECT:
                continue
            a_count = result_a.failure_counts.get(ft.value, 0)
            b_count = result_b.failure_counts.get(ft.value, 0)
            delta = b_count - a_count
            lines.append(
                f"  {ft.value:<25s} {a_count:>10d} {b_count:>10d} {delta:>+10d}"
            )

        lines.extend([
            "",
            "-" * 72,
            "ACCURACY BY DISTRACTOR COUNT",
            "-" * 72,
        ])
        for comp in distractor_comps:
            lines.append(
                f"  {comp.condition_value:>4s} distractors: "
                f"A={comp.model_a_accuracy:.1%}  B={comp.model_b_accuracy:.1%}  "
                f"delta={comp.difference:+.1%}"
            )

        lines.extend([
            "",
            "-" * 72,
            "ACCURACY BY SEPARATION DISTANCE",
            "-" * 72,
        ])
        for comp in distance_comps:
            lines.append(
                f"  {comp.condition_value:<20s}: "
                f"A={comp.model_a_accuracy:.1%}  B={comp.model_b_accuracy:.1%}  "
                f"delta={comp.difference:+.1%}"
            )

        lines.extend([
            "",
            "-" * 72,
            "ACCURACY BY NESTING DEPTH",
            "-" * 72,
        ])
        for comp in nesting_comps:
            lines.append(
                f"  depth={comp.condition_value}: "
                f"A={comp.model_a_accuracy:.1%}  B={comp.model_b_accuracy:.1%}  "
                f"delta={comp.difference:+.1%}"
            )

        lines.extend([
            "",
            "=" * 72,
            "HYPOTHESIS EVALUATION",
            "=" * 72,
            "",
            "H: If interference cross-terms support binding, Model B should",
            "   outperform Model A under high distractor count, long separation",
            "   distance, and nested clauses.",
            "",
        ])

        if hypothesis_supported:
            lines.append(
                "RESULT: HYPOTHESIS SUPPORTED — Model B (resonance) significantly "
                "outperforms Model A (softmax)."
            )
        else:
            if diff > 0:
                lines.append(
                    "RESULT: TREND SUPPORTS HYPOTHESIS but difference is not "
                    "statistically significant."
                )
            elif diff == 0:
                lines.append(
                    "RESULT: NO DIFFERENCE — Models perform identically."
                )
            else:
                lines.append(
                    "RESULT: HYPOTHESIS NOT SUPPORTED — Model A outperforms Model B."
                )

        lines.append("=" * 72)
        return "\n".join(lines)


def format_report(report: ComparisonReport) -> str:
    """Return the formatted summary string from a comparison report."""
    return report.summary
