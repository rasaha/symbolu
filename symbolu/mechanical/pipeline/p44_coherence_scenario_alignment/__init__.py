"""
Phase 44: Coherence-Scenario Alignment Engine

This phase measures alignment between current coherence state and
future scenario trajectories. It produces alignment scores, not decisions.

Phase 44 answers:
    "How well do the possible scenario trajectories align with the
    system's current coherence state?"

This is alignment measurement only - not forecasting, not choice, not gating.

Invariants:
    INV-P44-1: Measurement only (no ranking, no preference, no selection)
    INV-P44-2: Deterministic math only (no randomness, no learned parameters)
    INV-P44-3: Variant isolation (variants do not influence base alignment)
    INV-P44-4: No authority influence (output never affects regime, discourse, policy)
    INV-P44-5: Absence-safe (missing inputs -> no output)

Usage:
    from symbolu.mechanical.pipeline.p44_coherence_scenario_alignment import (
        maybe_run_p44,
        CoherenceScenarioAlignmentReport,
    )

    # In pipeline after P43:
    maybe_run_p44(ctx)

    # Access alignment report:
    if ctx.p44_coherence_scenario_alignment is not None:
        print(f"Base alignment: {ctx.p44_coherence_scenario_alignment.base_alignment_score}")
        print(f"Band: {ctx.p44_coherence_scenario_alignment.alignment_band}")
"""

from .p44_schema import (
    P44_VERSION,
    AlignmentBand,
    CoherenceScenarioAlignmentReport,
    create_alignment_report,
)
from .p44_alignment_engine import compute_alignment
from .p44_integration import (
    maybe_run_p44,
    run_p44_directly,
    is_p44_disabled,
    has_p44_alignment_report,
    get_p44_alignment_report,
    get_base_alignment_score,
    get_alignment_band,
    get_p44_version,
)

__all__ = [
    # Schema
    "P44_VERSION",
    "AlignmentBand",
    "CoherenceScenarioAlignmentReport",
    "create_alignment_report",
    # Engine
    "compute_alignment",
    # Integration
    "maybe_run_p44",
    "run_p44_directly",
    "is_p44_disabled",
    "has_p44_alignment_report",
    "get_p44_alignment_report",
    "get_base_alignment_score",
    "get_alignment_band",
    "get_p44_version",
]
