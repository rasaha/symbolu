"""Tests for training data generators."""

import pytest
from symbolu.training.schemas import IntentLabel, QueryIntentPair
from symbolu.training.generators.intent_generator import IntentPairGenerator
from symbolu.training.generators.paraphrase_generator import ParaphrasePairGenerator


class TestIntentPairGenerator:
    """Tests for IntentPairGenerator."""

    def test_generate_pairs(self):
        """Should generate the requested number of pairs."""
        generator = IntentPairGenerator(seed=42)
        pairs = generator.generate(count=100)
        assert len(pairs) == 100

    def test_reproducibility(self):
        """Same seed should produce same results."""
        gen1 = IntentPairGenerator(seed=42)
        gen2 = IntentPairGenerator(seed=42)
        pairs1 = gen1.generate(count=50)
        pairs2 = gen2.generate(count=50)
        assert [p.query for p in pairs1] == [p.query for p in pairs2]

    def test_different_seeds(self):
        """Different seeds should produce different results."""
        gen1 = IntentPairGenerator(seed=42)
        gen2 = IntentPairGenerator(seed=123)
        pairs1 = gen1.generate(count=50)
        pairs2 = gen2.generate(count=50)
        assert [p.query for p in pairs1] != [p.query for p in pairs2]

    def test_all_intents_covered(self):
        """Generated data should cover all intent types."""
        generator = IntentPairGenerator(seed=42)
        pairs = generator.generate(count=1000)
        intents = {p.intent for p in pairs}
        # Should have all 6 intents
        assert len(intents) == 6
        for label in IntentLabel:
            assert label in intents

    def test_balanced_distribution(self):
        """Intent distribution should be roughly balanced."""
        generator = IntentPairGenerator(seed=42)
        pairs = generator.generate(count=600)
        from collections import Counter
        counts = Counter(p.intent for p in pairs)
        # Each intent should have ~100 pairs (allow 50% variance)
        for intent, count in counts.items():
            assert 50 <= count <= 150, f"{intent}: {count}"

    def test_pairs_have_valid_structure(self):
        """Each pair should have valid structure."""
        generator = IntentPairGenerator(seed=42)
        pairs = generator.generate(count=50)
        for pair in pairs:
            assert pair.query and len(pair.query) > 0
            assert isinstance(pair.intent, IntentLabel)
            assert 0.0 <= pair.confidence <= 1.0
            assert pair.source == "synthetic"


class TestParaphrasePairGenerator:
    """Tests for ParaphrasePairGenerator."""

    def test_generate_pairs(self):
        """Should generate the requested number of pairs."""
        generator = ParaphrasePairGenerator(seed=42)
        pairs = generator.generate(count=100)
        assert len(pairs) == 100

    def test_similar_ratio(self):
        """Should respect the similar ratio parameter."""
        generator = ParaphrasePairGenerator(seed=42)
        pairs = generator.generate(count=100, similar_ratio=0.7)
        similar_count = sum(1 for p in pairs if p.similar)
        assert 65 <= similar_count <= 75  # Allow some variance

    def test_similar_pairs_have_high_score(self):
        """Similar pairs should have high similarity scores."""
        generator = ParaphrasePairGenerator(seed=42)
        pairs = generator.generate(count=100)
        for pair in pairs:
            if pair.similar:
                assert pair.similarity_score is not None
                assert pair.similarity_score >= 0.8

    def test_dissimilar_pairs_have_low_score(self):
        """Dissimilar pairs should have low similarity scores."""
        generator = ParaphrasePairGenerator(seed=42)
        pairs = generator.generate(count=100)
        for pair in pairs:
            if not pair.similar:
                assert pair.similarity_score is not None
                assert pair.similarity_score <= 0.3

    def test_pairs_not_identical(self):
        """Paraphrase pairs should not be identical."""
        generator = ParaphrasePairGenerator(seed=42)
        pairs = generator.generate(count=100)
        for pair in pairs:
            # Queries should not be exactly the same
            assert pair.query_a.lower().strip() != pair.query_b.lower().strip()

    def test_generate_from_intent_pairs(self):
        """Should generate paraphrase pairs from intent pairs."""
        intent_gen = IntentPairGenerator(seed=42)
        intent_pairs = intent_gen.generate(count=100)

        para_gen = ParaphrasePairGenerator(seed=42)
        para_pairs = para_gen.generate_from_intent_pairs(
            intent_pairs=intent_pairs,
            pairs_per_query=3,
        )

        # Should generate multiple pairs
        assert len(para_pairs) > 0

        # Should have both similar and dissimilar pairs
        similar = [p for p in para_pairs if p.similar]
        dissimilar = [p for p in para_pairs if not p.similar]
        assert len(similar) > 0
        assert len(dissimilar) > 0

    def test_reproducibility(self):
        """Same seed should produce same results."""
        gen1 = ParaphrasePairGenerator(seed=42)
        gen2 = ParaphrasePairGenerator(seed=42)
        pairs1 = gen1.generate(count=50)
        pairs2 = gen2.generate(count=50)
        assert [(p.query_a, p.query_b) for p in pairs1] == [
            (p.query_a, p.query_b) for p in pairs2
        ]
