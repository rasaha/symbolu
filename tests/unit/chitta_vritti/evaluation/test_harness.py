"""Tests for evaluation harness."""

import pytest
import numpy as np

from symbolu.chitta_vritti.types import ChittaVrittiInputs, OptimizedConfig
from symbolu.chitta_vritti.evaluation.harness import (
    EvaluationHarness,
    ABComparison,
    generate_synthetic_test_data,
)
from symbolu.chitta_vritti.evaluation.types import ErrorType


class TestEvaluationHarness:
    """Tests for main evaluation harness."""

    def test_evaluate_correct_sample(self):
        """Evaluating a correct sample should be labeled correctly."""
        harness = EvaluationHarness(batch_id="test")

        inputs = ChittaVrittiInputs(
            phonemic_rep=np.random.random(32),
            semantic_rep=np.random.random(32),
            entropy=0.2,
        )

        sample_id = harness.evaluate(
            inputs=inputs,
            expected_correct=True,
        )

        sample = harness.get_collector().get_sample(sample_id)
        assert sample.is_correct()

    def test_evaluate_error_sample(self):
        """Evaluating an error sample should capture error details."""
        harness = EvaluationHarness()

        inputs = ChittaVrittiInputs(
            phonemic_rep=np.random.random(32),
            semantic_rep=-np.random.random(32),  # Opposing
            entropy=0.6,
        )

        sample_id = harness.evaluate(
            inputs=inputs,
            expected_correct=False,
            error_type=ErrorType.SEMANTIC_MISMATCH,
            error_description="Test error",
        )

        sample = harness.get_collector().get_sample(sample_id)
        assert sample.is_error()
        assert sample.error_type == ErrorType.SEMANTIC_MISMATCH

    def test_generate_report(self):
        """Report generation should include all metrics."""
        harness = EvaluationHarness()

        # Add some samples
        for i in range(20):
            base = np.random.random(32)
            is_correct = i < 15

            if is_correct:
                inputs = ChittaVrittiInputs(
                    phonemic_rep=base,
                    semantic_rep=base + np.random.random(32) * 0.1,
                    entropy=0.1,
                )
            else:
                inputs = ChittaVrittiInputs(
                    phonemic_rep=base,
                    semantic_rep=-base,
                    entropy=0.6,
                )

            harness.evaluate(inputs=inputs, expected_correct=is_correct)

        report = harness.generate_report()

        assert report.total_samples == 20
        assert report.labeled_samples == 20
        assert report.correct_count == 15
        assert report.error_count == 5
        assert report.calibration is not None
        assert report.detection is not None
        assert report.correlation is not None

    def test_report_summary(self):
        """Report summary should be human-readable."""
        harness = EvaluationHarness()

        # Add minimal samples
        for i in range(10):
            inputs = ChittaVrittiInputs(entropy=0.1 * i)
            harness.evaluate(inputs=inputs, expected_correct=i < 7)

        report = harness.generate_report()
        summary = report.summary()

        assert "Chitta-Vṛtti Evaluation Report" in summary
        assert "Calibration" in summary
        assert "Error Detection" in summary
        assert "Correlations" in summary

    def test_find_optimal_threshold(self):
        """Should find optimal viparyaya threshold."""
        harness = EvaluationHarness()

        # Create samples with clear separation
        for i in range(50):
            # Correct samples: aligned, low entropy
            base = np.random.random(32)
            inputs = ChittaVrittiInputs(
                phonemic_rep=base,
                semantic_rep=base + np.random.random(32) * 0.05,
                structural_rep=base + np.random.random(32) * 0.05,
                entropy=0.05,
            )
            harness.evaluate(inputs=inputs, expected_correct=True)

        for i in range(20):
            # Error samples: opposing, high entropy
            base = np.random.random(32)
            inputs = ChittaVrittiInputs(
                phonemic_rep=base,
                semantic_rep=-base,
                structural_rep=np.random.random(32),
                entropy=0.7,
            )
            harness.evaluate(inputs=inputs, expected_correct=False)

        threshold, score = harness.find_optimal_viparyaya_threshold()

        assert 0.0 < threshold < 0.5
        assert score > 0.0

    def test_reset_clears_state(self):
        """Reset should clear all collected data."""
        harness = EvaluationHarness()

        inputs = ChittaVrittiInputs(entropy=0.2)
        harness.evaluate(inputs=inputs, expected_correct=True)

        assert len(harness.get_collector().get_batch()) == 1

        harness.reset()

        assert len(harness.get_collector().get_batch()) == 0


class TestABComparison:
    """Tests for A/B comparison framework."""

    def test_comparison_with_improvement(self):
        """CV should show improvement when it adds value."""
        ab = ABComparison()

        # With CV: 90% accurate, high scores correlate with correctness
        for i in range(100):
            is_correct = i < 90
            score = 0.9 if is_correct else 0.3
            ab.record_with_cv(score, is_correct)

        # Without CV: 70% accurate
        for i in range(100):
            is_correct = i < 70
            ab.record_without_cv(is_correct)

        result = ab.compare()

        assert result["with_cv"]["accuracy"] == 0.9
        assert result["without_cv"]["accuracy"] == 0.7
        assert result["comparison"]["accuracy_delta"] == pytest.approx(0.2)
        assert result["comparison"]["cv_adds_value"] is True

    def test_comparison_no_improvement(self):
        """Should detect when CV doesn't help."""
        ab = ABComparison()

        # Both conditions: 80% accurate
        for i in range(100):
            is_correct = i < 80
            ab.record_with_cv(0.5, is_correct)  # Random scores
            ab.record_without_cv(is_correct)

        result = ab.compare()

        assert result["comparison"]["accuracy_delta"] == pytest.approx(0.0)

    def test_high_confidence_accuracy(self):
        """High confidence predictions should be more accurate."""
        ab = ABComparison()

        # High scores (>= 0.7): always correct
        for i in range(50):
            ab.record_with_cv(0.85, True)

        # Low scores (< 0.7): 50% correct
        for i in range(50):
            ab.record_with_cv(0.4, i < 25)

        ab.record_without_cv(True)  # Need at least one

        result = ab.compare()

        assert result["with_cv"]["high_conf_accuracy"] == 1.0
        assert result["with_cv"]["accuracy"] == 0.75

    def test_summary_output(self):
        """Summary should be readable."""
        ab = ABComparison()

        for i in range(20):
            ab.record_with_cv(0.8, i < 18)
            ab.record_without_cv(i < 15)

        summary = ab.summary()

        assert "WITH CV" in summary
        assert "WITHOUT CV" in summary
        assert "COMPARISON" in summary

    def test_insufficient_data(self):
        """Should handle insufficient data gracefully."""
        ab = ABComparison()
        result = ab.compare()

        assert "error" in result


class TestSyntheticDataGeneration:
    """Tests for synthetic test data generation."""

    def test_generates_correct_count(self):
        """Should generate requested number of samples."""
        data = generate_synthetic_test_data(n_samples=50)
        assert len(data) == 50

    def test_error_rate_approximately_correct(self):
        """Error rate should match requested rate."""
        data = generate_synthetic_test_data(
            n_samples=1000,
            error_rate=0.3,
            seed=42,
        )

        errors = sum(1 for _, is_correct, _ in data if not is_correct)
        error_rate = errors / len(data)

        assert 0.25 < error_rate < 0.35

    def test_cv_predictive_power(self):
        """Higher predictive power should yield better detection."""
        from symbolu.chitta_vritti.engine import ChittaVrittiEngine

        engine = ChittaVrittiEngine()

        # High predictive power
        data_high = generate_synthetic_test_data(
            n_samples=100,
            cv_predictive_power=0.9,
            seed=42,
        )

        # Low predictive power
        data_low = generate_synthetic_test_data(
            n_samples=100,
            cv_predictive_power=0.5,
            seed=43,
        )

        # Compute viparyaya for each
        def avg_viparyaya_diff(data):
            correct_vip = []
            error_vip = []
            for inputs, is_correct, _ in data:
                result = engine.compute(inputs)
                if is_correct:
                    correct_vip.append(result.vritti["viparyaya"])
                else:
                    error_vip.append(result.vritti["viparyaya"])
                engine.reset_session()

            if not error_vip or not correct_vip:
                return 0.0
            return np.mean(error_vip) - np.mean(correct_vip)

        diff_high = avg_viparyaya_diff(data_high)
        diff_low = avg_viparyaya_diff(data_low)

        # Higher predictive power should yield larger separation
        assert diff_high > diff_low

    def test_data_structure(self):
        """Each sample should have correct structure."""
        data = generate_synthetic_test_data(n_samples=10)

        for inputs, is_correct, error_type in data:
            assert isinstance(inputs, ChittaVrittiInputs)
            assert isinstance(is_correct, bool)
            assert inputs.phonemic_rep is not None
            assert inputs.semantic_rep is not None
