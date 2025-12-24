"""Tests for training infrastructure."""

import json
import os
import tempfile
import pytest
from symbolu.training.schemas import IntentLabel, QueryIntentPair, ParaphrasePair
from symbolu.training.trainers.embedding_trainer import (
    EmbeddingTrainer,
    EmbeddingTrainerConfig,
    TrainingMetrics,
)
from symbolu.training.trainers.router_trainer import (
    RouterTrainer,
    RouterTrainerConfig,
    RouterMetrics,
)


class TestEmbeddingTrainer:
    """Tests for EmbeddingTrainer."""

    def _create_pairs(self, count: int = 100) -> list:
        """Create sample paraphrase pairs."""
        pairs = []
        for i in range(count // 2):
            # Similar pairs
            pairs.append(ParaphrasePair(
                query_a=f"How do I cook {i}?",
                query_b=f"What's the recipe for {i}?",
                similar=True,
                similarity_score=0.9,
            ))
            # Dissimilar pairs
            pairs.append(ParaphrasePair(
                query_a=f"What is weather {i}?",
                query_b=f"Calculate integral {i}",
                similar=False,
                similarity_score=0.1,
            ))
        return pairs

    def test_init_with_default_config(self):
        """Should initialize with default config."""
        trainer = EmbeddingTrainer()
        assert trainer.config.dimension == 768
        assert trainer.config.epochs == 10

    def test_init_with_custom_config(self):
        """Should initialize with custom config."""
        config = EmbeddingTrainerConfig(dimension=256, epochs=5)
        trainer = EmbeddingTrainer(config)
        assert trainer.config.dimension == 256
        assert trainer.config.epochs == 5

    def test_embed_produces_correct_dimension(self):
        """Embed should produce vectors of correct dimension."""
        config = EmbeddingTrainerConfig(dimension=768)
        trainer = EmbeddingTrainer(config)
        vec = trainer.embed("test query")
        assert len(vec) == 768

    def test_embed_is_normalized(self):
        """Embeddings should be L2 normalized."""
        trainer = EmbeddingTrainer()
        vec = trainer.embed("test query")
        import math
        norm = math.sqrt(sum(v * v for v in vec))
        assert abs(norm - 1.0) < 1e-6

    def test_embed_is_deterministic(self):
        """Same input should produce same embedding."""
        trainer = EmbeddingTrainer()
        vec1 = trainer.embed("test query")
        vec2 = trainer.embed("test query")
        assert vec1 == vec2

    def test_train_runs(self):
        """Training should complete without errors."""
        config = EmbeddingTrainerConfig(epochs=2, dimension=64)
        trainer = EmbeddingTrainer(config)
        pairs = self._create_pairs(20)
        metrics = trainer.train(pairs, verbose=False)
        assert len(metrics) == 2

    def test_train_produces_metrics(self):
        """Training should produce valid metrics."""
        config = EmbeddingTrainerConfig(epochs=3, dimension=64)
        trainer = EmbeddingTrainer(config)
        pairs = self._create_pairs(20)
        metrics = trainer.train(pairs, verbose=False)

        for m in metrics:
            assert isinstance(m, TrainingMetrics)
            assert m.epoch > 0
            assert 0.0 <= m.accuracy <= 1.0

    def test_save_and_load(self):
        """Should save and load model correctly."""
        config = EmbeddingTrainerConfig(epochs=2, dimension=64)
        trainer = EmbeddingTrainer(config)
        pairs = self._create_pairs(20)
        trainer.train(pairs, verbose=False)

        # Get embedding before save
        vec_before = trainer.embed("test query")

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            path = f.name

        try:
            trainer.save(path)

            # Create new trainer and load
            new_trainer = EmbeddingTrainer()
            new_trainer.load(path)

            # Embedding should match
            vec_after = new_trainer.embed("test query")
            assert vec_before == vec_after
        finally:
            os.unlink(path)

    def test_reproducibility_with_seed(self):
        """Same seed should produce same training results."""
        config1 = EmbeddingTrainerConfig(epochs=3, dimension=64, seed=42)
        config2 = EmbeddingTrainerConfig(epochs=3, dimension=64, seed=42)
        trainer1 = EmbeddingTrainer(config1)
        trainer2 = EmbeddingTrainer(config2)

        pairs = self._create_pairs(20)
        metrics1 = trainer1.train(pairs, verbose=False)
        metrics2 = trainer2.train(pairs, verbose=False)

        assert len(metrics1) == len(metrics2)
        for m1, m2 in zip(metrics1, metrics2):
            assert abs(m1.loss - m2.loss) < 1e-6


class TestRouterTrainer:
    """Tests for RouterTrainer."""

    def _create_pairs(self, count: int = 100) -> list:
        """Create sample intent pairs."""
        pairs = []
        intents = list(IntentLabel)
        for i in range(count):
            pairs.append(QueryIntentPair(
                query=f"Test query {i} for intent classification",
                intent=intents[i % len(intents)],
            ))
        return pairs

    def test_init_with_default_config(self):
        """Should initialize with default config."""
        trainer = RouterTrainer()
        assert trainer.config.embedding_dim == 768
        assert trainer.config.epochs == 20

    def test_init_with_custom_config(self):
        """Should initialize with custom config."""
        config = RouterTrainerConfig(embedding_dim=256, epochs=5)
        trainer = RouterTrainer(config)
        assert trainer.config.embedding_dim == 256
        assert trainer.config.epochs == 5

    def test_predict_returns_valid_intent(self):
        """Predict should return valid intent label."""
        trainer = RouterTrainer()
        intent, confidence, probs = trainer.predict("test query")
        assert isinstance(intent, IntentLabel)
        assert 0.0 <= confidence <= 1.0
        assert len(probs) == 6  # All intent types

    def test_predict_probabilities_sum_to_one(self):
        """Prediction probabilities should sum to 1."""
        trainer = RouterTrainer()
        _, _, probs = trainer.predict("test query")
        total = sum(probs.values())
        assert abs(total - 1.0) < 1e-6

    def test_train_runs(self):
        """Training should complete without errors."""
        config = RouterTrainerConfig(epochs=2, embedding_dim=64)
        trainer = RouterTrainer(config)
        pairs = self._create_pairs(30)
        metrics = trainer.train(pairs, verbose=False)
        assert len(metrics) == 2

    def test_train_produces_metrics(self):
        """Training should produce valid metrics."""
        config = RouterTrainerConfig(epochs=3, embedding_dim=64)
        trainer = RouterTrainer(config)
        pairs = self._create_pairs(30)
        metrics = trainer.train(pairs, verbose=False)

        for m in metrics:
            assert isinstance(m, RouterMetrics)
            assert m.epoch > 0
            assert 0.0 <= m.accuracy <= 1.0
            assert len(m.per_class_accuracy) == 6

    def test_save_and_load(self):
        """Should save and load model correctly."""
        config = RouterTrainerConfig(epochs=2, embedding_dim=64)
        trainer = RouterTrainer(config)
        pairs = self._create_pairs(30)
        trainer.train(pairs, verbose=False)

        # Get prediction before save
        intent_before, conf_before, _ = trainer.predict("test query")

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            path = f.name

        try:
            trainer.save(path)

            # Create new trainer and load
            new_trainer = RouterTrainer()
            new_trainer.load(path)

            # Prediction should match
            intent_after, conf_after, _ = new_trainer.predict("test query")
            assert intent_before == intent_after
            assert abs(conf_before - conf_after) < 1e-6
        finally:
            os.unlink(path)

    def test_train_with_embedder(self):
        """Should train using provided embedder."""
        embed_config = EmbeddingTrainerConfig(dimension=64, epochs=2)
        embedder = EmbeddingTrainer(embed_config)

        router_config = RouterTrainerConfig(embedding_dim=64, epochs=2)
        trainer = RouterTrainer(router_config, embedder=embedder)

        pairs = self._create_pairs(30)
        metrics = trainer.train(pairs, verbose=False)
        assert len(metrics) == 2

    def test_reproducibility_with_seed(self):
        """Same seed should produce same training results."""
        config1 = RouterTrainerConfig(epochs=3, embedding_dim=64, seed=42)
        config2 = RouterTrainerConfig(epochs=3, embedding_dim=64, seed=42)
        trainer1 = RouterTrainer(config1)
        trainer2 = RouterTrainer(config2)

        pairs = self._create_pairs(30)
        metrics1 = trainer1.train(pairs, verbose=False)
        metrics2 = trainer2.train(pairs, verbose=False)

        assert len(metrics1) == len(metrics2)
        for m1, m2 in zip(metrics1, metrics2):
            assert abs(m1.loss - m2.loss) < 1e-6


class TestTrainingMetrics:
    """Tests for training metrics dataclasses."""

    def test_training_metrics_to_dict(self):
        """TrainingMetrics should convert to dict."""
        m = TrainingMetrics(
            epoch=1,
            loss=0.5,
            accuracy=0.8,
            similar_avg_dist=0.2,
            dissimilar_avg_dist=0.7,
        )
        d = m.to_dict()
        assert d["epoch"] == 1
        assert d["loss"] == 0.5
        assert d["accuracy"] == 0.8

    def test_router_metrics_to_dict(self):
        """RouterMetrics should convert to dict."""
        m = RouterMetrics(
            epoch=1,
            loss=0.3,
            accuracy=0.9,
            per_class_accuracy={"reasoning": 0.85, "creative": 0.95},
        )
        d = m.to_dict()
        assert d["epoch"] == 1
        assert d["loss"] == 0.3
        assert "reasoning" in d["per_class_accuracy"]
