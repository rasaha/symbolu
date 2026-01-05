"""
Inference Gunas Module
======================

Inference-time Guna (Sattva/Rajas/Tamas) approximation using available signals.

This module implements the inference counterpart to TrainingGunas
(train_unified_llm.py:3440-3539), approximating cognitive states from
generation dynamics instead of training metrics (gradients, loss).

Mappings:
- **Sattva (Clarity):** Token probability confidence × sequence coherence
- **Rajas (Action):** Token-to-token probability variance (activity)
- **Tamas (Inertia):** Repetition rate / unique token ratio

The Gunas drive dynamic resonance alpha in EvolutionaryInferenceEngine
and inform metacognitive recommendations.

Usage:
------
    from symbolu.inference import InferenceGunas

    gunas = InferenceGunas(window_size=20)

    for token_id, prob in generated_tokens:
        s, r, t = gunas.update(token_id, prob)

        # Feed to EvolutionaryInferenceEngine
        engine.update_gunas(s, r, t)

        # High Tamas = repetition loop detected
        if t > 0.6:
            temperature *= 1.2  # Increase randomness
"""

import math
from typing import Dict, List, Tuple, Optional, Any
from collections import deque

import torch


class InferenceGunas:
    """
    Inference-time Guna approximation using generation dynamics.

    Without gradients and loss, we approximate:
    - Sattva: Token probability confidence (higher = clearer intent)
    - Rajas: Probability variance between tokens (activity/change)
    - Tamas: Repetition rate (inertia/stuckness)

    This bridges gap 2.2 from INFERENCE_HYBRID_TRANSFORMER_GAPS.md.

    Args:
        window_size: Number of tokens to track for statistics
        sattva_confidence_weight: Weight for confidence in Sattva (vs entropy)
        rajas_variance_scale: Scaling factor for variance → Rajas
        tamas_ngram_order: N-gram order for repetition detection (2=bigrams)

    Attributes:
        current_gunas: Current (sattva, rajas, tamas) tuple
        history: Deque of recent Guna states
    """

    def __init__(
        self,
        window_size: int = 20,
        sattva_confidence_weight: float = 0.7,
        rajas_variance_scale: float = 10.0,
        tamas_ngram_order: int = 2,
    ):
        self.window_size = window_size
        self.sattva_confidence_weight = sattva_confidence_weight
        self.rajas_variance_scale = rajas_variance_scale
        self.tamas_ngram_order = tamas_ngram_order

        # Tracking buffers
        self.token_probs: deque = deque(maxlen=window_size)
        self.token_ids: deque = deque(maxlen=window_size)
        self.entropy_values: deque = deque(maxlen=window_size)

        # Current state
        self.current_gunas: Tuple[float, float, float] = (0.33, 0.33, 0.34)
        self.history: deque = deque(maxlen=window_size)

    def update(
        self,
        token_id: int,
        token_prob: float,
        entropy: Optional[float] = None,
        top_probs: Optional[torch.Tensor] = None,
    ) -> Tuple[float, float, float]:
        """
        Update Guna state with new generated token.

        Args:
            token_id: Selected token ID
            token_prob: Probability of selected token
            entropy: Token distribution entropy (optional, for Sattva)
            top_probs: Top-k probabilities (optional, for Rajas variance)

        Returns:
            (sattva, rajas, tamas) normalized to sum to 1
        """
        self.token_probs.append(token_prob)
        self.token_ids.append(token_id)

        if entropy is not None:
            self.entropy_values.append(entropy)

        # Compute raw Gunas
        sattva_raw = self._compute_sattva(token_prob, entropy)
        rajas_raw = self._compute_rajas(top_probs)
        tamas_raw = self._compute_tamas()

        # Normalize to sum to 1
        total = sattva_raw + rajas_raw + tamas_raw
        if total > 0:
            s = sattva_raw / total
            r = rajas_raw / total
            t = tamas_raw / total
        else:
            s, r, t = 0.33, 0.33, 0.34

        self.current_gunas = (s, r, t)
        self.history.append(self.current_gunas)

        return self.current_gunas

    def _compute_sattva(
        self,
        token_prob: float,
        entropy: Optional[float] = None,
    ) -> float:
        """
        Compute Sattva (clarity/quality) from confidence signals.

        Sattva = confidence × (1 - normalized_entropy)

        High token probability + low entropy = clear, focused generation.

        Args:
            token_prob: Probability of selected token
            entropy: Normalized entropy (0-1), lower is better

        Returns:
            Raw Sattva value (0-1)
        """
        # Primary: token probability as confidence
        confidence = min(1.0, max(0.0, token_prob))

        # If entropy available, factor it in
        if entropy is not None and len(self.entropy_values) > 0:
            # Average recent entropy for stability
            avg_entropy = sum(self.entropy_values) / len(self.entropy_values)
            clarity = 1.0 - min(1.0, avg_entropy)

            # Weighted combination
            sattva = (
                self.sattva_confidence_weight * confidence +
                (1 - self.sattva_confidence_weight) * clarity
            )
        else:
            # Fallback: use probability directly
            # Higher prob = higher confidence = higher Sattva
            sattva = confidence

        return sattva

    def _compute_rajas(self, top_probs: Optional[torch.Tensor] = None) -> float:
        """
        Compute Rajas (action/activity) from probability variance.

        High variance in token probabilities = active exploration.
        Low variance = deterministic (may be stuck or very confident).

        Args:
            top_probs: Top-k probabilities for current token

        Returns:
            Raw Rajas value (0-1)
        """
        if len(self.token_probs) < 2:
            return 0.33  # Neutral until we have history

        probs = list(self.token_probs)
        mean_prob = sum(probs) / len(probs)

        # Variance of probabilities across tokens
        variance = sum((p - mean_prob) ** 2 for p in probs) / len(probs)

        # Scale to [0, 1] range
        # Typical variance range is 0-0.1, scale by rajas_variance_scale
        rajas = min(1.0, variance * self.rajas_variance_scale)

        # If top_probs available, factor in distribution spread
        if top_probs is not None and top_probs.numel() > 1:
            # Variance in top probabilities = distribution activity
            top_var = top_probs.var().item()
            rajas = (rajas + min(1.0, top_var * 10)) / 2

        return rajas

    def _compute_tamas(self) -> float:
        """
        Compute Tamas (inertia/stuckness) from repetition patterns.

        High repetition rate = model stuck in a loop.
        Low repetition = healthy exploration.

        Uses n-gram uniqueness as a proxy.

        Returns:
            Raw Tamas value (0-1)
        """
        if len(self.token_ids) < 3:
            return 0.33  # Neutral until enough history

        tokens = list(self.token_ids)

        # Unigram repetition
        unique_unigrams = len(set(tokens))
        unigram_ratio = unique_unigrams / len(tokens)

        # Bigram repetition (or specified n-gram order)
        if len(tokens) >= self.tamas_ngram_order:
            ngrams = [
                tuple(tokens[i:i + self.tamas_ngram_order])
                for i in range(len(tokens) - self.tamas_ngram_order + 1)
            ]
            unique_ngrams = len(set(ngrams))
            ngram_ratio = unique_ngrams / len(ngrams)
        else:
            ngram_ratio = 1.0

        # Tamas = 1 - uniqueness (more repetition = higher Tamas)
        tamas_unigram = 1.0 - unigram_ratio
        tamas_ngram = 1.0 - ngram_ratio

        # Weight n-gram higher (better at detecting loops)
        tamas = 0.3 * tamas_unigram + 0.7 * tamas_ngram

        return tamas

    def get_dynamic_alpha_multiplier(self, base_alpha: float = 0.1) -> float:
        """
        Compute dynamic resonance alpha multiplier based on Guna state.

        Mirrors training behavior (train_unified_llm.py:1536-1541):
        - High Sattva → increase alpha (trust karma more)
        - High Rajas → decrease alpha (focus on current)

        Args:
            base_alpha: Base resonance alpha

        Returns:
            Dynamic alpha value in range [0.05, 0.25]
        """
        s, r, t = self.current_gunas

        # Formula from training: alpha = base * (1.0 + s*1.5 - r*0.5)
        dynamic_alpha = base_alpha * (1.0 + (s * 1.5) - (r * 0.5))
        dynamic_alpha = max(0.05, min(0.25, dynamic_alpha))

        return dynamic_alpha

    def get_temperature_adjustment(self) -> float:
        """
        Suggest temperature adjustment based on Guna state.

        - High Tamas (repetition) → increase temperature
        - High Sattva (clarity) → can reduce temperature
        - High Rajas (activity) → maintain temperature

        Returns:
            Temperature multiplier (< 1 to reduce, > 1 to increase)
        """
        s, r, t = self.current_gunas

        if t > 0.5:
            # High Tamas: increase temperature to break repetition
            return 1.0 + (t - 0.5)  # Up to 1.5x
        elif s > 0.5:
            # High Sattva: can afford to reduce temperature
            return 1.0 - (s - 0.5) * 0.3  # Down to 0.85x
        else:
            return 1.0

    def is_repetition_detected(self, threshold: float = 0.6) -> bool:
        """
        Quick check if model is in a repetition loop.

        Args:
            threshold: Tamas threshold for repetition detection

        Returns:
            True if Tamas exceeds threshold
        """
        _, _, t = self.current_gunas
        return t > threshold

    def get_status(self) -> str:
        """Get formatted status string for logging."""
        s, r, t = self.current_gunas

        # Determine dominant Guna
        if s >= r and s >= t:
            dominant = "S"
            icon = "🔵"
        elif r >= s and r >= t:
            dominant = "R"
            icon = "🔴"
        else:
            dominant = "T"
            icon = "⚫"

        return f"Guna:{dominant}{icon}|s={s:.2f}|r={r:.2f}|t={t:.2f}"

    def get_detailed_state(self) -> Dict[str, Any]:
        """Get detailed Guna state for logging/monitoring."""
        s, r, t = self.current_gunas

        # Compute trends if enough history
        trends = {"sattva": 0.0, "rajas": 0.0, "tamas": 0.0}
        if len(self.history) >= 5:
            history = list(self.history)[-5:]
            trends["sattva"] = history[-1][0] - history[0][0]
            trends["rajas"] = history[-1][1] - history[0][1]
            trends["tamas"] = history[-1][2] - history[0][2]

        return {
            "sattva": s,
            "rajas": r,
            "tamas": t,
            "dominant": "sattva" if s >= r and s >= t else ("rajas" if r >= t else "tamas"),
            "trends": trends,
            "repetition_detected": self.is_repetition_detected(),
            "alpha_multiplier": self.get_dynamic_alpha_multiplier(),
            "temperature_adjustment": self.get_temperature_adjustment(),
        }

    def reset(self):
        """Reset all tracking state for new generation."""
        self.token_probs.clear()
        self.token_ids.clear()
        self.entropy_values.clear()
        self.history.clear()
        self.current_gunas = (0.33, 0.33, 0.34)
