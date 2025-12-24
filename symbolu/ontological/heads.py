"""
Ontological Engine - Task Heads
================================

Multi-task heads that operate on the 10D ontological representation:

1. ReasoningHead: Produces reasoning quality scores from O6-focused features
2. CreativityHead: Produces creativity quality scores from O2-focused features
3. GenerationHead: Seq2seq decoder for text generation (future)

These heads attach to the 10D bottleneck and enable task-specific training
while keeping the ontological representation interpretable.
"""

import math
from typing import List, Optional, Tuple, Dict, Any
from dataclasses import dataclass

from symbolu.ontological.types import (
    LAYER_INDEX,
    REASONING_LAYERS,
    CREATIVITY_LAYERS,
)


@dataclass
class HeadConfig:
    """Configuration for a task head."""
    input_dim: int = 10  # Always 10 from ontological output
    hidden_dims: Tuple[int, ...] = (64, 32)
    output_dim: int = 1
    dropout: float = 0.1
    use_attention: bool = True  # Attend to relevant ontological dimensions


class TaskHead:
    """
    Base class for task-specific heads.

    Takes 10D ontological input and produces task-specific outputs.
    Uses attention to focus on relevant dimensions.
    """

    def __init__(
        self,
        config: Optional[HeadConfig] = None,
        focus_layers: Optional[List[str]] = None,
    ):
        self.config = config or HeadConfig()
        self.focus_layers = focus_layers or []
        self._init_weights()

    def _init_weights(self) -> None:
        """Initialize head weights."""
        cfg = self.config

        # Attention weights for focusing on specific dimensions
        self._attention_weights = [1.0] * 10
        if self.focus_layers:
            # Boost attention for focus layers
            for layer_name in self.focus_layers:
                if layer_name in LAYER_INDEX:
                    idx = LAYER_INDEX[layer_name]
                    self._attention_weights[idx] = 2.0  # 2x attention

        # Normalize attention weights
        total = sum(self._attention_weights)
        self._attention_weights = [w / total for w in self._attention_weights]

        # Build MLP layers
        dims = [cfg.input_dim] + list(cfg.hidden_dims) + [cfg.output_dim]
        self._weights: List[List[List[float]]] = []
        self._biases: List[List[float]] = []

        for i in range(len(dims) - 1):
            in_dim = dims[i]
            out_dim = dims[i + 1]

            # Xavier initialization
            scale = math.sqrt(2.0 / (in_dim + out_dim))
            weights = [
                [self._randn() * scale for _ in range(in_dim)]
                for _ in range(out_dim)
            ]
            biases = [0.0] * out_dim

            self._weights.append(weights)
            self._biases.append(biases)

    def _randn(self) -> float:
        """Generate random number from standard normal."""
        import random
        u1 = random.random()
        u2 = random.random()
        return math.sqrt(-2 * math.log(u1 + 1e-10)) * math.cos(2 * math.pi * u2)

    def _linear(
        self,
        x: List[float],
        weights: List[List[float]],
        biases: List[float],
    ) -> List[float]:
        """Apply linear transformation."""
        out_dim = len(weights)
        result = []
        for i in range(out_dim):
            val = biases[i]
            for j in range(len(x)):
                val += weights[i][j] * x[j]
            result.append(val)
        return result

    def _relu(self, x: List[float]) -> List[float]:
        """ReLU activation."""
        return [max(0.0, v) for v in x]

    def _sigmoid(self, x: List[float]) -> List[float]:
        """Sigmoid activation."""
        return [1.0 / (1.0 + math.exp(-min(max(v, -20), 20))) for v in x]

    def _apply_attention(self, ontological_input: List[float]) -> List[float]:
        """Apply attention weights to focus on relevant dimensions."""
        if not self.config.use_attention:
            return ontological_input

        return [
            ontological_input[i] * self._attention_weights[i]
            for i in range(10)
        ]

    def forward(
        self,
        ontological_input: List[float],
        training: bool = False,
    ) -> List[float]:
        """
        Forward pass through the task head.

        Args:
            ontological_input: 10D ontological vector
            training: Whether in training mode

        Returns:
            Task-specific output
        """
        # Apply attention to focus on relevant dimensions
        x = self._apply_attention(ontological_input)

        # Forward through MLP layers
        for i in range(len(self._weights) - 1):
            x = self._linear(x, self._weights[i], self._biases[i])
            x = self._relu(x)

        # Output layer with sigmoid (produces 0-1 score)
        x = self._linear(x, self._weights[-1], self._biases[-1])
        x = self._sigmoid(x)

        return x

    def get_weights(self) -> Dict[str, Any]:
        """Get weights for saving."""
        return {
            "attention_weights": self._attention_weights,
            "weights": self._weights,
            "biases": self._biases,
        }

    def set_weights(self, weights_dict: Dict[str, Any]) -> None:
        """Load weights."""
        self._attention_weights = weights_dict["attention_weights"]
        self._weights = weights_dict["weights"]
        self._biases = weights_dict["biases"]


class ReasoningHead(TaskHead):
    """
    Task head specialized for reasoning quality assessment.

    Focuses on:
    - O6_REASONING: Primary reasoning dimension
    - O1_THINKING: Supporting contemplative reasoning
    - O8_META_OBSERVING: Meta-cognitive reasoning

    Output: Reasoning quality score (0-1)
    """

    def __init__(self, config: Optional[HeadConfig] = None):
        config = config or HeadConfig(
            hidden_dims=(128, 64),
            output_dim=1,
        )
        super().__init__(config, focus_layers=REASONING_LAYERS)

    def assess_reasoning(self, ontological_input: List[float]) -> float:
        """
        Assess reasoning quality from ontological representation.

        Returns:
            Score from 0 (poor reasoning) to 1 (excellent reasoning)
        """
        output = self.forward(ontological_input, training=False)
        return output[0]

    def get_reasoning_breakdown(
        self,
        ontological_input: List[float],
    ) -> Dict[str, float]:
        """
        Get detailed breakdown of reasoning components.

        Returns dict with:
        - overall: Overall reasoning score
        - logical: Score from O6_REASONING
        - contemplative: Score from O1_THINKING
        - meta: Score from O8_META_OBSERVING
        """
        overall = self.assess_reasoning(ontological_input)

        # Individual dimension contributions
        o6_idx = LAYER_INDEX["O7_REASONING"]
        o1_idx = LAYER_INDEX["O5_COGNITION"]
        o8_idx = LAYER_INDEX["O9_WITNESSES"]

        # Normalize to 0-1 (from tanh -1 to 1)
        logical = (ontological_input[o6_idx] + 1) / 2
        contemplative = (ontological_input[o1_idx] + 1) / 2
        meta = (ontological_input[o8_idx] + 1) / 2

        return {
            "overall": overall,
            "logical": logical,
            "contemplative": contemplative,
            "meta": meta,
        }


class CreativityHead(TaskHead):
    """
    Task head specialized for creativity quality assessment.

    Focuses on:
    - O2_FORMING: Primary creative dimension
    - O9_UNIFYING: Synthesis and integration
    - O7_PURPOSING: Intentional creation

    Output: Creativity quality score (0-1)
    """

    def __init__(self, config: Optional[HeadConfig] = None):
        config = config or HeadConfig(
            hidden_dims=(128, 64),
            output_dim=1,
        )
        super().__init__(config, focus_layers=CREATIVITY_LAYERS)

    def assess_creativity(self, ontological_input: List[float]) -> float:
        """
        Assess creativity quality from ontological representation.

        Returns:
            Score from 0 (not creative) to 1 (highly creative)
        """
        output = self.forward(ontological_input, training=False)
        return output[0]

    def get_creativity_breakdown(
        self,
        ontological_input: List[float],
    ) -> Dict[str, float]:
        """
        Get detailed breakdown of creativity components.

        Returns dict with:
        - overall: Overall creativity score
        - forming: Score from O2_FORMING (artistic structure)
        - synthesis: Score from O9_UNIFYING (integration)
        - intentional: Score from O7_PURPOSING (purposeful creation)
        """
        overall = self.assess_creativity(ontological_input)

        # Individual dimension contributions
        o2_idx = LAYER_INDEX["O4_STRUCTURE"]
        o9_idx = LAYER_INDEX["O10_UNIFYING"]
        o7_idx = LAYER_INDEX["O8_PURPOSE"]

        # Normalize to 0-1 (from tanh -1 to 1)
        forming = (ontological_input[o2_idx] + 1) / 2
        synthesis = (ontological_input[o9_idx] + 1) / 2
        intentional = (ontological_input[o7_idx] + 1) / 2

        return {
            "overall": overall,
            "forming": forming,
            "synthesis": synthesis,
            "intentional": intentional,
        }


class NoveltyEstimator:
    """
    Estimates novelty of outputs for creativity training.

    Computes semantic distance from training distribution to reward
    novel but coherent outputs.
    """

    def __init__(self, memory_size: int = 1000):
        self.memory_size = memory_size
        self._memory: List[List[float]] = []

    def add_to_memory(self, ontological_vector: List[float]) -> None:
        """Add a vector to the memory bank."""
        self._memory.append(ontological_vector)
        if len(self._memory) > self.memory_size:
            self._memory.pop(0)

    def compute_novelty(self, ontological_vector: List[float]) -> float:
        """
        Compute novelty score for a vector.

        Returns:
            Score from 0 (seen before) to 1 (highly novel)
        """
        if not self._memory:
            return 0.5  # Neutral if no memory

        # Compute average distance to memory
        total_distance = 0.0
        for mem_vec in self._memory:
            dist = self._cosine_distance(ontological_vector, mem_vec)
            total_distance += dist

        avg_distance = total_distance / len(self._memory)

        # Normalize to 0-1 (cosine distance is 0-2)
        novelty = min(avg_distance / 2.0, 1.0)

        return novelty

    def _cosine_distance(self, a: List[float], b: List[float]) -> float:
        """Compute cosine distance between two vectors."""
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(x * x for x in b))
        if norm_a < 1e-10 or norm_b < 1e-10:
            return 1.0
        similarity = dot / (norm_a * norm_b)
        return 1.0 - similarity


class MultiTaskHead:
    """
    Combined multi-task head with reasoning and creativity outputs.

    Enables joint training while maintaining specialized assessment.
    """

    def __init__(
        self,
        reasoning_config: Optional[HeadConfig] = None,
        creativity_config: Optional[HeadConfig] = None,
    ):
        self.reasoning_head = ReasoningHead(reasoning_config)
        self.creativity_head = CreativityHead(creativity_config)
        self.novelty_estimator = NoveltyEstimator()

    def forward(
        self,
        ontological_input: List[float],
        training: bool = False,
    ) -> Dict[str, float]:
        """
        Get all task outputs from ontological representation.

        Returns:
            Dict with reasoning_score, creativity_score, novelty_score
        """
        reasoning = self.reasoning_head.assess_reasoning(ontological_input)
        creativity = self.creativity_head.assess_creativity(ontological_input)
        novelty = self.novelty_estimator.compute_novelty(ontological_input)

        if training:
            self.novelty_estimator.add_to_memory(ontological_input)

        return {
            "reasoning_score": reasoning,
            "creativity_score": creativity,
            "novelty_score": novelty,
        }

    def get_full_breakdown(
        self,
        ontological_input: List[float],
    ) -> Dict[str, Any]:
        """Get full breakdown of all task outputs."""
        return {
            "reasoning": self.reasoning_head.get_reasoning_breakdown(ontological_input),
            "creativity": self.creativity_head.get_creativity_breakdown(ontological_input),
            "novelty": self.novelty_estimator.compute_novelty(ontological_input),
        }

    def get_weights(self) -> Dict[str, Any]:
        """Get all head weights for saving."""
        return {
            "reasoning": self.reasoning_head.get_weights(),
            "creativity": self.creativity_head.get_weights(),
        }

    def set_weights(self, weights_dict: Dict[str, Any]) -> None:
        """Load all head weights."""
        self.reasoning_head.set_weights(weights_dict["reasoning"])
        self.creativity_head.set_weights(weights_dict["creativity"])
