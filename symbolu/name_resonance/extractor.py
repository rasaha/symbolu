"""
Name Resonance System - Signal Extraction
==========================================

Layer 2: Extract mechanical, rule-based features from normalized input.

Tier: Core/Substrate (Tier 1)
Determinism: FULL (same input → same output)
"""

from typing import Tuple, List, Dict
import re

from symbolu.name_resonance.types import (
    NormalizedInput,
    ExtractedSignals,
    ScriptFamily,
)
from symbolu.resonance.phoneme_map import (
    PHONEME_PROFILES,
    PHONEME_CATEGORIES,
    PhonemeCategory,
)


# =============================================================================
# Extended Phoneme Dictionary for Names
# =============================================================================

# Common name phoneme patterns (ARPABET)
NAME_PHONEME_DICT: Dict[str, Tuple[str, ...]] = {
    # Common first names
    "john": ("JH", "AA", "N"),
    "james": ("JH", "EY", "M", "Z"),
    "michael": ("M", "AY", "K", "AH", "L"),
    "david": ("D", "EY", "V", "IH", "D"),
    "robert": ("R", "AA", "B", "ER", "T"),
    "william": ("W", "IH", "L", "Y", "AH", "M"),
    "mary": ("M", "EH", "R", "IY"),
    "sarah": ("S", "EH", "R", "AH"),
    "elizabeth": ("IH", "L", "IH", "Z", "AH", "B", "EH", "TH"),
    "jennifer": ("JH", "EH", "N", "IH", "F", "ER"),

    # Common surnames
    "smith": ("S", "M", "IH", "TH"),
    "johnson": ("JH", "AA", "N", "S", "AH", "N"),
    "williams": ("W", "IH", "L", "Y", "AH", "M", "Z"),
    "brown": ("B", "R", "AW", "N"),
    "jones": ("JH", "OW", "N", "Z"),
    "miller": ("M", "IH", "L", "ER"),
    "davis": ("D", "EY", "V", "IH", "S"),
    "wilson": ("W", "IH", "L", "S", "AH", "N"),
    "campbell": ("K", "AE", "M", "P", "B", "AH", "L"),
    "anderson": ("AE", "N", "D", "ER", "S", "AH", "N"),
    "taylor": ("T", "EY", "L", "ER"),
    "thomas": ("T", "AA", "M", "AH", "S"),
    "jackson": ("JH", "AE", "K", "S", "AH", "N"),
    "white": ("W", "AY", "T"),
    "harris": ("HH", "AE", "R", "IH", "S"),
    "martin": ("M", "AA", "R", "T", "IH", "N"),
    "thompson": ("T", "AA", "M", "P", "S", "AH", "N"),
    "garcia": ("G", "AA", "R", "S", "IY", "AH"),
    "martinez": ("M", "AA", "R", "T", "IY", "N", "EH", "Z"),
    "robinson": ("R", "AA", "B", "IH", "N", "S", "AH", "N"),
    "clark": ("K", "L", "AA", "R", "K"),
    "rodriguez": ("R", "AA", "D", "R", "IY", "G", "EH", "Z"),
    "lewis": ("L", "UW", "IH", "S"),
    "lee": ("L", "IY"),
    "walker": ("W", "AO", "K", "ER"),
    "hall": ("HH", "AO", "L"),
    "allen": ("AE", "L", "AH", "N"),
    "young": ("Y", "AH", "NG"),
    "king": ("K", "IH", "NG"),
    "wright": ("R", "AY", "T"),
    "scott": ("S", "K", "AA", "T"),
    "green": ("G", "R", "IY", "N"),
    "baker": ("B", "EY", "K", "ER"),
    "adams": ("AE", "D", "AH", "M", "Z"),
    "nelson": ("N", "EH", "L", "S", "AH", "N"),
    "hill": ("HH", "IH", "L"),
    "ramirez": ("R", "AH", "M", "IY", "R", "EH", "Z"),
    "campbell": ("K", "AE", "M", "P", "B", "AH", "L"),
    "mitchell": ("M", "IH", "CH", "AH", "L"),
    "roberts": ("R", "AA", "B", "ER", "T", "S"),
    "carter": ("K", "AA", "R", "T", "ER"),
    "phillips": ("F", "IH", "L", "IH", "P", "S"),
    "evans": ("EH", "V", "AH", "N", "Z"),
    "turner": ("T", "ER", "N", "ER"),
    "torres": ("T", "AO", "R", "EH", "S"),
    "parker": ("P", "AA", "R", "K", "ER"),
    "collins": ("K", "AA", "L", "IH", "N", "Z"),
    "edwards": ("EH", "D", "W", "ER", "D", "Z"),
    "stewart": ("S", "T", "UW", "ER", "T"),
    "sanchez": ("S", "AE", "N", "CH", "EH", "Z"),
    "morris": ("M", "AO", "R", "IH", "S"),
    "rogers": ("R", "AA", "JH", "ER", "Z"),
    "reed": ("R", "IY", "D"),
    "cook": ("K", "UH", "K"),
    "morgan": ("M", "AO", "R", "G", "AH", "N"),
    "bell": ("B", "EH", "L"),
    "murphy": ("M", "ER", "F", "IY"),
    "bailey": ("B", "EY", "L", "IY"),
    "rivera": ("R", "IH", "V", "EH", "R", "AH"),
    "cooper": ("K", "UW", "P", "ER"),
    "richardson": ("R", "IH", "CH", "ER", "D", "S", "AH", "N"),
    "cox": ("K", "AA", "K", "S"),
    "howard": ("HH", "AW", "ER", "D"),
    "ward": ("W", "AO", "R", "D"),
    "torres": ("T", "AO", "R", "EH", "Z"),
    "peterson": ("P", "IY", "T", "ER", "S", "AH", "N"),
    "gray": ("G", "R", "EY"),
    "ramirez": ("R", "AH", "M", "IY", "R", "EH", "Z"),
    "james": ("JH", "EY", "M", "Z"),
    "watson": ("W", "AA", "T", "S", "AH", "N"),
    "brooks": ("B", "R", "UH", "K", "S"),
    "kelly": ("K", "EH", "L", "IY"),
    "sanders": ("S", "AE", "N", "D", "ER", "Z"),
    "price": ("P", "R", "AY", "S"),
    "bennett": ("B", "EH", "N", "IH", "T"),
    "wood": ("W", "UH", "D"),
    "barnes": ("B", "AA", "R", "N", "Z"),
    "ross": ("R", "AO", "S"),
    "henderson": ("HH", "EH", "N", "D", "ER", "S", "AH", "N"),
    "coleman": ("K", "OW", "L", "M", "AH", "N"),
    "jenkins": ("JH", "EH", "NG", "K", "IH", "N", "Z"),
    "perry": ("P", "EH", "R", "IY"),
    "powell": ("P", "AW", "AH", "L"),
    "long": ("L", "AO", "NG"),
    "patterson": ("P", "AE", "T", "ER", "S", "AH", "N"),
    "hughes": ("HH", "Y", "UW", "Z"),
    "flores": ("F", "L", "AO", "R", "EH", "S"),
    "washington": ("W", "AA", "SH", "IH", "NG", "T", "AH", "N"),
    "butler": ("B", "AH", "T", "L", "ER"),
    "simmons": ("S", "IH", "M", "AH", "N", "Z"),
    "foster": ("F", "AO", "S", "T", "ER"),
    "gonzales": ("G", "AH", "N", "Z", "AA", "L", "EH", "S"),
    "bryant": ("B", "R", "AY", "AH", "N", "T"),
    "alexander": ("AE", "L", "IH", "G", "Z", "AE", "N", "D", "ER"),
    "russell": ("R", "AH", "S", "AH", "L"),
    "griffin": ("G", "R", "IH", "F", "IH", "N"),
    "diaz": ("D", "IY", "AE", "Z"),
    "hayes": ("HH", "EY", "Z"),

    # Indian names
    "rakesh": ("R", "AH", "K", "EY", "SH"),
    "suresh": ("S", "UH", "R", "EY", "SH"),
    "ramesh": ("R", "AH", "M", "EY", "SH"),
    "kumar": ("K", "UW", "M", "AA", "R"),
    "sharma": ("SH", "AA", "R", "M", "AH"),
    "singh": ("S", "IH", "NG"),
    "patel": ("P", "AH", "T", "EH", "L"),
    "gupta": ("G", "UH", "P", "T", "AH"),
    "sukesh": ("S", "UW", "K", "EY", "SH"),
    "soulpi": ("S", "OW", "L", "P", "IY"),
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
    "ll": ("L",), "bb": ("B",), "dd": ("D",), "ff": ("F",),
    "gg": ("G",), "mm": ("M",), "nn": ("N",), "pp": ("P",),
    "rr": ("R",), "ss": ("S",), "tt": ("T",), "zz": ("Z",),
}


# =============================================================================
# Input Normalization
# =============================================================================

def normalize_input(raw: str) -> NormalizedInput:
    """
    Normalize raw input to canonical form.

    Args:
        raw: Raw input string

    Returns:
        NormalizedInput with canonical form and segments
    """
    # Detect script family
    script = _detect_script(raw)

    # Normalize to lowercase, collapse whitespace
    canonical = raw.strip().lower()
    canonical = re.sub(r'\s+', ' ', canonical)

    # Remove non-alphabetic characters except spaces
    canonical = re.sub(r'[^a-z\s]', '', canonical)

    # Segment on whitespace
    segments = tuple(canonical.split()) if canonical else ()

    return NormalizedInput(
        original=raw,
        canonical=canonical,
        segments=segments,
        script_family=script,
    )


def _detect_script(text: str) -> ScriptFamily:
    """Detect the script family of the input."""
    has_latin = bool(re.search(r'[a-zA-Z]', text))
    has_devanagari = bool(re.search(r'[\u0900-\u097F]', text))

    if has_latin and has_devanagari:
        return ScriptFamily.MIXED
    elif has_devanagari:
        return ScriptFamily.DEVANAGARI
    elif has_latin:
        return ScriptFamily.LATIN
    else:
        return ScriptFamily.UNKNOWN


# =============================================================================
# Phoneme Extraction
# =============================================================================

def get_phonemes(word: str) -> Tuple[str, ...]:
    """
    Get phonemes for a word using dictionary or rules.

    Args:
        word: The word to convert

    Returns:
        Tuple of ARPABET phoneme symbols
    """
    word_lower = word.strip().lower()

    # Try name dictionary first
    if word_lower in NAME_PHONEME_DICT:
        return NAME_PHONEME_DICT[word_lower]

    # Fallback to rules
    return _apply_grapheme_rules(word_lower)


def _apply_grapheme_rules(word: str) -> Tuple[str, ...]:
    """Apply grapheme-to-phoneme rules."""
    phonemes: List[str] = []
    i = 0

    while i < len(word):
        matched = False

        # Try trigraphs and digraphs first (longest match)
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
# Signal Extraction
# =============================================================================

def extract_signals(normalized: NormalizedInput) -> ExtractedSignals:
    """
    Extract all mechanical signals from normalized input.

    This is a deterministic process with no interpretation.

    Args:
        normalized: Normalized input from Layer 1

    Returns:
        ExtractedSignals with all mechanical features
    """
    # Combine all segments for analysis
    full_word = "".join(normalized.segments)

    if not full_word:
        return _empty_signals()

    # Get phonemes
    phonemes = get_phonemes(full_word)

    if not phonemes:
        return _empty_signals()

    # Classify phonemes into categories
    categories = _classify_phonemes(phonemes)

    # Count phoneme types
    counts = _count_phoneme_types(categories)

    # Compute rhythmic signals
    syllable_count = _count_syllables(phonemes, categories)
    stress_pattern = _compute_stress_pattern(syllable_count)
    vowel_consonant_ratio = _compute_vowel_consonant_ratio(counts)

    # Compute structural signals
    onset_size = _compute_onset_cluster_size(phonemes, categories)
    coda_size = _compute_coda_cluster_size(phonemes, categories)

    # Get positional signals
    initial_phoneme = phonemes[0] if phonemes else ""
    final_phoneme = phonemes[-1] if phonemes else ""
    initial_category = categories[0] if categories else ""
    final_category = categories[-1] if categories else ""

    return ExtractedSignals(
        phoneme_sequence=phonemes,
        phoneme_categories=categories,
        syllable_count=syllable_count,
        stress_pattern=stress_pattern,
        vowel_consonant_ratio=vowel_consonant_ratio,
        onset_cluster_size=onset_size,
        coda_cluster_size=coda_size,
        initial_phoneme=initial_phoneme,
        final_phoneme=final_phoneme,
        initial_category=initial_category,
        final_category=final_category,
        plosive_count=counts.get("plosive", 0),
        fricative_count=counts.get("fricative", 0),
        nasal_count=counts.get("nasal", 0),
        liquid_count=counts.get("liquid", 0),
        glide_count=counts.get("glide", 0),
        vowel_count=counts.get("vowel", 0),
    )


def _empty_signals() -> ExtractedSignals:
    """Return empty signals for invalid input."""
    return ExtractedSignals(
        phoneme_sequence=(),
        phoneme_categories=(),
        syllable_count=1,
        stress_pattern=(1,),
        vowel_consonant_ratio=0.5,
        onset_cluster_size=0,
        coda_cluster_size=0,
        initial_phoneme="",
        final_phoneme="",
        initial_category="",
        final_category="",
        plosive_count=0,
        fricative_count=0,
        nasal_count=0,
        liquid_count=0,
        glide_count=0,
        vowel_count=0,
    )


def _classify_phonemes(phonemes: Tuple[str, ...]) -> Tuple[str, ...]:
    """Classify each phoneme into its category."""
    categories = []
    for p in phonemes:
        # Strip stress markers
        clean = p.rstrip("012")
        if clean in PHONEME_CATEGORIES:
            cat = PHONEME_CATEGORIES[clean]
            if cat in (PhonemeCategory.VOWEL_SHORT, PhonemeCategory.VOWEL_LONG,
                       PhonemeCategory.DIPHTHONG):
                categories.append("vowel")
            else:
                categories.append(cat.value)
        else:
            categories.append("unknown")
    return tuple(categories)


def _count_phoneme_types(categories: Tuple[str, ...]) -> Dict[str, int]:
    """Count phonemes by type."""
    counts: Dict[str, int] = {}
    for cat in categories:
        counts[cat] = counts.get(cat, 0) + 1
    return counts


def _count_syllables(phonemes: Tuple[str, ...], categories: Tuple[str, ...]) -> int:
    """Count syllables (approximately = number of vowels)."""
    vowel_count = sum(1 for cat in categories if cat == "vowel")
    return max(1, vowel_count)


def _compute_stress_pattern(syllable_count: int) -> Tuple[int, ...]:
    """
    Compute stress pattern.

    For names, default to trochaic (stress on first syllable).
    """
    if syllable_count == 1:
        return (1,)
    elif syllable_count == 2:
        return (1, 0)  # Trochaic: STRONG-weak
    elif syllable_count == 3:
        return (1, 0, 0)  # Dactylic: STRONG-weak-weak
    else:
        # Alternating with initial stress
        pattern = []
        for i in range(syllable_count):
            pattern.append(1 if i % 2 == 0 else 0)
        return tuple(pattern)


def _compute_vowel_consonant_ratio(counts: Dict[str, int]) -> float:
    """Compute ratio of vowels to total phonemes."""
    vowels = counts.get("vowel", 0)
    total = sum(counts.values())
    if total == 0:
        return 0.5
    return vowels / total


def _compute_onset_cluster_size(
    phonemes: Tuple[str, ...],
    categories: Tuple[str, ...]
) -> int:
    """Count initial consonant cluster size."""
    count = 0
    for cat in categories:
        if cat == "vowel":
            break
        count += 1
    return count


def _compute_coda_cluster_size(
    phonemes: Tuple[str, ...],
    categories: Tuple[str, ...]
) -> int:
    """Count final consonant cluster size."""
    count = 0
    for cat in reversed(categories):
        if cat == "vowel":
            break
        count += 1
    return count
