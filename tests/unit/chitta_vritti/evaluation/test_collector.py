"""Tests for ground truth collector."""

import pytest
import tempfile
import os
import numpy as np

from symbolu.chitta_vritti.types import ChittaVrittiInputs, ChittaVrittiResult
from symbolu.chitta_vritti.evaluation.collector import GroundTruthCollector, AutoLabeler
from symbolu.chitta_vritti.evaluation.types import OutcomeLabel, ErrorType


class TestGroundTruthCollector:
    """Tests for GroundTruthCollector."""

    def test_record_creates_sample(self):
        """Recording should create a sample with correct values."""
        collector = GroundTruthCollector(batch_id="test_batch")

        inputs = ChittaVrittiInputs(
            phonemic_rep=np.random.random(32),
            semantic_rep=np.random.random(32),
            entropy=0.3,
        )

        result = ChittaVrittiResult(
            coherence=0.8,
            fractures={("phonemic", "semantic"): 0.1},
            vritti={"pramana": 0.6, "viparyaya": 0.1, "vikalpa": 0.1, "smrti": 0.1, "nidra": 0.1},
            score=0.75,
            dominant_vritti="pramana",
            primary_fracture=("phonemic", "semantic"),
            explanation="Test",
        )

        sample_id = collector.record(inputs, result)

        assert sample_id.startswith("sample_")
        sample = collector.get_sample(sample_id)
        assert sample is not None
        assert sample.coherence == 0.8
        assert sample.score == 0.75
        assert sample.dominant_vritti == "pramana"

    def test_label_updates_sample(self):
        """Labeling should update sample outcome."""
        collector = GroundTruthCollector()

        inputs = ChittaVrittiInputs(entropy=0.1)
        result = ChittaVrittiResult(
            coherence=0.9,
            fractures={},
            vritti={"pramana": 0.8, "viparyaya": 0.05, "vikalpa": 0.05, "smrti": 0.05, "nidra": 0.05},
            score=0.85,
            dominant_vritti="pramana",
            primary_fracture=None,
            explanation="Test",
        )

        sample_id = collector.record(inputs, result)

        # Initially unlabeled
        sample = collector.get_sample(sample_id)
        assert not sample.is_labeled()

        # Label as correct
        success = collector.label(sample_id, OutcomeLabel.CORRECT)
        assert success

        sample = collector.get_sample(sample_id)
        assert sample.is_labeled()
        assert sample.is_correct()

    def test_label_with_error_details(self):
        """Labeling with error should capture error type and description."""
        collector = GroundTruthCollector()

        inputs = ChittaVrittiInputs(entropy=0.5)
        result = ChittaVrittiResult(
            coherence=0.5,
            fractures={},
            vritti={"pramana": 0.2, "viparyaya": 0.3, "vikalpa": 0.2, "smrti": 0.15, "nidra": 0.15},
            score=0.4,
            dominant_vritti="viparyaya",
            primary_fracture=None,
            explanation="Test",
        )

        sample_id = collector.record(inputs, result)
        collector.label(
            sample_id,
            OutcomeLabel.INCORRECT,
            error_type=ErrorType.SEMANTIC_MISMATCH,
            error_description="Meaning was wrong",
        )

        sample = collector.get_sample(sample_id)
        assert sample.is_error()
        assert sample.error_type == ErrorType.SEMANTIC_MISMATCH
        assert sample.error_description == "Meaning was wrong"

    def test_stats_computation(self):
        """Stats should reflect collected samples."""
        collector = GroundTruthCollector(batch_id="stats_test")

        # Add 3 samples
        for i in range(3):
            inputs = ChittaVrittiInputs(entropy=0.1 * i)
            result = ChittaVrittiResult(
                coherence=0.9,
                fractures={},
                vritti={"pramana": 0.8, "viparyaya": 0.05, "vikalpa": 0.05, "smrti": 0.05, "nidra": 0.05},
                score=0.85,
                dominant_vritti="pramana",
                primary_fracture=None,
                explanation="Test",
            )
            sample_id = collector.record(inputs, result)

            # Label 2 as correct, 1 as error
            if i < 2:
                collector.label(sample_id, OutcomeLabel.CORRECT)
            else:
                collector.label(sample_id, OutcomeLabel.INCORRECT)

        stats = collector.stats()
        assert stats["total_samples"] == 3
        assert stats["labeled_samples"] == 3
        assert stats["correct_count"] == 2
        assert stats["error_count"] == 1
        assert stats["accuracy"] == pytest.approx(2 / 3)

    def test_save_and_load(self):
        """Collector should save and load correctly."""
        collector = GroundTruthCollector(batch_id="save_test")

        inputs = ChittaVrittiInputs(entropy=0.2)
        result = ChittaVrittiResult(
            coherence=0.85,
            fractures={("a", "b"): 0.15},
            vritti={"pramana": 0.7, "viparyaya": 0.1, "vikalpa": 0.1, "smrti": 0.05, "nidra": 0.05},
            score=0.8,
            dominant_vritti="pramana",
            primary_fracture=("a", "b"),
            explanation="Test",
        )

        sample_id = collector.record(inputs, result)
        collector.label(sample_id, OutcomeLabel.CORRECT)

        # Save to temp file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            filepath = f.name

        try:
            collector.save(filepath)

            # Load and verify
            loaded = GroundTruthCollector.load(filepath)
            assert loaded._batch.batch_id == "save_test"
            assert len(loaded._batch.samples) == 1

            sample = loaded.get_sample(sample_id)
            assert sample is not None
            assert sample.coherence == 0.85
            assert sample.is_correct()
        finally:
            os.unlink(filepath)


class TestAutoLabeler:
    """Tests for automated labeling strategies."""

    def test_verification_function_labeler(self):
        """Labeler from verification function should work."""

        def always_correct(output, metadata):
            return True

        labeler = AutoLabeler.from_verification_function(always_correct)

        # Create a dummy sample
        from symbolu.chitta_vritti.evaluation.types import EvaluationSample

        sample = EvaluationSample(
            sample_id="test",
            coherence=0.5,
            fractures={},
            vritti={"pramana": 0.2, "viparyaya": 0.2, "vikalpa": 0.2, "smrti": 0.2, "nidra": 0.2},
            score=0.5,
            dominant_vritti="pramana",
            output_summary="test output",
        )

        outcome, error_type, description = labeler(sample)
        assert outcome == OutcomeLabel.CORRECT
        assert error_type == ErrorType.NONE

    def test_score_threshold_labeler(self):
        """Score threshold labeler should classify based on score."""
        labeler = AutoLabeler.from_score_threshold(threshold=0.7)

        from symbolu.chitta_vritti.evaluation.types import EvaluationSample

        high_score = EvaluationSample(
            sample_id="high",
            coherence=0.9,
            fractures={},
            vritti={"pramana": 0.8, "viparyaya": 0.05, "vikalpa": 0.05, "smrti": 0.05, "nidra": 0.05},
            score=0.85,
            dominant_vritti="pramana",
        )

        low_score = EvaluationSample(
            sample_id="low",
            coherence=0.4,
            fractures={},
            vritti={"pramana": 0.2, "viparyaya": 0.3, "vikalpa": 0.2, "smrti": 0.15, "nidra": 0.15},
            score=0.45,
            dominant_vritti="viparyaya",
        )

        outcome_high, _, _ = labeler(high_score)
        outcome_low, _, _ = labeler(low_score)

        assert outcome_high == OutcomeLabel.CORRECT
        assert outcome_low == OutcomeLabel.INCORRECT
