"""
Embedding Provider for Master Chat
===================================

Provides semantic embeddings for bucket entries and queries
using sentence-transformers.

Embeddings enable:
- Semantic similarity search within buckets
- Better context retrieval based on meaning
- Improved bucket centroid computation

Usage:
    from symbolu.service.master_chat.embeddings import get_embedding_provider

    embed = get_embedding_provider()
    vector = embed("How is my project going?")  # Returns List[float]

Version: 1.0
"""

from __future__ import annotations

import logging
from typing import Callable, Dict, List, Optional
from functools import lru_cache

logger = logging.getLogger(__name__)


# =============================================================================
# Embedding Provider Interface
# =============================================================================

EmbeddingProvider = Callable[[str], List[float]]


# =============================================================================
# Sentence Transformers Provider
# =============================================================================

class SentenceTransformerProvider:
    """
    Embedding provider using sentence-transformers library.

    Default model: all-MiniLM-L6-v2 (384 dimensions, fast, good quality)

    Alternative models:
        - all-mpnet-base-v2: 768 dim, higher quality, slower
        - paraphrase-MiniLM-L6-v2: 384 dim, optimized for paraphrase
        - multi-qa-MiniLM-L6-cos-v1: 384 dim, optimized for QA
    """

    # Singleton instances per model
    _instances: Dict[str, "SentenceTransformerProvider"] = {}

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        """
        Initialize the provider.

        Args:
            model_name: Name of the sentence-transformers model
        """
        self.model_name = model_name
        self._model = None
        self._dimension: Optional[int] = None

    @classmethod
    def get_instance(cls, model_name: str = "all-MiniLM-L6-v2") -> "SentenceTransformerProvider":
        """Get or create a singleton instance for the model."""
        if model_name not in cls._instances:
            cls._instances[model_name] = cls(model_name)
        return cls._instances[model_name]

    def _load_model(self):
        """Lazy load the model."""
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                logger.info(f"Loading sentence-transformers model: {self.model_name}")
                self._model = SentenceTransformer(self.model_name)
                self._dimension = self._model.get_sentence_embedding_dimension()
                logger.info(f"Model loaded: {self._dimension} dimensions")
            except ImportError:
                raise ImportError(
                    "sentence-transformers is required for embeddings. "
                    "Install with: pip install sentence-transformers"
                )

    def embed(self, text: str) -> List[float]:
        """
        Compute embedding for text.

        Args:
            text: Text to embed

        Returns:
            Embedding vector as list of floats
        """
        self._load_model()

        if not text or not text.strip():
            # Return zero vector for empty text
            return [0.0] * self._dimension

        embedding = self._model.encode(text, convert_to_numpy=True)
        return embedding.tolist()

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Compute embeddings for multiple texts.

        More efficient than calling embed() multiple times.

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors
        """
        self._load_model()

        if not texts:
            return []

        # Handle empty texts
        non_empty_indices = [i for i, t in enumerate(texts) if t and t.strip()]
        non_empty_texts = [texts[i] for i in non_empty_indices]

        if not non_empty_texts:
            return [[0.0] * self._dimension] * len(texts)

        # Compute embeddings
        embeddings = self._model.encode(non_empty_texts, convert_to_numpy=True)

        # Build result with zero vectors for empty texts
        result = [[0.0] * self._dimension] * len(texts)
        for idx, embedding in zip(non_empty_indices, embeddings):
            result[idx] = embedding.tolist()

        return result

    @property
    def dimension(self) -> int:
        """Get embedding dimension."""
        self._load_model()
        return self._dimension

    def __call__(self, text: str) -> List[float]:
        """Allow using instance as callable."""
        return self.embed(text)


# =============================================================================
# Fallback Provider (No Dependencies)
# =============================================================================

class SimpleHashProvider:
    """
    Simple hash-based pseudo-embedding provider.

    Used as fallback when sentence-transformers is not available.
    NOT suitable for production semantic search, but allows
    the system to function without ML dependencies.

    Produces deterministic vectors based on character hashing.
    """

    def __init__(self, dimension: int = 384):
        self.dimension = dimension

    def embed(self, text: str) -> List[float]:
        """Compute hash-based pseudo-embedding."""
        import hashlib

        if not text or not text.strip():
            return [0.0] * self.dimension

        # Normalize text
        text = text.lower().strip()

        # Create deterministic vector from hash
        vector = []
        for i in range(self.dimension):
            # Hash text with position salt
            h = hashlib.sha256(f"{text}:{i}".encode()).hexdigest()
            # Convert to float in [-1, 1]
            value = (int(h[:8], 16) / (2**32)) * 2 - 1
            vector.append(value)

        # Normalize to unit length
        magnitude = sum(v * v for v in vector) ** 0.5
        if magnitude > 0:
            vector = [v / magnitude for v in vector]

        return vector

    def __call__(self, text: str) -> List[float]:
        return self.embed(text)


# =============================================================================
# Factory Functions
# =============================================================================

@lru_cache(maxsize=8)
def get_embedding_provider(
    model_name: str = "all-MiniLM-L6-v2",
    fallback_to_hash: bool = True,
) -> EmbeddingProvider:
    """
    Get an embedding provider.

    Tries sentence-transformers first, falls back to hash-based
    provider if unavailable and fallback_to_hash is True.

    Args:
        model_name: Sentence-transformers model name
        fallback_to_hash: Whether to use hash fallback

    Returns:
        Callable that takes text and returns embedding vector
    """
    try:
        provider = SentenceTransformerProvider.get_instance(model_name)
        # Test that model loads
        provider._load_model()
        return provider
    except ImportError:
        if fallback_to_hash:
            logger.warning(
                "sentence-transformers not available, using hash-based fallback. "
                "Install sentence-transformers for proper semantic search."
            )
            return SimpleHashProvider()
        raise


def create_embedding_provider(
    model_name: str = "all-MiniLM-L6-v2",
) -> Optional[EmbeddingProvider]:
    """
    Create a new embedding provider (not cached).

    Returns None if sentence-transformers is not available.

    Args:
        model_name: Model name

    Returns:
        EmbeddingProvider or None
    """
    try:
        return SentenceTransformerProvider(model_name)
    except ImportError:
        return None


# =============================================================================
# Utility Functions
# =============================================================================

def cosine_similarity(a: List[float], b: List[float]) -> float:
    """
    Compute cosine similarity between two vectors.

    Args:
        a: First vector
        b: Second vector

    Returns:
        Similarity score in [-1, 1]
    """
    if len(a) != len(b) or not a:
        return 0.0

    dot_product = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(x * x for x in b) ** 0.5

    if norm_a == 0 or norm_b == 0:
        return 0.0

    return dot_product / (norm_a * norm_b)


def find_most_similar(
    query_embedding: List[float],
    candidates: List[List[float]],
    top_k: int = 5,
) -> List[tuple[int, float]]:
    """
    Find most similar embeddings to query.

    Args:
        query_embedding: Query vector
        candidates: List of candidate vectors
        top_k: Number of results to return

    Returns:
        List of (index, similarity_score) tuples, sorted by score descending
    """
    scores = []
    for i, candidate in enumerate(candidates):
        sim = cosine_similarity(query_embedding, candidate)
        scores.append((i, sim))

    scores.sort(key=lambda x: x[1], reverse=True)
    return scores[:top_k]


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    # Types
    "EmbeddingProvider",
    # Providers
    "SentenceTransformerProvider",
    "SimpleHashProvider",
    # Factory
    "get_embedding_provider",
    "create_embedding_provider",
    # Utilities
    "cosine_similarity",
    "find_most_similar",
]
