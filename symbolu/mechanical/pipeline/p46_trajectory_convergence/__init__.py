"""
Phase 46: Trajectory Field Convergence Engine

This phase measures whether the set of possible futures is structurally
collapsing toward coherence or remaining fragmented over time.

Phase 46 answers:
    "Is the trajectory field converging, diverging, or unresolved over time?"

This is field convergence measurement - not prediction,
not decision-making, not trajectory selection.

Invariants:
    INV-P46-1: No trajectory ranking (individual futures are never compared)
    INV-P46-2: Temporal comparison only (uses only past vs current convergence)
    INV-P46-3: Deterministic math (no learning, no heuristics)
    INV-P46-4: Observer-only (cannot influence routing, gating, or decisions)
    INV-P46-5: Absence-safe (missing inputs -> no output)

Usage:
    from symbolu.mechanical.pipeline.p46_trajectory_convergence import (
        maybe_run_p46,
        TrajectoryFieldConvergenceReport,
    )

    # In pipeline after P45:
    maybe_run_p46(ctx)

    # Access convergence report:
    if ctx.p46_trajectory_convergence is not None:
        print(f"Score: {ctx.p46_trajectory_convergence.convergence_score}")
        print(f"State: {ctx.p46_trajectory_convergence.field_state}")
        print(f"Trend: {ctx.p46_trajectory_convergence.convergence_trend}")
"""

from .p46_schema import (
    P46_VERSION,
    ConvergenceTrend,
    FieldState,
    TrajectoryFieldConvergenceReport,
    create_convergence_report,
)
from .p46_convergence_engine import compute_convergence_report
from .p46_integration import (
    maybe_run_p46,
    run_p46_directly,
    is_p46_disabled,
    has_p46_convergence_report,
    get_p46_convergence_report,
    get_convergence_score,
    get_field_state,
    get_convergence_trend,
    get_p46_version,
)

__all__ = [
    # Schema
    "P46_VERSION",
    "ConvergenceTrend",
    "FieldState",
    "TrajectoryFieldConvergenceReport",
    "create_convergence_report",
    # Engine
    "compute_convergence_report",
    # Integration
    "maybe_run_p46",
    "run_p46_directly",
    "is_p46_disabled",
    "has_p46_convergence_report",
    "get_p46_convergence_report",
    "get_convergence_score",
    "get_field_state",
    "get_convergence_trend",
    "get_p46_version",
]
