"""
Phase 42: Scenario Fusion Engine Pipeline Integration

Integration functions for running P42 within the pipeline.
Provides pipeline-friendly entry points and context extraction.

Usage:
    from symbolu_core.mechanical.pipeline.p42_scenario_fusion import maybe_run_p42

    # In pipeline after P41:
    maybe_run_p42(ctx)

    # Access scenario fusion field:
    if ctx.p42_scenario_fusion_field is not None:
        print(f"Dominant: {ctx.p42_scenario_fusion_field.dominant_regime}")
        print(f"Confidence: {ctx.p42_scenario_fusion_field.fusion_confidence}")
        print(f"Entropy: {ctx.p42_scenario_fusion_field.regime_entropy}")

INPUTS (Read-Only):
    Phase 42 MAY read:
        - One or more ScenarioRegimeMap objects from Phase 41
          (e.g., per turn, per horizon, per domain)
        - Phase 19 Drift Fusion Report (read-only, optional)
        - Phase 40 Cross-Horizon Alignment (read-only, optional)

    Phase 42 MUST NOT read:
        - Raw text
        - Semantics, intent, discourse
        - Acoustic / vrtti / kosha data
        - Governance / eligibility phases (>=50)

CRITICAL CONSTRAINTS:
    - Must NOT rank futures
    - Must NOT forecast trajectories
    - Must NOT select actions
    - Must NOT trigger simulation engines
    - Must NOT modify PipelineContext outside its own output

INVARIANTS:
    - INV-P42-1: Observer-only (no downstream authority impact)
    - INV-P42-2: Deterministic aggregation (no randomness, no learned weights)
    - INV-P42-3: No regime creation (cannot invent new regimes)
    - INV-P42-4: Monotonic ambiguity (more disagreement → higher entropy)
    - INV-P42-5: Absence-safe (empty input produces no output)
"""

from __future__ import annotations

from typing import Any, List, Optional, Sequence

from symbolu_core.mechanical.pipeline.p41_scenario_regime_mapper.p41_schema import (
    ScenarioRegimeMap,
)

from .p42_schema import (
    P42_VERSION,
    ScenarioFusionField,
)
from .p42_fusion import fuse_scenario_regimes


# ============================================================================
# SIGNAL EXTRACTION
# ============================================================================


def _extract_scenario_regime_maps(ctx: Any) -> List[ScenarioRegimeMap]:
    """
    Extract ScenarioRegimeMap objects from context.

    Supports multiple storage patterns:
        - ctx.p41_scenario_regime_map (single map)
        - ctx.p41_scenario_regime_maps (list of maps)
        - ctx.scenario_regime_maps (list of maps)

    INV-P42-1: We read these values but NEVER modify them.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        List of ScenarioRegimeMap objects (may be empty)
    """
    maps: List[ScenarioRegimeMap] = []

    # Check for single scenario map
    single_map = getattr(ctx, "p41_scenario_regime_map", None)
    if single_map is not None and isinstance(single_map, ScenarioRegimeMap):
        maps.append(single_map)

    # Check for list of scenario maps (alternative storage)
    list_maps = getattr(ctx, "p41_scenario_regime_maps", None)
    if list_maps is not None and isinstance(list_maps, (list, tuple)):
        for item in list_maps:
            if isinstance(item, ScenarioRegimeMap) and item not in maps:
                maps.append(item)

    # Check for generic scenario_regime_maps
    generic_maps = getattr(ctx, "scenario_regime_maps", None)
    if generic_maps is not None and isinstance(generic_maps, (list, tuple)):
        for item in generic_maps:
            if isinstance(item, ScenarioRegimeMap) and item not in maps:
                maps.append(item)

    return maps


# ============================================================================
# INTEGRATION FUNCTIONS
# ============================================================================


def maybe_run_p42(ctx: Any) -> Optional[ScenarioFusionField]:
    """
    Run P42 scenario fusion if prerequisites are met.

    This is the main integration entry point. It:
    1. Checks if P42 should run
    2. Extracts ScenarioRegimeMap inputs from context
    3. Runs the fusion computation
    4. Attaches the result to ctx.p42_scenario_fusion_field

    P42 is designed to run after P41 (scenario regime mapping).
    Returns None if no input maps are available (INV-P42-5).

    INV-P42-1: Observer-only - we only write to ctx.p42_scenario_fusion_field.
    INV-P42-2: Deterministic - same inputs always produce same outputs.
    INV-P42-5: Absence-safe - empty input produces None.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        The ScenarioFusionField if run, None if skipped
    """
    # Check if P42 is disabled on this context
    if is_p42_disabled(ctx):
        return None

    # Extract input scenario maps
    regime_maps = _extract_scenario_regime_maps(ctx)

    # INV-P42-5: Absence-safe - return None if no inputs
    if not regime_maps:
        return None

    # Run the fusion
    fusion_field = fuse_scenario_regimes(regime_maps)

    if fusion_field is None:
        return None

    # Attach to context (observer-only append)
    _attach_fusion_field_to_context(ctx, fusion_field)

    return fusion_field


def run_p42_directly(
    regime_maps: Sequence[ScenarioRegimeMap],
) -> Optional[ScenarioFusionField]:
    """
    Run P42 directly with explicit inputs (for testing).

    This bypasses context extraction and allows direct testing
    with mock values.

    INV-P42-2: Deterministic - same inputs always produce same outputs.
    INV-P42-5: Absence-safe - empty input produces None.

    Args:
        regime_maps: Sequence of ScenarioRegimeMap objects

    Returns:
        ScenarioFusionField if computation succeeds, None otherwise
    """
    return fuse_scenario_regimes(regime_maps)


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def is_p42_disabled(ctx: Any) -> bool:
    """
    Check if P42 is disabled on this context.

    P42 can be disabled by setting ctx._p42_disabled = True.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        True if P42 is disabled, False otherwise
    """
    return getattr(ctx, "_p42_disabled", False)


def has_p42_fusion_field(ctx: Any) -> bool:
    """
    Check if context has a P42 fusion field attached.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        True if ctx.p42_scenario_fusion_field is set and not None
    """
    return getattr(ctx, "p42_scenario_fusion_field", None) is not None


def get_p42_fusion_field(ctx: Any) -> Optional[ScenarioFusionField]:
    """
    Get the P42 fusion field from context if present.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        The ScenarioFusionField if present, None otherwise
    """
    return getattr(ctx, "p42_scenario_fusion_field", None)


def get_dominant_regime(ctx: Any) -> str:
    """
    Get the dominant regime from context.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        Dominant regime string, or "ambiguous_mixed" if no field
    """
    fusion_field = get_p42_fusion_field(ctx)
    if fusion_field is None:
        return "ambiguous_mixed"
    return fusion_field.dominant_regime


def get_fusion_confidence(ctx: Any) -> float:
    """
    Get the fusion confidence from context.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        Fusion confidence in [0.0, 1.0], or 0.0 if no field
    """
    fusion_field = get_p42_fusion_field(ctx)
    if fusion_field is None:
        return 0.0
    return fusion_field.fusion_confidence


def get_regime_entropy(ctx: Any) -> float:
    """
    Get the regime entropy from context.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        Regime entropy in [0.0, 1.0], or 0.0 if no field
    """
    fusion_field = get_p42_fusion_field(ctx)
    if fusion_field is None:
        return 0.0
    return fusion_field.regime_entropy


def get_regime_distribution(ctx: Any) -> dict:
    """
    Get the regime distribution from context.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        Regime distribution dict, or empty dict if no field
    """
    fusion_field = get_p42_fusion_field(ctx)
    if fusion_field is None:
        return {}
    return dict(fusion_field.regime_distribution)


def is_dominant_stable(ctx: Any) -> bool:
    """
    Check if the dominant regime is stable_continuity.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        True if dominant regime is stable_continuity, False otherwise
    """
    return get_dominant_regime(ctx) == "stable_continuity"


def is_dominant_divergent(ctx: Any) -> bool:
    """
    Check if the dominant regime is divergent_instability.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        True if dominant regime is divergent_instability, False otherwise
    """
    return get_dominant_regime(ctx) == "divergent_instability"


def is_ambiguous(ctx: Any) -> bool:
    """
    Check if the dominant regime is ambiguous_mixed.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        True if dominant regime is ambiguous_mixed, False otherwise
    """
    return get_dominant_regime(ctx) == "ambiguous_mixed"


def get_p42_version() -> str:
    """
    Get the current P42 schema version.

    Returns:
        Version string (e.g., "1.0.0")
    """
    return P42_VERSION


def _attach_fusion_field_to_context(
    ctx: Any,
    fusion_field: ScenarioFusionField,
) -> None:
    """
    Attach the P42 fusion field to context.

    This is observer-only: we only append to ctx.p42_scenario_fusion_field,
    we do NOT modify any other context fields or influence behavior.

    INV-P42-1: Only writes to ctx.p42_scenario_fusion_field, nothing else.

    Args:
        ctx: PipelineContext
        fusion_field: The P42 fusion field to attach
    """
    # Attach to p42_scenario_fusion_field attribute
    if hasattr(ctx, "p42_scenario_fusion_field"):
        ctx.p42_scenario_fusion_field = fusion_field
    else:
        try:
            setattr(ctx, "p42_scenario_fusion_field", fusion_field)
        except AttributeError:
            # Context is frozen or doesn't allow attribute setting
            pass


# Public exports
__all__ = [
    # Integration
    "maybe_run_p42",
    "run_p42_directly",
    # Helpers
    "is_p42_disabled",
    "has_p42_fusion_field",
    "get_p42_fusion_field",
    "get_dominant_regime",
    "get_fusion_confidence",
    "get_regime_entropy",
    "get_regime_distribution",
    "is_dominant_stable",
    "is_dominant_divergent",
    "is_ambiguous",
    "get_p42_version",
]
