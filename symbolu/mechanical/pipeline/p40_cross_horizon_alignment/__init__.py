"""
P40 - Cross-Horizon Resonance Alignment Engine

Phase 40 detects alignment vs divergence across time horizons from
Phase 39's multi-horizon forecasts. It does NOT decide which horizon
is "correct," adjust forecasts, or influence any authoritative phase.

This phase is:
    - Read-only
    - Observer-only
    - Non-authoritative
    - Non-gating
    - Non-persona
    - Non-renderer

PURPOSE (Plain English):
    Phase 40 answers a single question:
    "Are the horizons telling a consistent story, or are they pulling apart?"

    This phase is purely observational.

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

CRITICAL CONSTRAINTS:
    - Deterministic: Same inputs -> same outputs
    - Read-only: Does not modify system behavior
    - Observer-only: Never used for gating or behavior modification

INVARIANTS:
    - INV-P40-1: Observer-only (no influence on any authoritative phase)
    - INV-P40-2: Deterministic (same inputs -> same outputs)
    - INV-P40-3: No forecast mutation (Phase 39 values are never changed)
    - INV-P40-4: Alignment monotonicity (greater divergence => lower alignment_score)
    - INV-P40-5: Absence-safe (missing optional inputs degrade or remain neutral, never improve)
"""

from symbolu.mechanical.pipeline.p40_cross_horizon_alignment.p40_schema import (
    P40_VERSION,
    AlignmentBand,
    DominantHorizon,
    BAND_ALIGNED_THRESHOLD,
    BAND_STRAINED_THRESHOLD,
    DOMINANT_HORIZON_THRESHOLD,
    classify_alignment_band,
    CrossHorizonAlignment,
    create_alignment,
)

from symbolu.mechanical.pipeline.p40_cross_horizon_alignment.p40_resolver import (
    clamp,
    compute_divergence_index,
    compute_alignment_score,
    determine_dominant_horizon,
    resolve_cross_horizon_alignment,
)

from symbolu.mechanical.pipeline.p40_cross_horizon_alignment.p40_integration import (
    maybe_run_p40,
    run_p40_directly,
    is_p40_disabled,
    has_p40_alignment,
    get_p40_alignment,
    get_alignment_score,
    get_alignment_band,
    get_divergence_index,
    get_dominant_horizon,
    is_aligned,
    is_fragmented,
    get_p40_version,
)


__all__ = [
    # Version
    "P40_VERSION",
    # Type Aliases
    "AlignmentBand",
    "DominantHorizon",
    # Constants
    "BAND_ALIGNED_THRESHOLD",
    "BAND_STRAINED_THRESHOLD",
    "DOMINANT_HORIZON_THRESHOLD",
    # Schema Helpers
    "classify_alignment_band",
    # Dataclasses
    "CrossHorizonAlignment",
    # Factory
    "create_alignment",
    # Resolver Functions
    "clamp",
    "compute_divergence_index",
    "compute_alignment_score",
    "determine_dominant_horizon",
    "resolve_cross_horizon_alignment",
    # Integration
    "maybe_run_p40",
    "run_p40_directly",
    # Integration Helpers
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
