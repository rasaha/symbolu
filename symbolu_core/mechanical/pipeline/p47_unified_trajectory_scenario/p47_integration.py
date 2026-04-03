"""
Phase 47: Unified Trajectory-Scenario Synthesis Pipeline Integration

Integration functions for running P47 within the pipeline.
Provides pipeline-friendly entry points and context extraction.

Usage:
    from symbolu_core.mechanical.pipeline.p47_unified_trajectory_scenario import (
        maybe_run_p47,
    )

    # In pipeline after P42, P45, P46:
    maybe_run_p47(ctx)

    # Access synthesis report:
    if ctx.p47_unified_trajectory_scenario is not None:
        print(f"Alignment: {ctx.p47_unified_trajectory_scenario.alignment_score}")
        print(f"Band: {ctx.p47_unified_trajectory_scenario.alignment_band}")

INPUTS (Read-Only):
    Phase 47 MAY read:
        - ctx.p42_scenario_fusion_field (ScenarioFusionField)
        - ctx.p45_multi_trajectory_stability (MultiTrajectoryStabilityField)
        - ctx.p46_trajectory_convergence (TrajectoryFieldConvergenceReport)

    Phase 47 MUST NOT read:
        - Regime (P6)
        - Discourse, semantics, lexical layers
        - Acoustic / vrtti / kosha phases
        - Policy or governance phases (>=50)
        - Renderer or persona layers

CRITICAL CONSTRAINTS:
    - Must NOT rank futures
    - Must NOT select a scenario
    - Must NOT influence regime, discourse, semantics, or lexical layers
    - Must NOT affect governance or eligibility
    - Must NOT import acoustic or observer phases

INVARIANTS:
    INV-P47-1: No prediction (no future selection or ranking)
    INV-P47-2: Symmetric synthesis (scenario and trajectory treated as peers)
    INV-P47-3: Deterministic math only (pure weighted aggregation)
    INV-P47-4: Observer-only (cannot influence any authority phase)
    INV-P47-5: Absence-safe (missing inputs -> no output)
"""

from __future__ import annotations

from typing import Any, Optional

from .p47_schema import (
    P47_VERSION,
    UnifiedTrajectoryScenarioReport,
)
from .p47_synthesis_engine import run_p47_directly


# ============================================================================
# SIGNAL EXTRACTION
# ============================================================================


def _extract_p42_scenario_fusion(ctx: Any) -> Any:
    """
    Extract P42 ScenarioFusionField from context.

    Checks for:
        - ctx.p42_scenario_fusion_field

    INV-P47-4: We read this value but NEVER modify it.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        ScenarioFusionField if present, None otherwise
    """
    return getattr(ctx, "p42_scenario_fusion_field", None)


def _extract_p45_stability_field(ctx: Any) -> Any:
    """
    Extract P45 MultiTrajectoryStabilityField from context.

    Checks for:
        - ctx.p45_multi_trajectory_stability

    INV-P47-4: We read this value but NEVER modify it.

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

    INV-P47-4: We read this value but NEVER modify it.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        TrajectoryFieldConvergenceReport if present, None otherwise
    """
    return getattr(ctx, "p46_trajectory_convergence", None)


# ============================================================================
# INTEGRATION FUNCTIONS
# ============================================================================


def maybe_run_p47(ctx: Any) -> Optional[UnifiedTrajectoryScenarioReport]:
    """
    Run P47 unified trajectory-scenario synthesis if prerequisites are met.

    This is the main integration entry point. It:
    1. Checks if P47 should run
    2. Extracts P42, P45, P46 outputs from context
    3. Runs the synthesis computation
    4. Attaches the result to ctx.p47_unified_trajectory_scenario

    P47 is designed to run after P42, P45, and P46.
    Returns None if any required input is unavailable (INV-P47-5).

    INV-P47-1: No prediction - no future selection or ranking.
    INV-P47-2: Symmetric synthesis - scenario and trajectory as peers.
    INV-P47-3: Deterministic - same inputs always produce same outputs.
    INV-P47-4: Observer-only - we only write to ctx.p47_unified_trajectory_scenario.
    INV-P47-5: Absence-safe - missing input produces None.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        The UnifiedTrajectoryScenarioReport if run, None if skipped
    """
    # Check if P47 is disabled on this context
    if is_p47_disabled(ctx):
        return None

    # Extract required inputs
    p42_scenario_fusion = _extract_p42_scenario_fusion(ctx)
    p45_stability_field = _extract_p45_stability_field(ctx)
    p46_convergence = _extract_p46_trajectory_convergence(ctx)

    # INV-P47-5: Absence-safe - return None if any input is missing
    if p42_scenario_fusion is None:
        return None
    if p45_stability_field is None:
        return None
    if p46_convergence is None:
        return None

    # Run the synthesis computation
    synthesis_report = run_p47_directly(
        p42_scenario_fusion=p42_scenario_fusion,
        p45_multi_trajectory_stability=p45_stability_field,
        p46_trajectory_convergence=p46_convergence,
    )

    if synthesis_report is None:
        return None

    # Attach to context (observer-only append)
    _attach_synthesis_report_to_context(ctx, synthesis_report)

    return synthesis_report


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def is_p47_disabled(ctx: Any) -> bool:
    """
    Check if P47 is disabled on this context.

    P47 can be disabled by setting ctx._p47_disabled = True.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        True if P47 is disabled, False otherwise
    """
    return getattr(ctx, "_p47_disabled", False)


def has_p47_synthesis_report(ctx: Any) -> bool:
    """
    Check if context has a P47 synthesis report attached.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        True if ctx.p47_unified_trajectory_scenario is set and not None
    """
    return getattr(ctx, "p47_unified_trajectory_scenario", None) is not None


def get_p47_synthesis_report(ctx: Any) -> Optional[UnifiedTrajectoryScenarioReport]:
    """
    Get the P47 synthesis report from context if present.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        The UnifiedTrajectoryScenarioReport if present, None otherwise
    """
    return getattr(ctx, "p47_unified_trajectory_scenario", None)


def get_alignment_score(ctx: Any) -> float:
    """
    Get the alignment score from context.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        Alignment score in [0.0, 1.0], or 0.0 if no report
    """
    report = get_p47_synthesis_report(ctx)
    if report is None:
        return 0.0
    return report.alignment_score


def get_alignment_band(ctx: Any) -> str:
    """
    Get the alignment band from context.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        Alignment band string, or "misaligned" if no report
    """
    report = get_p47_synthesis_report(ctx)
    if report is None:
        return "misaligned"
    return report.alignment_band


def get_dominant_factor(ctx: Any) -> str:
    """
    Get the dominant factor from context.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        Dominant factor string, or "balanced" if no report
    """
    report = get_p47_synthesis_report(ctx)
    if report is None:
        return "balanced"
    return report.dominant_factor


def get_p47_version() -> str:
    """
    Get the current P47 schema version.

    Returns:
        Version string (e.g., "1.0.0")
    """
    return P47_VERSION


def _attach_synthesis_report_to_context(
    ctx: Any,
    synthesis_report: UnifiedTrajectoryScenarioReport,
) -> None:
    """
    Attach the P47 synthesis report to context.

    This is observer-only: we only append to ctx.p47_unified_trajectory_scenario,
    we do NOT modify any other context fields or influence behavior.

    INV-P47-4: Only writes to ctx.p47_unified_trajectory_scenario, nothing else.

    Args:
        ctx: PipelineContext
        synthesis_report: The P47 synthesis report to attach
    """
    # Attach to p47_unified_trajectory_scenario attribute
    if hasattr(ctx, "p47_unified_trajectory_scenario"):
        ctx.p47_unified_trajectory_scenario = synthesis_report
    else:
        try:
            setattr(ctx, "p47_unified_trajectory_scenario", synthesis_report)
        except AttributeError:
            # Context is frozen or doesn't allow attribute setting
            pass


# Public exports
__all__ = [
    # Integration
    "maybe_run_p47",
    "run_p47_directly",
    # Helpers
    "is_p47_disabled",
    "has_p47_synthesis_report",
    "get_p47_synthesis_report",
    "get_alignment_score",
    "get_alignment_band",
    "get_dominant_factor",
    "get_p47_version",
]
