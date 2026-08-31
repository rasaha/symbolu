#!/usr/bin/env python3
"""
Unified Coherence Controller — Appendix F Stage 4 + Stage 7A/7G
=================================================================

Merges coherence systems into a single controller that produces one
authoritative coherence signal for generation control.

Stage 4 (baseline) three-term formula::

    C_total = w_token · C_token + w_latent · C_latent + w_conv · C_conversation

Stage 7G extends with C_agreement (token-latent convergence)::

    C_agreement = 1 - |C_token - C_latent|

Stage 7A extends with S1/S2/S3 semantic coherence signals::

    S1 = per-layer coherence, S2 = global coherence, S3 = cross-layer coupling

Full formula (Stages 4 + 7A + 7G)::

    C_total = w_token · C_token + w_latent · C_latent
            + w_agreement · C_agreement + w_conv · C_conversation
            + w_s1 · S1 + w_s2 · S2 + w_s3 · S3

EMA smoothing prevents jitter::

    C_total_ema = ema_alpha · C_total + (1 - ema_alpha) · C_total_ema

Reference: Project_documentation/repository/docs/design/CONSCIOUS_GENERATION_DESIGN.md, Appendix F §F.6, §F.10.6.1, §F.10.6.7

Author: Sovereign-1 Training Initiative
Date: March 2026
Phase: Appendix F Stage 4 + Stage 7A/7G
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List


@dataclass
class UnifiedCoherenceConfig:
    """Configuration for the unified coherence controller.

    Stage 4 weights (w_token, w_latent, w_conv) sum to 1.0 when
    Stage 7 extensions are disabled (w_agreement=0, w_s1/s2/s3=0).

    Stage 7G rebalanced defaults (when w_agreement > 0):
        w_token=0.30, w_latent=0.25, w_agreement=0.20, w_conv=0.25

    Stage 7A S-score weights initialized to 0.0 for bounded introduction.
    Max bound of 0.15 each, ramped during training.

    Attributes:
        w_token: Weight for token-level coherence (Bliss gate mean).
        w_latent: Weight for latent coherence (Bhava vector).
        w_conv: Weight for conversation-level coherence (CoherenceEngine).
        w_agreement: Weight for token-latent convergence (Stage 7G).
        w_s1: Weight for per-layer semantic coherence S1 (Stage 7A).
        w_s2: Weight for global semantic coherence S2 (Stage 7A).
        w_s3: Weight for cross-layer coupling S3 (Stage 7A).
        s_weight_max: Maximum bound for S1/S2/S3 weights (Stage 7A).
        ema_alpha: Smoothing factor for EMA of C_total.
        history_window: Number of recent B(w) values to average for C_token.
        enable_agreement: Enable C_agreement (Stage 7G). When False,
            behaves like Stage 4 baseline.
        enable_semantic: Enable S1/S2/S3 integration (Stage 7A). When False,
            semantic signals are ignored.
    """
    # Stage 4 baseline weights
    w_token: float = 0.4
    w_latent: float = 0.3
    w_conv: float = 0.3

    # Stage 7G: C_agreement weight (init 0 for bounded intro)
    w_agreement: float = 0.0

    # Stage 7A: Semantic coherence weights (init 0 for bounded intro)
    w_s1: float = 0.0
    w_s2: float = 0.0
    w_s3: float = 0.0
    s_weight_max: float = 0.15

    # Smoothing
    ema_alpha: float = 0.1
    history_window: int = 20

    # Kill switches
    enable_agreement: bool = True
    enable_semantic: bool = True


class UnifiedCoherenceController:
    """Single authoritative coherence signal for generation control.

    Merges token-level (Bliss gate), latent (Bhava vector),
    conversation-level (CoherenceEngine), token-latent agreement (Stage 7G),
    and semantic coherence S1/S2/S3 (Stage 7A) into one signal.

    Usage::

        controller = UnifiedCoherenceController()

        # Per-token update during generation
        result = controller.update(
            c_token=0.85,       # mean Bliss from recent tokens
            c_latent=0.72,      # from BhavaVectorCompressor coherence_head
            c_conv=0.68,        # from CoherenceEngine quality_v3
            s1=0.75,            # per-layer coherence (Stage 7A)
            s2=0.80,            # global coherence (Stage 7A)
            s3=0.65,            # cross-layer coupling (Stage 7A)
        )
        coherence = result["C_total"]  # EMA-smoothed unified signal

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
        s1: Optional[float] = None,
        s2: Optional[float] = None,
        s3: Optional[float] = None,
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
            s1: Per-layer semantic coherence (Stage 7A). Defaults to 0.5.
            s2: Global semantic coherence (Stage 7A). Defaults to 0.5.
            s3: Cross-layer coupling (Stage 7A). Defaults to 0.5.

        Returns:
            Dict with:
                - C_total: EMA-smoothed unified coherence signal.
                - C_token: Token-level component used.
                - C_latent: Latent component used.
                - C_conversation: Conversation component used.
                - C_agreement: Token-latent convergence (Stage 7G).
                - S1, S2, S3: Semantic coherence components (Stage 7A).
                - C_raw: Pre-EMA unified coherence (for diagnostics).
        """
        ct = c_token if c_token is not None else self.c_token
        cl = c_latent if c_latent is not None else 0.5
        cc = c_conv if c_conv is not None else 0.7

        # Stage 7G: C_agreement = 1 - |C_token - C_latent|
        c_agreement = 1.0 - abs(ct - cl)

        # Stage 7A: Semantic coherence signals
        s1_val = s1 if s1 is not None else 0.5
        s2_val = s2 if s2 is not None else 0.5
        s3_val = s3 if s3 is not None else 0.5

        # Clamp S-weights to max bound
        cfg = self.config
        w_s1 = min(cfg.w_s1, cfg.s_weight_max) if cfg.enable_semantic else 0.0
        w_s2 = min(cfg.w_s2, cfg.s_weight_max) if cfg.enable_semantic else 0.0
        w_s3 = min(cfg.w_s3, cfg.s_weight_max) if cfg.enable_semantic else 0.0
        w_ag = cfg.w_agreement if cfg.enable_agreement else 0.0

        c_raw = (
            cfg.w_token * ct
            + cfg.w_latent * cl
            + w_ag * c_agreement
            + cfg.w_conv * cc
            + w_s1 * s1_val
            + w_s2 * s2_val
            + w_s3 * s3_val
        )

        # EMA smoothing to prevent jitter
        self.c_total_ema = (
            cfg.ema_alpha * c_raw
            + (1.0 - cfg.ema_alpha) * self.c_total_ema
        )

        return {
            "C_total": self.c_total_ema,
            "C_token": ct,
            "C_latent": cl,
            "C_conversation": cc,
            "C_agreement": c_agreement,
            "S1": s1_val,
            "S2": s2_val,
            "S3": s3_val,
            "C_raw": c_raw,
        }

    def reset(self) -> None:
        """Reset controller state for a new generation session."""
        self.c_total_ema = 0.7
        self.bliss_history.clear()
