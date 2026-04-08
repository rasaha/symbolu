"""
Semantic Integrity Formula v1.0 + Cognitive Drift Metric v3 - Phase 17

Deterministic, zero-LLM layer that measures:
  • semantic_integrity_score ∈ [0.0, 1.0]
      – How coherent and self-consistent the symbolic/practical/mirror layers are
        within a single turn and across recent turns.
  • cognitive_drift_v3 ∈ [0.0, 1.0]
      – How much the system's semantic "center of gravity" is drifting over time,
        combining structural, topical, and mapper/intent shifts.

CRITICAL:
    - Zero-LLM: Purely rule-based, math + structural comparisons
    - Non-invasive: NO changes to routing, TTOR, MLCR, mappers, Fusion, DHA, Renderer
    - Observation-only: Outputs used only for diagnostics & analytics (no behavior change)
    - Backward-compatible: All existing tests remain green
"""

from dataclasses import dataclass
from typing import List, Dict, Optional, Any
import statistics


@dataclass
class SemanticIntegritySnapshot:
    """
    Immutable snapshot of semantic integrity computation.

    Fields:
        semantic_integrity_score: Overall integrity score [0.0, 1.0] or None
        structural_consistency: Structural stability vs. rolling average [0.0, 1.0]
        layer_agreement_score: Agreement between symbolic/practical/mirror [0.0, 1.0]
        cross_turn_consistency: Consistency across last N turns [0.0, 1.0]
        mapper_alignment_score: Alignment between mapper profile and structure [0.0, 1.0]
        intent_identity_alignment: Alignment between intent/identity and structure [0.0, 1.0]
    """

    semantic_integrity_score: Optional[float]
    structural_consistency: float
    layer_agreement_score: float
    cross_turn_consistency: float
    mapper_alignment_score: float
    intent_identity_alignment: float


@dataclass
class CognitiveDriftSnapshotV3:
    """
    Immutable snapshot of cognitive drift v3 computation.

    Fields:
        cognitive_drift_v3: Overall drift score [0.0, 1.0] or None
        structure_drift: Drift in structural consistency [0.0, 1.0]
        topic_drift: Drift in topic/layer agreement [0.0, 1.0]
        mapper_drift: Drift in mapper activation patterns [0.0, 1.0]
        intent_identity_drift: Drift in intent arc + identity signature [0.0, 1.0]
    """

    cognitive_drift_v3: Optional[float]
    structure_drift: float
    topic_drift: float
    mapper_drift: float
    intent_identity_drift: float


def _clamp(value: float, min_val: float, max_val: float) -> float:
    """
    Clamp value to [min_val, max_val] range.

    Args:
        value: Value to clamp
        min_val: Minimum value
        max_val: Maximum value

    Returns:
        float: Clamped value
    """
    return max(min_val, min(max_val, value))


def _safe_mean(values: List[float]) -> float:
    """
    Compute mean of values, handling empty lists gracefully.

    Args:
        values: List of numeric values

    Returns:
        float: Mean value, or 0.5 if list is empty
    """
    if not values:
        return 0.5
    return sum(values) / len(values)


def _compute_structural_consistency(
    current_skeleton: Dict[str, Any],
    previous_skeletons: List[Dict[str, Any]],
) -> float:
    """
    Compute structural consistency between current skeleton and rolling average.

    Compares section counts and presence of key flags (symbolic/practical/mirror/dha).
    Higher similarity → closer to 1.0, large deviations → closer to 0.0.

    Args:
        current_skeleton: Current turn's semantic skeleton
        previous_skeletons: List of previous semantic skeletons (last N turns)

    Returns:
        float: Structural consistency score [0.0, 1.0]
    """
    if not previous_skeletons:
        return 1.0  # No history = perfectly consistent

    # Extract boolean flags from current skeleton
    current_flags = {
        "has_symbolic": current_skeleton.get("has_symbolic", False),
        "has_practical": current_skeleton.get("has_practical", False),
        "has_mirror": current_skeleton.get("has_mirror", False),
        "has_dha_insight": current_skeleton.get("has_dha_insight", False),
        "has_dha_alignment": current_skeleton.get("has_dha_alignment", False),
        "has_dha_conflict": current_skeleton.get("has_dha_conflict", False),
    }

    current_section_count = current_skeleton.get("section_count", 0)

    # Compute average flags and section count from previous skeletons
    num_flags = len(current_flags)
    flag_matches = 0

    for prev_skeleton in previous_skeletons:
        for flag_key in current_flags:
            prev_flag = prev_skeleton.get(flag_key, False)
            if current_flags[flag_key] == prev_flag:
                flag_matches += 1

    # Flag consistency: ratio of matching flags
    total_flag_comparisons = len(previous_skeletons) * num_flags
    if total_flag_comparisons > 0:
        flag_consistency = flag_matches / total_flag_comparisons
    else:
        flag_consistency = 1.0

    # Section count consistency: normalized distance from average
    prev_section_counts = [s.get("section_count", 0) for s in previous_skeletons]
    avg_section_count = _safe_mean(prev_section_counts)

    if avg_section_count > 0:
        section_deviation = abs(current_section_count - avg_section_count) / max(avg_section_count, 1.0)
        section_consistency = 1.0 - min(section_deviation, 1.0)
    else:
        section_consistency = 1.0 if current_section_count == 0 else 0.5

    # Combine flag and section consistency (weighted average)
    structural_consistency = 0.7 * flag_consistency + 0.3 * section_consistency

    return _clamp(structural_consistency, 0.0, 1.0)


def _compute_layer_agreement(current_skeleton: Dict[str, Any]) -> float:
    """
    Compute agreement/consistency between layers within a single turn.

    Checks for contradictions between symbolic/practical/mirror layers.
    Uses simple boolean/weight heuristics:
        - consistent signals → score ≥ 0.7
        - mixed/partial conflict → around 0.4–0.7
        - strong internal contradictions → ≤ 0.3

    Args:
        current_skeleton: Current turn's semantic skeleton

    Returns:
        float: Layer agreement score [0.0, 1.0]
    """
    # Extract layer presence flags
    has_symbolic = current_skeleton.get("has_symbolic", False)
    has_practical = current_skeleton.get("has_practical", False)
    has_mirror = current_skeleton.get("has_mirror", False)

    # Extract DHA markers (potential conflict indicators)
    has_dha_conflict = current_skeleton.get("has_dha_conflict", False)
    has_dha_alignment = current_skeleton.get("has_dha_alignment", False)

    # Rule 1: Strong conflict marker → low agreement
    if has_dha_conflict:
        return 0.3

    # Rule 2: Strong alignment marker → high agreement
    if has_dha_alignment:
        return 0.85

    # Rule 3: All three layers present → assume good agreement (balanced response)
    if has_symbolic and has_practical and has_mirror:
        return 0.75

    # Rule 4: Two layers present → moderate agreement
    layer_count = sum([has_symbolic, has_practical, has_mirror])
    if layer_count == 2:
        return 0.6

    # Rule 5: Only one layer → partial agreement (missing perspectives)
    if layer_count == 1:
        return 0.4

    # Rule 6: No layers → low agreement (incomplete response)
    return 0.2


def _compute_cross_turn_consistency(
    current_skeleton: Dict[str, Any],
    previous_skeletons: List[Dict[str, Any]],
) -> float:
    """
    Compute consistency between current skeleton and last N skeletons.

    Uses normalized Hamming / overlap score on key fields.

    Args:
        current_skeleton: Current turn's semantic skeleton
        previous_skeletons: List of previous semantic skeletons (last N turns)

    Returns:
        float: Cross-turn consistency score [0.0, 1.0]
    """
    if not previous_skeletons:
        return 1.0  # No history = perfectly consistent

    # Use last 3-5 skeletons for comparison
    recent_skeletons = previous_skeletons[-5:]

    # Extract boolean flags from current skeleton
    current_flags = {
        "has_symbolic": current_skeleton.get("has_symbolic", False),
        "has_practical": current_skeleton.get("has_practical", False),
        "has_mirror": current_skeleton.get("has_mirror", False),
        "has_dha_insight": current_skeleton.get("has_dha_insight", False),
        "has_dha_alignment": current_skeleton.get("has_dha_alignment", False),
        "has_dha_conflict": current_skeleton.get("has_dha_conflict", False),
    }

    # Compute Hamming similarity with each recent skeleton
    similarities = []
    for prev_skeleton in recent_skeletons:
        matches = sum(
            1 for key in current_flags
            if current_flags[key] == prev_skeleton.get(key, False)
        )
        similarity = matches / len(current_flags)
        similarities.append(similarity)

    # Return average similarity
    return _safe_mean(similarities)


def _compute_mapper_alignment(
    current_skeleton: Dict[str, Any],
    mapper_profile: Optional[Dict[str, Any]],
) -> float:
    """
    Compute alignment between mapper profile biases and structural emphasis.

    Checks if mapper profile (HRM/LCM/LAM biases) aligns with actual structural
    emphasis in the current skeleton.

    Args:
        current_skeleton: Current turn's semantic skeleton
        mapper_profile: Mapper profile with detail_bias, practical_bias, reflective_bias

    Returns:
        float: Mapper alignment score [0.0, 1.0]
    """
    if mapper_profile is None:
        return 0.5  # Neutral alignment if no mapper profile

    # Extract mapper biases
    detail_bias = mapper_profile.get("detail_bias", 0.0)
    practical_bias = mapper_profile.get("practical_bias", 0.0)
    reflective_bias = mapper_profile.get("reflective_bias", 0.0)

    # Extract layer presence flags
    has_symbolic = current_skeleton.get("has_symbolic", False)
    has_practical = current_skeleton.get("has_practical", False)
    has_mirror = current_skeleton.get("has_mirror", False)

    # Heuristic alignment scoring:
    # - High reflective_bias should correlate with symbolic/mirror layers
    # - High practical_bias should correlate with practical layer
    # - High detail_bias should correlate with higher section counts

    alignment_signals = []

    # Signal 1: Reflective bias vs symbolic layer
    if reflective_bias > 0.5:
        alignment_signals.append(1.0 if has_symbolic else 0.3)
    else:
        alignment_signals.append(0.5)  # Neutral

    # Signal 2: Practical bias vs practical layer
    if practical_bias > 0.5:
        alignment_signals.append(1.0 if has_practical else 0.3)
    else:
        alignment_signals.append(0.5)  # Neutral

    # Signal 3: Reflective bias vs mirror layer
    if reflective_bias > 0.5:
        alignment_signals.append(1.0 if has_mirror else 0.3)
    else:
        alignment_signals.append(0.5)  # Neutral

    # Compute average alignment
    return _safe_mean(alignment_signals)


def _compute_intent_identity_alignment(
    intent_arc: Optional[str],
    identity_signature: Optional[str],
) -> float:
    """
    Compute alignment between intent arc and identity signature.

    Aligned combinations:
        - insight_arc / stabilization_arc + self_anchoring / self_integration → high score
        - dissonance_arc / chaotic_arc + self_dissonance / self_fragmentation → low score

    Args:
        intent_arc: Intent arc classification (e.g., "insight_arc", "dissonance_arc")
        identity_signature: Identity signature (e.g., "self_anchoring", "self_dissonance")

    Returns:
        float: Intent-identity alignment score [0.0, 1.0]
    """
    if intent_arc is None or identity_signature is None:
        return 0.5  # Neutral if missing

    # Define positive/negative arc patterns
    positive_arcs = {"insight_arc", "stabilization_arc", "growth_arc", "clarity_arc"}
    negative_arcs = {"dissonance_arc", "chaotic_arc", "tension_arc", "regression_arc"}

    # Define positive/negative identity patterns
    positive_identities = {"self_anchoring", "self_integration", "self_discovery", "self_coherence"}
    negative_identities = {"self_dissonance", "self_fragmentation", "self_confusion", "self_contradiction"}

    # Check alignment
    is_positive_arc = intent_arc in positive_arcs
    is_negative_arc = intent_arc in negative_arcs

    is_positive_identity = identity_signature in positive_identities
    is_negative_identity = identity_signature in negative_identities

    # Aligned: both positive or both negative
    if (is_positive_arc and is_positive_identity) or (is_negative_arc and is_negative_identity):
        return 0.8

    # Misaligned: one positive, one negative
    if (is_positive_arc and is_negative_identity) or (is_negative_arc and is_positive_identity):
        return 0.2

    # Unknown patterns → neutral
    return 0.5


def compute_semantic_integrity(
    current_skeleton: Dict[str, Any],
    previous_skeletons: List[Dict[str, Any]],
    mapper_profile: Optional[Dict[str, Any]],
    intent_arc: Optional[str],
    identity_signature: Optional[str],
) -> SemanticIntegritySnapshot:
    """
    Compute semantic integrity score from semantic skeleton and context.

    This is the main semantic integrity computation function.

    Scoring formula:
        semantic_integrity_score = clamp(
            0.30 * structural_consistency
          + 0.25 * layer_agreement_score
          + 0.20 * cross_turn_consistency
          + 0.15 * mapper_alignment_score
          + 0.10 * intent_identity_alignment,
          0.0, 1.0
        )

    Args:
        current_skeleton: Current turn's semantic skeleton (from semantic_skeleton module)
        previous_skeletons: List of previous semantic skeletons (last N turns)
        mapper_profile: Mapper profile dict with biases
        intent_arc: Intent arc classification (optional)
        identity_signature: Identity signature classification (optional)

    Returns:
        SemanticIntegritySnapshot: Complete snapshot with integrity score and components

    Note:
        - All math is deterministic and zero-LLM
        - Missing inputs are handled gracefully with safe defaults
        - Returns None for integrity_score if current_skeleton is invalid
    """
    # Validate current skeleton
    if not current_skeleton:
        return SemanticIntegritySnapshot(
            semantic_integrity_score=None,
            structural_consistency=0.0,
            layer_agreement_score=0.0,
            cross_turn_consistency=0.0,
            mapper_alignment_score=0.0,
            intent_identity_alignment=0.0,
        )

    # Compute component scores
    structural_consistency = _compute_structural_consistency(current_skeleton, previous_skeletons)
    layer_agreement_score = _compute_layer_agreement(current_skeleton)
    cross_turn_consistency = _compute_cross_turn_consistency(current_skeleton, previous_skeletons)
    mapper_alignment_score = _compute_mapper_alignment(current_skeleton, mapper_profile)
    intent_identity_alignment = _compute_intent_identity_alignment(intent_arc, identity_signature)

    # Compute final semantic integrity score (weighted blend)
    semantic_integrity_score = _clamp(
        0.30 * structural_consistency
        + 0.25 * layer_agreement_score
        + 0.20 * cross_turn_consistency
        + 0.15 * mapper_alignment_score
        + 0.10 * intent_identity_alignment,
        0.0,
        1.0,
    )

    return SemanticIntegritySnapshot(
        semantic_integrity_score=semantic_integrity_score,
        structural_consistency=structural_consistency,
        layer_agreement_score=layer_agreement_score,
        cross_turn_consistency=cross_turn_consistency,
        mapper_alignment_score=mapper_alignment_score,
        intent_identity_alignment=intent_identity_alignment,
    )


def _compute_structure_drift(
    integrity_snapshots_last_n: List[SemanticIntegritySnapshot],
) -> float:
    """
    Compute structure drift from integrity snapshot history.

    Structure drift = 1.0 - average(structural_consistency over last N)
    Higher inconsistency → higher structure_drift.

    Args:
        integrity_snapshots_last_n: List of recent integrity snapshots

    Returns:
        float: Structure drift score [0.0, 1.0]
    """
    if not integrity_snapshots_last_n:
        return 0.0  # No history = no drift

    # Extract structural consistency values
    consistency_values = [
        snap.structural_consistency
        for snap in integrity_snapshots_last_n
        if snap.structural_consistency is not None
    ]

    if not consistency_values:
        return 0.0

    # Drift is inverse of average consistency
    avg_consistency = _safe_mean(consistency_values)
    structure_drift = 1.0 - avg_consistency

    return _clamp(structure_drift, 0.0, 1.0)


def _compute_topic_drift(
    integrity_snapshots_last_n: List[SemanticIntegritySnapshot],
) -> float:
    """
    Compute topic drift from integrity snapshot history.

    Uses variation in layer_agreement_score and cross_turn_consistency as proxy.
    Large swings → higher topic_drift.

    Args:
        integrity_snapshots_last_n: List of recent integrity snapshots

    Returns:
        float: Topic drift score [0.0, 1.0]
    """
    if not integrity_snapshots_last_n or len(integrity_snapshots_last_n) < 2:
        return 0.0  # No history = no drift

    # Extract layer agreement and cross-turn consistency values
    layer_agreement_values = [
        snap.layer_agreement_score
        for snap in integrity_snapshots_last_n
        if snap.layer_agreement_score is not None
    ]

    cross_turn_values = [
        snap.cross_turn_consistency
        for snap in integrity_snapshots_last_n
        if snap.cross_turn_consistency is not None
    ]

    # Compute variance in layer agreement (topic volatility)
    if len(layer_agreement_values) >= 2:
        try:
            layer_variance = statistics.variance(layer_agreement_values)
        except statistics.StatisticsError:
            layer_variance = 0.0
    else:
        layer_variance = 0.0

    # Compute variance in cross-turn consistency
    if len(cross_turn_values) >= 2:
        try:
            cross_variance = statistics.variance(cross_turn_values)
        except statistics.StatisticsError:
            cross_variance = 0.0
    else:
        cross_variance = 0.0

    # Topic drift is weighted combination of variances
    # Normalize variances to [0, 1] range (variance typically < 0.25 for [0, 1] values)
    normalized_layer_variance = min(layer_variance * 4.0, 1.0)
    normalized_cross_variance = min(cross_variance * 4.0, 1.0)

    topic_drift = 0.6 * normalized_layer_variance + 0.4 * normalized_cross_variance

    return _clamp(topic_drift, 0.0, 1.0)


def _compute_mapper_drift(
    mapper_history: List[Dict[str, Any]],
) -> float:
    """
    Compute mapper drift from mapper profile history.

    Counts mapper profile changes (activation pattern flips) over last N turns.
    Normalize (flips / N) to [0.0, 1.0].

    Args:
        mapper_history: List of mapper profile dicts

    Returns:
        float: Mapper drift score [0.0, 1.0]
    """
    if not mapper_history or len(mapper_history) < 2:
        return 0.0  # No history = no drift

    # Count significant changes in mapper activation patterns
    # We'll track changes in dominant mapper (highest bias)
    changes = 0

    for i in range(1, len(mapper_history)):
        prev_profile = mapper_history[i - 1]
        curr_profile = mapper_history[i]

        # Extract biases
        prev_detail = prev_profile.get("detail_bias", 0.0)
        prev_practical = prev_profile.get("practical_bias", 0.0)
        prev_reflective = prev_profile.get("reflective_bias", 0.0)

        curr_detail = curr_profile.get("detail_bias", 0.0)
        curr_practical = curr_profile.get("practical_bias", 0.0)
        curr_reflective = curr_profile.get("reflective_bias", 0.0)

        # Determine dominant mapper for each profile
        prev_dominant = max(
            [("detail", prev_detail), ("practical", prev_practical), ("reflective", prev_reflective)],
            key=lambda x: x[1]
        )[0]

        curr_dominant = max(
            [("detail", curr_detail), ("practical", curr_practical), ("reflective", curr_reflective)],
            key=lambda x: x[1]
        )[0]

        # Count change if dominant mapper flipped
        if prev_dominant != curr_dominant:
            changes += 1

    # Normalize: changes / comparisons
    num_comparisons = len(mapper_history) - 1
    if num_comparisons > 0:
        mapper_drift = changes / num_comparisons
    else:
        mapper_drift = 0.0

    return _clamp(mapper_drift, 0.0, 1.0)


def _compute_intent_identity_drift(
    intent_arc_history: List[Optional[str]],
    identity_signature_history: List[Optional[str]],
) -> float:
    """
    Compute intent-identity drift from arc and signature histories.

    Frequency of changes in intent_arc + identity_signature types.
    Stable intent & identity → low drift, frequent jumps → high drift.

    Args:
        intent_arc_history: List of intent arc classifications
        identity_signature_history: List of identity signature classifications

    Returns:
        float: Intent-identity drift score [0.0, 1.0]
    """
    # Count changes in intent arc
    intent_changes = 0
    if intent_arc_history and len(intent_arc_history) >= 2:
        for i in range(1, len(intent_arc_history)):
            prev_arc = intent_arc_history[i - 1]
            curr_arc = intent_arc_history[i]
            if prev_arc != curr_arc and prev_arc is not None and curr_arc is not None:
                intent_changes += 1

    # Count changes in identity signature
    identity_changes = 0
    if identity_signature_history and len(identity_signature_history) >= 2:
        for i in range(1, len(identity_signature_history)):
            prev_sig = identity_signature_history[i - 1]
            curr_sig = identity_signature_history[i]
            if prev_sig != curr_sig and prev_sig is not None and curr_sig is not None:
                identity_changes += 1

    # Compute total changes and normalize
    total_changes = intent_changes + identity_changes

    # Compute max possible changes
    intent_comparisons = max(len(intent_arc_history) - 1, 0)
    identity_comparisons = max(len(identity_signature_history) - 1, 0)
    max_changes = intent_comparisons + identity_comparisons

    if max_changes > 0:
        drift = total_changes / max_changes
    else:
        drift = 0.0

    return _clamp(drift, 0.0, 1.0)


def compute_cognitive_drift_v3(
    integrity_snapshots_last_n: List[SemanticIntegritySnapshot],
    mapper_history: List[Dict[str, Any]],
    intent_arc_history: List[Optional[str]],
    identity_signature_history: List[Optional[str]],
) -> CognitiveDriftSnapshotV3:
    """
    Compute cognitive drift v3 score from integrity history and context histories.

    This is the main cognitive drift v3 computation function.

    Drift formula:
        cognitive_drift_v3 = clamp(
            0.35 * structure_drift
          + 0.30 * topic_drift
          + 0.20 * mapper_drift
          + 0.15 * intent_identity_drift,
          0.0, 1.0
        )

    Args:
        integrity_snapshots_last_n: List of recent semantic integrity snapshots
        mapper_history: List of mapper profile dicts
        intent_arc_history: List of intent arc classifications
        identity_signature_history: List of identity signature classifications

    Returns:
        CognitiveDriftSnapshotV3: Complete snapshot with drift score and components

    Note:
        - All math is deterministic and zero-LLM
        - Missing inputs are handled gracefully with 0.0 defaults
        - Returns None for drift_v3 if all component histories are empty
    """
    # Compute component drifts
    structure_drift = _compute_structure_drift(integrity_snapshots_last_n)
    topic_drift = _compute_topic_drift(integrity_snapshots_last_n)
    mapper_drift = _compute_mapper_drift(mapper_history)
    intent_identity_drift = _compute_intent_identity_drift(
        intent_arc_history,
        identity_signature_history,
    )

    # If all histories are empty, return None for cognitive drift
    has_any_history = (
        bool(integrity_snapshots_last_n)
        or bool(mapper_history)
        or bool(intent_arc_history)
        or bool(identity_signature_history)
    )

    if not has_any_history:
        cognitive_drift_v3 = None
    else:
        # Compute final cognitive drift v3 score (weighted blend)
        cognitive_drift_v3 = _clamp(
            0.35 * structure_drift
            + 0.30 * topic_drift
            + 0.20 * mapper_drift
            + 0.15 * intent_identity_drift,
            0.0,
            1.0,
        )

    return CognitiveDriftSnapshotV3(
        cognitive_drift_v3=cognitive_drift_v3,
        structure_drift=structure_drift,
        topic_drift=topic_drift,
        mapper_drift=mapper_drift,
        intent_identity_drift=intent_identity_drift,
    )
