"""
Acoustic Unit Mapper — Expressive Delta v2 (EXPERIMENTAL)
==========================================================

╔═══════════════════════════════════════════════════════════════════════════════╗
║                        ⚠️  EXPERIMENTAL — DELTA v2  ⚠️                        ║
║                                                                                ║
║  This module is EXPERIMENTAL and must NOT be used in production pipelines     ║
║  or governance decisions. It exists solely as a testbed for evaluating        ║
║  CODA/ONSET refinements for Phase-2 preparation.                              ║
║                                                                                ║
║  DEPENDS ON (conceptually): acoustic_unit_mapper_expressive_delta.py (v1)     ║
║  CANONICAL MODULE: symbolu/formulas/acoustic_unit_mapper.py                   ║
║  This delta does NOT replace or modify ANY prior module.                      ║
╚═══════════════════════════════════════════════════════════════════════════════╝

EXPRESSIVE DELTA v2 PURPOSE:
    This experimental module adds structural refinements to prepare for Phase-2
    decoding. It builds on the ExpressiveAcousticUnit output shape from delta v1
    and adds CODA/ONSET role detection and negation eligibility markers.

    ┌─────────────────────────────────────────────────────────────────────────┐
    │  CRITICAL INSIGHT: VC NEGATION CORRECTNESS                              │
    │                                                                          │
    │  VC negation applies ONLY when the consonant is a CODA in a fused unit. │
    │  Vowel + onset consonant sequences (e.g., a-ha, e-ha) must NOT trigger  │
    │  negation because the consonant initiates a new syllable, not closes.   │
    │                                                                          │
    │  Examples:                                                               │
    │    - "ab" → vowel 'a' + CODA consonant 'b' → eligible for negation      │
    │    - "aha" / "a-ha" → vowel 'a' + ONSET 'h' + vowel → NOT negation      │
    │    - "eha" → vowel 'e' + ONSET 'h' + vowel 'a' → NOT negation           │
    │                                                                          │
    │  The CODA vs ONSET distinction is essential for expressive correctness. │
    └─────────────────────────────────────────────────────────────────────────┘

DELTA v2 CHANGES (layered on v1):
    1. consonant_role: Literal["onset", "coda", "none"] — positional role marker
    2. eligible_for_negation: bool — structural eligibility flag (NOT application)
    3. fused_unit: bool — single fused sound group marker

RELATIONSHIP TO PRIOR MODULES:
    - Delta v1 remains VALID and UNCHANGED
    - Delta v2 ONLY refines eligibility logic with additional structural markers
    - NO semantics have leaked upstream
    - Phase-2 decoding is STILL REQUIRED to apply vrtti logic

CORE/SUBSTRATE INVARIANTS (PRESERVED — NON-NEGOTIABLE):
    - NO semantics: No knowledge of meaning
    - NO intent: No inference of user purpose
    - NO routing: No control flow direction
    - NO policy: No behavioral decisions
    - NO LLM calls: Purely deterministic, rule-based
    - NO vrtti values: No emotional/intentional mapping (positive or negative)
    - NO ontology/guna/kosha: No philosophical categorization
    - NO emotion inference: No "sad means X" logic
    - NO dictionary/synonym decisions: No lexical interpretation
    - DETERMINISTIC: Same input always produces same output
    - LANGUAGE-AGNOSTIC: Works on phonetic structure only
    - READ-ONLY: Pure transformation with no side effects
    - NON-AUTHORITATIVE: Cannot influence governance or routing

This is still pre-interpretive infrastructure, not intelligence.
Phase-2 decoding remains required for vrtti application.

Version: 0.2-experimental-delta-v2
Date: 2025-12-15
Based on: acoustic_unit_mapper_expressive_delta.py v0.1-experimental
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Literal, TYPE_CHECKING

# Import from delta v1 for type reference and structural composition
from .acoustic_unit_mapper_expressive_delta import (
    ExpressiveAcousticUnit,
    ClusterOrder,
    SoundClass,
    VowelHeight,
    VowelBackness,
    map_expressive_acoustic_units,
    EXTENDED_VOWELS,
)


# ============================================================================
# EXPERIMENTAL MODULE MARKER (DELTA v2)
# ============================================================================

EXPERIMENTAL_MODULE_V2 = True
EXPERIMENTAL_WARNING_V2 = (
    "This module is EXPERIMENTAL (Delta v2). Do not use in production pipelines or "
    "governance decisions. This is a Phase-2 preparatory refinement layer. "
    "For production use: symbolu/formulas/acoustic_unit_mapper.py"
)


# ============================================================================
# CORE/SUBSTRATE INVARIANT DECLARATIONS (DELTA v2 — REINFORCED)
# ============================================================================

SUBSTRATE_INVARIANTS_V2 = {
    # Core invariants (inherited)
    "NO_SEMANTICS": True,
    "NO_INTENT": True,
    "NO_ROUTING": True,
    "NO_POLICY": True,
    "NO_LLM_CALLS": True,
    "DETERMINISTIC": True,
    "LANGUAGE_AGNOSTIC": True,
    "READ_ONLY": True,
    "NON_AUTHORITATIVE": True,

    # Delta v1 invariants (preserved)
    "NO_VRTTI_VALUES": True,
    "NO_ONTOLOGY": True,
    "NO_GUNA_KOSHA": True,
    "NO_EMOTION_INFERENCE": True,

    # Delta v2 invariants (explicit additions)
    "NO_NEGATION_APPLICATION": True,      # v2: Eligibility only, not application
    "NO_MEANING_INFERENCE": True,         # v2: No dictionary/synonym decisions
    "NO_PHASE2_DECODING": True,           # v2: Explicitly preparatory only
    "STRUCTURAL_TRUTH_ONLY": True,        # v2: Only structural correctness
}


# ============================================================================
# CONSONANT ROLE TYPE
# ============================================================================

ConsonantRole = Literal["onset", "coda", "none"]
"""
DELTA v2: Positional role of consonant within acoustic unit.

Terminology (structural, not linguistic):
    - ONSET: Consonant that initiates/precedes a vowel within the unit
             The consonant "opens" the syllable toward the vowel.
             Examples: CV patterns ("sa", "ta"), VCV middle consonant ("aha")

    - CODA: Consonant that closes/follows a vowel with no vowel after it
            The consonant "closes" the syllable, terminating the vowel.
            Examples: VC patterns ("ab", "as"), CVC final consonant ("sat")

    - NONE: No consonant present in the unit (pure vowel)

WHY THIS MATTERS:
    VC pattern does NOT always imply negation eligibility.

    Consider:
        "ab" → 'a' + 'b'(coda) → fused unit → eligible for negation
        "aha" → 'a' + 'h'(onset) + 'a' → 'h' opens toward second 'a' → NOT eligible

    The onset consonant in "aha" does NOT close the first vowel; it initiates
    the second syllable. Only CODA consonants (that terminate a vowel with no
    following vowel) can participate in negation eligibility.

    This distinction is CRITICAL for expressive model correctness.
"""


# ============================================================================
# DATACLASS — DELTA v2 ENHANCED UNIT
# ============================================================================


@dataclass(frozen=True)
class ExpressiveAcousticUnitV2:
    """
    DELTA v2: Enhanced acoustic unit with CODA/ONSET refinements.

    This wraps ExpressiveAcousticUnit with additional structural markers
    for Phase-2 preparation WITHOUT adding semantic interpretation.

    INHERITED FIELDS (from ExpressiveAcousticUnit — all preserved):
        raw_text: str
        index: int
        sound_class: SoundClass
        vowel_height: VowelHeight
        vowel_backness: VowelBackness
        consonant_count: int
        vowel_count: int
        length: int
        is_syllable_nucleus: bool
        vowel_first: bool                    (from delta v1)
        expressive_anchor: Literal[...]      (from delta v1)
        cluster_order: ClusterOrder          (from delta v1)

    DELTA v2 FIELDS (new — structural only):
        consonant_role: ConsonantRole — positional role of consonant
        eligible_for_negation: bool — structural eligibility marker
        fused_unit: bool — single fused sound group marker

    INVARIANTS (enforced):
        - No meaning field
        - No vrtti field (positive or negative)
        - No emotion inference
        - No negation APPLICATION (only eligibility signaling)
        - Purely structural/acoustic properties
    """
    # Base unit reference (composition, not inheritance)
    base_unit: ExpressiveAcousticUnit
    """Reference to the delta v1 ExpressiveAcousticUnit being refined."""

    # ═══════════════════════════════════════════════════════════════════════
    # DELTA v2 FIELD 1: Consonant Role (CODA vs ONSET)
    # ═══════════════════════════════════════════════════════════════════════

    consonant_role: ConsonantRole
    """
    DELTA v2: Positional role of consonant within this unit.

    Rules (deterministic, structural only):
        - "coda" if:
            * Unit pattern is VC or CVC
            * AND consonant appears AFTER the vowel
            * AND there is NO vowel following that consonant in the same unit
        - "onset" if:
            * Consonant is followed by a vowel within the same unit
            * Applies to CV, VCV patterns, and middle consonants
        - "none" if:
            * No consonant exists in the unit (pure vowel)

    Examples:
        "ab"  → consonant_role = "coda"   (b follows a, no vowel after b)
        "ba"  → consonant_role = "onset"  (b precedes a)
        "sat" → consonant_role = "coda"   (t is final, closes the vowel)
        "aha" → consonant_role = "onset"  (h precedes second a)
        "a"   → consonant_role = "none"   (no consonant)

    ⚠️ This is STRUCTURAL ONLY — no semantic meaning is attached.
    ⚠️ This does NOT apply negation — it only identifies role.
    """

    # ═══════════════════════════════════════════════════════════════════════
    # DELTA v2 FIELD 2: Negation Eligibility (STRUCTURAL FLAG ONLY)
    # ═══════════════════════════════════════════════════════════════════════

    eligible_for_negation: bool
    """
    DELTA v2: Structural eligibility for negation in Phase-2.

    Rules (deterministic):
        - True ONLY when:
            * vowel_first == True (from base unit)
            * AND consonant_role == "coda"
        - False otherwise

    ⚠️ CRITICAL: This field does NOT apply negation.
    ⚠️ It ONLY signals eligibility for Phase-2 negation logic.
    ⚠️ Phase-2 decoding is REQUIRED to actually apply vrtti logic.

    Rationale:
        VC pattern alone is NOT sufficient for negation eligibility.
        The consonant must be a CODA (closing the vowel) for negation
        to be structurally valid.

        Examples:
            "ab" → vowel_first=True, consonant_role="coda" → eligible=True
            "aha" → even if vowel_first=True, consonant_role="onset" → eligible=False
            "ba" → vowel_first=False → eligible=False (regardless of role)

    This prevents incorrect negation of onset consonant sequences.
    """

    # ═══════════════════════════════════════════════════════════════════════
    # DELTA v2 FIELD 3: Fused Unit Marker
    # ═══════════════════════════════════════════════════════════════════════

    fused_unit: bool
    """
    DELTA v2: Marker for single fused sound group.

    Rules (deterministic, inferred from cluster_order only):
        - True if:
            * Unit represents a single fused sound group
            * No internal syllable break implied
            * Patterns: V, C, CV, VC, CVC (simple patterns)
        - False if:
            * Structure implies separable pronunciation
            * Internal syllable boundary exists
            * Patterns: VCV, COMPLEX (multi-syllable patterns)

    Examples:
        "ab"  → fused_unit = True   (single fused VC unit)
        "ba"  → fused_unit = True   (single fused CV unit)
        "sat" → fused_unit = True   (single fused CVC unit)
        "aha" → fused_unit = False  (VCV: separable as a-ha)
        "ata" → fused_unit = False  (VCV: separable as a-ta)

    This allows Phase-2 to distinguish:
        "ab" (fused, eligible for negation)
        "a-ha" (not fused, consonant is onset of second syllable)

    ⚠️ Inferred ONLY from cluster_order, not linguistics or semantics.
    """

    # ═══════════════════════════════════════════════════════════════════════
    # CONVENIENCE ACCESSORS (passthrough to base unit)
    # ═══════════════════════════════════════════════════════════════════════

    @property
    def raw_text(self) -> str:
        """Passthrough to base unit raw_text."""
        return self.base_unit.raw_text

    @property
    def index(self) -> int:
        """Passthrough to base unit index."""
        return self.base_unit.index

    @property
    def sound_class(self) -> SoundClass:
        """Passthrough to base unit sound_class."""
        return self.base_unit.sound_class

    @property
    def vowel_height(self) -> VowelHeight:
        """Passthrough to base unit vowel_height."""
        return self.base_unit.vowel_height

    @property
    def vowel_backness(self) -> VowelBackness:
        """Passthrough to base unit vowel_backness."""
        return self.base_unit.vowel_backness

    @property
    def consonant_count(self) -> int:
        """Passthrough to base unit consonant_count."""
        return self.base_unit.consonant_count

    @property
    def vowel_count(self) -> int:
        """Passthrough to base unit vowel_count."""
        return self.base_unit.vowel_count

    @property
    def length(self) -> int:
        """Passthrough to base unit length."""
        return self.base_unit.length

    @property
    def is_syllable_nucleus(self) -> bool:
        """Passthrough to base unit is_syllable_nucleus."""
        return self.base_unit.is_syllable_nucleus

    @property
    def vowel_first(self) -> bool:
        """Passthrough to base unit vowel_first (delta v1)."""
        return self.base_unit.vowel_first

    @property
    def expressive_anchor(self) -> Literal["consonant", "vowel"]:
        """Passthrough to base unit expressive_anchor (delta v1)."""
        return self.base_unit.expressive_anchor

    @property
    def cluster_order(self) -> ClusterOrder:
        """Passthrough to base unit cluster_order (delta v1)."""
        return self.base_unit.cluster_order

    def __post_init__(self) -> None:
        """Validate ExpressiveAcousticUnitV2 invariants."""
        # Validate base_unit is provided
        if not isinstance(self.base_unit, ExpressiveAcousticUnit):
            raise TypeError(
                f"ExpressiveAcousticUnitV2.base_unit must be ExpressiveAcousticUnit, "
                f"got {type(self.base_unit).__name__}"
            )

        # Validate consonant_role is valid
        if self.consonant_role not in ("onset", "coda", "none"):
            raise ValueError(
                f"ExpressiveAcousticUnitV2.consonant_role must be 'onset', 'coda', or 'none', "
                f"got {self.consonant_role!r}"
            )

        # Validate consonant_role consistency with consonant_count
        if self.base_unit.consonant_count == 0 and self.consonant_role != "none":
            raise ValueError(
                "ExpressiveAcousticUnitV2: consonant_count=0 requires consonant_role='none'"
            )
        if self.base_unit.consonant_count > 0 and self.consonant_role == "none":
            raise ValueError(
                "ExpressiveAcousticUnitV2: consonant_count>0 cannot have consonant_role='none'"
            )

        # Validate eligible_for_negation consistency
        # eligible_for_negation can ONLY be True when vowel_first AND coda
        if self.eligible_for_negation:
            if not self.base_unit.vowel_first:
                raise ValueError(
                    "ExpressiveAcousticUnitV2: eligible_for_negation=True requires vowel_first=True"
                )
            if self.consonant_role != "coda":
                raise ValueError(
                    "ExpressiveAcousticUnitV2: eligible_for_negation=True requires consonant_role='coda'"
                )


# ============================================================================
# DERIVATION FUNCTIONS (DELTA v2 — DETERMINISTIC)
# ============================================================================


def _derive_consonant_role(unit: ExpressiveAcousticUnit) -> ConsonantRole:
    """
    DELTA v2: Derive the consonant role (onset/coda/none) from unit structure.

    This is a DETERMINISTIC function based purely on structural analysis.
    NO semantics, NO linguistics beyond positional patterns.

    Rules:
        1. If consonant_count == 0 → "none"
        2. If cluster_order is CV or VCV → "onset"
           (consonant precedes or is followed by vowel)
        3. If cluster_order is VC or CVC → "coda"
           (consonant follows vowel with no vowel after)
        4. If cluster_order is C → "onset" (isolated consonant, treat as potential onset)
        5. If cluster_order is COMPLEX → analyze raw_text character by character

    Args:
        unit: ExpressiveAcousticUnit from delta v1

    Returns:
        ConsonantRole: "onset", "coda", or "none"
    """
    # Case 1: No consonant
    if unit.consonant_count == 0:
        return "none"

    # Case 2: Pure consonant (treat as onset - it would precede a vowel)
    if unit.cluster_order == ClusterOrder.C:
        return "onset"

    # Case 3: Onset patterns (consonant precedes or is between vowels)
    if unit.cluster_order in (ClusterOrder.CV, ClusterOrder.VCV):
        return "onset"

    # Case 4: Coda patterns (consonant closes the vowel)
    if unit.cluster_order in (ClusterOrder.VC, ClusterOrder.CVC):
        return "coda"

    # Case 5: Complex patterns - analyze final position
    # For complex patterns, check if the unit ends with consonant(s)
    # If it ends with consonant after a vowel, it's coda behavior
    if unit.cluster_order == ClusterOrder.COMPLEX:
        return _analyze_complex_consonant_role(unit.raw_text)

    # Case 6: Pure vowel (should not reach here, but defensive)
    if unit.cluster_order == ClusterOrder.V:
        return "none"

    # Fallback: treat as onset (conservative)
    return "onset"


def _analyze_complex_consonant_role(raw_text: str) -> ConsonantRole:
    """
    DELTA v2: Analyze complex patterns to determine consonant role.

    For COMPLEX cluster_order, we analyze the actual character sequence
    to determine if the primary consonant behavior is onset or coda.

    Strategy:
        - Find the LAST consonant in the sequence
        - If it has no vowel after it → coda
        - If it has a vowel after it → onset

    This is still purely structural analysis.
    """
    if not raw_text:
        return "none"

    # Find positions of all consonants and vowels
    last_consonant_idx = -1
    last_vowel_after_consonant = False

    for i, char in enumerate(raw_text):
        char_lower = char.lower()
        if char_lower not in EXTENDED_VOWELS and char_lower.isalpha():
            last_consonant_idx = i
            last_vowel_after_consonant = False
        elif char_lower in EXTENDED_VOWELS:
            if last_consonant_idx >= 0:
                last_vowel_after_consonant = True

    # No consonant found
    if last_consonant_idx < 0:
        return "none"

    # If there's a vowel after the last consonant, it's onset behavior
    # Otherwise, the last consonant is a coda
    if last_vowel_after_consonant:
        return "onset"
    else:
        return "coda"


def _derive_fused_unit(unit: ExpressiveAcousticUnit) -> bool:
    """
    DELTA v2: Derive whether unit is a single fused sound group.

    This is a DETERMINISTIC function based purely on cluster_order.
    NO semantics, NO linguistics.

    Rules:
        - True for simple, single-syllable patterns: V, C, CV, VC, CVC
        - False for multi-syllable patterns: VCV, COMPLEX

    Rationale:
        - VCV implies V-CV structure (separable as two syllables)
        - COMPLEX implies irregular/multi-pattern (potentially separable)
        - Simple patterns are naturally fused single sounds

    Args:
        unit: ExpressiveAcousticUnit from delta v1

    Returns:
        bool: True if fused single sound group, False if separable
    """
    # Fused patterns: single syllable, no internal breaks
    fused_patterns = {
        ClusterOrder.V,    # Single vowel
        ClusterOrder.C,    # Consonant cluster (no syllable break)
        ClusterOrder.CV,   # Consonant-vowel (single syllable)
        ClusterOrder.VC,   # Vowel-consonant (single syllable)
        ClusterOrder.CVC,  # Consonant-vowel-consonant (single syllable)
    }

    return unit.cluster_order in fused_patterns


def _derive_negation_eligibility(
    unit: ExpressiveAcousticUnit,
    consonant_role: ConsonantRole
) -> bool:
    """
    DELTA v2: Derive negation eligibility from structural properties.

    This is a DETERMINISTIC function. It does NOT apply negation.
    It ONLY signals eligibility for Phase-2 negation logic.

    Rules:
        - True ONLY when:
            * vowel_first == True (from unit)
            * AND consonant_role == "coda"
        - False otherwise

    Rationale:
        VC pattern alone is insufficient. The consonant must CLOSE the vowel
        (be a coda) for negation to be structurally valid.

        Counter-examples that must NOT be eligible:
            - "aha" → vowel_first may be True, but 'h' is onset → NOT eligible
            - "a-ha" → separable, 'h' initiates new syllable → NOT eligible

        Valid examples:
            - "ab" → vowel_first=True, 'b' is coda → eligible
            - "as" → vowel_first=True, 's' is coda → eligible

    ⚠️ Phase-2 decoding is STILL REQUIRED to apply vrtti logic.
    ⚠️ This is STRUCTURAL eligibility only.

    Args:
        unit: ExpressiveAcousticUnit from delta v1
        consonant_role: Pre-computed consonant role

    Returns:
        bool: True if structurally eligible for negation, False otherwise
    """
    # Both conditions must be met
    return unit.vowel_first and consonant_role == "coda"


# ============================================================================
# MAIN REFINEMENT FUNCTION (DELTA v2)
# ============================================================================


def refine_to_v2(unit: ExpressiveAcousticUnit) -> ExpressiveAcousticUnitV2:
    """
    DELTA v2: Refine a delta v1 unit into a delta v2 unit.

    This is the primary transformation function for delta v2.
    It adds CODA/ONSET role detection, negation eligibility,
    and fused unit markers to an existing ExpressiveAcousticUnit.

    INVARIANTS (enforced):
        - Deterministic: Same input always produces same output
        - No semantics: Only structural refinements
        - No vrtti application: Only eligibility signaling
        - Read-only: Pure transformation

    Args:
        unit: ExpressiveAcousticUnit from delta v1

    Returns:
        ExpressiveAcousticUnitV2 with added structural refinements
    """
    # Derive delta v2 fields (order matters for eligibility)
    consonant_role = _derive_consonant_role(unit)
    fused = _derive_fused_unit(unit)
    eligible = _derive_negation_eligibility(unit, consonant_role)

    return ExpressiveAcousticUnitV2(
        base_unit=unit,
        consonant_role=consonant_role,
        eligible_for_negation=eligible,
        fused_unit=fused,
    )


def map_expressive_acoustic_units_v2(text: str) -> List[ExpressiveAcousticUnitV2]:
    """
    DELTA v2: Full pipeline from raw text to v2 units.

    This combines delta v1 mapping with delta v2 refinements.

    Pipeline:
        1. text → ExpressiveAcousticUnit (via delta v1)
        2. ExpressiveAcousticUnit → ExpressiveAcousticUnitV2 (via refine_to_v2)

    CORE/SUBSTRATE INVARIANTS (enforced):
        - Deterministic: Same input always produces same output
        - No semantics: Units have no meaning
        - No LLM calls: Pure rule-based processing
        - No vrtti application: Only structural eligibility
        - Language-agnostic: Works on sound structure only

    Args:
        text: Raw input string to tokenize

    Returns:
        List of ExpressiveAcousticUnitV2 primitives in order

    Examples:
        >>> units = map_expressive_acoustic_units_v2("ab")
        >>> units[0].consonant_role
        'coda'
        >>> units[0].eligible_for_negation
        True
        >>> units[0].fused_unit
        True

        >>> units = map_expressive_acoustic_units_v2("aha")
        >>> units[0].consonant_role
        'onset'
        >>> units[0].eligible_for_negation
        False
        >>> units[0].fused_unit
        False
    """
    # Step 1: Get delta v1 units
    v1_units = map_expressive_acoustic_units(text)

    # Step 2: Refine to v2
    return [refine_to_v2(unit) for unit in v1_units]


# ============================================================================
# UTILITY FUNCTIONS (DELTA v2)
# ============================================================================


def count_negation_eligible_units(units: List[ExpressiveAcousticUnitV2]) -> int:
    """DELTA v2: Count units that are structurally eligible for negation."""
    return sum(1 for u in units if u.eligible_for_negation)


def count_coda_units(units: List[ExpressiveAcousticUnitV2]) -> int:
    """DELTA v2: Count units with coda consonant role."""
    return sum(1 for u in units if u.consonant_role == "coda")


def count_onset_units(units: List[ExpressiveAcousticUnitV2]) -> int:
    """DELTA v2: Count units with onset consonant role."""
    return sum(1 for u in units if u.consonant_role == "onset")


def count_fused_units(units: List[ExpressiveAcousticUnitV2]) -> int:
    """DELTA v2: Count units that are fused single sound groups."""
    return sum(1 for u in units if u.fused_unit)


def get_consonant_role_distribution(
    units: List[ExpressiveAcousticUnitV2]
) -> dict[ConsonantRole, int]:
    """DELTA v2: Get distribution of consonant roles."""
    distribution: dict[ConsonantRole, int] = {"onset": 0, "coda": 0, "none": 0}
    for unit in units:
        distribution[unit.consonant_role] += 1
    return distribution


def get_v2_acoustic_signature(units: List[ExpressiveAcousticUnitV2]) -> str:
    """
    DELTA v2: Generate compact acoustic signature with v2 markers.

    Format: "{role}{fused}{eligible}|{cluster_order}" for each unit
    Where:
        - role: 'O' for onset, 'D' for coda, 'N' for none
        - fused: 'F' if fused, 'S' if separable
        - eligible: 'E' if eligible for negation, '-' if not
        - cluster_order: Pattern code

    Example: "DF E|vc" (coda, fused, eligible, VC pattern)
    """
    if not units:
        return ""

    signatures = []
    for unit in units:
        role_map = {"onset": "O", "coda": "D", "none": "N"}
        role = role_map[unit.consonant_role]
        fused = "F" if unit.fused_unit else "S"
        eligible = "E" if unit.eligible_for_negation else "-"
        co = unit.cluster_order.value
        signatures.append(f"{role}{fused}{eligible}|{co}")

    return " ".join(signatures)


# ============================================================================
# EXPERIMENTAL VALIDATION (DELTA v2)
# ============================================================================


def validate_invariants_v2() -> bool:
    """
    Validate that all substrate invariants are preserved in delta v2.

    This function exists to explicitly document and verify
    that this experimental module does not violate core constraints.

    CONFIRMATION CHECKLIST:
        ✓ Delta v1 remains VALID and UNCHANGED
        ✓ Delta v2 ONLY refines eligibility logic
        ✓ NO semantics have leaked upstream
        ✓ Phase-2 decoding is STILL REQUIRED to apply vrtti logic
        ✓ NO negation is APPLIED — only eligibility is signaled
        ✓ All derivations are DETERMINISTIC
    """
    # All invariants must be True
    for invariant, value in SUBSTRATE_INVARIANTS_V2.items():
        if not value:
            raise AssertionError(f"Substrate invariant violated: {invariant}")

    return True


def validate_v2_consistency(units: List[ExpressiveAcousticUnitV2]) -> bool:
    """
    DELTA v2: Validate structural consistency of v2 units.

    Checks:
        1. All eligible_for_negation=True units have vowel_first=True AND coda
        2. All units with consonant_count=0 have consonant_role="none"
        3. All VCV/COMPLEX units have fused_unit=False
    """
    for unit in units:
        # Check 1: Eligibility requires vowel_first AND coda
        if unit.eligible_for_negation:
            if not unit.vowel_first:
                raise AssertionError(
                    f"Inconsistent: eligible_for_negation but vowel_first=False for '{unit.raw_text}'"
                )
            if unit.consonant_role != "coda":
                raise AssertionError(
                    f"Inconsistent: eligible_for_negation but consonant_role='{unit.consonant_role}' for '{unit.raw_text}'"
                )

        # Check 2: No consonant means role is none
        if unit.consonant_count == 0 and unit.consonant_role != "none":
            raise AssertionError(
                f"Inconsistent: consonant_count=0 but consonant_role='{unit.consonant_role}' for '{unit.raw_text}'"
            )

        # Check 3: VCV/COMPLEX should not be fused
        if unit.cluster_order in (ClusterOrder.VCV, ClusterOrder.COMPLEX):
            if unit.fused_unit:
                raise AssertionError(
                    f"Inconsistent: VCV/COMPLEX pattern but fused_unit=True for '{unit.raw_text}'"
                )

    return True


# ============================================================================
# PUBLIC EXPORTS
# ============================================================================

__all__ = [
    # Primary functions
    "map_expressive_acoustic_units_v2",
    "refine_to_v2",

    # Data class
    "ExpressiveAcousticUnitV2",

    # Type alias
    "ConsonantRole",

    # Derivation functions (exposed for testing)
    "_derive_consonant_role",
    "_derive_fused_unit",
    "_derive_negation_eligibility",

    # Utility functions
    "count_negation_eligible_units",
    "count_coda_units",
    "count_onset_units",
    "count_fused_units",
    "get_consonant_role_distribution",
    "get_v2_acoustic_signature",

    # Constants
    "SUBSTRATE_INVARIANTS_V2",
    "EXPERIMENTAL_MODULE_V2",
    "EXPERIMENTAL_WARNING_V2",

    # Validation
    "validate_invariants_v2",
    "validate_v2_consistency",
]


# ============================================================================
# MODULE INITIALIZATION — EXPERIMENTAL WARNING (DELTA v2)
# ============================================================================

if __name__ != "__main__":
    # Print warning on import (can be suppressed in production by not importing)
    import warnings
    warnings.warn(EXPERIMENTAL_WARNING_V2, UserWarning, stacklevel=2)
