"""
TTOR v1.4 Formulas Module

Pure mathematical functions for Two-Tier Ontology Router calculations.
All functions are:
- Deterministic (no randomness)
- Side-effect free (no external state)
- Type-annotated for strict checking

Formula Categories:
1. Aspect Base Scoring - Computes tier affinity from aspect probabilities
2. Anchor Boosts - Computes experiential anchor contributions
3. Entropy Mix - Combines entropy measures into routing signals
4. Domain Modulation - Adjusts scores based on domain context
5. Final Score Computation - Combines all signals for tier determination
"""

from typing import Dict, Tuple

from .constants import (
    ANCHOR_WEIGHT,
    ASPECT_WEIGHT,
    ENTROPY_WEIGHT,
    H_D_MAX,
    H_G_MAX,
    LOWER_ANCHORS,
    LOWER_ASPECTS,
    REFLECTIVE_DOMAIN_UPPER_BOOST,
    REFLECTIVE_DOMAINS,
    TASK_DOMAIN_LOWER_BOOST,
    TASK_DOMAINS,
    UPPER_ANCHORS,
    UPPER_ASPECTS,
)


def aspect_base_scores(aspect_probs: Dict[str, float]) -> Tuple[float, float]:
    """
    Compute base tier scores from aspect probabilities.

    Aggregates aspect probabilities by tier classification:
    - Lower aspects: Execution, Identity, Form, Cognition
    - Upper aspects: Agency, Reasoning, Purpose, Observation, Core, Universal

    Args:
        aspect_probs: Dictionary mapping aspect names to probabilities [0, 1]

    Returns:
        Tuple of (lower_base, upper_base) scores, each in [0, 1]

    Formula:
        lower_base = sum(prob for aspect in LOWER_ASPECTS) / len(LOWER_ASPECTS)
        upper_base = sum(prob for aspect in UPPER_ASPECTS) / len(UPPER_ASPECTS)
    """
    # Compute lower tier base score
    lower_sum: float = 0.0
    lower_count: int = 0
    for aspect in LOWER_ASPECTS:
        if aspect in aspect_probs:
            lower_sum += aspect_probs[aspect]
            lower_count += 1

    lower_base = lower_sum / max(lower_count, 1)

    # Compute upper tier base score
    upper_sum: float = 0.0
    upper_count: int = 0
    for aspect in UPPER_ASPECTS:
        if aspect in aspect_probs:
            upper_sum += aspect_probs[aspect]
            upper_count += 1

    upper_base = upper_sum / max(upper_count, 1)

    return (lower_base, upper_base)


def anchor_boosts(anchor_scores: Dict[str, float]) -> Tuple[float, float]:
    """
    Compute tier boost contributions from experiential anchors.

    Aggregates anchor scores by tier classification:
    - Lower anchors: Needs, Exchange, Challenge
    - Upper anchors: Belonging, Relation, Change, Meaning, Role, Collective

    Args:
        anchor_scores: Dictionary mapping anchor names to scores [0, 1]

    Returns:
        Tuple of (lower_boost, upper_boost) values, each in [0, 1]

    Formula:
        lower_boost = sum(score for anchor in LOWER_ANCHORS) / len(LOWER_ANCHORS)
        upper_boost = sum(score for anchor in UPPER_ANCHORS) / len(UPPER_ANCHORS)
    """
    # Compute lower anchor boost
    lower_sum: float = 0.0
    lower_count: int = 0
    for anchor in LOWER_ANCHORS:
        score = anchor_scores.get(anchor, 0.0)
        lower_sum += score
        lower_count += 1

    lower_boost = lower_sum / max(lower_count, 1)

    # Compute upper anchor boost
    upper_sum: float = 0.0
    upper_count: int = 0
    for anchor in UPPER_ANCHORS:
        score = anchor_scores.get(anchor, 0.0)
        upper_sum += score
        upper_count += 1

    upper_boost = upper_sum / max(upper_count, 1)

    return (lower_boost, upper_boost)


def entropy_mix(H_D: float, H_G: float) -> Tuple[float, float]:
    """
    Compute entropy-based routing signals from entropy measures.

    Combines dimensional (H_D) and guna (H_G) entropy into:
    - Normalized entropy: Overall uncertainty signal
    - Entropy ratio: Balance between dimensional and guna uncertainty

    Args:
        H_D: Dimensional entropy [0, ln(10)]
        H_G: Guna entropy [0, ln(3)]

    Returns:
        Tuple of (normalized_entropy, entropy_ratio):
        - normalized_entropy: Combined normalized value [0, 1]
        - entropy_ratio: H_G contribution relative to combined [0, 1]

    Formula:
        H_D_norm = H_D / H_D_MAX
        H_G_norm = H_G / H_G_MAX
        normalized_entropy = 0.6 * H_D_norm + 0.4 * H_G_norm
        entropy_ratio = H_G_norm / (H_D_norm + H_G_norm + epsilon)
    """
    # Prevent division by zero
    epsilon: float = 1e-10

    # Normalize entropy values to [0, 1]
    H_D_norm = H_D / H_D_MAX if H_D_MAX > 0 else 0.0
    H_G_norm = H_G / H_G_MAX if H_G_MAX > 0 else 0.0

    # Clamp to [0, 1] for safety
    H_D_norm = max(0.0, min(1.0, H_D_norm))
    H_G_norm = max(0.0, min(1.0, H_G_norm))

    # Weighted combination: dimensional entropy has higher weight (0.6)
    # as it captures more dimensional uncertainty
    normalized_entropy = 0.6 * H_D_norm + 0.4 * H_G_norm

    # Compute ratio of guna entropy to total entropy
    # High ratio indicates more guna-based (emotional/quality) uncertainty
    total_norm = H_D_norm + H_G_norm + epsilon
    entropy_ratio = H_G_norm / total_norm

    return (normalized_entropy, entropy_ratio)


def domain_modulation(domain: str) -> Tuple[float, float]:
    """
    Compute domain-based score modulations.

    Different domains favor different tiers:
    - Task domains (code, math): Boost lower tier
    - Reflective domains (therapy, philosophy): Boost upper tier
    - Other domains: No modulation

    Args:
        domain: Domain classification string

    Returns:
        Tuple of (lower_mod, upper_mod) modulation values

    Formula:
        If domain in TASK_DOMAINS: lower_mod = +0.1, upper_mod = 0
        If domain in REFLECTIVE_DOMAINS: lower_mod = 0, upper_mod = +0.1
        Otherwise: lower_mod = 0, upper_mod = 0
    """
    lower_mod: float = 0.0
    upper_mod: float = 0.0

    if domain in TASK_DOMAINS:
        lower_mod = TASK_DOMAIN_LOWER_BOOST
    elif domain in REFLECTIVE_DOMAINS:
        upper_mod = REFLECTIVE_DOMAIN_UPPER_BOOST

    return (lower_mod, upper_mod)


def compute_entropy_boosts(
    normalized_entropy: float,
    entropy_ratio: float,
) -> Tuple[float, float]:
    """
    Compute entropy-based tier boosts.

    High entropy generally favors upper tier (more abstract processing needed).
    High guna ratio (emotional uncertainty) also favors upper tier.

    Args:
        normalized_entropy: Combined normalized entropy [0, 1]
        entropy_ratio: Guna contribution ratio [0, 1]

    Returns:
        Tuple of (lower_entropy_boost, upper_entropy_boost)

    Formula:
        lower_entropy_boost = (1 - normalized_entropy) * 0.5
        upper_entropy_boost = normalized_entropy * 0.5 + entropy_ratio * 0.3
    """
    # Low entropy favors lower tier (concrete, certain processing)
    lower_entropy_boost = (1.0 - normalized_entropy) * 0.5

    # High entropy favors upper tier (abstract, meaning-focused processing)
    # Guna ratio adds additional upper tier affinity
    upper_entropy_boost = normalized_entropy * 0.5 + entropy_ratio * 0.3

    return (lower_entropy_boost, upper_entropy_boost)


def final_scores(
    lower_base: float,
    upper_base: float,
    lower_anchor_boost: float,
    upper_anchor_boost: float,
    lower_entropy_boost: float,
    upper_entropy_boost: float,
    lower_domain_mod: float,
    upper_domain_mod: float,
) -> Tuple[float, float]:
    """
    Compute final tier scores by combining all signal components.

    Combines aspect base scores, anchor boosts, entropy boosts, and
    domain modulations using weighted formula.

    Args:
        lower_base: Lower tier aspect base score [0, 1]
        upper_base: Upper tier aspect base score [0, 1]
        lower_anchor_boost: Lower tier anchor boost [0, 1]
        upper_anchor_boost: Upper tier anchor boost [0, 1]
        lower_entropy_boost: Lower tier entropy boost
        upper_entropy_boost: Upper tier entropy boost
        lower_domain_mod: Lower tier domain modulation
        upper_domain_mod: Upper tier domain modulation

    Returns:
        Tuple of (final_lower, final_upper) scores

    Formula:
        final_lower = (ASPECT_WEIGHT * lower_base +
                       ANCHOR_WEIGHT * lower_anchor_boost +
                       ENTROPY_WEIGHT * lower_entropy_boost +
                       lower_domain_mod)

        final_upper = (ASPECT_WEIGHT * upper_base +
                       ANCHOR_WEIGHT * upper_anchor_boost +
                       ENTROPY_WEIGHT * upper_entropy_boost +
                       upper_domain_mod)
    """
    final_lower = (
        ASPECT_WEIGHT * lower_base
        + ANCHOR_WEIGHT * lower_anchor_boost
        + ENTROPY_WEIGHT * lower_entropy_boost
        + lower_domain_mod
    )

    final_upper = (
        ASPECT_WEIGHT * upper_base
        + ANCHOR_WEIGHT * upper_anchor_boost
        + ENTROPY_WEIGHT * upper_entropy_boost
        + upper_domain_mod
    )

    return (final_lower, final_upper)


def compute_conflict_score(
    lower_anchor_boost: float,
    upper_anchor_boost: float,
) -> float:
    """
    Compute anchor conflict score.

    Measures the degree of conflict between lower and upper anchor signals.
    High conflict suggests hybrid processing may be needed.

    Args:
        lower_anchor_boost: Lower tier anchor boost [0, 1]
        upper_anchor_boost: Upper tier anchor boost [0, 1]

    Returns:
        Conflict score [0, 1]: 1.0 = maximum conflict (equal strong signals)

    Formula:
        conflict = 2 * min(lower, upper) / (lower + upper + epsilon)
    """
    epsilon: float = 1e-10
    total = lower_anchor_boost + upper_anchor_boost + epsilon

    # Conflict is highest when both signals are equal and strong
    min_signal = min(lower_anchor_boost, upper_anchor_boost)
    conflict = 2.0 * min_signal / total

    return min(1.0, conflict)


def normalize_to_unit_interval(value: float, min_val: float, max_val: float) -> float:
    """
    Normalize a value to [0, 1] interval.

    Args:
        value: Value to normalize
        min_val: Minimum of input range
        max_val: Maximum of input range

    Returns:
        Normalized value in [0, 1]
    """
    if max_val <= min_val:
        return 0.0

    normalized = (value - min_val) / (max_val - min_val)
    return max(0.0, min(1.0, normalized))
