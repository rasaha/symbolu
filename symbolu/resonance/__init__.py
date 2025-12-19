"""
Phonetic Resonance Engine
=========================

Computes phonetic harmony between words based on their
10-dimensional ontological projections.

Core Hypothesis:
    Words with similar phonetic structures resonate on the same
    ontological dimensions. "Truth is light" feels natural because
    both words share OPEN, EXPANSIVE phonetic character.

Usage:
    from symbolu.resonance import analyze_phrase, compare_words

    # Analyze a phrase
    result = analyze_phrase("truth is light")
    print(result.overall_harmony)  # 0.81
    print(result.prediction)       # "HARMONIC"

    # Compare two words
    resonance = compare_words("sky", "blue")
    print(resonance.similarity)    # 0.82
"""

from symbolu.resonance.types import (
    PhonemeCategory,
    OntologicalLayer,
    PhonemeProfile,
    WordVector,
    ResonanceResult,
    PhraseAnalysis,
    ComparisonResult,
    LAYER_NAMES,
)

from symbolu.resonance.engine import (
    word_to_vector,
    compute_resonance,
    analyze_phrase_vectors,
    compare_phrases as compare_phrase_analyses,
    HARMONY_THRESHOLD,
    DISSONANCE_THRESHOLD,
)

from symbolu.resonance.phoneme_map import (
    get_phoneme_profile,
    get_layer_affinities,
    get_phoneme_category,
    is_vowel,
    is_consonant,
    list_phonemes,
    PHONEME_PROFILES,
)

from symbolu.resonance.analyzer import (
    analyze_word,
    analyze_phrase,
    compare_words,
    compare_phrases,
    quick_compare,
    word_resonance_report,
    phrase_harmony_report,
    get_phonemes,
    extract_content_words,
    # Varṇa-based analyzer functions
    analyze_word_varna,
    analyze_phrase_varna,
    compare_arpabet_vs_varna,
)

from symbolu.resonance.varna_bridge import (
    varna_to_10d_vector,
    varna_word_to_vector,
    english_phoneme_to_varna,
    phonemes_to_varnas,
    get_varna_affinities,
    get_bridge_meaning,
    list_varnas,
    ENGLISH_TO_VARNA,
)

__all__ = [
    # Types
    "PhonemeCategory",
    "OntologicalLayer",
    "PhonemeProfile",
    "WordVector",
    "ResonanceResult",
    "PhraseAnalysis",
    "ComparisonResult",
    "LAYER_NAMES",
    # Engine functions
    "word_to_vector",
    "compute_resonance",
    "analyze_phrase_vectors",
    "compare_phrase_analyses",
    "HARMONY_THRESHOLD",
    "DISSONANCE_THRESHOLD",
    # Phoneme map
    "get_phoneme_profile",
    "get_layer_affinities",
    "get_phoneme_category",
    "is_vowel",
    "is_consonant",
    "list_phonemes",
    "PHONEME_PROFILES",
    # High-level analyzer functions
    "analyze_word",
    "analyze_phrase",
    "compare_words",
    "compare_phrases",
    "quick_compare",
    "word_resonance_report",
    "phrase_harmony_report",
    "get_phonemes",
    "extract_content_words",
    # Varṇa-based analyzer functions
    "analyze_word_varna",
    "analyze_phrase_varna",
    "compare_arpabet_vs_varna",
    # Varṇa bridge functions
    "varna_to_10d_vector",
    "varna_word_to_vector",
    "english_phoneme_to_varna",
    "phonemes_to_varnas",
    "get_varna_affinities",
    "get_bridge_meaning",
    "list_varnas",
    "ENGLISH_TO_VARNA",
]
