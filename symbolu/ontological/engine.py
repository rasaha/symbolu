"""
Ontological Engine - Core Model
===============================

The learnable 10D ontological engine with skip connections.

Architecture:
    Text → Encoder (DistilBERT) → Hidden Layers → 10D Output

Features:
- Skip connections (ResNet-style) for gradient flow
- Layer normalization for stable training
- Dropout for regularization
- Interpretable 10D output
"""

import math
from typing import List, Optional, Tuple, Dict, Any
from dataclasses import dataclass

from symbolu.ontological.types import (
    OntologicalConfig,
    OntologicalVector,
    LAYER_NAMES,
)


@dataclass
class HiddenState:
    """Internal representation at each layer."""
    values: List[float]
    layer_name: str


class OntologicalEngine:
    """
    Learnable 10D Ontological Engine (Option B - Hybrid).

    Maps text to interpretable 10-dimensional ontological vectors
    using learned transformations.

    Architecture:
        Input (768D from encoder)
            ↓
        Hidden Layer 1 (512D) ← Skip Connection
            ↓
        Hidden Layer 2 (256D) ← Skip Connection
            ↓
        Output Layer (10D) ← Ontological Dimensions

    Usage:
        engine = OntologicalEngine(config)
        vector = engine.forward(embedding)  # 768D → 10D
        result = engine.analyze("What is the meaning of truth?")
    """

    def __init__(self, config: Optional[OntologicalConfig] = None):
        self.config = config or OntologicalConfig()
        self._init_weights()

        # Text encoder placeholder (will be DistilBERT in full implementation)
        self._encoder_ready = False

    def _init_weights(self) -> None:
        """Initialize all learnable weights."""
        cfg = self.config

        # Build layer dimensions
        dims = [cfg.encoder_dim] + list(cfg.hidden_dims) + [cfg.ontological_dim]
        self._layer_dims = dims

        # Initialize weights for each layer
        self._weights: List[List[List[float]]] = []
        self._biases: List[List[float]] = []

        # Skip connection projection weights (for dimension mismatch)
        self._skip_weights: List[Optional[List[List[float]]]] = []

        # Layer normalization parameters
        self._ln_gamma: List[List[float]] = []
        self._ln_beta: List[List[float]] = []

        for i in range(len(dims) - 1):
            in_dim = dims[i]
            out_dim = dims[i + 1]

            # Main layer weights (Xavier initialization)
            scale = math.sqrt(2.0 / (in_dim + out_dim))
            weights = [
                [self._randn() * scale for _ in range(in_dim)]
                for _ in range(out_dim)
            ]
            biases = [0.0] * out_dim

            self._weights.append(weights)
            self._biases.append(biases)

            # Skip connection projection (if dimensions differ)
            if cfg.use_skip_connections and i > 0:
                prev_dim = dims[i - 1] if i > 0 else dims[0]
                if prev_dim != out_dim:
                    skip_scale = math.sqrt(2.0 / (prev_dim + out_dim))
                    skip_w = [
                        [self._randn() * skip_scale for _ in range(prev_dim)]
                        for _ in range(out_dim)
                    ]
                    self._skip_weights.append(skip_w)
                else:
                    self._skip_weights.append(None)
            else:
                self._skip_weights.append(None)

            # Layer norm parameters
            if cfg.use_layer_norm:
                self._ln_gamma.append([1.0] * out_dim)
                self._ln_beta.append([0.0] * out_dim)
            else:
                self._ln_gamma.append([1.0] * out_dim)
                self._ln_beta.append([0.0] * out_dim)

        # Name the output dimensions
        self._output_names = list(LAYER_NAMES)

    def _randn(self) -> float:
        """Generate a random number from standard normal distribution."""
        import random
        # Box-Muller transform
        u1 = random.random()
        u2 = random.random()
        return math.sqrt(-2 * math.log(u1 + 1e-10)) * math.cos(2 * math.pi * u2)

    def _linear(
        self,
        x: List[float],
        weights: List[List[float]],
        biases: List[float],
    ) -> List[float]:
        """Apply linear transformation: y = Wx + b."""
        out_dim = len(weights)
        in_dim = len(x)
        result = []
        for i in range(out_dim):
            val = biases[i]
            for j in range(in_dim):
                val += weights[i][j] * x[j]
            result.append(val)
        return result

    def _relu(self, x: List[float]) -> List[float]:
        """ReLU activation."""
        return [max(0.0, v) for v in x]

    def _gelu(self, x: List[float]) -> List[float]:
        """GELU activation (used in transformers)."""
        return [
            0.5 * v * (1 + math.tanh(math.sqrt(2 / math.pi) * (v + 0.044715 * v ** 3)))
            for v in x
        ]

    def _tanh(self, x: List[float]) -> List[float]:
        """Tanh activation (keeps values in [-1, 1])."""
        return [math.tanh(v) for v in x]

    def _sigmoid(self, x: List[float]) -> List[float]:
        """Sigmoid activation."""
        return [1.0 / (1.0 + math.exp(-min(max(v, -20), 20))) for v in x]

    def _dropout(self, x: List[float], training: bool = True) -> List[float]:
        """Apply dropout during training."""
        if not training or self.config.dropout <= 0:
            return x
        import random
        keep_prob = 1.0 - self.config.dropout
        return [
            v / keep_prob if random.random() < keep_prob else 0.0
            for v in x
        ]

    def _layer_norm(
        self,
        x: List[float],
        gamma: List[float],
        beta: List[float],
        eps: float = 1e-5,
    ) -> List[float]:
        """Apply layer normalization."""
        mean = sum(x) / len(x)
        var = sum((v - mean) ** 2 for v in x) / len(x)
        std = math.sqrt(var + eps)
        return [gamma[i] * (x[i] - mean) / std + beta[i] for i in range(len(x))]

    def _add_vectors(self, a: List[float], b: List[float]) -> List[float]:
        """Element-wise addition of two vectors."""
        if len(a) != len(b):
            raise ValueError(f"Vector dimension mismatch: {len(a)} vs {len(b)}")
        return [a[i] + b[i] for i in range(len(a))]

    def forward(
        self,
        embedding: List[float],
        training: bool = False,
    ) -> List[float]:
        """
        Forward pass: embedding → 10D ontological vector.

        Args:
            embedding: Input embedding (768D from text encoder)
            training: Whether in training mode (enables dropout)

        Returns:
            10D ontological vector
        """
        cfg = self.config

        # Store intermediate activations for skip connections
        activations = [embedding]
        x = embedding

        # Forward through hidden layers
        for i in range(len(self._weights) - 1):  # All but output layer
            # Linear transformation
            x = self._linear(x, self._weights[i], self._biases[i])

            # Layer normalization
            if cfg.use_layer_norm:
                x = self._layer_norm(x, self._ln_gamma[i], self._ln_beta[i])

            # Activation
            x = self._gelu(x)

            # Dropout
            x = self._dropout(x, training)

            # Skip connection (add previous layer's output if dimensions match)
            if cfg.use_skip_connections and i > 0:
                prev = activations[-1]
                skip_w = self._skip_weights[i]
                if skip_w is not None:
                    # Project previous activation to current dimension
                    prev = self._linear(prev, skip_w, [0.0] * len(x))
                if len(prev) == len(x):
                    x = self._add_vectors(x, prev)

            activations.append(x)

        # Output layer (no dropout, different activation)
        x = self._linear(x, self._weights[-1], self._biases[-1])

        # Output activation
        if cfg.output_activation == "tanh":
            x = self._tanh(x)
        elif cfg.output_activation == "sigmoid":
            x = self._sigmoid(x)
        # else: linear (no activation)

        return x

    def analyze(self, text: str) -> OntologicalVector:
        """
        Analyze text and return its ontological vector.

        Args:
            text: Input text to analyze

        Returns:
            OntologicalVector with 10 named dimensions
        """
        # Get embedding (uses simple hash-based encoder if DistilBERT not loaded)
        embedding = self._encode_text(text)

        # Forward pass
        output = self.forward(embedding, training=False)

        return OntologicalVector(values=tuple(output), text=text)

    def _encode_text(self, text: str) -> List[float]:
        """
        Encode text to embedding vector.

        Uses hash-based encoding as fallback if transformer not loaded.
        """
        if self._encoder_ready:
            # TODO: Use actual DistilBERT encoder
            pass

        # Fallback: hash-based encoding (deterministic)
        return self._hash_encode(text, self.config.encoder_dim)

    def _hash_encode(self, text: str, dim: int) -> List[float]:
        """Generate embedding using hash function (fallback encoder)."""
        import hashlib

        vectors = []
        num_hashes = (dim + 7) // 8

        for i in range(num_hashes):
            seed = f"{text.lower().strip()}_{i}"
            hash_bytes = hashlib.sha256(seed.encode("utf-8")).digest()
            for j in range(0, len(hash_bytes), 4):
                chunk = hash_bytes[j:j + 4]
                value = int.from_bytes(chunk, byteorder="big", signed=True)
                normalized = value / (2 ** 31)
                vectors.append(normalized)
                if len(vectors) >= dim:
                    break
            if len(vectors) >= dim:
                break

        return vectors[:dim]

    def get_weights(self) -> Dict[str, Any]:
        """Get all model weights for saving."""
        return {
            "config": self.config.to_dict(),
            "weights": self._weights,
            "biases": self._biases,
            "skip_weights": self._skip_weights,
            "ln_gamma": self._ln_gamma,
            "ln_beta": self._ln_beta,
        }

    def set_weights(self, weights_dict: Dict[str, Any]) -> None:
        """Load model weights."""
        self._weights = weights_dict["weights"]
        self._biases = weights_dict["biases"]
        self._skip_weights = weights_dict.get("skip_weights", [None] * len(self._weights))
        self._ln_gamma = weights_dict.get("ln_gamma", [[1.0] * d for d in self._layer_dims[1:]])
        self._ln_beta = weights_dict.get("ln_beta", [[0.0] * d for d in self._layer_dims[1:]])

    def parameter_count(self) -> int:
        """Count total trainable parameters."""
        count = 0

        # Main layer weights and biases
        for w, b in zip(self._weights, self._biases):
            count += len(w) * len(w[0])  # Weight matrix
            count += len(b)  # Bias vector

        # Skip connection weights
        for skip_w in self._skip_weights:
            if skip_w is not None:
                count += len(skip_w) * len(skip_w[0])

        # Layer norm parameters
        for gamma, beta in zip(self._ln_gamma, self._ln_beta):
            count += len(gamma) + len(beta)

        return count

    def summary(self) -> str:
        """Print model summary."""
        lines = [
            "=" * 60,
            "LEARNABLE 10D ONTOLOGICAL ENGINE (Option B - Hybrid)",
            "=" * 60,
            "",
            "Architecture:",
        ]

        dims = self._layer_dims
        for i, dim in enumerate(dims):
            if i == 0:
                lines.append(f"  Input:  {dim}D (from text encoder)")
            elif i == len(dims) - 1:
                lines.append(f"  Output: {dim}D (ontological dimensions)")
            else:
                skip = " + skip" if self.config.use_skip_connections else ""
                lines.append(f"  Hidden {i}: {dim}D{skip}")

        lines.extend([
            "",
            "Ontological Output Dimensions:",
        ])
        for name in LAYER_NAMES:
            lines.append(f"  - {name}")

        lines.extend([
            "",
            f"Total Parameters: {self.parameter_count():,}",
            f"Skip Connections: {self.config.use_skip_connections}",
            f"Layer Norm: {self.config.use_layer_norm}",
            f"Dropout: {self.config.dropout}",
            "",
            "=" * 60,
        ])

        return "\n".join(lines)


def create_engine(
    encoder_name: str = "distilbert-base-uncased",
    hidden_dims: Tuple[int, ...] = (512, 256),
    use_skip_connections: bool = True,
    dropout: float = 0.1,
) -> OntologicalEngine:
    """
    Factory function to create an ontological engine.

    Args:
        encoder_name: Name of pretrained encoder
        hidden_dims: Sizes of hidden layers
        use_skip_connections: Whether to use ResNet-style skip connections
        dropout: Dropout probability

    Returns:
        Configured OntologicalEngine
    """
    config = OntologicalConfig(
        encoder_name=encoder_name,
        hidden_dims=hidden_dims,
        use_skip_connections=use_skip_connections,
        dropout=dropout,
    )
    return OntologicalEngine(config)
