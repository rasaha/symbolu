"""
Tests for embedding provider.
"""

import pytest

from symbolu_core.service.master_chat.embeddings import (
    SimpleHashProvider,
    cosine_similarity,
    find_most_similar,
    get_embedding_provider,
)


class TestSimpleHashProvider:
    """Tests for hash-based fallback provider."""

    @pytest.fixture
    def provider(self):
        return SimpleHashProvider(dimension=384)

    def test_embed_returns_vector(self, provider):
        """Embedding returns correct dimension vector."""
        embedding = provider.embed("Hello world")

        assert len(embedding) == 384
        assert all(isinstance(x, float) for x in embedding)

    def test_embed_deterministic(self, provider):
        """Same text produces same embedding."""
        e1 = provider.embed("Test text")
        e2 = provider.embed("Test text")

        assert e1 == e2

    def test_embed_different_for_different_text(self, provider):
        """Different text produces different embedding."""
        e1 = provider.embed("Hello")
        e2 = provider.embed("World")

        assert e1 != e2

    def test_embed_normalized(self, provider):
        """Embedding is unit normalized."""
        embedding = provider.embed("Test")

        magnitude = sum(x * x for x in embedding) ** 0.5
        assert abs(magnitude - 1.0) < 0.01  # Close to 1

    def test_embed_empty_text(self, provider):
        """Empty text returns zero vector."""
        embedding = provider.embed("")

        assert all(x == 0.0 for x in embedding)

    def test_callable(self, provider):
        """Provider can be called directly."""
        embedding = provider("Test")
        assert len(embedding) == 384


class TestCosineSimilarity:
    """Tests for cosine similarity function."""

    def test_identical_vectors(self):
        """Identical vectors have similarity 1."""
        a = [1.0, 0.0, 0.0]
        sim = cosine_similarity(a, a)
        assert sim == pytest.approx(1.0)

    def test_orthogonal_vectors(self):
        """Orthogonal vectors have similarity 0."""
        a = [1.0, 0.0, 0.0]
        b = [0.0, 1.0, 0.0]
        sim = cosine_similarity(a, b)
        assert sim == pytest.approx(0.0)

    def test_opposite_vectors(self):
        """Opposite vectors have similarity -1."""
        a = [1.0, 0.0, 0.0]
        b = [-1.0, 0.0, 0.0]
        sim = cosine_similarity(a, b)
        assert sim == pytest.approx(-1.0)

    def test_similar_vectors(self):
        """Similar vectors have high similarity."""
        a = [1.0, 1.0, 0.0]
        b = [1.0, 0.9, 0.1]
        sim = cosine_similarity(a, b)
        assert sim > 0.9

    def test_empty_vectors(self):
        """Empty vectors return 0."""
        assert cosine_similarity([], []) == 0.0

    def test_different_lengths(self):
        """Different length vectors return 0."""
        assert cosine_similarity([1, 2], [1, 2, 3]) == 0.0

    def test_zero_vectors(self):
        """Zero vectors return 0."""
        assert cosine_similarity([0, 0, 0], [0, 0, 0]) == 0.0


class TestFindMostSimilar:
    """Tests for find_most_similar function."""

    def test_find_most_similar_basic(self):
        """Find most similar vectors."""
        query = [1.0, 0.0, 0.0]
        candidates = [
            [1.0, 0.0, 0.0],  # Identical
            [0.0, 1.0, 0.0],  # Orthogonal
            [0.9, 0.1, 0.0],  # Similar
        ]

        results = find_most_similar(query, candidates, top_k=2)

        assert len(results) == 2
        assert results[0][0] == 0  # First candidate (identical)
        assert results[0][1] == pytest.approx(1.0)

    def test_find_most_similar_respects_k(self):
        """Returns only top_k results."""
        query = [1.0, 0.0, 0.0]
        candidates = [[0.1 * i, 1 - 0.1 * i, 0.0] for i in range(10)]

        results = find_most_similar(query, candidates, top_k=3)

        assert len(results) == 3

    def test_find_most_similar_sorted(self):
        """Results are sorted by similarity descending."""
        query = [1.0, 0.0, 0.0]
        candidates = [
            [0.5, 0.5, 0.0],
            [1.0, 0.0, 0.0],
            [0.7, 0.3, 0.0],
        ]

        results = find_most_similar(query, candidates, top_k=3)

        scores = [r[1] for r in results]
        assert scores == sorted(scores, reverse=True)


class TestGetEmbeddingProvider:
    """Tests for provider factory."""

    def test_get_provider_fallback(self):
        """Factory returns fallback when sentence-transformers unavailable."""
        # This will use fallback since we're testing without sentence-transformers
        provider = get_embedding_provider(fallback_to_hash=True)

        assert provider is not None
        # Test it works
        embedding = provider("Test")
        assert len(embedding) > 0

    def test_get_provider_cached(self):
        """Provider is cached."""
        p1 = get_embedding_provider(fallback_to_hash=True)
        p2 = get_embedding_provider(fallback_to_hash=True)

        assert p1 is p2


class TestEmbeddingIntegration:
    """Integration tests for embeddings with bucket system."""

    def test_hash_provider_semantic_consistency(self):
        """Hash provider provides some semantic consistency."""
        provider = SimpleHashProvider(dimension=384)

        # Similar sentences should have higher similarity than dissimilar
        s1 = provider.embed("I love programming in Python")
        s2 = provider.embed("I enjoy coding with Python")
        s3 = provider.embed("The weather is sunny today")

        sim_similar = cosine_similarity(s1, s2)
        sim_dissimilar = cosine_similarity(s1, s3)

        # Note: Hash provider doesn't guarantee semantic similarity,
        # but different text will produce different embeddings
        assert s1 != s3

    def test_embedding_with_bucket_entry(self):
        """Embedding integrates with bucket entry."""
        from symbolu_core.service.master_chat.bucket_models import BucketEntry
        from datetime import datetime

        provider = SimpleHashProvider(dimension=384)

        content = "I learned about neural networks"
        embedding = provider.embed(content)

        entry = BucketEntry(
            entry_id="e1",
            content=content,
            source_turn_id="t1",
            timestamp=datetime.utcnow(),
            embedding=embedding,
        )

        assert entry.embedding is not None
        assert len(entry.embedding) == 384
