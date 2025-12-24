"""
P41 Mapper - Coherence-Regime Scenario Mapping Logic

Implements the deterministic mapping rules for Phase 41.
Translates coherence, drift, and alignment signals into scenario regime labels.

MAPPING RULES (Applied in order):

Rule A - Stable Continuity:
    IF coherence_v3_quality >= 0.75
    AND alignment_score >= 0.75
    AND drift_fusion_index <= 0.30
    -> "stable_continuity"

Rule B - Strained Transition:
    IF coherence_v3_quality >= 0.55
    AND alignment_score >= 0.45
    AND drift_fusion_index <= 0.55
    -> "strained_transition"

Rule C - Divergent Instability:
    IF alignment_score < 0.45
    OR drift_fusion_index >= 0.70
    -> "divergent_instability"

Fallback:
    -> "ambiguous_mixed"

CONFIDENCE FORMULA:
    confidence = clamp(
        0.4 * coherence_v3_quality
      + 0.4 * alignment_score
      + 0.2 * (1 - drift_fusion_index)
    )

INVARIANTS:
    - INV-P41-2: Deterministic (same inputs -> same outputs)
    - INV-P41-3: Scenario labels only (no probabilities, no forecasts)
    - INV-P41-4: Monotonic consistency (lower coherence/alignment cannot yield "better" regimes)
    - INV-P41-5: Absence-safe (missing inputs degrade confidence, never improve)
"""

from typing import List, Optional, Tuple

from symbolu.mechanical.pipeline.p41_scenario_regime_mapper.p41_schema import (
    ScenarioRegime,
    ScenarioRegimeMap,
    # Thresholds
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
    # Signal tags
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
    # Factory
    create_scenario_regime_map,
)


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================


def clamp(value: float, min_val: float = 0.0, max_val: float = 1.0) -> float:
    """
    Clamp a value to the specified range.

    Args:
        value: The value to clamp
        min_val: Minimum bound (default 0.0)
        max_val: Maximum bound (default 1.0)

    Returns:
        Clamped value
    """
    return max(min_val, min(max_val, value))


def safe_get(
    value: Optional[float],
    default: float,
    absence_penalty: bool = False,
) -> Tuple[float, bool]:
    """
    Safely extract a float value with optional absence penalty tracking.

    INV-P41-5: Missing inputs should degrade confidence, not improve it.

    Args:
        value: The optional float value
        default: Default value if None
        absence_penalty: Whether to track absence

    Returns:
        Tuple of (clamped value, was_absent flag)
    """
    if value is None:
        return (clamp(default), True)
    return (clamp(value), False)


# =============================================================================
# SIGNAL GENERATION
# =============================================================================


def generate_supporting_signals(
    coherence_v3_quality: float,
    alignment_score: float,
    drift_fusion_index: float,
    has_absence: bool = False,
) -> Tuple[str, ...]:
    """
    Generate supporting signal tags based on input values.

    Only produces string tags - no interpretation text, no reasoning chains.

    Args:
        coherence_v3_quality: Coherence quality [0.0, 1.0]
        alignment_score: Alignment score [0.0, 1.0]
        drift_fusion_index: Drift fusion index [0.0, 1.0]
        has_absence: Whether any inputs were absent

    Returns:
        Tuple of signal tag strings
    """
    signals: List[str] = []

    # Coherence signals
    if coherence_v3_quality >= STABLE_COHERENCE_THRESHOLD:
        signals.append(SIGNAL_HIGH_COHERENCE)
    elif coherence_v3_quality >= STRAINED_COHERENCE_THRESHOLD:
        signals.append(SIGNAL_MODERATE_COHERENCE)
    else:
        signals.append(SIGNAL_LOW_COHERENCE)

    # Alignment signals
    if alignment_score >= STABLE_ALIGNMENT_THRESHOLD:
        signals.append(SIGNAL_HIGH_ALIGNMENT)
    elif alignment_score >= STRAINED_ALIGNMENT_THRESHOLD:
        signals.append(SIGNAL_MODERATE_ALIGNMENT)
    else:
        signals.append(SIGNAL_LOW_ALIGNMENT)
        signals.append(SIGNAL_HORIZON_FRAGMENTATION)

    # Drift signals
    if drift_fusion_index <= STABLE_DRIFT_MAX_THRESHOLD:
        signals.append(SIGNAL_LOW_DRIFT)
    elif drift_fusion_index >= DIVERGENT_DRIFT_THRESHOLD:
        signals.append(SIGNAL_HIGH_DRIFT)
    else:
        signals.append(SIGNAL_MODERATE_DRIFT)

    # Quality penalty detection
    if coherence_v3_quality < STRAINED_COHERENCE_THRESHOLD:
        signals.append(SIGNAL_QUALITY_PENALTY_ACTIVE)

    # Absence penalty
    if has_absence:
        signals.append(SIGNAL_ABSENCE_PENALTY)

    return tuple(signals)


# =============================================================================
# MAPPING RULES
# =============================================================================


def apply_rule_a_stable_continuity(
    coherence_v3_quality: float,
    alignment_score: float,
    drift_fusion_index: float,
) -> bool:
    """
    Rule A - Stable Continuity check.

    IF coherence_v3_quality >= 0.75
    AND alignment_score >= 0.75
    AND drift_fusion_index <= 0.30
    -> True

    Args:
        coherence_v3_quality: Coherence quality [0.0, 1.0]
        alignment_score: Alignment score [0.0, 1.0]
        drift_fusion_index: Drift fusion index [0.0, 1.0]

    Returns:
        True if rule matches
    """
    return (
        coherence_v3_quality >= STABLE_COHERENCE_THRESHOLD
        and alignment_score >= STABLE_ALIGNMENT_THRESHOLD
        and drift_fusion_index <= STABLE_DRIFT_MAX_THRESHOLD
    )


def apply_rule_b_strained_transition(
    coherence_v3_quality: float,
    alignment_score: float,
    drift_fusion_index: float,
) -> bool:
    """
    Rule B - Strained Transition check.

    IF coherence_v3_quality >= 0.55
    AND alignment_score >= 0.45
    AND drift_fusion_index <= 0.55
    -> True

    Args:
        coherence_v3_quality: Coherence quality [0.0, 1.0]
        alignment_score: Alignment score [0.0, 1.0]
        drift_fusion_index: Drift fusion index [0.0, 1.0]

    Returns:
        True if rule matches
    """
    return (
        coherence_v3_quality >= STRAINED_COHERENCE_THRESHOLD
        and alignment_score >= STRAINED_ALIGNMENT_THRESHOLD
        and drift_fusion_index <= STRAINED_DRIFT_MAX_THRESHOLD
    )


def apply_rule_c_divergent_instability(
    alignment_score: float,
    drift_fusion_index: float,
) -> bool:
    """
    Rule C - Divergent Instability check.

    IF alignment_score < 0.45
    OR drift_fusion_index >= 0.70
    -> True

    Args:
        alignment_score: Alignment score [0.0, 1.0]
        drift_fusion_index: Drift fusion index [0.0, 1.0]

    Returns:
        True if rule matches
    """
    return (
        alignment_score < DIVERGENT_ALIGNMENT_THRESHOLD
        or drift_fusion_index >= DIVERGENT_DRIFT_THRESHOLD
    )


def determine_scenario_regime(
    coherence_v3_quality: float,
    alignment_score: float,
    drift_fusion_index: float,
) -> ScenarioRegime:
    """
    Apply mapping rules in order to determine scenario regime.

    Rules are applied in strict order:
    1. Rule A (stable_continuity)
    2. Rule B (strained_transition)
    3. Rule C (divergent_instability)
    4. Fallback (ambiguous_mixed)

    INV-P41-4: Monotonic consistency is enforced by the ordered rules.
    Lower coherence/alignment cannot yield "better" regimes because
    Rule A has stricter thresholds than Rule B.

    Args:
        coherence_v3_quality: Coherence quality [0.0, 1.0]
        alignment_score: Alignment score [0.0, 1.0]
        drift_fusion_index: Drift fusion index [0.0, 1.0]

    Returns:
        Scenario regime classification
    """
    # Rule A - Stable Continuity (strictest)
    if apply_rule_a_stable_continuity(
        coherence_v3_quality, alignment_score, drift_fusion_index
    ):
        return "stable_continuity"

    # Rule B - Strained Transition
    if apply_rule_b_strained_transition(
        coherence_v3_quality, alignment_score, drift_fusion_index
    ):
        return "strained_transition"

    # Rule C - Divergent Instability
    if apply_rule_c_divergent_instability(alignment_score, drift_fusion_index):
        return "divergent_instability"

    # Fallback - Ambiguous Mixed
    return "ambiguous_mixed"


# =============================================================================
# CONFIDENCE CALCULATION
# =============================================================================


def compute_confidence(
    coherence_v3_quality: float,
    alignment_score: float,
    drift_fusion_index: float,
) -> float:
    """
    Compute confidence score using weighted formula.

    confidence = clamp(
        0.4 * coherence_v3_quality
      + 0.4 * alignment_score
      + 0.2 * (1 - drift_fusion_index)
    )

    INV-P41-5: The formula uses (1 - drift) so higher drift reduces confidence.

    Args:
        coherence_v3_quality: Coherence quality [0.0, 1.0]
        alignment_score: Alignment score [0.0, 1.0]
        drift_fusion_index: Drift fusion index [0.0, 1.0]

    Returns:
        Confidence score [0.0, 1.0]
    """
    stability_component = 1.0 - drift_fusion_index

    confidence = (
        CONFIDENCE_WEIGHT_COHERENCE * coherence_v3_quality
        + CONFIDENCE_WEIGHT_ALIGNMENT * alignment_score
        + CONFIDENCE_WEIGHT_STABILITY * stability_component
    )

    return clamp(confidence)


# =============================================================================
# MAIN RESOLVER
# =============================================================================


def resolve_scenario_regime(
    coherence_v3_quality: Optional[float] = None,
    alignment_score: Optional[float] = None,
    drift_fusion_index: Optional[float] = None,
) -> Optional[ScenarioRegimeMap]:
    """
    Main resolver - maps signals to scenario regime classification.

    This function is deterministic: same inputs always produce same outputs.
    (INV-P41-2)

    Missing inputs are handled with absence-safe defaults:
    - coherence_v3_quality: defaults to 0.5 (neutral)
    - alignment_score: defaults to 0.5 (neutral)
    - drift_fusion_index: defaults to 0.5 (neutral)

    These defaults ensure that missing inputs cannot inflate the regime
    classification to "better" regimes. (INV-P41-5)

    Args:
        coherence_v3_quality: P12 coherence v3 quality [0.0, 1.0]
        alignment_score: P40 alignment score [0.0, 1.0]
        drift_fusion_index: P19 drift fusion index [0.0, 1.0]

    Returns:
        ScenarioRegimeMap if computation succeeds, None if all inputs missing
    """
    # Track absence for penalty signal
    has_absence = False

    # INV-P41-5: Default to neutral values (0.5) for missing inputs
    # This ensures absence cannot improve the classification
    cq, cq_absent = safe_get(coherence_v3_quality, 0.5)
    al, al_absent = safe_get(alignment_score, 0.5)
    dfi, dfi_absent = safe_get(drift_fusion_index, 0.5)

    has_absence = cq_absent or al_absent or dfi_absent

    # If ALL inputs are missing, return None (graceful degradation)
    if cq_absent and al_absent and dfi_absent:
        return None

    # Step 1 - Signal Normalization (clamping already done in safe_get)
    # No rescaling beyond clamping [0.0, 1.0]

    # Step 2 - Scenario Mapping Rules
    scenario_regime = determine_scenario_regime(cq, al, dfi)

    # Step 3 - Confidence Score
    confidence = compute_confidence(cq, al, dfi)

    # Apply absence penalty to confidence
    if has_absence:
        # Reduce confidence by 10% for each missing input
        absence_count = sum([cq_absent, al_absent, dfi_absent])
        penalty = 0.10 * absence_count
        confidence = clamp(confidence - penalty)

    # Step 4 - Supporting Signals
    supporting_signals = generate_supporting_signals(cq, al, dfi, has_absence)

    # Create and return the map
    return create_scenario_regime_map(
        scenario_regime=scenario_regime,
        confidence=confidence,
        supporting_signals=supporting_signals,
        coherence_v3_quality=cq,
        alignment_score=al,
        drift_fusion_index=dfi,
        debug={
            "input_cq_absent": cq_absent,
            "input_al_absent": al_absent,
            "input_dfi_absent": dfi_absent,
            "absence_penalty_applied": has_absence,
        },
    )


# Public exports
__all__ = [
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
]
