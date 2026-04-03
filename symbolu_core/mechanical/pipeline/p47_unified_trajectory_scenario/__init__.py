"""
Phase 47: Unified Trajectory-Scenario Synthesis

First and only place where scenario space and trajectory space are
synthesized into a single observational construct.

Phase 47 answers:
    "Do the scenario space (what-if worlds) and the trajectory field
    (future paths) agree structurally, or are they drifting apart?"

This is structural synthesis, not prediction and not action.

Usage:
    from symbolu_core.mechanical.pipeline.p47_unified_trajectory_scenario import (
        maybe_run_p47,
        run_p47_directly,
        UnifiedTrajectoryScenarioReport,
    )

    # In pipeline after P42, P45, P46:
    report = maybe_run_p47(ctx)

    if report is not None:
        print(f"Alignment: {report.alignment_score}")
        print(f"Band: {report.alignment_band}")
        print(f"Dominant: {report.dominant_factor}")

Invariants:
    INV-P47-1: No prediction (no future selection or ranking)
    INV-P47-2: Symmetric synthesis (scenario and trajectory treated as peers)
    INV-P47-3: Deterministic math only (pure weighted aggregation)
    INV-P47-4: Observer-only (cannot influence any authority phase)
    INV-P47-5: Absence-safe (missing inputs -> no output)
"""

from .p47_schema import (
    P47_VERSION,
    AlignmentBand,
    DominantFactor,
    UnifiedTrajectoryScenarioReport,
    create_unified_trajectory_scenario_report,
    ALIGNED_THRESHOLD,
    STRAINED_THRESHOLD,
    DOMINANCE_THRESHOLD,
)

from .p47_synthesis_engine import (
    compute_synthesis_report,
    run_p47_directly,
)

from .p47_integration import (
    maybe_run_p47,
    is_p47_disabled,
    has_p47_synthesis_report,
    get_p47_synthesis_report,
    get_alignment_score,
    get_alignment_band,
    get_dominant_factor,
    get_p47_version,
)


__all__ = [
    # Schema
    "P47_VERSION",
    "AlignmentBand",
    "DominantFactor",
    "UnifiedTrajectoryScenarioReport",
    "create_unified_trajectory_scenario_report",
    "ALIGNED_THRESHOLD",
    "STRAINED_THRESHOLD",
    "DOMINANCE_THRESHOLD",
    # Engine
    "compute_synthesis_report",
    "run_p47_directly",
    # Integration
    "maybe_run_p47",
    "is_p47_disabled",
    "has_p47_synthesis_report",
    "get_p47_synthesis_report",
    "get_alignment_score",
    "get_alignment_band",
    "get_dominant_factor",
    "get_p47_version",
]
