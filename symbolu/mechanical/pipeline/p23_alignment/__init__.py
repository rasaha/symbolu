"""
P23 - Inner-Outer Alignment Observer

This phase is observer-only and non-authoritative.

P23 observes whether the internal acoustic pressure (from P22) is aligned with
the externally allowed interaction mode (from P6 + P7).

P23 answers only this question:
    Is the internal acoustic pressure (from P22) aligned with the externally
    allowed interaction mode (from P6 + P7)?

P23:
    - does not decide what to say
    - does not decide how to say it
    - does not gate or block
    - does not infer emotion or intent

It observes alignment or tension and reports it.

CRITICAL ARCHITECTURAL INVARIANT:
    P23 is purely observational. It witnesses alignment without authority.
    The alignment report is immutable and has no downstream effect on routing.

Usage:
    from symbolu.mechanical.pipeline.p23_alignment import maybe_run_p23

    # In pipeline after P22:
    ctx = maybe_run_p23(ctx)

    # Access report:
    if ctx.p23_alignment_report is not None:
        print(ctx.p23_alignment_report.alignment_state)
"""

from symbolu.mechanical.pipeline.p23_alignment.p23_schema import (
    # Version
    P23_VERSION,
    # Enums
    AlignmentState,
    # Dataclasses
    P23AlignmentReport,
    # Exceptions
    P23InvariantViolation,
    # Factory functions
    create_aligned_report,
    create_neutral_report,
    create_tension_report,
    create_contradiction_report,
    create_empty_report,
)

from symbolu.mechanical.pipeline.p23_alignment.p23_resolver import (
    AlignmentObserver,
    observe_alignment,
    access_forbidden_attribute,
    # Forbidden attribute sets
    FORBIDDEN_TEXT_ATTRS,
    FORBIDDEN_TOKEN_ATTRS,
    FORBIDDEN_SEMANTIC_ATTRS,
    FORBIDDEN_INTENT_ATTRS,
    FORBIDDEN_ONTOLOGY_ATTRS,
    FORBIDDEN_RAG_ATTRS,
    FORBIDDEN_HISTORY_ATTRS,
    FORBIDDEN_PREDICTION_ATTRS,
    ALL_FORBIDDEN_ATTRS,
    # Regime/Pressure tables
    REGIME_MAX_PRESSURE,
    PRESSURE_ORDER,
    # Tags
    TAG_ALIGNED,
    TAG_NEUTRAL,
    TAG_TENSION,
    TAG_CONTRADICTION,
    TAG_PRESSURE_EXCEEDS_DISCOURSE,
    TAG_PRESSURE_FORM_MISMATCH,
    TAG_HIGH_PRESSURE_DEFERRAL,
    TAG_CHAOTIC_MOTION,
    TAG_OSCILLATORY_MOTION,
    TAG_CONSERVATIVE_REGIME,
    TAG_BLOCKED_UPSTREAM,
)

from symbolu.mechanical.pipeline.p23_alignment.p23_integration import (
    # Singleton
    get_p23_observer,
    # Integration
    maybe_run_p23,
    run_p23,
    run_p23_directly,
    # Helpers
    is_p23_disabled,
    has_p23_report,
    get_p23_report,
    get_alignment_state,
    get_tension_score,
    get_alignment_tags,
    is_aligned,
    is_tension,
    get_p23_version,
)


__all__ = [
    # === Schema ===
    # Version
    "P23_VERSION",
    # Enums
    "AlignmentState",
    # Dataclasses
    "P23AlignmentReport",
    # Exceptions
    "P23InvariantViolation",
    # Factory functions
    "create_aligned_report",
    "create_neutral_report",
    "create_tension_report",
    "create_contradiction_report",
    "create_empty_report",
    # === Resolver ===
    "AlignmentObserver",
    "observe_alignment",
    "access_forbidden_attribute",
    # Forbidden attribute sets
    "FORBIDDEN_TEXT_ATTRS",
    "FORBIDDEN_TOKEN_ATTRS",
    "FORBIDDEN_SEMANTIC_ATTRS",
    "FORBIDDEN_INTENT_ATTRS",
    "FORBIDDEN_ONTOLOGY_ATTRS",
    "FORBIDDEN_RAG_ATTRS",
    "FORBIDDEN_HISTORY_ATTRS",
    "FORBIDDEN_PREDICTION_ATTRS",
    "ALL_FORBIDDEN_ATTRS",
    # Regime/Pressure tables
    "REGIME_MAX_PRESSURE",
    "PRESSURE_ORDER",
    # Tags
    "TAG_ALIGNED",
    "TAG_NEUTRAL",
    "TAG_TENSION",
    "TAG_CONTRADICTION",
    "TAG_PRESSURE_EXCEEDS_DISCOURSE",
    "TAG_PRESSURE_FORM_MISMATCH",
    "TAG_HIGH_PRESSURE_DEFERRAL",
    "TAG_CHAOTIC_MOTION",
    "TAG_OSCILLATORY_MOTION",
    "TAG_CONSERVATIVE_REGIME",
    "TAG_BLOCKED_UPSTREAM",
    # === Integration ===
    # Singleton
    "get_p23_observer",
    # Integration
    "maybe_run_p23",
    "run_p23",
    "run_p23_directly",
    # Helpers
    "is_p23_disabled",
    "has_p23_report",
    "get_p23_report",
    "get_alignment_state",
    "get_tension_score",
    "get_alignment_tags",
    "is_aligned",
    "is_tension",
    "get_p23_version",
]
