#!/usr/bin/env python3
"""
Inference Metacognitive Monitor
================================

Real-time generation quality monitoring during inference.

Tracks coherence signals and can signal when generation should be:
- Aborted (quality too low)
- Restarted with different parameters
- Continued normally

Training Reference: MetacognitiveTracker in train_unified_llm.py:666-825

Author: Sovereign-1 Training Initiative
Date: January 2026
"""

import torch
import torch.nn.functional as F
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum
import math


class GenerationRecommendation(Enum):
    """Recommendations for generation control."""
    CONTINUE = "continue"
    SLOW_DOWN = "slow_down"  # Reduce temperature
    SPEED_UP = "speed_up"  # Increase temperature
    ABORT = "abort"  # Stop generation
    RESTART = "restart"  # Restart with different params
    STABILIZE = "stabilize"  # Apply additional sampling constraints


@dataclass
class MetacognitiveConfig:
    """Configuration for metacognitive monitoring."""
    coherence_window: int = 10
    alarm_threshold: float = 0.3
    excellent_threshold: float = 0.8
    consecutive_low_trigger: int = 3
    consecutive_high_trigger: int = 5
    entropy_weight: float = 0.6
    repetition_weight: float = 0.4


class InferenceMetacognition:
    """
    Real-time generation quality monitoring.

    Tracks coherence signals and can signal when generation
    should be aborted, restarted, or parameters adjusted.

    Example:
        monitor = InferenceMetacognition()

        for step in generation_loop:
            logits = model(tokens)
            meta = monitor.update(logits, hidden_state)

            if meta["recommendation"] == GenerationRecommendation.ABORT:
                break

            adjustments = monitor.get_generation_adjustment()
            temperature *= adjustments.get("temperature_multiplier", 1.0)
    """

    def __init__(self, config: Optional[MetacognitiveConfig] = None):
        """
        Initialize metacognitive monitor.

        Args:
            config: Monitoring configuration
        """
        self.config = config or MetacognitiveConfig()

        # History tracking
        self.coherence_history: List[float] = []
        self.entropy_history: List[float] = []
        self.hidden_state_history: List[torch.Tensor] = []
        self.token_history: List[int] = []

        # State
        self.consecutive_low: int = 0
        self.consecutive_high: int = 0
        self.total_tokens: int = 0
        self.alarm_triggered: bool = False

    def update(
        self,
        token_logits: torch.Tensor,
        hidden_state: Optional[torch.Tensor] = None,
        generated_token: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Update metacognitive state with new generation step.

        Computes:
        - Entropy of token distribution (proxy for confidence)
        - Optional: Hidden state coherence with previous
        - Repetition tracking

        Args:
            token_logits: [B, V] or [V] logits for next token
            hidden_state: Optional [B, D] or [D] hidden state
            generated_token: Optional generated token ID

        Returns:
            meta: Dict with recommendation, coherence, entropy, etc.
        """
        self.total_tokens += 1

        # Flatten if batched
        if token_logits.dim() > 1:
            token_logits = token_logits[0]

        # Compute token entropy
        probs = F.softmax(token_logits, dim=-1)
        entropy = -(probs * torch.log(probs + 1e-10)).sum().item()

        # Normalize entropy to [0, 1] (vocab size dependent)
        vocab_size = token_logits.shape[-1]
        max_entropy = math.log(vocab_size)
        normalized_entropy = entropy / max_entropy

        self.entropy_history.append(normalized_entropy)

        # Compute coherence proxy (lower entropy = higher confidence = higher coherence)
        entropy_coherence = 1.0 - normalized_entropy

        # Track token for repetition
        if generated_token is not None:
            self.token_history.append(generated_token)

        # Compute repetition penalty
        repetition_score = self._compute_repetition_score()

        # Combined coherence
        coherence = (
            self.config.entropy_weight * entropy_coherence +
            self.config.repetition_weight * (1.0 - repetition_score)
        )

        self.coherence_history.append(coherence)

        # Track hidden state for cross-step coherence
        if hidden_state is not None:
            if hidden_state.dim() > 1:
                hidden_state = hidden_state[0]
            self.hidden_state_history.append(hidden_state.detach().cpu())
            if len(self.hidden_state_history) > 10:
                self.hidden_state_history.pop(0)

        # Update consecutive counters
        if coherence < self.config.alarm_threshold:
            self.consecutive_low += 1
            self.consecutive_high = 0
        elif coherence > self.config.excellent_threshold:
            self.consecutive_high += 1
            self.consecutive_low = 0
        else:
            self.consecutive_low = 0
            self.consecutive_high = 0

        # Determine recommendation
        recommendation = self._get_recommendation()

        return {
            "recommendation": recommendation,
            "coherence": coherence,
            "entropy": normalized_entropy,
            "repetition_score": repetition_score,
            "consecutive_low": self.consecutive_low,
            "consecutive_high": self.consecutive_high,
            "alarm": self.alarm_triggered,
        }

    def _compute_repetition_score(self) -> float:
        """
        Compute repetition score from recent tokens.

        Returns:
            score: 0.0 (no repetition) to 1.0 (heavy repetition)
        """
        if len(self.token_history) < 3:
            return 0.0

        recent = self.token_history[-20:]

        # Bigram repetition
        bigrams = list(zip(recent[:-1], recent[1:]))
        unique_bigrams = len(set(bigrams))
        bigram_diversity = unique_bigrams / max(1, len(bigrams))

        # Single token repetition
        unique_tokens = len(set(recent))
        token_diversity = unique_tokens / len(recent)

        # Combined (lower diversity = higher repetition)
        repetition = 1.0 - (0.5 * bigram_diversity + 0.5 * token_diversity)

        return repetition

    def _get_recommendation(self) -> GenerationRecommendation:
        """Get generation recommendation based on current state."""
        # Check for abort condition
        if self.consecutive_low >= self.config.consecutive_low_trigger:
            self.alarm_triggered = True
            return GenerationRecommendation.ABORT

        # Check recent history for sustained low coherence
        if len(self.coherence_history) >= 5:
            recent_avg = sum(self.coherence_history[-5:]) / 5
            if recent_avg < self.config.alarm_threshold:
                return GenerationRecommendation.SLOW_DOWN

        # Check for excellent performance
        if self.consecutive_high >= self.config.consecutive_high_trigger:
            return GenerationRecommendation.SPEED_UP

        # Check repetition
        if len(self.token_history) >= 10:
            rep_score = self._compute_repetition_score()
            if rep_score > 0.7:
                return GenerationRecommendation.STABILIZE

        return GenerationRecommendation.CONTINUE

    def get_generation_adjustment(self) -> Dict[str, float]:
        """
        Suggest generation parameter adjustments based on state.

        Returns:
            adjustments: Dict with temperature_multiplier, top_p_adjustment, etc.
        """
        if not self.coherence_history:
            return {}

        avg_coherence = sum(self.coherence_history[-10:]) / min(10, len(self.coherence_history))
        recent_entropy = self.entropy_history[-1] if self.entropy_history else 0.5

        adjustments = {}

        if avg_coherence < self.config.alarm_threshold:
            # Low coherence: reduce temperature for more deterministic outputs
            adjustments["temperature_multiplier"] = 0.7
            adjustments["top_p_adjustment"] = -0.1
            adjustments["reason"] = "low_coherence"

        elif avg_coherence > self.config.excellent_threshold:
            # High coherence: can afford more creativity
            adjustments["temperature_multiplier"] = 1.1
            adjustments["top_p_adjustment"] = 0.05
            adjustments["reason"] = "high_coherence"

        elif recent_entropy > 0.8:
            # Very high entropy: sharpen distribution
            adjustments["temperature_multiplier"] = 0.8
            adjustments["top_k_adjustment"] = -10
            adjustments["reason"] = "high_entropy"

        # Check for repetition issues
        if len(self.token_history) >= 10:
            rep_score = self._compute_repetition_score()
            if rep_score > 0.5:
                # Increase diversity
                adjustments["temperature_multiplier"] = adjustments.get("temperature_multiplier", 1.0) * 1.1
                adjustments["repetition_penalty"] = 1.2
                adjustments["reason"] = adjustments.get("reason", "") + "_repetitive"

        return adjustments

    def compute_hidden_coherence(self) -> float:
        """
        Compute coherence between recent hidden states.

        Returns:
            coherence: Average cosine similarity between consecutive states
        """
        if len(self.hidden_state_history) < 2:
            return 1.0

        similarities = []
        for i in range(1, len(self.hidden_state_history)):
            prev = self.hidden_state_history[i - 1].view(1, -1)
            curr = self.hidden_state_history[i].view(1, -1)
            sim = F.cosine_similarity(prev, curr).item()
            similarities.append(sim)

        return sum(similarities) / len(similarities)

    def get_status_line(self) -> str:
        """
        Get status line for monitoring display.

        Returns:
            status: Human-readable status string
        """
        if not self.coherence_history:
            return "Metacog: no data"

        avg_coherence = sum(self.coherence_history[-10:]) / min(10, len(self.coherence_history))
        avg_entropy = sum(self.entropy_history[-10:]) / min(10, len(self.entropy_history))

        recommendation = self._get_recommendation()

        parts = [
            f"Metacog",
            f"Coh: {avg_coherence:.2f}",
            f"Ent: {avg_entropy:.2f}",
            f"Rec: {recommendation.value}",
        ]

        if self.alarm_triggered:
            parts.append("ALARM!")

        return " | ".join(parts)

    def reset(self) -> None:
        """Reset all tracking state."""
        self.coherence_history = []
        self.entropy_history = []
        self.hidden_state_history = []
        self.token_history = []
        self.consecutive_low = 0
        self.consecutive_high = 0
        self.total_tokens = 0
        self.alarm_triggered = False

    def get_summary(self) -> Dict[str, Any]:
        """
        Get summary statistics for the generation session.

        Returns:
            summary: Dict with statistics
        """
        if not self.coherence_history:
            return {"tokens": 0, "status": "no_data"}

        return {
            "tokens": self.total_tokens,
            "avg_coherence": sum(self.coherence_history) / len(self.coherence_history),
            "min_coherence": min(self.coherence_history),
            "max_coherence": max(self.coherence_history),
            "avg_entropy": sum(self.entropy_history) / len(self.entropy_history),
            "alarm_triggered": self.alarm_triggered,
            "final_recommendation": self._get_recommendation().value,
            "repetition_score": self._compute_repetition_score(),
        }
