"""
P40 - Cross-Horizon Resonance Alignment Pipeline Integration

Integration functions for running P40 within the pipeline.
Provides pipeline-friendly entry points and context extraction.

Usage:
    from symbolu.mechanical.pipeline.p40_cross_horizon_alignment import maybe_run_p40

    # In pipeline after P39:
    maybe_run_p40(ctx)

    # Access alignment:
    if ctx.p40_cross_horizon_alignment is not None:
        print(f"Alignment: {ctx.p40_cross_horizon_alignment.alignment_score}")
        print(f"Band: {ctx.p40_cross_horizon_alignment.alignment_band}")
        print(f"Divergence: {ctx.p40_cross_horizon_alignment.divergence_index}")
        print(f"Dominant: {ctx.p40_cross_horizon_alignment.dominant_horizon}")

INPUTS (Read-Only):
    Phase 40 MAY read:
        - Phase 39 MultiHorizonForecast (required)
        - Phase 19 Drift Fusion report (optional)
        - Phase 18 Temporal Entropy Differential (optional)

    Phase 40 MUST NOT read:
        - User text
        - Semantics
        - Lexical content
        - Regime or discourse envelopes
        - Acoustic / prosodic data
        - Any Phase >= 50 module

CRITICAL CONSTRAINTS:
    - Must NOT change regime, discourse, semantics, or lexical selection
    - Must NOT influence DHA, Persona Engine, Renderer
    - Must NOT influence insight gating (P32)
    - Must NOT infer intent or emotion
    - Must NOT gate actions or trigger side effects

INVARIANTS:
    - INV-P40-1: Observer-only (no influence on any authoritative phase)
    - INV-P40-2: Deterministic (same inputs -> same outputs)
    - INV-P40-3: No forecast mutation (Phase 39 values are never changed)
    - INV-P40-4: Alignment monotonicity (greater divergence => lower alignment_score)
    - INV-P40-5: Absence-safe (missing optional inputs degrade or remain neutral, never improve)
"""

from __future__ import annotations

from typing import Any, Optional

from symbolu.mechanical.pipeline.p40_cross_horizon_alignment.p40_schema import (
    CrossHorizonAlignment,
    P40_VERSION,
)
from symbolu.mechanical.pipeline.p40_cross_horizon_alignment.p40_resolver import (
    resolve_cross_horizon_alignment,
)


# ============================================================================
# SIGNAL EXTRACTION
# ============================================================================


def _extract_p39_horizons(ctx: Any) -> tuple[
    Optional[float],
    Optional[float],
    Optional[float],
]:
    """
    Extract Phase 39 horizon scores from context.

    Reads from:
    - ctx.p39_multi_horizon.short_term_score
    - ctx.p39_multi_horizon.medium_term_score
    - ctx.p39_multi_horizon.long_term_score

    INV-P40-3: We read these values but NEVER modify them.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        Tuple of (short_term, medium_term, long_term) scores, or (None, None, None)
        if P39 forecast is unavailable
    """
    if hasattr(ctx, "p39_multi_horizon") and ctx.p39_multi_horizon is not None:
        p39 = ctx.p39_multi_horizon
        short = getattr(p39, "short_term_score", None)
        medium = getattr(p39, "medium_term_score", None)
        long = getattr(p39, "long_term_score", None)

        if short is not None and medium is not None and long is not None:
            return (float(short), float(medium), float(long))

    return (None, None, None)


def _extract_drift_fusion_index(ctx: Any) -> Optional[float]:
    """
    Extract P19 drift fusion index from context (optional).

    Reads from:
    - ctx.p19.drift_fusion_index (primary)

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        Drift fusion index in [0.0, 1.0], or None if unavailable
    """
    if hasattr(ctx, "p19") and ctx.p19 is not None:
        dfi = getattr(ctx.p19, "drift_fusion_index", None)
        if dfi is not None:
            return float(dfi)

    return None


def _extract_temporal_entropy_diff(ctx: Any) -> Optional[float]:
    """
    Extract P18 temporal entropy differential from context (optional).

    Reads from:
    - ctx.p18.delta_entropy (primary)

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        Temporal entropy diff in [-1.0, 1.0], or None if unavailable
    """
    if hasattr(ctx, "p18") and ctx.p18 is not None:
        delta = getattr(ctx.p18, "delta_entropy", None)
        if delta is not None:
            return float(delta)

    return None


# ============================================================================
# INTEGRATION FUNCTIONS
# ============================================================================


def maybe_run_p40(ctx: Any) -> Optional[CrossHorizonAlignment]:
    """
    Run P40 cross-horizon alignment if prerequisites are met.

    This is the main integration entry point. It:
    1. Checks if P40 should run
    2. Extracts input signals from context (P39 required, P18/P19 optional)
    3. Runs the alignment computation
    4. Attaches the report to ctx.p40_cross_horizon_alignment

    P40 is designed to run after P39 (multi-horizon forecast).
    It requires all three P39 horizon scores to be present.

    INV-P40-1: Observer-only - we only write to ctx.p40_cross_horizon_alignment.
    INV-P40-3: P39 values are read but never modified.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        The CrossHorizonAlignment if run, None if skipped
    """
    # Check if P40 is disabled on this context
    if is_p40_disabled(ctx):
        return None

    # Extract P39 horizon scores (required)
    short_term, medium_term, long_term = _extract_p39_horizons(ctx)

    # All three P39 scores are required - skip if any unavailable
    if short_term is None or medium_term is None or long_term is None:
        return None

    # Extract optional inputs for observability (P18, P19)
    drift_fusion_index = _extract_drift_fusion_index(ctx)
    temporal_entropy_diff = _extract_temporal_entropy_diff(ctx)

    # Run the resolver
    alignment = resolve_cross_horizon_alignment(
        short_term_score=short_term,
        medium_term_score=medium_term,
        long_term_score=long_term,
        drift_fusion_index=drift_fusion_index,
        temporal_entropy_diff=temporal_entropy_diff,
    )

    if alignment is None:
        return None

    # Attach to context (observer-only append)
    _attach_alignment_to_context(ctx, alignment)

    return alignment


def run_p40_directly(
    short_term_score: Optional[float] = None,
    medium_term_score: Optional[float] = None,
    long_term_score: Optional[float] = None,
    drift_fusion_index: Optional[float] = None,
    temporal_entropy_diff: Optional[float] = None,
) -> Optional[CrossHorizonAlignment]:
    """
    Run P40 directly with explicit inputs (for testing).

    This bypasses context extraction and allows direct testing
    with mock values.

    Args:
        short_term_score: P39 short-term score [0.0, 1.0]
        medium_term_score: P39 medium-term score [0.0, 1.0]
        long_term_score: P39 long-term score [0.0, 1.0]
        drift_fusion_index: P19 drift fusion index [0.0, 1.0]
        temporal_entropy_diff: P18 temporal entropy diff [-1.0, 1.0]

    Returns:
        CrossHorizonAlignment if all required inputs provided, None otherwise
    """
    return resolve_cross_horizon_alignment(
        short_term_score=short_term_score,
        medium_term_score=medium_term_score,
        long_term_score=long_term_score,
        drift_fusion_index=drift_fusion_index,
        temporal_entropy_diff=temporal_entropy_diff,
    )


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def is_p40_disabled(ctx: Any) -> bool:
    """
    Check if P40 is disabled on this context.

    P40 can be disabled by setting ctx._p40_disabled = True.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        True if P40 is disabled, False otherwise
    """
    return getattr(ctx, "_p40_disabled", False)


def has_p40_alignment(ctx: Any) -> bool:
    """
    Check if context has a P40 alignment attached.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        True if ctx.p40_cross_horizon_alignment is set and not None
    """
    return getattr(ctx, "p40_cross_horizon_alignment", None) is not None


def get_p40_alignment(ctx: Any) -> Optional[CrossHorizonAlignment]:
    """
    Get the P40 alignment from context if present.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        The CrossHorizonAlignment if present, None otherwise
    """
    return getattr(ctx, "p40_cross_horizon_alignment", None)


def get_alignment_score(ctx: Any) -> float:
    """
    Get the alignment score from context.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        Alignment score in [0.0, 1.0], or 0.5 if no alignment
    """
    alignment = get_p40_alignment(ctx)
    if alignment is None:
        return 0.5
    return alignment.alignment_score


def get_alignment_band(ctx: Any) -> str:
    """
    Get the alignment band from context.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        Alignment band ("aligned", "strained", "fragmented"), or "strained" if no alignment
    """
    alignment = get_p40_alignment(ctx)
    if alignment is None:
        return "strained"
    return alignment.alignment_band


def get_divergence_index(ctx: Any) -> float:
    """
    Get the divergence index from context.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        Divergence index in [0.0, 1.0], or 0.0 if no alignment
    """
    alignment = get_p40_alignment(ctx)
    if alignment is None:
        return 0.0
    return alignment.divergence_index


def get_dominant_horizon(ctx: Any) -> str:
    """
    Get the dominant horizon from context.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        Dominant horizon ("short", "medium", "long", "none"), or "none" if no alignment
    """
    alignment = get_p40_alignment(ctx)
    if alignment is None:
        return "none"
    return alignment.dominant_horizon


def is_aligned(ctx: Any) -> bool:
    """
    Check if horizons are aligned.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        True if alignment band is "aligned", False otherwise
    """
    alignment = get_p40_alignment(ctx)
    if alignment is None:
        return False
    return alignment.is_aligned()


def is_fragmented(ctx: Any) -> bool:
    """
    Check if horizons are fragmented.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        True if alignment band is "fragmented", False otherwise
    """
    alignment = get_p40_alignment(ctx)
    if alignment is None:
        return False
    return alignment.is_fragmented()


def get_p40_version() -> str:
    """
    Get the current P40 schema version.

    Returns:
        Version string (e.g., "1.0.0")
    """
    return P40_VERSION


def _attach_alignment_to_context(
    ctx: Any,
    alignment: CrossHorizonAlignment,
) -> None:
    """
    Attach the P40 alignment to context.

    This is observer-only: we only append to ctx.p40_cross_horizon_alignment,
    we do NOT modify any other context fields or influence behavior.

    INV-P40-1: Only writes to ctx.p40_cross_horizon_alignment, nothing else.

    Args:
        ctx: PipelineContext
        alignment: The P40 alignment to attach
    """
    # Attach to p40_cross_horizon_alignment attribute
    if hasattr(ctx, "p40_cross_horizon_alignment"):
        ctx.p40_cross_horizon_alignment = alignment
    else:
        try:
            setattr(ctx, "p40_cross_horizon_alignment", alignment)
        except AttributeError:
            # Context is frozen or doesn't allow attribute setting
            pass


# Public exports
__all__ = [
    # Integration
    "maybe_run_p40",
    "run_p40_directly",
    # Helpers
    "is_p40_disabled",
    "has_p40_alignment",
    "get_p40_alignment",
    "get_alignment_score",
    "get_alignment_band",
    "get_divergence_index",
    "get_dominant_horizon",
    "is_aligned",
    "is_fragmented",
    "get_p40_version",
]
