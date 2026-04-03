"""
Phase 41 - Coherence-Regime Scenario Mapper

This phase translates numeric coherence and alignment signals into a
scenario classification that later phases (42-44) may simulate.

This phase is:
    - Read-only
    - Observer-only
    - Non-authoritative
    - Deterministic
    - Zero-LLM

PURPOSE:
    Phase 41 answers one question only:
    "Given coherence, drift, and horizon alignment, which scenario regimes are plausible?"

    It maps signals -> scenario labels, NOT decisions.

    It does NOT:
        - Predict outcomes
        - Decide which scenario is correct
        - Gate behavior
        - Influence discourse or tone

    It IS a symbolic categorization layer.

INPUTS (Read-Only):
    Phase 41 MAY read:
        - Phase 10 Coherence v3 score
        - Phase 12 Coherence v3 Quality
        - Phase 19 Drift Fusion Report
        - Phase 40 Cross-Horizon Alignment

    Phase 41 MUST NOT read:
        - Raw user text
        - Semantics, intent, discourse, lexical frames
        - Acoustic / vrtti / kosha data
        - Any governance or eligibility phase (>=50)

OUTPUTS:
    ScenarioRegimeMap - frozen dataclass with:
        - scenario_regime: "stable_continuity" | "strained_transition" |
                           "divergent_instability" | "ambiguous_mixed"
        - confidence: float [0.0, 1.0]
        - supporting_signals: tuple[str]
        - observer_only: Literal[True]

INVARIANTS:
    - INV-P41-1: Observer-only (no influence on regimes, discourse, routing, or action)
    - INV-P41-2: Deterministic (same inputs -> same outputs)
    - INV-P41-3: Scenario labels only (no probabilities, no forecasts, no optimization)
    - INV-P41-4: Monotonic consistency (lower coherence / alignment cannot yield "better" regimes)
    - INV-P41-5: Absence-safe (missing optional inputs degrade confidence, never improve it)

Usage:
    from symbolu_core.mechanical.pipeline.p41_scenario_regime_mapper import (
        maybe_run_p41,
        run_p41_directly,
        ScenarioRegimeMap,
    )

    # In pipeline after P40:
    maybe_run_p41(ctx)

    # Or run directly for testing:
    result = run_p41_directly(
        coherence_v3_quality=0.8,
        alignment_score=0.75,
        drift_fusion_index=0.2,
    )
    print(result.scenario_regime)  # "stable_continuity"
"""

from symbolu_core.mechanical.pipeline.p41_scenario_regime_mapper.p41_schema import (
    # Version
    P41_VERSION,
    # Type Aliases
    ScenarioRegime,
    # Constants - Mapping Thresholds
    STABLE_COHERENCE_THRESHOLD,
    STABLE_ALIGNMENT_THRESHOLD,
    STABLE_DRIFT_MAX_THRESHOLD,
    STRAINED_COHERENCE_THRESHOLD,
    STRAINED_ALIGNMENT_THRESHOLD,
    STRAINED_DRIFT_MAX_THRESHOLD,
    DIVERGENT_ALIGNMENT_THRESHOLD,
    DIVERGENT_DRIFT_THRESHOLD,
    # Confidence weights
    CONFIDENCE_WEIGHT_COHERENCE,
    CONFIDENCE_WEIGHT_ALIGNMENT,
    CONFIDENCE_WEIGHT_STABILITY,
    # Signal Tags
    SIGNAL_HIGH_COHERENCE,
    SIGNAL_LOW_COHERENCE,
    SIGNAL_MODERATE_COHERENCE,
    SIGNAL_HIGH_ALIGNMENT,
    SIGNAL_LOW_ALIGNMENT,
    SIGNAL_MODERATE_ALIGNMENT,
    SIGNAL_LOW_DRIFT,
    SIGNAL_HIGH_DRIFT,
    SIGNAL_MODERATE_DRIFT,
    SIGNAL_HORIZON_FRAGMENTATION,
    SIGNAL_QUALITY_PENALTY_ACTIVE,
    SIGNAL_ABSENCE_PENALTY,
    # Dataclasses
    ScenarioRegimeMap,
    # Factory
    create_scenario_regime_map,
)

from symbolu_core.mechanical.pipeline.p41_scenario_regime_mapper.p41_mapper import (
    # Utilities
    clamp,
    safe_get,
    # Signal generation
    generate_supporting_signals,
    # Mapping rules
    apply_rule_a_stable_continuity,
    apply_rule_b_strained_transition,
    apply_rule_c_divergent_instability,
    determine_scenario_regime,
    # Confidence
    compute_confidence,
    # Main resolver
    resolve_scenario_regime,
)

from symbolu_core.mechanical.pipeline.p41_scenario_regime_mapper.p41_integration import (
    # Integration
    maybe_run_p41,
    run_p41_directly,
    # Helpers
    is_p41_disabled,
    has_p41_scenario_map,
    get_p41_scenario_map,
    get_scenario_regime,
    get_regime_confidence,
    is_stable_regime,
    is_divergent_regime,
    get_p41_version,
)


__all__ = [
    # Version
    "P41_VERSION",
    # Type Aliases
    "ScenarioRegime",
    # Constants - Mapping Thresholds
    "STABLE_COHERENCE_THRESHOLD",
    "STABLE_ALIGNMENT_THRESHOLD",
    "STABLE_DRIFT_MAX_THRESHOLD",
    "STRAINED_COHERENCE_THRESHOLD",
    "STRAINED_ALIGNMENT_THRESHOLD",
    "STRAINED_DRIFT_MAX_THRESHOLD",
    "DIVERGENT_ALIGNMENT_THRESHOLD",
    "DIVERGENT_DRIFT_THRESHOLD",
    # Confidence weights
    "CONFIDENCE_WEIGHT_COHERENCE",
    "CONFIDENCE_WEIGHT_ALIGNMENT",
    "CONFIDENCE_WEIGHT_STABILITY",
    # Signal Tags
    "SIGNAL_HIGH_COHERENCE",
    "SIGNAL_LOW_COHERENCE",
    "SIGNAL_MODERATE_COHERENCE",
    "SIGNAL_HIGH_ALIGNMENT",
    "SIGNAL_LOW_ALIGNMENT",
    "SIGNAL_MODERATE_ALIGNMENT",
    "SIGNAL_LOW_DRIFT",
    "SIGNAL_HIGH_DRIFT",
    "SIGNAL_MODERATE_DRIFT",
    "SIGNAL_HORIZON_FRAGMENTATION",
    "SIGNAL_QUALITY_PENALTY_ACTIVE",
    "SIGNAL_ABSENCE_PENALTY",
    # Dataclasses
    "ScenarioRegimeMap",
    # Factory
    "create_scenario_regime_map",
    # Utilities
    "clamp",
    "safe_get",
    # Signal generation
    "generate_supporting_signals",
    # Mapping rules
    "apply_rule_a_stable_continuity",
    "apply_rule_b_strained_transition",
    "apply_rule_c_divergent_instability",
    "determine_scenario_regime",
    # Confidence
    "compute_confidence",
    # Main resolver
    "resolve_scenario_regime",
    # Integration
    "maybe_run_p41",
    "run_p41_directly",
    # Helpers
    "is_p41_disabled",
    "has_p41_scenario_map",
    "get_p41_scenario_map",
    "get_scenario_regime",
    "get_regime_confidence",
    "is_stable_regime",
    "is_divergent_regime",
    "get_p41_version",
]
