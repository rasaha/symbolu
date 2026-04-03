"""
Learned Embedding Provider (Consumer)
=====================================

Consumer embedding provider using trained models.
Supports loading trained embedding models from Phase 4.
Falls back to hash-based embeddings if no model is loaded.

Trained Model:
- Uses contrastive learning on paraphrase pairs
- 768D embeddings (configurable)
- Can be trained using symbolu.training.trainers.EmbeddingTrainer
"""

import hashlib
import json
import math
from pathlib import Path
from typing import List, Optional

from symbolu_core.providers.interfaces.embedding_provider import EmbeddingProvider


# Consumer embedding dimension (matches common transformer models)
CONSUMER_EMBEDDING_DIM = 768


class LearnedEmbeddingProvider(EmbeddingProvider):
    """
    Consumer embedding provider using trained embeddings.

    Can operate in two modes:
    1. Trained mode: Uses a loaded model for embeddings
    2. Fallback mode: Uses hash-based embeddings (for testing)

    Attributes:
        dimension: The embedding dimension (768 by default)
        model_path: Path to loaded model (if any)
    """

    def __init__(self, model_path: Optional[str] = None):
        """
        Initialize the learned embedding provider.

        Args:
            model_path: Optional path to trained model checkpoint
        """
        self._dimension = CONSUMER_EMBEDDING_DIM
        self._model_path: Optional[str] = None
        self._weights: Optional[List[List[float]]] = None
        self._bias: Optional[List[float]] = None
        self._vocab_cache: dict = {}

        if model_path:
            self.load_model(model_path)

    def load_model(self, model_path: str) -> None:
        """
        Load a trained embedding model.

        Args:
            model_path: Path to the model checkpoint (JSON format)

        Raises:
            FileNotFoundError: If model file doesn't exist
            ValueError: If model format is invalid
        """
        path = Path(model_path)
        if not path.exists():
            raise FileNotFoundError(f"Model not found: {model_path}")

        with open(path, "r") as f:
            data = json.load(f)

        # Validate model format
        if "weights" not in data or "bias" not in data:
            raise ValueError("Invalid model format: missing weights or bias")

        self._weights = data["weights"]
        self._bias = data["bias"]
        self._dimension = data.get("config", {}).get("dimension", len(self._bias))
        self._model_path = model_path
        self._vocab_cache.clear()

    def is_model_loaded(self) -> bool:
        """Check if a trained model is loaded."""
        return self._weights is not None and self._bias is not None

    def embed(self, text: str) -> List[float]:
        """
        Convert text to an embedding vector.

        If a trained model is loaded, uses the learned transformation.
        Otherwise, falls back to hash-based embeddings.

        Args:
            text: Input text string

        Returns:
            List of floats (normalized embedding vector)
        """
        if not text or not text.strip():
            return [0.0] * self._dimension

        # Get base embedding
        base = self._get_base_embedding(text)

        # Apply learned transformation if model is loaded
        if self.is_model_loaded():
            transformed = self._apply_transformation(base)
        else:
            transformed = base

        # Normalize to unit vector
        return self._normalize(transformed)

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Batch embed multiple texts.

        Args:
            texts: List of text strings

        Returns:
            List of embedding vectors (one per text)
        """
        return [self.embed(text) for text in texts]

    def get_dimension(self) -> int:
        """
        Return the embedding dimension.

        Returns:
            Embedding dimension (768 by default)
        """
        return self._dimension

    def _get_base_embedding(self, text: str) -> List[float]:
        """
        Generate base embedding using hash function.

        This is the input to the learned transformation.
        Uses caching for efficiency.

        Args:
            text: Input text

        Returns:
            List of floats (un-normalized)
        """
        cache_key = text.lower().strip()
        if cache_key in self._vocab_cache:
            return self._vocab_cache[cache_key]

        vectors = []
        num_hashes_needed = (self._dimension + 7) // 8

        for i in range(num_hashes_needed):
            seed = f"{cache_key}_{i}"
            hash_bytes = hashlib.sha256(seed.encode("utf-8")).digest()
            for j in range(0, len(hash_bytes), 4):
                chunk = hash_bytes[j:j + 4]
                value = int.from_bytes(chunk, byteorder="big", signed=True)
                normalized = value / (2**31)
                vectors.append(normalized)
                if len(vectors) >= self._dimension:
                    break
            if len(vectors) >= self._dimension:
                break

        result = vectors[:self._dimension]
        self._vocab_cache[cache_key] = result
        return result

    def _apply_transformation(self, base: List[float]) -> List[float]:
        """
        Apply learned transformation matrix to base embedding.

        Args:
            base: Base embedding vector

        Returns:
            Transformed embedding vector
        """
        result = []
        for i in range(self._dimension):
            val = self._bias[i]
            for j in range(self._dimension):
                val += self._weights[i][j] * base[j]
            result.append(val)
        return result

    def _normalize(self, vector: List[float]) -> List[float]:
        """
        L2 normalize a vector.

        Args:
            vector: Input vector

        Returns:
            Normalized vector (unit length)
        """
        norm = math.sqrt(sum(x * x for x in vector))
        if norm < 1e-10:
            return vector
        return [x / norm for x in vector]
