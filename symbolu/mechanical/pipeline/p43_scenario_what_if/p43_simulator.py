"""
Phase 43: Scenario What-If Simulation Logic

Deterministic generation of what-if scenario variants from
ScenarioFusionField (Phase 42).

Core Simulation Logic:
    Step 1: Guard (return None if no base input)
    Step 2: Define allowed perturbations (exactly 4)
    Step 3: Generate variants (apply each perturbation deterministically)
    Step 4: Resolve resulting regime
    Step 5: Package output

Invariants:
    INV-P43-1: Simulation only (no prediction, no likelihoods)
    INV-P43-2: Deterministic perturbations (no randomness, seeded noise only if fixed)
    INV-P43-3: Bounded exploration (exactly four variants, no more)
    INV-P43-4: No authority impact (results never influence regime, discourse, or action)
    INV-P43-5: Absence-safe (no base input -> no output)
"""

from typing import Dict, List, Optional, Tuple

from symbolu.mechanical.pipeline.p42_scenario_fusion.p42_schema import (
    ScenarioFusionField,
)

from .p43_schema import (
    CONFIDENCE_DROP_DELTA,
    DOMINANT_THRESHOLD,
    ENTROPY_SHIFT_DELTA,
    NOISE_INJECTION_DELTA,
    VALID_PERTURBATIONS,
    VALID_REGIMES,
    ScenarioRegime,
    ScenarioVariant,
    ScenarioWhatIfSet,
    create_scenario_variant,
    create_scenario_what_if_set,
)


def clamp(value: float, min_val: float = 0.0, max_val: float = 1.0) -> float:
    """Clamp a value to [min_val, max_val]."""
    return max(min_val, min(max_val, value))


def resolve_regime_from_distribution(
    distribution: Dict[str, float],
) -> ScenarioRegime:
    """
    Step 4: Resolve resulting regime from distribution.

    Rules (same as Phase 42):
        - If max(regime_distribution) >= 0.60 -> dominant
        - Else -> "ambiguous_mixed"

    No new regime logic allowed.

    Args:
        distribution: Regime distribution dict (must sum to ~1.0)

    Returns:
        The resulting regime label
    """
    max_proportion = 0.0
    max_regime: Optional[str] = None

    for regime in VALID_REGIMES:
        proportion = distribution.get(regime, 0.0)
        if proportion > max_proportion:
            max_proportion = proportion
            max_regime = regime

    if max_proportion >= DOMINANT_THRESHOLD and max_regime is not None:
        return max_regime  # type: ignore[return-value]

    return "ambiguous_mixed"


def get_second_highest_regime(
    distribution: Dict[str, float],
    exclude_regime: str,
) -> str:
    """
    Get the regime with second-highest proportion in distribution.

    Used for regime_flip perturbation.

    Args:
        distribution: Regime distribution dict
        exclude_regime: The regime to exclude (dominant regime)

    Returns:
        The second-highest regime, or first valid non-excluded regime
    """
    sorted_regimes = sorted(
        [(r, distribution.get(r, 0.0)) for r in VALID_REGIMES if r != exclude_regime],
        key=lambda x: x[1],
        reverse=True,
    )

    if sorted_regimes:
        return sorted_regimes[0][0]

    # Fallback: return first valid regime that isn't excluded
    for regime in VALID_REGIMES:
        if regime != exclude_regime:
            return regime

    # Should never happen, but return ambiguous_mixed as last resort
    return "ambiguous_mixed"


def apply_entropy_shift(
    base_entropy: float,
    base_confidence: float,
    base_distribution: Dict[str, float],
) -> Tuple[ScenarioRegime, float, float]:
    """
    Apply entropy_shift perturbation.

    Increase entropy by +0.15 (clamped to [0, 1]).
    This simulates increased uncertainty/disagreement.

    INV-P43-2: Deterministic - fixed delta, no randomness.

    Returns:
        (resulting_regime, delta_entropy, delta_confidence)
    """
    # Entropy shift doesn't directly change confidence in this model
    # But higher entropy might indicate regime becomes ambiguous
    new_entropy = clamp(base_entropy + ENTROPY_SHIFT_DELTA)
    delta_entropy = new_entropy - base_entropy
    delta_confidence = 0.0  # Entropy shift doesn't change confidence

    # Simulate effect: if entropy is high, regime becomes ambiguous
    # We use existing distribution but check if high entropy pushes to ambiguous
    resulting_regime = resolve_regime_from_distribution(base_distribution)
    if new_entropy > 0.85:
        resulting_regime = "ambiguous_mixed"

    return resulting_regime, delta_entropy, delta_confidence


def apply_confidence_drop(
    base_entropy: float,
    base_confidence: float,
    base_distribution: Dict[str, float],
) -> Tuple[ScenarioRegime, float, float]:
    """
    Apply confidence_drop perturbation.

    Reduce fusion_confidence by -0.20 (clamped to [0, 1]).
    This simulates reduced certainty in the scenario field.

    INV-P43-2: Deterministic - fixed delta, no randomness.

    Returns:
        (resulting_regime, delta_entropy, delta_confidence)
    """
    new_confidence = clamp(base_confidence - CONFIDENCE_DROP_DELTA)
    delta_confidence = new_confidence - base_confidence  # Will be negative
    delta_entropy = 0.0  # Confidence drop doesn't change entropy

    # Regime stays the same (confidence affects certainty, not classification)
    resulting_regime = resolve_regime_from_distribution(base_distribution)

    return resulting_regime, delta_entropy, delta_confidence


def apply_regime_flip(
    base_entropy: float,
    base_confidence: float,
    base_distribution: Dict[str, float],
    base_regime: str,
) -> Tuple[ScenarioRegime, float, float]:
    """
    Apply regime_flip perturbation.

    Swap dominant regime with second-highest regime.
    This simulates a scenario where the secondary regime becomes dominant.

    INV-P43-2: Deterministic - based on fixed distribution ordering.

    Returns:
        (resulting_regime, delta_entropy, delta_confidence)
    """
    # Get second-highest regime
    second_regime = get_second_highest_regime(base_distribution, base_regime)

    # Create modified distribution with swapped values
    modified_dist = dict(base_distribution)
    dominant_val = modified_dist.get(base_regime, 0.0)
    second_val = modified_dist.get(second_regime, 0.0)

    modified_dist[base_regime] = second_val
    modified_dist[second_regime] = dominant_val

    # Resolve regime from modified distribution
    resulting_regime = resolve_regime_from_distribution(modified_dist)

    # No direct entropy/confidence change from flip
    # But we can compute implied entropy change from distribution change
    delta_entropy = 0.0
    delta_confidence = 0.0

    return resulting_regime, delta_entropy, delta_confidence


def apply_noise_injection(
    base_entropy: float,
    base_confidence: float,
    base_distribution: Dict[str, float],
) -> Tuple[ScenarioRegime, float, float]:
    """
    Apply noise_injection perturbation.

    Add +/- 0.05 bounded noise to distribution, renormalize.
    Uses fixed pattern (not random) for determinism.

    INV-P43-2: Deterministic - fixed noise pattern, no randomness.

    The noise pattern is: [+delta, -delta, +delta/2, -delta/2]
    Applied to regimes in canonical order, then renormalized.

    Returns:
        (resulting_regime, delta_entropy, delta_confidence)
    """
    delta = NOISE_INJECTION_DELTA

    # Fixed noise pattern (deterministic)
    noise_pattern = [+delta, -delta, +delta / 2, -delta / 2]

    # Apply noise to distribution
    modified_dist: Dict[str, float] = {}
    for i, regime in enumerate(VALID_REGIMES):
        base_val = base_distribution.get(regime, 0.0)
        noise = noise_pattern[i % len(noise_pattern)]
        modified_dist[regime] = max(0.0, base_val + noise)

    # Renormalize
    total = sum(modified_dist.values())
    if total > 0:
        for regime in modified_dist:
            modified_dist[regime] /= total

    # Resolve regime from modified distribution
    resulting_regime = resolve_regime_from_distribution(modified_dist)

    # Small changes from noise
    delta_entropy = 0.0  # Noise doesn't systematically change entropy
    delta_confidence = 0.0  # Noise doesn't change confidence

    return resulting_regime, delta_entropy, delta_confidence


def simulate_what_if_variants(
    fusion_field: ScenarioFusionField,
) -> Optional[ScenarioWhatIfSet]:
    """
    Main simulation function: Generate what-if variants from
    a ScenarioFusionField.

    This function implements all 5 steps of the simulation logic:
        1. Guard (return None if input is None)
        2. Define allowed perturbations
        3. Generate variants
        4. Resolve resulting regimes
        5. Package output

    Invariants enforced:
        INV-P43-1: Simulation only (pure possibility exploration)
        INV-P43-2: Deterministic (no randomness, fixed perturbations)
        INV-P43-3: Bounded exploration (exactly 4 variants)
        INV-P43-4: No authority impact (observer-only output)
        INV-P43-5: Absence-safe (returns None for None input)

    Args:
        fusion_field: ScenarioFusionField from Phase 42

    Returns:
        ScenarioWhatIfSet if input is valid, None otherwise
    """
    # Step 1: Guard (INV-P43-5: Absence-safe)
    if fusion_field is None:
        return None

    # Extract base values
    base_regime = fusion_field.dominant_regime
    base_entropy = fusion_field.regime_entropy
    base_confidence = fusion_field.fusion_confidence
    base_distribution = dict(fusion_field.regime_distribution)

    # Step 2 & 3: Generate exactly 4 variants (INV-P43-3)
    variants: List[ScenarioVariant] = []

    # Variant 1: entropy_shift
    regime_1, delta_e_1, delta_c_1 = apply_entropy_shift(
        base_entropy, base_confidence, base_distribution
    )
    variants.append(
        create_scenario_variant(
            variant_id="v1_entropy_shift",
            perturbation_type="entropy_shift",
            resulting_regime=regime_1,
            delta_entropy=delta_e_1,
            delta_confidence=delta_c_1,
        )
    )

    # Variant 2: confidence_drop
    regime_2, delta_e_2, delta_c_2 = apply_confidence_drop(
        base_entropy, base_confidence, base_distribution
    )
    variants.append(
        create_scenario_variant(
            variant_id="v2_confidence_drop",
            perturbation_type="confidence_drop",
            resulting_regime=regime_2,
            delta_entropy=delta_e_2,
            delta_confidence=delta_c_2,
        )
    )

    # Variant 3: regime_flip
    regime_3, delta_e_3, delta_c_3 = apply_regime_flip(
        base_entropy, base_confidence, base_distribution, base_regime
    )
    variants.append(
        create_scenario_variant(
            variant_id="v3_regime_flip",
            perturbation_type="regime_flip",
            resulting_regime=regime_3,
            delta_entropy=delta_e_3,
            delta_confidence=delta_c_3,
        )
    )

    # Variant 4: noise_injection
    regime_4, delta_e_4, delta_c_4 = apply_noise_injection(
        base_entropy, base_confidence, base_distribution
    )
    variants.append(
        create_scenario_variant(
            variant_id="v4_noise_injection",
            perturbation_type="noise_injection",
            resulting_regime=regime_4,
            delta_entropy=delta_e_4,
            delta_confidence=delta_c_4,
        )
    )

    # Step 5: Package output (INV-P43-4: observer_only=True)
    debug = {
        "base_regime": base_regime,
        "base_entropy": base_entropy,
        "base_confidence": base_confidence,
        "base_distribution": base_distribution,
    }

    return create_scenario_what_if_set(
        base_regime=base_regime,
        what_if_variants=variants,
        debug=debug,
    )


# Public exports
__all__ = [
    "clamp",
    "resolve_regime_from_distribution",
    "get_second_highest_regime",
    "apply_entropy_shift",
    "apply_confidence_drop",
    "apply_regime_flip",
    "apply_noise_injection",
    "simulate_what_if_variants",
]
