"""
Phase 43: Scenario What-If Simulator Pipeline Integration

Integration functions for running P43 within the pipeline.
Provides pipeline-friendly entry points and context extraction.

Usage:
    from symbolu_core.mechanical.pipeline.p43_scenario_what_if import maybe_run_p43

    # In pipeline after P42:
    maybe_run_p43(ctx)

    # Access what-if set:
    if ctx.p43_scenario_what_if is not None:
        print(f"Base regime: {ctx.p43_scenario_what_if.base_regime}")
        print(f"Variants: {ctx.p43_scenario_what_if.variant_count}")

INPUTS (Read-Only):
    Phase 43 MAY read:
        - ScenarioFusionField from Phase 42
        - Optional: Phase 40 Cross-Horizon Alignment
        - Optional: Phase 19 Drift Fusion Report

    Phase 43 MUST NOT read:
        - Raw text
        - Semantics, intent, discourse
        - Acoustic / vrtti / kosha data
        - Regime gate outputs (P6)
        - Any governance or eligibility phases (>=50)

CRITICAL CONSTRAINTS:
    - Must NOT rank variants
    - Must NOT choose a "best" outcome
    - Must NOT forecast timelines
    - Must NOT feed results upstream
    - Must NOT modify PipelineContext beyond its own field

INVARIANTS:
    - INV-P43-1: Simulation only (no prediction, no likelihoods)
    - INV-P43-2: Deterministic perturbations (no randomness)
    - INV-P43-3: Bounded exploration (exactly four variants)
    - INV-P43-4: No authority impact (observer-only)
    - INV-P43-5: Absence-safe (no input -> no output)
"""

from __future__ import annotations

from typing import Any, Optional

from symbolu_core.mechanical.pipeline.p42_scenario_fusion.p42_schema import (
    ScenarioFusionField,
)

from .p43_schema import (
    P43_VERSION,
    ScenarioWhatIfSet,
)
from .p43_simulator import simulate_what_if_variants


# ============================================================================
# SIGNAL EXTRACTION
# ============================================================================


def _extract_scenario_fusion_field(ctx: Any) -> Optional[ScenarioFusionField]:
    """
    Extract ScenarioFusionField from context.

    Checks for:
        - ctx.p42_scenario_fusion_field

    INV-P43-4: We read these values but NEVER modify them.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        ScenarioFusionField if present, None otherwise
    """
    fusion_field = getattr(ctx, "p42_scenario_fusion_field", None)
    if fusion_field is not None and isinstance(fusion_field, ScenarioFusionField):
        return fusion_field
    return None


# ============================================================================
# INTEGRATION FUNCTIONS
# ============================================================================


def maybe_run_p43(ctx: Any) -> Optional[ScenarioWhatIfSet]:
    """
    Run P43 what-if simulation if prerequisites are met.

    This is the main integration entry point. It:
    1. Checks if P43 should run
    2. Extracts ScenarioFusionField from context
    3. Runs the simulation
    4. Attaches the result to ctx.p43_scenario_what_if

    P43 is designed to run after P42 (scenario fusion).
    Returns None if no fusion field is available (INV-P43-5).

    INV-P43-1: Simulation only - we generate possibilities, not predictions.
    INV-P43-2: Deterministic - same inputs always produce same outputs.
    INV-P43-4: Observer-only - we only write to ctx.p43_scenario_what_if.
    INV-P43-5: Absence-safe - no input produces None.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        The ScenarioWhatIfSet if run, None if skipped
    """
    # Check if P43 is disabled on this context
    if is_p43_disabled(ctx):
        return None

    # Extract input fusion field
    fusion_field = _extract_scenario_fusion_field(ctx)

    # INV-P43-5: Absence-safe - return None if no input
    if fusion_field is None:
        return None

    # Run the simulation
    what_if_set = simulate_what_if_variants(fusion_field)

    if what_if_set is None:
        return None

    # Attach to context (observer-only append)
    _attach_what_if_set_to_context(ctx, what_if_set)

    return what_if_set


def run_p43_directly(
    fusion_field: ScenarioFusionField,
) -> Optional[ScenarioWhatIfSet]:
    """
    Run P43 directly with explicit input (for testing).

    This bypasses context extraction and allows direct testing
    with mock values.

    INV-P43-2: Deterministic - same inputs always produce same outputs.
    INV-P43-5: Absence-safe - None input produces None output.

    Args:
        fusion_field: ScenarioFusionField from Phase 42

    Returns:
        ScenarioWhatIfSet if computation succeeds, None otherwise
    """
    return simulate_what_if_variants(fusion_field)


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def is_p43_disabled(ctx: Any) -> bool:
    """
    Check if P43 is disabled on this context.

    P43 can be disabled by setting ctx._p43_disabled = True.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        True if P43 is disabled, False otherwise
    """
    return getattr(ctx, "_p43_disabled", False)


def has_p43_what_if_set(ctx: Any) -> bool:
    """
    Check if context has a P43 what-if set attached.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        True if ctx.p43_scenario_what_if is set and not None
    """
    return getattr(ctx, "p43_scenario_what_if", None) is not None


def get_p43_what_if_set(ctx: Any) -> Optional[ScenarioWhatIfSet]:
    """
    Get the P43 what-if set from context if present.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        The ScenarioWhatIfSet if present, None otherwise
    """
    return getattr(ctx, "p43_scenario_what_if", None)


def get_base_regime(ctx: Any) -> str:
    """
    Get the base regime from the what-if set.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        Base regime string, or "ambiguous_mixed" if no set
    """
    what_if_set = get_p43_what_if_set(ctx)
    if what_if_set is None:
        return "ambiguous_mixed"
    return what_if_set.base_regime


def get_variant_count(ctx: Any) -> int:
    """
    Get the number of variants in the what-if set.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        Number of variants, or 0 if no set
    """
    what_if_set = get_p43_what_if_set(ctx)
    if what_if_set is None:
        return 0
    return what_if_set.variant_count


def get_p43_version() -> str:
    """
    Get the current P43 schema version.

    Returns:
        Version string (e.g., "1.0.0")
    """
    return P43_VERSION


def _attach_what_if_set_to_context(
    ctx: Any,
    what_if_set: ScenarioWhatIfSet,
) -> None:
    """
    Attach the P43 what-if set to context.

    This is observer-only: we only append to ctx.p43_scenario_what_if,
    we do NOT modify any other context fields or influence behavior.

    INV-P43-4: Only writes to ctx.p43_scenario_what_if, nothing else.

    Args:
        ctx: PipelineContext
        what_if_set: The P43 what-if set to attach
    """
    # Attach to p43_scenario_what_if attribute
    if hasattr(ctx, "p43_scenario_what_if"):
        ctx.p43_scenario_what_if = what_if_set
    else:
        try:
            setattr(ctx, "p43_scenario_what_if", what_if_set)
        except AttributeError:
            # Context is frozen or doesn't allow attribute setting
            pass


# Public exports
__all__ = [
    # Integration
    "maybe_run_p43",
    "run_p43_directly",
    # Helpers
    "is_p43_disabled",
    "has_p43_what_if_set",
    "get_p43_what_if_set",
    "get_base_regime",
    "get_variant_count",
    "get_p43_version",
]
