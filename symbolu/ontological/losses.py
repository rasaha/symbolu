"""
Ontological Engine - Loss Functions
====================================

Custom loss functions for training the 10D ontological engine:

1. Supervision Loss: MSE between predicted and target vectors
2. Purity Loss: Encourages dimension specialization (MI minimization)
3. Orthogonality Loss: Keeps dimensions decorrelated
4. Task-specific Losses: For reasoning and creativity heads
"""

import math
from typing import List, Optional, Dict, Tuple
from dataclasses import dataclass

from symbolu.ontological.types import LAYER_NAMES, LAYER_INDEX


@dataclass
class LossComponents:
    """Breakdown of all loss components."""
    total: float
    supervision: float
    purity: float
    orthogonality: float
    reasoning: Optional[float] = None
    creativity: Optional[float] = None

    def to_dict(self) -> Dict[str, float]:
        result = {
            "total": self.total,
            "supervision": self.supervision,
            "purity": self.purity,
            "orthogonality": self.orthogonality,
        }
        if self.reasoning is not None:
            result["reasoning"] = self.reasoning
        if self.creativity is not None:
            result["creativity"] = self.creativity
        return result


class OntologicalLoss:
    """
    Combined loss function for ontological engine training.

    Components:
    1. Supervision Loss: Direct supervision on dimension values
    2. Purity Loss: Mutual information minimization between dimensions
    3. Orthogonality Loss: Encourages decorrelated representations

    The purity loss is critical for preventing "dimension bleeding" -
    where O6 (Reasoning) starts to correlate with O2 (Creativity).

    Usage:
        loss_fn = OntologicalLoss(purity_weight=0.1)
        loss = loss_fn.compute(
            predictions=[[0.5, 0.2, ...]],
            targets=[[0.6, 0.1, ...]],
        )
    """

    def __init__(
        self,
        supervision_weight: float = 1.0,
        purity_weight: float = 0.1,
        orthogonality_weight: float = 0.05,
        dimension_weights: Optional[Dict[str, float]] = None,
    ):
        """
        Initialize the loss function.

        Args:
            supervision_weight: Weight for supervision loss
            purity_weight: Weight for purity/specialization loss
            orthogonality_weight: Weight for orthogonality loss
            dimension_weights: Optional per-dimension weights (e.g., boost O6)
        """
        self.supervision_weight = supervision_weight
        self.purity_weight = purity_weight
        self.orthogonality_weight = orthogonality_weight

        # Default: equal weight to all dimensions
        self.dimension_weights = dimension_weights or {
            name: 1.0 for name in LAYER_NAMES
        }

    def compute(
        self,
        predictions: List[List[float]],
        targets: Optional[List[List[float]]] = None,
        dimension_labels: Optional[List[Dict[str, float]]] = None,
    ) -> LossComponents:
        """
        Compute the combined loss.

        Args:
            predictions: Batch of 10D predictions
            targets: Optional full 10D target vectors
            dimension_labels: Optional per-dimension labels (sparse)

        Returns:
            LossComponents with breakdown of all losses
        """
        batch_size = len(predictions)

        # Supervision loss
        supervision_loss = 0.0
        if targets is not None:
            supervision_loss = self._supervision_loss(predictions, targets)
        elif dimension_labels is not None:
            supervision_loss = self._sparse_supervision_loss(predictions, dimension_labels)

        # Purity loss (encourage specialization)
        purity_loss = self._purity_loss(predictions)

        # Orthogonality loss (decorrelate dimensions)
        orthogonality_loss = self._orthogonality_loss(predictions)

        # Combined loss
        total = (
            self.supervision_weight * supervision_loss +
            self.purity_weight * purity_loss +
            self.orthogonality_weight * orthogonality_loss
        )

        return LossComponents(
            total=total,
            supervision=supervision_loss,
            purity=purity_loss,
            orthogonality=orthogonality_loss,
        )

    def _supervision_loss(
        self,
        predictions: List[List[float]],
        targets: List[List[float]],
    ) -> float:
        """
        Mean squared error between predictions and targets.

        Weighted by dimension_weights to emphasize certain dimensions.
        """
        total_loss = 0.0
        count = 0

        for pred, target in zip(predictions, targets):
            if target is None:
                continue
            for i in range(10):
                weight = self.dimension_weights.get(LAYER_NAMES[i], 1.0)
                diff = pred[i] - target[i]
                total_loss += weight * (diff ** 2)
                count += 1

        return total_loss / max(count, 1)

    def _sparse_supervision_loss(
        self,
        predictions: List[List[float]],
        dimension_labels: List[Dict[str, float]],
    ) -> float:
        """
        Supervision loss for sparse labels (only some dimensions labeled).

        Useful when you only have labels for O6 (reasoning) or O2 (creativity).
        """
        total_loss = 0.0
        count = 0

        for pred, labels in zip(predictions, dimension_labels):
            if labels is None:
                continue
            for dim_name, target_value in labels.items():
                if dim_name not in LAYER_INDEX:
                    continue
                idx = LAYER_INDEX[dim_name]
                weight = self.dimension_weights.get(dim_name, 1.0)
                diff = pred[idx] - target_value
                total_loss += weight * (diff ** 2)
                count += 1

        return total_loss / max(count, 1)

    def _purity_loss(self, predictions: List[List[float]]) -> float:
        """
        Purity loss: encourages each sample to specialize in few dimensions.

        Uses negative entropy to encourage sparse activations:
        - High purity = few dimensions active = low loss
        - Low purity = many dimensions equally active = high loss

        This prevents "dimension bleeding" where all dimensions activate together.
        """
        total_loss = 0.0

        for pred in predictions:
            # Convert to positive values (shift and scale)
            # tanh output is in [-1, 1], shift to [0, 1]
            positive = [(v + 1.0) / 2.0 for v in pred]

            # Normalize to probability distribution
            total = sum(positive) + 1e-10
            probs = [p / total for p in positive]

            # Compute entropy (higher = less pure)
            entropy = 0.0
            for p in probs:
                if p > 1e-10:
                    entropy -= p * math.log(p + 1e-10)

            # Normalize by max entropy (log(10))
            max_entropy = math.log(10)
            normalized_entropy = entropy / max_entropy

            # Loss = entropy (we want to minimize it for purity)
            total_loss += normalized_entropy

        return total_loss / max(len(predictions), 1)

    def _orthogonality_loss(self, predictions: List[List[float]]) -> float:
        """
        Orthogonality loss: encourages decorrelated dimensions across batch.

        Computes the correlation matrix between dimensions and penalizes
        off-diagonal correlations.

        This ensures O6 (Reasoning) doesn't always activate with O2 (Creativity).
        """
        if len(predictions) < 2:
            return 0.0

        batch_size = len(predictions)

        # Compute mean for each dimension
        means = [0.0] * 10
        for pred in predictions:
            for i in range(10):
                means[i] += pred[i]
        means = [m / batch_size for m in means]

        # Compute covariance matrix
        cov = [[0.0] * 10 for _ in range(10)]
        for pred in predictions:
            centered = [pred[i] - means[i] for i in range(10)]
            for i in range(10):
                for j in range(10):
                    cov[i][j] += centered[i] * centered[j]

        for i in range(10):
            for j in range(10):
                cov[i][j] /= batch_size

        # Compute standard deviations
        stds = [math.sqrt(cov[i][i] + 1e-10) for i in range(10)]

        # Compute correlation matrix and sum off-diagonal elements
        off_diagonal_sum = 0.0
        for i in range(10):
            for j in range(i + 1, 10):
                # Correlation between dimensions i and j
                corr = cov[i][j] / (stds[i] * stds[j] + 1e-10)
                # Penalize high correlations
                off_diagonal_sum += corr ** 2

        # Normalize by number of pairs
        num_pairs = 10 * 9 / 2
        return off_diagonal_sum / num_pairs


class ReasoningLoss:
    """
    Task-specific loss for reasoning quality.

    Focuses on O6_REASONING dimension with auxiliary signals.
    """

    def __init__(self, weight: float = 1.0):
        self.weight = weight

    def compute(
        self,
        predictions: List[float],  # Reasoning head outputs
        targets: List[float],  # Reasoning quality labels (0-1)
    ) -> float:
        """Binary cross-entropy loss for reasoning quality."""
        total_loss = 0.0
        count = 0

        for pred, target in zip(predictions, targets):
            if target is None:
                continue
            # Clamp prediction to avoid log(0)
            pred = max(min(pred, 1.0 - 1e-7), 1e-7)
            # BCE loss
            loss = -(target * math.log(pred) + (1 - target) * math.log(1 - pred))
            total_loss += loss
            count += 1

        return self.weight * total_loss / max(count, 1)


class CreativityLoss:
    """
    Task-specific loss for creativity quality.

    Focuses on O2_FORMING dimension with novelty signals.
    """

    def __init__(self, weight: float = 1.0):
        self.weight = weight

    def compute(
        self,
        predictions: List[float],  # Creativity head outputs
        targets: List[float],  # Creativity quality labels (0-1)
        novelty_scores: Optional[List[float]] = None,  # Optional novelty bonus
    ) -> float:
        """
        MSE loss for creativity with optional novelty bonus.

        Novelty scores reward outputs that are distant from training distribution.
        """
        total_loss = 0.0
        count = 0

        for i, (pred, target) in enumerate(zip(predictions, targets)):
            if target is None:
                continue
            # Base MSE loss
            loss = (pred - target) ** 2

            # Optional novelty bonus (reduce loss for novel outputs)
            if novelty_scores is not None and i < len(novelty_scores):
                novelty = novelty_scores[i]
                # Higher novelty = lower loss penalty
                loss *= (1.0 - 0.5 * novelty)

            total_loss += loss
            count += 1

        return self.weight * total_loss / max(count, 1)


class CombinedLoss:
    """
    Full combined loss for multi-task training.

    Combines:
    - Ontological loss (supervision + purity + orthogonality)
    - Reasoning loss (for O6 task head)
    - Creativity loss (for O2 task head)
    """

    def __init__(
        self,
        ontological_weight: float = 1.0,
        reasoning_weight: float = 0.5,
        creativity_weight: float = 0.5,
        purity_weight: float = 0.1,
        orthogonality_weight: float = 0.05,
    ):
        self.ontological_loss = OntologicalLoss(
            purity_weight=purity_weight,
            orthogonality_weight=orthogonality_weight,
        )
        self.reasoning_loss = ReasoningLoss(weight=reasoning_weight)
        self.creativity_loss = CreativityLoss(weight=creativity_weight)
        self.ontological_weight = ontological_weight

    def compute(
        self,
        ontological_predictions: List[List[float]],
        ontological_targets: Optional[List[List[float]]] = None,
        dimension_labels: Optional[List[Dict[str, float]]] = None,
        reasoning_predictions: Optional[List[float]] = None,
        reasoning_targets: Optional[List[float]] = None,
        creativity_predictions: Optional[List[float]] = None,
        creativity_targets: Optional[List[float]] = None,
    ) -> LossComponents:
        """Compute full combined loss."""

        # Ontological loss
        onto_loss = self.ontological_loss.compute(
            ontological_predictions,
            ontological_targets,
            dimension_labels,
        )

        # Reasoning loss
        reasoning_loss_val = None
        if reasoning_predictions is not None and reasoning_targets is not None:
            reasoning_loss_val = self.reasoning_loss.compute(
                reasoning_predictions,
                reasoning_targets,
            )

        # Creativity loss
        creativity_loss_val = None
        if creativity_predictions is not None and creativity_targets is not None:
            creativity_loss_val = self.creativity_loss.compute(
                creativity_predictions,
                creativity_targets,
            )

        # Total loss
        total = self.ontological_weight * onto_loss.total
        if reasoning_loss_val is not None:
            total += reasoning_loss_val
        if creativity_loss_val is not None:
            total += creativity_loss_val

        return LossComponents(
            total=total,
            supervision=onto_loss.supervision,
            purity=onto_loss.purity,
            orthogonality=onto_loss.orthogonality,
            reasoning=reasoning_loss_val,
            creativity=creativity_loss_val,
        )
