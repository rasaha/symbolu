"""
Name Resonance System - Canonical Matcher
==========================================

Implements the canonical matching framework:
    MATCH = FEASIBILITY (C) × REALIZATION (R)

Where:
- C (Constraint/Feasibility): From varṇa/ontological analysis
  - Answers: "Is this allowed to exist?"
  - Detects ontological violations, conflicts, inversions

- R (Realization/Strength): From experiential/structural analysis
  - Answers: "How strongly does it manifest?"
  - Measures phonetic resonance coherence

Key Principle:
    Constraint and Realization must not be added or averaged.
    High resonance with violated constraint is INVALID, not "partially good".
    Perfect constraint with zero realization is POTENTIAL, not outcome.

Diagnostic Matrix:
    ┌─────────────┬───────────────┬───────────────┐
    │             │   High R      │    Low R      │
    ├─────────────┼───────────────┼───────────────┤
    │   High C    │  TRUE_MATCH   │    LATENT     │
    │   Low C     │  DISTORTED    │   NON_MATCH   │
    └─────────────┴───────────────┴───────────────┘

Tier: Core/Substrate (Tier 1)
Authority: NONE (signal processing only)
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import Tuple, Dict, List

from symbolu.resonance.analyzer import analyze_word
from symbolu.resonance.varna_bridge import (
    varna_word_to_vector,
    phonemes_to_varnas,
    get_varna_affinities,
    ENGLISH_TO_VARNA,
)
from symbolu.resonance.types import LAYER_NAMES
from symbolu.name_resonance.types import DIMENSION_NAMES
from symbolu.name_resonance.ontological_bridge import (
    get_ontological_vector,
    project_ontological_to_experiential,
)
from symbolu.name_resonance.extractor import normalize_input, extract_signals
from symbolu.name_resonance.projector import project_to_structural_profile


# =============================================================================
# Types
# =============================================================================

class MatchMode(Enum):
    """Classification of canonical match based on C × R matrix."""
    TRUE_MATCH = "true_match"      # High C, High R - Both allowed and realized
    LATENT = "latent"              # High C, Low R - Allowed but not manifested
    DISTORTED = "distorted"        # Low C, High R - Manifested but not allowed
    NON_MATCH = "non_match"        # Low C, Low R - Neither allowed nor realized


@dataclass(frozen=True)
class ViolationDetail:
    """Details of an ontological constraint violation."""
    violation_type: str
    severity: float  # 0.0 to 1.0
    description: str


@dataclass(frozen=True)
class ConstraintAnalysis:
    """Result of constraint/feasibility analysis (C)."""
    feasibility: float  # C ∈ [0, 1]
    violations: Tuple[ViolationDetail, ...]
    dominant_layer_a: str
    dominant_layer_b: str
    layer_distance: int  # How many layers apart
    direction_aligned: bool  # Are vectors pointing same ontological direction


@dataclass(frozen=True)
class RealizationAnalysis:
    """Result of realization/manifestation analysis (R)."""
    realization: float  # R ∈ [0, 1]
    experiential_similarity: float
    phonetic_coherence: float
    structural_alignment: float


@dataclass(frozen=True)
class CanonicalMatchResult:
    """
    Complete result of canonical matching.

    The core formula: MATCH = C × R

    This structure ensures:
    - No collapsing of constraint into realization
    - No double-counting
    - Full diagnostic visibility
    """
    # Core match score
    match_score: float  # C × R

    # Component scores
    feasibility: float  # C - constraint satisfaction
    realization: float  # R - manifestation strength

    # Classification
    mode: MatchMode

    # Detailed analysis
    constraint_analysis: ConstraintAnalysis
    realization_analysis: RealizationAnalysis

    # Input words
    word_a: str
    word_b: str

    # Confidence (optional entropy-based)
    confidence: float  # exp(-H) where H is mismatch entropy


# =============================================================================
# Constraint Feasibility Computation (C)
# =============================================================================

# Ontological layer ordering (from base to transcendent)
LAYER_ORDER = {
    "O1_THINKING": 0,
    "O2_FORMING": 1,
    "O3_ACTING": 2,
    "O4_TAGGING": 3,
    "O5_DIRECTING": 4,
    "O6_REASONING": 5,
    "O7_PURPOSING": 6,
    "O8_META_OBSERVING": 7,
    "O9_UNIFYING": 8,
    "O10_ABSOLVING": 9,
}

# Layer compatibility matrix (which layers can resonate together)
# Adjacent and complementary layers resonate well
LAYER_COMPATIBILITY: Dict[int, Tuple[int, ...]] = {
    0: (0, 1, 2, 3),       # THINKING compatible with forming, acting, tagging
    1: (0, 1, 2, 3, 4),    # FORMING
    2: (1, 2, 3, 4, 5),    # ACTING
    3: (2, 3, 4, 5, 6),    # TAGGING
    4: (3, 4, 5, 6, 7),    # DIRECTING
    5: (4, 5, 6, 7, 8),    # REASONING
    6: (5, 6, 7, 8, 9),    # PURPOSING
    7: (6, 7, 8, 9),       # META_OBSERVING
    8: (7, 8, 9),          # UNIFYING
    9: (7, 8, 9),          # ABSOLVING
}

# Violation weights - Tuned for better discrimination
VIOLATION_WEIGHTS = {
    "layer_incompatibility": 0.8,    # Dominant layers don't resonate
    "direction_conflict": 0.6,       # Vectors point opposite directions
    "dominance_mismatch": 0.5,       # Very different dominance patterns
    "bridge_break": 0.7,             # Varṇa bridge meaning conflict
    "polarity_conflict": 0.4,        # Positive/negative polarity mismatch
    "profile_divergence": 0.6,       # Overall profile shape mismatch
    "energy_mismatch": 0.5,          # Energy level mismatch
}


def compute_constraint_feasibility(word_a: str, word_b: str) -> ConstraintAnalysis:
    """
    Compute constraint/feasibility score (C) from ontological analysis.

    C = exp(-Σ(violation_i × weight_i))

    Args:
        word_a: First word
        word_b: Second word

    Returns:
        ConstraintAnalysis with feasibility score and violation details
    """
    violations: List[ViolationDetail] = []

    # Get 10D ontological vectors
    onto_vec_a = get_ontological_vector(word_a)
    onto_vec_b = get_ontological_vector(word_b)

    # Find dominant layers
    dominant_a = max(onto_vec_a, key=lambda x: x[1])
    dominant_b = max(onto_vec_b, key=lambda x: x[1])

    layer_a_name = dominant_a[0]
    layer_b_name = dominant_b[0]
    layer_a_idx = LAYER_ORDER.get(layer_a_name, 0)
    layer_b_idx = LAYER_ORDER.get(layer_b_name, 0)

    layer_distance = abs(layer_a_idx - layer_b_idx)

    # Check 1: Layer compatibility
    compatible_layers = LAYER_COMPATIBILITY.get(layer_a_idx, ())
    if layer_b_idx not in compatible_layers:
        severity = min(1.0, layer_distance / 5.0)  # Scale by distance
        violations.append(ViolationDetail(
            violation_type="layer_incompatibility",
            severity=severity,
            description=f"Dominant layers {layer_a_name} and {layer_b_name} are {layer_distance} steps apart"
        ))

    # Check 2: Vector direction alignment
    vec_a = tuple(v[1] for v in onto_vec_a)
    vec_b = tuple(v[1] for v in onto_vec_b)

    dot_product = sum(a * b for a, b in zip(vec_a, vec_b))
    mag_a = math.sqrt(sum(a * a for a in vec_a))
    mag_b = math.sqrt(sum(b * b for b in vec_b))

    if mag_a > 0 and mag_b > 0:
        cosine = dot_product / (mag_a * mag_b)
        direction_aligned = cosine > 0.3
    else:
        cosine = 0.0
        direction_aligned = False

    if not direction_aligned:
        violations.append(ViolationDetail(
            violation_type="direction_conflict",
            severity=max(0.0, 0.5 - cosine),  # Higher severity for more negative
            description=f"Ontological vectors diverge (cosine={cosine:.3f})"
        ))

    # Check 3: Dominance pattern similarity
    # Compare the shape of the 10D vectors
    top_3_a = sorted(range(10), key=lambda i: vec_a[i], reverse=True)[:3]
    top_3_b = sorted(range(10), key=lambda i: vec_b[i], reverse=True)[:3]

    overlap = len(set(top_3_a) & set(top_3_b))
    if overlap == 0:
        violations.append(ViolationDetail(
            violation_type="dominance_mismatch",
            severity=0.6,
            description="No overlap in top 3 dominant ontological layers"
        ))
    elif overlap == 1:
        violations.append(ViolationDetail(
            violation_type="dominance_mismatch",
            severity=0.3,
            description="Only 1 of top 3 dominant layers overlap"
        ))

    # Check 4: Varṇa bridge compatibility
    from symbolu.resonance.analyzer import get_phonemes
    phonemes_a = get_phonemes(word_a.lower())
    phonemes_b = get_phonemes(word_b.lower())

    varnas_a = phonemes_to_varnas(phonemes_a)
    varnas_b = phonemes_to_varnas(phonemes_b)

    # Check if initial varṇas have compatible bridge meanings
    if varnas_a and varnas_b:
        from symbolu.resonance.varna_bridge import get_bridge_meaning
        bridge_a = get_bridge_meaning(varnas_a[0])
        bridge_b = get_bridge_meaning(varnas_b[0])

        # Simple check: if one is "dissolution" and other is "birth", conflict
        conflict_pairs = [
            ("dissolution", "birth"),
            ("purgative", "integrative"),
            ("contraction", "expansion"),
            ("destruction", "creation"),
            ("surrender", "action"),
            ("closure", "expansion"),
            ("fear", "hope"),
            ("ignorance", "knowledge"),
            ("cruelty", "compassion"),
            ("inertia", "action"),
        ]

        for pair in conflict_pairs:
            if (pair[0] in bridge_a and pair[1] in bridge_b) or \
               (pair[1] in bridge_a and pair[0] in bridge_b):
                violations.append(ViolationDetail(
                    violation_type="bridge_break",
                    severity=0.7,
                    description=f"Varṇa bridge conflict: {bridge_a} vs {bridge_b}"
                ))
                break

    # Check 5: Profile divergence (overall shape mismatch)
    # Compute Euclidean distance between normalized profiles
    euclidean_dist = math.sqrt(sum((a - b) ** 2 for a, b in zip(vec_a, vec_b)))
    max_possible_dist = math.sqrt(10)  # Max distance if vectors are orthogonal

    if euclidean_dist > max_possible_dist * 0.5:
        severity = (euclidean_dist / max_possible_dist) - 0.5
        violations.append(ViolationDetail(
            violation_type="profile_divergence",
            severity=min(1.0, severity * 2),
            description=f"Ontological profiles diverge significantly (dist={euclidean_dist:.3f})"
        ))

    # Check 6: Energy mismatch (total activation difference)
    total_a = sum(vec_a)
    total_b = sum(vec_b)
    energy_diff = abs(total_a - total_b) / max(total_a, total_b, 0.001)

    if energy_diff > 0.3:
        violations.append(ViolationDetail(
            violation_type="energy_mismatch",
            severity=min(1.0, energy_diff),
            description=f"Ontological energy levels differ ({total_a:.2f} vs {total_b:.2f})"
        ))

    # Check 7: Varṇa set overlap (how many shared varṇa types)
    if varnas_a and varnas_b:
        varna_set_a = set(varnas_a)
        varna_set_b = set(varnas_b)
        if varna_set_a and varna_set_b:
            overlap = len(varna_set_a & varna_set_b)
            union = len(varna_set_a | varna_set_b)
            jaccard = overlap / union if union > 0 else 0

            if jaccard < 0.1:  # Very little varṇa overlap
                violations.append(ViolationDetail(
                    violation_type="bridge_break",
                    severity=0.4,
                    description=f"No shared varṇa types (Jaccard={jaccard:.2f})"
                ))

    # Compute C = exp(-Σ(violation_i × weight_i))
    total_penalty = 0.0
    for v in violations:
        weight = VIOLATION_WEIGHTS.get(v.violation_type, 0.1)
        total_penalty += v.severity * weight

    feasibility = math.exp(-total_penalty)

    return ConstraintAnalysis(
        feasibility=round(feasibility, 4),
        violations=tuple(violations),
        dominant_layer_a=layer_a_name,
        dominant_layer_b=layer_b_name,
        layer_distance=layer_distance,
        direction_aligned=direction_aligned,
    )


# =============================================================================
# Realization Strength Computation (R)
# =============================================================================

def compute_realization_strength(word_a: str, word_b: str) -> RealizationAnalysis:
    """
    Compute realization/manifestation strength (R) from experiential analysis.

    R combines:
    - Experiential dimension similarity (12D cosine)
    - Phonetic structural coherence
    - Pattern alignment

    Args:
        word_a: First word
        word_b: Second word

    Returns:
        RealizationAnalysis with realization score and components
    """
    # Get 12D experiential profiles
    normalized_a = normalize_input(word_a)
    normalized_b = normalize_input(word_b)

    signals_a = extract_signals(normalized_a)
    signals_b = extract_signals(normalized_b)

    profile_a = project_to_structural_profile(signals_a)
    profile_b = project_to_structural_profile(signals_b)

    # Compute experiential similarity (12D cosine)
    vec_a = tuple(getattr(profile_a, dim) for dim in DIMENSION_NAMES)
    vec_b = tuple(getattr(profile_b, dim) for dim in DIMENSION_NAMES)

    dot_product = sum(a * b for a, b in zip(vec_a, vec_b))
    mag_a = math.sqrt(sum(a * a for a in vec_a))
    mag_b = math.sqrt(sum(b * b for b in vec_b))

    if mag_a > 0 and mag_b > 0:
        experiential_similarity = dot_product / (mag_a * mag_b)
    else:
        experiential_similarity = 0.0

    # Compute phonetic coherence
    # Based on shared phoneme categories
    cats_a = set(signals_a.phoneme_categories)
    cats_b = set(signals_b.phoneme_categories)

    if cats_a or cats_b:
        phonetic_coherence = len(cats_a & cats_b) / len(cats_a | cats_b)
    else:
        phonetic_coherence = 0.0

    # Compute structural alignment
    # Compare key structural features
    alignment_factors = []

    # Syllable similarity
    syl_diff = abs(signals_a.syllable_count - signals_b.syllable_count)
    alignment_factors.append(1.0 / (1.0 + syl_diff))

    # V/C ratio similarity
    vc_diff = abs(signals_a.vowel_consonant_ratio - signals_b.vowel_consonant_ratio)
    alignment_factors.append(1.0 / (1.0 + vc_diff))

    # Initial/final category match
    if signals_a.initial_category == signals_b.initial_category:
        alignment_factors.append(1.0)
    else:
        alignment_factors.append(0.5)

    if signals_a.final_category == signals_b.final_category:
        alignment_factors.append(1.0)
    else:
        alignment_factors.append(0.5)

    structural_alignment = sum(alignment_factors) / len(alignment_factors)

    # Combine into R
    # Weighted combination
    realization = (
        0.5 * experiential_similarity +
        0.25 * phonetic_coherence +
        0.25 * structural_alignment
    )

    # Clamp to [0, 1]
    realization = max(0.0, min(1.0, realization))

    return RealizationAnalysis(
        realization=round(realization, 4),
        experiential_similarity=round(experiential_similarity, 4),
        phonetic_coherence=round(phonetic_coherence, 4),
        structural_alignment=round(structural_alignment, 4),
    )


# =============================================================================
# Canonical Match Computation
# =============================================================================

# Thresholds for mode classification
C_THRESHOLD = 0.6  # Above this is "high" feasibility
R_THRESHOLD = 0.5  # Above this is "high" realization


def classify_match_mode(c: float, r: float) -> MatchMode:
    """
    Classify match into one of four modes based on C and R.

    Args:
        c: Constraint/feasibility score
        r: Realization/strength score

    Returns:
        MatchMode classification
    """
    high_c = c >= C_THRESHOLD
    high_r = r >= R_THRESHOLD

    if high_c and high_r:
        return MatchMode.TRUE_MATCH
    elif high_c and not high_r:
        return MatchMode.LATENT
    elif not high_c and high_r:
        return MatchMode.DISTORTED
    else:
        return MatchMode.NON_MATCH


def compute_confidence(c: float, r: float) -> float:
    """
    Compute confidence based on alignment between C and R.

    High confidence when C and R agree (both high or both low).
    Low confidence when they diverge (one high, one low).

    Uses entropy-like measure: confidence = exp(-H)
    Where H = variance in normalized [C, R]

    Args:
        c: Constraint score
        r: Realization score

    Returns:
        Confidence score in [0, 1]
    """
    # Variance of [c, r]
    mean = (c + r) / 2
    variance = ((c - mean) ** 2 + (r - mean) ** 2) / 2

    # H as variance (higher variance = higher entropy = less confidence)
    h = variance

    # Confidence = exp(-H), scaled for typical variance range
    confidence = math.exp(-h * 4)  # Scale factor for sensitivity

    return round(confidence, 4)


def canonical_match(word_a: str, word_b: str) -> CanonicalMatchResult:
    """
    Compute canonical match between two words.

    MATCH = C × R

    Where:
    - C = Constraint feasibility (from ontological analysis)
    - R = Realization strength (from experiential analysis)

    Args:
        word_a: First word
        word_b: Second word

    Returns:
        CanonicalMatchResult with full diagnostic information
    """
    # Compute C (constraint/feasibility)
    constraint = compute_constraint_feasibility(word_a, word_b)
    c = constraint.feasibility

    # Compute R (realization/manifestation)
    realization = compute_realization_strength(word_a, word_b)
    r = realization.realization

    # Compute MATCH = C × R
    match_score = c * r

    # Classify mode
    mode = classify_match_mode(c, r)

    # Compute confidence
    confidence = compute_confidence(c, r)

    return CanonicalMatchResult(
        match_score=round(match_score, 4),
        feasibility=c,
        realization=r,
        mode=mode,
        constraint_analysis=constraint,
        realization_analysis=realization,
        word_a=word_a,
        word_b=word_b,
        confidence=confidence,
    )


# =============================================================================
# Batch Analysis
# =============================================================================

def analyze_pairs(pairs: List[Tuple[str, str]]) -> List[CanonicalMatchResult]:
    """
    Analyze multiple word pairs.

    Args:
        pairs: List of (word_a, word_b) tuples

    Returns:
        List of CanonicalMatchResults
    """
    return [canonical_match(a, b) for a, b in pairs]


def format_result(result: CanonicalMatchResult) -> str:
    """
    Format a canonical match result for display.

    Args:
        result: CanonicalMatchResult to format

    Returns:
        Formatted string
    """
    mode_symbols = {
        MatchMode.TRUE_MATCH: "✓✓",
        MatchMode.LATENT: "○○",
        MatchMode.DISTORTED: "⚠⚠",
        MatchMode.NON_MATCH: "✗✗",
    }

    symbol = mode_symbols[result.mode]

    return (
        f"{symbol} {result.word_a} ↔ {result.word_b}: "
        f"MATCH={result.match_score:.3f} "
        f"(C={result.feasibility:.3f} × R={result.realization:.3f}) "
        f"[{result.mode.value}] "
        f"conf={result.confidence:.2f}"
    )


def demo_canonical_matching() -> str:
    """
    Demonstrate canonical matching with test pairs.

    Returns:
        Formatted demo output
    """
    # Test pairs with expected semantic relationships
    test_pairs = [
        # Should be TRUE_MATCH (semantically related)
        ("king", "queen"),
        ("love", "heart"),
        ("sun", "light"),
        ("tree", "forest"),
        ("water", "river"),

        # Should be NON_MATCH (semantically unrelated)
        ("love", "table"),
        ("king", "banana"),
        ("tree", "computer"),
        ("sun", "pencil"),

        # Interesting cases
        ("happy", "joy"),       # Synonyms
        ("light", "darkness"),  # Antonyms
        ("fire", "water"),      # Opposites
        ("peace", "war"),       # Antonyms
    ]

    lines = [
        "=" * 70,
        "CANONICAL MATCHING DEMO",
        "=" * 70,
        "",
        "Formula: MATCH = C × R",
        "Where C = constraint feasibility, R = realization strength",
        "",
        "Thresholds: C >= 0.6 = High, R >= 0.5 = High",
        "",
        "Modes:",
        "  ✓✓ TRUE_MATCH  : High C, High R - Both allowed and realized",
        "  ○○ LATENT      : High C, Low R - Allowed but not manifested",
        "  ⚠⚠ DISTORTED   : Low C, High R - Manifested but not allowed",
        "  ✗✗ NON_MATCH   : Low C, Low R - Neither allowed nor realized",
        "",
        "-" * 70,
        "",
    ]

    results = analyze_pairs(test_pairs)

    # Group by mode
    by_mode: Dict[MatchMode, List[CanonicalMatchResult]] = {
        mode: [] for mode in MatchMode
    }

    for result in results:
        by_mode[result.mode].append(result)

    for mode in [MatchMode.TRUE_MATCH, MatchMode.LATENT,
                 MatchMode.DISTORTED, MatchMode.NON_MATCH]:
        if by_mode[mode]:
            lines.append(f"{mode.value.upper()}:")
            for result in by_mode[mode]:
                lines.append(f"  {format_result(result)}")
            lines.append("")

    # Summary stats
    lines.extend([
        "-" * 70,
        "SUMMARY:",
        f"  TRUE_MATCH:  {len(by_mode[MatchMode.TRUE_MATCH])}",
        f"  LATENT:      {len(by_mode[MatchMode.LATENT])}",
        f"  DISTORTED:   {len(by_mode[MatchMode.DISTORTED])}",
        f"  NON_MATCH:   {len(by_mode[MatchMode.NON_MATCH])}",
        "",
        "=" * 70,
    ])

    return "\n".join(lines)


# =============================================================================
# Public API
# =============================================================================

__all__ = [
    "MatchMode",
    "ViolationDetail",
    "ConstraintAnalysis",
    "RealizationAnalysis",
    "CanonicalMatchResult",
    "compute_constraint_feasibility",
    "compute_realization_strength",
    "canonical_match",
    "analyze_pairs",
    "format_result",
    "demo_canonical_matching",
]
