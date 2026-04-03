"""
Name Resonance System - Domain Matching
=======================================

Layer 4: Match structural profiles against domain patterns.

Tier: Core/Substrate (Tier 1)
Determinism: FULL (same profile + domain → same score)
"""

from typing import Tuple, List

from symbolu_core.name_resonance.types import (
    StructuralProfile,
    DomainPattern,
    DomainCompatibilityResult,
    DimensionScore,
    CompatibilityLevel,
    DIMENSION_NAMES,
)


def compute_domain_compatibility(
    profile: StructuralProfile,
    domain: DomainPattern,
) -> DomainCompatibilityResult:
    """
    Compute compatibility between a structural profile and a domain pattern.

    Method:
    1. For each dimension, compute match score (1 - |actual - ideal|)
    2. Weight match scores by dimension importance
    3. Sum weighted scores for total compatibility
    4. Classify based on threshold

    Args:
        profile: 12D StructuralProfile from Layer 3
        domain: DomainPattern defining requirements

    Returns:
        DomainCompatibilityResult with score, classification, and breakdown
    """
    dimension_scores: List[DimensionScore] = []
    top_matches: List[Tuple[str, float]] = []
    weak_matches: List[Tuple[str, float]] = []

    total_weighted_score = 0.0

    for dim in DIMENSION_NAMES:
        actual = getattr(profile, dim)
        ideal = domain.get_ideal(dim)
        weight = domain.get_weight(dim)

        # Match score: 1.0 when perfect match, 0.0 when maximally different
        distance = abs(actual - ideal)
        match_score = 1.0 - distance

        # Weighted contribution
        weighted_contribution = match_score * weight

        dimension_scores.append(DimensionScore(
            dimension=dim,
            actual=round(actual, 3),
            ideal=round(ideal, 3),
            weight=round(weight, 3),
            match_score=round(match_score, 3),
            weighted_contribution=round(weighted_contribution, 4),
        ))

        total_weighted_score += weighted_contribution

        # Track best and worst matches
        if match_score >= 0.85 and weight >= 0.08:
            top_matches.append((dim, match_score))
        elif match_score <= 0.50 and weight >= 0.08:
            weak_matches.append((dim, match_score))

    # Sort matches by match score
    top_matches.sort(key=lambda x: x[1], reverse=True)
    weak_matches.sort(key=lambda x: x[1])

    # Classify compatibility
    threshold = domain.compatibility_threshold
    if total_weighted_score >= threshold + 0.12:
        classification = CompatibilityLevel.STRONG
    elif total_weighted_score >= threshold:
        classification = CompatibilityLevel.MODERATE
    elif total_weighted_score >= threshold - 0.12:
        classification = CompatibilityLevel.PARTIAL
    else:
        classification = CompatibilityLevel.WEAK

    return DomainCompatibilityResult(
        domain_name=domain.name,
        domain_category=domain.category,
        compatibility_score=round(total_weighted_score, 3),
        classification=classification,
        dimension_breakdown=tuple(dimension_scores),
        rationale=domain.rationale,
        top_matches=tuple(t[0] for t in top_matches[:3]),
        weak_matches=tuple(w[0] for w in weak_matches[:3]),
    )


def match_all_domains(
    profile: StructuralProfile,
    domains: Tuple[DomainPattern, ...],
) -> Tuple[DomainCompatibilityResult, ...]:
    """
    Match a profile against all provided domains.

    Args:
        profile: 12D StructuralProfile
        domains: Tuple of DomainPatterns to match

    Returns:
        Tuple of DomainCompatibilityResults, sorted by score (highest first)
    """
    results = [compute_domain_compatibility(profile, domain) for domain in domains]

    # Sort by compatibility score, descending
    results.sort(key=lambda r: r.compatibility_score, reverse=True)

    return tuple(results)


def get_compatibility_summary(
    results: Tuple[DomainCompatibilityResult, ...],
) -> Tuple[Tuple[str, ...], Tuple[str, ...]]:
    """
    Get summary of high and low compatibility domains.

    Args:
        results: Domain compatibility results

    Returns:
        (high_compatibility_domains, low_compatibility_domains)
    """
    high = tuple(
        r.domain_name for r in results
        if r.classification in (CompatibilityLevel.STRONG, CompatibilityLevel.MODERATE)
    )
    low = tuple(
        r.domain_name for r in results
        if r.classification == CompatibilityLevel.WEAK
    )
    return high, low
