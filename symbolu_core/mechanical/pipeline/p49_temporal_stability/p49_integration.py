"""
Phase 49: Temporal Stability Index Pipeline Integration

Integration functions for running P49 within the pipeline.
Provides pipeline-friendly entry points and context extraction.

Usage:
    from symbolu_core.mechanical.pipeline.p49_temporal_stability import (
        maybe_run_p49,
    )

    # In pipeline after P38, P40, P45, P46, P47:
    maybe_run_p49(ctx)

    # Access stability index:
    if ctx.p49_temporal_stability is not None:
        print(f"Index: {ctx.p49_temporal_stability.temporal_stability_index}")
        print(f"Band: {ctx.p49_temporal_stability.stability_band}")

INPUTS (Read-Only):
    Phase 49 MAY read:
        - ctx.p38_temporal_forecast (Phase38TemporalForecast)
        - ctx.p40_cross_horizon_alignment (CrossHorizonAlignment)
        - ctx.p45_multi_trajectory_stability (MultiTrajectoryStabilityField)
        - ctx.p46_trajectory_convergence (TrajectoryFieldConvergenceReport)
        - ctx.p47_unified_trajectory_scenario (UnifiedTrajectoryScenarioReport)

    Phase 49 MUST NOT read:
        - Regime (P6)
        - Discourse, semantics, lexical layers
        - Acoustic / vrtti / kosha phases
        - Policy or governance phases (>=50)
        - Renderer or persona layers

CRITICAL CONSTRAINTS:
    - Must NOT influence regime (P6)
    - Must NOT affect discourse or semantics
    - Must NOT trigger actions
    - Must NOT import observer acoustic phases
    - Must NOT import governance / eligibility code

INVARIANTS:
    INV-P49-1: Observer-only (no downstream influence)
    INV-P49-2: Deterministic (pure math, no state)
    INV-P49-3: No authority (cannot gate, block, or trigger)
    INV-P49-4: Absence-safe (missing inputs -> None)
    INV-P49-5: Temporal meaning only (index reflects time stability, not intent or emotion)
"""

from __future__ import annotations

from typing import Any, Optional

from .p49_schema import (
    P49_VERSION,
    TemporalStabilityIndex,
)
from .p49_index import run_p49_directly


# ============================================================================
# SIGNAL EXTRACTION
# ============================================================================


def _extract_p38_temporal_forecast(ctx: Any) -> Any:
    """
    Extract P38 Phase38TemporalForecast from context.

    Checks for:
        - ctx.p38_temporal_forecast

    INV-P49-1: We read this value but NEVER modify it.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        Phase38TemporalForecast if present, None otherwise
    """
    return getattr(ctx, "p38_temporal_forecast", None)


def _extract_p40_cross_horizon_alignment(ctx: Any) -> Any:
    """
    Extract P40 CrossHorizonAlignment from context.

    Checks for:
        - ctx.p40_cross_horizon_alignment

    INV-P49-1: We read this value but NEVER modify it.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        CrossHorizonAlignment if present, None otherwise
    """
    return getattr(ctx, "p40_cross_horizon_alignment", None)


def _extract_p45_multi_trajectory_stability(ctx: Any) -> Any:
    """
    Extract P45 MultiTrajectoryStabilityField from context.

    Checks for:
        - ctx.p45_multi_trajectory_stability

    INV-P49-1: We read this value but NEVER modify it.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        MultiTrajectoryStabilityField if present, None otherwise
    """
    return getattr(ctx, "p45_multi_trajectory_stability", None)


def _extract_p46_trajectory_convergence(ctx: Any) -> Any:
    """
    Extract P46 TrajectoryFieldConvergenceReport from context.

    Checks for:
        - ctx.p46_trajectory_convergence

    INV-P49-1: We read this value but NEVER modify it.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        TrajectoryFieldConvergenceReport if present, None otherwise
    """
    return getattr(ctx, "p46_trajectory_convergence", None)


def _extract_p47_unified_trajectory_scenario(ctx: Any) -> Any:
    """
    Extract P47 UnifiedTrajectoryScenarioReport from context.

    Checks for:
        - ctx.p47_unified_trajectory_scenario

    INV-P49-1: We read this value but NEVER modify it.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        UnifiedTrajectoryScenarioReport if present, None otherwise
    """
    return getattr(ctx, "p47_unified_trajectory_scenario", None)


# ============================================================================
# INTEGRATION FUNCTIONS
# ============================================================================


def maybe_run_p49(ctx: Any) -> Optional[TemporalStabilityIndex]:
    """
    Run P49 temporal stability index computation if prerequisites are met.

    This is the main integration entry point. It:
    1. Checks if P49 should run
    2. Extracts P38, P40, P45, P46, P47 outputs from context
    3. Runs the index computation
    4. Attaches the result to ctx.p49_temporal_stability

    P49 is designed to run after P38, P40, P45, P46, and P47.
    Returns None if any required input is unavailable (INV-P49-4).

    INV-P49-1: Observer-only - we only write to ctx.p49_temporal_stability.
    INV-P49-2: Deterministic - same inputs always produce same outputs.
    INV-P49-3: No authority - output cannot gate, block, or trigger.
    INV-P49-4: Absence-safe - missing input produces None.
    INV-P49-5: Temporal meaning only - combines temporal stability signals.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        The TemporalStabilityIndex if run, None if skipped
    """
    # Check if P49 is disabled on this context
    if is_p49_disabled(ctx):
        return None

    # Extract required inputs
    p38_forecast = _extract_p38_temporal_forecast(ctx)
    p40_alignment = _extract_p40_cross_horizon_alignment(ctx)
    p45_stability = _extract_p45_multi_trajectory_stability(ctx)
    p46_convergence = _extract_p46_trajectory_convergence(ctx)
    p47_synthesis = _extract_p47_unified_trajectory_scenario(ctx)

    # INV-P49-4: Absence-safe - return None if any input is missing
    if p38_forecast is None:
        return None
    if p40_alignment is None:
        return None
    if p45_stability is None:
        return None
    if p46_convergence is None:
        return None
    if p47_synthesis is None:
        return None

    # Run the index computation
    stability_index = run_p49_directly(
        p38_temporal_forecast=p38_forecast,
        p40_cross_horizon_alignment=p40_alignment,
        p45_multi_trajectory_stability=p45_stability,
        p46_trajectory_convergence=p46_convergence,
        p47_unified_trajectory_scenario=p47_synthesis,
    )

    if stability_index is None:
        return None

    # Attach to context (observer-only append)
    _attach_stability_index_to_context(ctx, stability_index)

    return stability_index


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def is_p49_disabled(ctx: Any) -> bool:
    """
    Check if P49 is disabled on this context.

    P49 can be disabled by setting ctx._p49_disabled = True.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        True if P49 is disabled, False otherwise
    """
    return getattr(ctx, "_p49_disabled", False)


def has_p49_stability_index(ctx: Any) -> bool:
    """
    Check if context has a P49 stability index attached.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        True if ctx.p49_temporal_stability is set and not None
    """
    return getattr(ctx, "p49_temporal_stability", None) is not None


def get_p49_stability_index(ctx: Any) -> Optional[TemporalStabilityIndex]:
    """
    Get the P49 stability index from context if present.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        The TemporalStabilityIndex if present, None otherwise
    """
    return getattr(ctx, "p49_temporal_stability", None)


def get_temporal_stability_index(ctx: Any) -> float:
    """
    Get the temporal stability index value from context.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        Temporal stability index value, or 0.0 if no report
    """
    report = get_p49_stability_index(ctx)
    if report is None:
        return 0.0
    return report.temporal_stability_index


def get_stability_band(ctx: Any) -> str:
    """
    Get the stability band from context.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        Stability band string, or "unstable" if no report
    """
    report = get_p49_stability_index(ctx)
    if report is None:
        return "unstable"
    return report.stability_band


def get_p49_version() -> str:
    """
    Get the current P49 schema version.

    Returns:
        Version string (e.g., "1.0.0")
    """
    return P49_VERSION


def _attach_stability_index_to_context(
    ctx: Any,
    stability_index: TemporalStabilityIndex,
) -> None:
    """
    Attach the P49 stability index to context.

    This is observer-only: we only append to ctx.p49_temporal_stability,
    we do NOT modify any other context fields or influence behavior.

    INV-P49-1: Only writes to ctx.p49_temporal_stability, nothing else.

    Args:
        ctx: PipelineContext
        stability_index: The P49 stability index to attach
    """
    # Attach to p49_temporal_stability attribute
    if hasattr(ctx, "p49_temporal_stability"):
        ctx.p49_temporal_stability = stability_index
    else:
        try:
            setattr(ctx, "p49_temporal_stability", stability_index)
        except AttributeError:
            # Context is frozen or doesn't allow attribute setting
            pass


# Public exports
__all__ = [
    # Integration
    "maybe_run_p49",
    "run_p49_directly",
    # Helpers
    "is_p49_disabled",
    "has_p49_stability_index",
    "get_p49_stability_index",
    "get_temporal_stability_index",
    "get_stability_band",
    "get_p49_version",
]
