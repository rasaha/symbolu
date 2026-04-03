"""
SMI Engine - Semantic Mismatch Index Computation
================================================

The Semantic Mismatch Index (SMI) measures the distance between:
- Inner Layer (Kosha): Acoustic/consciousness depth derived from consonants
- Outer Layer (Ontology): Semantic/cultural meaning derived from context

SMI = |inner_kosha - outer_ontology_normalized| / max_distance

Where:
    inner_kosha ∈ [1, 5]  (from consonant-to-kosha mapping)
    outer_ontology_normalized = 1.0 + (ontology_level - 1) * (4/9)  ∈ [1.0, 5.0]
    max_distance = 4.0  (= 5.0 - 1.0, the shared axis span)

This ensures:
    - Both axes are aligned to [1, 5]
    - SMI spans the full [0.0, 1.0] range
    - The distance metric is symmetric

Design Principle:
    Sound carries inner meaning (kosha).
    Context carries outer meaning (ontology).
    SMI measures their alignment or tension.

Usage:
    from agentic.core.smi import SMIEngine

    engine = SMIEngine()
    result = engine.compute("hello")
    print(result.smi)  # 0.0 - 1.0
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple

from agentic.core.models import SMIResult, SyllableAnalysis, WordAnalysis
from agentic.core.constants import (
    CONSONANT_TO_KOSHA_MAP,
    KOSHA_DESCRIPTIONS,
    CANONICAL_KOSHA_LAYERS,
    ONTOLOGICAL_LAYERS,
    SMI_THRESHOLDS,
    VOWEL_ASPECT_BRIDGES,
)


# =============================================================================
# SMI COMPUTATION PARAMETERS
# =============================================================================

# Normalization: linear map from ontology [1,10] → kosha-aligned [1.0, 5.0]
# Formula: normalized = 1.0 + (ontology - 1) * (4.0 / 9.0)
# This ensures Ontology 1 → 1.0 (= Kosha min) and Ontology 10 → 5.0 (= Kosha max)
ONTOLOGY_NORM_OFFSET = 1.0
ONTOLOGY_NORM_SCALE = 4.0 / 9.0  # (kosha_max - kosha_min) / (ontology_max - ontology_min)

# Maximum possible distance between kosha [1,5] and normalized ontology [1,5]
MAX_KOSHA_ONTOLOGY_DISTANCE = 4.0

# Default kosha level when consonant not found (middle ground)
DEFAULT_KOSHA_LEVEL = 3

# Default ontology level when semantic meaning not determined
DEFAULT_ONTOLOGY_LEVEL = 5


# =============================================================================
# SYLLABLE DECOMPOSITION
# =============================================================================


def extract_consonant(syllable: str) -> Optional[str]:
    """Extract the primary consonant from a syllable.

    Handles common romanized consonant patterns including:
    - Aspirated consonants (kh, gh, ch, th, dh, ph, bh, jh)
    - Simple consonants (k, g, c, t, d, p, b, j, m, n, y, r, l, s, sh)

    Returns None for pure vowel syllables.
    """
    if not syllable:
        return None

    syllable = syllable.lower().strip()

    # Check for digraph consonants first (aspirated and compound)
    digraphs = [
        "kh", "gh", "ch", "th", "dh", "ph", "bh", "jh",
        "sh", "ng", "ny",
    ]
    for digraph in digraphs:
        if syllable.startswith(digraph):
            # Map to canonical form
            canonical_map = {
                "kh": "kha", "gh": "gha", "ch": "cha",
                "th": "tha", "dh": "dha", "ph": "pha",
                "bh": "bha", "jh": "jha", "sh": "sha",
            }
            return canonical_map.get(digraph, digraph)

    # Check for single consonants
    if syllable[0].isalpha() and syllable[0] not in "aeiou":
        # Map to canonical form (consonant + 'a')
        cons = syllable[0]
        canonical_map = {
            "k": "ka", "g": "ga", "c": "ca", "j": "ja",
            "t": "ta", "d": "da", "n": "na", "p": "pa",
            "b": "ba", "m": "ma", "y": "ya", "r": "ra",
            "l": "la", "s": "sa", "f": "pha",
        }
        return canonical_map.get(cons, cons)

    return None


def extract_vowel(syllable: str) -> Optional[str]:
    """Extract the primary vowel from a syllable."""
    if not syllable:
        return None

    syllable = syllable.lower().strip()

    # Check for diphthongs
    diphthongs = ["ai", "au", "ei", "ou", "oi"]
    for diph in diphthongs:
        if diph in syllable:
            return diph

    # Check for simple vowels
    for char in syllable:
        if char in "aeiou":
            return char

    return None


def syllabify(word: str) -> List[str]:
    """Split a word into syllables.

    Uses a simple CV (consonant-vowel) pattern recognition.
    """
    if not word:
        return []

    word = word.lower().strip()
    syllables = []
    current = ""

    i = 0
    while i < len(word):
        char = word[i]

        # Check for digraph consonants
        if i < len(word) - 1:
            digraph = word[i:i+2]
            if digraph in ["kh", "gh", "ch", "th", "dh", "ph", "bh", "jh", "sh"]:
                # Start new syllable if current ends with vowel
                if current and current[-1] in "aeiou":
                    syllables.append(current)
                    current = ""
                current += digraph
                i += 2
                continue

        if char in "aeiou":
            current += char
            # Check if next is consonant (could be start of new syllable)
            if i < len(word) - 1 and word[i+1] not in "aeiou":
                syllables.append(current)
                current = ""
        else:
            # Consonant
            if current and current[-1] in "aeiou":
                syllables.append(current)
                current = ""
            current += char

        i += 1

    if current:
        syllables.append(current)

    return syllables if syllables else [word]


# =============================================================================
# KOSHA MAPPING
# =============================================================================


def get_kosha_level(consonant: Optional[str]) -> int:
    """Get the kosha level (1-5) for a consonant.

    Returns DEFAULT_KOSHA_LEVEL if consonant not in mapping.
    """
    if not consonant:
        # Pure vowel syllable - maps to highest (ANANDAMAYA)
        return 5

    info = CONSONANT_TO_KOSHA_MAP.get(consonant)
    if info:
        return info["level"]

    # Try lowercase variant
    info = CONSONANT_TO_KOSHA_MAP.get(consonant.lower())
    if info:
        return info["level"]

    return DEFAULT_KOSHA_LEVEL


def get_kosha_name(level: int) -> str:
    """Get the kosha name for a level."""
    return CANONICAL_KOSHA_LAYERS.get(level, "UNKNOWN")


def get_vritti_for_kosha(kosha_name: str) -> str:
    """Get the dominant vritti tendency for a kosha."""
    desc = KOSHA_DESCRIPTIONS.get(kosha_name, {})
    return desc.get("vritti_tendency", "Unknown")


# =============================================================================
# ONTOLOGY MAPPING
# =============================================================================


# Keyword to ontology layer mapping
SEMANTIC_KEYWORDS: Dict[str, int] = {
    # Execution (1) - Action, doing
    "do": 1, "make": 1, "run": 1, "walk": 1, "act": 1, "execute": 1,
    "perform": 1, "work": 1, "build": 1, "create": 1,

    # Identity (2) - Labels, roles
    "name": 2, "call": 2, "am": 2, "is": 2, "are": 2, "identity": 2,
    "role": 2, "title": 2, "label": 2,

    # Form (3) - Shape, appearance
    "look": 3, "shape": 3, "form": 3, "body": 3, "appear": 3,
    "face": 3, "figure": 3, "physical": 3,

    # Cognition (4) - Thinking
    "think": 4, "mind": 4, "thought": 4, "idea": 4, "concept": 4,
    "mental": 4, "cognitive": 4, "know": 4,

    # Agency (5) - Will, control
    "want": 5, "will": 5, "control": 5, "decide": 5, "choose": 5,
    "ego": 5, "self": 5, "desire": 5,

    # Reasoning (6) - Analysis
    "reason": 6, "analyze": 6, "logic": 6, "understand": 6, "explain": 6,
    "intellect": 6, "discriminate": 6, "judge": 6,

    # Purpose (7) - Meaning, intention
    "purpose": 7, "meaning": 7, "intention": 7, "goal": 7, "aim": 7,
    "soul": 7, "destiny": 7, "mission": 7,

    # Observation (8) - Awareness
    "observe": 8, "watch": 8, "witness": 8, "aware": 8, "notice": 8,
    "see": 8, "perceive": 8, "attention": 8,

    # Core (9) - Essence
    "essence": 9, "core": 9, "true": 9, "atman": 9, "being": 9,
    "exist": 9, "real": 9, "authentic": 9,

    # Universal (10) - Cosmic
    "universal": 10, "cosmic": 10, "infinite": 10, "eternal": 10,
    "divine": 10, "brahman": 10, "absolute": 10, "transcend": 10,
}


def get_ontology_level(word: str, context: Optional[str] = None) -> int:
    """Determine the ontology level (1-10) for a word based on semantics.

    Uses keyword matching and context analysis.
    Returns DEFAULT_ONTOLOGY_LEVEL if meaning cannot be determined.
    """
    if not word:
        return DEFAULT_ONTOLOGY_LEVEL

    word_lower = word.lower().strip()

    # Direct keyword match
    if word_lower in SEMANTIC_KEYWORDS:
        return SEMANTIC_KEYWORDS[word_lower]

    # Check if word contains any keywords
    for keyword, level in SEMANTIC_KEYWORDS.items():
        if keyword in word_lower or word_lower in keyword:
            return level

    # Vowel-based aspect inference (fallback)
    vowel = extract_vowel(word)
    if vowel and vowel in VOWEL_ASPECT_BRIDGES:
        aspect = VOWEL_ASPECT_BRIDGES[vowel]["aspect"]
        aspect_to_level = {
            "EGO": 5,
            "INTELLECT": 6,
            "WITNESS": 8,
        }
        return aspect_to_level.get(aspect, DEFAULT_ONTOLOGY_LEVEL)

    return DEFAULT_ONTOLOGY_LEVEL


def get_ontology_name(level: int) -> str:
    """Get the ontology layer name for a level."""
    for name, data in ONTOLOGICAL_LAYERS.items():
        if data["level"] == level:
            return name
    return "UNKNOWN"


# =============================================================================
# VRITTI DISTRIBUTION COMPUTATION
# =============================================================================


def compute_vritti_distribution(kosha_level: int) -> List[float]:
    """Compute 5-dimensional vritti distribution from kosha level.

    Vritti order: [pramana, viparyaya, vikalpa, smrti, nidra]

    Each kosha has a dominant vritti tendency:
    - ANNAMAYA (1) → nidra dominant
    - PRANAMAYA (2) → vikalpa dominant
    - MANOMAYA (3) → viparyaya dominant
    - VIJNANAMAYA (4) → pramana dominant
    - ANANDAMAYA (5) → pramana dominant (pure)
    """
    # Base distribution (uniform)
    dist = [0.2, 0.2, 0.2, 0.2, 0.2]

    # Vritti indices: pramana=0, viparyaya=1, vikalpa=2, smrti=3, nidra=4
    kosha_to_dominant = {
        1: 4,  # ANNAMAYA → nidra
        2: 2,  # PRANAMAYA → vikalpa
        3: 1,  # MANOMAYA → viparyaya
        4: 0,  # VIJNANAMAYA → pramana
        5: 0,  # ANANDAMAYA → pramana
    }

    dominant_idx = kosha_to_dominant.get(kosha_level, 0)

    # Boost dominant vritti
    boost = 0.3
    dist[dominant_idx] += boost

    # Reduce others proportionally
    reduction = boost / 4
    for i in range(5):
        if i != dominant_idx:
            dist[i] -= reduction

    # Ensure normalization
    total = sum(dist)
    return [v / total for v in dist]


# =============================================================================
# SMI ENGINE
# =============================================================================


class SMIEngine:
    """
    Computes Semantic Mismatch Index between inner and outer layers.

    SMI = normalized geometric distance between:
    - Inner layer (acoustic/kosha derived from consonants)
    - Outer layer (semantic/ontology derived from context)

    SMI ranges from 0.0 (perfect alignment) to 1.0 (maximum tension).

    Usage:
        engine = SMIEngine()
        result = engine.compute("hello")

        # Per-word analysis
        words = engine.compute_per_word(["hello", "world"])

        # Component breakdown
        components = engine.get_components("hello")
    """

    def __init__(self) -> None:
        """Initialize the SMI engine."""
        self._cache: Dict[str, SMIResult] = {}

    def compute(self, text: str, context: Optional[str] = None) -> SMIResult:
        """Compute SMI for text.

        Args:
            text: The text to analyze
            context: Optional context for semantic interpretation

        Returns:
            SMIResult with smi score and component breakdown
        """
        if not text:
            return SMIResult(
                smi=0.0,
                inner_kosha=DEFAULT_KOSHA_LEVEL,
                outer_ontology=DEFAULT_ONTOLOGY_LEVEL,
                components={},
                interpretation="Empty input",
            )

        # Check cache
        cache_key = f"{text}:{context or ''}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        # Split into words
        words = re.findall(r'\b\w+\b', text.lower())
        if not words:
            return SMIResult(
                smi=0.0,
                inner_kosha=DEFAULT_KOSHA_LEVEL,
                outer_ontology=DEFAULT_ONTOLOGY_LEVEL,
                components={},
                interpretation="No words found",
            )

        # Compute per-word SMI and aggregate
        word_results = self._analyze_words(words, context)

        # Aggregate: weighted average by word length
        total_weight = sum(len(w) for w in words)
        avg_smi = sum(
            wr.smi * len(words[i]) / total_weight
            for i, wr in enumerate(word_results)
        )

        # Compute average inner/outer layers
        avg_inner = sum(wr.inner_kosha for wr in word_results) / len(word_results)
        avg_outer = sum(wr.outer_ontology for wr in word_results) / len(word_results)

        # Determine interpretation
        interpretation = self._interpret_smi(avg_smi)

        result = SMIResult(
            smi=round(avg_smi, 4),
            inner_kosha=round(avg_inner),
            outer_ontology=round(avg_outer),
            components={
                "word_count": len(words),
                "avg_inner_kosha": round(avg_inner, 2),
                "avg_outer_ontology": round(avg_outer, 2),
                "words": [w.word for w in word_results[:5]],  # First 5
            },
            interpretation=interpretation,
        )

        self._cache[cache_key] = result
        return result

    def compute_per_word(self, words: List[str], context: Optional[str] = None) -> List[WordAnalysis]:
        """Compute SMI for each word.

        Args:
            words: List of words to analyze
            context: Optional context for semantic interpretation

        Returns:
            List of WordAnalysis objects
        """
        return self._analyze_words(words, context)

    def get_components(self, text: str, context: Optional[str] = None) -> Dict[str, float]:
        """Get SMI component breakdown.

        Args:
            text: Text to analyze
            context: Optional context

        Returns:
            Dictionary with component values
        """
        result = self.compute(text, context)

        # Get detailed syllable breakdown for first word
        words = re.findall(r'\b\w+\b', text.lower())
        if not words:
            return {"smi": 0.0}

        first_word = words[0]
        syllables = syllabify(first_word)
        syllable_analyses = []

        for syl in syllables:
            consonant = extract_consonant(syl)
            vowel = extract_vowel(syl)
            kosha_level = get_kosha_level(consonant)
            vritti_dist = compute_vritti_distribution(kosha_level)

            syllable_analyses.append({
                "syllable": syl,
                "consonant": consonant,
                "vowel": vowel,
                "kosha_level": kosha_level,
                "kosha_name": get_kosha_name(kosha_level),
                "vritti_distribution": vritti_dist,
            })

        return {
            "smi": result.smi,
            "inner_kosha": result.inner_kosha,
            "outer_ontology": result.outer_ontology,
            "interpretation": result.interpretation,
            "syllables": syllable_analyses,
        }

    def analyze_syllable(self, syllable: str) -> SyllableAnalysis:
        """Analyze a single syllable.

        Args:
            syllable: The syllable to analyze

        Returns:
            SyllableAnalysis with consonant, vowel, kosha, and vritti
        """
        consonant = extract_consonant(syllable)
        vowel = extract_vowel(syllable)
        kosha_level = get_kosha_level(consonant)
        vritti_dist = compute_vritti_distribution(kosha_level)

        return SyllableAnalysis(
            syllable=syllable,
            consonant=consonant,
            vowel=vowel,
            kosha_id=kosha_level,
            vritti_distribution=vritti_dist,
        )

    def _analyze_words(
        self,
        words: List[str],
        context: Optional[str] = None,
    ) -> List[WordAnalysis]:
        """Analyze a list of words."""
        results = []

        for word in words:
            # Get syllables
            syllables = syllabify(word)
            syllable_analyses = [self.analyze_syllable(s) for s in syllables]

            # Compute average inner kosha from syllables
            if syllable_analyses:
                avg_kosha = sum(s.kosha_id or DEFAULT_KOSHA_LEVEL for s in syllable_analyses) / len(syllable_analyses)
            else:
                avg_kosha = DEFAULT_KOSHA_LEVEL

            # Get outer ontology level
            ontology_level = get_ontology_level(word, context)

            # Normalize ontology [1,10] to kosha-aligned [1.0, 5.0] and compute SMI
            normalized_ontology = ONTOLOGY_NORM_OFFSET + (ontology_level - 1) * ONTOLOGY_NORM_SCALE
            smi = abs(avg_kosha - normalized_ontology) / MAX_KOSHA_ONTOLOGY_DISTANCE

            results.append(WordAnalysis(
                word=word,
                syllables=syllable_analyses,
                ontology_layer=ontology_level,
                inner_kosha=round(avg_kosha),
                outer_ontology=ontology_level,
                smi=round(smi, 4),
            ))

        return results

    def _interpret_smi(self, smi: float) -> str:
        """Generate human-readable interpretation of SMI value."""
        if smi < SMI_THRESHOLDS["LOW"]:
            return "Low tension: Sound and meaning are well-aligned"
        elif smi < SMI_THRESHOLDS["MODERATE"]:
            return "Moderate tension: Some mismatch between acoustic and semantic layers"
        elif smi < SMI_THRESHOLDS["HIGH"]:
            return "High tension: Significant gap between inner and outer meaning"
        else:
            return "Critical tension: Maximum divergence between sound and meaning"

    def clear_cache(self) -> None:
        """Clear the computation cache."""
        self._cache.clear()


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================


def compute_smi(text: str, context: Optional[str] = None) -> float:
    """Convenience function to compute SMI for text.

    Args:
        text: Text to analyze
        context: Optional context

    Returns:
        SMI value (0.0 - 1.0)
    """
    engine = SMIEngine()
    return engine.compute(text, context).smi


def analyze_word(word: str) -> WordAnalysis:
    """Convenience function to analyze a single word.

    Args:
        word: Word to analyze

    Returns:
        WordAnalysis object
    """
    engine = SMIEngine()
    results = engine.compute_per_word([word])
    return results[0] if results else WordAnalysis(word=word)


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "SMIEngine",
    "SMIResult",
    "SyllableAnalysis",
    "WordAnalysis",
    "compute_smi",
    "analyze_word",
    "extract_consonant",
    "extract_vowel",
    "syllabify",
    "get_kosha_level",
    "get_ontology_level",
    "compute_vritti_distribution",
]
