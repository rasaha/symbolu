"""
Embeddings Generator
=====================

Generates vector embeddings for RAG.
"""

from typing import List, Optional
import numpy as np


class EmbeddingsGenerator:
    """
    Generates embeddings using sentence-transformers.
    """
    
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model_name = model_name
        self._model = None
    
    @property
    def model(self):
        """Lazy load the model."""
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                self._model = SentenceTransformer(self.model_name)
            except ImportError:
                raise ImportError("sentence-transformers required: pip install sentence-transformers")
        return self._model
    
    def generate(self, texts: List[str]) -> np.ndarray:
        """Generate embeddings for texts."""
        return self.model.encode(texts)
    
    def generate_single(self, text: str) -> np.ndarray:
        """Generate embedding for single text."""
        return self.model.encode([text])[0]
