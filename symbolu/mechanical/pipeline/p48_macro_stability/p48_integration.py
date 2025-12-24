"""
Phase 48: Macro-Stability Regime Analyzer Pipeline Integration

Integration functions for running P48 within the pipeline.
Provides pipeline-friendly entry points and context extraction.

Usage:
    from symbolu.mechanical.pipeline.p48_macro_stability import (
        maybe_run_p48,
    )

    # In pipeline after P45, P46, P47:
    maybe_run_p48(ctx)

    # Access regime report:
    if ctx.p48_macro_stability is not None:
        print(f"Regime: {ctx.p48_macro_stability.macro_regime}")
        print(f"Confidence: {ctx.p48_macro_stability.confidence}")

INPUTS (Read-Only):
    Phase 48 MAY read:
        - ctx.p45_multi_trajectory_stability (MultiTrajectoryStabilityField)
        - ctx.p46_trajectory_convergence (TrajectoryFieldConvergenceReport)
        - ctx.p47_unified_trajectory_scenario (UnifiedTrajectoryScenarioReport)

    Phase 48 MUST NOT read:
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
    INV-P48-1: Classification-only (no numeric synthesis beyond confidence)
    INV-P48-2: No future selection (no path choice, no ranking)
    INV-P48-3: Deterministic (pure rule + arithmetic)
    INV-P48-4: Observer-only (cannot influence authority layers)
    INV-P48-5: Absence-safe (missing input -> None)
"""

from __future__ import annotations

from typing import Any, Optional

from .p48_schema import (
    P48_VERSION,
    MacroStabilityRegimeReport,
)
from .p48_regime_analyzer import run_p48_directly


# ============================================================================
# SIGNAL EXTRACTION
# ============================================================================


def _extract_p45_stability_field(ctx: Any) -> Any:
    """
    Extract P45 MultiTrajectoryStabilityField from context.

    Checks for:
        - ctx.p45_multi_trajectory_stability

    INV-P48-4: We read this value but NEVER modify it.

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

    INV-P48-4: We read this value but NEVER modify it.

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

    INV-P48-4: We read this value but NEVER modify it.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        UnifiedTrajectoryScenarioReport if present, None otherwise
    """
    return getattr(ctx, "p47_unified_trajectory_scenario", None)


# ============================================================================
# INTEGRATION FUNCTIONS
# ============================================================================


def maybe_run_p48(ctx: Any) -> Optional[MacroStabilityRegimeReport]:
    """
    Run P48 macro-stability regime analyzer if prerequisites are met.

    This is the main integration entry point. It:
    1. Checks if P48 should run
    2. Extracts P45, P46, P47 outputs from context
    3. Runs the regime classification
    4. Attaches the result to ctx.p48_macro_stability

    P48 is designed to run after P45, P46, and P47.
    Returns None if any required input is unavailable (INV-P48-5).

    INV-P48-1: Classification-only - regime categorization, not synthesis.
    INV-P48-2: No future selection - no ranking or path choice.
    INV-P48-3: Deterministic - same inputs always produce same outputs.
    INV-P48-4: Observer-only - we only write to ctx.p48_macro_stability.
    INV-P48-5: Absence-safe - missing input produces None.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        The MacroStabilityRegimeReport if run, None if skipped
    """
    # Check if P48 is disabled on this context
    if is_p48_disabled(ctx):
        return None

    # Extract required inputs
    p45_stability_field = _extract_p45_stability_field(ctx)
    p46_convergence = _extract_p46_trajectory_convergence(ctx)
    p47_synthesis = _extract_p47_unified_trajectory_scenario(ctx)

    # INV-P48-5: Absence-safe - return None if any input is missing
    if p45_stability_field is None:
        return None
    if p46_convergence is None:
        return None
    if p47_synthesis is None:
        return None

    # Run the regime classification
    regime_report = run_p48_directly(
        p45_multi_trajectory_stability=p45_stability_field,
        p46_trajectory_convergence=p46_convergence,
        p47_unified_trajectory_scenario=p47_synthesis,
    )

    if regime_report is None:
        return None

    # Attach to context (observer-only append)
    _attach_regime_report_to_context(ctx, regime_report)

    return regime_report


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def is_p48_disabled(ctx: Any) -> bool:
    """
    Check if P48 is disabled on this context.

    P48 can be disabled by setting ctx._p48_disabled = True.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        True if P48 is disabled, False otherwise
    """
    return getattr(ctx, "_p48_disabled", False)


def has_p48_regime_report(ctx: Any) -> bool:
    """
    Check if context has a P48 regime report attached.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        True if ctx.p48_macro_stability is set and not None
    """
    return getattr(ctx, "p48_macro_stability", None) is not None


def get_p48_regime_report(ctx: Any) -> Optional[MacroStabilityRegimeReport]:
    """
    Get the P48 regime report from context if present.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        The MacroStabilityRegimeReport if present, None otherwise
    """
    return getattr(ctx, "p48_macro_stability", None)


def get_macro_regime(ctx: Any) -> str:
    """
    Get the macro regime from context.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        Macro regime string, or "indeterminate" if no report
    """
    report = get_p48_regime_report(ctx)
    if report is None:
        return "indeterminate"
    return report.macro_regime


def get_regime_confidence(ctx: Any) -> float:
    """
    Get the regime confidence from context.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        Confidence score in [0.0, 1.0], or 0.0 if no report
    """
    report = get_p48_regime_report(ctx)
    if report is None:
        return 0.0
    return report.confidence


def get_p48_version() -> str:
    """
    Get the current P48 schema version.

    Returns:
        Version string (e.g., "1.0.0")
    """
    return P48_VERSION


def _attach_regime_report_to_context(
    ctx: Any,
    regime_report: MacroStabilityRegimeReport,
) -> None:
    """
    Attach the P48 regime report to context.

    This is observer-only: we only append to ctx.p48_macro_stability,
    we do NOT modify any other context fields or influence behavior.

    INV-P48-4: Only writes to ctx.p48_macro_stability, nothing else.

    Args:
        ctx: PipelineContext
        regime_report: The P48 regime report to attach
    """
    # Attach to p48_macro_stability attribute
    if hasattr(ctx, "p48_macro_stability"):
        ctx.p48_macro_stability = regime_report
    else:
        try:
            setattr(ctx, "p48_macro_stability", regime_report)
        except AttributeError:
            # Context is frozen or doesn't allow attribute setting
            pass


# Public exports
__all__ = [
    # Integration
    "maybe_run_p48",
    "run_p48_directly",
    # Helpers
    "is_p48_disabled",
    "has_p48_regime_report",
    "get_p48_regime_report",
    "get_macro_regime",
    "get_regime_confidence",
    "get_p48_version",
]
