"""
Phonetic Resonance Engine - Phoneme Layer Mappings
===================================================

Maps ARPABET phonemes to their 12D ontological layer affinities.

Each phoneme has affinities to all 12 layers based on:
- Articulation manner (how the sound is produced)
- Articulation place (where in the mouth)
- Voicing (voiced vs unvoiced)
- Duration (short vs sustained)

Layer order (12D patent-exact sequence):
    0: O1_POTENTIAL    - Dormant capacity
    1: O2_IDENTITY     - Classification, labeling
    2: O3_EXECUTION    - Action, karma
    3: O4_STRUCTURE    - Form, shape
    4: O5_COGNITION    - Perception, attention
    5: O6_AGENCY       - Direction, control
    6: O7_REASONING    - Logic, analysis
    7: O8_PURPOSE      - Intent, goals
    8: O9_WITNESSES    - Awareness, observation
    9: O10_UNIFYING    - Connection, harmony
    10: O11_INTEGRATION - Resolution, consolidation
    11: O12_ABSOLVING  - Release, transcendence
"""

from typing import Dict, Tuple
from symbolu_core.resonance.types import PhonemeCategory, PhonemeProfile


# =============================================================================
# Phoneme → Layer Affinity Mappings (12D)
# =============================================================================
# Values represent affinity strength (0.0 to 1.0) for each layer
# Order: [O1_POT, O2_ID, O3_EXEC, O4_STR, O5_COG, O6_AGN, O7_RSN, O8_PUR, O9_WIT, O10_UNI, O11_INT, O12_ABS]

# Plosives: Sudden, forceful sounds → Execution, Agency
PLOSIVE_AFFINITIES: Dict[str, Tuple[float, ...]] = {
    # Voiceless plosives - more forceful, directive
    "P": (0.05, 0.2, 0.8, 0.3, 0.1, 0.6, 0.2, 0.4, 0.1, 0.1, 0.1, 0.1),  # Bilabial
    "T": (0.05, 0.3, 0.7, 0.4, 0.2, 0.5, 0.3, 0.3, 0.2, 0.1, 0.1, 0.1),  # Alveolar
    "K": (0.05, 0.2, 0.8, 0.5, 0.2, 0.7, 0.2, 0.4, 0.1, 0.1, 0.1, 0.1),  # Velar
    # Voiced plosives - more resonant, forming
    "B": (0.05, 0.2, 0.6, 0.5, 0.2, 0.4, 0.2, 0.5, 0.2, 0.3, 0.2, 0.1),  # Bilabial
    "D": (0.05, 0.3, 0.5, 0.5, 0.3, 0.4, 0.4, 0.4, 0.2, 0.2, 0.2, 0.1),  # Alveolar
    "G": (0.05, 0.2, 0.6, 0.5, 0.2, 0.5, 0.3, 0.5, 0.1, 0.2, 0.2, 0.1),  # Velar
}

# Fricatives: Continuous, controlled → Agency, Reasoning
FRICATIVE_AFFINITIES: Dict[str, Tuple[float, ...]] = {
    "F": (0.05, 0.2, 0.3, 0.4, 0.2, 0.6, 0.5, 0.3, 0.2, 0.2, 0.2, 0.2),  # Labiodental
    "V": (0.05, 0.2, 0.3, 0.4, 0.3, 0.5, 0.4, 0.4, 0.2, 0.3, 0.2, 0.2),  # Labiodental voiced
    "TH": (0.05, 0.2, 0.2, 0.3, 0.4, 0.4, 0.6, 0.3, 0.3, 0.2, 0.2, 0.3),  # Dental voiceless
    "DH": (0.05, 0.2, 0.2, 0.4, 0.4, 0.4, 0.5, 0.4, 0.3, 0.3, 0.2, 0.2),  # Dental voiced
    "S": (0.05, 0.4, 0.3, 0.3, 0.3, 0.6, 0.7, 0.3, 0.3, 0.1, 0.1, 0.1),  # Alveolar
    "Z": (0.05, 0.4, 0.3, 0.4, 0.3, 0.5, 0.6, 0.4, 0.3, 0.2, 0.1, 0.1),  # Alveolar voiced
    "SH": (0.05, 0.3, 0.2, 0.4, 0.3, 0.5, 0.5, 0.3, 0.4, 0.3, 0.2, 0.2),  # Postalveolar
    "ZH": (0.05, 0.3, 0.2, 0.4, 0.3, 0.4, 0.5, 0.4, 0.4, 0.3, 0.2, 0.2),  # Postalveolar voiced
    "HH": (0.1, 0.1, 0.1, 0.2, 0.5, 0.2, 0.3, 0.3, 0.5, 0.4, 0.5, 0.6),  # Glottal - breath
}

# Affricates: Combined plosive+fricative → Execution, Structure
AFFRICATE_AFFINITIES: Dict[str, Tuple[float, ...]] = {
    "CH": (0.05, 0.3, 0.6, 0.5, 0.2, 0.5, 0.3, 0.4, 0.2, 0.2, 0.1, 0.1),  # Voiceless
    "JH": (0.05, 0.3, 0.5, 0.5, 0.2, 0.4, 0.3, 0.5, 0.2, 0.3, 0.2, 0.1),  # Voiced
}

# Nasals: Resonant, connecting → Unifying, Cognition
NASAL_AFFINITIES: Dict[str, Tuple[float, ...]] = {
    "M": (0.1, 0.2, 0.2, 0.3, 0.4, 0.2, 0.3, 0.3, 0.3, 0.7, 0.5, 0.4),  # Bilabial
    "N": (0.1, 0.3, 0.2, 0.3, 0.5, 0.3, 0.4, 0.3, 0.3, 0.6, 0.4, 0.3),  # Alveolar
    "NG": (0.1, 0.2, 0.2, 0.3, 0.4, 0.2, 0.3, 0.3, 0.4, 0.7, 0.6, 0.5),  # Velar
}

# Liquids: Flowing, smooth → Structure, Unifying
LIQUID_AFFINITIES: Dict[str, Tuple[float, ...]] = {
    "L": (0.1, 0.2, 0.2, 0.6, 0.3, 0.3, 0.3, 0.4, 0.3, 0.6, 0.5, 0.4),  # Lateral
    "R": (0.1, 0.2, 0.3, 0.5, 0.3, 0.4, 0.3, 0.5, 0.3, 0.5, 0.4, 0.3),  # Rhotic
}

# Glides: Transitional → Structure, Purpose
GLIDE_AFFINITIES: Dict[str, Tuple[float, ...]] = {
    "W": (0.1, 0.1, 0.2, 0.5, 0.3, 0.3, 0.2, 0.5, 0.3, 0.5, 0.4, 0.4),  # Labial-velar
    "Y": (0.1, 0.2, 0.2, 0.5, 0.3, 0.4, 0.3, 0.5, 0.3, 0.4, 0.3, 0.3),  # Palatal
}

# Short Vowels: Brief, focused → Cognition, Identity
SHORT_VOWEL_AFFINITIES: Dict[str, Tuple[float, ...]] = {
    "IH": (0.1, 0.5, 0.2, 0.3, 0.6, 0.3, 0.4, 0.3, 0.4, 0.2, 0.2, 0.2),  # as in "bit"
    "EH": (0.1, 0.4, 0.2, 0.4, 0.5, 0.3, 0.4, 0.4, 0.4, 0.3, 0.2, 0.2),  # as in "bet"
    "AE": (0.1, 0.4, 0.3, 0.4, 0.4, 0.3, 0.4, 0.4, 0.3, 0.3, 0.3, 0.3),  # as in "bat"
    "AH": (0.1, 0.3, 0.2, 0.3, 0.5, 0.2, 0.4, 0.3, 0.5, 0.4, 0.4, 0.5),  # as in "but"
    "UH": (0.1, 0.3, 0.2, 0.4, 0.5, 0.2, 0.3, 0.4, 0.4, 0.5, 0.4, 0.4),  # as in "book"
}

# Long Vowels: Sustained, open → Absolving, Unifying
LONG_VOWEL_AFFINITIES: Dict[str, Tuple[float, ...]] = {
    "IY": (0.1, 0.3, 0.2, 0.4, 0.5, 0.3, 0.4, 0.4, 0.5, 0.5, 0.5, 0.5),  # as in "beat"
    "EY": (0.1, 0.3, 0.2, 0.5, 0.4, 0.4, 0.4, 0.5, 0.4, 0.4, 0.4, 0.4),  # as in "bait"
    "AA": (0.15, 0.2, 0.3, 0.3, 0.3, 0.2, 0.3, 0.3, 0.5, 0.6, 0.6, 0.7),  # as in "father"
    "AO": (0.15, 0.2, 0.2, 0.4, 0.3, 0.3, 0.3, 0.4, 0.5, 0.6, 0.6, 0.6),  # as in "thought"
    "OW": (0.1, 0.2, 0.2, 0.5, 0.3, 0.3, 0.3, 0.5, 0.4, 0.5, 0.5, 0.5),  # as in "boat"
    "UW": (0.15, 0.2, 0.2, 0.4, 0.4, 0.2, 0.3, 0.4, 0.5, 0.6, 0.6, 0.6),  # as in "boot"
}

# Diphthongs: Rising/falling → Purpose, Structure
DIPHTHONG_AFFINITIES: Dict[str, Tuple[float, ...]] = {
    "AY": (0.1, 0.2, 0.3, 0.5, 0.3, 0.4, 0.3, 0.6, 0.4, 0.4, 0.4, 0.4),  # as in "bite"
    "AW": (0.1, 0.2, 0.3, 0.4, 0.3, 0.3, 0.3, 0.5, 0.5, 0.5, 0.5, 0.5),  # as in "bout"
    "OY": (0.1, 0.3, 0.3, 0.5, 0.3, 0.4, 0.3, 0.6, 0.4, 0.4, 0.4, 0.4),  # as in "boy"
    "ER": (0.1, 0.3, 0.2, 0.4, 0.4, 0.3, 0.4, 0.4, 0.4, 0.5, 0.4, 0.4),  # as in "bird"
}


# =============================================================================
# Phoneme Category Mapping
# =============================================================================

PHONEME_CATEGORIES: Dict[str, PhonemeCategory] = {
    # Plosives
    "P": PhonemeCategory.PLOSIVE,
    "B": PhonemeCategory.PLOSIVE,
    "T": PhonemeCategory.PLOSIVE,
    "D": PhonemeCategory.PLOSIVE,
    "K": PhonemeCategory.PLOSIVE,
    "G": PhonemeCategory.PLOSIVE,
    # Fricatives
    "F": PhonemeCategory.FRICATIVE,
    "V": PhonemeCategory.FRICATIVE,
    "TH": PhonemeCategory.FRICATIVE,
    "DH": PhonemeCategory.FRICATIVE,
    "S": PhonemeCategory.FRICATIVE,
    "Z": PhonemeCategory.FRICATIVE,
    "SH": PhonemeCategory.FRICATIVE,
    "ZH": PhonemeCategory.FRICATIVE,
    "HH": PhonemeCategory.FRICATIVE,
    # Affricates
    "CH": PhonemeCategory.AFFRICATE,
    "JH": PhonemeCategory.AFFRICATE,
    # Nasals
    "M": PhonemeCategory.NASAL,
    "N": PhonemeCategory.NASAL,
    "NG": PhonemeCategory.NASAL,
    # Liquids
    "L": PhonemeCategory.LIQUID,
    "R": PhonemeCategory.LIQUID,
    # Glides
    "W": PhonemeCategory.GLIDE,
    "Y": PhonemeCategory.GLIDE,
    # Short vowels
    "IH": PhonemeCategory.VOWEL_SHORT,
    "EH": PhonemeCategory.VOWEL_SHORT,
    "AE": PhonemeCategory.VOWEL_SHORT,
    "AH": PhonemeCategory.VOWEL_SHORT,
    "UH": PhonemeCategory.VOWEL_SHORT,
    # Long vowels
    "IY": PhonemeCategory.VOWEL_LONG,
    "EY": PhonemeCategory.VOWEL_LONG,
    "AA": PhonemeCategory.VOWEL_LONG,
    "AO": PhonemeCategory.VOWEL_LONG,
    "OW": PhonemeCategory.VOWEL_LONG,
    "UW": PhonemeCategory.VOWEL_LONG,
    # Diphthongs
    "AY": PhonemeCategory.DIPHTHONG,
    "AW": PhonemeCategory.DIPHTHONG,
    "OY": PhonemeCategory.DIPHTHONG,
    "ER": PhonemeCategory.DIPHTHONG,
}


# =============================================================================
# Combined Phoneme Profiles
# =============================================================================

def _build_phoneme_profiles() -> Dict[str, PhonemeProfile]:
    """Build complete phoneme profiles from affinity maps."""
    profiles: Dict[str, PhonemeProfile] = {}

    all_affinities = {
        **PLOSIVE_AFFINITIES,
        **FRICATIVE_AFFINITIES,
        **AFFRICATE_AFFINITIES,
        **NASAL_AFFINITIES,
        **LIQUID_AFFINITIES,
        **GLIDE_AFFINITIES,
        **SHORT_VOWEL_AFFINITIES,
        **LONG_VOWEL_AFFINITIES,
        **DIPHTHONG_AFFINITIES,
    }

    for phoneme, affinities in all_affinities.items():
        category = PHONEME_CATEGORIES.get(phoneme)
        if category is None:
            continue
        profiles[phoneme] = PhonemeProfile(
            phoneme=phoneme,
            category=category,
            layer_affinities=affinities,
        )

    return profiles


# The master phoneme map - immutable after initialization
PHONEME_PROFILES: Dict[str, PhonemeProfile] = _build_phoneme_profiles()


# =============================================================================
# Lookup Functions
# =============================================================================

def get_phoneme_profile(phoneme: str) -> PhonemeProfile:
    """
    Get the phoneme profile for a given ARPABET phoneme.

    Args:
        phoneme: ARPABET phoneme symbol (e.g., "L", "AY", "T")

    Returns:
        PhonemeProfile with category and layer affinities

    Raises:
        KeyError: If phoneme is not in the map
    """
    # Strip stress markers (0, 1, 2)
    clean = phoneme.rstrip("012")
    if clean not in PHONEME_PROFILES:
        raise KeyError(f"Unknown phoneme: {phoneme}")
    return PHONEME_PROFILES[clean]


def get_layer_affinities(phoneme: str) -> Tuple[float, ...]:
    """
    Get the 12D layer affinities for a phoneme.

    Args:
        phoneme: ARPABET phoneme symbol

    Returns:
        Tuple of 12 floats representing layer affinities
    """
    return get_phoneme_profile(phoneme).layer_affinities


def get_phoneme_category(phoneme: str) -> PhonemeCategory:
    """
    Get the category for a phoneme.

    Args:
        phoneme: ARPABET phoneme symbol

    Returns:
        PhonemeCategory enum value
    """
    return get_phoneme_profile(phoneme).category


def is_vowel(phoneme: str) -> bool:
    """Check if phoneme is a vowel (short, long, or diphthong)."""
    try:
        category = get_phoneme_category(phoneme)
        return category in (
            PhonemeCategory.VOWEL_SHORT,
            PhonemeCategory.VOWEL_LONG,
            PhonemeCategory.DIPHTHONG,
        )
    except KeyError:
        return False


def is_consonant(phoneme: str) -> bool:
    """Check if phoneme is a consonant."""
    try:
        category = get_phoneme_category(phoneme)
        return category in (
            PhonemeCategory.PLOSIVE,
            PhonemeCategory.FRICATIVE,
            PhonemeCategory.AFFRICATE,
            PhonemeCategory.NASAL,
            PhonemeCategory.LIQUID,
            PhonemeCategory.GLIDE,
        )
    except KeyError:
        return False


def list_phonemes() -> Tuple[str, ...]:
    """Return all known phonemes."""
    return tuple(sorted(PHONEME_PROFILES.keys()))
