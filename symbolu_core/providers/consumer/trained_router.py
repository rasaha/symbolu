"""
Trained Router Provider (Consumer)
==================================

Consumer router provider using trained classifier.
Supports loading trained router models from Phase 4.
Falls back to GENERAL routing if no model is loaded.

Trained Model:
- Linear classifier on top of embeddings
- 6 output classes (ModelType enum)
- Trained on labeled query-intent pairs
"""

import json
import math
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

from symbolu_core.providers.interfaces.router_provider import (
    RouterProvider,
    RoutingDecision,
    ModelType,
)
from symbolu_core.providers.consumer.learned_embedding import LearnedEmbeddingProvider


# Mapping from IntentLabel to ModelType
INTENT_TO_MODEL_TYPE = {
    "reasoning": ModelType.REASONING,
    "reflective": ModelType.REFLECTIVE,
    "creative": ModelType.CREATIVE,
    "relationship": ModelType.RELATIONSHIP,
    "action": ModelType.ACTION,
    "general": ModelType.GENERAL,
}

# Mapping to dominant layer
INTENT_TO_LAYER = {
    "reasoning": "O7_REASONING",
    "reflective": "O10_UNIFYING",
    "creative": "O5_CREATING",
    "relationship": "O4_FEELING",
    "action": "O3_EXECUTION",
    "general": "O7_REASONING",
}


class TrainedRouterProvider(RouterProvider):
    """
    Consumer router provider using trained classifier.

    Can operate in two modes:
    1. Trained mode: Uses loaded classifier model
    2. Fallback mode: Returns GENERAL for all queries

    Attributes:
        model_path: Path to loaded model (if any)
        embedder: Embedding provider for encoding queries
    """

    # Intent labels in consistent order (must match RouterTrainer.LABELS)
    LABELS = [
        "reasoning", "reflective", "creative",
        "relationship", "action", "general",
    ]

    def __init__(
        self,
        model_path: Optional[str] = None,
        embedder: Optional[LearnedEmbeddingProvider] = None,
    ):
        """
        Initialize the trained router provider.

        Args:
            model_path: Optional path to trained model checkpoint
            embedder: Optional embedding provider (creates one if not provided)
        """
        self._model_path: Optional[str] = None
        self._weights: Optional[List[List[float]]] = None
        self._bias: Optional[List[float]] = None
        self._embedding_dim: int = 768
        self._embedder = embedder or LearnedEmbeddingProvider()

        if model_path:
            self.load_model(model_path)

    def load_model(self, model_path: str) -> None:
        """
        Load a trained router model.

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
        self._embedding_dim = data.get("config", {}).get("embedding_dim", 768)
        self._model_path = model_path

    def is_model_loaded(self) -> bool:
        """Check if a trained model is loaded."""
        return self._weights is not None and self._bias is not None

    def route(self, query: str) -> RoutingDecision:
        """
        Route a query using trained classifier.

        If a model is loaded, runs the classifier.
        Otherwise, returns GENERAL with placeholder values.

        Args:
            query: The input query/prompt

        Returns:
            RoutingDecision with model type and confidence
        """
        if self.is_model_loaded():
            return self._route_with_model(query)
        else:
            return self._route_fallback(query)

    def _route_with_model(self, query: str) -> RoutingDecision:
        """Route using trained classifier."""
        # Get embedding
        embedding = self._embedder.embed(query)

        # Compute logits
        logits = self._forward(embedding)

        # Get probabilities
        probs = self._softmax(logits)

        # Find best prediction
        best_idx = 0
        best_prob = probs[0]
        for i, p in enumerate(probs):
            if p > best_prob:
                best_prob = p
                best_idx = i

        predicted_label = self.LABELS[best_idx]

        # Build layer scores from probabilities
        layer_scores = []
        for i, label in enumerate(self.LABELS):
            layer = INTENT_TO_LAYER[label]
            layer_scores.append((layer, probs[i]))
        layer_scores.sort(key=lambda x: x[1], reverse=True)

        # Build trace
        trace = {
            "provider": "trained",
            "model_loaded": True,
            "predicted_label": predicted_label,
            "probabilities": {label: probs[i] for i, label in enumerate(self.LABELS)},
            "query_length": len(query),
        }

        return RoutingDecision(
            model_type=INTENT_TO_MODEL_TYPE[predicted_label],
            confidence=best_prob,
            dominant_layer=INTENT_TO_LAYER[predicted_label],
            layer_scores=tuple(layer_scores[:3]),  # Top 3 layers
            trace=trace,
        )

    def _route_fallback(self, query: str) -> RoutingDecision:
        """Fallback routing when no model is loaded."""
        trace = {
            "provider": "trained",
            "model_loaded": False,
            "stub_mode": True,
            "query_length": len(query),
            "note": "No model loaded. Returning GENERAL.",
        }

        return RoutingDecision(
            model_type=ModelType.GENERAL,
            confidence=0.5,
            dominant_layer="O7_REASONING",
            layer_scores=(
                ("O7_REASONING", 0.2),
                ("O10_UNIFYING", 0.15),
                ("O3_EXECUTION", 0.1),
            ),
            trace=trace,
        )

    def _forward(self, embedding: List[float]) -> List[float]:
        """Compute class logits from embedding."""
        logits = []
        for i in range(len(self.LABELS)):
            val = self._bias[i]
            for j, emb_val in enumerate(embedding):
                if j < len(self._weights[i]):
                    val += self._weights[i][j] * emb_val
            logits.append(val)
        return logits

    def _softmax(self, logits: List[float]) -> List[float]:
        """Compute softmax probabilities."""
        max_val = max(logits)
        exp_vals = [math.exp(x - max_val) for x in logits]
        total = sum(exp_vals)
        return [e / total for e in exp_vals]

    def route_batch(self, queries: List[str]) -> List[RoutingDecision]:
        """
        Batch route multiple queries.

        Args:
            queries: List of input queries

        Returns:
            List of RoutingDecision objects (one per query)
        """
        return [self.route(query) for query in queries]

    def predict_with_probs(
        self,
        query: str,
    ) -> Tuple[str, float, Dict[str, float]]:
        """
        Predict intent label with all probabilities.

        Useful for debugging and analysis.

        Args:
            query: Input query

        Returns:
            Tuple of (predicted_label, confidence, all_probabilities)
        """
        if not self.is_model_loaded():
            return "general", 0.5, {label: 1/6 for label in self.LABELS}

        embedding = self._embedder.embed(query)
        logits = self._forward(embedding)
        probs = self._softmax(logits)

        best_idx = max(range(len(probs)), key=lambda i: probs[i])
        all_probs = {label: probs[i] for i, label in enumerate(self.LABELS)}

        return self.LABELS[best_idx], probs[best_idx], all_probs
