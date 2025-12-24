"""
Ontological Engine - Text Encoders
===================================

Text encoding modules for the ontological engine:
1. HashEncoder: Deterministic fallback (no dependencies)
2. DistilBERTEncoder: Pretrained transformer (requires transformers)
3. SentenceTransformerEncoder: MiniLM encoder (384D, fast)
4. HybridEncoder: Auto-selects based on availability

Offline Usage:
    # First, save model on machine with HuggingFace access:
    save_model_for_offline("./models/minilm")

    # Then load from local path (no network required):
    encoder = get_encoder("minilm", model_path="./models/minilm")

Usage:
    encoder = get_encoder()  # Auto-selects best available
    embedding = encoder.encode("What is the meaning of truth?")
"""

import hashlib
import math
import os
from typing import List, Optional, Protocol
from abc import ABC, abstractmethod


class TextEncoder(ABC):
    """Abstract base class for text encoders."""

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Return the embedding dimension."""
        pass

    @abstractmethod
    def encode(self, text: str) -> List[float]:
        """Encode text to embedding vector."""
        pass

    @abstractmethod
    def encode_batch(self, texts: List[str]) -> List[List[float]]:
        """Encode a batch of texts."""
        pass

    @property
    def name(self) -> str:
        """Return encoder name."""
        return self.__class__.__name__


class HashEncoder(TextEncoder):
    """
    Deterministic hash-based encoder (no dependencies).

    Uses SHA-256 to generate reproducible embeddings.
    Same input always produces the same output.

    This is a fallback encoder when transformer libraries
    are not available.
    """

    def __init__(self, dimension: int = 768):
        self._dimension = dimension

    @property
    def dimension(self) -> int:
        return self._dimension

    def encode(self, text: str) -> List[float]:
        """Generate embedding using hash function."""
        vectors = []
        num_hashes = (self._dimension + 7) // 8

        for i in range(num_hashes):
            seed = f"{text.lower().strip()}_{i}"
            hash_bytes = hashlib.sha256(seed.encode("utf-8")).digest()
            for j in range(0, len(hash_bytes), 4):
                chunk = hash_bytes[j:j + 4]
                value = int.from_bytes(chunk, byteorder="big", signed=True)
                normalized = value / (2 ** 31)
                vectors.append(normalized)
                if len(vectors) >= self._dimension:
                    break
            if len(vectors) >= self._dimension:
                break

        return vectors[:self._dimension]

    def encode_batch(self, texts: List[str]) -> List[List[float]]:
        """Encode batch of texts."""
        return [self.encode(text) for text in texts]


class DistilBERTEncoder(TextEncoder):
    """
    DistilBERT-based encoder using HuggingFace transformers.

    Provides high-quality semantic embeddings using the
    pretrained distilbert-base-uncased model.

    Requires: pip install transformers torch
    """

    def __init__(
        self,
        model_name: str = "distilbert-base-uncased",
        max_length: int = 128,
        device: Optional[str] = None,
    ):
        self.model_name = model_name
        self.max_length = max_length
        self._model = None
        self._tokenizer = None
        self._device = device
        self._dimension = 768  # DistilBERT hidden size

    def _load_model(self):
        """Lazy load the model and tokenizer."""
        if self._model is not None:
            return

        try:
            from transformers import DistilBertModel, DistilBertTokenizer
            import torch

            self._tokenizer = DistilBertTokenizer.from_pretrained(self.model_name)
            self._model = DistilBertModel.from_pretrained(self.model_name)

            # Set device
            if self._device is None:
                self._device = "cuda" if torch.cuda.is_available() else "cpu"

            self._model = self._model.to(self._device)
            self._model.eval()

            print(f"Loaded {self.model_name} on {self._device}")

        except ImportError as e:
            raise ImportError(
                "DistilBERT encoder requires 'transformers' and 'torch'. "
                "Install with: pip install transformers torch"
            ) from e

    @property
    def dimension(self) -> int:
        return self._dimension

    def encode(self, text: str) -> List[float]:
        """Encode single text using DistilBERT."""
        return self.encode_batch([text])[0]

    def encode_batch(self, texts: List[str]) -> List[List[float]]:
        """Encode batch of texts using DistilBERT."""
        self._load_model()

        import torch

        # Tokenize
        inputs = self._tokenizer(
            texts,
            padding=True,
            truncation=True,
            max_length=self.max_length,
            return_tensors="pt",
        )
        inputs = {k: v.to(self._device) for k, v in inputs.items()}

        # Forward pass
        with torch.no_grad():
            outputs = self._model(**inputs)

        # Use [CLS] token embedding (first token)
        embeddings = outputs.last_hidden_state[:, 0, :]

        # Convert to list
        return embeddings.cpu().tolist()


class HybridEncoder(TextEncoder):
    """
    Hybrid encoder that auto-selects best available encoder.

    Priority:
    1. SentenceTransformer MiniLM (384D, 2.5x faster than DistilBERT)
    2. DistilBERT (768D fallback if sentence-transformers unavailable)
    3. HashEncoder (final fallback)
    """

    def __init__(self, prefer_transformer: bool = True, dimension: int = 384):
        self._prefer_transformer = prefer_transformer
        self._fallback_dimension = dimension
        self._encoder: Optional[TextEncoder] = None
        self._init_encoder()

    def _init_encoder(self):
        """Initialize the best available encoder."""
        if self._prefer_transformer:
            # Try MiniLM first (faster, 384D)
            try:
                self._encoder = SentenceTransformerEncoder()
                # Test that it works
                self._encoder._load_model()
                print("Using MiniLM encoder (384D)")
                return
            except (ImportError, Exception) as e:
                print(f"MiniLM not available ({e}), trying DistilBERT...")

            # Fall back to DistilBERT (768D)
            try:
                self._encoder = DistilBERTEncoder()
                # Test that it works
                self._encoder._load_model()
                print("Using DistilBERT encoder (768D)")
                return
            except (ImportError, Exception) as e:
                print(f"DistilBERT not available ({e}), falling back to hash encoder")

        self._encoder = HashEncoder(dimension=self._fallback_dimension)
        print("Using hash-based encoder")

    @property
    def dimension(self) -> int:
        return self._encoder.dimension

    @property
    def name(self) -> str:
        return f"Hybrid({self._encoder.name})"

    def encode(self, text: str) -> List[float]:
        return self._encoder.encode(text)

    def encode_batch(self, texts: List[str]) -> List[List[float]]:
        return self._encoder.encode_batch(texts)


def get_encoder(
    encoder_type: str = "auto",
    dimension: int = 384,
    device: Optional[str] = None,
    model_path: Optional[str] = None,
    offline: bool = False,
) -> TextEncoder:
    """
    Factory function to get a text encoder.

    Args:
        encoder_type: "auto", "minilm", "distilbert", or "hash"
        dimension: Embedding dimension (for hash encoder)
        device: Device for transformer ("cuda" or "cpu")
        model_path: Local path to saved model (for offline use)
        offline: If True, only load from local path, never download

    Returns:
        TextEncoder instance

    Note:
        "auto" tries MiniLM (384D) first, then DistilBERT (768D), then hash.
        MiniLM is 2.5x faster than DistilBERT with only 5% quality drop.

    Offline Usage:
        # First save model (on machine with HuggingFace access):
        save_model_for_offline("./models/minilm")

        # Then load offline:
        encoder = get_encoder("minilm", model_path="./models/minilm")
    """
    if encoder_type == "hash":
        return HashEncoder(dimension=dimension)
    elif encoder_type == "minilm":
        return SentenceTransformerEncoder(
            device=device,
            model_path=model_path,
            offline=offline,
        )
    elif encoder_type == "distilbert":
        return DistilBERTEncoder(device=device)
    elif encoder_type == "auto":
        # If model_path provided, use it for MiniLM
        if model_path:
            return SentenceTransformerEncoder(
                device=device,
                model_path=model_path,
                offline=offline,
            )
        return HybridEncoder(prefer_transformer=True, dimension=dimension)
    else:
        raise ValueError(f"Unknown encoder type: {encoder_type}")


# ============================================
# Sentence Transformer Alternative
# ============================================

class SentenceTransformerEncoder(TextEncoder):
    """
    Sentence Transformer encoder for semantic similarity.

    Uses all-MiniLM-L6-v2 by default (384D, fast, good quality).

    Supports offline loading from local model path.

    Requires: pip install sentence-transformers

    Usage:
        # Online (downloads from HuggingFace):
        encoder = SentenceTransformerEncoder()

        # Offline (loads from local path):
        encoder = SentenceTransformerEncoder(model_path="./models/minilm")
    """

    def __init__(
        self,
        model_name: str = "all-MiniLM-L6-v2",
        model_path: Optional[str] = None,
        device: Optional[str] = None,
        offline: bool = False,
    ):
        """
        Initialize the encoder.

        Args:
            model_name: HuggingFace model name (used if model_path not provided)
            model_path: Local path to saved model (for offline use)
            device: Device for inference ("cuda" or "cpu")
            offline: If True, only load from local path, never download
        """
        self.model_name = model_name
        self.model_path = model_path
        self._model = None
        self._device = device
        self._offline = offline
        self._dimension = 384  # Default for MiniLM

    def _load_model(self):
        """Lazy load the model."""
        if self._model is not None:
            return

        try:
            from sentence_transformers import SentenceTransformer

            # Determine model source
            if self.model_path and os.path.exists(self.model_path):
                # Load from local path
                model_source = self.model_path
                print(f"Loading model from local path: {self.model_path}")
            elif self._offline:
                raise FileNotFoundError(
                    f"Offline mode enabled but model not found at: {self.model_path}"
                )
            else:
                # Download from HuggingFace
                model_source = self.model_name

            self._model = SentenceTransformer(model_source, device=self._device)
            self._dimension = self._model.get_sentence_embedding_dimension()

            print(f"Loaded {model_source} ({self._dimension}D)")

        except ImportError as e:
            raise ImportError(
                "SentenceTransformer encoder requires 'sentence-transformers'. "
                "Install with: pip install sentence-transformers"
            ) from e

    def save(self, path: str) -> None:
        """
        Save the model to a local path for offline use.

        Args:
            path: Directory path to save the model

        Usage:
            encoder = SentenceTransformerEncoder()
            encoder.save("./models/minilm")
        """
        self._load_model()
        self._model.save(path)
        print(f"Model saved to: {path}")

    @property
    def dimension(self) -> int:
        return self._dimension

    def encode(self, text: str) -> List[float]:
        return self.encode_batch([text])[0]

    def encode_batch(self, texts: List[str]) -> List[List[float]]:
        self._load_model()
        embeddings = self._model.encode(texts, convert_to_numpy=True)
        return embeddings.tolist()


def save_model_for_offline(
    save_path: str,
    model_name: str = "all-MiniLM-L6-v2",
) -> None:
    """
    Download and save a model for offline use.

    Run this on a machine with HuggingFace access, then copy
    the saved directory to machines without access.

    Args:
        save_path: Directory to save the model
        model_name: HuggingFace model name to download

    Usage:
        # On machine with internet:
        save_model_for_offline("./models/minilm")

        # Copy ./models/minilm to target machine, then:
        encoder = get_encoder("minilm", model_path="./models/minilm")
    """
    print(f"Downloading {model_name}...")
    encoder = SentenceTransformerEncoder(model_name=model_name)
    encoder.save(save_path)
    print(f"\nModel saved to: {save_path}")
    print(f"Copy this directory to target machine and use:")
    print(f'  encoder = get_encoder("minilm", model_path="{save_path}")')
