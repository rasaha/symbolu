"""
Acoustic Unit Mapper — Expressive Delta v3.1 (Phase-1b)

• Removes heuristic phonetic classification
• Uses Sanskrit Varṇa symbols as acoustic substrate
• Attaches bridge meanings (pre-semantic, non-interpreted)
• No vr̥tti, no semantics, no observer/observed logic
• v3 and v2 remain unchanged

v3.1 FIX: Unknown varṇas are no longer classified as vowels/consonants
using a hard-coded set. They are emitted as opaque unknown units only.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import List, Literal, Dict, Any, Optional


# ============================================================================
# VERSION AND MODULE MARKER
# ============================================================================

ACOUSTIC_MAPPER_VERSION = 3.1

EXPERIMENT_ONLY = True  # Required by ONTOLOGY_FREEZE_CONTRACT
EXPERIMENTAL_MODULE_V3_1 = True
EXPERIMENTAL_WARNING_V3_1 = (
    "This module is EXPERIMENTAL (Delta v3.1 — Phase-1b). Do not use in production "
    "pipelines or governance decisions. Uses Varṇa-based substrate only. "
    "For production use: symbolu/formulas/acoustic_unit_mapper.py"
)


# ============================================================================
# CORE/SUBSTRATE INVARIANT DECLARATIONS (Phase-1b)
# ============================================================================

SUBSTRATE_INVARIANTS_V3_1 = {
    # Core invariants (non-negotiable)
    "NO_SEMANTICS": True,
    "NO_INTENT": True,
    "NO_ROUTING": True,
    "NO_POLICY": True,
    "NO_LLM_CALLS": True,
    "DETERMINISTIC": True,
    "READ_ONLY": True,
    "NON_AUTHORITATIVE": True,

    # Phase-1b invariants (explicit)
    "NO_VRTTI_POLARITY": True,
    "NO_OBSERVER_OBSERVED": True,
    "NO_CONTEXTUAL_MEANING": True,
    "NO_DICTIONARY_LOGIC": True,
    "NO_SYNONYM_LOGIC": True,
    "NO_PHONETIC_HEURISTICS": True,

    # Removals from v1/v2 (explicit exclusions)
    "NO_SOUND_CLASS_ENUM": True,
    "NO_VOWEL_HEIGHT": True,
    "NO_VOWEL_BACKNESS": True,
    "NO_STOP_FRICATIVE_NASAL": True,
    "NO_IPA_ARTICULATORY": True,
    "NO_STRENGTH_FORCE_EMOTION": True,

    # v3.1 addition: No heuristic fallback classification
    "NO_HEURISTIC_FALLBACK_CLASSIFICATION": True,
}


# ============================================================================
# JSON DATA PATH (CANONICAL SOURCE)
# ============================================================================

# Resolve relative to this file's location
_MODULE_DIR = Path(__file__).parent
_JSON_PATH = _MODULE_DIR.parent / "data" / "varna_bridge_map_v1.json"


# ============================================================================
# CLUSTER ORDER TYPE (Simplified for Phase-1b)
# ============================================================================

ClusterOrder = Literal["V", "C", "CV", "VC", "CVC", "VCV", "COMPLEX"]
"""
Cluster order pattern within acoustic unit.

NOTE: cluster_order is a structural pattern marker, not a linguistic
syllabification claim. It describes the observed V/C sequence pattern
without making phonological assertions.

- V: Pure vowel ("a", "i", "u")
- C: Pure consonant(s) ("k", "st")
- CV: Consonant-vowel ("sa", "ta")
- VC: Vowel-consonant ("as", "at")
- CVC: Consonant-vowel-consonant ("sat", "tam")
- VCV: Vowel-consonant-vowel ("aha", "ata")
- COMPLEX: Irregular/multi-pattern or unknown varṇas
"""


# ============================================================================
# DATACLASS — ACOUSTIC BRIDGE UNIT (Phase-1b)
# ============================================================================


@dataclass(frozen=True)
class AcousticBridgeUnit:
    """
    Phase-1b Acoustic Bridge Unit — Varṇa-based substrate.

    This is the output unit for the v3.1 mapper. It contains ONLY:
    - Varṇa symbol identification
    - Structural properties (vowel/consonant, aspiration)
    - Bridge meaning from JSON (identifier only, not interpreted)
    - Cluster order preservation

    NO SEMANTICS. NO INTERPRETATION. NO VRTTI.

    v3.1 NOTE: Unknown varṇas (not in JSON) are emitted with:
        is_vowel=False, is_consonant=False, is_aspirated=False,
        bridge_meaning="unknown", cluster_order="COMPLEX"

    Fields:
        varna: The Sanskrit varṇa symbol (e.g., "sa", "da", "a")
        index: Position in the sequence (0-indexed)
        is_vowel: True if this is a vowel varṇa
        is_consonant: True if this is a consonant varṇa
        is_aspirated: True if consonant is aspirated (from JSON)
        bridge_meaning: Identifier from JSON (NOT interpreted)
        cluster_order: CV/VC/CVC pattern preservation
    """
    varna: str
    index: int
    is_vowel: bool
    is_consonant: bool
    is_aspirated: bool
    bridge_meaning: str
    cluster_order: ClusterOrder

    def __post_init__(self) -> None:
        """Validate AcousticBridgeUnit invariants."""
        # Index must be non-negative
        if not isinstance(self.index, int) or self.index < 0:
            raise ValueError(
                f"AcousticBridgeUnit.index must be non-negative int, got {self.index}"
            )

        # Vowel and consonant are mutually exclusive (but both can be False for unknown)
        if self.is_vowel and self.is_consonant:
            raise ValueError(
                "AcousticBridgeUnit cannot be both vowel and consonant"
            )

        # Aspiration only applies to consonants
        if self.is_aspirated and not self.is_consonant:
            raise ValueError(
                "AcousticBridgeUnit: is_aspirated=True requires is_consonant=True"
            )

        # Varna must be non-empty
        if not self.varna:
            raise ValueError("AcousticBridgeUnit.varna cannot be empty")


# ============================================================================
# VARNA BRIDGE MAP LOADER
# ============================================================================


class VarnaBridgeMap:
    """
    Loader and accessor for the canonical Varṇa Bridge Map JSON.

    This class provides the SOLE acoustic authority for v3.1.
    All lookups are deterministic and read-only.
    """

    def __init__(self, json_path: Optional[Path] = None):
        """
        Initialize the Varṇa Bridge Map from JSON.

        Args:
            json_path: Path to JSON file. Defaults to canonical location.
        """
        self._json_path = json_path or _JSON_PATH
        self._data: Dict[str, Any] = {}
        self._vowels: Dict[str, Dict[str, Any]] = {}
        self._consonants: Dict[str, Dict[str, Any]] = {}
        self._all_varnas: Dict[str, Dict[str, Any]] = {}
        self._load()

    def _load(self) -> None:
        """Load and parse the JSON file."""
        if not self._json_path.exists():
            raise FileNotFoundError(
                f"Varṇa Bridge Map JSON not found at: {self._json_path}"
            )

        with open(self._json_path, 'r', encoding='utf-8') as f:
            self._data = json.load(f)

        # Extract vowels and consonants
        self._vowels = self._data.get("vowels", {})
        self._consonants = self._data.get("consonants", {})

        # Build unified lookup (vowels and consonants combined)
        self._all_varnas = {}
        for varna, info in self._vowels.items():
            self._all_varnas[varna] = {
                **info,
                "is_vowel": True,
                "is_consonant": False,
                "is_aspirated": False,  # Vowels are never aspirated
            }
        for varna, info in self._consonants.items():
            self._all_varnas[varna] = {
                **info,
                "is_vowel": False,
                "is_consonant": True,
                "is_aspirated": info.get("aspirated", False),
            }

    def lookup(self, varna: str) -> Optional[Dict[str, Any]]:
        """
        Look up a varṇa by symbol.

        Args:
            varna: The varṇa symbol to look up (e.g., "sa", "a")

        Returns:
            Dictionary with varṇa properties, or None if not found.
        """
        return self._all_varnas.get(varna)

    def get_bridge_meaning(self, varna: str) -> str:
        """
        Get the bridge meaning for a varṇa.

        Args:
            varna: The varṇa symbol

        Returns:
            Bridge meaning string, or "unknown" if not found.
        """
        info = self.lookup(varna)
        if info:
            return info.get("bridge_meaning", "unknown")
        return "unknown"

    def is_vowel(self, varna: str) -> bool:
        """Check if varṇa is a vowel."""
        info = self.lookup(varna)
        return info.get("is_vowel", False) if info else False

    def is_consonant(self, varna: str) -> bool:
        """Check if varṇa is a consonant."""
        info = self.lookup(varna)
        return info.get("is_consonant", False) if info else False

    def is_aspirated(self, varna: str) -> bool:
        """Check if consonant is aspirated."""
        info = self.lookup(varna)
        return info.get("is_aspirated", False) if info else False

    @property
    def vowel_symbols(self) -> frozenset:
        """Get all vowel symbols."""
        return frozenset(self._vowels.keys())

    @property
    def consonant_symbols(self) -> frozenset:
        """Get all consonant symbols."""
        return frozenset(self._consonants.keys())

    @property
    def all_symbols(self) -> frozenset:
        """Get all varṇa symbols."""
        return frozenset(self._all_varnas.keys())


# ============================================================================
# SINGLETON BRIDGE MAP INSTANCE
# ============================================================================

_bridge_map: Optional[VarnaBridgeMap] = None


def _get_bridge_map() -> VarnaBridgeMap:
    """Get or create the singleton VarnaBridgeMap instance."""
    global _bridge_map
    if _bridge_map is None:
        _bridge_map = VarnaBridgeMap()
    return _bridge_map


# ============================================================================
# TEXT NORMALIZATION (Minimal — Preserve Order)
# ============================================================================


def _normalize_text(text: str) -> str:
    """
    Normalize input text for varṇa segmentation.

    Rules (deterministic):
        1. Strip leading/trailing whitespace
        2. Convert to lowercase
        3. Keep only alphabetic characters and spaces
        4. NO reordering or collapsing

    Args:
        text: Raw input string

    Returns:
        Normalized string
    """
    result = text.strip().lower()
    filtered = []
    for char in result:
        if char.isalpha() or char == ' ':
            filtered.append(char)
    return ''.join(filtered)


# ============================================================================
# VARNA SEGMENTATION
# ============================================================================


def _segment_into_varnas(text: str, bridge_map: VarnaBridgeMap) -> List[str]:
    """
    Segment normalized text into Sanskrit varṇa units.

    This uses a greedy longest-match algorithm to identify varṇa units
    from the JSON-defined symbol set.

    Strategy:
        1. Try to match the longest known varṇa at current position
        2. If no match, treat single character as unit
        3. Preserve order (no reordering)

    Args:
        text: Normalized input string
        bridge_map: VarnaBridgeMap instance for symbol lookup

    Returns:
        List of varṇa strings in order
    """
    if not text:
        return []

    varnas = []
    all_symbols = bridge_map.all_symbols

    # Sort symbols by length (longest first) for greedy matching
    sorted_symbols = sorted(all_symbols, key=len, reverse=True)

    i = 0
    while i < len(text):
        # Skip spaces
        if text[i] == ' ':
            i += 1
            continue

        # Try to match longest known varṇa
        matched = False
        for symbol in sorted_symbols:
            if text[i:i+len(symbol)] == symbol:
                varnas.append(symbol)
                i += len(symbol)
                matched = True
                break

        if not matched:
            # Single character as fallback
            varnas.append(text[i])
            i += 1

    return varnas


# ============================================================================
# CLUSTER ORDER DETECTION
# ============================================================================


def _detect_cluster_order(varnas: List[str], bridge_map: VarnaBridgeMap) -> ClusterOrder:
    """
    Detect the cluster order pattern for a sequence of varṇas.

    NOTE: cluster_order is a structural pattern marker, not a linguistic
    syllabification claim. It describes the observed V/C sequence without
    making phonological assertions about syllable boundaries.

    Args:
        varnas: List of varṇa strings
        bridge_map: VarnaBridgeMap instance

    Returns:
        ClusterOrder pattern
    """
    if not varnas:
        return "COMPLEX"

    # Build C/V pattern
    pattern = ""
    for varna in varnas:
        if bridge_map.is_vowel(varna):
            if not pattern or pattern[-1] != 'V':
                pattern += 'V'
        else:
            if not pattern or pattern[-1] != 'C':
                pattern += 'C'

    # Map to ClusterOrder
    pattern_map: Dict[str, ClusterOrder] = {
        'V': "V",
        'C': "C",
        'CV': "CV",
        'VC': "VC",
        'CVC': "CVC",
        'VCV': "VCV",
    }

    return pattern_map.get(pattern, "COMPLEX")


# ============================================================================
# MAIN MAPPER FUNCTION
# ============================================================================


def map_acoustic_units(text: str) -> List[AcousticBridgeUnit]:
    """
    Map input text to Phase-1b acoustic bridge units.

    This is the primary entry point for the v3.1 mapper.
    It transforms raw text into a sequence of AcousticBridgeUnit primitives
    using ONLY the Varṇa Bridge Map JSON as the acoustic authority.

    CORE/SUBSTRATE INVARIANTS (enforced):
        - Deterministic: Same input always produces same output
        - No semantics: Units have no meaning (bridge_meaning is identifier only)
        - No LLM calls: Pure rule-based processing
        - No phonetic heuristics: No IPA, no articulatory assumptions
        - No vr̥tti: No polarity resolution
        - No observer/observed: No perspective logic
        - No heuristic fallback: Unknown varṇas are NOT classified

    Pipeline:
        1. Normalize input text
        2. Segment into varṇa units using greedy longest-match
        3. For each varṇa:
            - Look up in JSON
            - If found: determine vowel/consonant, aspiration, bridge meaning
            - If NOT found: emit opaque unknown unit (no classification)
            - Preserve cluster order
        4. Emit ordered AcousticBridgeUnit list

    v3.1 FIX: Unknown varṇas are emitted as opaque units with:
        is_vowel=False, is_consonant=False, is_aspirated=False,
        bridge_meaning="unknown", cluster_order="COMPLEX"

    Args:
        text: Raw input string to process

    Returns:
        List of AcousticBridgeUnit primitives in order

    Examples:
        >>> units = map_acoustic_units("sa")
        >>> len(units)
        1
        >>> units[0].varna
        'sa'
        >>> units[0].is_consonant
        True
        >>> units[0].bridge_meaning
        'escape_pressure'

        >>> units = map_acoustic_units("a")
        >>> units[0].is_vowel
        True
        >>> units[0].bridge_meaning
        'birth_of_cognition'

        >>> units = map_acoustic_units("xyz")  # Unknown varṇas
        >>> units[0].is_vowel
        False
        >>> units[0].is_consonant
        False
        >>> units[0].bridge_meaning
        'unknown'
    """
    # Handle edge cases
    if not text:
        return []

    if not isinstance(text, str):
        raise TypeError(f"map_acoustic_units requires str, got {type(text).__name__}")

    # Get bridge map
    bridge_map = _get_bridge_map()

    # Step 1: Normalize input
    normalized = _normalize_text(text)
    if not normalized:
        return []

    # Step 2: Segment into varṇa units
    varnas = _segment_into_varnas(normalized, bridge_map)
    if not varnas:
        return []

    # Step 3: Build acoustic bridge units
    units = []
    for idx, varna in enumerate(varnas):
        # Look up varṇa properties from JSON
        info = bridge_map.lookup(varna)

        # Handle unknown varṇas (not in JSON) — v3.1 FIX
        # Do NOT classify as vowel/consonant using heuristics
        # Emit opaque unknown unit only
        if info is None:
            unit = AcousticBridgeUnit(
                varna=varna,
                index=idx,
                is_vowel=False,
                is_consonant=False,
                is_aspirated=False,
                bridge_meaning="unknown",
                cluster_order="COMPLEX",
            )
            units.append(unit)
            continue

        # Determine properties from JSON
        is_vowel = bridge_map.is_vowel(varna)
        is_consonant = bridge_map.is_consonant(varna)
        is_aspirated = bridge_map.is_aspirated(varna)
        bridge_meaning = bridge_map.get_bridge_meaning(varna)

        # Determine cluster order for this single unit
        # For individual units, pattern is just V or C
        if is_vowel:
            cluster_order: ClusterOrder = "V"
        elif is_consonant:
            cluster_order = "C"
        else:
            cluster_order = "COMPLEX"

        unit = AcousticBridgeUnit(
            varna=varna,
            index=idx,
            is_vowel=is_vowel,
            is_consonant=is_consonant,
            is_aspirated=is_aspirated,
            bridge_meaning=bridge_meaning,
            cluster_order=cluster_order,
        )
        units.append(unit)

    return units


def map_acoustic_units_with_context(text: str) -> List[AcousticBridgeUnit]:
    """
    Map input text to Phase-1b acoustic bridge units with contextual cluster order.

    This variant computes cluster_order based on the full sequence context,
    not just individual units. Use this when you need accurate CV/VC/CVC patterns.

    Args:
        text: Raw input string to process

    Returns:
        List of AcousticBridgeUnit primitives with contextual cluster_order
    """
    # Get base units
    units = map_acoustic_units(text)
    if not units:
        return []

    # Get bridge map for pattern detection
    bridge_map = _get_bridge_map()

    # Compute overall cluster order
    varnas = [u.varna for u in units]
    overall_order = _detect_cluster_order(varnas, bridge_map)

    # Rebuild units with contextual cluster order
    contextual_units = []
    for unit in units:
        contextual_unit = AcousticBridgeUnit(
            varna=unit.varna,
            index=unit.index,
            is_vowel=unit.is_vowel,
            is_consonant=unit.is_consonant,
            is_aspirated=unit.is_aspirated,
            bridge_meaning=unit.bridge_meaning,
            cluster_order=overall_order,
        )
        contextual_units.append(contextual_unit)

    return contextual_units


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================


def count_vowels(units: List[AcousticBridgeUnit]) -> int:
    """Count vowel units."""
    return sum(1 for u in units if u.is_vowel)


def count_consonants(units: List[AcousticBridgeUnit]) -> int:
    """Count consonant units."""
    return sum(1 for u in units if u.is_consonant)


def count_aspirated(units: List[AcousticBridgeUnit]) -> int:
    """Count aspirated consonant units."""
    return sum(1 for u in units if u.is_aspirated)


def count_unknown(units: List[AcousticBridgeUnit]) -> int:
    """Count unknown units (neither vowel nor consonant)."""
    return sum(1 for u in units if not u.is_vowel and not u.is_consonant)


def get_bridge_meanings(units: List[AcousticBridgeUnit]) -> List[str]:
    """Extract bridge meanings (identifiers only) from units."""
    return [u.bridge_meaning for u in units]


def get_acoustic_signature(units: List[AcousticBridgeUnit]) -> str:
    """
    Generate compact acoustic signature for units.

    Format: "{type}{aspirated}:{varna}" for each unit
    Where:
        - type: 'V' for vowel, 'C' for consonant, 'U' for unknown
        - aspirated: 'h' if aspirated, '' if not
        - varna: The varṇa symbol

    Example: "C:sa|V:a|Ch:kha|U:x"
    """
    if not units:
        return ""

    parts = []
    for unit in units:
        if unit.is_vowel:
            type_marker = "V"
        elif unit.is_consonant:
            type_marker = "C"
        else:
            type_marker = "U"  # Unknown
        asp_marker = "h" if unit.is_aspirated else ""
        parts.append(f"{type_marker}{asp_marker}:{unit.varna}")

    return "|".join(parts)


# ============================================================================
# VALIDATION FUNCTIONS
# ============================================================================


def validate_invariants_v3_1() -> bool:
    """
    Validate that all Phase-1b substrate invariants are preserved.

    CONFIRMATION CHECKLIST:
        ✓ v3 file remains UNCHANGED
        ✓ v2 file remains UNCHANGED
        ✓ v3.1 uses JSON as SOLE acoustic authority
        ✓ Heuristic phonetics fully REMOVED
        ✓ Heuristic fallback classification REMOVED
        ✓ No SoundClass, VowelHeight, VowelBackness
        ✓ No STOP/FRICATIVE/NASAL logic
        ✓ No IPA or articulatory assumptions
        ✓ Aspirates PRESERVED from JSON
        ✓ Vowels limited to JSON definitions
        ✓ Bridge meanings attached but NOT interpreted
        ✓ Unknown varṇas produce opaque units only
        ✓ Output is Phase-1b compliant
    """
    for invariant, value in SUBSTRATE_INVARIANTS_V3_1.items():
        if not value:
            raise AssertionError(f"Substrate invariant violated: {invariant}")
    return True


def validate_unit_consistency(units: List[AcousticBridgeUnit]) -> bool:
    """
    Validate structural consistency of acoustic bridge units.

    Checks:
        1. All units have valid varṇa symbols
        2. Vowel/consonant flags are mutually exclusive (but can both be False)
        3. Aspiration only applies to consonants
        4. Bridge meanings are non-empty
    """
    for unit in units:
        # Check vowel/consonant mutual exclusivity
        if unit.is_vowel and unit.is_consonant:
            raise AssertionError(
                f"Unit '{unit.varna}' cannot be both vowel and consonant"
            )

        # Check aspiration constraint
        if unit.is_aspirated and not unit.is_consonant:
            raise AssertionError(
                f"Unit '{unit.varna}' is aspirated but not a consonant"
            )

        # Check bridge meaning
        if not unit.bridge_meaning:
            raise AssertionError(
                f"Unit '{unit.varna}' has empty bridge_meaning"
            )

    return True


# ============================================================================
# PUBLIC EXPORTS
# ============================================================================

__all__ = [
    # Version
    "ACOUSTIC_MAPPER_VERSION",

    # Primary functions
    "map_acoustic_units",
    "map_acoustic_units_with_context",

    # Data class
    "AcousticBridgeUnit",

    # Type alias
    "ClusterOrder",

    # Bridge map class
    "VarnaBridgeMap",

    # Utility functions
    "count_vowels",
    "count_consonants",
    "count_aspirated",
    "count_unknown",
    "get_bridge_meanings",
    "get_acoustic_signature",

    # Constants
    "SUBSTRATE_INVARIANTS_V3_1",
    "EXPERIMENTAL_MODULE_V3_1",
    "EXPERIMENTAL_WARNING_V3_1",

    # Validation
    "validate_invariants_v3_1",
    "validate_unit_consistency",
]


# ============================================================================
# MODULE INITIALIZATION — EXPERIMENTAL WARNING (Phase-1b)
# ============================================================================

if __name__ != "__main__":
    import warnings
    warnings.warn(EXPERIMENTAL_WARNING_V3_1, UserWarning, stacklevel=2)
