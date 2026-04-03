#!/usr/bin/env python3
"""
Inference Gunas
================

Inference-time approximation of Sattva/Rajas/Tamas cognitive states.

Without gradients, we approximate:
- Sattva (Clarity): Token probability confidence x sequence coherence
- Rajas (Action): Token-to-token probability variance (activity)
- Tamas (Inertia): Repetition rate (stuckness)

Training Reference: TrainingGunas in train_unified_llm.py:3440-3539

Author: Sovereign-1 Training Initiative
Date: January 2026
"""

import torch
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
import math


@dataclass
class GunaConfig:
    """Configuration for Guna inference."""
    window_size: int = 20
    sattva_confidence_weight: float = 0.7
    sattva_coherence_weight: float = 0.3
    rajas_variance_scale: float = 10.0
    tamas_unique_window: int = 10


class InferenceGunas:
    """
    Inference-time Guna approximation using available signals.

    The three Gunas represent cognitive qualities:
    - Sattva (Clarity): High confidence, coherent generation
    - Rajas (Action): High variance, dynamic generation
    - Tamas (Inertia): Repetitive, stuck generation

    Example:
        gunas = InferenceGunas()

        for token_id, prob in generation:
            sattva, rajas, tamas = gunas.update(token_id, prob)
            print(f"S:{sattva:.2f} R:{rajas:.2f} T:{tamas:.2f}")

            # Adjust resonance alpha based on Sattva
            alpha = base_alpha * (1.0 + sattva * 0.5)
    """

    def __init__(self, config: Optional[GunaConfig] = None):
        """
        Initialize Guna tracker.

        Args:
            config: Guna configuration
        """
        self.config = config or GunaConfig()

        # History tracking
        self.token_probs: List[float] = []
        self.generated_tokens: List[int] = []
        self.coherence_scores: List[float] = []

        # Current Guna state
        self._sattva: float = 0.33
        self._rajas: float = 0.33
        self._tamas: float = 0.33

    def update(
        self,
        token_id: int,
        token_prob: float,
        top_probs: Optional[torch.Tensor] = None,
        coherence_score: Optional[float] = None,
    ) -> Tuple[float, float, float]:
        """
        Update Guna state with new generated token.

        Args:
            token_id: Generated token ID
            token_prob: Probability of the generated token
            top_probs: Optional tensor of top-k probabilities for entropy
            coherence_score: Optional external coherence score

        Returns:
            (sattva, rajas, tamas): Normalized to sum to 1.0
        """
        self.token_probs.append(token_prob)
        self.generated_tokens.append(token_id)

        if coherence_score is not None:
            self.coherence_scores.append(coherence_score)

        # Keep window
        if len(self.token_probs) > self.config.window_size:
            self.token_probs = self.token_probs[-self.config.window_size:]
            self.generated_tokens = self.generated_tokens[-self.config.window_size:]
            if self.coherence_scores:
                self.coherence_scores = self.coherence_scores[-self.config.window_size:]

        # Compute Sattva (Clarity)
        self._sattva = self._compute_sattva(top_probs)

        # Compute Rajas (Action/Activity)
        self._rajas = self._compute_rajas()

        # Compute Tamas (Inertia/Stuckness)
        self._tamas = self._compute_tamas()

        # Normalize to sum to 1
        total = self._sattva + self._rajas + self._tamas
        if total > 0:
            self._sattva /= total
            self._rajas /= total
            self._tamas /= total
        else:
            self._sattva = self._rajas = self._tamas = 0.33

        return self._sattva, self._rajas, self._tamas

    def _compute_sattva(self, top_probs: Optional[torch.Tensor] = None) -> float:
        """
        Compute Sattva (Clarity) score.

        Based on:
        - Average token probability (confidence)
        - Optional coherence scores
        - Optional entropy from top_probs
        """
        if not self.token_probs:
            return 0.33

        # Base: average confidence
        avg_prob = sum(self.token_probs) / len(self.token_probs)

        # Optional: incorporate coherence
        if self.coherence_scores:
            avg_coherence = sum(self.coherence_scores) / len(self.coherence_scores)
            sattva = (
                self.config.sattva_confidence_weight * avg_prob +
                self.config.sattva_coherence_weight * avg_coherence
            )
        else:
            sattva = avg_prob

        # Optional: entropy adjustment from top_probs
        if top_probs is not None:
            # Lower entropy = higher clarity
            probs = top_probs.float()
            probs = probs / probs.sum()
            entropy = -(probs * torch.log(probs + 1e-10)).sum().item()
            max_entropy = math.log(len(probs))
            normalized_entropy = entropy / max(max_entropy, 1e-8)
            sattva = sattva * (1.0 - normalized_entropy * 0.5)

        return sattva

    def _compute_rajas(self) -> float:
        """
        Compute Rajas (Action/Activity) score.

        Based on probability variance - high variance indicates
        dynamic, changing generation.
        """
        if len(self.token_probs) < 2:
            return 0.33

        # Compute variance of probabilities
        mean_prob = sum(self.token_probs) / len(self.token_probs)
        variance = sum((p - mean_prob) ** 2 for p in self.token_probs) / len(self.token_probs)

        # Scale variance to [0, 1]
        rajas = min(1.0, variance * self.config.rajas_variance_scale)

        return rajas

    def _compute_tamas(self) -> float:
        """
        Compute Tamas (Inertia/Stuckness) score.

        Based on repetition rate - high repetition indicates
        stuck, inertial generation.
        """
        if len(self.generated_tokens) < 3:
            return 0.33

        recent = self.generated_tokens[-self.config.tamas_unique_window:]

        # Unique ratio (more unique = less tamas)
        unique_ratio = len(set(recent)) / len(recent)

        # Tamas = inverse of diversity
        tamas = 1.0 - unique_ratio

        # Bonus for immediate repetition (consecutive same token)
        if len(recent) >= 2:
            consecutive_repeats = sum(
                1 for i in range(1, len(recent)) if recent[i] == recent[i - 1]
            )
            repeat_ratio = consecutive_repeats / (len(recent) - 1)
            tamas = tamas * 0.7 + repeat_ratio * 0.3

        return tamas

    @property
    def sattva(self) -> float:
        """Get current Sattva (Clarity) value."""
        return self._sattva

    @property
    def rajas(self) -> float:
        """Get current Rajas (Action) value."""
        return self._rajas

    @property
    def tamas(self) -> float:
        """Get current Tamas (Inertia) value."""
        return self._tamas

    def get_dominant_guna(self) -> str:
        """
        Get the dominant Guna.

        Returns:
            name: "sattva", "rajas", or "tamas"
        """
        if self._sattva >= self._rajas and self._sattva >= self._tamas:
            return "sattva"
        elif self._rajas >= self._tamas:
            return "rajas"
        return "tamas"

    def get_resonance_modifier(self, base_alpha: float = 0.1) -> float:
        """
        Get resonance alpha modifier based on Guna state.

        Training formula:
            dynamic_alpha = base_alpha * (1.0 + (sattva * 1.5) - (rajas * 0.5))

        Args:
            base_alpha: Base resonance alpha

        Returns:
            modified_alpha: Adjusted alpha value
        """
        # Higher Sattva = stronger resonance (clearer connection)
        # Higher Rajas = slightly weaker resonance (too dynamic)
        # Tamas doesn't directly affect resonance

        modifier = 1.0 + (self._sattva * 1.5) - (self._rajas * 0.5)
        modifier = max(0.5, min(2.0, modifier))  # Clamp

        return base_alpha * modifier

    def get_temperature_modifier(self, base_temp: float = 1.0) -> float:
        """
        Get temperature modifier based on Guna state.

        - High Sattva: Lower temperature (confident, focused)
        - High Rajas: Keep temperature (dynamic)
        - High Tamas: Higher temperature (break inertia)

        Args:
            base_temp: Base temperature

        Returns:
            modified_temp: Adjusted temperature
        """
        # High Tamas needs randomness to break repetition
        # High Sattva can afford lower temperature
        modifier = 1.0 + (self._tamas * 0.3) - (self._sattva * 0.2)
        modifier = max(0.5, min(1.5, modifier))

        return base_temp * modifier

    def get_status_line(self) -> str:
        """
        Get status line for monitoring display.

        Returns:
            status: Human-readable status string
        """
        dominant = self.get_dominant_guna()
        return (
            f"Gunas: S:{self._sattva:.2f} R:{self._rajas:.2f} T:{self._tamas:.2f} "
            f"[{dominant.upper()}]"
        )

    def reset(self) -> None:
        """Reset all state."""
        self.token_probs = []
        self.generated_tokens = []
        self.coherence_scores = []
        self._sattva = 0.33
        self._rajas = 0.33
        self._tamas = 0.33

    def get_state(self) -> Dict[str, Any]:
        """Get full state for serialization."""
        return {
            "sattva": self._sattva,
            "rajas": self._rajas,
            "tamas": self._tamas,
            "token_probs": self.token_probs[-20:],  # Last 20 only
            "tokens_generated": len(self.generated_tokens),
        }
