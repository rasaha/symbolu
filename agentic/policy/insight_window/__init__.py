"""
Phase 32 - Insight Window Gating

INTEGRATION PATH: ACTIVE / PIPELINE-NATIVE (Policy Phase P0)

    This package is the ACTIVE insight window system used by the
    P32 pipeline integration step (p32_integration.py → maybe_run_p32()).

    It produces InsightWindowEnvelope, which is stored on PipelineContext.p32
    and consumed by downstream pipeline observers.

    A SEPARATE insight window system exists at the module level
    (insight_window_gating.py → compute_insight_window()), which
    serves the policy engine path (policy_engine.py). The two systems:
    - Use different formulas and different schemas
    - Serve different callers (pipeline P32 step vs policy engine)
    - Are both actively used

    Consolidation is planned for a future phase. Until then, this
    package is the canonical pipeline-facing insight window system.

Determines whether deeper insights may be surfaced, without triggering
action, regime change, or delivery decisions.

This module produces a single numeric gate signal and a reasoned explanation.

WHAT P32 DOES:
- Decides: "Is the system allowed to surface deeper insight right now?"
- Produces: InsightWindowEnvelope with is_open, insight_depth, reason_codes

WHAT P32 DOES NOT DO:
- Decide what insight to show
- Decide how to phrase it
- Decide whether to act
- Decide whether to advise
- Trigger regime changes (P6)
- Select discourse acts (P7)
- Modify semantics or lexical frames (P8-P9)
- Influence persona, DHA, renderer
- Trigger actions or agent handoff

CRITICAL INVARIANTS:
- INV-P32-1: Insight gating never opens due to observers
- INV-P32-2: Gate monotonicity enforced (can only close, never open)
- INV-P32-3: No upstream influence
- INV-P32-4: Deterministic behavior
- INV-P32-5: Envelope is advisory only

CORE FORMULA (LOCKED):
    raw_depth =
        0.40 * coherence_v3_quality
      + 0.30 * ucf_score
      + 0.20 * schema_stability
      + 0.10 * (1 - drift_fusion_index)

MONOTONIC PENALTIES:
    - If temporal_entropy_diff > 0.6 → multiply by 0.85
    - If coherence_v3_quality < 0.45 → multiply by 0.80
    - If acoustic_alignment_score < 0.4 → multiply by 0.95 (observer-only)

GATE RULE:
    is_open = insight_depth >= 0.55

Usage:
    from agentic.policy.insight_window import (
        InsightGatingEngine,
        get_insight_gating_engine,
        InsightWindowEnvelope,
    )

    # Via engine
    engine = get_insight_gating_engine()
    envelope = engine.compute(ctx)

    if envelope.is_open:
        # Insight window is open
        print(f"Depth: {envelope.insight_depth}")
    else:
        print(f"Closed: {envelope.gating_reason_codes}")
"""

from .insight_envelope import (
    # Version
    P32_VERSION,
    # Enums
    ConfidenceBand,
    # Constants
    ALLOWED_REASON_CODES,
    INSIGHT_GATE_THRESHOLD,
    CONFIDENCE_HIGH_THRESHOLD,
    CONFIDENCE_LOW_THRESHOLD,
    # Dataclasses
    InsightWindowEnvelope,
    # Helpers
    create_envelope,
    create_closed_envelope,
)

from .insight_gating_formula import (
    # Weights (LOCKED)
    W_COHERENCE_V3_QUALITY,
    W_UCF_SCORE,
    W_SCHEMA_STABILITY,
    W_DRIFT_INVERSE,
    # Thresholds (LOCKED)
    TEMPORAL_ENTROPY_THRESHOLD,
    TEMPORAL_ENTROPY_PENALTY,
    COHERENCE_QUALITY_THRESHOLD,
    COHERENCE_QUALITY_PENALTY,
    ACOUSTIC_ALIGNMENT_THRESHOLD,
    ACOUSTIC_ALIGNMENT_PENALTY,
    NEUTRAL_DEFAULT,
    # Result type
    FormulaResult,
    # Functions
    compute_raw_depth,
    apply_temporal_entropy_penalty,
    apply_coherence_quality_penalty,
    apply_acoustic_penalty,
    compute_insight_depth,
)

from .insight_gating_engine import (
    InsightGatingEngine,
    get_insight_gating_engine,
)


__all__ = [
    # Version
    "P32_VERSION",
    # Enums
    "ConfidenceBand",
    # Constants - Envelope
    "ALLOWED_REASON_CODES",
    "INSIGHT_GATE_THRESHOLD",
    "CONFIDENCE_HIGH_THRESHOLD",
    "CONFIDENCE_LOW_THRESHOLD",
    # Constants - Formula Weights (LOCKED)
    "W_COHERENCE_V3_QUALITY",
    "W_UCF_SCORE",
    "W_SCHEMA_STABILITY",
    "W_DRIFT_INVERSE",
    # Constants - Thresholds (LOCKED)
    "TEMPORAL_ENTROPY_THRESHOLD",
    "TEMPORAL_ENTROPY_PENALTY",
    "COHERENCE_QUALITY_THRESHOLD",
    "COHERENCE_QUALITY_PENALTY",
    "ACOUSTIC_ALIGNMENT_THRESHOLD",
    "ACOUSTIC_ALIGNMENT_PENALTY",
    "NEUTRAL_DEFAULT",
    # Dataclasses
    "InsightWindowEnvelope",
    "FormulaResult",
    # Helpers
    "create_envelope",
    "create_closed_envelope",
    # Formula functions
    "compute_raw_depth",
    "apply_temporal_entropy_penalty",
    "apply_coherence_quality_penalty",
    "apply_acoustic_penalty",
    "compute_insight_depth",
    # Engine
    "InsightGatingEngine",
    "get_insight_gating_engine",
]

__version__ = P32_VERSION

# Integration path marker — identifies which insight window system this is
_INSIGHT_WINDOW_PATH = "pipeline_native"

# Policy Phase P2: Canonical status metadata for operational clarity.
# Queryable by tooling, simulation, and migration scripts.
INSIGHT_WINDOW_STATUS = {
    "path": "pipeline_native",
    "canonical": True,
    "schema": "InsightWindowEnvelope",
    "caller": "p32_integration.py::maybe_run_p32",
    "output_key": "PipelineContext.p32",
    "status": "active",
    "consolidation_target": True,
    "version": "1.0",
    "notes": (
        "This is the pipeline-native insight window system (P32). "
        "A parallel policy-engine-facing system exists in insight_window_gating.py. "
        "Both are active; consolidation is planned for a future phase."
    ),
}
