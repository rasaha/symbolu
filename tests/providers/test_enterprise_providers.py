"""
Enterprise Provider Tests
=========================

Tests for enterprise (symbolic) providers.
Verifies that enterprise providers correctly wrap existing code
and produce deterministic, auditable results.
"""

import pytest

from symbolu.providers.enterprise import (
    HashEmbeddingProvider,
    PhonemeRouterProvider,
    ResonanceFilterProvider,
)
from symbolu.providers.interfaces import (
    EmbeddingProvider,
    RouterProvider,
    FilterProvider,
    ModelType,
)


class TestHashEmbeddingProvider:
    """Tests for HashEmbeddingProvider."""

    @pytest.fixture
    def provider(self):
        """Create a HashEmbeddingProvider instance."""
        return HashEmbeddingProvider()

    def test_implements_interface(self, provider):
        """Verify HashEmbeddingProvider implements EmbeddingProvider."""
        assert isinstance(provider, EmbeddingProvider)

    def test_dimension_is_256(self, provider):
        """Verify enterprise embeddings are 256D."""
        assert provider.get_dimension() == 256

    def test_embed_returns_correct_dimension(self, provider):
        """Verify embed returns vector of correct dimension."""
        vec = provider.embed("hello world")
        assert len(vec) == 256

    def test_embed_is_deterministic(self, provider):
        """Verify embed produces identical results for same input."""
        vec1 = provider.embed("quantum physics")
        vec2 = provider.embed("quantum physics")
        assert vec1 == vec2

    def test_embed_batch(self, provider):
        """Verify embed_batch works correctly."""
        texts = ["hello", "world", "test"]
        vecs = provider.embed_batch(texts)
        assert len(vecs) == 3
        assert all(len(v) == 256 for v in vecs)

    def test_embed_empty_text(self, provider):
        """Verify embed handles empty text."""
        vec = provider.embed("")
        assert len(vec) == 256
        assert all(v == 0.0 for v in vec)

    def test_similarity_identical_vectors(self, provider):
        """Verify similarity of identical vectors is 1.0."""
        vec = provider.embed("test")
        sim = provider.similarity(vec, vec)
        assert sim == pytest.approx(1.0)

    def test_embed_produces_normalized_vectors(self, provider):
        """Verify embeddings are normalized (unit length)."""
        import math
        vec = provider.embed("hello world")
        norm = math.sqrt(sum(v * v for v in vec))
        assert norm == pytest.approx(1.0, abs=0.01)


class TestPhonemeRouterProvider:
    """Tests for PhonemeRouterProvider."""

    @pytest.fixture
    def provider(self):
        """Create a PhonemeRouterProvider instance."""
        return PhonemeRouterProvider()

    def test_implements_interface(self, provider):
        """Verify PhonemeRouterProvider implements RouterProvider."""
        assert isinstance(provider, RouterProvider)

    def test_route_returns_routing_decision(self, provider):
        """Verify route returns RoutingDecision."""
        decision = provider.route("How do atoms bond?")
        assert hasattr(decision, "model_type")
        assert hasattr(decision, "confidence")
        assert hasattr(decision, "dominant_layer")
        assert hasattr(decision, "layer_scores")
        assert hasattr(decision, "trace")

    def test_route_is_deterministic(self, provider):
        """Verify route produces identical results for same input."""
        decision1 = provider.route("Calculate the force")
        decision2 = provider.route("Calculate the force")
        assert decision1.model_type == decision2.model_type
        assert decision1.confidence == decision2.confidence
        assert decision1.dominant_layer == decision2.dominant_layer

    def test_route_batch(self, provider):
        """Verify route_batch works correctly."""
        queries = ["What is love?", "Calculate 2+2", "Run the script"]
        decisions = provider.route_batch(queries)
        assert len(decisions) == 3
        assert all(hasattr(d, "model_type") for d in decisions)

    def test_trace_includes_provider(self, provider):
        """Verify trace includes provider information."""
        decision = provider.route("test query")
        assert "provider" in decision.trace
        assert decision.trace["provider"] == "phoneme"

    def test_trace_includes_words(self, provider):
        """Verify trace includes word-level analysis."""
        decision = provider.route("truth is light")
        assert "words" in decision.trace
        assert len(decision.trace["words"]) > 0

    def test_model_type_is_valid_enum(self, provider):
        """Verify model_type is a valid ModelType."""
        decision = provider.route("some query")
        assert isinstance(decision.model_type, ModelType)


class TestResonanceFilterProvider:
    """Tests for ResonanceFilterProvider."""

    @pytest.fixture
    def provider(self):
        """Create a ResonanceFilterProvider instance."""
        return ResonanceFilterProvider(threshold=0.3)

    def test_implements_interface(self, provider):
        """Verify ResonanceFilterProvider implements FilterProvider."""
        assert isinstance(provider, FilterProvider)

    def test_filter_returns_filter_result(self, provider):
        """Verify filter returns FilterResult."""
        candidates = ("apple", "banana", "atom", "molecule")
        result = provider.filter(candidates, "chemistry", top_k=10)
        assert hasattr(result, "filtered_texts")
        assert hasattr(result, "scores")
        assert hasattr(result, "stats")

    def test_filter_respects_top_k(self, provider):
        """Verify filter respects top_k limit."""
        candidates = tuple(f"word{i}" for i in range(100))
        result = provider.filter(candidates, "test", top_k=5)
        assert len(result.filtered_texts) <= 5

    def test_filter_empty_candidates(self, provider):
        """Verify filter handles empty candidates."""
        result = provider.filter((), "test", top_k=10)
        assert result.count == 0
        assert result.filtered_texts == ()

    def test_filter_is_deterministic(self, provider):
        """Verify filter produces identical results for same input."""
        candidates = ("apple", "atom", "banana")
        result1 = provider.filter(candidates, "science", top_k=10)
        result2 = provider.filter(candidates, "science", top_k=10)
        assert result1.filtered_texts == result2.filtered_texts
        assert result1.scores == result2.scores

    def test_stats_include_provider(self, provider):
        """Verify stats include provider information."""
        result = provider.filter(("a", "b"), "test", top_k=10)
        assert "provider" in result.stats
        assert result.stats["provider"] == "resonance"

    def test_get_threshold(self, provider):
        """Verify get_threshold returns configured threshold."""
        assert provider.get_threshold() == 0.3

    def test_scores_are_floats(self, provider):
        """Verify scores are floats between 0 and 1."""
        candidates = ("physics", "chemistry", "biology")
        result = provider.filter(candidates, "science", top_k=10)
        for score in result.scores:
            assert isinstance(score, float)
            assert 0.0 <= score <= 1.0
