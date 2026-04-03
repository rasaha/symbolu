"""
Embedding Provider Interface
============================

Abstract interface for embedding providers.
Enterprise mode uses hash-based 256D embeddings.
Consumer mode uses pre-trained 768D embeddings.
"""

from abc import ABC, abstractmethod
from typing import List
import math


class EmbeddingProvider(ABC):
    """
    Abstract interface for embedding providers.

    Implementations must provide deterministic embeddings for reproducibility.
    Both enterprise and consumer providers produce normalized vectors suitable
    for cosine similarity computation.
    """

    @abstractmethod
    def embed(self, text: str) -> List[float]:
        """
        Convert text to an embedding vector.

        Args:
            text: Input text string

        Returns:
            List of floats (normalized embedding vector)
        """
        pass

    @abstractmethod
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Batch embed multiple texts.

        Args:
            texts: List of text strings

        Returns:
            List of embedding vectors (one per text)
        """
        pass

    @abstractmethod
    def get_dimension(self) -> int:
        """
        Return the embedding dimension.

        Returns:
            Integer dimension of embedding vectors
        """
        pass

    def similarity(self, vec_a: List[float], vec_b: List[float]) -> float:
        """
        Compute cosine similarity between two vectors.

        Default implementation uses standard cosine similarity.
        Providers may override for optimized implementations.

        Args:
            vec_a: First embedding vector
            vec_b: Second embedding vector

        Returns:
            Cosine similarity score (0.0 to 1.0 for normalized vectors)
        """
        if len(vec_a) != len(vec_b):
            raise ValueError(
                f"Vector dimensions must match: {len(vec_a)} != {len(vec_b)}"
            )

        dot_product = sum(a * b for a, b in zip(vec_a, vec_b))
        mag_a = math.sqrt(sum(a * a for a in vec_a))
        mag_b = math.sqrt(sum(b * b for b in vec_b))

        if mag_a == 0 or mag_b == 0:
            return 0.0

        return dot_product / (mag_a * mag_b)
