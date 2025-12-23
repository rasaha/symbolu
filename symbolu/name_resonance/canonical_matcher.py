"""
Name Resonance System - Canonical Matcher
==========================================

Implements the canonical matching framework:
    MATCH = C × R × S

Where:
- C (Constraint/Feasibility): From varṇa/ontological analysis
  - Answers: "Is this allowed to exist?"

- R (Realization/Strength): From experiential/structural analysis
  - Answers: "How strongly does it manifest?"

- S (Referential Coherence): From external referent classes
  - Answers: "Do these point to the same external invariant?"
  - NON-PHONEMIC - provides source independence

Key Principle:
    The system requires at least one non-phonemic axis (S).
    Constraint and realization may share a bridge, but they
    may not share the same evidence base.

Zero-Kill Rule:
    If C < 0.1 (C_ZERO_KILL_THRESHOLD), S is NOT evaluated.
    Ontologically invalid pairings get MATCH = 0 without semantic
    computation. This ensures C acts as a hard gate - if phonemic
    structure doesn't permit the pairing, semantic coherence is moot.

Diagnostic Matrix (C × R, gated by S):
    ┌─────────────┬───────────────┬───────────────┐
    │             │   High R      │    Low R      │
    ├─────────────┼───────────────┼───────────────┤
    │   High C    │  TRUE_MATCH   │    LATENT     │
    │   Low C     │  DISTORTED    │   NON_MATCH   │
    └─────────────┴───────────────┴───────────────┘

When S is low, MATCH collapses regardless of C × R.

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
    phonemes_to_varnas,
)
from symbolu.resonance.types import LAYER_NAMES
from symbolu.name_resonance.types import DIMENSION_NAMES
from symbolu.name_resonance.ontological_bridge import get_ontological_vector
from symbolu.name_resonance.extractor import normalize_input, extract_signals
from symbolu.name_resonance.projector import project_to_structural_profile
from symbolu.name_resonance.referent_classes import (
    compute_referent_coherence,
    compute_semantic_contextual_coherence,
    ReferentAnalysis,
    SemanticContextAnalysis,
    SemanticContextConfig,
    DEFAULT_CONTEXT_CONFIG,
)


# =============================================================================
# Types
# =============================================================================

class MatchMode(Enum):
    """Classification of canonical match based on C × R × S."""
    TRUE_MATCH = "true_match"           # High C, High R, High S
    LATENT = "latent"                   # High C, Low R, High S
    DISTORTED = "distorted"             # Low C, High R, High S
    NON_MATCH = "non_match"             # Low C, Low R, or Low S
    REFERENT_MISMATCH = "ref_mismatch"  # Any C/R, but Low S


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
    layer_distance: int
    direction_aligned: bool


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

    The core formula: MATCH = C × R × S

    This structure ensures:
    - Source independence (S is non-phonemic)
    - No collapsing of constraint into realization
    - Full diagnostic visibility
    """
    # Core match score
    match_score: float  # C × R × S

    # Component scores
    feasibility: float      # C - constraint satisfaction (phonemic → ontology)
    realization: float      # R - manifestation strength (phonemic → experience)
    referent: float         # S - referential coherence (NON-phonemic)

    # Classification
    mode: MatchMode

    # Detailed analysis
    constraint_analysis: ConstraintAnalysis
    realization_analysis: RealizationAnalysis
    referent_analysis: ReferentAnalysis

    # Input words
    word_a: str
    word_b: str

    # Confidence
    confidence: float


# =============================================================================
# Constraint Feasibility Computation (C)
# =============================================================================

LAYER_ORDER = {
    "O1_THINKING": 0, "O2_FORMING": 1, "O3_ACTING": 2, "O4_TAGGING": 3,
    "O5_DIRECTING": 4, "O6_REASONING": 5, "O7_PURPOSING": 6,
    "O8_META_OBSERVING": 7, "O9_UNIFYING": 8, "O10_ABSOLVING": 9,
}

LAYER_COMPATIBILITY: Dict[int, Tuple[int, ...]] = {
    0: (0, 1, 2, 3), 1: (0, 1, 2, 3, 4), 2: (1, 2, 3, 4, 5),
    3: (2, 3, 4, 5, 6), 4: (3, 4, 5, 6, 7), 5: (4, 5, 6, 7, 8),
    6: (5, 6, 7, 8, 9), 7: (6, 7, 8, 9), 8: (7, 8, 9), 9: (7, 8, 9),
}

VIOLATION_WEIGHTS = {
    "layer_incompatibility": 0.6,
    "direction_conflict": 0.5,
    "dominance_mismatch": 0.4,
    "bridge_break": 0.5,
}


def compute_constraint_feasibility(word_a: str, word_b: str) -> ConstraintAnalysis:
    """Compute constraint/feasibility score (C) from ontological analysis."""
    violations: List[ViolationDetail] = []

    onto_vec_a = get_ontological_vector(word_a)
    onto_vec_b = get_ontological_vector(word_b)

    dominant_a = max(onto_vec_a, key=lambda x: x[1])
    dominant_b = max(onto_vec_b, key=lambda x: x[1])

    layer_a_name = dominant_a[0]
    layer_b_name = dominant_b[0]
    layer_a_idx = LAYER_ORDER.get(layer_a_name, 0)
    layer_b_idx = LAYER_ORDER.get(layer_b_name, 0)
    layer_distance = abs(layer_a_idx - layer_b_idx)

    # Check layer compatibility
    compatible_layers = LAYER_COMPATIBILITY.get(layer_a_idx, ())
    if layer_b_idx not in compatible_layers:
        severity = min(1.0, layer_distance / 5.0)
        violations.append(ViolationDetail(
            violation_type="layer_incompatibility",
            severity=severity,
            description=f"Layers {layer_a_name} and {layer_b_name} are {layer_distance} steps apart"
        ))

    # Check direction alignment
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
            severity=max(0.0, 0.5 - cosine),
            description=f"Ontological vectors diverge (cosine={cosine:.3f})"
        ))

    # Check dominance pattern
    top_3_a = sorted(range(10), key=lambda i: vec_a[i], reverse=True)[:3]
    top_3_b = sorted(range(10), key=lambda i: vec_b[i], reverse=True)[:3]
    overlap = len(set(top_3_a) & set(top_3_b))

    if overlap == 0:
        violations.append(ViolationDetail(
            violation_type="dominance_mismatch",
            severity=0.5,
            description="No overlap in top 3 dominant layers"
        ))
    elif overlap == 1:
        violations.append(ViolationDetail(
            violation_type="dominance_mismatch",
            severity=0.2,
            description="Only 1 of top 3 layers overlap"
        ))

    # Compute C = exp(-Σ(violation × weight))
    total_penalty = sum(
        v.severity * VIOLATION_WEIGHTS.get(v.violation_type, 0.1)
        for v in violations
    )
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
    """Compute realization/manifestation strength (R) from experiential analysis."""
    normalized_a = normalize_input(word_a)
    normalized_b = normalize_input(word_b)

    signals_a = extract_signals(normalized_a)
    signals_b = extract_signals(normalized_b)

    profile_a = project_to_structural_profile(signals_a)
    profile_b = project_to_structural_profile(signals_b)

    # Experiential similarity (12D cosine)
    vec_a = tuple(getattr(profile_a, dim) for dim in DIMENSION_NAMES)
    vec_b = tuple(getattr(profile_b, dim) for dim in DIMENSION_NAMES)

    dot_product = sum(a * b for a, b in zip(vec_a, vec_b))
    mag_a = math.sqrt(sum(a * a for a in vec_a))
    mag_b = math.sqrt(sum(b * b for b in vec_b))

    experiential_similarity = dot_product / (mag_a * mag_b) if mag_a > 0 and mag_b > 0 else 0.0

    # Phonetic coherence
    cats_a = set(signals_a.phoneme_categories)
    cats_b = set(signals_b.phoneme_categories)
    phonetic_coherence = len(cats_a & cats_b) / len(cats_a | cats_b) if (cats_a or cats_b) else 0.0

    # Structural alignment
    alignment_factors = [
        1.0 / (1.0 + abs(signals_a.syllable_count - signals_b.syllable_count)),
        1.0 / (1.0 + abs(signals_a.vowel_consonant_ratio - signals_b.vowel_consonant_ratio)),
        1.0 if signals_a.initial_category == signals_b.initial_category else 0.5,
        1.0 if signals_a.final_category == signals_b.final_category else 0.5,
    ]
    structural_alignment = sum(alignment_factors) / len(alignment_factors)

    realization = 0.5 * experiential_similarity + 0.25 * phonetic_coherence + 0.25 * structural_alignment
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

C_THRESHOLD = 0.6
R_THRESHOLD = 0.5
S_THRESHOLD = 0.2  # Low threshold - any shared referent matters
C_ZERO_KILL_THRESHOLD = 0.1  # Zero-kill: if C < this, S is not evaluated (ontologically invalid)


def classify_match_mode(c: float, r: float, s: float) -> MatchMode:
    """Classify match into one of the modes based on C, R, and S."""
    # S gates everything - if referents don't align, it's a mismatch
    if s < S_THRESHOLD:
        return MatchMode.REFERENT_MISMATCH

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


def compute_confidence(c: float, r: float, s: float) -> float:
    """Compute confidence based on alignment between C, R, and S."""
    mean = (c + r + s) / 3
    variance = ((c - mean) ** 2 + (r - mean) ** 2 + (s - mean) ** 2) / 3
    return round(math.exp(-variance * 4), 4)


def canonical_match(
    word_a: str,
    word_b: str,
    context: str | None = None,
    use_contextual_s: bool = True,
    context_config: SemanticContextConfig | None = None,
) -> CanonicalMatchResult:
    """
    Compute canonical match between two words.

    MATCH = C × R × S

    Where:
    - C = Constraint feasibility (phonemic → ontology)
    - R = Realization strength (phonemic → experience)
    - S = Semantic Contextual Meaning (NON-phonemic, context-aware)

    Args:
        word_a: First word
        word_b: Second word
        context: Optional context string to disambiguate meaning
        use_contextual_s: If True, use semantic contextual S (default)
        context_config: Configuration for contextual S computation

    Returns:
        CanonicalMatchResult with full diagnostic information

    Example:
        >>> # Default: semantic contextual S
        >>> result = canonical_match("king", "queen")

        >>> # With explicit context
        >>> result = canonical_match("king", "queen", context="chess game")

        >>> # Legacy: class-based S only
        >>> result = canonical_match("king", "queen", use_contextual_s=False)
    """
    # Compute C (constraint/feasibility)
    constraint = compute_constraint_feasibility(word_a, word_b)
    c = constraint.feasibility

    # Compute R (realization/manifestation)
    realization = compute_realization_strength(word_a, word_b)
    r = realization.realization

    # ZERO-KILL RULE: If C is below threshold, don't evaluate S
    # Ontologically invalid pairings get MATCH = 0 without semantic computation
    if c < C_ZERO_KILL_THRESHOLD:
        s = 0.0
        # Create minimal referent analysis for zero-kill case
        referent = ReferentAnalysis(
            coherence=0.0,
            word_a=word_a,
            word_b=word_b,
            primary_a=frozenset(),
            primary_b=frozenset(),
            secondary_a=frozenset(),
            secondary_b=frozenset(),
            shared_primary=frozenset(),
            shared_secondary=frozenset(),
            is_grounded=False,
            is_unknown=True,  # Mark as unknown due to zero-kill
        )
    else:
        # Compute S (Semantic Contextual Meaning) - NON-PHONEMIC
        if use_contextual_s:
            # New: Semantic Contextual S
            semantic_result = compute_semantic_contextual_coherence(
                word_a, word_b,
                context=context,
                config=context_config or DEFAULT_CONTEXT_CONFIG,
            )
            s = semantic_result.combined_coherence
            # Also get class-based for the referent_analysis field
            referent = compute_referent_coherence(word_a, word_b)
        else:
            # Legacy: Class-based S only
            referent = compute_referent_coherence(word_a, word_b)
            s = referent.coherence

    # MATCH = C × R × S
    match_score = c * r * s

    # Classify mode
    mode = classify_match_mode(c, r, s)

    # Confidence
    confidence = compute_confidence(c, r, s)

    return CanonicalMatchResult(
        match_score=round(match_score, 4),
        feasibility=c,
        realization=r,
        referent=s,
        mode=mode,
        constraint_analysis=constraint,
        realization_analysis=realization,
        referent_analysis=referent,
        word_a=word_a,
        word_b=word_b,
        confidence=confidence,
    )


# =============================================================================
# Display Functions
# =============================================================================

def format_result(result: CanonicalMatchResult) -> str:
    """Format a canonical match result for display."""
    mode_symbols = {
        MatchMode.TRUE_MATCH: "✓✓",
        MatchMode.LATENT: "○○",
        MatchMode.DISTORTED: "⚠⚠",
        MatchMode.NON_MATCH: "✗✗",
        MatchMode.REFERENT_MISMATCH: "≠≠",
    }

    symbol = mode_symbols[result.mode]
    return (
        f"{symbol} {result.word_a} ↔ {result.word_b}: "
        f"MATCH={result.match_score:.3f} "
        f"(C={result.feasibility:.2f} × R={result.realization:.2f} × S={result.referent:.2f}) "
        f"[{result.mode.value}]"
    )


def demo_canonical_matching() -> str:
    """Demonstrate canonical matching with test pairs."""
    test_pairs = [
        # Should match (semantically related)
        ("king", "queen"),
        ("sun", "light"),
        ("tree", "forest"),
        ("water", "river"),
        ("love", "heart"),
        ("happy", "joy"),

        # Should NOT match (semantically unrelated)
        ("love", "table"),
        ("king", "banana"),
        ("tree", "computer"),
        ("sun", "pencil"),

        # Antonyms (interesting case)
        ("light", "darkness"),
        ("fire", "water"),
        ("peace", "war"),
    ]

    lines = [
        "=" * 75,
        "CANONICAL MATCHING DEMO (C × R × S)",
        "=" * 75,
        "",
        "Formula: MATCH = C × R × S",
        "  C = Constraint feasibility (phonemic → ontology)",
        "  R = Realization strength (phonemic → experience)",
        "  S = Referential coherence (NON-phonemic) ← KEY ADDITION",
        "",
        "Modes:",
        "  ✓✓ TRUE_MATCH     : High C, High R, High S",
        "  ○○ LATENT         : High C, Low R, High S",
        "  ⚠⚠ DISTORTED      : Low C, High R, High S",
        "  ✗✗ NON_MATCH      : Low C, Low R",
        "  ≠≠ REF_MISMATCH   : Low S (referents don't align)",
        "",
        "-" * 75,
    ]

    # Group results by mode
    by_mode: Dict[MatchMode, List[CanonicalMatchResult]] = {m: [] for m in MatchMode}

    for a, b in test_pairs:
        result = canonical_match(a, b)
        by_mode[result.mode].append(result)

    for mode in [MatchMode.TRUE_MATCH, MatchMode.LATENT, MatchMode.DISTORTED,
                 MatchMode.REFERENT_MISMATCH, MatchMode.NON_MATCH]:
        if by_mode[mode]:
            lines.append(f"\n{mode.value.upper()}:")
            for result in by_mode[mode]:
                lines.append(f"  {format_result(result)}")

    # Accuracy analysis
    related = [("king", "queen"), ("sun", "light"), ("tree", "forest"),
               ("water", "river"), ("love", "heart"), ("happy", "joy")]
    unrelated = [("love", "table"), ("king", "banana"),
                 ("tree", "computer"), ("sun", "pencil")]

    correct_related = sum(1 for a, b in related if canonical_match(a, b).match_score >= 0.15)
    correct_unrelated = sum(1 for a, b in unrelated if canonical_match(a, b).match_score < 0.15)

    lines.extend([
        "",
        "-" * 75,
        "ACCURACY:",
        f"  Related pairs (score >= 0.15): {correct_related}/{len(related)}",
        f"  Unrelated pairs (score < 0.15): {correct_unrelated}/{len(unrelated)}",
        f"  Total: {correct_related + correct_unrelated}/{len(related) + len(unrelated)}",
        "=" * 75,
    ])

    return "\n".join(lines)


# =============================================================================
# Public API
# =============================================================================

__all__ = [
    # Types
    "MatchMode",
    "ViolationDetail",
    "ConstraintAnalysis",
    "RealizationAnalysis",
    "CanonicalMatchResult",
    # Re-exported from referent_classes for convenience
    "SemanticContextConfig",
    "SemanticContextAnalysis",
    # Functions
    "compute_constraint_feasibility",
    "compute_realization_strength",
    "canonical_match",
    "format_result",
    "demo_canonical_matching",
]
