"""
Phonetic Resonance Engine - Type Definitions
=============================================

All types are frozen (immutable) dataclasses.
All collections are immutable (tuple, frozenset).
"""

from dataclasses import dataclass
from enum import Enum
from typing import Tuple, Optional


class PhonemeCategory(Enum):
    """
    Phoneme categories based on articulation manner.

    Each category has distinct ontological affinities:
    - PLOSIVE: Sudden, forceful → ACTING, DIRECTING
    - FRICATIVE: Continuous, controlled → DIRECTING, REASONING
    - AFFRICATE: Combined action → ACTING, FORMING
    - NASAL: Resonant, connecting → UNIFYING, THINKING
    - LIQUID: Flowing, smooth → FORMING, UNIFYING
    - GLIDE: Transitional → FORMING, PURPOSING
    - VOWEL_SHORT: Brief, focused → THINKING, TAGGING
    - VOWEL_LONG: Sustained, open → ABSOLVING, UNIFYING
    - DIPHTHONG: Rising/falling → PURPOSING, FORMING
    """
    PLOSIVE = "plosive"           # p, b, t, d, k, g
    FRICATIVE = "fricative"       # f, v, s, z, sh, th, h
    AFFRICATE = "affricate"       # ch, j
    NASAL = "nasal"               # m, n, ng
    LIQUID = "liquid"             # l, r
    GLIDE = "glide"               # w, y
    VOWEL_SHORT = "vowel_short"   # ih, eh, ah, uh
    VOWEL_LONG = "vowel_long"     # iy, ey, uw, ow
    DIPHTHONG = "diphthong"       # ay, aw, oy


class OntologicalLayer(Enum):
    """
    The 10 ontological layers for meaning projection.

    Each word resonates with multiple layers at different strengths.
    """
    O1_THINKING = "O1_THINKING"
    O2_FORMING = "O2_FORMING"
    O3_ACTING = "O3_ACTING"
    O4_TAGGING = "O4_TAGGING"
    O5_DIRECTING = "O5_DIRECTING"
    O6_REASONING = "O6_REASONING"
    O7_PURPOSING = "O7_PURPOSING"
    O8_META_OBSERVING = "O8_META_OBSERVING"
    O9_UNIFYING = "O9_UNIFYING"
    O10_ABSOLVING = "O10_ABSOLVING"


# Layer names for easy indexing
LAYER_NAMES: Tuple[str, ...] = (
    "O1_THINKING",
    "O2_FORMING",
    "O3_ACTING",
    "O4_TAGGING",
    "O5_DIRECTING",
    "O6_REASONING",
    "O7_PURPOSING",
    "O8_META_OBSERVING",
    "O9_UNIFYING",
    "O10_ABSOLVING",
)


@dataclass(frozen=True)
class PhonemeProfile:
    """
    Single phoneme's profile including category and layer affinities.

    Attributes:
        phoneme: The phoneme symbol (ARPABET format, e.g., "L", "AY", "T")
        category: The phoneme category (LIQUID, DIPHTHONG, etc.)
        layer_affinities: 10D vector of affinities to each ontological layer
    """
    phoneme: str
    category: PhonemeCategory
    layer_affinities: Tuple[float, ...]  # 10 values, one per layer

    def __post_init__(self):
        if len(self.layer_affinities) != 10:
            raise ValueError(f"layer_affinities must have 10 values, got {len(self.layer_affinities)}")


@dataclass(frozen=True)
class WordVector:
    """
    10D ontological vector for a word.

    Attributes:
        word: The original word
        phonemes: Tuple of phonemes extracted from the word
        vector: 10D normalized vector (sums to ~1.0)
        trajectory: Magnitude at each phoneme position (for prosodic shape)
        dominant_layer: The layer with highest affinity
        dominant_score: The score of the dominant layer
    """
    word: str
    phonemes: Tuple[str, ...]
    vector: Tuple[float, ...]           # 10 dimensions
    trajectory: Tuple[float, ...]       # magnitude per phoneme
    dominant_layer: str
    dominant_score: float

    def __post_init__(self):
        if len(self.vector) != 10:
            raise ValueError(f"vector must have 10 values, got {len(self.vector)}")

    def get_top_layers(self, n: int = 3) -> Tuple[Tuple[str, float], ...]:
        """Get the top N layers by score."""
        indexed = [(LAYER_NAMES[i], self.vector[i]) for i in range(10)]
        sorted_layers = sorted(indexed, key=lambda x: x[1], reverse=True)
        return tuple(sorted_layers[:n])


@dataclass(frozen=True)
class ResonanceResult:
    """
    Phonetic resonance between two words.

    Attributes:
        word_a: First word
        word_b: Second word
        similarity: Cosine similarity (0.0 to 1.0)
        harmonic: True if similarity > 0.7
        dissonant: True if similarity < 0.3
        shared_dimensions: Layers where both words have high affinity
        conflicting_dimensions: Layers where words have opposite affinities
        trajectory_alignment: How well the prosodic shapes match
    """
    word_a: str
    word_b: str
    similarity: float
    harmonic: bool
    dissonant: bool
    shared_dimensions: Tuple[str, ...]
    conflicting_dimensions: Tuple[str, ...]
    trajectory_alignment: float  # -1.0 to 1.0 (negative = opposite shapes)


@dataclass(frozen=True)
class PhraseAnalysis:
    """
    Full phonetic analysis of a phrase.

    Attributes:
        phrase: Original phrase
        words: WordVector for each content word
        pairwise_resonance: Resonance between each pair of words
        overall_harmony: Mean similarity across all pairs (0.0 to 1.0)
        overall_dissonance: Variance in vectors (higher = more conflict)
        prediction: "HARMONIC", "DISSONANT", or "NEUTRAL"
        key_resonances: Most significant word pairs (positive or negative)
    """
    phrase: str
    words: Tuple[WordVector, ...]
    pairwise_resonance: Tuple[ResonanceResult, ...]
    overall_harmony: float
    overall_dissonance: float
    prediction: str
    key_resonances: Tuple[ResonanceResult, ...]


@dataclass(frozen=True)
class ComparisonResult:
    """
    Comparison between two phrases.

    Attributes:
        phrase_a: First phrase
        phrase_b: Second phrase
        analysis_a: Full analysis of first phrase
        analysis_b: Full analysis of second phrase
        harmony_difference: How much more/less harmonic A is than B
        more_harmonic: Which phrase is more phonetically harmonic
        insight: Key difference between the phrases
    """
    phrase_a: str
    phrase_b: str
    analysis_a: PhraseAnalysis
    analysis_b: PhraseAnalysis
    harmony_difference: float
    more_harmonic: str
    insight: str
