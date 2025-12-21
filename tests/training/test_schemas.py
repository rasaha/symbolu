"""Tests for training data schemas."""

import pytest
from symbolu.training.schemas import (
    IntentLabel,
    QueryIntentPair,
    ParaphrasePair,
    TrainingDataset,
)


class TestIntentLabel:
    """Tests for IntentLabel enum."""

    def test_all_labels_exist(self):
        """All expected intent labels should exist."""
        expected = [
            "reasoning", "reflective", "creative",
            "relationship", "action", "general"
        ]
        for label in expected:
            assert hasattr(IntentLabel, label.upper())

    def test_label_values(self):
        """Label values should match expected strings."""
        assert IntentLabel.REASONING.value == "reasoning"
        assert IntentLabel.CREATIVE.value == "creative"
        assert IntentLabel.ACTION.value == "action"


class TestQueryIntentPair:
    """Tests for QueryIntentPair dataclass."""

    def test_create_pair(self):
        """Should create a valid query-intent pair."""
        pair = QueryIntentPair(
            query="How do neural networks learn?",
            intent=IntentLabel.REASONING,
        )
        assert pair.query == "How do neural networks learn?"
        assert pair.intent == IntentLabel.REASONING
        assert pair.confidence == 1.0  # default
        assert pair.source == "synthetic"  # default

    def test_pair_with_metadata(self):
        """Should store optional metadata."""
        pair = QueryIntentPair(
            query="Test query",
            intent=IntentLabel.GENERAL,
            confidence=0.9,
            source="synthetic",
            metadata={"domain": "test"},
        )
        assert pair.confidence == 0.9
        assert pair.source == "synthetic"
        assert pair.metadata == {"domain": "test"}


class TestParaphrasePair:
    """Tests for ParaphrasePair dataclass."""

    def test_create_similar_pair(self):
        """Should create a similar paraphrase pair."""
        pair = ParaphrasePair(
            query_a="How does photosynthesis work?",
            query_b="Explain photosynthesis",
            similar=True,
        )
        assert pair.similar is True
        assert pair.similarity_score is None  # optional

    def test_create_dissimilar_pair(self):
        """Should create a dissimilar paraphrase pair."""
        pair = ParaphrasePair(
            query_a="What is the weather?",
            query_b="How to cook pasta?",
            similar=False,
            similarity_score=0.1,
        )
        assert pair.similar is False
        assert pair.similarity_score == 0.1


class TestTrainingDataset:
    """Tests for TrainingDataset dataclass."""

    def test_create_dataset(self):
        """Should create a valid dataset."""
        intent_pairs = [
            QueryIntentPair(query="Test", intent=IntentLabel.GENERAL),
        ]
        para_pairs = [
            ParaphrasePair(query_a="A", query_b="B", similar=True),
        ]
        dataset = TrainingDataset(
            name="test",
            version="1.0",
            intent_pairs=intent_pairs,
            paraphrase_pairs=para_pairs,
        )
        assert dataset.name == "test"
        assert len(dataset.intent_pairs) == 1
        assert len(dataset.paraphrase_pairs) == 1
