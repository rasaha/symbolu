"""
Hash Embedding Provider (Enterprise)
====================================

Wraps the existing hash-based encoder from symbolu/rag/embeddings/encoder.py.
Provides deterministic 256D embeddings suitable for enterprise use cases
requiring full auditability and reproducibility.
"""

from typing import List

from symbolu_core.providers.interfaces.embedding_provider import EmbeddingProvider
from symbolu_core.rag.embeddings.encoder import embed, embed_chunks, get_embedding_dim


class HashEmbeddingProvider(EmbeddingProvider):
    """
    Enterprise embedding provider using deterministic hash-based encoding.

    This provider wraps the existing hash-based encoder and produces
    256D vectors that are fully deterministic and reproducible.

    Attributes:
        dimension: The embedding dimension (256)
    """

    def __init__(self):
        """Initialize the hash embedding provider."""
        self._dimension = get_embedding_dim()

    def embed(self, text: str) -> List[float]:
        """
        Convert text to a 256D embedding vector using hash-based encoding.

        Args:
            text: Input text string

        Returns:
            List of floats (normalized 256D embedding vector)
        """
        return embed(text)

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Batch embed multiple texts.

        Args:
            texts: List of text strings

        Returns:
            List of 256D embedding vectors (one per text)
        """
        return embed_chunks(texts)

    def get_dimension(self) -> int:
        """
        Return the embedding dimension.

        Returns:
            256 (hash-based embedding dimension)
        """
        return self._dimension
