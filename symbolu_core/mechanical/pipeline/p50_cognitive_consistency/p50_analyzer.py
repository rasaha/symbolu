"""
Phase 50: Cognitive Consistency Regression Analyzer

Core computation engine with deterministic formula logic.

Phase 50 answers:
    "Is the system contradicting itself compared to its own prior cognitive state?"

This is not semantic contradiction detection.
It is self-consistency regression only.

INPUTS (Read-Only):
    Phase 50 MAY read:
        - P6 RegimeEnvelope
        - P7 DiscourseEnvelope
        - P8 SemanticFrame
        - P9 LexicalFrame
        - P10-P14 (for trace continuity only, not evaluation)
        - P16 Regression Guard history
        - P18 Temporal Entropy Differential
        - P19 Drift Fusion Report
        - P20 Unified Cognitive Snapshot
        - Historical snapshots (previous turns)

    Phase 50 MUST NOT read:
        - Raw user text
        - Acoustic content
        - Ontology interpretation
        - Any future forecast (P38+)
        - Any observer-only acoustic reports (P22-P24)

INVARIANTS:
    INV-P50-A1: P50 cannot modify any upstream phase output
    INV-P50-A2: P50 cannot gate any action or delivery
    INV-P50-A3: P50 cannot be read by P6-P21
    INV-P50-A4: P50 output is observer-only
    INV-P50-D1: Same history + same input -> same report (bitwise)
    INV-P50-D2: No randomness, no thresholds learned at runtime
    INV-P50-S1: No semantic reinterpretation
    INV-P50-S2: No acoustic interpretation
    INV-P50-S3: No persona influence
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from .p50_schema import (
    CognitiveConsistencyReport,
    create_cognitive_consistency_report,
    W_REGIME_STABILITY,
    W_DISCOURSE_CONTINUITY,
    W_SEMANTIC_PRESERVATION,
    W_LEXICAL_POLARITY,
    W_DRIFT_ENTROPY,
)


# ============================================================================
# CONTRADICTION DETECTION RULES
# ============================================================================

# Regime transition contradiction table
# Maps (previous_regime, current_regime) -> contradiction flag
# Only contradictory transitions are listed here
CONTRADICTORY_REGIME_TRANSITIONS = frozenset([
    # HOLD -> aggressive modes is contradictory
    ("HOLD", "INFORM"),
    ("HOLD", "REFLECT"),
    # DE_ESCALATE -> non-deescalating is contradictory
    ("DE_ESCALATE", "INFORM"),
    # STABILIZE -> volatility-inducing is contradictory
    ("STABILIZE", "INFORM"),
])

# Discourse act contradiction table
CONTRADICTORY_DISCOURSE_TRANSITIONS = frozenset([
    # DEFERRAL -> active engagement is contradictory
    ("DEFERRAL", "INSTRUCTION"),
    ("DEFERRAL", "EXPLANATION"),
    # ACKNOWLEDGMENT -> directive is contradictory
    ("ACKNOWLEDGMENT", "INSTRUCTION"),
])


# ============================================================================
# CORE CONSISTENCY COMPUTATION
# ============================================================================


def _compute_regime_stability(
    current_regime: Optional[str],
    previous_regime: Optional[str],
) -> Tuple[float, List[str]]:
    """
    Compute regime stability score between current and previous state.

    INV-P50-D1: Deterministic - same inputs always produce same output.
    INV-P50-S1: No semantic reinterpretation - only structural comparison.

    Args:
        current_regime: Current regime string (e.g., "INFORM", "HOLD")
        previous_regime: Previous regime string

    Returns:
        Tuple of (stability_score [0.0, 1.0], list of contradiction flags)
    """
    contradictions = []

    # No history case - return neutral
    if previous_regime is None:
        return 1.0, []

    # No current regime - return neutral
    if current_regime is None:
        return 1.0, []

    # Same regime = stable
    if current_regime == previous_regime:
        return 1.0, []

    # Check for contradictory transition
    transition = (previous_regime, current_regime)
    if transition in CONTRADICTORY_REGIME_TRANSITIONS:
        contradictions.append(
            f"REGIME_CONTRADICTION: {previous_regime} -> {current_regime}"
        )
        return 0.0, contradictions

    # Different but not contradictory = partial stability
    return 0.6, []


def _compute_discourse_continuity(
    current_act: Optional[str],
    previous_act: Optional[str],
) -> Tuple[float, List[str]]:
    """
    Compute discourse act continuity score.

    INV-P50-D1: Deterministic.
    INV-P50-S1: No semantic reinterpretation.

    Args:
        current_act: Current discourse act string
        previous_act: Previous discourse act string

    Returns:
        Tuple of (continuity_score [0.0, 1.0], list of contradiction flags)
    """
    contradictions = []

    # No history case
    if previous_act is None:
        return 1.0, []

    if current_act is None:
        return 1.0, []

    # Same act = continuous
    if current_act == previous_act:
        return 1.0, []

    # Check for contradictory transition
    transition = (previous_act, current_act)
    if transition in CONTRADICTORY_DISCOURSE_TRANSITIONS:
        contradictions.append(
            f"DISCOURSE_CONTRADICTION: {previous_act} -> {current_act}"
        )
        return 0.0, contradictions

    # Different but not contradictory = partial continuity
    return 0.7, []


def _compute_semantic_preservation(
    current_slots: Optional[Dict[str, Any]],
    previous_slots: Optional[Dict[str, Any]],
) -> Tuple[float, List[str]]:
    """
    Compute semantic slot preservation score.

    Detects silent inversion where slots existed before but
    are now missing or have inverted values.

    INV-P50-D1: Deterministic.
    INV-P50-S1: No semantic reinterpretation - only presence/absence check.

    Args:
        current_slots: Current semantic slot dictionary
        previous_slots: Previous semantic slot dictionary

    Returns:
        Tuple of (preservation_score [0.0, 1.0], list of contradiction flags)
    """
    contradictions = []

    # No history case
    if previous_slots is None:
        return 1.0, []

    if current_slots is None:
        return 1.0, []

    if not previous_slots:
        return 1.0, []

    # Count preserved slots
    previous_keys = set(previous_slots.keys())
    current_keys = set(current_slots.keys())

    # Silent removal is suspicious
    removed_slots = previous_keys - current_keys
    if removed_slots:
        for slot in sorted(removed_slots):
            contradictions.append(f"SLOT_REMOVED: {slot}")

    # Calculate preservation ratio
    if len(previous_keys) == 0:
        return 1.0, contradictions

    preserved = len(previous_keys & current_keys)
    preservation_score = preserved / len(previous_keys)

    return preservation_score, contradictions


def _compute_lexical_polarity(
    current_polarity: Optional[float],
    previous_polarity: Optional[float],
) -> Tuple[float, List[str]]:
    """
    Compute lexical polarity reversal score.

    Detects when polarity (sentiment orientation) inverts significantly.

    INV-P50-D1: Deterministic.
    INV-P50-S1: No semantic reinterpretation.

    Args:
        current_polarity: Current polarity value [-1.0, 1.0]
        previous_polarity: Previous polarity value [-1.0, 1.0]

    Returns:
        Tuple of (polarity_score [0.0, 1.0], list of contradiction flags)
    """
    contradictions = []

    # No history case
    if previous_polarity is None:
        return 1.0, []

    if current_polarity is None:
        return 1.0, []

    # Calculate polarity change
    delta = current_polarity - previous_polarity

    # Significant reversal (crossing zero with magnitude)
    if previous_polarity > 0.3 and current_polarity < -0.3:
        contradictions.append(
            f"POLARITY_REVERSAL: {previous_polarity:.2f} -> {current_polarity:.2f}"
        )
        return 0.0, contradictions

    if previous_polarity < -0.3 and current_polarity > 0.3:
        contradictions.append(
            f"POLARITY_REVERSAL: {previous_polarity:.2f} -> {current_polarity:.2f}"
        )
        return 0.0, contradictions

    # Small change = stable
    if abs(delta) < 0.2:
        return 1.0, []

    # Moderate change
    return max(0.3, 1.0 - abs(delta)), []


def _compute_drift_entropy_agreement(
    drift_index: Optional[float],
    entropy_diff: Optional[float],
    entropy_volatility: Optional[float],
) -> Tuple[float, List[str]]:
    """
    Compute agreement between drift and entropy signals.

    When drift says "high instability" but entropy says "stable" (or vice versa),
    this indicates internal cognitive inconsistency.

    INV-P50-D1: Deterministic.
    INV-P50-S1: No semantic reinterpretation.

    Args:
        drift_index: Drift fusion index [0.0, 1.0] from P19
        entropy_diff: Temporal entropy differential from P18
        entropy_volatility: Temporal entropy volatility from P18

    Returns:
        Tuple of (agreement_score [0.0, 1.0], list of regression flags)
    """
    flags = []

    # Missing inputs
    if drift_index is None:
        return 1.0, []

    if entropy_volatility is None:
        return 1.0, []

    # Check for disagreement
    # High drift + low volatility = disagreement
    if drift_index > 0.65 and entropy_volatility < 0.30:
        flags.append("DRIFT_ENTROPY_DISAGREEMENT_HIGH")
        return 0.3, flags

    # Low drift + high volatility = disagreement
    if drift_index < 0.30 and entropy_volatility > 0.65:
        flags.append("DRIFT_ENTROPY_DISAGREEMENT_LOW")
        return 0.3, flags

    # Agreement
    agreement = 1.0 - abs(drift_index - entropy_volatility)
    return max(0.0, agreement), flags


def _compute_consistency_score(
    regime_stability: float,
    discourse_continuity: float,
    semantic_preservation: float,
    lexical_polarity: float,
    drift_entropy_agreement: float,
) -> float:
    """
    Compute final consistency score using deterministic weighted aggregation.

    INV-P50-D1: Deterministic - pure math, no randomness.
    INV-P50-D2: No thresholds learned at runtime - all weights are fixed.

    Formula:
        consistency_score = clamp(
            0.25 * R +  # Regime stability
            0.20 * D +  # Discourse continuity
            0.20 * S +  # Semantic preservation
            0.15 * L +  # Lexical polarity
            0.20 * E,   # Drift-entropy agreement
            0.0,
            1.0
        )

    Args:
        regime_stability: R [0.0, 1.0]
        discourse_continuity: D [0.0, 1.0]
        semantic_preservation: S [0.0, 1.0]
        lexical_polarity: L [0.0, 1.0]
        drift_entropy_agreement: E [0.0, 1.0]

    Returns:
        Consistency score in [0.0, 1.0]
    """
    R = regime_stability
    D = discourse_continuity
    S = semantic_preservation
    L = lexical_polarity
    E = drift_entropy_agreement

    # Weighted aggregation
    raw_score = (
        W_REGIME_STABILITY * R +
        W_DISCOURSE_CONTINUITY * D +
        W_SEMANTIC_PRESERVATION * S +
        W_LEXICAL_POLARITY * L +
        W_DRIFT_ENTROPY * E
    )

    # Clamp to [0.0, 1.0]
    return max(0.0, min(1.0, raw_score))


# ============================================================================
# ENTRY POINTS
# ============================================================================


def compute_cognitive_consistency(
    current_regime: Optional[str],
    previous_regime: Optional[str],
    current_discourse_act: Optional[str],
    previous_discourse_act: Optional[str],
    current_semantic_slots: Optional[Dict[str, Any]],
    previous_semantic_slots: Optional[Dict[str, Any]],
    current_polarity: Optional[float],
    previous_polarity: Optional[float],
    drift_index: Optional[float],
    entropy_diff: Optional[float],
    entropy_volatility: Optional[float],
) -> CognitiveConsistencyReport:
    """
    Compute cognitive consistency report from raw inputs.

    INV-P50-A4: Observer-only - creates report with observer_only=True.
    INV-P50-D1: Deterministic - same inputs always produce same output.
    INV-P50-S1: No semantic reinterpretation - structural comparison only.

    Args:
        current_regime: Current regime string
        previous_regime: Previous regime string
        current_discourse_act: Current discourse act string
        previous_discourse_act: Previous discourse act string
        current_semantic_slots: Current semantic slot dictionary
        previous_semantic_slots: Previous semantic slot dictionary
        current_polarity: Current lexical polarity [-1.0, 1.0]
        previous_polarity: Previous lexical polarity [-1.0, 1.0]
        drift_index: Drift fusion index [0.0, 1.0] from P19
        entropy_diff: Temporal entropy differential from P18
        entropy_volatility: Temporal entropy volatility from P18

    Returns:
        CognitiveConsistencyReport
    """
    all_contradictions: List[str] = []
    all_flags: List[str] = []

    # Compute individual factors
    regime_stability, regime_contradictions = _compute_regime_stability(
        current_regime, previous_regime
    )
    all_contradictions.extend(regime_contradictions)

    discourse_continuity, discourse_contradictions = _compute_discourse_continuity(
        current_discourse_act, previous_discourse_act
    )
    all_contradictions.extend(discourse_contradictions)

    semantic_preservation, semantic_contradictions = _compute_semantic_preservation(
        current_semantic_slots, previous_semantic_slots
    )
    all_contradictions.extend(semantic_contradictions)

    lexical_polarity, polarity_contradictions = _compute_lexical_polarity(
        current_polarity, previous_polarity
    )
    all_contradictions.extend(polarity_contradictions)

    drift_entropy_agreement, drift_flags = _compute_drift_entropy_agreement(
        drift_index, entropy_diff, entropy_volatility
    )
    all_flags.extend(drift_flags)

    # Compute final score
    consistency_score = _compute_consistency_score(
        regime_stability=regime_stability,
        discourse_continuity=discourse_continuity,
        semantic_preservation=semantic_preservation,
        lexical_polarity=lexical_polarity,
        drift_entropy_agreement=drift_entropy_agreement,
    )

    # Add low consistency flag if needed
    if consistency_score < 0.45:
        all_flags.append("LOW_CONSISTENCY_DETECTED")

    # Build debug info
    debug = {
        "inputs": {
            "current_regime": current_regime,
            "previous_regime": previous_regime,
            "current_discourse_act": current_discourse_act,
            "previous_discourse_act": previous_discourse_act,
            "has_current_slots": current_semantic_slots is not None,
            "has_previous_slots": previous_semantic_slots is not None,
            "current_polarity": current_polarity,
            "previous_polarity": previous_polarity,
            "drift_index": drift_index,
            "entropy_diff": entropy_diff,
            "entropy_volatility": entropy_volatility,
        },
        "factors": {
            "regime_stability": regime_stability,
            "discourse_continuity": discourse_continuity,
            "semantic_preservation": semantic_preservation,
            "lexical_polarity": lexical_polarity,
            "drift_entropy_agreement": drift_entropy_agreement,
        },
        "weights": {
            "W_REGIME_STABILITY": W_REGIME_STABILITY,
            "W_DISCOURSE_CONTINUITY": W_DISCOURSE_CONTINUITY,
            "W_SEMANTIC_PRESERVATION": W_SEMANTIC_PRESERVATION,
            "W_LEXICAL_POLARITY": W_LEXICAL_POLARITY,
            "W_DRIFT_ENTROPY": W_DRIFT_ENTROPY,
        },
    }

    return create_cognitive_consistency_report(
        consistency_score=consistency_score,
        detected_contradictions=tuple(sorted(all_contradictions)),
        regression_flags=tuple(sorted(all_flags)),
        debug=debug,
    )


def run_p50_directly(
    p6_regime: Any,
    p7_discourse: Any,
    p8_semantic_frame: Any,
    p9_lexical_frame: Any,
    p18_entropy: Any,
    p19_drift: Any,
    previous_p6_regime: Any = None,
    previous_p7_discourse: Any = None,
    previous_p8_semantic_frame: Any = None,
    previous_p9_lexical_frame: Any = None,
) -> Optional[CognitiveConsistencyReport]:
    """
    Run P50 cognitive consistency regression directly with upstream reports.

    This is the direct computation entry point for testing and
    bypassing context extraction.

    INV-P50-A1: We read but NEVER modify upstream outputs.
    INV-P50-D1: Same inputs always produce same output.

    Args:
        p6_regime: Current P6 RegimeEnvelope
        p7_discourse: Current P7 DiscourseEnvelope
        p8_semantic_frame: Current P8 SemanticFrame
        p9_lexical_frame: Current P9 LexicalFrame
        p18_entropy: Current P18 temporal entropy report
        p19_drift: Current P19 drift fusion report
        previous_p6_regime: Previous P6 RegimeEnvelope
        previous_p7_discourse: Previous P7 DiscourseEnvelope
        previous_p8_semantic_frame: Previous P8 SemanticFrame
        previous_p9_lexical_frame: Previous P9 LexicalFrame

    Returns:
        CognitiveConsistencyReport if computation succeeds, None otherwise
    """
    # Extract current regime
    current_regime = None
    if p6_regime is not None:
        regime = getattr(p6_regime, "regime", None)
        if regime is not None:
            current_regime = regime.value if hasattr(regime, "value") else str(regime)

    # Extract previous regime
    previous_regime = None
    if previous_p6_regime is not None:
        regime = getattr(previous_p6_regime, "regime", None)
        if regime is not None:
            previous_regime = regime.value if hasattr(regime, "value") else str(regime)

    # Extract current discourse act
    current_discourse_act = None
    if p7_discourse is not None:
        act = getattr(p7_discourse, "act", None)
        if act is not None:
            current_discourse_act = act.value if hasattr(act, "value") else str(act)

    # Extract previous discourse act
    previous_discourse_act = None
    if previous_p7_discourse is not None:
        act = getattr(previous_p7_discourse, "act", None)
        if act is not None:
            previous_discourse_act = act.value if hasattr(act, "value") else str(act)

    # Extract current semantic slots
    current_semantic_slots = None
    if p8_semantic_frame is not None:
        slots = getattr(p8_semantic_frame, "slots", None)
        if slots is not None:
            current_semantic_slots = dict(slots) if isinstance(slots, dict) else None

    # Extract previous semantic slots
    previous_semantic_slots = None
    if previous_p8_semantic_frame is not None:
        slots = getattr(previous_p8_semantic_frame, "slots", None)
        if slots is not None:
            previous_semantic_slots = dict(slots) if isinstance(slots, dict) else None

    # Extract lexical polarity (from lexical frame if available)
    current_polarity = None
    if p9_lexical_frame is not None:
        polarity = getattr(p9_lexical_frame, "polarity", None)
        if polarity is not None:
            current_polarity = float(polarity)

    previous_polarity = None
    if previous_p9_lexical_frame is not None:
        polarity = getattr(previous_p9_lexical_frame, "polarity", None)
        if polarity is not None:
            previous_polarity = float(polarity)

    # Extract drift index from P19
    drift_index = None
    if p19_drift is not None:
        drift_index = getattr(p19_drift, "drift_fusion_index", None)

    # Extract entropy values from P18
    entropy_diff = None
    entropy_volatility = None
    if p18_entropy is not None:
        entropy_diff = getattr(p18_entropy, "delta_entropy", None)
        # Try to get volatility from volatility_band
        volatility_band = getattr(p18_entropy, "volatility_band", None)
        if volatility_band is not None:
            band_value = volatility_band.value if hasattr(volatility_band, "value") else str(volatility_band)
            # Map band to numeric value
            if band_value == "LOW":
                entropy_volatility = 0.2
            elif band_value == "MED":
                entropy_volatility = 0.5
            elif band_value == "HIGH":
                entropy_volatility = 0.8
            else:
                entropy_volatility = 0.5  # Default for UNKNOWN

    # Compute consistency
    return compute_cognitive_consistency(
        current_regime=current_regime,
        previous_regime=previous_regime,
        current_discourse_act=current_discourse_act,
        previous_discourse_act=previous_discourse_act,
        current_semantic_slots=current_semantic_slots,
        previous_semantic_slots=previous_semantic_slots,
        current_polarity=current_polarity,
        previous_polarity=previous_polarity,
        drift_index=drift_index,
        entropy_diff=entropy_diff,
        entropy_volatility=entropy_volatility,
    )


# Public exports
__all__ = [
    "compute_cognitive_consistency",
    "run_p50_directly",
]
