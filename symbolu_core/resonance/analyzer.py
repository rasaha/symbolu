"""
Phonetic Resonance Engine - High-Level Analyzer
================================================

Provides simple API for analyzing words and phrases.

Main functions:
- analyze_word: Convert a word to its 10D ontological vector
- analyze_phrase: Analyze phonetic harmony in a phrase
- compare_words: Compare two words for resonance
- compare_phrases: Compare two phrases for relative harmony
"""

from typing import Tuple, List, Dict, Optional
import re

from symbolu_core.resonance.types import (
    WordVector,
    ResonanceResult,
    PhraseAnalysis,
    ComparisonResult,
)
from symbolu_core.resonance.engine import (
    word_to_vector,
    compute_resonance,
    analyze_phrase_vectors,
    compare_phrases as _compare_phrase_analyses,
)


# =============================================================================
# Phoneme Dictionary (Embedded for Independence)
# =============================================================================

# Common words with ARPABET phonemes
PHONEME_DICT: Dict[str, Tuple[str, ...]] = {
    # Core content words for demonstration
    "sky": ("S", "K", "AY"),
    "blue": ("B", "L", "UW"),
    "red": ("R", "EH", "D"),
    "truth": ("T", "R", "UW", "TH"),
    "light": ("L", "AY", "T"),
    "darkness": ("D", "AA", "R", "K", "N", "AH", "S"),
    "love": ("L", "AH", "V"),
    "peace": ("P", "IY", "S"),
    "war": ("W", "AO", "R"),
    "hate": ("HH", "EY", "T"),
    "beauty": ("B", "Y", "UW", "T", "IY"),
    "justice": ("JH", "AH", "S", "T", "IH", "S"),
    "freedom": ("F", "R", "IY", "D", "AH", "M"),
    "power": ("P", "AW", "ER"),
    "knowledge": ("N", "AA", "L", "IH", "JH"),
    "wisdom": ("W", "IH", "Z", "D", "AH", "M"),
    "time": ("T", "AY", "M"),
    "life": ("L", "AY", "F"),
    "death": ("D", "EH", "TH"),
    "hope": ("HH", "OW", "P"),
    "fear": ("F", "IY", "R"),
    "joy": ("JH", "OY"),
    "sorrow": ("S", "AA", "R", "OW"),
    "sun": ("S", "AH", "N"),
    "moon": ("M", "UW", "N"),
    "star": ("S", "T", "AA", "R"),
    "earth": ("ER", "TH"),
    "water": ("W", "AO", "T", "ER"),
    "fire": ("F", "AY", "R"),
    "air": ("EH", "R"),
    "stone": ("S", "T", "OW", "N"),
    "tree": ("T", "R", "IY"),
    "flower": ("F", "L", "AW", "ER"),
    "river": ("R", "IH", "V", "ER"),
    "mountain": ("M", "AW", "N", "T", "AH", "N"),
    "ocean": ("OW", "SH", "AH", "N"),
    "wind": ("W", "IH", "N", "D"),
    "rain": ("R", "EY", "N"),
    "snow": ("S", "N", "OW"),
    "cloud": ("K", "L", "AW", "D"),
    "heart": ("HH", "AA", "R", "T"),
    "mind": ("M", "AY", "N", "D"),
    "soul": ("S", "OW", "L"),
    "spirit": ("S", "P", "IH", "R", "IH", "T"),
    "body": ("B", "AA", "D", "IY"),
    "thought": ("TH", "AO", "T"),
    "dream": ("D", "R", "IY", "M"),
    "word": ("W", "ER", "D"),
    "voice": ("V", "OY", "S"),
    "silence": ("S", "AY", "L", "AH", "N", "S"),
    "music": ("M", "Y", "UW", "Z", "IH", "K"),
    "song": ("S", "AO", "NG"),
    "dance": ("D", "AE", "N", "S"),
    "art": ("AA", "R", "T"),
    "science": ("S", "AY", "AH", "N", "S"),
    "nature": ("N", "EY", "CH", "ER"),
    "spirit": ("S", "P", "IH", "R", "IH", "T"),
    "god": ("G", "AA", "D"),
    "man": ("M", "AE", "N"),
    "woman": ("W", "UH", "M", "AH", "N"),
    "child": ("CH", "AY", "L", "D"),
    "mother": ("M", "AH", "DH", "ER"),
    "father": ("F", "AA", "DH", "ER"),
    "friend": ("F", "R", "EH", "N", "D"),
    "enemy": ("EH", "N", "AH", "M", "IY"),
    "king": ("K", "IH", "NG"),
    "queen": ("K", "W", "IY", "N"),
    "hero": ("HH", "IY", "R", "OW"),
    "villain": ("V", "IH", "L", "AH", "N"),
    "good": ("G", "UH", "D"),
    "evil": ("IY", "V", "AH", "L"),
    "right": ("R", "AY", "T"),
    "wrong": ("R", "AO", "NG"),
    "true": ("T", "R", "UW"),
    "false": ("F", "AO", "L", "S"),
    "bright": ("B", "R", "AY", "T"),
    "dark": ("D", "AA", "R", "K"),
    "warm": ("W", "AO", "R", "M"),
    "cold": ("K", "OW", "L", "D"),
    "soft": ("S", "AO", "F", "T"),
    "hard": ("HH", "AA", "R", "D"),
    "fast": ("F", "AE", "S", "T"),
    "slow": ("S", "L", "OW"),
    "high": ("HH", "AY"),
    "low": ("L", "OW"),
    "big": ("B", "IH", "G"),
    "small": ("S", "M", "AO", "L"),
    "old": ("OW", "L", "D"),
    "young": ("Y", "AH", "NG"),
    "new": ("N", "UW"),
    "ancient": ("EY", "N", "CH", "AH", "N", "T"),
    "is": ("IH", "Z"),
    "the": ("DH", "AH"),
    "a": ("AH",),
    "and": ("AE", "N", "D"),
    "of": ("AH", "V"),
    "to": ("T", "UW"),
    "in": ("IH", "N"),
    "for": ("F", "AO", "R"),
    "on": ("AA", "N"),
    "with": ("W", "IH", "TH"),
    "as": ("AE", "Z"),
    "at": ("AE", "T"),
    "by": ("B", "AY"),
    "from": ("F", "R", "AH", "M"),
    "or": ("AO", "R"),
    "but": ("B", "AH", "T"),
    "not": ("N", "AA", "T"),
    "be": ("B", "IY"),
    "are": ("AA", "R"),
    "was": ("W", "AA", "Z"),
    "were": ("W", "ER"),
    "been": ("B", "IH", "N"),
    "have": ("HH", "AE", "V"),
    "has": ("HH", "AE", "Z"),
    "had": ("HH", "AE", "D"),
    "do": ("D", "UW"),
    "does": ("D", "AH", "Z"),
    "did": ("D", "IH", "D"),
    "will": ("W", "IH", "L"),
    "would": ("W", "UH", "D"),
    "could": ("K", "UH", "D"),
    "should": ("SH", "UH", "D"),
    "may": ("M", "EY"),
    "might": ("M", "AY", "T"),
    "must": ("M", "AH", "S", "T"),
    "can": ("K", "AE", "N"),
    "this": ("DH", "IH", "S"),
    "that": ("DH", "AE", "T"),
    "these": ("DH", "IY", "Z"),
    "those": ("DH", "OW", "Z"),
    "what": ("W", "AH", "T"),
    "which": ("W", "IH", "CH"),
    "who": ("HH", "UW"),
    "whom": ("HH", "UW", "M"),
    "whose": ("HH", "UW", "Z"),
    "where": ("W", "EH", "R"),
    "when": ("W", "EH", "N"),
    "why": ("W", "AY"),
    "how": ("HH", "AW"),
    "all": ("AO", "L"),
    "each": ("IY", "CH"),
    "every": ("EH", "V", "R", "IY"),
    "both": ("B", "OW", "TH"),
    "few": ("F", "Y", "UW"),
    "more": ("M", "AO", "R"),
    "most": ("M", "OW", "S", "T"),
    "some": ("S", "AH", "M"),
    "any": ("EH", "N", "IY"),
    "no": ("N", "OW"),
    "none": ("N", "AH", "N"),
    "one": ("W", "AH", "N"),
    "two": ("T", "UW"),
    "three": ("TH", "R", "IY"),
    "four": ("F", "AO", "R"),
    "five": ("F", "AY", "V"),
    "i": ("AY",),
    "you": ("Y", "UW"),
    "he": ("HH", "IY"),
    "she": ("SH", "IY"),
    "it": ("IH", "T"),
    "we": ("W", "IY"),
    "they": ("DH", "EY"),
    "me": ("M", "IY"),
    "him": ("HH", "IH", "M"),
    "her": ("HH", "ER"),
    "us": ("AH", "S"),
    "them": ("DH", "EH", "M"),
    "my": ("M", "AY"),
    "your": ("Y", "AO", "R"),
    "his": ("HH", "IH", "Z"),
    "its": ("IH", "T", "S"),
    "our": ("AW", "ER"),
    "their": ("DH", "EH", "R"),
}

# Grapheme-to-phoneme fallback rules
GRAPHEME_RULES: Dict[str, Tuple[str, ...]] = {
    "a": ("AE",), "e": ("EH",), "i": ("IH",), "o": ("AA",), "u": ("AH",),
    "b": ("B",), "c": ("K",), "d": ("D",), "f": ("F",), "g": ("G",),
    "h": ("HH",), "j": ("JH",), "k": ("K",), "l": ("L",), "m": ("M",),
    "n": ("N",), "p": ("P",), "q": ("K",), "r": ("R",), "s": ("S",),
    "t": ("T",), "v": ("V",), "w": ("W",), "x": ("K", "S"), "y": ("Y",),
    "z": ("Z",),
}

DIGRAPH_RULES: Dict[str, Tuple[str, ...]] = {
    "ch": ("CH",), "sh": ("SH",), "th": ("TH",), "ph": ("F",),
    "wh": ("W",), "ck": ("K",), "ng": ("NG",), "qu": ("K", "W"),
    "ee": ("IY",), "ea": ("IY",), "oo": ("UW",), "ai": ("EY",),
    "ay": ("EY",), "ey": ("IY",), "ou": ("AW",), "ow": ("OW",),
    "oi": ("OY",), "oy": ("OY",), "ie": ("IY",), "igh": ("AY",),
}


# =============================================================================
# Phoneme Extraction
# =============================================================================

def get_phonemes(word: str) -> Tuple[str, ...]:
    """
    Get phonemes for a word.

    Uses dictionary lookup first, then fallback rules.

    Args:
        word: The word to convert

    Returns:
        Tuple of ARPABET phoneme symbols
    """
    word_lower = word.strip().lower()

    # Try dictionary
    if word_lower in PHONEME_DICT:
        return PHONEME_DICT[word_lower]

    # Fallback to rules
    return _apply_rules(word_lower)


def _apply_rules(word: str) -> Tuple[str, ...]:
    """Apply grapheme-to-phoneme rules."""
    phonemes: List[str] = []
    i = 0

    while i < len(word):
        matched = False

        # Try digraphs first (longest match)
        for length in [3, 2]:
            if i + length <= len(word):
                chunk = word[i:i+length]
                if chunk in DIGRAPH_RULES:
                    phonemes.extend(DIGRAPH_RULES[chunk])
                    i += length
                    matched = True
                    break

        if not matched:
            char = word[i]
            if char in GRAPHEME_RULES:
                phonemes.extend(GRAPHEME_RULES[char])
            i += 1

    return tuple(phonemes)


# =============================================================================
# Word Analysis
# =============================================================================

def analyze_word(word: str) -> WordVector:
    """
    Analyze a word and return its 10D ontological vector.

    Args:
        word: The word to analyze

    Returns:
        WordVector with normalized 10D projection

    Example:
        >>> vec = analyze_word("love")
        >>> print(vec.dominant_layer)  # e.g., "O10_UNIFYING"
    """
    phonemes = get_phonemes(word)
    return word_to_vector(word, phonemes)


# =============================================================================
# Word Comparison
# =============================================================================

def compare_words(word_a: str, word_b: str) -> ResonanceResult:
    """
    Compare two words for phonetic resonance.

    Args:
        word_a: First word
        word_b: Second word

    Returns:
        ResonanceResult with similarity and analysis

    Example:
        >>> result = compare_words("sky", "blue")
        >>> print(f"Similarity: {result.similarity:.2f}")
        >>> print(f"Harmonic: {result.harmonic}")
    """
    vec_a = analyze_word(word_a)
    vec_b = analyze_word(word_b)
    return compute_resonance(vec_a, vec_b)


# =============================================================================
# Phrase Analysis
# =============================================================================

# Stop words to filter out
STOP_WORDS = frozenset({
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "must", "can", "shall", "and", "or", "but",
    "if", "then", "else", "when", "where", "why", "how", "what", "which",
    "who", "whom", "whose", "that", "this", "these", "those", "it", "its",
    "of", "to", "in", "for", "on", "with", "at", "by", "from", "as",
    "i", "you", "he", "she", "we", "they", "me", "him", "her", "us", "them",
    "my", "your", "his", "our", "their",
})


def extract_content_words(phrase: str) -> Tuple[str, ...]:
    """
    Extract content words from a phrase (filter stop words).

    Args:
        phrase: Input phrase

    Returns:
        Tuple of content words
    """
    # Tokenize: split on whitespace and punctuation
    words = re.findall(r"[a-zA-Z]+", phrase.lower())
    # Filter stop words
    return tuple(w for w in words if w not in STOP_WORDS)


def analyze_phrase(phrase: str) -> PhraseAnalysis:
    """
    Analyze phonetic harmony in a phrase.

    Args:
        phrase: The phrase to analyze

    Returns:
        PhraseAnalysis with harmony/dissonance prediction

    Example:
        >>> result = analyze_phrase("The sky is blue")
        >>> print(f"Harmony: {result.overall_harmony:.2f}")
        >>> print(f"Prediction: {result.prediction}")
    """
    content_words = extract_content_words(phrase)

    if not content_words:
        return PhraseAnalysis(
            phrase=phrase,
            words=(),
            pairwise_resonance=(),
            overall_harmony=0.0,
            overall_dissonance=0.0,
            prediction="NEUTRAL",
            key_resonances=(),
        )

    # Analyze each content word
    word_vectors = tuple(analyze_word(w) for w in content_words)

    # Compute phrase-level metrics
    analysis = analyze_phrase_vectors(word_vectors)

    # Override phrase with original
    return PhraseAnalysis(
        phrase=phrase,
        words=analysis.words,
        pairwise_resonance=analysis.pairwise_resonance,
        overall_harmony=analysis.overall_harmony,
        overall_dissonance=analysis.overall_dissonance,
        prediction=analysis.prediction,
        key_resonances=analysis.key_resonances,
    )


# =============================================================================
# Phrase Comparison
# =============================================================================

def compare_phrases(phrase_a: str, phrase_b: str) -> ComparisonResult:
    """
    Compare two phrases for relative phonetic harmony.

    Args:
        phrase_a: First phrase
        phrase_b: Second phrase

    Returns:
        ComparisonResult indicating which is more harmonic

    Example:
        >>> result = compare_phrases("The sky is blue", "The sky is red")
        >>> print(f"More harmonic: {result.more_harmonic}")
        >>> print(f"Insight: {result.insight}")
    """
    analysis_a = analyze_phrase(phrase_a)
    analysis_b = analyze_phrase(phrase_b)

    comparison = _compare_phrase_analyses(analysis_a, analysis_b)

    return ComparisonResult(
        phrase_a=phrase_a,
        phrase_b=phrase_b,
        analysis_a=analysis_a,
        analysis_b=analysis_b,
        harmony_difference=comparison["harmony_difference"],
        more_harmonic=comparison["more_harmonic"],
        insight=comparison["insight"],
    )


# =============================================================================
# Convenience Functions
# =============================================================================

def quick_compare(phrase_a: str, phrase_b: str) -> str:
    """
    Quick comparison returning a simple verdict.

    Args:
        phrase_a: First phrase
        phrase_b: Second phrase

    Returns:
        Human-readable comparison result

    Example:
        >>> print(quick_compare("Truth is light", "Truth is darkness"))
        "Truth is light" has stronger phonetic resonance (0.72 vs 0.48)
    """
    result = compare_phrases(phrase_a, phrase_b)
    return (
        f'"{result.more_harmonic}" has stronger phonetic resonance '
        f'({result.analysis_a.overall_harmony:.2f} vs '
        f'{result.analysis_b.overall_harmony:.2f})'
    )


def word_resonance_report(word: str) -> str:
    """
    Generate a human-readable report for a word's phonetic profile.

    Args:
        word: The word to analyze

    Returns:
        Formatted report string
    """
    vec = analyze_word(word)

    lines = [
        f"Word: {word}",
        f"Phonemes: {' '.join(vec.phonemes)}",
        f"Dominant Layer: {vec.dominant_layer} ({vec.dominant_score:.2f})",
        "Top 3 Layers:",
    ]

    for layer, score in vec.get_top_layers(3):
        lines.append(f"  - {layer}: {score:.2f}")

    return "\n".join(lines)


def phrase_harmony_report(phrase: str) -> str:
    """
    Generate a human-readable harmony report for a phrase.

    Args:
        phrase: The phrase to analyze

    Returns:
        Formatted report string
    """
    analysis = analyze_phrase(phrase)

    lines = [
        f"Phrase: {phrase}",
        f"Content Words: {', '.join(w.word for w in analysis.words)}",
        f"Overall Harmony: {analysis.overall_harmony:.2f}",
        f"Prediction: {analysis.prediction}",
    ]

    if analysis.key_resonances:
        lines.append("Key Word Pairs:")
        for res in analysis.key_resonances:
            status = "✓" if res.harmonic else ("✗" if res.dissonant else "○")
            lines.append(
                f"  {status} {res.word_a} ↔ {res.word_b}: {res.similarity:.2f}"
            )

    return "\n".join(lines)


# =============================================================================
# Varṇa-Based Analysis (Enhanced Sanskrit Phoneme System)
# =============================================================================

def analyze_word_varna(word: str) -> WordVector:
    """
    Analyze a word using Varṇa-based affinities (Sanskrit phoneme system).

    This uses the enhanced Varṇa mappings that include:
    - Bridge meanings (semantic associations per phoneme)
    - Layer descriptions (ontological layer activation)
    - Polarity information (positive/negative manifestations)

    Args:
        word: The word to analyze

    Returns:
        WordVector with 10D projection based on Varṇa affinities

    Example:
        >>> vec = analyze_word_varna("truth")
        >>> print(vec.dominant_layer)
    """
    from symbolu_core.resonance.varna_bridge import varna_word_to_vector
    phonemes = get_phonemes(word)
    return varna_word_to_vector(word, phonemes)


def analyze_phrase_varna(phrase: str) -> PhraseAnalysis:
    """
    Analyze phonetic harmony using Varṇa-based affinities.

    Args:
        phrase: The phrase to analyze

    Returns:
        PhraseAnalysis with harmony/dissonance using Varṇa system
    """
    content_words = extract_content_words(phrase)

    if not content_words:
        return PhraseAnalysis(
            phrase=phrase,
            words=(),
            pairwise_resonance=(),
            overall_harmony=0.0,
            overall_dissonance=0.0,
            prediction="NEUTRAL",
            key_resonances=(),
        )

    # Analyze each content word using Varṇa
    word_vectors = tuple(analyze_word_varna(w) for w in content_words)

    # Compute phrase-level metrics
    analysis = analyze_phrase_vectors(word_vectors)

    return PhraseAnalysis(
        phrase=phrase,
        words=analysis.words,
        pairwise_resonance=analysis.pairwise_resonance,
        overall_harmony=analysis.overall_harmony,
        overall_dissonance=analysis.overall_dissonance,
        prediction=analysis.prediction,
        key_resonances=analysis.key_resonances,
    )


def compare_arpabet_vs_varna(word: str) -> str:
    """
    Compare ARPABET vs Varṇa analysis for a word.

    Args:
        word: The word to analyze

    Returns:
        Formatted comparison string

    Example:
        >>> print(compare_arpabet_vs_varna("truth"))
    """
    from symbolu_core.resonance.varna_bridge import phonemes_to_varnas

    arpabet_vec = analyze_word(word)
    varna_vec = analyze_word_varna(word)

    # Get phonemes and varnas
    phonemes = get_phonemes(word)
    varnas = phonemes_to_varnas(phonemes)

    lines = [
        f"Word: {word}",
        "",
        "=== ARPABET Analysis ===",
        f"Phonemes: {' '.join(phonemes)}",
        f"Dominant Layer: {arpabet_vec.dominant_layer} ({arpabet_vec.dominant_score:.3f})",
        "",
        "=== Varṇa Analysis ===",
        f"Varṇas: {' '.join(varnas)}",
        f"Dominant Layer: {varna_vec.dominant_layer} ({varna_vec.dominant_score:.3f})",
        "",
        "=== Layer Comparison ===",
    ]

    # Compare each layer
    layer_names = [
        "O3_EXECUTION", "O2_IDENTITY", "O4_STRUCTURE", "O5_COGNITION", "O6_AGENCY",
        "O7_REASONING", "O8_PURPOSE", "O9_WITNESSES", "O10_UNIFYING", "O12_ABSOLVING"
    ]

    for i, layer in enumerate(layer_names):
        arp_val = arpabet_vec.vector[i]
        var_val = varna_vec.vector[i]
        diff = var_val - arp_val
        diff_str = f"+{diff:.3f}" if diff >= 0 else f"{diff:.3f}"
        lines.append(f"  {layer:20s}: ARPABET={arp_val:.3f}  Varṇa={var_val:.3f}  Δ={diff_str}")

    return "\n".join(lines)
