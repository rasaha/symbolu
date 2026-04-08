"""
Phase 44: Coherence-Scenario Alignment Engine - Core Logic

Deterministic alignment computation between coherence state and scenario futures.

Phase 44 answers:
    "How well do the possible scenario trajectories align with the
    system's current coherence state?"

This is alignment measurement only - not forecasting, not choice, not gating.

ALGORITHM:

Step 1 - Guard Conditions:
    If coherence_v3_quality is None OR ScenarioFusionField is None:
        Return None (no fabrication)

Step 2 - Base Alignment Score:
    base_alignment_score = 0.60 * coherence_v3_quality + 0.40 * fusion_confidence
    Clamp to [0.0, 1.0]

Step 3 - Variant Alignment Scores (if P43 present):
    For each ScenarioVariant:
        variant_alignment = base_alignment_score
                           - abs(variant.delta_entropy)
                           - abs(variant.delta_confidence)
    Clamp to [0.0, 1.0]
    No normalization across variants.
    No comparison between variants.

Step 4 - Alignment Band Classification:
    Based ONLY on base_alignment_score:
        >= 0.70 -> "aligned"
        >= 0.45 -> "strained"
        < 0.45  -> "misaligned"
    Variants never affect the band.

Invariants:
    INV-P44-1: Measurement only (no ranking, no preference, no selection)
    INV-P44-2: Deterministic math only (no randomness, no learned parameters)
    INV-P44-3: Variant isolation (variants do not influence base alignment)
    INV-P44-4: No authority influence (output never affects regime, discourse, policy)
    INV-P44-5: Absence-safe (missing inputs -> no output)
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from .p44_schema import (
    COHERENCE_QUALITY_WEIGHT,
    FUSION_CONFIDENCE_WEIGHT,
    CoherenceScenarioAlignmentReport,
    create_alignment_report,
)


def compute_alignment(
    coherence_v3_quality: Optional[float],
    scenario_fusion_confidence: Optional[float],
    what_if_variants: Optional[Tuple[Any, ...]] = None,
) -> Optional[CoherenceScenarioAlignmentReport]:
    """
    Compute coherence-scenario alignment measurement.

    This is the core deterministic alignment computation.

    INV-P44-1: Measurement only - no ranking, preference, or selection.
    INV-P44-2: Deterministic - no randomness, no learned parameters.
    INV-P44-3: Variant isolation - variants do not influence base alignment.
    INV-P44-5: Absence-safe - missing inputs produce no output.

    Args:
        coherence_v3_quality: Quality score from Phase 12 [0.0, 1.0]
        scenario_fusion_confidence: Fusion confidence from Phase 42 [0.0, 1.0]
        what_if_variants: Optional tuple of ScenarioVariant from Phase 43

    Returns:
        CoherenceScenarioAlignmentReport if inputs valid, None otherwise
    """
    # Step 1: Guard conditions (INV-P44-5)
    if coherence_v3_quality is None or scenario_fusion_confidence is None:
        return None

    # Validate inputs are numeric
    try:
        coherence_v3_quality = float(coherence_v3_quality)
        scenario_fusion_confidence = float(scenario_fusion_confidence)
    except (TypeError, ValueError):
        return None

    # Step 2: Compute base alignment score (INV-P44-2: deterministic)
    base_alignment_score = _compute_base_alignment(
        coherence_v3_quality,
        scenario_fusion_confidence,
    )

    # Step 3: Compute variant alignment scores (if P43 present)
    variant_alignment = _compute_variant_alignments(
        base_alignment_score,
        what_if_variants,
    )

    # Build debug info
    debug = {
        "coherence_v3_quality_input": coherence_v3_quality,
        "scenario_fusion_confidence_input": scenario_fusion_confidence,
        "variant_count": len(what_if_variants) if what_if_variants else 0,
    }

    # Step 4 & 5: Create and return report
    # (alignment_band is automatically derived from base_alignment_score
    # in create_alignment_report, enforcing INV-P44-3)
    return create_alignment_report(
        base_alignment_score=base_alignment_score,
        variant_alignment=variant_alignment,
        debug=debug,
    )


def _compute_base_alignment(
    coherence_v3_quality: float,
    scenario_fusion_confidence: float,
) -> float:
    """
    Compute base alignment score.

    Formula:
        base_alignment_score = 0.60 * coherence_v3_quality
                             + 0.40 * scenario_fusion_confidence

    INV-P44-2: Deterministic math with fixed weights.

    Args:
        coherence_v3_quality: Quality score from Phase 12 [0.0, 1.0]
        scenario_fusion_confidence: Fusion confidence from Phase 42 [0.0, 1.0]

    Returns:
        Base alignment score clamped to [0.0, 1.0]
    """
    raw_score = (
        COHERENCE_QUALITY_WEIGHT * coherence_v3_quality
        + FUSION_CONFIDENCE_WEIGHT * scenario_fusion_confidence
    )

    # Clamp to [0.0, 1.0]
    return max(0.0, min(1.0, raw_score))


def _compute_variant_alignments(
    base_alignment_score: float,
    what_if_variants: Optional[Tuple[Any, ...]] = None,
) -> Dict[str, float]:
    """
    Compute alignment scores for each scenario variant.

    Formula per variant:
        variant_alignment = base_alignment_score
                          - abs(variant.delta_entropy)
                          - abs(variant.delta_confidence)

    INV-P44-1: No ranking between variants - just compute each independently.
    INV-P44-2: Deterministic subtraction only.
    INV-P44-3: These scores do NOT influence base_alignment_score or band.

    Args:
        base_alignment_score: The base alignment score [0.0, 1.0]
        what_if_variants: Optional tuple of ScenarioVariant from Phase 43

    Returns:
        Dict mapping variant_id -> alignment_score
    """
    if what_if_variants is None:
        return {}

    variant_alignment: Dict[str, float] = {}

    for variant in what_if_variants:
        # Extract variant attributes safely
        variant_id = getattr(variant, "variant_id", None)
        delta_entropy = getattr(variant, "delta_entropy", None)
        delta_confidence = getattr(variant, "delta_confidence", None)

        # Skip variants with missing attributes
        if variant_id is None:
            continue

        if delta_entropy is None or delta_confidence is None:
            # Use base score if deltas not available
            variant_alignment[variant_id] = base_alignment_score
            continue

        # Compute variant alignment (INV-P44-2: deterministic)
        try:
            delta_entropy = float(delta_entropy)
            delta_confidence = float(delta_confidence)

            raw_variant_score = (
                base_alignment_score
                - abs(delta_entropy)
                - abs(delta_confidence)
            )

            # Clamp to [0.0, 1.0]
            variant_alignment[variant_id] = max(0.0, min(1.0, raw_variant_score))

        except (TypeError, ValueError):
            # On conversion error, use base score
            variant_alignment[variant_id] = base_alignment_score

    return variant_alignment
