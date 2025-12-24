"""
Name Resonance System - Domain Semantic Profiles
=================================================

Provides the S term (Semantic Type Coherence) for name↔domain matching.

S answers: "Does this name's semantic signature align with what this
career domain semantically requires?"

Key properties of S for name↔domain:
- NON-PHONEMIC: Domain profiles are externally defined, not derived from phonemes
- Source-independent: Provides validation axis separate from C and R
- Deterministic: Same name + domain → same S score

This module defines:
1. Semantic traits (derived from 12D ontological layers)
2. Domain semantic profiles (what each career requires)
3. S computation (name's inferred traits vs domain's required traits)

The C×R×S formula for name↔domain:
- C = Ontological constraint (phonemic → 12D layers alignment)
- R = Structural realization (phonemic → 12D profile match)
- S = Semantic type coherence (inferred traits vs required traits)

Tier: Core/Substrate (Tier 1)
Authority: NONE (signal processing only)
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Tuple, FrozenSet, List

from symbolu.resonance.types import LAYER_NAMES


# =============================================================================
# Semantic Traits (Derived from Ontological Layers)
# =============================================================================

class SemanticTrait(Enum):
    """
    Semantic traits that can be inferred from ontological layer dominance.

    These represent the KIND of person/energy a name resonates with.
    """
    # Cognitive traits
    CONTEMPLATIVE = "contemplative"       # Thinking, reflection
    ANALYTICAL = "analytical"             # Reasoning, logic
    CREATIVE = "creative"                 # Forming, building new things

    # Action traits
    DYNAMIC = "dynamic"                   # Acting, force, movement
    DIRECTIVE = "directive"               # Leading, guiding, controlling
    PURPOSEFUL = "purposeful"             # Goal-oriented, intentional

    # Perceptual traits
    OBSERVANT = "observant"               # Meta-observing, awareness
    INTUITIVE = "intuitive"               # Tagging, sensing, classifying

    # Relational traits
    HARMONIZING = "harmonizing"           # Unifying, connecting
    TRANSCENDENT = "transcendent"         # Absolving, releasing, peace

    # Energy traits
    SUSTAINED = "sustained"               # Long-duration energy
    EXPLOSIVE = "explosive"               # Quick, forceful energy
    BALANCED = "balanced"                 # Even, stable energy
    FLOWING = "flowing"                   # Continuous, smooth energy


# =============================================================================
# Ontological Layer → Semantic Traits Mapping
# =============================================================================

# Which semantic traits each ontological layer contributes to
LAYER_TO_TRAITS: Dict[str, Tuple[Tuple[SemanticTrait, float], ...]] = {
    "O1_POTENTIAL": (
        (SemanticTrait.CONTEMPLATIVE, 0.9),
        (SemanticTrait.SUSTAINED, 0.7),
        (SemanticTrait.BALANCED, 0.5),
    ),
    "O2_IDENTITY": (
        (SemanticTrait.INTUITIVE, 0.8),
        (SemanticTrait.ANALYTICAL, 0.5),
        (SemanticTrait.BALANCED, 0.4),
    ),
    "O3_EXECUTION": (
        (SemanticTrait.DYNAMIC, 0.9),
        (SemanticTrait.EXPLOSIVE, 0.7),
        (SemanticTrait.DIRECTIVE, 0.4),
    ),
    "O4_STRUCTURE": (
        (SemanticTrait.CREATIVE, 0.9),
        (SemanticTrait.PURPOSEFUL, 0.6),
        (SemanticTrait.BALANCED, 0.5),
    ),
    "O5_COGNITION": (
        (SemanticTrait.CONTEMPLATIVE, 0.8),
        (SemanticTrait.OBSERVANT, 0.7),
        (SemanticTrait.ANALYTICAL, 0.5),
    ),
    "O6_AGENCY": (
        (SemanticTrait.DIRECTIVE, 0.9),
        (SemanticTrait.PURPOSEFUL, 0.7),
        (SemanticTrait.DYNAMIC, 0.4),
    ),
    "O7_REASONING": (
        (SemanticTrait.ANALYTICAL, 0.9),
        (SemanticTrait.CONTEMPLATIVE, 0.5),
        (SemanticTrait.SUSTAINED, 0.5),
    ),
    "O8_PURPOSE": (
        (SemanticTrait.PURPOSEFUL, 0.9),
        (SemanticTrait.DIRECTIVE, 0.5),
        (SemanticTrait.HARMONIZING, 0.4),
    ),
    "O9_WITNESSES": (
        (SemanticTrait.OBSERVANT, 0.9),
        (SemanticTrait.CONTEMPLATIVE, 0.6),
        (SemanticTrait.BALANCED, 0.5),
    ),
    "O10_UNIFYING": (
        (SemanticTrait.HARMONIZING, 0.9),
        (SemanticTrait.FLOWING, 0.7),
        (SemanticTrait.BALANCED, 0.5),
    ),
    "O11_INTEGRATION": (
        (SemanticTrait.HARMONIZING, 0.8),
        (SemanticTrait.PURPOSEFUL, 0.6),
        (SemanticTrait.SUSTAINED, 0.5),
    ),
    "O12_ABSOLVING": (
        (SemanticTrait.TRANSCENDENT, 0.9),
        (SemanticTrait.FLOWING, 0.6),
        (SemanticTrait.SUSTAINED, 0.5),
    ),
}


# =============================================================================
# Domain Semantic Profiles (NON-PHONEMIC - Externally Defined)
# =============================================================================

@dataclass(frozen=True)
class DomainSemanticProfile:
    """
    Semantic profile defining what a domain/career requires.

    This is NON-PHONEMIC - defined by domain knowledge, not phonemes.
    """
    domain_name: str

    # Required traits (must have) with importance weights
    required_traits: Tuple[Tuple[SemanticTrait, float], ...]

    # Complementary traits (nice to have)
    complementary_traits: FrozenSet[SemanticTrait]

    # Conflicting traits (negative indicators)
    conflicting_traits: FrozenSet[SemanticTrait]

    # Description of the domain's semantic requirements
    rationale: str


# Domain semantic profiles - what each career semantically requires
DOMAIN_SEMANTIC_PROFILES: Dict[str, DomainSemanticProfile] = {
    # Sports
    "Golf": DomainSemanticProfile(
        domain_name="Golf",
        required_traits=(
            (SemanticTrait.BALANCED, 0.9),
            (SemanticTrait.SUSTAINED, 0.8),
            (SemanticTrait.CONTEMPLATIVE, 0.6),
            (SemanticTrait.PURPOSEFUL, 0.7),
        ),
        complementary_traits=frozenset({
            SemanticTrait.OBSERVANT,
            SemanticTrait.FLOWING,
        }),
        conflicting_traits=frozenset({
            SemanticTrait.EXPLOSIVE,
        }),
        rationale="Golf requires patience, sustained focus, balance, and purposeful action",
    ),
    "Tennis": DomainSemanticProfile(
        domain_name="Tennis",
        required_traits=(
            (SemanticTrait.DYNAMIC, 0.9),
            (SemanticTrait.EXPLOSIVE, 0.8),
            (SemanticTrait.DIRECTIVE, 0.6),
            (SemanticTrait.PURPOSEFUL, 0.7),
        ),
        complementary_traits=frozenset({
            SemanticTrait.ANALYTICAL,
            SemanticTrait.BALANCED,
        }),
        conflicting_traits=frozenset({
            SemanticTrait.TRANSCENDENT,
        }),
        rationale="Tennis requires explosive action, dynamic movement, and directive control",
    ),
    "Swimming": DomainSemanticProfile(
        domain_name="Swimming",
        required_traits=(
            (SemanticTrait.FLOWING, 0.9),
            (SemanticTrait.SUSTAINED, 0.8),
            (SemanticTrait.HARMONIZING, 0.6),
            (SemanticTrait.DYNAMIC, 0.5),
        ),
        complementary_traits=frozenset({
            SemanticTrait.BALANCED,
            SemanticTrait.PURPOSEFUL,
        }),
        conflicting_traits=frozenset({
            SemanticTrait.EXPLOSIVE,
        }),
        rationale="Swimming requires flow, sustained effort, and harmony with the water",
    ),
    "Basketball": DomainSemanticProfile(
        domain_name="Basketball",
        required_traits=(
            (SemanticTrait.DYNAMIC, 0.9),
            (SemanticTrait.EXPLOSIVE, 0.7),
            (SemanticTrait.HARMONIZING, 0.7),
            (SemanticTrait.DIRECTIVE, 0.6),
        ),
        complementary_traits=frozenset({
            SemanticTrait.PURPOSEFUL,
            SemanticTrait.INTUITIVE,
        }),
        conflicting_traits=frozenset({
            SemanticTrait.CONTEMPLATIVE,
        }),
        rationale="Basketball requires dynamic action, explosive plays, and team harmony",
    ),
    "Football": DomainSemanticProfile(
        domain_name="Football",
        required_traits=(
            (SemanticTrait.DYNAMIC, 0.9),
            (SemanticTrait.EXPLOSIVE, 0.8),
            (SemanticTrait.DIRECTIVE, 0.7),
            (SemanticTrait.PURPOSEFUL, 0.6),
        ),
        complementary_traits=frozenset({
            SemanticTrait.HARMONIZING,
        }),
        conflicting_traits=frozenset({
            SemanticTrait.TRANSCENDENT,
            SemanticTrait.CONTEMPLATIVE,
        }),
        rationale="Football requires explosive dynamic action and directive leadership",
    ),

    # Careers
    "Engineering": DomainSemanticProfile(
        domain_name="Engineering",
        required_traits=(
            (SemanticTrait.ANALYTICAL, 0.9),
            (SemanticTrait.CREATIVE, 0.8),
            (SemanticTrait.PURPOSEFUL, 0.7),
            (SemanticTrait.SUSTAINED, 0.6),
        ),
        complementary_traits=frozenset({
            SemanticTrait.CONTEMPLATIVE,
            SemanticTrait.BALANCED,
        }),
        conflicting_traits=frozenset({
            SemanticTrait.EXPLOSIVE,
        }),
        rationale="Engineering requires analytical thinking, creative problem-solving, sustained focus",
    ),
    "Law": DomainSemanticProfile(
        domain_name="Law",
        required_traits=(
            (SemanticTrait.ANALYTICAL, 0.9),
            (SemanticTrait.DIRECTIVE, 0.8),
            (SemanticTrait.PURPOSEFUL, 0.7),
            (SemanticTrait.CONTEMPLATIVE, 0.5),
        ),
        complementary_traits=frozenset({
            SemanticTrait.SUSTAINED,
            SemanticTrait.OBSERVANT,
        }),
        conflicting_traits=frozenset({
            SemanticTrait.TRANSCENDENT,
        }),
        rationale="Law requires analytical reasoning, directive argumentation, purposeful advocacy",
    ),
    "Medicine": DomainSemanticProfile(
        domain_name="Medicine",
        required_traits=(
            (SemanticTrait.ANALYTICAL, 0.8),
            (SemanticTrait.HARMONIZING, 0.8),
            (SemanticTrait.SUSTAINED, 0.7),
            (SemanticTrait.PURPOSEFUL, 0.7),
        ),
        complementary_traits=frozenset({
            SemanticTrait.CONTEMPLATIVE,
            SemanticTrait.OBSERVANT,
            SemanticTrait.INTUITIVE,
        }),
        conflicting_traits=frozenset(),
        rationale="Medicine requires analytical diagnosis, harmonizing care, sustained attention",
    ),
    "Finance": DomainSemanticProfile(
        domain_name="Finance",
        required_traits=(
            (SemanticTrait.ANALYTICAL, 0.9),
            (SemanticTrait.PURPOSEFUL, 0.8),
            (SemanticTrait.DIRECTIVE, 0.6),
            (SemanticTrait.DYNAMIC, 0.5),
        ),
        complementary_traits=frozenset({
            SemanticTrait.SUSTAINED,
            SemanticTrait.BALANCED,
        }),
        conflicting_traits=frozenset({
            SemanticTrait.TRANSCENDENT,
        }),
        rationale="Finance requires analytical precision, purposeful strategy, directive action",
    ),
    "Creative Arts": DomainSemanticProfile(
        domain_name="Creative Arts",
        required_traits=(
            (SemanticTrait.CREATIVE, 0.9),
            (SemanticTrait.CONTEMPLATIVE, 0.7),
            (SemanticTrait.FLOWING, 0.7),
            (SemanticTrait.INTUITIVE, 0.6),
        ),
        complementary_traits=frozenset({
            SemanticTrait.OBSERVANT,
            SemanticTrait.TRANSCENDENT,
        }),
        conflicting_traits=frozenset({
            SemanticTrait.DIRECTIVE,
        }),
        rationale="Creative arts require creative expression, contemplative depth, flowing inspiration",
    ),
    "Teaching": DomainSemanticProfile(
        domain_name="Teaching",
        required_traits=(
            (SemanticTrait.HARMONIZING, 0.9),
            (SemanticTrait.DIRECTIVE, 0.7),
            (SemanticTrait.CONTEMPLATIVE, 0.6),
            (SemanticTrait.SUSTAINED, 0.7),
        ),
        complementary_traits=frozenset({
            SemanticTrait.PURPOSEFUL,
            SemanticTrait.OBSERVANT,
        }),
        conflicting_traits=frozenset(),
        rationale="Teaching requires harmonizing connection, directive guidance, sustained patience",
    ),
    "Technology": DomainSemanticProfile(
        domain_name="Technology",
        required_traits=(
            (SemanticTrait.ANALYTICAL, 0.9),
            (SemanticTrait.CREATIVE, 0.8),
            (SemanticTrait.PURPOSEFUL, 0.7),
            (SemanticTrait.SUSTAINED, 0.6),
        ),
        complementary_traits=frozenset({
            SemanticTrait.DYNAMIC,
            SemanticTrait.CONTEMPLATIVE,
        }),
        conflicting_traits=frozenset(),
        rationale="Technology requires analytical problem-solving, creative innovation, sustained focus",
    ),
    "Leadership": DomainSemanticProfile(
        domain_name="Leadership",
        required_traits=(
            (SemanticTrait.DIRECTIVE, 0.9),
            (SemanticTrait.PURPOSEFUL, 0.9),
            (SemanticTrait.HARMONIZING, 0.7),
            (SemanticTrait.OBSERVANT, 0.6),
        ),
        complementary_traits=frozenset({
            SemanticTrait.DYNAMIC,
            SemanticTrait.SUSTAINED,
        }),
        conflicting_traits=frozenset({
            SemanticTrait.TRANSCENDENT,
        }),
        rationale="Leadership requires directive vision, purposeful action, harmonizing teams",
    ),
    "Research": DomainSemanticProfile(
        domain_name="Research",
        required_traits=(
            (SemanticTrait.CONTEMPLATIVE, 0.9),
            (SemanticTrait.ANALYTICAL, 0.9),
            (SemanticTrait.SUSTAINED, 0.8),
            (SemanticTrait.OBSERVANT, 0.7),
        ),
        complementary_traits=frozenset({
            SemanticTrait.CREATIVE,
            SemanticTrait.PURPOSEFUL,
        }),
        conflicting_traits=frozenset({
            SemanticTrait.EXPLOSIVE,
        }),
        rationale="Research requires contemplative depth, analytical rigor, sustained inquiry",
    ),
    "Sales": DomainSemanticProfile(
        domain_name="Sales",
        required_traits=(
            (SemanticTrait.DYNAMIC, 0.9),
            (SemanticTrait.DIRECTIVE, 0.8),
            (SemanticTrait.HARMONIZING, 0.7),
            (SemanticTrait.PURPOSEFUL, 0.8),
        ),
        complementary_traits=frozenset({
            SemanticTrait.INTUITIVE,
            SemanticTrait.EXPLOSIVE,
        }),
        conflicting_traits=frozenset({
            SemanticTrait.CONTEMPLATIVE,
        }),
        rationale="Sales requires dynamic energy, directive persuasion, harmonizing relationships",
    ),
    "Entrepreneurship": DomainSemanticProfile(
        domain_name="Entrepreneurship",
        required_traits=(
            (SemanticTrait.CREATIVE, 0.9),
            (SemanticTrait.DYNAMIC, 0.8),
            (SemanticTrait.PURPOSEFUL, 0.9),
            (SemanticTrait.DIRECTIVE, 0.7),
        ),
        complementary_traits=frozenset({
            SemanticTrait.ANALYTICAL,
            SemanticTrait.EXPLOSIVE,
        }),
        conflicting_traits=frozenset({
            SemanticTrait.TRANSCENDENT,
        }),
        rationale="Entrepreneurship requires creative vision, dynamic action, purposeful drive",
    ),
}


# =============================================================================
# Semantic Trait Computation from Ontological Layers
# =============================================================================

def compute_semantic_traits(
    ontological_vector: Tuple[Tuple[str, float], ...],
) -> Dict[SemanticTrait, float]:
    """
    Compute semantic trait scores from ontological layer values.

    Args:
        ontological_vector: 12D ontological layer values as (layer_name, value) tuples

    Returns:
        Dict mapping SemanticTrait to score [0, 1]
    """
    # Initialize trait scores
    trait_scores: Dict[SemanticTrait, float] = {trait: 0.0 for trait in SemanticTrait}

    # Accumulate weighted trait contributions from each layer
    for layer_name, layer_value in ontological_vector:
        if layer_name in LAYER_TO_TRAITS:
            for trait, weight in LAYER_TO_TRAITS[layer_name]:
                trait_scores[trait] += layer_value * weight

    # Normalize to [0, 1]
    max_score = max(trait_scores.values()) if trait_scores else 1.0
    if max_score > 0:
        trait_scores = {
            trait: min(1.0, score / max_score)
            for trait, score in trait_scores.items()
        }

    return trait_scores


def get_dominant_traits(
    trait_scores: Dict[SemanticTrait, float],
    threshold: float = 0.5,
    top_n: int = 4,
) -> List[Tuple[SemanticTrait, float]]:
    """
    Get the dominant semantic traits (above threshold or top N).

    Args:
        trait_scores: Dict of trait scores
        threshold: Minimum score to be considered dominant
        top_n: Maximum number of traits to return

    Returns:
        List of (trait, score) tuples, sorted by score descending
    """
    # Filter by threshold and sort
    filtered = [
        (trait, score) for trait, score in trait_scores.items()
        if score >= threshold
    ]
    sorted_traits = sorted(filtered, key=lambda x: x[1], reverse=True)

    # Return top N
    return sorted_traits[:top_n]


# =============================================================================
# S Computation: Semantic Type Coherence
# =============================================================================

@dataclass(frozen=True)
class SemanticCoherenceResult:
    """
    Result of semantic type coherence (S) computation for name↔domain.
    """
    coherence: float  # S ∈ [0, 1]

    # Name's semantic profile
    name_traits: Tuple[Tuple[str, float], ...]  # (trait_name, score)
    name_dominant_traits: Tuple[str, ...]

    # Domain's semantic requirements
    domain_name: str
    domain_required_traits: Tuple[str, ...]
    domain_complementary: Tuple[str, ...]
    domain_conflicting: Tuple[str, ...]

    # Match analysis
    matched_required: Tuple[str, ...]     # Name has domain's required traits
    matched_complementary: Tuple[str, ...]  # Name has domain's complementary traits
    conflicts_found: Tuple[str, ...]       # Name has domain's conflicting traits

    # Explanation
    rationale: str


def compute_semantic_coherence(
    ontological_vector: Tuple[Tuple[str, float], ...],
    domain_name: str,
) -> SemanticCoherenceResult:
    """
    Compute semantic type coherence (S) between a name and a domain.

    This is the S term in C×R×S for name↔domain matching.

    S answers: "Does this name's inferred semantic type align with
    what this career domain semantically requires?"

    Args:
        ontological_vector: Name's 12D ontological layer values
        domain_name: Name of the domain to match against

    Returns:
        SemanticCoherenceResult with S score and analysis

    Example:
        >>> # Get ontological vector for a name
        >>> onto_vec = get_ontological_vector("Campbell")
        >>> # Compute S for Golf domain
        >>> result = compute_semantic_coherence(onto_vec, "Golf")
        >>> print(f"S = {result.coherence}")
    """
    # Get domain profile (or create default)
    if domain_name in DOMAIN_SEMANTIC_PROFILES:
        domain_profile = DOMAIN_SEMANTIC_PROFILES[domain_name]
    else:
        # Unknown domain - return neutral S
        return SemanticCoherenceResult(
            coherence=0.5,
            name_traits=(),
            name_dominant_traits=(),
            domain_name=domain_name,
            domain_required_traits=(),
            domain_complementary=(),
            domain_conflicting=(),
            matched_required=(),
            matched_complementary=(),
            conflicts_found=(),
            rationale=f"Unknown domain '{domain_name}' - using neutral S=0.5",
        )

    # Compute name's semantic traits from ontological vector
    trait_scores = compute_semantic_traits(ontological_vector)
    dominant_traits = get_dominant_traits(trait_scores, threshold=0.4, top_n=5)

    # Convert to sets for comparison
    name_trait_set = {trait for trait, score in dominant_traits if score >= 0.3}

    # Domain requirements
    required_traits = {trait for trait, weight in domain_profile.required_traits}
    complementary_traits = domain_profile.complementary_traits
    conflicting_traits = domain_profile.conflicting_traits

    # Compute matches
    matched_required = name_trait_set & required_traits
    matched_complementary = name_trait_set & complementary_traits
    conflicts_found = name_trait_set & conflicting_traits

    # Compute S score
    # Base: proportion of required traits matched
    if required_traits:
        required_match_ratio = len(matched_required) / len(required_traits)
    else:
        required_match_ratio = 0.5

    # Weight by how strong the match is
    weighted_match = 0.0
    total_weight = 0.0
    for req_trait, weight in domain_profile.required_traits:
        total_weight += weight
        if req_trait in name_trait_set:
            # Get the name's score for this trait
            name_score = trait_scores.get(req_trait, 0.0)
            weighted_match += weight * name_score

    if total_weight > 0:
        weighted_ratio = weighted_match / total_weight
    else:
        weighted_ratio = 0.5

    # Boost for complementary matches
    complementary_boost = 0.05 * len(matched_complementary)

    # Penalty for conflicts
    conflict_penalty = 0.15 * len(conflicts_found)

    # Final S
    s_score = (0.4 * required_match_ratio + 0.6 * weighted_ratio) + complementary_boost - conflict_penalty
    s_score = max(0.0, min(1.0, s_score))

    # Generate rationale
    rationale_parts = []
    if matched_required:
        rationale_parts.append(f"Matches required: {', '.join(t.value for t in matched_required)}")
    if matched_complementary:
        rationale_parts.append(f"Matches complementary: {', '.join(t.value for t in matched_complementary)}")
    if conflicts_found:
        rationale_parts.append(f"Conflicts: {', '.join(t.value for t in conflicts_found)}")

    rationale = "; ".join(rationale_parts) if rationale_parts else "No significant trait alignment"

    return SemanticCoherenceResult(
        coherence=round(s_score, 4),
        name_traits=tuple((t.value, round(s, 4)) for t, s in trait_scores.items() if s > 0.2),
        name_dominant_traits=tuple(t.value for t, s in dominant_traits),
        domain_name=domain_name,
        domain_required_traits=tuple(t.value for t, w in domain_profile.required_traits),
        domain_complementary=tuple(t.value for t in complementary_traits),
        domain_conflicting=tuple(t.value for t in conflicting_traits),
        matched_required=tuple(t.value for t in matched_required),
        matched_complementary=tuple(t.value for t in matched_complementary),
        conflicts_found=tuple(t.value for t in conflicts_found),
        rationale=rationale,
    )


# =============================================================================
# Full C×R×S Computation for Name↔Domain
# =============================================================================

@dataclass(frozen=True)
class NameDomainMatchResult:
    """
    Complete result of C×R×S matching between name and domain.
    """
    # Final score
    match_score: float  # C × R × S

    # Components
    constraint: float      # C - ontological alignment
    realization: float     # R - structural profile match
    semantic: float        # S - semantic type coherence

    # Detailed analysis
    semantic_analysis: SemanticCoherenceResult

    # Classification
    match_quality: str  # "strong", "moderate", "partial", "weak"

    # Input
    name: str
    domain: str


# =============================================================================
# Zero-Kill Threshold
# =============================================================================

# If C (ontological constraint) falls below this threshold, the pairing
# is considered ontologically invalid. S is not evaluated (set to 0).
# This prevents wasting computation on impossible pairings and makes
# the hard gate explicit.
C_ZERO_KILL_THRESHOLD = 0.1


def classify_match_quality(score: float) -> str:
    """Classify match score into quality tier."""
    if score >= 0.5:
        return "strong"
    elif score >= 0.3:
        return "moderate"
    elif score >= 0.15:
        return "partial"
    else:
        return "weak"


def compute_name_domain_crs(
    name: str,
    domain_name: str,
    ontological_vector: Tuple[Tuple[str, float], ...],
    structural_match_score: float,
) -> NameDomainMatchResult:
    """
    Compute full C×R×S score for name↔domain matching.

    Zero-Kill Rule:
        If C < C_ZERO_KILL_THRESHOLD, S is not evaluated (S = 0).
        This ensures ontologically invalid pairings get MATCH = 0
        without wasting computation on semantic analysis.

    Args:
        name: The name being analyzed
        domain_name: The domain to match against
        ontological_vector: Name's 12D ontological layer values
        structural_match_score: R score from 12D profile matching (0-1)

    Returns:
        NameDomainMatchResult with full C×R×S analysis
    """
    # C = Ontological constraint/alignment
    # For name↔domain, C measures whether the name's ontological signature
    # is compatible with the domain's energy requirements
    # Use the variance of the ontological vector as inverse of constraint
    onto_values = [v for _, v in ontological_vector]
    onto_mean = sum(onto_values) / len(onto_values) if onto_values else 0.5
    onto_var = sum((v - onto_mean) ** 2 for v in onto_values) / len(onto_values) if onto_values else 0
    # Higher variance = more focused signature = better constraint fit
    c_score = 0.5 + 0.5 * min(1.0, onto_var * 10)  # Scale variance to [0.5, 1.0]

    # R = Structural realization (passed in from 12D profile matching)
    r_score = structural_match_score

    # ZERO-KILL RULE: If C is below threshold, don't evaluate S
    # This is the hard gate - ontologically invalid pairings get MATCH = 0
    if c_score < C_ZERO_KILL_THRESHOLD:
        # C is too low - ontologically invalid pairing
        # S is not meaningful, so set to 0
        s_score = 0.0
        semantic_result = SemanticCoherenceResult(
            coherence=0.0,
            name_traits=(),
            name_dominant_traits=(),
            domain_name=domain_name,
            domain_required_traits=(),
            domain_complementary=(),
            domain_conflicting=(),
            matched_required=(),
            matched_complementary=(),
            conflicts_found=(),
            rationale=f"Zero-kill: C={c_score:.3f} < threshold={C_ZERO_KILL_THRESHOLD} (ontologically invalid)",
        )
    else:
        # C is valid - proceed with semantic evaluation
        # S = Semantic type coherence
        semantic_result = compute_semantic_coherence(ontological_vector, domain_name)
        s_score = semantic_result.coherence

    # MATCH = C × R × S
    match_score = c_score * r_score * s_score

    return NameDomainMatchResult(
        match_score=round(match_score, 4),
        constraint=round(c_score, 4),
        realization=round(r_score, 4),
        semantic=round(s_score, 4),
        semantic_analysis=semantic_result,
        match_quality=classify_match_quality(match_score),
        name=name,
        domain=domain_name,
    )


# =============================================================================
# Public API
# =============================================================================

__all__ = [
    # Types
    "SemanticTrait",
    "DomainSemanticProfile",
    "SemanticCoherenceResult",
    "NameDomainMatchResult",
    # Data
    "LAYER_TO_TRAITS",
    "DOMAIN_SEMANTIC_PROFILES",
    # Functions
    "compute_semantic_traits",
    "get_dominant_traits",
    "compute_semantic_coherence",
    "compute_name_domain_crs",
    "classify_match_quality",
]
