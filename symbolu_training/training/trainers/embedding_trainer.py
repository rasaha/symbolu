"""
Embedding Trainer
=================

Trains embedding models using contrastive learning on paraphrase pairs.
Uses a simple neural approach that can work without heavy ML dependencies.
"""

import hashlib
import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import random

from symbolu_training.training.schemas import ParaphrasePair


@dataclass
class EmbeddingTrainerConfig:
    """Configuration for embedding training."""
    dimension: int = 768
    learning_rate: float = 0.01
    margin: float = 0.5  # Contrastive margin
    epochs: int = 10
    batch_size: int = 32
    seed: int = 42
    checkpoint_dir: str = "symbolu/training/checkpoints"


@dataclass
class TrainingMetrics:
    """Metrics from training."""
    epoch: int
    loss: float
    accuracy: float
    similar_avg_dist: float
    dissimilar_avg_dist: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "epoch": self.epoch,
            "loss": self.loss,
            "accuracy": self.accuracy,
            "similar_avg_dist": self.similar_avg_dist,
            "dissimilar_avg_dist": self.dissimilar_avg_dist,
        }


class EmbeddingTrainer:
    """
    Trains embedding models using contrastive learning.

    This implementation uses a simple learned transformation approach:
    1. Start with hash-based base embeddings
    2. Learn a transformation matrix to optimize contrastive loss
    3. Push similar pairs together, dissimilar pairs apart

    For production, this can be replaced with PyTorch/TensorFlow
    implementations using the same interface.

    Usage:
        trainer = EmbeddingTrainer(config)
        metrics = trainer.train(paraphrase_pairs)
        trainer.save("model.json")
    """

    def __init__(self, config: Optional[EmbeddingTrainerConfig] = None):
        self.config = config or EmbeddingTrainerConfig()
        self.rng = random.Random(self.config.seed)

        # Learnable parameters: transformation matrix
        # W is a dimension x dimension matrix (initialized near identity)
        self._weights: List[List[float]] = self._init_weights()
        self._bias: List[float] = [0.0] * self.config.dimension

        # Vocabulary cache for base embeddings
        self._vocab_cache: Dict[str, List[float]] = {}

        # Training history
        self.history: List[TrainingMetrics] = []

    def _init_weights(self) -> List[List[float]]:
        """Initialize weight matrix (near identity with small noise)."""
        dim = self.config.dimension
        weights = []
        for i in range(dim):
            row = []
            for j in range(dim):
                if i == j:
                    # Diagonal: start near 1
                    row.append(1.0 + self.rng.gauss(0, 0.01))
                else:
                    # Off-diagonal: start near 0
                    row.append(self.rng.gauss(0, 0.01))
            weights.append(row)
        return weights

    def _text_to_base_embedding(self, text: str) -> List[float]:
        """Generate base embedding using hash function (deterministic)."""
        if text in self._vocab_cache:
            return self._vocab_cache[text]

        dim = self.config.dimension
        vectors = []
        num_hashes = (dim + 7) // 8

        for i in range(num_hashes):
            seed = f"{text.lower().strip()}_{i}"
            hash_bytes = hashlib.sha256(seed.encode("utf-8")).digest()
            for j in range(0, len(hash_bytes), 4):
                chunk = hash_bytes[j:j + 4]
                value = int.from_bytes(chunk, byteorder="big", signed=True)
                normalized = value / (2**31)
                vectors.append(normalized)
                if len(vectors) >= dim:
                    break
            if len(vectors) >= dim:
                break

        result = vectors[:dim]
        self._vocab_cache[text] = result
        return result

    def _transform(self, base_vec: List[float]) -> List[float]:
        """Apply learned transformation to base embedding."""
        dim = self.config.dimension
        result = []
        for i in range(dim):
            val = self._bias[i]
            for j in range(dim):
                val += self._weights[i][j] * base_vec[j]
            result.append(val)
        return result

    def _normalize(self, vec: List[float]) -> List[float]:
        """L2 normalize a vector."""
        norm = math.sqrt(sum(v * v for v in vec))
        if norm < 1e-10:
            return vec
        return [v / norm for v in vec]

    def embed(self, text: str) -> List[float]:
        """Generate embedding for text using learned transformation."""
        base = self._text_to_base_embedding(text)
        transformed = self._transform(base)
        return self._normalize(transformed)

    def _cosine_distance(self, vec_a: List[float], vec_b: List[float]) -> float:
        """Compute cosine distance (1 - similarity)."""
        dot = sum(a * b for a, b in zip(vec_a, vec_b))
        # Vectors are normalized, so dot product is cosine similarity
        return 1.0 - dot

    def _contrastive_loss(
        self,
        vec_a: List[float],
        vec_b: List[float],
        similar: bool,
    ) -> float:
        """
        Compute contrastive loss for a pair.

        Similar pairs: minimize distance
        Dissimilar pairs: maximize distance up to margin
        """
        dist = self._cosine_distance(vec_a, vec_b)

        if similar:
            # Pull together
            return dist * dist
        else:
            # Push apart (up to margin)
            return max(0.0, self.config.margin - dist) ** 2

    def _compute_gradients(
        self,
        pairs: List[ParaphrasePair],
    ) -> Tuple[List[List[float]], List[float], float]:
        """
        Compute gradients for a batch of pairs.

        Returns (weight_grads, bias_grads, avg_loss)
        """
        dim = self.config.dimension
        weight_grads = [[0.0] * dim for _ in range(dim)]
        bias_grads = [0.0] * dim
        total_loss = 0.0

        for pair in pairs:
            base_a = self._text_to_base_embedding(pair.query_a)
            base_b = self._text_to_base_embedding(pair.query_b)

            vec_a = self._normalize(self._transform(base_a))
            vec_b = self._normalize(self._transform(base_b))

            loss = self._contrastive_loss(vec_a, vec_b, pair.similar)
            total_loss += loss

            # Simplified gradient: push/pull in embedding space
            dist = self._cosine_distance(vec_a, vec_b)

            if pair.similar:
                # Gradient to reduce distance
                scale = 2.0 * dist
            else:
                # Gradient to increase distance (if within margin)
                if dist < self.config.margin:
                    scale = -2.0 * (self.config.margin - dist)
                else:
                    scale = 0.0

            # Update gradients (simplified: update towards/away from each other)
            for i in range(dim):
                diff = vec_a[i] - vec_b[i]
                for j in range(dim):
                    weight_grads[i][j] += scale * diff * (base_a[j] - base_b[j]) / len(pairs)
                bias_grads[i] += scale * diff / len(pairs)

        return weight_grads, bias_grads, total_loss / len(pairs)

    def train(
        self,
        pairs: List[ParaphrasePair],
        verbose: bool = True,
    ) -> List[TrainingMetrics]:
        """
        Train embeddings using contrastive learning.

        Args:
            pairs: List of paraphrase pairs
            verbose: Whether to print progress

        Returns:
            List of training metrics per epoch
        """
        self.history = []

        for epoch in range(self.config.epochs):
            # Shuffle pairs
            shuffled = list(pairs)
            self.rng.shuffle(shuffled)

            # Process in batches
            epoch_loss = 0.0
            num_batches = 0

            for i in range(0, len(shuffled), self.config.batch_size):
                batch = shuffled[i:i + self.config.batch_size]
                if not batch:
                    continue

                # Compute gradients
                weight_grads, bias_grads, batch_loss = self._compute_gradients(batch)
                epoch_loss += batch_loss
                num_batches += 1

                # Update weights
                lr = self.config.learning_rate
                dim = self.config.dimension
                for i in range(dim):
                    self._bias[i] -= lr * bias_grads[i]
                    for j in range(dim):
                        self._weights[i][j] -= lr * weight_grads[i][j]

            # Compute metrics
            metrics = self._compute_epoch_metrics(pairs, epoch + 1, epoch_loss / max(num_batches, 1))
            self.history.append(metrics)

            if verbose:
                print(f"Epoch {epoch + 1}/{self.config.epochs}: "
                      f"loss={metrics.loss:.4f}, acc={metrics.accuracy:.2%}, "
                      f"sim_dist={metrics.similar_avg_dist:.4f}, "
                      f"dissim_dist={metrics.dissimilar_avg_dist:.4f}")

        return self.history

    def _compute_epoch_metrics(
        self,
        pairs: List[ParaphrasePair],
        epoch: int,
        loss: float,
    ) -> TrainingMetrics:
        """Compute metrics for an epoch."""
        similar_dists = []
        dissimilar_dists = []
        correct = 0

        for pair in pairs:
            vec_a = self.embed(pair.query_a)
            vec_b = self.embed(pair.query_b)
            dist = self._cosine_distance(vec_a, vec_b)

            if pair.similar:
                similar_dists.append(dist)
                # Correct if distance is small
                if dist < 0.5:
                    correct += 1
            else:
                dissimilar_dists.append(dist)
                # Correct if distance is large
                if dist >= 0.5:
                    correct += 1

        return TrainingMetrics(
            epoch=epoch,
            loss=loss,
            accuracy=correct / len(pairs) if pairs else 0.0,
            similar_avg_dist=sum(similar_dists) / len(similar_dists) if similar_dists else 0.0,
            dissimilar_avg_dist=sum(dissimilar_dists) / len(dissimilar_dists) if dissimilar_dists else 0.0,
        )

    def save(self, path: str) -> None:
        """Save trained model to file."""
        checkpoint_path = Path(path)
        checkpoint_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "config": {
                "dimension": self.config.dimension,
                "margin": self.config.margin,
            },
            "weights": self._weights,
            "bias": self._bias,
            "history": [m.to_dict() for m in self.history],
        }

        with open(checkpoint_path, "w") as f:
            json.dump(data, f)

    def load(self, path: str) -> None:
        """Load trained model from file."""
        with open(path, "r") as f:
            data = json.load(f)

        self._weights = data["weights"]
        self._bias = data["bias"]
        self.config.dimension = data["config"]["dimension"]
        self.config.margin = data["config"]["margin"]
        self.history = [
            TrainingMetrics(**m) for m in data.get("history", [])
        ]

    def get_dimension(self) -> int:
        """Return embedding dimension."""
        return self.config.dimension
