"""Tests for evaluation metrics computation."""

import pytest
import numpy as np

from symbolu.chitta_vritti.evaluation.types import EvaluationSample, OutcomeLabel, ErrorType
from symbolu.chitta_vritti.evaluation.metrics import MetricsComputer, find_optimal_threshold


def make_sample(
    sample_id: str,
    coherence: float,
    score: float,
    viparyaya: float,
    is_correct: bool,
) -> EvaluationSample:
    """Helper to create evaluation samples."""
    return EvaluationSample(
        sample_id=sample_id,
        coherence=coherence,
        score=score,
        fractures={},
        vritti={
            "pramana": 1.0 - viparyaya - 0.3,
            "viparyaya": viparyaya,
            "vikalpa": 0.1,
            "smrti": 0.1,
            "nidra": 0.1,
        },
        dominant_vritti="pramana" if viparyaya < 0.3 else "viparyaya",
        outcome=OutcomeLabel.CORRECT if is_correct else OutcomeLabel.INCORRECT,
        error_type=ErrorType.NONE if is_correct else ErrorType.OTHER,
    )


class TestCalibrationMetrics:
    """Tests for calibration computation."""

    def test_perfect_calibration(self):
        """Perfectly calibrated predictions should have ECE ≈ 0."""
        # Create samples where score matches accuracy
        samples = []
        for i in range(100):
            score = i / 100.0
            # Correct with probability = score
            is_correct = np.random.random() < score
            samples.append(make_sample(f"s{i}", score, score, 0.1, is_correct))

        computer = MetricsComputer(num_calibration_bins=10)
        result = computer.compute_calibration(samples)

        # ECE should be low for calibrated predictions
        # (not exactly 0 due to sampling variance)
        assert result.expected_calibration_error < 0.2

    def test_overconfident_predictions(self):
        """Overconfident predictions should have high ECE."""
        # All predictions are score=0.9 but only 50% correct
        samples = [
            make_sample(f"s{i}", 0.9, 0.9, 0.1, i % 2 == 0) for i in range(100)
        ]

        computer = MetricsComputer()
        result = computer.compute_calibration(samples)

        # Should have significant calibration error (0.9 - 0.5 = 0.4)
        assert result.expected_calibration_error > 0.3

    def test_brier_score_perfect(self):
        """Perfect predictions should have Brier score ≈ 0."""
        # All score=1.0 and all correct
        samples = [make_sample(f"s{i}", 1.0, 1.0, 0.0, True) for i in range(50)]

        computer = MetricsComputer()
        result = computer.compute_calibration(samples)

        assert result.brier_score == pytest.approx(0.0)

    def test_brier_score_worst(self):
        """Worst predictions should have Brier score ≈ 1."""
        # All score=1.0 but all incorrect
        samples = [make_sample(f"s{i}", 1.0, 1.0, 0.0, False) for i in range(50)]

        computer = MetricsComputer()
        result = computer.compute_calibration(samples)

        assert result.brier_score == pytest.approx(1.0)

    def test_empty_samples(self):
        """Empty samples should return default result."""
        computer = MetricsComputer()
        result = computer.compute_calibration([])

        assert result.expected_calibration_error == 0.0
        assert result.brier_score == 0.0


class TestDetectionMetrics:
    """Tests for error detection metrics."""

    def test_perfect_detection(self):
        """Perfect viparyaya detection should have TPR=1, FPR=0."""
        samples = []
        # Errors have high viparyaya
        for i in range(25):
            samples.append(make_sample(f"err{i}", 0.3, 0.3, 0.5, False))
        # Correct have low viparyaya
        for i in range(75):
            samples.append(make_sample(f"cor{i}", 0.9, 0.9, 0.1, True))

        computer = MetricsComputer()
        result = computer.compute_detection(samples, viparyaya_threshold=0.3)

        assert result.true_positive_rate == pytest.approx(1.0)
        assert result.false_positive_rate == pytest.approx(0.0)
        assert result.precision == pytest.approx(1.0)
        assert result.f1_score == pytest.approx(1.0)

    def test_no_detection_power(self):
        """Random viparyaya should have AUC ≈ 0.5."""
        rng = np.random.default_rng(42)
        samples = []
        for i in range(100):
            is_correct = rng.random() > 0.3
            viparyaya = rng.random() * 0.5  # Random, uncorrelated
            samples.append(make_sample(f"s{i}", 0.5, 0.5, viparyaya, is_correct))

        computer = MetricsComputer()
        result = computer.compute_detection(samples)

        # AUC should be close to 0.5 (random)
        assert 0.3 < result.auc_roc < 0.7

    def test_confusion_matrix_counts(self):
        """Confusion matrix should have correct counts."""
        # 10 errors, 5 flagged (TP=5, FN=5)
        # 20 correct, 2 flagged (FP=2, TN=18)
        samples = []
        for i in range(5):
            samples.append(make_sample(f"tp{i}", 0.3, 0.3, 0.4, False))  # TP
        for i in range(5):
            samples.append(make_sample(f"fn{i}", 0.3, 0.3, 0.2, False))  # FN
        for i in range(2):
            samples.append(make_sample(f"fp{i}", 0.9, 0.9, 0.4, True))  # FP
        for i in range(18):
            samples.append(make_sample(f"tn{i}", 0.9, 0.9, 0.1, True))  # TN

        computer = MetricsComputer()
        result = computer.compute_detection(samples, viparyaya_threshold=0.3)

        assert result.true_positives == 5
        assert result.false_negatives == 5
        assert result.false_positives == 2
        assert result.true_negatives == 18


class TestCorrelationMetrics:
    """Tests for correlation computation."""

    def test_perfect_positive_correlation(self):
        """Perfect correlation should be 1.0."""
        samples = []
        for i in range(20):
            score = i / 19.0
            is_correct = score > 0.5
            samples.append(make_sample(f"s{i}", score, score, 0.1, is_correct))

        computer = MetricsComputer()
        result = computer.compute_correlation(samples)

        # Score should correlate strongly with correctness
        assert result.score_vs_correct > 0.8

    def test_negative_correlation(self):
        """Viparyaya should negatively correlate with correctness."""
        samples = []
        # High viparyaya = error, low viparyaya = correct
        for i in range(10):
            samples.append(make_sample(f"err{i}", 0.3, 0.3, 0.5, False))
        for i in range(10):
            samples.append(make_sample(f"cor{i}", 0.9, 0.9, 0.1, True))

        computer = MetricsComputer()
        result = computer.compute_correlation(samples)

        # Viparyaya should positively correlate with ERROR
        assert result.viparyaya_vs_error > 0.5

    def test_insufficient_samples(self):
        """Less than 3 samples should return zeros."""
        samples = [make_sample("s1", 0.5, 0.5, 0.2, True)]

        computer = MetricsComputer()
        result = computer.compute_correlation(samples)

        assert result.coherence_vs_correct == 0.0
        assert result.coherence_pvalue == 1.0

    def test_vritti_correlations(self):
        """Per-vṛtti correlations should be computed."""
        samples = []
        for i in range(20):
            is_correct = i < 10
            viparyaya = 0.1 if is_correct else 0.4
            samples.append(make_sample(f"s{i}", 0.5, 0.5, viparyaya, is_correct))

        computer = MetricsComputer()
        result = computer.compute_correlation(samples)

        assert "viparyaya" in result.vritti_correlations
        # Viparyaya should correlate positively with errors
        assert result.vritti_correlations["viparyaya"] > 0


class TestVrittiDistribution:
    """Tests for vṛtti distribution computation."""

    def test_distribution_in_errors_vs_correct(self):
        """Should compute average vṛtti for each outcome."""
        samples = []
        # Errors: high viparyaya
        for i in range(5):
            samples.append(make_sample(f"err{i}", 0.3, 0.3, 0.5, False))
        # Correct: low viparyaya
        for i in range(5):
            samples.append(make_sample(f"cor{i}", 0.9, 0.9, 0.1, True))

        computer = MetricsComputer()
        vritti_errors, vritti_correct = computer.compute_vritti_distribution(samples)

        assert vritti_errors["viparyaya"] > vritti_correct["viparyaya"]


class TestOptimalThreshold:
    """Tests for optimal threshold finding."""

    def test_finds_best_f1_threshold(self):
        """Should find threshold that maximizes F1."""
        samples = []
        # Clear separation at threshold 0.3
        for i in range(20):
            samples.append(make_sample(f"err{i}", 0.3, 0.3, 0.35, False))
        for i in range(80):
            samples.append(make_sample(f"cor{i}", 0.9, 0.9, 0.15, True))

        threshold, score = find_optimal_threshold(samples, metric="f1")

        # Optimal should be between correct (0.15) and error (0.35)
        assert 0.1 <= threshold <= 0.4
        assert score > 0.8
