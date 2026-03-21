#!/usr/bin/env python3
"""
Unified Coherence Controller — Appendix F Stage 4
===================================================

Merges three disconnected coherence systems into a single controller
that produces one authoritative coherence signal for generation control.

Aggregation formula::

    C_total = w_token · C_token + w_latent · C_latent + w_conv · C_conversation

Where:
    C_token        = mean B(w) from BlissTokenGate across K recent tokens
    C_latent       = sigmoid(coherence_head(bhava_vector)) from Stage 3
    C_conversation = quality_v3 from CoherenceEngine (or 0.7 default)

EMA smoothing prevents jitter::

    C_total_ema = ema_alpha · C_total + (1 - ema_alpha) · C_total_ema

The unified signal replaces the simple coherence scalar that Stage 1's
CoherenceAwareDecoder previously consumed.

Reference: docs/design/CONSCIOUS_GENERATION_DESIGN.md, Appendix F §F.6

Author: Sovereign-1 Training Initiative
Date: March 2026
Phase: Appendix F Stage 4 — Unified Coherence Controller
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List


@dataclass
class UnifiedCoherenceConfig:
    """Configuration for the unified coherence controller.

    Attributes:
        w_token: Weight for token-level coherence (Bliss gate mean).
        w_latent: Weight for latent coherence (Bhava vector).
        w_conv: Weight for conversation-level coherence (CoherenceEngine).
        ema_alpha: Smoothing factor for exponential moving average of C_total.
            Lower values = smoother (less responsive), higher = more responsive.
        history_window: Number of recent B(w) values to average for C_token.
    """
    w_token: float = 0.4
    w_latent: float = 0.3
    w_conv: float = 0.3
    ema_alpha: float = 0.1
    history_window: int = 20


class UnifiedCoherenceController:
    """Single authoritative coherence signal for generation control.

    Merges token-level (Bliss gate), latent (Bhava vector), and
    conversation-level (CoherenceEngine) coherence into one signal.

    Usage::

        controller = UnifiedCoherenceController()

        # Per-token update during generation
        result = controller.update(
            c_token=0.85,       # mean Bliss from recent tokens
            c_latent=0.72,      # from BhavaVectorCompressor coherence_head
            c_conv=0.68,        # from CoherenceEngine quality_v3
        )
        coherence = result["C_total"]  # EMA-smoothed unified signal

        # Feed to Stage 1
        policy = coherence_decoder.adjust_policy(
            coherence=coherence, base_temperature=0.7, base_top_p=0.9
        )

    Attributes:
        config: UnifiedCoherenceConfig with weights and smoothing params.
        c_total_ema: Current EMA-smoothed unified coherence value.
        bliss_history: Rolling window of recent B(w) values for C_token.
    """

    def __init__(self, config: UnifiedCoherenceConfig = None):
        self.config = config or UnifiedCoherenceConfig()
        self.c_total_ema = 0.7  # Initial optimistic value
        self.bliss_history: List[float] = []

    def record_bliss(self, bliss_value: float) -> None:
        """Record a per-token Bliss value B(w) into the rolling window.

        Args:
            bliss_value: Bliss coherence for the current token, in [0, 1].
        """
        self.bliss_history.append(bliss_value)
        if len(self.bliss_history) > self.config.history_window:
            self.bliss_history = self.bliss_history[-self.config.history_window:]

    @property
    def c_token(self) -> float:
        """Compute C_token as mean B(w) across recent tokens."""
        if not self.bliss_history:
            return 0.5  # Neutral default when no Bliss data
        return sum(self.bliss_history) / len(self.bliss_history)

    def update(
        self,
        c_token: Optional[float] = None,
        c_latent: Optional[float] = None,
        c_conv: Optional[float] = None,
    ) -> Dict[str, float]:
        """Compute unified coherence from available signals.

        Missing signals default to neutral values so the controller
        degrades gracefully when not all sources are available.

        Args:
            c_token: Token-level coherence (Bliss gate mean). If None,
                uses self.c_token from bliss_history, or 0.5 if empty.
            c_latent: Latent coherence from BhavaVectorCompressor
                coherence_head. Defaults to 0.5 if None.
            c_conv: Conversation-level coherence from CoherenceEngine
                quality_v3. Defaults to 0.7 if None.

        Returns:
            Dict with:
                - C_total: EMA-smoothed unified coherence signal.
                - C_token: Token-level component used.
                - C_latent: Latent component used.
                - C_conversation: Conversation component used.
                - C_raw: Pre-EMA unified coherence (for diagnostics).
        """
        ct = c_token if c_token is not None else self.c_token
        cl = c_latent if c_latent is not None else 0.5
        cc = c_conv if c_conv is not None else 0.7

        c_raw = (
            self.config.w_token * ct
            + self.config.w_latent * cl
            + self.config.w_conv * cc
        )

        # EMA smoothing to prevent jitter
        self.c_total_ema = (
            self.config.ema_alpha * c_raw
            + (1.0 - self.config.ema_alpha) * self.c_total_ema
        )

        return {
            "C_total": self.c_total_ema,
            "C_token": ct,
            "C_latent": cl,
            "C_conversation": cc,
            "C_raw": c_raw,
        }

    def reset(self) -> None:
        """Reset controller state for a new generation session."""
        self.c_total_ema = 0.7
        self.bliss_history.clear()
