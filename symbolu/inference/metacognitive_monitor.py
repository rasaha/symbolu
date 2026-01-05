"""
Inference Metacognition Module
==============================

Real-time generation quality monitoring with actionable recommendations.

This module implements the inference counterpart to the training-time
MetacognitiveTracker (train_unified_llm.py:666-825), providing:

1. Token-level entropy monitoring as confidence proxy
2. Coherence trend detection
3. Actionable recommendations (ABORT, BRAKE, RECOVER, etc.)
4. Dynamic generation parameter adjustment

The metacognitive system provides "Sovereign" agency over generation,
allowing the model to self-regulate quality in real-time.

Usage:
------
    from symbolu.inference import InferenceMetacognition

    monitor = InferenceMetacognition(alarm_threshold=0.3)

    for token in generation:
        status = monitor.update(token_logits, token_prob)

        if status['recommendation'] == 'ABORT':
            break  # Stop generation

        if status['recommendation'] == 'BRAKE':
            temperature *= 0.8  # Reduce creativity
"""

import math
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum
from collections import deque

import torch
import torch.nn.functional as F


class Recommendation(Enum):
    """Metacognitive recommendations for generation control."""
    ABORT = "ABORT"          # Critical failure - stop generation
    BRAKE = "BRAKE"          # Rapid degradation - protect model
    SLOW_DOWN = "SLOW_DOWN"  # Coherence alarm - reduce temperature
    RECOVER = "RECOVER"      # Stagnation - increase temperature/randomness
    ACCELERATE = "ACCELERATE"  # High quality - can push harder
    STABILIZE = "STABILIZE"  # Declining trend - maintain current
    CONTINUE = "CONTINUE"    # Default - no intervention needed


class InferenceMetacognition:
    """
    Real-time generation quality monitoring.

    Tracks coherence signals and provides actionable recommendations
    for generation control. Uses token entropy as a proxy for model
    confidence, enabling quality monitoring without hidden state access.

    This bridges gap 2.1 from INFERENCE_HYBRID_TRANSFORMER_GAPS.md,
    implementing the inference counterpart to MetacognitiveTracker.

    Args:
        coherence_window: Number of tokens to track for trend analysis
        alarm_threshold: Coherence threshold for alarm state (0-1)
        abort_consecutive: Consecutive low-coherence tokens before ABORT
        entropy_vocab_size: Vocabulary size for entropy normalization

    Attributes:
        coherence_history: Recent coherence (confidence) values
        entropy_history: Recent entropy values
        recommendation: Current recommendation
    """

    def __init__(
        self,
        coherence_window: int = 50,
        alarm_threshold: float = 0.3,
        abort_consecutive: int = 5,
        entropy_vocab_size: int = 50257,
    ):
        self.coherence_window = coherence_window
        self.alarm_threshold = alarm_threshold
        self.abort_consecutive = abort_consecutive
        self.max_entropy = math.log(entropy_vocab_size)

        # Tracking buffers (using deque for efficient window management)
        self.coherence_history: deque = deque(maxlen=coherence_window)
        self.entropy_history: deque = deque(maxlen=coherence_window)
        self.token_probs: deque = deque(maxlen=coherence_window)

        # Guna tracking (updated externally or computed from probs)
        self.guna_history: deque = deque(maxlen=coherence_window)
        self.current_gunas: Tuple[float, float, float] = (0.33, 0.33, 0.34)

        # Alarm states
        self.coherence_alarm = False
        self.consecutive_low = 0

        # Statistics
        self.total_tokens = 0

    def update(
        self,
        token_logits: torch.Tensor,
        token_prob: Optional[float] = None,
        hidden_state: Optional[torch.Tensor] = None,
    ) -> Dict[str, Any]:
        """
        Update metacognitive state with new generation step.

        Computes:
        - Entropy of token distribution (proxy for uncertainty)
        - Coherence proxy from confidence (1 - normalized_entropy)
        - Recommendation for generation control

        Args:
            token_logits: Logits for current token [V] or [B, V]
            token_prob: Probability of selected token (optional)
            hidden_state: Hidden state for coherence (optional, advanced)

        Returns:
            Dict with:
            - recommendation: Recommendation enum value
            - coherence: Current coherence proxy
            - entropy: Normalized entropy
            - alarm: Whether alarm state is active
            - adjustments: Suggested parameter adjustments
        """
        self.total_tokens += 1

        # Flatten if batched
        if token_logits.dim() > 1:
            token_logits = token_logits[0]

        # Compute token entropy
        probs = F.softmax(token_logits.float(), dim=-1)
        entropy = -(probs * torch.log(probs + 1e-10)).sum().item()

        # Normalize to [0, 1] range
        normalized_entropy = min(1.0, entropy / self.max_entropy)

        # Coherence proxy: higher confidence = higher coherence
        # Low entropy (confident) → high coherence
        coherence_proxy = 1.0 - normalized_entropy

        # Track selected token probability if provided
        if token_prob is not None:
            self.token_probs.append(token_prob)

        # Update histories
        self.coherence_history.append(coherence_proxy)
        self.entropy_history.append(normalized_entropy)

        # Check alarm conditions
        self._update_alarm_state(coherence_proxy)

        # Get recommendation
        recommendation = self._get_recommendation()

        # Compute parameter adjustments
        adjustments = self._get_generation_adjustments()

        return {
            "recommendation": recommendation.value,
            "coherence": coherence_proxy,
            "entropy": normalized_entropy,
            "alarm": self.coherence_alarm,
            "consecutive_low": self.consecutive_low,
            "adjustments": adjustments,
            "total_tokens": self.total_tokens,
        }

    def _update_alarm_state(self, coherence: float):
        """Update alarm state based on coherence."""
        # Track consecutive low-coherence tokens
        if coherence < self.alarm_threshold:
            self.consecutive_low += 1
        else:
            self.consecutive_low = 0

        # Check if recent average is below threshold
        if len(self.coherence_history) >= 5:
            recent_avg = sum(list(self.coherence_history)[-5:]) / 5
            self.coherence_alarm = recent_avg < self.alarm_threshold
        else:
            self.coherence_alarm = coherence < self.alarm_threshold

    def _get_recommendation(self) -> Recommendation:
        """
        Generate metacognitive recommendation based on current state.

        Recommendation Hierarchy (matching training MetacognitiveTracker):
        - ABORT: Sustained critical failure (consecutive low coherence)
        - BRAKE: Rapid degradation, protect the model
        - SLOW_DOWN: Coherence alarm, reduce temperature
        - RECOVER: High Tamas (stagnation), need perturbation
        - ACCELERATE: High Sattva + improving, push forward
        - STABILIZE: Declining trend, maintain course
        - CONTINUE: Default state
        """
        # Get current Guna state
        s, r, t = self.current_gunas

        # Priority 0: ABORT - sustained critical failure
        if self.consecutive_low >= self.abort_consecutive:
            return Recommendation.ABORT

        # Priority 1: BRAKE - rapid degradation
        if self.coherence_alarm and len(self.coherence_history) >= 3:
            history = list(self.coherence_history)
            recent_trend = history[-1] - history[-3]
            if recent_trend < -0.15:  # Rapid drop
                return Recommendation.BRAKE

        # Priority 2: SLOW_DOWN - coherence alarm (but not critical)
        if self.coherence_alarm:
            return Recommendation.SLOW_DOWN

        # Priority 3: RECOVER - Tamas stagnation
        if t > 0.5 and len(self.coherence_history) >= 10:
            # Check if coherence has been flat (stagnation)
            history = list(self.coherence_history)[-10:]
            mean = sum(history) / len(history)
            variance = sum((c - mean) ** 2 for c in history) / len(history)
            std = variance ** 0.5
            if std < 0.02:  # Very flat = stagnation
                return Recommendation.RECOVER

        # Priority 4: Check for positive/negative trends
        if len(self.coherence_history) >= 5:
            history = list(self.coherence_history)
            trend = history[-1] - history[-5]

            # High Sattva + improving = ACCELERATE
            if s > 0.4 and trend > 0.05:
                return Recommendation.ACCELERATE

            # Declining coherence = STABILIZE
            if trend < -0.05:
                return Recommendation.STABILIZE

        return Recommendation.CONTINUE

    def _get_generation_adjustments(self) -> Dict[str, float]:
        """
        Suggest generation parameter adjustments based on state.

        Returns adjustments to temperature, top_p, etc.
        """
        if len(self.coherence_history) < 3:
            return {}

        history = list(self.coherence_history)
        avg_coherence = sum(history[-10:]) / min(10, len(history))

        adjustments = {}

        if avg_coherence < 0.3:
            # Low coherence: reduce temperature for more deterministic outputs
            adjustments["temperature_multiplier"] = 0.7
            adjustments["top_p_adjustment"] = -0.1
        elif avg_coherence < 0.5:
            # Moderate coherence: slight reduction
            adjustments["temperature_multiplier"] = 0.9
            adjustments["top_p_adjustment"] = -0.05
        elif avg_coherence > 0.8:
            # High coherence: can afford more creativity
            adjustments["temperature_multiplier"] = 1.1
            adjustments["top_p_adjustment"] = 0.05

        return adjustments

    def update_gunas(self, sattva: float, rajas: float, tamas: float):
        """
        Update Guna state from external tracker (InferenceGunas).

        Args:
            sattva: Clarity/confidence (0-1)
            rajas: Activity/variance (0-1)
            tamas: Inertia/repetition (0-1)
        """
        # Normalize to sum to 1
        total = sattva + rajas + tamas
        if total > 0:
            self.current_gunas = (sattva / total, rajas / total, tamas / total)
        self.guna_history.append(self.current_gunas)

    def should_abort(self) -> bool:
        """Quick check if generation should be aborted."""
        return self.consecutive_low >= self.abort_consecutive

    def should_intervene(self) -> bool:
        """Check if any intervention is needed."""
        rec = self._get_recommendation()
        return rec not in (Recommendation.CONTINUE, Recommendation.ACCELERATE)

    def get_status(self) -> str:
        """Get formatted status string for logging."""
        if not self.coherence_history:
            return "Meta:--"

        rec = self._get_recommendation()
        icons = {
            Recommendation.ABORT: "🛑",
            Recommendation.BRAKE: "⛔",
            Recommendation.SLOW_DOWN: "🐢",
            Recommendation.RECOVER: "🔄",
            Recommendation.ACCELERATE: "🚀",
            Recommendation.STABILIZE: "⚓",
            Recommendation.CONTINUE: "➡️",
        }
        icon = icons.get(rec, "➡️")
        coh = list(self.coherence_history)[-1]

        return f"Meta:{rec.value[:4]}|c={coh:.2f}{icon}"

    def get_detailed_status(self) -> Dict[str, Any]:
        """Get detailed metacognitive status for logging."""
        s, r, t = self.current_gunas
        history = list(self.coherence_history)

        return {
            "recommendation": self._get_recommendation().value,
            "coherence_current": history[-1] if history else 0.0,
            "coherence_mean": sum(history) / len(history) if history else 0.0,
            "coherence_alarm": self.coherence_alarm,
            "consecutive_low": self.consecutive_low,
            "guna_sattva": s,
            "guna_rajas": r,
            "guna_tamas": t,
            "total_tokens": self.total_tokens,
        }

    def reset(self):
        """Reset all tracking state for new generation."""
        self.coherence_history.clear()
        self.entropy_history.clear()
        self.token_probs.clear()
        self.guna_history.clear()
        self.current_gunas = (0.33, 0.33, 0.34)
        self.coherence_alarm = False
        self.consecutive_low = 0
        self.total_tokens = 0
