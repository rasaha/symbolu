"""
Consumer Provider Tests
=======================

Tests for consumer (pre-trained) provider stubs.
Verifies that stubs produce valid output structures
even with placeholder implementations.
"""

import pytest

from symbolu.providers.consumer import (
    LearnedEmbeddingProvider,
    TrainedRouterProvider,
    AttentionFilterProvider,
)
from symbolu.providers.interfaces import (
    EmbeddingProvider,
    RouterProvider,
    FilterProvider,
    ModelType,
)


class TestLearnedEmbeddingProvider:
    """Tests for LearnedEmbeddingProvider stub."""

    @pytest.fixture
    def provider(self):
        """Create a LearnedEmbeddingProvider instance."""
        return LearnedEmbeddingProvider()

    def test_implements_interface(self, provider):
        """Verify LearnedEmbeddingProvider implements EmbeddingProvider."""
        assert isinstance(provider, EmbeddingProvider)

    def test_dimension_is_768(self, provider):
        """Verify consumer embeddings are 768D."""
        assert provider.get_dimension() == 768

    def test_embed_returns_correct_dimension(self, provider):
        """Verify embed returns vector of correct dimension."""
        vec = provider.embed("hello world")
        assert len(vec) == 768

    def test_embed_is_deterministic(self, provider):
        """Verify stub produces identical results for same input."""
        vec1 = provider.embed("quantum physics")
        vec2 = provider.embed("quantum physics")
        assert vec1 == vec2

    def test_embed_batch(self, provider):
        """Verify embed_batch works correctly."""
        texts = ["hello", "world", "test"]
        vecs = provider.embed_batch(texts)
        assert len(vecs) == 3
        assert all(len(v) == 768 for v in vecs)

    def test_embed_empty_text(self, provider):
        """Verify embed handles empty text."""
        vec = provider.embed("")
        assert len(vec) == 768
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

    def test_different_texts_produce_different_embeddings(self, provider):
        """Verify different texts produce different embeddings."""
        vec1 = provider.embed("hello world")
        vec2 = provider.embed("goodbye universe")
        assert vec1 != vec2


class TestTrainedRouterProvider:
    """Tests for TrainedRouterProvider stub."""

    @pytest.fixture
    def provider(self):
        """Create a TrainedRouterProvider instance."""
        return TrainedRouterProvider()

    def test_implements_interface(self, provider):
        """Verify TrainedRouterProvider implements RouterProvider."""
        assert isinstance(provider, RouterProvider)

    def test_route_returns_routing_decision(self, provider):
        """Verify route returns RoutingDecision."""
        decision = provider.route("How do atoms bond?")
        assert hasattr(decision, "model_type")
        assert hasattr(decision, "confidence")
        assert hasattr(decision, "dominant_layer")
        assert hasattr(decision, "layer_scores")
        assert hasattr(decision, "trace")

    def test_stub_returns_general(self, provider):
        """Verify stub returns GENERAL model type."""
        decision = provider.route("any query")
        assert decision.model_type == ModelType.GENERAL

    def test_route_batch(self, provider):
        """Verify route_batch works correctly."""
        queries = ["What is love?", "Calculate 2+2", "Run the script"]
        decisions = provider.route_batch(queries)
        assert len(decisions) == 3
        assert all(d.model_type == ModelType.GENERAL for d in decisions)

    def test_trace_indicates_stub_mode(self, provider):
        """Verify trace indicates stub mode."""
        decision = provider.route("test query")
        assert "stub_mode" in decision.trace
        assert decision.trace["stub_mode"] is True

    def test_trace_includes_provider(self, provider):
        """Verify trace includes provider information."""
        decision = provider.route("test query")
        assert "provider" in decision.trace
        assert decision.trace["provider"] == "trained"

    def test_model_type_is_valid_enum(self, provider):
        """Verify model_type is a valid ModelType."""
        decision = provider.route("some query")
        assert isinstance(decision.model_type, ModelType)


class TestAttentionFilterProvider:
    """Tests for AttentionFilterProvider stub."""

    @pytest.fixture
    def provider(self):
        """Create an AttentionFilterProvider instance."""
        return AttentionFilterProvider()

    def test_implements_interface(self, provider):
        """Verify AttentionFilterProvider implements FilterProvider."""
        assert isinstance(provider, FilterProvider)

    def test_filter_returns_filter_result(self, provider):
        """Verify filter returns FilterResult."""
        candidates = ("apple", "banana", "atom", "molecule")
        result = provider.filter(candidates, "chemistry", top_k=10)
        assert hasattr(result, "filtered_texts")
        assert hasattr(result, "scores")
        assert hasattr(result, "stats")

    def test_stub_passes_through_candidates(self, provider):
        """Verify stub passes through all candidates (up to top_k)."""
        candidates = ("a", "b", "c")
        result = provider.filter(candidates, "test", top_k=10)
        assert set(result.filtered_texts) == set(candidates)

    def test_filter_respects_top_k(self, provider):
        """Verify filter respects top_k limit."""
        candidates = tuple(f"word{i}" for i in range(100))
        result = provider.filter(candidates, "test", top_k=5)
        assert len(result.filtered_texts) == 5

    def test_filter_empty_candidates(self, provider):
        """Verify filter handles empty candidates."""
        result = provider.filter((), "test", top_k=10)
        assert result.count == 0
        assert result.filtered_texts == ()

    def test_stats_indicate_stub_mode(self, provider):
        """Verify stats indicate stub mode."""
        result = provider.filter(("a", "b"), "test", top_k=10)
        assert "stub_mode" in result.stats
        assert result.stats["stub_mode"] is True

    def test_stats_include_provider(self, provider):
        """Verify stats include provider information."""
        result = provider.filter(("a", "b"), "test", top_k=10)
        assert "provider" in result.stats
        assert result.stats["provider"] == "attention"

    def test_scores_are_placeholder(self, provider):
        """Verify stub returns placeholder scores (all 1.0)."""
        candidates = ("a", "b", "c")
        result = provider.filter(candidates, "test", top_k=10)
        assert all(score == 1.0 for score in result.scores)
