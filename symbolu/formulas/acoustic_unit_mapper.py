"""
Acoustic Unit Mapper — Core/Substrate Utility
==============================================

╔═══════════════════════════════════════════════════════════════════════════════╗
║                         CORE/SUBSTRATE LAYER                                   ║
║                                                                                ║
║  This module is part of the Core/Substrate layer.                              ║
║  It is NOT a pipeline phase and has no authority over intent, regime,          ║
║  semantics, or delivery.                                                       ║
╚═══════════════════════════════════════════════════════════════════════════════╝

CORE/SUBSTRATE MODULE — Transforms raw input text into acoustic units.

This module computes the foundational acoustic decomposition of input text
into ordered symbolic primitives based purely on sound/syllable structure.

ARCHITECTURAL CONSTRAINTS (CORE/SUBSTRATE INVARIANTS):
    - NO semantics: This module has no knowledge of meaning
    - NO intent: This module never infers user purpose
    - NO routing: This module does not direct control flow
    - NO policy: This module does not make behavioral decisions
    - NO LLM calls: Purely deterministic, rule-based processing
    - DETERMINISTIC: Same input always produces same output
    - LANGUAGE-AGNOSTIC: Works on phonetic structure, not language rules
    - READ-ONLY: Pure transformation with no side effects
    - NON-AUTHORITATIVE: Cannot influence governance or routing decisions

This module:
    - Computes acoustic tokenization
    - Measures phonetic properties
    - Does NOT interpret meaning
    - Does NOT infer emotion or intent
    - Does NOT affect delivery decisions

Outputs are pure symbolic primitives that may be observed by downstream phases.

Algorithm:
    1. Normalize input (lowercase, strip edges)
    2. Segment into sound-groups (consonant-vowel clusters)
    3. Extract acoustic properties from each cluster
    4. Return ordered list of AcousticUnit primitives

HISTORICAL NOTE: Legacy docstrings may reference "Phase 1". This is a
historical development label, NOT an authoritative pipeline phase.

Version: 1.0 (Core/Substrate Utility)
Date: 2025-12-13
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import List, Tuple


# ============================================================================
# CORE/SUBSTRATE INVARIANT DECLARATIONS
# ============================================================================

# These constants enforce Core/Substrate boundaries (historical "Phase 1" label)
PHASE_1_INVARIANTS = {
    "NO_SEMANTICS": True,
    "NO_INTENT": True,
    "NO_ROUTING": True,
    "NO_POLICY": True,
    "NO_LLM_CALLS": True,
    "DETERMINISTIC": True,
    "LANGUAGE_AGNOSTIC": True,
    "READ_ONLY": True,
}


# ============================================================================
# ENUMS - Sound Classification Types (Non-Semantic)
# ============================================================================


class SoundClass(str, Enum):
    """
    Classification of sounds by acoustic properties only.

    These are phonetic categories, NOT linguistic or semantic categories.
    Classification is based on physical articulation properties.
    """
    VOWEL = "vowel"           # Open vocal tract sounds
    STOP = "stop"             # Plosive/occlusive sounds (p, b, t, d, k, g)
    FRICATIVE = "fricative"   # Turbulent airflow sounds (f, v, s, z, sh, h)
    NASAL = "nasal"           # Nasal resonance sounds (m, n, ng)
    LIQUID = "liquid"         # Lateral/rhotic sounds (l, r)
    GLIDE = "glide"           # Semi-vowels (w, y)
    AFFRICATE = "affricate"   # Stop + fricative (ch, j)
    UNKNOWN = "unknown"       # Unclassified sounds


class VowelHeight(str, Enum):
    """Vowel height classification based on tongue position."""
    HIGH = "high"       # i, u
    MID = "mid"         # e, o
    LOW = "low"         # a
    UNKNOWN = "unknown"


class VowelBackness(str, Enum):
    """Vowel backness classification based on tongue position."""
    FRONT = "front"     # i, e
    CENTRAL = "central" # a
    BACK = "back"       # o, u
    UNKNOWN = "unknown"


# ============================================================================
# DATACLASSES - Acoustic Primitives
# ============================================================================


@dataclass(frozen=True)
class AcousticUnit:
    """
    A single acoustic unit representing a sound-group in the input.

    This is a pure symbolic primitive with NO semantic content.
    It captures only the acoustic/articulatory properties of a sound cluster.

    Attributes:
        raw_text: The original text segment (for tracing only)
        index: Position in the sequence (0-indexed)
        sound_class: Primary sound classification
        vowel_height: Height of any vowel component (or UNKNOWN)
        vowel_backness: Backness of any vowel component (or UNKNOWN)
        consonant_count: Number of consonants in cluster
        vowel_count: Number of vowels in cluster
        length: Character length of the unit
        is_syllable_nucleus: Whether this unit contains a vowel nucleus

    Core/Substrate Invariants:
        - No meaning field
        - No intent field
        - No semantic category
        - Purely structural/acoustic properties
    """
    raw_text: str
    index: int
    sound_class: SoundClass
    vowel_height: VowelHeight
    vowel_backness: VowelBackness
    consonant_count: int
    vowel_count: int
    length: int
    is_syllable_nucleus: bool

    def __post_init__(self) -> None:
        """Validate AcousticUnit invariants."""
        if not isinstance(self.index, int) or self.index < 0:
            raise ValueError(f"AcousticUnit.index must be non-negative int, got {self.index}")
        if not isinstance(self.consonant_count, int) or self.consonant_count < 0:
            raise ValueError(f"AcousticUnit.consonant_count must be non-negative int")
        if not isinstance(self.vowel_count, int) or self.vowel_count < 0:
            raise ValueError(f"AcousticUnit.vowel_count must be non-negative int")
        if not isinstance(self.length, int) or self.length < 0:
            raise ValueError(f"AcousticUnit.length must be non-negative int")


# ============================================================================
# ACOUSTIC CLASSIFICATION TABLES (Deterministic)
# ============================================================================

# Vowel characters (language-agnostic base set)
VOWELS = frozenset("aeiouAEIOU")

# Extended vowel set for non-ASCII
EXTENDED_VOWELS = frozenset("aeiouAEIOUàáâãäåæèéêëìíîïòóôõöùúûüāēīōūąęįų")

# Consonant-to-sound-class mapping (based on articulatory phonetics)
CONSONANT_CLASS_MAP = {
    # Stops (plosives)
    'p': SoundClass.STOP, 'b': SoundClass.STOP,
    't': SoundClass.STOP, 'd': SoundClass.STOP,
    'k': SoundClass.STOP, 'g': SoundClass.STOP,
    'q': SoundClass.STOP, 'c': SoundClass.STOP,  # Hard C

    # Fricatives
    'f': SoundClass.FRICATIVE, 'v': SoundClass.FRICATIVE,
    's': SoundClass.FRICATIVE, 'z': SoundClass.FRICATIVE,
    'h': SoundClass.FRICATIVE, 'x': SoundClass.FRICATIVE,

    # Nasals
    'm': SoundClass.NASAL, 'n': SoundClass.NASAL,

    # Liquids
    'l': SoundClass.LIQUID, 'r': SoundClass.LIQUID,

    # Glides
    'w': SoundClass.GLIDE, 'y': SoundClass.GLIDE,

    # Affricates (simplified - treated as fricatives for decomposition)
    'j': SoundClass.AFFRICATE,
}

# Vowel height mapping
VOWEL_HEIGHT_MAP = {
    'i': VowelHeight.HIGH, 'u': VowelHeight.HIGH,
    'e': VowelHeight.MID, 'o': VowelHeight.MID,
    'a': VowelHeight.LOW,
}

# Vowel backness mapping
VOWEL_BACKNESS_MAP = {
    'i': VowelBackness.FRONT, 'e': VowelBackness.FRONT,
    'a': VowelBackness.CENTRAL,
    'o': VowelBackness.BACK, 'u': VowelBackness.BACK,
}


# ============================================================================
# CORE MAPPING FUNCTIONS
# ============================================================================


def map_acoustic_units(text: str) -> List[AcousticUnit]:
    """
    Convert input string into ordered acoustic units.

    This is the primary Phase 1 entry point. It transforms raw text
    into a sequence of AcousticUnit primitives based purely on
    acoustic/phonetic structure.

    CORE/SUBSTRATE INVARIANTS:
        - Deterministic: Same input always produces same output
        - No semantics: Units have no meaning
        - No LLM calls: Pure rule-based processing
        - Language-agnostic: Works on sound structure only

    Algorithm:
        1. Normalize input
        2. Segment into sound-groups (CV clusters)
        3. Classify each segment
        4. Return ordered list

    Args:
        text: Raw input string to tokenize

    Returns:
        List of AcousticUnit primitives in order

    Examples:
        >>> units = map_acoustic_units("hello")
        >>> len(units) > 0
        True
        >>> all(isinstance(u, AcousticUnit) for u in units)
        True
    """
    # Handle edge cases
    if not text:
        return []

    if not isinstance(text, str):
        raise TypeError(f"map_acoustic_units requires str, got {type(text).__name__}")

    # Step 1: Normalize input
    normalized = _normalize_text(text)

    if not normalized:
        return []

    # Step 2: Segment into sound-groups
    segments = _segment_into_sound_groups(normalized)

    # Step 3: Build acoustic units
    units = []
    for idx, segment in enumerate(segments):
        unit = _build_acoustic_unit(segment, idx)
        units.append(unit)

    return units


def _normalize_text(text: str) -> str:
    """
    Normalize input text for acoustic processing.

    Rules (deterministic):
        1. Strip leading/trailing whitespace
        2. Convert to lowercase
        3. Preserve internal spaces as segment boundaries
        4. Remove non-alphabetic characters except spaces

    This is a read-only transformation.
    """
    # Strip and lowercase
    result = text.strip().lower()

    # Keep only alphabetic chars and spaces
    filtered = []
    for char in result:
        if char.isalpha() or char == ' ':
            filtered.append(char)

    return ''.join(filtered)


def _segment_into_sound_groups(text: str) -> List[str]:
    """
    Segment normalized text into consonant-vowel sound groups.

    This uses a simple CV-syllable heuristic:
        - Each vowel starts a new nucleus
        - Consonants attach to the following vowel if possible
        - Word boundaries (spaces) force segment breaks

    This is language-agnostic and based on acoustic principles,
    not linguistic syllabification rules.
    """
    if not text:
        return []

    segments = []
    current_segment = []

    for char in text:
        if char == ' ':
            # Space forces segment break
            if current_segment:
                segments.append(''.join(current_segment))
                current_segment = []
            continue

        is_vowel = char in EXTENDED_VOWELS

        if is_vowel:
            # Vowel: add to current and potentially complete segment
            current_segment.append(char)
            # Check if next is consonant or end - if so, close segment
            # For simplicity: always close after vowel (CV pattern)
            segments.append(''.join(current_segment))
            current_segment = []
        else:
            # Consonant: accumulate
            current_segment.append(char)

    # Handle trailing consonants
    if current_segment:
        if segments:
            # Attach to previous segment if it ended with vowel
            segments[-1] = segments[-1] + ''.join(current_segment)
        else:
            # Standalone consonants
            segments.append(''.join(current_segment))

    # Filter empty segments
    return [s for s in segments if s]


def _build_acoustic_unit(segment: str, index: int) -> AcousticUnit:
    """
    Build an AcousticUnit from a text segment.

    This analyzes the acoustic properties of the segment
    without any semantic interpretation.
    """
    # Count vowels and consonants
    vowel_count = sum(1 for c in segment if c.lower() in EXTENDED_VOWELS)
    consonant_count = len(segment) - vowel_count

    # Determine primary sound class
    sound_class = _classify_sound(segment)

    # Determine vowel properties (from first vowel found)
    vowel_height, vowel_backness = _classify_vowel(segment)

    # Has syllable nucleus if contains vowel
    is_syllable_nucleus = vowel_count > 0

    return AcousticUnit(
        raw_text=segment,
        index=index,
        sound_class=sound_class,
        vowel_height=vowel_height,
        vowel_backness=vowel_backness,
        consonant_count=consonant_count,
        vowel_count=vowel_count,
        length=len(segment),
        is_syllable_nucleus=is_syllable_nucleus,
    )


def _classify_sound(segment: str) -> SoundClass:
    """
    Classify the primary sound type of a segment.

    Priority: vowel > first consonant class > unknown
    """
    # If contains vowel, classify as vowel (nucleus)
    for char in segment:
        if char.lower() in EXTENDED_VOWELS:
            return SoundClass.VOWEL

    # Otherwise, classify by first consonant
    for char in segment:
        char_lower = char.lower()
        if char_lower in CONSONANT_CLASS_MAP:
            return CONSONANT_CLASS_MAP[char_lower]

    return SoundClass.UNKNOWN


def _classify_vowel(segment: str) -> Tuple[VowelHeight, VowelBackness]:
    """
    Extract vowel height and backness from segment.

    Returns properties of first vowel found, or UNKNOWN if none.
    """
    for char in segment:
        char_lower = char.lower()
        if char_lower in VOWEL_HEIGHT_MAP:
            return (
                VOWEL_HEIGHT_MAP.get(char_lower, VowelHeight.UNKNOWN),
                VOWEL_BACKNESS_MAP.get(char_lower, VowelBackness.UNKNOWN),
            )

    return (VowelHeight.UNKNOWN, VowelBackness.UNKNOWN)


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================


def get_acoustic_signature(units: List[AcousticUnit]) -> str:
    """
    Generate a compact acoustic signature from units.

    This is a deterministic fingerprint of the acoustic structure.
    Useful for comparing acoustic patterns without semantic content.

    Format: "{sound_class_initial}{vowel_height_initial}" for each unit
    Example: "VL-SM-VH" (vowel-low, stop-mid, vowel-high)
    """
    if not units:
        return ""

    signatures = []
    for unit in units:
        sc = unit.sound_class.value[0].upper()  # First letter
        vh = unit.vowel_height.value[0].upper() if unit.vowel_height != VowelHeight.UNKNOWN else "X"
        signatures.append(f"{sc}{vh}")

    return "-".join(signatures)


def count_syllable_nuclei(units: List[AcousticUnit]) -> int:
    """Count the number of syllable nuclei (vowel-containing units)."""
    return sum(1 for u in units if u.is_syllable_nucleus)


# ============================================================================
# PUBLIC EXPORTS
# ============================================================================

__all__ = [
    # Primary function
    "map_acoustic_units",
    # Data classes
    "AcousticUnit",
    # Enums
    "SoundClass",
    "VowelHeight",
    "VowelBackness",
    # Utility functions
    "get_acoustic_signature",
    "count_syllable_nuclei",
    # Constants
    "PHASE_1_INVARIANTS",
]
