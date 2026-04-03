"""
P39 - Multi-Horizon Temporal Forecasting

Phase 39 extends Phase 38's single-horizon temporal coherence forecasts
into parallel multi-horizon forecasting, producing short/medium/long
horizon projections without influencing any authoritative decision,
routing, or gating.

This phase is:
    - Read-only
    - Observer-only
    - Non-authoritative
    - Non-gating
    - Non-persona
    - Non-renderer

Usage:
    from symbolu_core.mechanical.pipeline.p39_multi_horizon import maybe_run_p39

    # In pipeline after P38:
    maybe_run_p39(ctx)

    # Access forecast:
    if ctx.p39_multi_horizon is not None:
        print(f"Short: {ctx.p39_multi_horizon.short_term_score}")
        print(f"Medium: {ctx.p39_multi_horizon.medium_term_score}")
        print(f"Long: {ctx.p39_multi_horizon.long_term_score}")
        print(f"Divergence: {ctx.p39_multi_horizon.horizon_divergence}")

CRITICAL CONSTRAINTS:
    - Deterministic: Same inputs -> same outputs
    - Read-only: Does not modify system behavior
    - Observer-only: Never used for gating or behavior modification

INVARIANTS:
    - INV-P39-1: Observer-only (no influence on any authoritative phase)
    - INV-P39-2: Deterministic (same inputs -> same outputs)
    - INV-P39-3: Horizon monotonicity (flag if long_term > short_term)
    - INV-P39-4: No horizon can exceed Phase 38 base forecast
    - INV-P39-5: Absence-safe (missing inputs degrade confidence, never inflate)
"""

from symbolu_core.mechanical.pipeline.p39_multi_horizon.p39_schema import (
    P39_VERSION,
    HorizonBand,
    ALPHA,
    BETA,
    GAMMA,
    BAND_STABLE_THRESHOLD,
    BAND_STRAINED_THRESHOLD,
    classify_band,
    MultiHorizonForecast,
    create_forecast,
)

from symbolu_core.mechanical.pipeline.p39_multi_horizon.p39_resolver import (
    clamp,
    compute_short_term,
    compute_medium_term,
    compute_long_term,
    compute_horizon_divergence,
    check_monotonicity_violation,
    resolve_multi_horizon,
)

from symbolu_core.mechanical.pipeline.p39_multi_horizon.p39_integration import (
    maybe_run_p39,
    run_p39_directly,
    is_p39_disabled,
    has_p39_forecast,
    get_p39_forecast,
    get_short_term_score,
    get_medium_term_score,
    get_long_term_score,
    get_horizon_divergence,
    is_any_horizon_volatile,
    are_all_horizons_stable,
    get_p39_version,
)


__all__ = [
    # Version
    "P39_VERSION",
    # Type Aliases
    "HorizonBand",
    # Constants
    "ALPHA",
    "BETA",
    "GAMMA",
    "BAND_STABLE_THRESHOLD",
    "BAND_STRAINED_THRESHOLD",
    # Schema Helpers
    "classify_band",
    # Dataclasses
    "MultiHorizonForecast",
    # Factory
    "create_forecast",
    # Resolver Functions
    "clamp",
    "compute_short_term",
    "compute_medium_term",
    "compute_long_term",
    "compute_horizon_divergence",
    "check_monotonicity_violation",
    "resolve_multi_horizon",
    # Integration
    "maybe_run_p39",
    "run_p39_directly",
    # Integration Helpers
    "is_p39_disabled",
    "has_p39_forecast",
    "get_p39_forecast",
    "get_short_term_score",
    "get_medium_term_score",
    "get_long_term_score",
    "get_horizon_divergence",
    "is_any_horizon_volatile",
    "are_all_horizons_stable",
    "get_p39_version",
]
