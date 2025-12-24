"""
Phase 46: Trajectory Field Convergence Pipeline Integration

Integration functions for running P46 within the pipeline.
Provides pipeline-friendly entry points and context extraction.

Usage:
    from symbolu.mechanical.pipeline.p46_trajectory_convergence import (
        maybe_run_p46,
    )

    # In pipeline after P45:
    maybe_run_p46(ctx)

    # Access convergence report:
    if ctx.p46_trajectory_convergence is not None:
        print(f"Score: {ctx.p46_trajectory_convergence.convergence_score}")
        print(f"State: {ctx.p46_trajectory_convergence.field_state}")

INPUTS (Read-Only):
    Phase 46 MAY read:
        - ctx.p45_multi_trajectory_stability (current P45 stability field)
        - ctx.p45_historical_snapshots (optional list of prior P45 snapshots)

    Phase 46 MUST NOT read:
        - Regime (P6)
        - Discourse / semantics / lexical layers
        - Acoustic / vrtti / kosha layers
        - Policy or governance phases (>=50)
        - Renderer or persona layers

CRITICAL CONSTRAINTS:
    - Must NOT rank or select trajectories
    - Must NOT predict outcomes
    - Must NOT influence any authority phase
    - Must NOT gate decisions
    - Must NOT feed any upstream phase

INVARIANTS:
    INV-P46-1: No trajectory ranking (individual futures are never compared)
    INV-P46-2: Temporal comparison only (uses only past vs current convergence)
    INV-P46-3: Deterministic math (no learning, no heuristics)
    INV-P46-4: Observer-only (cannot influence routing, gating, or decisions)
    INV-P46-5: Absence-safe (missing inputs -> no output)
"""

from __future__ import annotations

from typing import Any, List, Optional

from .p46_schema import (
    P46_VERSION,
    TrajectoryFieldConvergenceReport,
)
from .p46_convergence_engine import compute_convergence_report


# ============================================================================
# SIGNAL EXTRACTION
# ============================================================================


def _extract_p45_stability_field(ctx: Any) -> Any:
    """
    Extract P45 multi-trajectory stability field from context.

    Checks for:
        - ctx.p45_multi_trajectory_stability

    INV-P46-4: We read this value but NEVER modify it.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        MultiTrajectoryStabilityField if present, None otherwise
    """
    return getattr(ctx, "p45_multi_trajectory_stability", None)


def _extract_p45_historical_snapshots(ctx: Any) -> List[Any]:
    """
    Extract historical P45 snapshots from context.

    Checks for:
        - ctx.p45_historical_snapshots

    INV-P46-2: We use historical data for temporal comparison only.
    INV-P46-4: We read this value but NEVER modify it.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        List of prior P45 stability fields (empty list if none)
    """
    snapshots = getattr(ctx, "p45_historical_snapshots", None)
    if snapshots is None:
        return []
    if not isinstance(snapshots, list):
        return []
    return snapshots


# ============================================================================
# INTEGRATION FUNCTIONS
# ============================================================================


def maybe_run_p46(ctx: Any) -> Optional[TrajectoryFieldConvergenceReport]:
    """
    Run P46 trajectory field convergence computation if prerequisites are met.

    This is the main integration entry point. It:
    1. Checks if P46 should run
    2. Extracts P45 MultiTrajectoryStabilityField from context
    3. Extracts historical P45 snapshots if available
    4. Runs the convergence computation
    5. Attaches the result to ctx.p46_trajectory_convergence

    P46 is designed to run after P45.
    Returns None if required inputs are unavailable (INV-P46-5).

    INV-P46-1: No trajectory ranking - no comparison of individual futures.
    INV-P46-2: Temporal comparison - uses past vs current convergence.
    INV-P46-3: Deterministic - same inputs always produce same outputs.
    INV-P46-4: Observer-only - we only write to ctx.p46_trajectory_convergence.
    INV-P46-5: Absence-safe - missing input produces None.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        The TrajectoryFieldConvergenceReport if run, None if skipped
    """
    # Check if P46 is disabled on this context
    if is_p46_disabled(ctx):
        return None

    # Extract P45 stability field
    p45_stability_field = _extract_p45_stability_field(ctx)

    # INV-P46-5: Absence-safe - return None if P45 is missing
    if p45_stability_field is None:
        return None

    # Extract historical snapshots (optional)
    p45_historical = _extract_p45_historical_snapshots(ctx)

    # Run the convergence computation
    convergence_report = compute_convergence_report(
        p45_stability_field=p45_stability_field,
        p45_historical_snapshots=p45_historical,
    )

    if convergence_report is None:
        return None

    # Attach to context (observer-only append)
    _attach_convergence_report_to_context(ctx, convergence_report)

    return convergence_report


def run_p46_directly(
    p45_stability_field: Any,
    p45_historical_snapshots: List[Any] | None = None,
) -> Optional[TrajectoryFieldConvergenceReport]:
    """
    Run P46 directly with explicit inputs (for testing).

    This bypasses context extraction and allows direct testing
    with mock values.

    INV-P46-3: Deterministic - same inputs always produce same outputs.
    INV-P46-5: Absence-safe - missing input produces None.

    Args:
        p45_stability_field: Current P45 MultiTrajectoryStabilityField
        p45_historical_snapshots: Optional list of prior P45 snapshots

    Returns:
        TrajectoryFieldConvergenceReport if computation succeeds, None otherwise
    """
    return compute_convergence_report(
        p45_stability_field=p45_stability_field,
        p45_historical_snapshots=p45_historical_snapshots,
    )


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def is_p46_disabled(ctx: Any) -> bool:
    """
    Check if P46 is disabled on this context.

    P46 can be disabled by setting ctx._p46_disabled = True.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        True if P46 is disabled, False otherwise
    """
    return getattr(ctx, "_p46_disabled", False)


def has_p46_convergence_report(ctx: Any) -> bool:
    """
    Check if context has a P46 convergence report attached.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        True if ctx.p46_trajectory_convergence is set and not None
    """
    return getattr(ctx, "p46_trajectory_convergence", None) is not None


def get_p46_convergence_report(ctx: Any) -> Optional[TrajectoryFieldConvergenceReport]:
    """
    Get the P46 convergence report from context if present.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        The TrajectoryFieldConvergenceReport if present, None otherwise
    """
    return getattr(ctx, "p46_trajectory_convergence", None)


def get_convergence_score(ctx: Any) -> float:
    """
    Get the convergence score from context.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        Convergence score in [0.0, 1.0], or 0.0 if no report
    """
    report = get_p46_convergence_report(ctx)
    if report is None:
        return 0.0
    return report.convergence_score


def get_field_state(ctx: Any) -> str:
    """
    Get the field state from context.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        Field state string, or "diverging" if no report
    """
    report = get_p46_convergence_report(ctx)
    if report is None:
        return "diverging"
    return report.field_state


def get_convergence_trend(ctx: Any) -> str:
    """
    Get the convergence trend from context.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        Convergence trend string, or "flat" if no report
    """
    report = get_p46_convergence_report(ctx)
    if report is None:
        return "flat"
    return report.convergence_trend


def get_p46_version() -> str:
    """
    Get the current P46 schema version.

    Returns:
        Version string (e.g., "1.0.0")
    """
    return P46_VERSION


def _attach_convergence_report_to_context(
    ctx: Any,
    convergence_report: TrajectoryFieldConvergenceReport,
) -> None:
    """
    Attach the P46 convergence report to context.

    This is observer-only: we only append to ctx.p46_trajectory_convergence,
    we do NOT modify any other context fields or influence behavior.

    INV-P46-4: Only writes to ctx.p46_trajectory_convergence, nothing else.

    Args:
        ctx: PipelineContext
        convergence_report: The P46 convergence report to attach
    """
    # Attach to p46_trajectory_convergence attribute
    if hasattr(ctx, "p46_trajectory_convergence"):
        ctx.p46_trajectory_convergence = convergence_report
    else:
        try:
            setattr(ctx, "p46_trajectory_convergence", convergence_report)
        except AttributeError:
            # Context is frozen or doesn't allow attribute setting
            pass


# Public exports
__all__ = [
    # Integration
    "maybe_run_p46",
    "run_p46_directly",
    # Helpers
    "is_p46_disabled",
    "has_p46_convergence_report",
    "get_p46_convergence_report",
    "get_convergence_score",
    "get_field_state",
    "get_convergence_trend",
    "get_p46_version",
]
