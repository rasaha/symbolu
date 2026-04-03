"""
Phase 42: Scenario Fusion Logic

Deterministic aggregation of multiple ScenarioRegimeMap observations
into a unified ScenarioFusionField.

Core Fusion Logic:
    Step 1: Collect inputs (list of ScenarioRegimeMap)
    Step 2: Build distribution (count occurrences, normalize)
    Step 3: Dominant regime selection (≥0.60 → that regime, else "ambiguous_mixed")
    Step 4: Fusion confidence = mean(confidences) * max(distribution)
    Step 5: Regime entropy = normalized Shannon entropy

Invariants:
    INV-P42-1: Observer-only (no downstream authority impact)
    INV-P42-2: Deterministic aggregation (no randomness, no learned weights)
    INV-P42-3: No regime creation (cannot invent new regimes)
    INV-P42-4: Monotonic ambiguity (more disagreement → higher entropy)
    INV-P42-5: Absence-safe (empty input produces no output)
"""

import math
from typing import Dict, List, Optional, Sequence

from symbolu_core.mechanical.pipeline.p41_scenario_regime_mapper.p41_schema import (
    ScenarioRegimeMap,
)

from .p42_schema import (
    DOMINANT_THRESHOLD,
    NUM_REGIMES,
    VALID_REGIMES,
    ScenarioFusionField,
    ScenarioRegime,
    create_scenario_fusion_field,
)


def clamp(value: float, min_val: float = 0.0, max_val: float = 1.0) -> float:
    """Clamp a value to [min_val, max_val]."""
    return max(min_val, min(max_val, value))


def build_regime_distribution(
    regime_maps: Sequence[ScenarioRegimeMap],
) -> Dict[str, float]:
    """
    Step 2: Build normalized distribution from regime counts.

    Counts occurrences of each scenario_regime and normalizes to sum = 1.0.

    Args:
        regime_maps: Non-empty sequence of ScenarioRegimeMap objects

    Returns:
        Dictionary mapping each regime to its normalized frequency
    """
    # Initialize counts for all valid regimes
    counts: Dict[str, int] = {regime: 0 for regime in VALID_REGIMES}

    # Count occurrences
    for regime_map in regime_maps:
        regime = regime_map.scenario_regime
        if regime in counts:
            counts[regime] += 1

    # Normalize
    total = len(regime_maps)
    distribution: Dict[str, float] = {}
    for regime in VALID_REGIMES:
        distribution[regime] = counts[regime] / total if total > 0 else 0.0

    return distribution


def select_dominant_regime(
    distribution: Dict[str, float],
) -> ScenarioRegime:
    """
    Step 3: Select dominant regime from distribution.

    Rules:
        - If one regime ≥ 0.60 → dominant_regime = that regime
        - Else → dominant_regime = "ambiguous_mixed"

    No tie-breaking heuristics. No weighting tricks.

    Args:
        distribution: Normalized regime distribution (sum = 1.0)

    Returns:
        The dominant regime label
    """
    # Find the regime with maximum proportion
    max_proportion = 0.0
    max_regime: Optional[str] = None

    for regime in VALID_REGIMES:
        proportion = distribution.get(regime, 0.0)
        if proportion > max_proportion:
            max_proportion = proportion
            max_regime = regime

    # Check if it meets the threshold
    if max_proportion >= DOMINANT_THRESHOLD and max_regime is not None:
        return max_regime  # type: ignore[return-value]

    # Fallback to ambiguous_mixed
    return "ambiguous_mixed"


def compute_fusion_confidence(
    regime_maps: Sequence[ScenarioRegimeMap],
    distribution: Dict[str, float],
) -> float:
    """
    Step 4: Compute fusion confidence.

    Formula:
        fusion_confidence = mean(confidence for all inputs) * max(distribution values)

    Result is clamped to [0.0, 1.0].

    Args:
        regime_maps: Non-empty sequence of ScenarioRegimeMap objects
        distribution: Normalized regime distribution

    Returns:
        Fusion confidence score in [0.0, 1.0]
    """
    if not regime_maps:
        return 0.0

    # Calculate mean confidence
    total_confidence = sum(rm.confidence for rm in regime_maps)
    mean_confidence = total_confidence / len(regime_maps)

    # Get max distribution value
    max_distribution = max(distribution.values()) if distribution else 0.0

    # Compute fusion confidence
    fusion_confidence = mean_confidence * max_distribution

    return clamp(fusion_confidence)


def compute_regime_entropy(distribution: Dict[str, float]) -> float:
    """
    Step 5: Compute normalized Shannon entropy.

    Formula:
        entropy = -Σ p_i * log(p_i) / log(N)

    Where:
        - p_i = regime_distribution values
        - N = number of possible regimes (4)

    Result is in [0.0, 1.0]:
        - 0.0 = perfect agreement (one regime = 100%)
        - 1.0 = maximum disagreement (uniform distribution)

    This satisfies INV-P42-4: Monotonic ambiguity
    (more disagreement → higher entropy, never lower)

    Args:
        distribution: Normalized regime distribution

    Returns:
        Normalized entropy in [0.0, 1.0]
    """
    # Handle edge cases
    if not distribution:
        return 0.0

    # Calculate Shannon entropy
    entropy = 0.0
    for p in distribution.values():
        if p > 0:
            entropy -= p * math.log(p)

    # Normalize by log(N) where N = number of regimes
    # This ensures result is in [0.0, 1.0]
    max_entropy = math.log(NUM_REGIMES)
    if max_entropy > 0:
        normalized_entropy = entropy / max_entropy
    else:
        normalized_entropy = 0.0

    return clamp(normalized_entropy)


def fuse_scenario_regimes(
    regime_maps: Sequence[ScenarioRegimeMap],
) -> Optional[ScenarioFusionField]:
    """
    Main fusion function: Fuse multiple ScenarioRegimeMap observations
    into a single ScenarioFusionField.

    This function implements all 5 steps of the fusion logic:
        1. Collect inputs
        2. Build distribution
        3. Select dominant regime
        4. Compute fusion confidence
        5. Compute regime entropy

    Invariants enforced:
        INV-P42-1: Observer-only (returns frozen dataclass, no side effects)
        INV-P42-2: Deterministic (pure function, no randomness)
        INV-P42-3: No regime creation (only uses VALID_REGIMES)
        INV-P42-4: Monotonic ambiguity (entropy increases with disagreement)
        INV-P42-5: Absence-safe (returns None for empty input)

    Args:
        regime_maps: Sequence of ScenarioRegimeMap objects from Phase 41

    Returns:
        ScenarioFusionField if input is non-empty, None otherwise
    """
    # Step 1: Collect inputs (INV-P42-5: Absence-safe)
    if not regime_maps:
        return None

    # Convert to list for consistent handling
    regime_list: List[ScenarioRegimeMap] = list(regime_maps)

    # Step 2: Build distribution
    distribution = build_regime_distribution(regime_list)

    # Step 3: Select dominant regime (INV-P42-3: No regime creation)
    dominant_regime = select_dominant_regime(distribution)

    # Step 4: Compute fusion confidence
    fusion_confidence = compute_fusion_confidence(regime_list, distribution)

    # Step 5: Compute regime entropy (INV-P42-4: Monotonic ambiguity)
    regime_entropy = compute_regime_entropy(distribution)

    # Build debug info for observability
    debug = {
        "input_regimes": [rm.scenario_regime for rm in regime_list],
        "input_confidences": [rm.confidence for rm in regime_list],
        "raw_counts": {
            regime: sum(1 for rm in regime_list if rm.scenario_regime == regime)
            for regime in VALID_REGIMES
        },
    }

    # Create and return (INV-P42-1: Observer-only)
    return create_scenario_fusion_field(
        dominant_regime=dominant_regime,
        regime_distribution=distribution,
        fusion_confidence=fusion_confidence,
        regime_entropy=regime_entropy,
        input_count=len(regime_list),
        debug=debug,
    )


# Public exports
__all__ = [
    "clamp",
    "build_regime_distribution",
    "select_dominant_regime",
    "compute_fusion_confidence",
    "compute_regime_entropy",
    "fuse_scenario_regimes",
]
