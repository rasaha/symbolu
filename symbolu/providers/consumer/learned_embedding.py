"""
Learned Embedding Provider (Consumer) - STUB
=============================================

Placeholder for pre-trained embedding provider.
Currently returns deterministic pseudo-random 768D vectors.
Will be replaced with actual trained model in Phase 4-5.

Future Implementation:
- Sentence-BERT (distilbert-base) or similar
- 768D embeddings
- Trained on contrastive loss with paraphrase data
"""

import hashlib
import math
from typing import List

from symbolu.providers.interfaces.embedding_provider import EmbeddingProvider


# Consumer embedding dimension (matches common transformer models)
CONSUMER_EMBEDDING_DIM = 768


class LearnedEmbeddingProvider(EmbeddingProvider):
    """
    Consumer embedding provider using pre-trained embeddings.

    STUB IMPLEMENTATION:
    Currently produces deterministic pseudo-random 768D vectors
    based on text hashing. This ensures reproducibility for testing.

    Future implementation will use a trained sentence transformer.

    Attributes:
        dimension: The embedding dimension (768)
    """

    def __init__(self):
        """Initialize the learned embedding provider."""
        self._dimension = CONSUMER_EMBEDDING_DIM

    def embed(self, text: str) -> List[float]:
        """
        Convert text to a 768D embedding vector.

        STUB: Uses deterministic hash-based pseudo-random generation.
        Future: Will use pre-trained sentence transformer.

        Args:
            text: Input text string

        Returns:
            List of floats (normalized 768D embedding vector)
        """
        if not text or not text.strip():
            return [0.0] * self._dimension

        # Generate deterministic pseudo-random embedding based on text hash
        embedding = self._hash_to_vector(text)

        # Normalize to unit vector
        embedding = self._normalize(embedding)

        return embedding

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Batch embed multiple texts.

        Args:
            texts: List of text strings

        Returns:
            List of 768D embedding vectors (one per text)
        """
        return [self.embed(text) for text in texts]

    def get_dimension(self) -> int:
        """
        Return the embedding dimension.

        Returns:
            768 (pre-trained embedding dimension)
        """
        return self._dimension

    def _hash_to_vector(self, text: str) -> List[float]:
        """
        Generate a deterministic pseudo-random vector from text.

        Uses SHA-256 to generate enough bytes for 768 dimensions.
        This is a placeholder until we have a trained model.

        Args:
            text: Input text

        Returns:
            List of floats (un-normalized)
        """
        # We need 768 floats
        # Each SHA-256 hash gives 32 bytes = 8 floats (4 bytes each)
        # So we need 768/8 = 96 hashes
        vectors = []
        num_hashes_needed = (self._dimension + 7) // 8  # Ceiling division

        for i in range(num_hashes_needed):
            seed = f"{text}_{i}"
            hash_bytes = hashlib.sha256(seed.encode("utf-8")).digest()
            # Convert each 4 bytes to a float between -1 and 1
            for j in range(0, len(hash_bytes), 4):
                chunk = hash_bytes[j : j + 4]
                value = int.from_bytes(chunk, byteorder="big", signed=True)
                # Normalize to [-1, 1]
                normalized = value / (2**31)
                vectors.append(normalized)
                if len(vectors) >= self._dimension:
                    return vectors[:self._dimension]

        return vectors[:self._dimension]

    def _normalize(self, vector: List[float]) -> List[float]:
        """
        L2 normalize a vector.

        Args:
            vector: Input vector

        Returns:
            Normalized vector (unit length)
        """
        norm = math.sqrt(sum(x * x for x in vector))
        if norm == 0:
            return vector
        return [x / norm for x in vector]
