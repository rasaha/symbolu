"""
Router Trainer
==============

Trains intent classification models for routing queries.
Uses a simple softmax classifier over embeddings.
"""

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import random

from symbolu.training.schemas import QueryIntentPair, IntentLabel
from symbolu.training.trainers.embedding_trainer import EmbeddingTrainer


@dataclass
class RouterTrainerConfig:
    """Configuration for router training."""
    embedding_dim: int = 768
    learning_rate: float = 0.1
    epochs: int = 20
    batch_size: int = 32
    seed: int = 42
    checkpoint_dir: str = "symbolu/training/checkpoints"


@dataclass
class RouterMetrics:
    """Metrics from training."""
    epoch: int
    loss: float
    accuracy: float
    per_class_accuracy: Dict[str, float]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "epoch": self.epoch,
            "loss": self.loss,
            "accuracy": self.accuracy,
            "per_class_accuracy": self.per_class_accuracy,
        }


class RouterTrainer:
    """
    Trains intent classification models.

    Uses a simple linear classifier:
    1. Embed query using provided embedder
    2. Apply linear layer + softmax for classification
    3. Train using cross-entropy loss

    For production, this can be replaced with more sophisticated
    classifiers (BERT fine-tuning, etc.) using the same interface.

    Usage:
        embedder = EmbeddingTrainer(config)
        trainer = RouterTrainer(config, embedder)
        metrics = trainer.train(intent_pairs)
        trainer.save("router.json")
    """

    # Intent labels in consistent order
    LABELS = [
        IntentLabel.REASONING,
        IntentLabel.REFLECTIVE,
        IntentLabel.CREATIVE,
        IntentLabel.RELATIONSHIP,
        IntentLabel.ACTION,
        IntentLabel.GENERAL,
    ]

    def __init__(
        self,
        config: Optional[RouterTrainerConfig] = None,
        embedder: Optional[EmbeddingTrainer] = None,
    ):
        self.config = config or RouterTrainerConfig()
        self.rng = random.Random(self.config.seed)

        # Use provided embedder or create new one
        self.embedder = embedder

        # Linear layer weights: num_classes x embedding_dim
        num_classes = len(self.LABELS)
        dim = self.config.embedding_dim
        self._weights: List[List[float]] = [
            [self.rng.gauss(0, 0.1) for _ in range(dim)]
            for _ in range(num_classes)
        ]
        self._bias: List[float] = [0.0] * num_classes

        # Label to index mapping
        self._label_to_idx = {label: i for i, label in enumerate(self.LABELS)}

        # Training history
        self.history: List[RouterMetrics] = []

    def _embed(self, text: str) -> List[float]:
        """Get embedding for text."""
        if self.embedder:
            return self.embedder.embed(text)
        else:
            # Fall back to hash-based embedding
            import hashlib
            dim = self.config.embedding_dim
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
                        return vectors[:dim]
            return vectors[:dim]

    def _softmax(self, logits: List[float]) -> List[float]:
        """Compute softmax probabilities."""
        # Subtract max for numerical stability
        max_val = max(logits)
        exp_vals = [math.exp(x - max_val) for x in logits]
        total = sum(exp_vals)
        return [e / total for e in exp_vals]

    def _forward(self, embedding: List[float]) -> List[float]:
        """Compute class logits from embedding."""
        logits = []
        for i in range(len(self.LABELS)):
            val = self._bias[i]
            for j, emb_val in enumerate(embedding):
                val += self._weights[i][j] * emb_val
            logits.append(val)
        return logits

    def predict(self, query: str) -> Tuple[IntentLabel, float, Dict[str, float]]:
        """
        Predict intent for a query.

        Returns:
            Tuple of (predicted_label, confidence, all_probabilities)
        """
        embedding = self._embed(query)
        logits = self._forward(embedding)
        probs = self._softmax(logits)

        # Find max
        max_idx = 0
        max_prob = probs[0]
        for i, p in enumerate(probs):
            if p > max_prob:
                max_prob = p
                max_idx = i

        all_probs = {label.value: probs[i] for i, label in enumerate(self.LABELS)}
        return self.LABELS[max_idx], max_prob, all_probs

    def _cross_entropy_loss(
        self,
        probs: List[float],
        target_idx: int,
    ) -> float:
        """Compute cross-entropy loss."""
        # Clip for numerical stability
        eps = 1e-10
        return -math.log(max(probs[target_idx], eps))

    def _compute_gradients(
        self,
        pairs: List[QueryIntentPair],
    ) -> Tuple[List[List[float]], List[float], float]:
        """
        Compute gradients for a batch.

        Returns (weight_grads, bias_grads, avg_loss)
        """
        num_classes = len(self.LABELS)
        dim = self.config.embedding_dim
        weight_grads = [[0.0] * dim for _ in range(num_classes)]
        bias_grads = [0.0] * num_classes
        total_loss = 0.0

        for pair in pairs:
            embedding = self._embed(pair.query)
            logits = self._forward(embedding)
            probs = self._softmax(logits)

            target_idx = self._label_to_idx[pair.intent]
            loss = self._cross_entropy_loss(probs, target_idx)
            total_loss += loss

            # Gradient of softmax cross-entropy: prob - one_hot
            for i in range(num_classes):
                gradient = probs[i] - (1.0 if i == target_idx else 0.0)
                bias_grads[i] += gradient / len(pairs)
                for j, emb_val in enumerate(embedding):
                    weight_grads[i][j] += gradient * emb_val / len(pairs)

        return weight_grads, bias_grads, total_loss / len(pairs)

    def train(
        self,
        pairs: List[QueryIntentPair],
        verbose: bool = True,
    ) -> List[RouterMetrics]:
        """
        Train intent classifier.

        Args:
            pairs: List of query-intent pairs
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
                for i in range(len(self.LABELS)):
                    self._bias[i] -= lr * bias_grads[i]
                    for j in range(self.config.embedding_dim):
                        self._weights[i][j] -= lr * weight_grads[i][j]

            # Compute metrics
            metrics = self._compute_epoch_metrics(pairs, epoch + 1, epoch_loss / max(num_batches, 1))
            self.history.append(metrics)

            if verbose:
                print(f"Epoch {epoch + 1}/{self.config.epochs}: "
                      f"loss={metrics.loss:.4f}, acc={metrics.accuracy:.2%}")

        return self.history

    def _compute_epoch_metrics(
        self,
        pairs: List[QueryIntentPair],
        epoch: int,
        loss: float,
    ) -> RouterMetrics:
        """Compute metrics for an epoch."""
        correct_per_class: Dict[str, int] = {}
        total_per_class: Dict[str, int] = {}
        total_correct = 0

        for label in self.LABELS:
            correct_per_class[label.value] = 0
            total_per_class[label.value] = 0

        for pair in pairs:
            predicted, _, _ = self.predict(pair.query)
            total_per_class[pair.intent.value] += 1

            if predicted == pair.intent:
                total_correct += 1
                correct_per_class[pair.intent.value] += 1

        per_class_acc = {}
        for label in self.LABELS:
            total = total_per_class[label.value]
            if total > 0:
                per_class_acc[label.value] = correct_per_class[label.value] / total
            else:
                per_class_acc[label.value] = 0.0

        return RouterMetrics(
            epoch=epoch,
            loss=loss,
            accuracy=total_correct / len(pairs) if pairs else 0.0,
            per_class_accuracy=per_class_acc,
        )

    def save(self, path: str) -> None:
        """Save trained model to file."""
        checkpoint_path = Path(path)
        checkpoint_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "config": {
                "embedding_dim": self.config.embedding_dim,
            },
            "weights": self._weights,
            "bias": self._bias,
            "labels": [label.value for label in self.LABELS],
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
        self.config.embedding_dim = data["config"]["embedding_dim"]
        self.history = [
            RouterMetrics(**m) for m in data.get("history", [])
        ]
