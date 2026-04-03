"""
Scenario Fusion Engine v1.0 - Phase 42

Deterministic, zero-LLM, observation-only "Scenario Fusion Engine" that fuses
Phase 41 Coherence-Regime Scenario Mapper outputs into a unified scenario fusion snapshot.

CRITICAL INVARIANTS:
    - Zero-LLM: Purely rule-based, deterministic math only
    - Observation-only: NO changes to routing, TTOR, MLCR, mappers, Fusion, DHA, Renderer
    - Diagnostics/UI only: Feeds coherence state, session summary, unified API, and DILchat badges
    - Non-invasive: Does not modify any existing coherence formulas or behaviors
    - Backward-compatible: All existing tests remain green
    - Deterministic: Same inputs → same outputs always
    - Fully bounded: All outputs [0.0, 1.0] where applicable
    - Graceful degradation: Returns None if insufficient data
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
import math


@dataclass
class ScenarioFusionSnapshot:
    """
    Immutable snapshot of scenario fusion computation.

    This snapshot fuses regime-level scenario outputs from Phase 41 into a unified
    representation that characterizes scenario alignment, divergence, consensus,
    and future uncertainty.

    Fields:
        fused_scenario_vector: Stability-weighted, normalized scenario representation
        scenario_alignment_score: [0.0, 1.0] - how aligned the regimes are (higher = more aligned)
        scenario_divergence_index: [0.0, 1.0] - how divergent they are (higher = more divergent)
        multi_regime_consensus: [0.0, 1.0] - agreement across regimes (higher = more agreement)
        dominant_future_path: Dominant regime/scenario or None
        future_uncertainty_band: "low" | "medium" | "high" | None
        diagnostic_tags: Pattern indicators (e.g., "SCENARIO_CONVERGING")
    """

    fused_scenario_vector: Dict[str, float] = field(default_factory=dict)
    scenario_alignment_score: float = 0.0
    scenario_divergence_index: float = 0.0
    multi_regime_consensus: float = 0.0
    dominant_future_path: Optional[str] = None
    future_uncertainty_band: Optional[str] = None
    diagnostic_tags: List[str] = field(default_factory=list)


def _clamp(value: float, min_val: float = 0.0, max_val: float = 1.0) -> float:
    """
    Clamp value to [min_val, max_val] range.

    Args:
        value: Value to clamp
        min_val: Minimum value (default 0.0)
        max_val: Maximum value (default 1.0)

    Returns:
        float: Clamped value
    """
    return max(min_val, min(max_val, value))


def _compute_shannon_entropy(distribution: Dict[str, float]) -> float:
    """
    Compute Shannon entropy of normalized distribution.

    Args:
        distribution: Normalized distribution (should sum to ~1.0)

    Returns:
        float: Entropy [0.0, 1.0], where 0 = focused, 1 = uniform
    """
    if not distribution:
        return 0.0

    n = len(distribution)
    if n <= 1:
        return 0.0

    # Compute Shannon entropy: H = -Σ(p_i * log2(p_i))
    entropy_raw = 0.0
    for prob in distribution.values():
        if prob > 0.0:
            entropy_raw -= prob * math.log2(prob)

    # Normalize by max entropy (log2(N))
    max_entropy = math.log2(n)
    entropy = entropy_raw / max_entropy if max_entropy > 0 else 0.0

    return _clamp(entropy, 0.0, 1.0)


def _compute_gini_coefficient(values: List[float]) -> float:
    """
    Compute Gini coefficient for measuring inequality/concentration.

    Args:
        values: List of non-negative values

    Returns:
        float: Gini coefficient [0.0, 1.0], where 0 = perfect equality, 1 = perfect inequality
    """
    if not values or len(values) <= 1:
        return 0.0

    # Sort values
    sorted_values = sorted(values)
    n = len(sorted_values)

    # Compute Gini coefficient
    # G = (2 * Σ(i * x_i)) / (n * Σ(x_i)) - (n+1)/n
    total = sum(sorted_values)

    if total <= 0.0:
        return 0.0

    weighted_sum = sum((i + 1) * val for i, val in enumerate(sorted_values))

    gini = (2.0 * weighted_sum) / (n * total) - (n + 1.0) / n

    return _clamp(gini, 0.0, 1.0)


def _normalize_vector(vector: Dict[str, float]) -> Dict[str, float]:
    """
    Normalize vector to sum to 1.0.

    Args:
        vector: Raw vector values

    Returns:
        dict: Normalized vector (sum = 1.0), or empty dict if sum is zero
    """
    if not vector:
        return {}

    total = sum(vector.values())

    if total <= 0.0:
        return {}

    return {key: val / total for key, val in vector.items()}


def compute_scenario_fusion(
    regime_scenarios: Dict[str, Any],
    *,
    regime_band: Optional[str] = None,
    secondary_regimes: Optional[List[str]] = None,
) -> Optional[ScenarioFusionSnapshot]:
    """
    Compute Scenario Fusion Engine v1.0.

    This function fuses Phase 41 regime-level scenario outputs into a unified
    scenario fusion snapshot that characterizes:
      - Scenario alignment (how focused/concentrated the regimes are)
      - Scenario divergence (how spread out/dispersed they are)
      - Multi-regime consensus (agreement across regimes)
      - Dominant future path (most likely scenario/regime)
      - Future uncertainty band (low/medium/high based on distribution)

    Args:
        regime_scenarios: Regime scores from Phase 41 (dict mapping regime name → score [0.0, 1.0])
        regime_band: Optional regime band from Phase 41 ("stable" | "mixed" | "volatile")
        secondary_regimes: Optional list of secondary regimes (sorted by score)

    Returns:
        ScenarioFusionSnapshot or None if insufficient data

    Formula Design:
        - scenario_alignment_score: Based on Gini coefficient and entropy (high = concentrated/aligned)
        - scenario_divergence_index: Complement of alignment or entropy-based (high = dispersed/divergent)
        - multi_regime_consensus: Variance-based measure (high = low variance = consensus)
        - dominant_future_path: Regime with highest score (deterministic tie-breaking)
        - future_uncertainty_band:
            - LOW: high alignment, high consensus, low divergence
            - MEDIUM: mixed indicators
            - HIGH: low alignment, low consensus, high divergence
        - fused_scenario_vector: Normalized regime scores (stability-weighted if needed)

    Graceful Degradation:
        Returns None if regime_scenarios is empty or invalid.
    """
    # ========================================================================
    # STEP 1: VALIDATE INPUT
    # ========================================================================

    if not regime_scenarios or not isinstance(regime_scenarios, dict):
        return None

    # Filter out None/invalid values and clamp to [0.0, 1.0]
    valid_scenarios = {
        regime: _clamp(score, 0.0, 1.0)
        for regime, score in regime_scenarios.items()
        if isinstance(score, (int, float)) and score is not None
    }

    if not valid_scenarios or len(valid_scenarios) < 2:
        # Need at least 2 regimes for meaningful fusion
        return None

    # ========================================================================
    # STEP 2: NORMALIZE SCENARIO VECTOR
    # ========================================================================

    # Normalize to create probability distribution
    fused_scenario_vector = _normalize_vector(valid_scenarios)

    if not fused_scenario_vector:
        return None

    # ========================================================================
    # STEP 3: COMPUTE SCENARIO ALIGNMENT SCORE
    # ========================================================================

    # Scenario alignment measures how concentrated/focused the scores are
    # High alignment = one or few regimes dominate
    # Low alignment = scores evenly distributed

    # Use Gini coefficient (inequality measure)
    # High Gini = high inequality = high alignment (one regime dominates)
    scores_list = list(valid_scenarios.values())
    gini = _compute_gini_coefficient(scores_list)

    # Use entropy (uniformity measure)
    # Low entropy = focused = high alignment
    entropy = _compute_shannon_entropy(fused_scenario_vector)

    # Combine Gini and inverted entropy
    # Gini: 0 = equal, 1 = concentrated → directly use for alignment
    # Entropy: 0 = focused, 1 = uniform → invert for alignment
    scenario_alignment_score = (0.60 * gini + 0.40 * (1.0 - entropy))
    scenario_alignment_score = _clamp(scenario_alignment_score, 0.0, 1.0)

    # ========================================================================
    # STEP 4: COMPUTE SCENARIO DIVERGENCE INDEX
    # ========================================================================

    # Divergence is the complement of alignment in this context
    # Can also incorporate entropy directly
    # High divergence = scores spread out, no clear winner

    # Use entropy as primary driver for divergence
    # High entropy = high divergence
    scenario_divergence_index = entropy

    # Ensure divergence + alignment don't necessarily sum to 1.0
    # (they measure related but distinct aspects)
    scenario_divergence_index = _clamp(scenario_divergence_index, 0.0, 1.0)

    # ========================================================================
    # STEP 5: COMPUTE MULTI-REGIME CONSENSUS
    # ========================================================================

    # Consensus measures agreement across regimes
    # High consensus = low variance, scores clustered together
    # Low consensus = high variance, scores widely spread

    # Compute variance of scores
    mean_score = sum(scores_list) / len(scores_list)
    variance = sum((score - mean_score) ** 2 for score in scores_list) / len(scores_list)

    # Normalize variance to [0.0, 1.0]
    # Max variance for scores in [0, 1] is 0.25 (when half are 0, half are 1)
    normalized_variance = min(variance / 0.25, 1.0)

    # Consensus is inverted variance
    # Low variance → high consensus
    multi_regime_consensus = _clamp(1.0 - normalized_variance, 0.0, 1.0)

    # ========================================================================
    # STEP 6: DETERMINE DOMINANT FUTURE PATH
    # ========================================================================

    # Dominant future path is the regime with highest score
    # Deterministic tie-breaking using sorted keys
    sorted_regimes = sorted(
        valid_scenarios.items(),
        key=lambda x: (x[1], x[0]),  # Sort by score DESC, then name ASC for determinism
        reverse=True
    )

    dominant_future_path = sorted_regimes[0][0] if sorted_regimes else None

    # ========================================================================
    # STEP 7: DETERMINE FUTURE UNCERTAINTY BAND
    # ========================================================================

    # Uncertainty band based on alignment, divergence, and consensus
    # LOW: high alignment (>0.65), high consensus (>0.65), low divergence (<0.35)
    # HIGH: low alignment (<0.40), low consensus (<0.40), high divergence (>0.65)
    # MEDIUM: everything else

    future_uncertainty_band = None

    # LOW uncertainty: strong alignment, strong consensus, low divergence
    if (scenario_alignment_score >= 0.65 and
        multi_regime_consensus >= 0.65 and
        scenario_divergence_index <= 0.35):
        future_uncertainty_band = "low"

    # HIGH uncertainty: weak alignment, weak consensus, high divergence
    elif (scenario_alignment_score <= 0.40 and
          multi_regime_consensus <= 0.40 and
          scenario_divergence_index >= 0.65):
        future_uncertainty_band = "high"

    # MEDIUM uncertainty: mixed indicators
    else:
        future_uncertainty_band = "medium"

    # ========================================================================
    # STEP 8: GENERATE DIAGNOSTIC TAGS
    # ========================================================================

    diagnostic_tags = []

    # Alignment tags
    if scenario_alignment_score >= 0.70:
        diagnostic_tags.append("SCENARIO_HIGHLY_ALIGNED")
    elif scenario_alignment_score <= 0.35:
        diagnostic_tags.append("SCENARIO_POORLY_ALIGNED")

    # Divergence tags
    if scenario_divergence_index >= 0.70:
        diagnostic_tags.append("SCENARIO_DIVERGING")
    elif scenario_divergence_index <= 0.35:
        diagnostic_tags.append("SCENARIO_CONVERGING")

    # Consensus tags
    if multi_regime_consensus >= 0.70:
        diagnostic_tags.append("SCENARIO_CONSENSUS_STRONG")
    elif multi_regime_consensus <= 0.35:
        diagnostic_tags.append("SCENARIO_CONSENSUS_WEAK")

    # Uncertainty tags
    if future_uncertainty_band == "low":
        diagnostic_tags.append("SCENARIO_FUTURE_STABLE")
    elif future_uncertainty_band == "high":
        diagnostic_tags.append("SCENARIO_FUTURE_UNCERTAIN")
    elif future_uncertainty_band == "medium":
        diagnostic_tags.append("SCENARIO_FUTURE_CAUTIOUS")

    # Pattern tags
    if scenario_alignment_score >= 0.65 and multi_regime_consensus >= 0.65:
        diagnostic_tags.append("SCENARIO_PATH_CONVERGING")

    if scenario_divergence_index >= 0.65 and multi_regime_consensus <= 0.40:
        diagnostic_tags.append("SCENARIO_PATH_DIVERGING")

    # Regime band tags (if provided)
    if regime_band:
        if regime_band == "stable":
            diagnostic_tags.append("SCENARIO_REGIME_STABLE")
        elif regime_band == "volatile":
            diagnostic_tags.append("SCENARIO_REGIME_VOLATILE")
        elif regime_band == "mixed":
            diagnostic_tags.append("SCENARIO_REGIME_MIXED")

    # Dominant path tags
    if dominant_future_path:
        diagnostic_tags.append(f"SCENARIO_PATH_{dominant_future_path.upper()}")

    # Sort and deduplicate for determinism
    diagnostic_tags = sorted(set(diagnostic_tags))

    # ========================================================================
    # STEP 9: RETURN SNAPSHOT
    # ========================================================================

    return ScenarioFusionSnapshot(
        fused_scenario_vector=fused_scenario_vector,
        scenario_alignment_score=scenario_alignment_score,
        scenario_divergence_index=scenario_divergence_index,
        multi_regime_consensus=multi_regime_consensus,
        dominant_future_path=dominant_future_path,
        future_uncertainty_band=future_uncertainty_band,
        diagnostic_tags=diagnostic_tags,
    )
