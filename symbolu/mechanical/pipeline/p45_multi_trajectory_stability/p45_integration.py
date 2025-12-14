"""
Phase 45: Multi-Trajectory Stability Field Pipeline Integration

Integration functions for running P45 within the pipeline.
Provides pipeline-friendly entry points and context extraction.

Usage:
    from symbolu.mechanical.pipeline.p45_multi_trajectory_stability import (
        maybe_run_p45,
    )

    # In pipeline after P44:
    maybe_run_p45(ctx)

    # Access stability field:
    if ctx.p45_multi_trajectory_stability is not None:
        print(f"Stability: {ctx.p45_multi_trajectory_stability.stability_index}")
        print(f"Band: {ctx.p45_multi_trajectory_stability.stability_band}")

INPUTS (Read-Only):
    Phase 45 MAY read:
        - ctx.p44_coherence_scenario_alignment (CoherenceScenarioAlignmentReport)
        - ctx.p43_scenario_what_if (ScenarioWhatIfSet)
        - ctx.coherence_v3_quality (optional, for context)

    Phase 45 MUST NOT read:
        - Regime (P6)
        - Discourse, semantics, lexical outputs
        - Acoustic / vrtti / kosha layers
        - Policy or governance phases (>=50)
        - Renderer or persona layers

CRITICAL CONSTRAINTS:
    - Must NOT choose a "best" trajectory
    - Must NOT rank variants
    - Must NOT forecast outcomes
    - Must NOT gate decisions
    - Must NOT feed any upstream phase

INVARIANTS:
    - INV-P45-1: No trajectory preference (no ranking, sorting, or selection)
    - INV-P45-2: Deterministic aggregation only (pure math, no heuristics, no learning)
    - INV-P45-3: Field-level semantics only (individual variants do not influence bands)
    - INV-P45-4: Observer-only (output never influences routing or governance)
    - INV-P45-5: Absence-safe (missing inputs -> no output)
"""

from __future__ import annotations

from typing import Any, Optional

from .p45_schema import (
    P45_VERSION,
    MultiTrajectoryStabilityField,
)
from .p45_stability_engine import compute_stability_field


# ============================================================================
# SIGNAL EXTRACTION
# ============================================================================


def _extract_p44_alignment_report(ctx: Any) -> Any:
    """
    Extract P44 coherence-scenario alignment report from context.

    Checks for:
        - ctx.p44_coherence_scenario_alignment

    INV-P45-4: We read this value but NEVER modify it.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        CoherenceScenarioAlignmentReport if present, None otherwise
    """
    return getattr(ctx, "p44_coherence_scenario_alignment", None)


def _extract_p43_what_if_set(ctx: Any) -> Any:
    """
    Extract P43 scenario what-if set from context.

    Checks for:
        - ctx.p43_scenario_what_if

    INV-P45-4: We read this value but NEVER modify it.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        ScenarioWhatIfSet if present, None otherwise
    """
    return getattr(ctx, "p43_scenario_what_if", None)


# ============================================================================
# INTEGRATION FUNCTIONS
# ============================================================================


def maybe_run_p45(ctx: Any) -> Optional[MultiTrajectoryStabilityField]:
    """
    Run P45 multi-trajectory stability field computation if prerequisites are met.

    This is the main integration entry point. It:
    1. Checks if P45 should run
    2. Extracts P44 CoherenceScenarioAlignmentReport from context
    3. Extracts P43 ScenarioWhatIfSet from context
    4. Runs the stability field computation
    5. Attaches the result to ctx.p45_multi_trajectory_stability

    P45 is designed to run after P44.
    Returns None if required inputs are unavailable (INV-P45-5).

    INV-P45-1: No trajectory preference - no ranking, sorting, or selection.
    INV-P45-2: Deterministic - same inputs always produce same outputs.
    INV-P45-4: Observer-only - we only write to ctx.p45_multi_trajectory_stability.
    INV-P45-5: Absence-safe - missing input produces None.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        The MultiTrajectoryStabilityField if run, None if skipped
    """
    # Check if P45 is disabled on this context
    if is_p45_disabled(ctx):
        return None

    # Extract P44 alignment report
    p44_alignment_report = _extract_p44_alignment_report(ctx)

    # Extract P43 what-if set
    p43_what_if_set = _extract_p43_what_if_set(ctx)

    # INV-P45-5: Absence-safe - return None if required inputs missing
    if p44_alignment_report is None or p43_what_if_set is None:
        return None

    # Run the stability field computation
    stability_field = compute_stability_field(
        p44_alignment_report=p44_alignment_report,
        p43_what_if_set=p43_what_if_set,
    )

    if stability_field is None:
        return None

    # Attach to context (observer-only append)
    _attach_stability_field_to_context(ctx, stability_field)

    return stability_field


def run_p45_directly(
    p44_alignment_report: Any,
    p43_what_if_set: Any,
) -> Optional[MultiTrajectoryStabilityField]:
    """
    Run P45 directly with explicit inputs (for testing).

    This bypasses context extraction and allows direct testing
    with mock values.

    INV-P45-2: Deterministic - same inputs always produce same outputs.
    INV-P45-5: Absence-safe - missing input produces None.

    Args:
        p44_alignment_report: CoherenceScenarioAlignmentReport from Phase 44
        p43_what_if_set: ScenarioWhatIfSet from Phase 43

    Returns:
        MultiTrajectoryStabilityField if computation succeeds, None otherwise
    """
    return compute_stability_field(
        p44_alignment_report=p44_alignment_report,
        p43_what_if_set=p43_what_if_set,
    )


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def is_p45_disabled(ctx: Any) -> bool:
    """
    Check if P45 is disabled on this context.

    P45 can be disabled by setting ctx._p45_disabled = True.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        True if P45 is disabled, False otherwise
    """
    return getattr(ctx, "_p45_disabled", False)


def has_p45_stability_field(ctx: Any) -> bool:
    """
    Check if context has a P45 stability field attached.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        True if ctx.p45_multi_trajectory_stability is set and not None
    """
    return getattr(ctx, "p45_multi_trajectory_stability", None) is not None


def get_p45_stability_field(ctx: Any) -> Optional[MultiTrajectoryStabilityField]:
    """
    Get the P45 stability field from context if present.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        The MultiTrajectoryStabilityField if present, None otherwise
    """
    return getattr(ctx, "p45_multi_trajectory_stability", None)


def get_stability_index(ctx: Any) -> float:
    """
    Get the stability index from context.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        Stability index in [0.0, 1.0], or 0.0 if no field
    """
    field = get_p45_stability_field(ctx)
    if field is None:
        return 0.0
    return field.stability_index


def get_stability_band(ctx: Any) -> str:
    """
    Get the stability band from context.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        Stability band string, or "chaotic" if no field
    """
    field = get_p45_stability_field(ctx)
    if field is None:
        return "chaotic"
    return field.stability_band


def get_p45_version() -> str:
    """
    Get the current P45 schema version.

    Returns:
        Version string (e.g., "1.0.0")
    """
    return P45_VERSION


def _attach_stability_field_to_context(
    ctx: Any,
    stability_field: MultiTrajectoryStabilityField,
) -> None:
    """
    Attach the P45 stability field to context.

    This is observer-only: we only append to ctx.p45_multi_trajectory_stability,
    we do NOT modify any other context fields or influence behavior.

    INV-P45-4: Only writes to ctx.p45_multi_trajectory_stability, nothing else.

    Args:
        ctx: PipelineContext
        stability_field: The P45 stability field to attach
    """
    # Attach to p45_multi_trajectory_stability attribute
    if hasattr(ctx, "p45_multi_trajectory_stability"):
        ctx.p45_multi_trajectory_stability = stability_field
    else:
        try:
            setattr(ctx, "p45_multi_trajectory_stability", stability_field)
        except AttributeError:
            # Context is frozen or doesn't allow attribute setting
            pass


# Public exports
__all__ = [
    # Integration
    "maybe_run_p45",
    "run_p45_directly",
    # Helpers
    "is_p45_disabled",
    "has_p45_stability_field",
    "get_p45_stability_field",
    "get_stability_index",
    "get_stability_band",
    "get_p45_version",
]
