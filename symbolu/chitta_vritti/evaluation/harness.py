"""Main evaluation harness for Chitta-Vṛtti.

Ties together collection, metrics computation, and reporting
into a complete evaluation pipeline.
"""

import uuid
from datetime import datetime
from typing import Optional, Callable, Any

import numpy as np

from symbolu.chitta_vritti.types import ChittaVrittiInputs, OptimizedConfig
from symbolu.chitta_vritti.engine import ChittaVrittiEngine
from symbolu.chitta_vritti.evaluation.types import (
    EvaluationSample,
    EvaluationBatch,
    EvaluationReport,
    OutcomeLabel,
    ErrorType,
)
from symbolu.chitta_vritti.evaluation.collector import GroundTruthCollector
from symbolu.chitta_vritti.evaluation.metrics import MetricsComputer, find_optimal_threshold


class EvaluationHarness:
    """Complete evaluation harness for Chitta-Vṛtti.

    Provides end-to-end evaluation workflow:
    1. Run inference and collect CV outputs
    2. Label samples with ground truth
    3. Compute comprehensive metrics
    4. Generate evaluation report

    Usage:
        harness = EvaluationHarness()

        # Run evaluation on test cases
        for test_input, expected_output in test_cases:
            harness.evaluate(test_input, expected_output, verify_fn)

        # Generate report
        report = harness.generate_report()
        print(report.summary())
    """

    def __init__(
        self,
        config: Optional[OptimizedConfig] = None,
        batch_id: Optional[str] = None,
    ) -> None:
        """Initialize evaluation harness.

        Args:
            config: OptimizedConfig for Chitta-Vṛtti engine
            batch_id: Unique identifier for this evaluation run
        """
        self._config = config or OptimizedConfig()
        self._engine = ChittaVrittiEngine(config=self._config)
        self._collector = GroundTruthCollector(
            batch_id=batch_id or f"eval_{uuid.uuid4().hex[:8]}",
            description="Chitta-Vṛtti evaluation run",
        )
        self._metrics = MetricsComputer()

    def evaluate(
        self,
        inputs: ChittaVrittiInputs,
        expected_correct: bool,
        error_type: ErrorType = ErrorType.NONE,
        error_description: str = "",
        metadata: Optional[dict] = None,
        output_summary: str = "",
    ) -> str:
        """Evaluate a single test case.

        Args:
            inputs: ChittaVrittiInputs for the test case
            expected_correct: Whether the output should be correct
            error_type: Type of error if not correct
            error_description: Description of the error
            metadata: Optional metadata
            output_summary: Optional output summary

        Returns:
            sample_id for reference
        """
        # Run CV computation
        result = self._engine.compute(inputs)

        # Record sample
        sample_id = self._collector.record(
            inputs=inputs,
            result=result,
            metadata=metadata,
            output_summary=output_summary,
        )

        # Label immediately
        outcome = OutcomeLabel.CORRECT if expected_correct else OutcomeLabel.INCORRECT
        self._collector.label(
            sample_id=sample_id,
            outcome=outcome,
            error_type=error_type,
            error_description=error_description,
        )

        return sample_id

    def evaluate_with_verifier(
        self,
        inputs: ChittaVrittiInputs,
        verifier: Callable[[Any], tuple[bool, ErrorType, str]],
        output: Any,
        metadata: Optional[dict] = None,
    ) -> str:
        """Evaluate using a verification function.

        Args:
            inputs: ChittaVrittiInputs for the test case
            verifier: Function(output) -> (is_correct, error_type, description)
            output: The actual output to verify
            metadata: Optional metadata

        Returns:
            sample_id for reference
        """
        # Verify output
        is_correct, error_type, description = verifier(output)

        return self.evaluate(
            inputs=inputs,
            expected_correct=is_correct,
            error_type=error_type,
            error_description=description,
            metadata=metadata,
            output_summary=str(output)[:500],  # Truncate for storage
        )

    def generate_report(self) -> EvaluationReport:
        """Generate comprehensive evaluation report.

        Returns:
            EvaluationReport with all metrics
        """
        batch = self._collector.get_batch()
        samples = batch.samples
        labeled = batch.labeled_samples()

        # Compute all metrics
        calibration = self._metrics.compute_calibration(labeled)
        detection = self._metrics.compute_detection(labeled)
        correlation = self._metrics.compute_correlation(labeled)
        vritti_errors, vritti_correct = self._metrics.compute_vritti_distribution(labeled)

        # Error distribution
        error_dist = {}
        for s in batch.error_samples():
            error_type = s.error_type.value
            error_dist[error_type] = error_dist.get(error_type, 0) + 1

        # Build report
        report = EvaluationReport(
            report_id=f"report_{uuid.uuid4().hex[:8]}",
            generated_at=datetime.now(),
            batch_id=batch.batch_id,
            total_samples=len(samples),
            labeled_samples=len(labeled),
            correct_count=len(batch.correct_samples()),
            error_count=len(batch.error_samples()),
            baseline_accuracy=len(batch.correct_samples()) / max(1, len(labeled)),
            calibration=calibration,
            detection=detection,
            correlation=correlation,
            error_distribution=error_dist,
            vritti_in_errors=vritti_errors,
            vritti_in_correct=vritti_correct,
        )

        return report

    def find_optimal_viparyaya_threshold(
        self,
        metric: str = "f1",
    ) -> tuple[float, float]:
        """Find optimal viparyaya threshold for error detection.

        Args:
            metric: Metric to optimize ("f1", "precision", "recall", "balanced")

        Returns:
            Tuple of (optimal_threshold, metric_value)
        """
        labeled = self._collector.get_batch().labeled_samples()
        return find_optimal_threshold(labeled, metric)

    def get_collector(self) -> GroundTruthCollector:
        """Get the underlying collector for advanced operations."""
        return self._collector

    def get_engine(self) -> ChittaVrittiEngine:
        """Get the underlying CV engine."""
        return self._engine

    def reset(self) -> None:
        """Reset the harness for a new evaluation run."""
        self._engine.reset_session()
        self._collector.clear()

    def save(self, filepath: str) -> None:
        """Save collected data to file."""
        self._collector.save(filepath)

    @classmethod
    def load(cls, filepath: str, config: Optional[OptimizedConfig] = None) -> "EvaluationHarness":
        """Load harness from saved data."""
        harness = cls(config=config)
        harness._collector = GroundTruthCollector.load(filepath)
        return harness


class ABComparison:
    """A/B comparison framework for with/without CV modulation.

    Compares system performance with and without Chitta-Vṛtti
    metacognitive signals to quantify impact.
    """

    def __init__(self) -> None:
        """Initialize A/B comparison."""
        self._with_cv_results: list[tuple[float, bool]] = []  # (cv_score, is_correct)
        self._without_cv_results: list[bool] = []  # is_correct only

    def record_with_cv(
        self,
        cv_score: float,
        is_correct: bool,
    ) -> None:
        """Record result from system WITH CV modulation.

        Args:
            cv_score: Chitta-Vṛtti score
            is_correct: Whether output was correct
        """
        self._with_cv_results.append((cv_score, is_correct))

    def record_without_cv(
        self,
        is_correct: bool,
    ) -> None:
        """Record result from system WITHOUT CV modulation.

        Args:
            is_correct: Whether output was correct
        """
        self._without_cv_results.append(is_correct)

    def compare(self) -> dict[str, Any]:
        """Compare performance between conditions.

        Returns:
            Dictionary with comparison metrics
        """
        if not self._with_cv_results or not self._without_cv_results:
            return {"error": "Insufficient data for comparison"}

        # Accuracy comparison
        with_cv_correct = sum(1 for _, c in self._with_cv_results if c)
        with_cv_accuracy = with_cv_correct / len(self._with_cv_results)

        without_cv_correct = sum(1 for c in self._without_cv_results if c)
        without_cv_accuracy = without_cv_correct / len(self._without_cv_results)

        accuracy_delta = with_cv_accuracy - without_cv_accuracy

        # Filtered accuracy (only use high-confidence CV predictions)
        high_conf = [(s, c) for s, c in self._with_cv_results if s >= 0.7]
        if high_conf:
            high_conf_accuracy = sum(1 for _, c in high_conf if c) / len(high_conf)
        else:
            high_conf_accuracy = 0.0

        # Error reduction when CV flags issues
        cv_flagged = [(s, c) for s, c in self._with_cv_results if s < 0.5]
        if cv_flagged:
            flagged_error_rate = sum(1 for _, c in cv_flagged if not c) / len(cv_flagged)
        else:
            flagged_error_rate = 0.0

        return {
            "with_cv": {
                "n_samples": len(self._with_cv_results),
                "accuracy": with_cv_accuracy,
                "high_conf_accuracy": high_conf_accuracy,
                "high_conf_n": len(high_conf),
            },
            "without_cv": {
                "n_samples": len(self._without_cv_results),
                "accuracy": without_cv_accuracy,
            },
            "comparison": {
                "accuracy_delta": accuracy_delta,
                "relative_improvement": accuracy_delta / max(0.01, without_cv_accuracy),
                "flagged_error_rate": flagged_error_rate,
                "cv_adds_value": accuracy_delta > 0 or high_conf_accuracy > without_cv_accuracy,
            },
        }

    def summary(self) -> str:
        """Generate human-readable comparison summary."""
        results = self.compare()

        if "error" in results:
            return f"Error: {results['error']}"

        with_cv = results["with_cv"]
        without_cv = results["without_cv"]
        comparison = results["comparison"]

        lines = [
            "=== A/B Comparison: With vs Without Chitta-Vṛtti ===",
            "",
            f"WITH CV ({with_cv['n_samples']} samples):",
            f"  Overall accuracy: {with_cv['accuracy']:.1%}",
            f"  High-confidence accuracy (score >= 0.7): {with_cv['high_conf_accuracy']:.1%} ({with_cv['high_conf_n']} samples)",
            "",
            f"WITHOUT CV ({without_cv['n_samples']} samples):",
            f"  Overall accuracy: {without_cv['accuracy']:.1%}",
            "",
            "COMPARISON:",
            f"  Accuracy delta: {comparison['accuracy_delta']:+.1%}",
            f"  Relative improvement: {comparison['relative_improvement']:+.1%}",
            f"  Error rate when CV flags (score < 0.5): {comparison['flagged_error_rate']:.1%}",
            "",
            f"  CV adds value: {'Yes' if comparison['cv_adds_value'] else 'No'}",
        ]

        return "\n".join(lines)


def generate_synthetic_test_data(
    n_samples: int = 100,
    error_rate: float = 0.2,
    cv_predictive_power: float = 0.7,
    seed: int = 42,
) -> list[tuple[ChittaVrittiInputs, bool, ErrorType]]:
    """Generate synthetic test data for evaluation harness testing.

    Creates test cases where CV signals correlate with correctness
    to the specified degree.

    Args:
        n_samples: Number of samples to generate
        error_rate: Proportion of samples that are errors
        cv_predictive_power: How well CV should predict errors (0.5 = random)
        seed: Random seed for reproducibility

    Returns:
        List of (inputs, is_correct, error_type) tuples
    """
    rng = np.random.default_rng(seed)
    dim = 32
    test_data = []

    for i in range(n_samples):
        is_correct = rng.random() > error_rate

        # Generate inputs that correlate with correctness
        if is_correct:
            # Correct: high coherence (aligned representations)
            if rng.random() < cv_predictive_power:
                base = rng.random(dim)
                phonemic = base + rng.random(dim) * 0.1
                semantic = base + rng.random(dim) * 0.1
                structural = base + rng.random(dim) * 0.1
                temporal = base + rng.random(dim) * 0.1
                entropy = rng.random() * 0.3
            else:
                # Sometimes correct even with low coherence
                phonemic = rng.random(dim)
                semantic = rng.random(dim)
                structural = rng.random(dim)
                temporal = rng.random(dim)
                entropy = rng.random() * 0.7
        else:
            # Error: low coherence (misaligned representations)
            if rng.random() < cv_predictive_power:
                phonemic = rng.random(dim)
                semantic = -phonemic + rng.random(dim) * 0.2  # Opposing
                structural = rng.random(dim)
                temporal = rng.random(dim)
                entropy = 0.3 + rng.random() * 0.5
            else:
                # Sometimes error even with high coherence
                base = rng.random(dim)
                phonemic = base + rng.random(dim) * 0.1
                semantic = base + rng.random(dim) * 0.1
                structural = base + rng.random(dim) * 0.1
                temporal = base + rng.random(dim) * 0.1
                entropy = rng.random() * 0.3

        inputs = ChittaVrittiInputs(
            phonemic_rep=phonemic,
            semantic_rep=semantic,
            structural_rep=structural,
            temporal_rep=temporal,
            entropy=entropy,
            motion=rng.random() * 0.5,
            confidence=0.5 + rng.random() * 0.5,
        )

        error_type = ErrorType.NONE if is_correct else ErrorType.SEMANTIC_MISMATCH

        test_data.append((inputs, is_correct, error_type))

    return test_data
