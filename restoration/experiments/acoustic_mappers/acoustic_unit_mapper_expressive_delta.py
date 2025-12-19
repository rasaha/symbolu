"""
Acoustic Unit Mapper — Expressive Delta (EXPERIMENTAL)
=======================================================

╔═══════════════════════════════════════════════════════════════════════════════╗
║                              ⚠️  EXPERIMENTAL  ⚠️                              ║
║                                                                                ║
║  This module is EXPERIMENTAL and must NOT be used in production pipelines     ║
║  or governance decisions. It exists solely as a testbed for evaluating        ║
║  expressive-acoustic correctness enhancements.                                ║
║                                                                                ║
║  CANONICAL MODULE: symbolu/formulas/acoustic_unit_mapper.py                   ║
║  This delta does NOT replace or modify the canonical module.                  ║
╚═══════════════════════════════════════════════════════════════════════════════╝

EXPRESSIVE DELTA PURPOSE:
    This experimental module explores structural metadata fields that preserve
    expressive directionality WITHOUT interpretation. It is a controlled delta
    for evaluation only.

DELTA CHANGES FROM CANONICAL MODULE:
    1. vowel_first: bool — Detects when vowel precedes consonant in unit
    2. expressive_anchor: Literal["consonant", "vowel"] — Directional marker
    3. cluster_order: str — Explicit CV/VC ordering preservation
    4. Consonant-anchored segmentation (vowels as wrappers, not nuclei)
    5. Raw order fidelity (sa ≠ as, no normalization collapse)

CORE/SUBSTRATE INVARIANTS (PRESERVED — NON-NEGOTIABLE):
    - NO semantics: No knowledge of meaning
    - NO intent: No inference of user purpose
    - NO routing: No control flow direction
    - NO policy: No behavioral decisions
    - NO LLM calls: Purely deterministic, rule-based
    - NO vrtti values: No emotional/intentional mapping
    - NO ontology/guna/kosha: No philosophical categorization
    - DETERMINISTIC: Same input always produces same output
    - LANGUAGE-AGNOSTIC: Works on phonetic structure only
    - READ-ONLY: Pure transformation with no side effects
    - NON-AUTHORITATIVE: Cannot influence governance or routing

This is still substrate, not intelligence.

Version: 0.1-experimental
Date: 2025-12-15
Based on: symbolu/formulas/acoustic_unit_mapper.py v1.0
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import List, Literal, Tuple


# ============================================================================
# EXPERIMENTAL MODULE MARKER
# ============================================================================

EXPERIMENTAL_MODULE = True
EXPERIMENTAL_WARNING = (
    "This module is EXPERIMENTAL. Do not use in production pipelines or "
    "governance decisions. For production use: symbolu/formulas/acoustic_unit_mapper.py"
)


# ============================================================================
# CORE/SUBSTRATE INVARIANT DECLARATIONS (UNCHANGED FROM CANONICAL)
# ============================================================================

SUBSTRATE_INVARIANTS = {
    "NO_SEMANTICS": True,
    "NO_INTENT": True,
    "NO_ROUTING": True,
    "NO_POLICY": True,
    "NO_LLM_CALLS": True,
    "NO_VRTTI_VALUES": True,          # DELTA: Explicit vrtti exclusion
    "NO_ONTOLOGY": True,              # DELTA: Explicit ontology exclusion
    "NO_GUNA_KOSHA": True,            # DELTA: Explicit guna/kosha exclusion
    "NO_EMOTION_INFERENCE": True,     # DELTA: Explicit emotion exclusion
    "DETERMINISTIC": True,
    "LANGUAGE_AGNOSTIC": True,
    "READ_ONLY": True,
    "NON_AUTHORITATIVE": True,
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
# DELTA ADDITION: Cluster Order Enum
# ============================================================================


class ClusterOrder(str, Enum):
    """
    DELTA FIELD: Explicit ordering pattern within acoustic unit.

    This captures the structural arrangement of consonants (C) and vowels (V)
    WITHOUT any semantic interpretation. It is purely positional metadata.

    - CV: Consonant precedes vowel (e.g., "sa", "ta", "ma")
    - VC: Vowel precedes consonant (e.g., "as", "at", "am")
    - CVC: Consonant-vowel-consonant (e.g., "sat", "tam")
    - V: Isolated vowel (e.g., "a", "i")
    - C: Isolated consonant(s) (e.g., "st", "kr")
    - COMPLEX: Multi-syllable or irregular patterns
    """
    CV = "cv"           # Consonant-vowel (e.g., "sa")
    VC = "vc"           # Vowel-consonant (e.g., "as")
    CVC = "cvc"         # Consonant-vowel-consonant (e.g., "sat")
    VCV = "vcv"         # Vowel-consonant-vowel (e.g., "asa")
    V = "v"             # Isolated vowel
    C = "c"             # Isolated consonant(s)
    COMPLEX = "complex" # Irregular/multi-pattern


# ============================================================================
# DATACLASSES - Acoustic Primitives (DELTA ENHANCED)
# ============================================================================


@dataclass(frozen=True)
class ExpressiveAcousticUnit:
    """
    DELTA: Enhanced acoustic unit with expressive structural metadata.

    This extends the canonical AcousticUnit with additional fields for
    expressive directionality WITHOUT adding semantic interpretation.

    CANONICAL FIELDS (preserved):
        raw_text: The original text segment (for tracing only)
        index: Position in the sequence (0-indexed)
        sound_class: Primary sound classification
        vowel_height: Height of any vowel component (or UNKNOWN)
        vowel_backness: Backness of any vowel component (or UNKNOWN)
        consonant_count: Number of consonants in cluster
        vowel_count: Number of vowels in cluster
        length: Character length of the unit
        is_syllable_nucleus: Whether this unit contains a vowel nucleus

    DELTA FIELDS (new — structural only):
        vowel_first: True if vowel precedes consonant in this unit
        expressive_anchor: "consonant" or "vowel" — directional marker
        cluster_order: Explicit CV/VC/CVC pattern

    INVARIANTS (enforced):
        - No meaning field
        - No intent field
        - No vrtti field
        - No semantic category
        - No emotion inference
        - Purely structural/acoustic properties
    """
    # Canonical fields (unchanged)
    raw_text: str
    index: int
    sound_class: SoundClass
    vowel_height: VowelHeight
    vowel_backness: VowelBackness
    consonant_count: int
    vowel_count: int
    length: int
    is_syllable_nucleus: bool

    # DELTA FIELDS — Expressive structural metadata
    vowel_first: bool
    """
    DELTA: True when a vowel precedes a consonant within this unit.

    Examples:
        - "ab" → vowel_first = True (vowel 'a' precedes consonant 'b')
        - "ba" → vowel_first = False (consonant 'b' precedes vowel 'a')
        - "a"  → vowel_first = True (starts with vowel, no consonant)
        - "b"  → vowel_first = False (no vowel present)

    This is STRUCTURAL ONLY — no semantic meaning is attached.
    """

    expressive_anchor: Literal["consonant", "vowel"]
    """
    DELTA: Directional marker for expressive structure.

    Rules (deterministic):
        - Default = "consonant" (consonant-anchored units are standard)
        - If vowel_first = True → expressive_anchor = "vowel"

    ⚠️ This is NOT positive/negative vrtti.
    ⚠️ This is NOT emotional polarity.
    It is ONLY a directional marker for downstream phases.
    """

    cluster_order: ClusterOrder
    """
    DELTA: Explicit CV/VC ordering pattern.

    Preserves raw order fidelity:
        - "sa" → CV (consonant-vowel)
        - "as" → VC (vowel-consonant)
        - "sa" ≠ "as" (distinct patterns, never collapsed)

    This ensures no normalization that would lose ordering information.
    """

    def __post_init__(self) -> None:
        """Validate ExpressiveAcousticUnit invariants."""
        # Index validation
        if not isinstance(self.index, int) or self.index < 0:
            raise ValueError(
                f"ExpressiveAcousticUnit.index must be non-negative int, got {self.index}"
            )
        # Count validations
        if not isinstance(self.consonant_count, int) or self.consonant_count < 0:
            raise ValueError("ExpressiveAcousticUnit.consonant_count must be non-negative int")
        if not isinstance(self.vowel_count, int) or self.vowel_count < 0:
            raise ValueError("ExpressiveAcousticUnit.vowel_count must be non-negative int")
        if not isinstance(self.length, int) or self.length < 0:
            raise ValueError("ExpressiveAcousticUnit.length must be non-negative int")
        # DELTA: Validate expressive_anchor consistency
        if self.vowel_first and self.expressive_anchor != "vowel":
            raise ValueError(
                "ExpressiveAcousticUnit: vowel_first=True requires expressive_anchor='vowel'"
            )
        if not self.vowel_first and self.expressive_anchor != "consonant":
            raise ValueError(
                "ExpressiveAcousticUnit: vowel_first=False requires expressive_anchor='consonant'"
            )


# ============================================================================
# ACOUSTIC CLASSIFICATION TABLES (Deterministic — unchanged from canonical)
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
    'q': SoundClass.STOP, 'c': SoundClass.STOP,

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

    # Affricates
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
# CORE MAPPING FUNCTIONS (DELTA ENHANCED)
# ============================================================================


def map_expressive_acoustic_units(text: str) -> List[ExpressiveAcousticUnit]:
    """
    DELTA: Convert input string into ordered expressive acoustic units.

    This is the primary entry point for the experimental expressive mapper.
    It transforms raw text into a sequence of ExpressiveAcousticUnit primitives
    with additional structural metadata for expressive directionality.

    CORE/SUBSTRATE INVARIANTS (enforced):
        - Deterministic: Same input always produces same output
        - No semantics: Units have no meaning
        - No LLM calls: Pure rule-based processing
        - Language-agnostic: Works on sound structure only
        - No vrtti/emotion inference

    DELTA ENHANCEMENTS:
        - Consonant-anchored segmentation
        - vowel_first detection
        - expressive_anchor directional marker
        - cluster_order preservation (sa ≠ as)

    Args:
        text: Raw input string to tokenize

    Returns:
        List of ExpressiveAcousticUnit primitives in order

    Examples:
        >>> units = map_expressive_acoustic_units("sata")
        >>> units[0].vowel_first
        False
        >>> units[0].expressive_anchor
        'consonant'
        >>> units[0].cluster_order
        <ClusterOrder.CV: 'cv'>

        >>> units = map_expressive_acoustic_units("asta")
        >>> units[0].vowel_first
        True
        >>> units[0].expressive_anchor
        'vowel'
        >>> units[0].cluster_order
        <ClusterOrder.VC: 'vc'>
    """
    # Handle edge cases
    if not text:
        return []

    if not isinstance(text, str):
        raise TypeError(f"map_expressive_acoustic_units requires str, got {type(text).__name__}")

    # Step 1: Normalize input (minimal — preserve order)
    normalized = _normalize_text_preserving_order(text)

    if not normalized:
        return []

    # Step 2: Segment into consonant-anchored sound groups
    # DELTA: Uses consonant-anchored segmentation, not vowel-nucleated
    segments = _segment_consonant_anchored(normalized)

    # Step 3: Build expressive acoustic units
    units = []
    for idx, segment in enumerate(segments):
        unit = _build_expressive_acoustic_unit(segment, idx)
        units.append(unit)

    return units


def _normalize_text_preserving_order(text: str) -> str:
    """
    Normalize input text while preserving character order.

    DELTA: This normalization is minimal to ensure raw order fidelity.
    "sa" and "as" remain distinct after normalization.

    Rules (deterministic):
        1. Strip leading/trailing whitespace
        2. Convert to lowercase
        3. Preserve internal spaces as segment boundaries
        4. Remove non-alphabetic characters except spaces
        5. NO reordering or collapsing

    This is a read-only transformation.
    """
    # Strip and lowercase
    result = text.strip().lower()

    # Keep only alphabetic chars and spaces — NO reordering
    filtered = []
    for char in result:
        if char.isalpha() or char == ' ':
            filtered.append(char)

    return ''.join(filtered)


def _segment_consonant_anchored(text: str) -> List[str]:
    """
    DELTA: Segment text using consonant-anchored logic.

    Unlike the canonical mapper which uses vowel-nucleated segmentation,
    this experimental approach anchors units on consonants, treating
    vowels as wrappers/modifiers.

    Key differences from canonical:
        - Consonants are the anchoring points
        - Vowels attach to consonants (before or after)
        - Preserves CV vs VC distinction explicitly
        - Word boundaries (spaces) force segment breaks

    This segmentation ensures:
        - "sa" → single unit with consonant anchor
        - "as" → single unit with vowel-first pattern
        - "sa" ≠ "as" (distinct segments, never collapsed)
    """
    if not text:
        return []

    segments = []
    current_segment = []
    prev_was_vowel = False

    for i, char in enumerate(text):
        if char == ' ':
            # Space forces segment break
            if current_segment:
                segments.append(''.join(current_segment))
                current_segment = []
            prev_was_vowel = False
            continue

        is_vowel = char.lower() in EXTENDED_VOWELS
        is_consonant = not is_vowel

        if is_consonant:
            # DELTA: Consonant-anchored logic
            # If previous was a vowel, check if we should close
            if prev_was_vowel and current_segment:
                # Look ahead: if next char is vowel or end, close current segment
                next_idx = i + 1
                next_is_vowel = (
                    next_idx < len(text) and
                    text[next_idx].lower() in EXTENDED_VOWELS
                )
                if next_is_vowel or next_idx >= len(text) or text[next_idx] == ' ':
                    # Current consonant starts new segment
                    segments.append(''.join(current_segment))
                    current_segment = [char]
                    prev_was_vowel = False
                    continue

            current_segment.append(char)
            prev_was_vowel = False

        else:  # is_vowel
            current_segment.append(char)
            prev_was_vowel = True

            # DELTA: After vowel, check if segment should close
            next_idx = i + 1
            # Close segment after vowel if:
            # - End of text
            # - Space follows
            # - Another vowel follows (V-V boundary)
            if next_idx >= len(text) or text[next_idx] == ' ':
                segments.append(''.join(current_segment))
                current_segment = []
            elif text[next_idx].lower() in EXTENDED_VOWELS:
                # V-V boundary: close current
                segments.append(''.join(current_segment))
                current_segment = []

    # Handle any remaining segment
    if current_segment:
        segments.append(''.join(current_segment))

    # Filter empty segments
    return [s for s in segments if s]


def _build_expressive_acoustic_unit(segment: str, index: int) -> ExpressiveAcousticUnit:
    """
    DELTA: Build an ExpressiveAcousticUnit from a text segment.

    This analyzes acoustic properties AND expressive structural metadata
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

    # DELTA: Determine vowel_first
    vowel_first = _detect_vowel_first(segment)

    # DELTA: Determine expressive_anchor (derived from vowel_first)
    expressive_anchor: Literal["consonant", "vowel"] = "vowel" if vowel_first else "consonant"

    # DELTA: Determine cluster_order
    cluster_order = _classify_cluster_order(segment)

    return ExpressiveAcousticUnit(
        raw_text=segment,
        index=index,
        sound_class=sound_class,
        vowel_height=vowel_height,
        vowel_backness=vowel_backness,
        consonant_count=consonant_count,
        vowel_count=vowel_count,
        length=len(segment),
        is_syllable_nucleus=is_syllable_nucleus,
        # DELTA fields
        vowel_first=vowel_first,
        expressive_anchor=expressive_anchor,
        cluster_order=cluster_order,
    )


def _detect_vowel_first(segment: str) -> bool:
    """
    DELTA: Detect if vowel precedes consonant in segment.

    Returns True when:
        - A vowel appears before any consonant in the segment
        - The segment starts with a vowel
        - The segment is purely vowels

    Returns False when:
        - A consonant appears before any vowel
        - The segment starts with a consonant
        - The segment is purely consonants

    Examples:
        - "ab" → True (vowel 'a' precedes consonant 'b')
        - "ba" → False (consonant 'b' precedes vowel 'a')
        - "a"  → True (pure vowel, counts as vowel-first)
        - "b"  → False (pure consonant)
        - "ast" → True (vowel 'a' is first)
        - "sta" → False (consonant 's' is first)
    """
    if not segment:
        return False

    first_char = segment[0].lower()
    return first_char in EXTENDED_VOWELS


def _classify_cluster_order(segment: str) -> ClusterOrder:
    """
    DELTA: Classify the CV/VC pattern of a segment.

    This preserves raw order fidelity:
        - "sa" → CV
        - "as" → VC
        - "sat" → CVC
        - "asa" → VCV
        - "a" → V
        - "st" → C

    NO normalization that would collapse ordering.
    """
    if not segment:
        return ClusterOrder.COMPLEX

    # Build pattern string
    pattern = ""
    for char in segment:
        if char.lower() in EXTENDED_VOWELS:
            if not pattern or pattern[-1] != 'V':
                pattern += 'V'
        else:
            if not pattern or pattern[-1] != 'C':
                pattern += 'C'

    # Map pattern to ClusterOrder
    pattern_map = {
        'V': ClusterOrder.V,
        'C': ClusterOrder.C,
        'CV': ClusterOrder.CV,
        'VC': ClusterOrder.VC,
        'CVC': ClusterOrder.CVC,
        'VCV': ClusterOrder.VCV,
    }

    return pattern_map.get(pattern, ClusterOrder.COMPLEX)


def _classify_sound(segment: str) -> SoundClass:
    """
    Classify the primary sound type of a segment.

    DELTA: For consonant-anchored units, prioritize consonant classification
    when both consonants and vowels are present.

    Priority order:
        1. If pure vowel → VOWEL
        2. If contains consonant → classify by first consonant
        3. Otherwise → UNKNOWN
    """
    has_vowel = any(c.lower() in EXTENDED_VOWELS for c in segment)
    has_consonant = any(c.lower() not in EXTENDED_VOWELS and c.isalpha() for c in segment)

    # Pure vowel segment
    if has_vowel and not has_consonant:
        return SoundClass.VOWEL

    # Contains consonant: classify by first consonant (consonant-anchored)
    for char in segment:
        char_lower = char.lower()
        if char_lower in CONSONANT_CLASS_MAP:
            return CONSONANT_CLASS_MAP[char_lower]

    # Fallback: if has vowel but no mapped consonant
    if has_vowel:
        return SoundClass.VOWEL

    return SoundClass.UNKNOWN


def _classify_vowel(segment: str) -> Tuple[VowelHeight, VowelBackness]:
    """
    Extract vowel height and backness from segment.

    Returns properties of first vowel found, or UNKNOWN if none.
    (Unchanged from canonical)
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
# UTILITY FUNCTIONS (DELTA ENHANCED)
# ============================================================================


def get_expressive_acoustic_signature(units: List[ExpressiveAcousticUnit]) -> str:
    """
    DELTA: Generate compact acoustic signature with expressive markers.

    Format: "{anchor}{sound_class_initial}{cluster_order}" for each unit
    Where:
        - anchor: 'C' for consonant, 'V' for vowel
        - sound_class_initial: First letter of sound class
        - cluster_order: Pattern code

    Example: "CSL-cv|VVL-vc" (consonant-stop-cv, vowel-vowel-vc)
    """
    if not units:
        return ""

    signatures = []
    for unit in units:
        anchor = "V" if unit.expressive_anchor == "vowel" else "C"
        sc = unit.sound_class.value[0].upper()
        co = unit.cluster_order.value
        signatures.append(f"{anchor}{sc}-{co}")

    return "|".join(signatures)


def count_vowel_first_units(units: List[ExpressiveAcousticUnit]) -> int:
    """DELTA: Count units where vowel precedes consonant."""
    return sum(1 for u in units if u.vowel_first)


def count_consonant_anchored_units(units: List[ExpressiveAcousticUnit]) -> int:
    """DELTA: Count units with consonant anchor (default pattern)."""
    return sum(1 for u in units if u.expressive_anchor == "consonant")


def get_cluster_order_distribution(
    units: List[ExpressiveAcousticUnit]
) -> dict[ClusterOrder, int]:
    """DELTA: Get distribution of cluster order patterns."""
    distribution: dict[ClusterOrder, int] = {}
    for unit in units:
        distribution[unit.cluster_order] = distribution.get(unit.cluster_order, 0) + 1
    return distribution


# ============================================================================
# EXPERIMENTAL VALIDATION
# ============================================================================


def validate_invariants() -> bool:
    """
    Validate that all substrate invariants are preserved.

    This function exists to explicitly document and verify
    that this experimental module does not violate core constraints.
    """
    # All invariants must be True
    for invariant, value in SUBSTRATE_INVARIANTS.items():
        if not value:
            raise AssertionError(f"Substrate invariant violated: {invariant}")
    return True


# ============================================================================
# PUBLIC EXPORTS
# ============================================================================

__all__ = [
    # Primary function
    "map_expressive_acoustic_units",
    # Data classes
    "ExpressiveAcousticUnit",
    # Enums
    "SoundClass",
    "VowelHeight",
    "VowelBackness",
    "ClusterOrder",  # DELTA
    # Utility functions
    "get_expressive_acoustic_signature",
    "count_vowel_first_units",         # DELTA
    "count_consonant_anchored_units",  # DELTA
    "get_cluster_order_distribution",  # DELTA
    # Constants
    "SUBSTRATE_INVARIANTS",
    "EXPERIMENTAL_MODULE",
    "EXPERIMENTAL_WARNING",
    # Validation
    "validate_invariants",
]


# ============================================================================
# MODULE INITIALIZATION — EXPERIMENTAL WARNING
# ============================================================================

if __name__ != "__main__":
    # Print warning on import (can be suppressed in production by not importing)
    import warnings
    warnings.warn(EXPERIMENTAL_WARNING, UserWarning, stacklevel=2)
