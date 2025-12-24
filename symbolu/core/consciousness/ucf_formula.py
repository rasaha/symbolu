"""
P26 - Unified Consciousness Formula Pure Computation

Pure, deterministic formula computation for the UCF scalar.

This module contains ONLY the mathematical computation of UCF.
No state, no side effects, no LLM calls, no randomness.

Formula (Canonical v1.0):
    UCF = clamp(
        0.30 * coherence_v3_quality +
        0.25 * (1 - drift_fusion_index) +
        0.20 * (1 - entropy_volatility) +
        0.15 * schema_stability +
        0.10 * identity_harmonics_stability
    )

Rules:
    - Missing optional inputs -> neutral contribution (0.5, no penalty)
    - All intermediate values clamped
    - Final UCF clamped [0.0, 1.0]
    - Same inputs -> identical outputs (bitwise determinism)

CRITICAL: This module MUST NOT import:
    - P6-P9 (regime, discourse, semantics, lexical)
    - P21 delivery logic
    - Renderer, DHA, Persona
    - Observer-only phases (P22-P24)
    - Any module that performs LLM calls or uses randomness
"""

from __future__ import annotations

from typing import Dict, Optional, Tuple

from symbolu.core.consciousness.ucf_schema import (
    UCF_WEIGHTS,
    STABILITY_THRESHOLDS,
    NEUTRAL_DEFAULT,
    StabilityBand,
    UnifiedConsciousnessState,
    create_ucf_state,
)


# ============================================================================
# PURE FUNCTIONS - No state, no side effects
# ============================================================================


def clamp(value: float, min_val: float = 0.0, max_val: float = 1.0) -> float:
    """
    Clamp value to [min_val, max_val] range.

    This is a pure function with no side effects.

    Args:
        value: Value to clamp
        min_val: Minimum value (default 0.0)
        max_val: Maximum value (default 1.0)

    Returns:
        float: Clamped value
    """
    return max(min_val, min(max_val, value))


def compute_stability_band(ucf_score: float) -> StabilityBand:
    """
    Compute stability band from UCF score using deterministic thresholds.

    This is a pure function with no heuristics.

    Args:
        ucf_score: UCF score in [0.0, 1.0]

    Returns:
        StabilityBand: stable, transitional, or unstable

    Rules (deterministic, no exceptions):
        ucf >= 0.75 -> "stable"
        0.45 <= ucf < 0.75 -> "transitional"
        ucf < 0.45 -> "unstable"
    """
    if ucf_score >= STABILITY_THRESHOLDS["stable"]:
        return StabilityBand.STABLE
    elif ucf_score >= STABILITY_THRESHOLDS["transitional"]:
        return StabilityBand.TRANSITIONAL
    else:
        return StabilityBand.UNSTABLE


def compute_ucf(
    *,
    coherence_v3_quality: Optional[float] = None,
    drift_fusion_index: Optional[float] = None,
    entropy_volatility: Optional[float] = None,
    schema_stability: Optional[float] = None,
    identity_harmonics_stability: Optional[float] = None,
) -> UnifiedConsciousnessState:
    """
    Compute Unified Consciousness Formula (UCF) v1.0.

    This is a pure, deterministic function that computes the UCF scalar
    from upstream coherence signals. Same inputs ALWAYS produce the same
    output (bitwise identical).

    Formula (Canonical):
        UCF = clamp(
            0.30 * coherence_v3_quality +
            0.25 * (1 - drift_fusion_index) +
            0.20 * (1 - entropy_volatility) +
            0.15 * schema_stability +
            0.10 * identity_harmonics_stability
        )

    Args:
        coherence_v3_quality: P10/P12 coherence quality [0.0, 1.0]
                             Higher = better coherence quality
        drift_fusion_index: P19 drift fusion index [0.0, 1.0]
                           Higher = more drift (inverted in formula)
        entropy_volatility: P18 entropy volatility [0.0, 1.0]
                           Higher = more volatile (inverted in formula)
        schema_stability: P33 schema stability [0.0, 1.0]
                         Higher = more stable schema
        identity_harmonics_stability: Identity harmonics [0.0, 1.0]
                                     Higher = more harmonious identity

    Returns:
        UnifiedConsciousnessState with:
        - ucf_score: [0.0, 1.0], higher = more stable
        - stability_band: stable/transitional/unstable
        - contributing_factors: breakdown of each factor
        - confidence: based on how many inputs were available

    Invariants:
        - INV-P26-3: UCF is monotonic with respect to instability
          (higher instability inputs -> lower UCF)
        - INV-P26-5: Absence of optional inputs never destabilizes output
          (missing inputs use neutral default 0.5)
    """
    debug: Dict[str, any] = {"missing_inputs": [], "raw_inputs": {}}

    # Track raw inputs for debug
    debug["raw_inputs"] = {
        "coherence_v3_quality": coherence_v3_quality,
        "drift_fusion_index": drift_fusion_index,
        "entropy_volatility": entropy_volatility,
        "schema_stability": schema_stability,
        "identity_harmonics_stability": identity_harmonics_stability,
    }

    # ========================================================================
    # STEP 1: Prepare inputs with graceful degradation
    # ========================================================================

    # Track how many inputs are available for confidence calculation
    available_count = 0
    total_weight = 0.0

    # Coherence V3 Quality (weight: 0.30)
    if coherence_v3_quality is not None:
        cq_value = clamp(coherence_v3_quality)
        available_count += 1
        total_weight += UCF_WEIGHTS["coherence_v3_quality"]
    else:
        cq_value = NEUTRAL_DEFAULT
        debug["missing_inputs"].append("coherence_v3_quality")

    # Drift Fusion Stability (weight: 0.25) - INVERTED
    # drift_fusion_index is a risk metric, so we invert it
    if drift_fusion_index is not None:
        df_stability = 1.0 - clamp(drift_fusion_index)
        available_count += 1
        total_weight += UCF_WEIGHTS["drift_fusion_stability"]
    else:
        df_stability = NEUTRAL_DEFAULT
        debug["missing_inputs"].append("drift_fusion_index")

    # Entropy Stability (weight: 0.20) - INVERTED
    # entropy_volatility is a risk metric, so we invert it
    if entropy_volatility is not None:
        ent_stability = 1.0 - clamp(entropy_volatility)
        available_count += 1
        total_weight += UCF_WEIGHTS["entropy_stability"]
    else:
        ent_stability = NEUTRAL_DEFAULT
        debug["missing_inputs"].append("entropy_volatility")

    # Schema Stability (weight: 0.15)
    if schema_stability is not None:
        schema_value = clamp(schema_stability)
        available_count += 1
        total_weight += UCF_WEIGHTS["schema_stability"]
    else:
        schema_value = NEUTRAL_DEFAULT
        debug["missing_inputs"].append("schema_stability")

    # Identity Harmonics Stability (weight: 0.10)
    if identity_harmonics_stability is not None:
        ih_value = clamp(identity_harmonics_stability)
        available_count += 1
        total_weight += UCF_WEIGHTS["identity_harmonics"]
    else:
        ih_value = NEUTRAL_DEFAULT
        debug["missing_inputs"].append("identity_harmonics_stability")

    # ========================================================================
    # STEP 2: Compute UCF using weighted blend
    # ========================================================================

    # Canonical formula: weighted sum of stability signals
    raw_ucf = (
        UCF_WEIGHTS["coherence_v3_quality"] * cq_value +
        UCF_WEIGHTS["drift_fusion_stability"] * df_stability +
        UCF_WEIGHTS["entropy_stability"] * ent_stability +
        UCF_WEIGHTS["schema_stability"] * schema_value +
        UCF_WEIGHTS["identity_harmonics"] * ih_value
    )

    # Clamp final UCF to [0.0, 1.0]
    ucf_score = clamp(raw_ucf)

    debug["raw_ucf_before_clamp"] = raw_ucf
    debug["ucf_score_after_clamp"] = ucf_score

    # ========================================================================
    # STEP 3: Compute contributing factors
    # ========================================================================

    contributing_factors = {
        "coherence_v3_quality": cq_value,
        "drift_fusion_stability": df_stability,
        "entropy_stability": ent_stability,
        "schema_stability": schema_value,
        "identity_harmonics": ih_value,
    }

    # ========================================================================
    # STEP 4: Compute confidence
    # ========================================================================

    # Confidence is based on how many inputs were actually available
    # 5 inputs available = 1.0, 0 inputs = 0.0
    confidence = available_count / 5.0

    debug["available_count"] = available_count
    debug["confidence"] = confidence

    # ========================================================================
    # STEP 5: Create and return state
    # ========================================================================

    return create_ucf_state(
        ucf_score=ucf_score,
        contributing_factors=contributing_factors,
        confidence=confidence,
        debug=debug,
    )


def compute_ucf_from_factors(
    factors: Dict[str, Optional[float]],
) -> UnifiedConsciousnessState:
    """
    Compute UCF from a dictionary of factors.

    This is a convenience wrapper around compute_ucf that accepts
    a dictionary of factor values.

    Args:
        factors: Dictionary with keys:
            - coherence_v3_quality
            - drift_fusion_index
            - entropy_volatility
            - schema_stability
            - identity_harmonics_stability

    Returns:
        UnifiedConsciousnessState
    """
    return compute_ucf(
        coherence_v3_quality=factors.get("coherence_v3_quality"),
        drift_fusion_index=factors.get("drift_fusion_index"),
        entropy_volatility=factors.get("entropy_volatility"),
        schema_stability=factors.get("schema_stability"),
        identity_harmonics_stability=factors.get("identity_harmonics_stability"),
    )


def verify_ucf_determinism(
    coherence_v3_quality: Optional[float] = None,
    drift_fusion_index: Optional[float] = None,
    entropy_volatility: Optional[float] = None,
    schema_stability: Optional[float] = None,
    identity_harmonics_stability: Optional[float] = None,
    iterations: int = 10,
) -> Tuple[bool, float]:
    """
    Verify UCF is deterministic by computing it multiple times.

    This is a testing utility to verify INV-P26 determinism guarantees.

    Args:
        All UCF input parameters
        iterations: Number of times to compute UCF

    Returns:
        Tuple of (is_deterministic, ucf_score)
        is_deterministic is True if all iterations produced identical results
    """
    results = []
    for _ in range(iterations):
        state = compute_ucf(
            coherence_v3_quality=coherence_v3_quality,
            drift_fusion_index=drift_fusion_index,
            entropy_volatility=entropy_volatility,
            schema_stability=schema_stability,
            identity_harmonics_stability=identity_harmonics_stability,
        )
        results.append(state.ucf_score)

    # Check all results are identical
    is_deterministic = len(set(results)) == 1
    ucf_score = results[0] if results else 0.0

    return is_deterministic, ucf_score


# Public exports
__all__ = [
    # Pure functions
    "clamp",
    "compute_stability_band",
    "compute_ucf",
    "compute_ucf_from_factors",
    # Testing utilities
    "verify_ucf_determinism",
]
