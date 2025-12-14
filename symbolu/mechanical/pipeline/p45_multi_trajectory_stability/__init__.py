"""
Phase 45: Multi-Trajectory Stability Field

This phase computes a stability field over multiple possible futures,
measuring dispersion, volatility, and convergence tendency
without preferring or selecting any trajectory.

Phase 45 answers:
    "Across all possible trajectories, how stable is the future space as a whole?"

This is field-level structural analysis - not decision-making,
not trajectory selection, not outcome prediction.

Invariants:
    INV-P45-1: No trajectory preference (no ranking, sorting, or selection)
    INV-P45-2: Deterministic aggregation only (pure math, no heuristics, no learning)
    INV-P45-3: Field-level semantics only (individual variants do not influence bands)
    INV-P45-4: Observer-only (output never influences routing or governance)
    INV-P45-5: Absence-safe (missing inputs -> no output)

Usage:
    from symbolu.mechanical.pipeline.p45_multi_trajectory_stability import (
        maybe_run_p45,
        MultiTrajectoryStabilityField,
    )

    # In pipeline after P44:
    maybe_run_p45(ctx)

    # Access stability field:
    if ctx.p45_multi_trajectory_stability is not None:
        print(f"Stability: {ctx.p45_multi_trajectory_stability.stability_index}")
        print(f"Band: {ctx.p45_multi_trajectory_stability.stability_band}")
"""

from .p45_schema import (
    P45_VERSION,
    StabilityBand,
    MultiTrajectoryStabilityField,
    create_stability_field,
)
from .p45_stability_engine import compute_stability_field
from .p45_integration import (
    maybe_run_p45,
    run_p45_directly,
    is_p45_disabled,
    has_p45_stability_field,
    get_p45_stability_field,
    get_stability_index,
    get_stability_band,
    get_p45_version,
)

__all__ = [
    # Schema
    "P45_VERSION",
    "StabilityBand",
    "MultiTrajectoryStabilityField",
    "create_stability_field",
    # Engine
    "compute_stability_field",
    # Integration
    "maybe_run_p45",
    "run_p45_directly",
    "is_p45_disabled",
    "has_p45_stability_field",
    "get_p45_stability_field",
    "get_stability_index",
    "get_stability_band",
    "get_p45_version",
]
