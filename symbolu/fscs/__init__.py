"""
symbolu.fscs — Text-FSCS: Frequency-Stratified Coherence Softmax for transformer attention.

EXPERIMENTAL. Implementation-complete, not yet benchmark-validated.

This package is the first-pass implementation of the Text-FSCS specification
(see CONSOLIDATED TECHNICAL SPECIFICATION — Text-FSCS v5.0).

Scope of this first-pass implementation:
    - Three-signal coherence gating (output delta + residual delta; optional
      block-mass attention KL is stubbed but off by default)
    - Pre-softmax routing gate with per-band sharpness and thresholds
    - Boundary detector (heuristic v1: newline/brace/punctuation tokens)
    - Surprise-delta suppressor (stable-but-wrong protection)
    - Layer-level cap with importance tiebreaker
    - Stopgrad alignment loss for co-training regimes
    - Mistral-7B frozen-backbone integration via MistralFSCSWrapper

Scope explicitly deferred (and stated in docs/FSCS_IMPLEMENTATION_STATUS.md):
    - Per-head (vs per-token) gate granularity
    - Per-band coarse operators: Mid-band strided, Global-band EMA cache
      with forced refresh. This first-pass uses a single windowed coarse
      operator across all bands.
    - Cross-layer caution propagation (§8 of spec)
    - Plateau block sparsity (§11 of spec)
    - Trained classifier boundary detector v2
    - Field-integrated softmax (Phase 4 of the broader CG curriculum)

Author: Rakesh Mohan / Ugence Labs
Branch: claude/vc-pitch-document-LBYcN
"""

from symbolu.fscs.core import (
    FSCSConfig,
    FSCSCoherenceModule,
    FSCSRoutingGate,
    FSCSBoundaryDetector,
    FSCSSurpriseDeltaSuppressor,
    FSCSLayerCap,
    FSCSEMACache,
    FSCSCoarseAdapter,
    fscs_alignment_loss,
    fscs_band_contrast_loss,
)

try:
    from symbolu.fscs.mistral_gated_layer import FSCSGatedDecoderLayer
    _MISTRAL_AVAILABLE = True
except ImportError:
    # transformers not installed — core FSCS modules still usable
    _MISTRAL_AVAILABLE = False

__all__ = [
    "FSCSConfig",
    "FSCSCoherenceModule",
    "FSCSRoutingGate",
    "FSCSBoundaryDetector",
    "FSCSSurpriseDeltaSuppressor",
    "FSCSLayerCap",
    "FSCSCoarseAdapter",
    "fscs_alignment_loss",
]

if _MISTRAL_AVAILABLE:
    __all__.append("FSCSGatedDecoderLayer")
