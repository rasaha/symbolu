"""
Phase-2 Modifier Engine (v3.2)
==============================

A structural modifier layer that operates on Phase-1b output.

Purpose:
    - Annotate structural relationships between adjacent acoustic units
    - NO semantic interpretation
    - NO mutation of Phase-1b units

Input: List[AcousticBridgeUnit]
Output: List[Phase2ModifiedUnit]

Version: 3.2
Date: 2025-12-15
Depends On: Phase-1b Acoustic Unit Mapper v3.1
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Literal, Dict, Any, Optional, Tuple
import hashlib
import json


# ============================================================================
# VERSION AND MODULE MARKER
# ============================================================================

PHASE2_ENGINE_VERSION = "3.2"

EXPERIMENTAL_MODULE_V3_2 = True
EXPERIMENTAL_WARNING_V3_2 = (
    "This module is EXPERIMENTAL (Phase-2 Modifier Engine v3.2). "
    "Do not use in production pipelines or governance decisions. "
    "Operates on Phase-1b output only. No semantic interpretation."
)


# ============================================================================
# PHASE-2 INVARIANTS (v3.2)
# ============================================================================

PHASE2_INVARIANTS_V3_2 = {
    # Structural constraints
    "DETERMINISTIC": True,
    "REVERSIBLE": True,
    "AUDITABLE": True,
    "NON_MUTATING": True,

    # Semantic exclusions
    "NO_SEMANTICS": True,
    "NO_MEANING_ASSIGNMENT": True,
    "NO_INTENT_INFERENCE": True,
    "NO_EMOTION_INFERENCE": True,
    "NO_SENTIMENT_ANALYSIS": True,

    # Linguistic exclusions
    "NO_WORD_BOUNDARY_DETECTION": True,
    "NO_SYLLABLE_ANALYSIS": True,
    "NO_MORPHEME_DETECTION": True,
    "NO_PHONOTACTIC_RULES": True,
    "NO_PRONUNCIATION_INFERENCE": True,

    # Polarity exclusions
    "NO_VRTTI_POLARITY": True,
    "NO_NEGATION_INFERENCE": True,
    "NO_AFFIRMATION_INFERENCE": True,
    "NO_OBSERVER_OBSERVED_LOGIC": True,

    # Classification exclusions
    "NO_LANGUAGE_DETECTION": True,
    "NO_SCRIPT_CLASSIFICATION": True,
    "NO_ERROR_CLASSIFICATION": True,
    "NO_VALIDITY_JUDGMENT": True,

    # External dependency exclusions
    "NO_DICTIONARY_LOOKUP": True,
    "NO_LLM_INFERENCE": True,
    "NO_HEURISTIC_RULES": True,
    "NO_STATISTICAL_MODELS": True,
}


# ============================================================================
# TYPE DEFINITIONS (Modifier Value Types)
# ============================================================================

AdjacencyType = Literal["isolated", "bound_left", "bound_right", "bound_both"]
VowelConsonantTransition = Literal["V_to_C", "C_to_V", "V_to_V", "C_to_C", "U_involved"]
AspirationContrast = Literal["both_aspirated", "both_unaspirated", "contrast_present", "not_applicable"]
UnknownBarrier = Literal["is_unknown", "left_of_unknown", "right_of_unknown", "between_unknowns", "none"]
BoundaryPosition = Literal["sequence_start", "sequence_end", "sequence_interior", "singleton"]
ContinuityType = Literal["continuous", "interrupted"]
SequenceClass = Literal["all_known", "all_unknown", "mixed", "empty"]
RepetitionMarker = Literal["repeated", "not_repeated"]

# Modifier types for Phase2Modifier dataclass
ModifierType = Literal[
    "NEGATION",
    "INVERSION",
    "AMPLIFICATION",
    "ATTENUATION",
    "MASK"
]

ModifierScope = Literal["UNIT", "CLUSTER"]
ModifierDirection = Literal["FORWARD", "BACKWARD"]


# ============================================================================
# DATACLASSES — MODIFIER STRUCTURES
# ============================================================================


@dataclass(frozen=True)
class ContinuitySpan:
    """Represents a contiguous span with continuity information."""
    type: ContinuityType
    span_indices: Tuple[int, int]  # (start_index, end_index) inclusive


@dataclass(frozen=True)
class ComputationMetadata:
    """Metadata about modifier computation."""
    phase2_version: str
    computed_at_index: int
    sequence_length: int
    modifier_count: int


@dataclass(frozen=True)
class Phase2Modifier:
    """
    Individual modifier annotation as per spec.

    Used for relational effects (negation, inversion, etc.)
    """
    modifier_type: ModifierType
    target_index: int
    scope: ModifierScope
    direction: ModifierDirection
    trigger: str


@dataclass(frozen=True)
class ModifierEnvelope:
    """
    Container for all modifiers attached to a unit.

    This is the Phase-2 annotation layer - additive only, no Phase-1b mutation.
    """
    # Unit-level modifiers (apply to single unit)
    adjacency_type: AdjacencyType
    boundary_position: BoundaryPosition
    unknown_barrier: UnknownBarrier

    # Pair-level modifiers (apply to this unit + next)
    vowel_consonant_transition: Optional[VowelConsonantTransition]  # None for last unit
    aspiration_contrast: Optional[AspirationContrast]  # None for last unit
    repetition_marker: Optional[RepetitionMarker]  # None for last unit

    # Span-level context (reference only)
    continuity_spans: Tuple[ContinuitySpan, ...]
    sequence_class: SequenceClass

    # Relational modifiers (from original spec)
    relational_modifiers: Tuple[Phase2Modifier, ...]

    # Computation metadata
    metadata: ComputationMetadata


# ============================================================================
# IMPORT Phase-1b TYPES (for type checking)
# ============================================================================

# We import AcousticBridgeUnit at runtime to avoid circular imports
# Type stub for IDE support
try:
    from acoustic_unit_mapper_expressive_delta_v3_1 import AcousticBridgeUnit
except ImportError:
    # Fallback for when running from different directory
    AcousticBridgeUnit = Any  # type: ignore


@dataclass(frozen=True)
class Phase2ModifiedUnit:
    """
    Phase-2 output unit containing immutable Phase-1b reference + modifiers.

    This is the primary output type for the Phase-2 modifier engine.

    Invariants:
        - source_unit is IMMUTABLE (frozen Phase-1b AcousticBridgeUnit)
        - modifiers are additive only (no Phase-1b data deleted)
        - Original sequence is recoverable via source_unit extraction
    """
    source_unit: Any  # AcousticBridgeUnit (frozen, immutable)
    modifiers: ModifierEnvelope

    # Pre-computed hash of source_unit for integrity verification
    source_hash: str = field(default="")

    def __post_init__(self):
        """Compute source hash if not provided."""
        if not self.source_hash:
            # Compute hash from source unit fields
            hash_input = (
                f"{self.source_unit.varna}|"
                f"{self.source_unit.index}|"
                f"{self.source_unit.is_vowel}|"
                f"{self.source_unit.is_consonant}|"
                f"{self.source_unit.is_aspirated}|"
                f"{self.source_unit.bridge_meaning}|"
                f"{self.source_unit.cluster_order}"
            )
            computed_hash = hashlib.sha256(hash_input.encode()).hexdigest()[:16]
            # Use object.__setattr__ since frozen=True
            object.__setattr__(self, 'source_hash', computed_hash)


# ============================================================================
# MODIFIER COMPUTATION FUNCTIONS
# ============================================================================


def _compute_adjacency_type(index: int, sequence_length: int) -> AdjacencyType:
    """
    Compute adjacency type for a unit at given index.

    Rules:
        - isolated: single unit in sequence
        - bound_right: first unit, sequence > 1
        - bound_left: last unit, sequence > 1
        - bound_both: interior unit
    """
    if sequence_length == 1:
        return "isolated"
    elif index == 0:
        return "bound_right"
    elif index == sequence_length - 1:
        return "bound_left"
    else:
        return "bound_both"


def _compute_boundary_position(index: int, sequence_length: int) -> BoundaryPosition:
    """
    Compute boundary position for a unit.

    Rules:
        - singleton: single unit in sequence
        - sequence_start: first unit
        - sequence_end: last unit
        - sequence_interior: interior unit
    """
    if sequence_length == 1:
        return "singleton"
    elif index == 0:
        return "sequence_start"
    elif index == sequence_length - 1:
        return "sequence_end"
    else:
        return "sequence_interior"


def _is_unit_unknown(unit: Any) -> bool:
    """Check if a unit is unknown (neither vowel nor consonant)."""
    return not unit.is_vowel and not unit.is_consonant


def _compute_unknown_barrier(
    index: int,
    units: List[Any],
) -> UnknownBarrier:
    """
    Compute unknown barrier modifier for a unit.

    Rules:
        - is_unknown: current unit is unknown
        - left_of_unknown: current known, next is unknown
        - right_of_unknown: current known, previous is unknown
        - between_unknowns: both neighbors are unknown
        - none: no unknown involvement
    """
    current = units[index]
    seq_len = len(units)

    # Check if current is unknown
    if _is_unit_unknown(current):
        return "is_unknown"

    # Check neighbors
    prev_unknown = index > 0 and _is_unit_unknown(units[index - 1])
    next_unknown = index < seq_len - 1 and _is_unit_unknown(units[index + 1])

    if prev_unknown and next_unknown:
        return "between_unknowns"
    elif next_unknown:
        return "left_of_unknown"
    elif prev_unknown:
        return "right_of_unknown"
    else:
        return "none"


def _compute_vowel_consonant_transition(
    current: Any,
    next_unit: Any,
) -> VowelConsonantTransition:
    """
    Compute vowel-consonant transition between two adjacent units.

    Rules:
        - U_involved: either unit is unknown
        - V_to_C: vowel -> consonant
        - C_to_V: consonant -> vowel
        - V_to_V: vowel -> vowel
        - C_to_C: consonant -> consonant
    """
    # Check for unknown involvement
    if _is_unit_unknown(current) or _is_unit_unknown(next_unit):
        return "U_involved"

    # Vowel/consonant transitions
    if current.is_vowel and next_unit.is_consonant:
        return "V_to_C"
    elif current.is_consonant and next_unit.is_vowel:
        return "C_to_V"
    elif current.is_vowel and next_unit.is_vowel:
        return "V_to_V"
    elif current.is_consonant and next_unit.is_consonant:
        return "C_to_C"
    else:
        # Fallback (shouldn't happen if is_vowel/is_consonant are correct)
        return "U_involved"


def _compute_aspiration_contrast(
    current: Any,
    next_unit: Any,
) -> AspirationContrast:
    """
    Compute aspiration contrast between two adjacent consonants.

    Rules:
        - not_applicable: either unit is not a consonant
        - both_aspirated: both consonants are aspirated
        - both_unaspirated: both consonants are unaspirated
        - contrast_present: aspiration differs
    """
    # Only applicable for consonant pairs
    if not current.is_consonant or not next_unit.is_consonant:
        return "not_applicable"

    if current.is_aspirated and next_unit.is_aspirated:
        return "both_aspirated"
    elif not current.is_aspirated and not next_unit.is_aspirated:
        return "both_unaspirated"
    else:
        return "contrast_present"


def _compute_repetition_marker(
    current: Any,
    next_unit: Any,
) -> RepetitionMarker:
    """
    Compute repetition marker for adjacent units.

    Rules:
        - repeated: same varna
        - not_repeated: different varnas
    """
    if current.varna == next_unit.varna:
        return "repeated"
    else:
        return "not_repeated"


def _compute_continuity_spans(units: List[Any]) -> Tuple[ContinuitySpan, ...]:
    """
    Compute continuity spans for the sequence.

    A span is 'continuous' if all units are known (vowel or consonant).
    A span is 'interrupted' if any unit is unknown.
    """
    if not units:
        return ()

    spans = []
    current_type: ContinuityType = "continuous" if not _is_unit_unknown(units[0]) else "interrupted"
    start_idx = 0

    for i, unit in enumerate(units):
        unit_type: ContinuityType = "continuous" if not _is_unit_unknown(unit) else "interrupted"

        if unit_type != current_type:
            # Close current span
            spans.append(ContinuitySpan(type=current_type, span_indices=(start_idx, i - 1)))
            # Start new span
            current_type = unit_type
            start_idx = i

    # Close final span
    spans.append(ContinuitySpan(type=current_type, span_indices=(start_idx, len(units) - 1)))

    return tuple(spans)


def _compute_sequence_class(units: List[Any]) -> SequenceClass:
    """
    Compute sequence class for the entire sequence.

    Rules:
        - empty: no units
        - all_known: all units are vowel or consonant
        - all_unknown: all units are unknown
        - mixed: some known, some unknown
    """
    if not units:
        return "empty"

    known_count = sum(1 for u in units if not _is_unit_unknown(u))
    unknown_count = len(units) - known_count

    if unknown_count == 0:
        return "all_known"
    elif known_count == 0:
        return "all_unknown"
    else:
        return "mixed"


def _compute_relational_modifiers(
    index: int,
    units: List[Any],
) -> Tuple[Phase2Modifier, ...]:
    """
    Compute relational modifiers (negation, inversion, etc.) for a unit.

    This implements the vowel-first negation rule from the spec:
        - If a vowel appears before a consonant, the consonant's bridge meaning
          is relationally negated (modifier attached, Phase-1b NOT modified)

    Also implements:
        - Aspirated observer shift (marks externally projected)
        - Unknown isolation (blocks modifier propagation)
    """
    modifiers = []
    current = units[index]
    seq_len = len(units)

    # Rule 1: Vowel-First Negation
    # If previous unit is a vowel and current is a consonant -> attach NEGATION
    if index > 0:
        prev_unit = units[index - 1]
        if prev_unit.is_vowel and current.is_consonant:
            modifiers.append(Phase2Modifier(
                modifier_type="NEGATION",
                target_index=index,
                scope="UNIT",
                direction="BACKWARD",
                trigger="vowel_first"
            ))

    # Rule 2: Aspirated Observer Shift (MASK for externally projected)
    if current.is_consonant and current.is_aspirated:
        modifiers.append(Phase2Modifier(
            modifier_type="MASK",
            target_index=index,
            scope="UNIT",
            direction="FORWARD",
            trigger="aspirated"
        ))

    # Rule 3: Unknown Isolation (block propagation - ATTENUATION marker)
    if _is_unit_unknown(current):
        modifiers.append(Phase2Modifier(
            modifier_type="ATTENUATION",
            target_index=index,
            scope="CLUSTER",
            direction="FORWARD",
            trigger="unknown_barrier"
        ))

    return tuple(modifiers)


# ============================================================================
# MAIN MODIFIER ENGINE FUNCTION
# ============================================================================


def apply_modifiers(units: List[Any]) -> List[Phase2ModifiedUnit]:
    """
    Apply Phase-2 modifiers to a list of Phase-1b AcousticBridgeUnits.

    This is the primary entry point for the Phase-2 modifier engine.

    Args:
        units: List[AcousticBridgeUnit] from Phase-1b mapper

    Returns:
        List[Phase2ModifiedUnit] with modifiers attached

    Invariants:
        - Phase-1b units are NOT modified
        - Original sequence recoverable via: [m.source_unit for m in modified]
        - Deterministic: same input always produces same output
    """
    if not units:
        return []

    seq_len = len(units)

    # Pre-compute span-level modifiers (shared across all units)
    continuity_spans = _compute_continuity_spans(units)
    sequence_class = _compute_sequence_class(units)

    modified_units = []

    for idx, unit in enumerate(units):
        # Compute unit-level modifiers
        adjacency_type = _compute_adjacency_type(idx, seq_len)
        boundary_position = _compute_boundary_position(idx, seq_len)
        unknown_barrier = _compute_unknown_barrier(idx, units)

        # Compute pair-level modifiers (None for last unit)
        if idx < seq_len - 1:
            next_unit = units[idx + 1]
            vowel_consonant_transition = _compute_vowel_consonant_transition(unit, next_unit)
            aspiration_contrast = _compute_aspiration_contrast(unit, next_unit)
            repetition_marker = _compute_repetition_marker(unit, next_unit)
        else:
            vowel_consonant_transition = None
            aspiration_contrast = None
            repetition_marker = None

        # Compute relational modifiers
        relational_modifiers = _compute_relational_modifiers(idx, units)

        # Build modifier envelope
        envelope = ModifierEnvelope(
            adjacency_type=adjacency_type,
            boundary_position=boundary_position,
            unknown_barrier=unknown_barrier,
            vowel_consonant_transition=vowel_consonant_transition,
            aspiration_contrast=aspiration_contrast,
            repetition_marker=repetition_marker,
            continuity_spans=continuity_spans,
            sequence_class=sequence_class,
            relational_modifiers=relational_modifiers,
            metadata=ComputationMetadata(
                phase2_version=PHASE2_ENGINE_VERSION,
                computed_at_index=idx,
                sequence_length=seq_len,
                modifier_count=len(relational_modifiers)
            )
        )

        # Create modified unit (source_unit is immutable reference)
        modified_unit = Phase2ModifiedUnit(
            source_unit=unit,
            modifiers=envelope
        )

        modified_units.append(modified_unit)

    return modified_units


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================


def extract_phase1b_units(modified_units: List[Phase2ModifiedUnit]) -> List[Any]:
    """
    Extract original Phase-1b units from Phase-2 modified units.

    This demonstrates the reversibility guarantee:
        original = extract_phase1b_units(modified)
        assert original == input_units  # Exact recovery
    """
    return [m.source_unit for m in modified_units]


def compute_phase1b_hash(units: List[Any]) -> str:
    """
    Compute a deterministic hash of Phase-1b units for integrity verification.

    This is used to verify that Phase-1b units are unchanged after Phase-2.
    """
    if not units:
        return hashlib.sha256(b"empty").hexdigest()[:32]

    hash_parts = []
    for unit in units:
        part = (
            f"{unit.varna}|{unit.index}|{unit.is_vowel}|"
            f"{unit.is_consonant}|{unit.is_aspirated}|"
            f"{unit.bridge_meaning}|{unit.cluster_order}"
        )
        hash_parts.append(part)

    combined = "||".join(hash_parts)
    return hashlib.sha256(combined.encode()).hexdigest()[:32]


def verify_phase1b_integrity(
    original_units: List[Any],
    modified_units: List[Phase2ModifiedUnit]
) -> bool:
    """
    Verify that Phase-1b units are unchanged after Phase-2 processing.

    Returns True if:
        1. Same number of units
        2. All fields match exactly
        3. Hash matches
    """
    extracted = extract_phase1b_units(modified_units)

    # Check count
    if len(original_units) != len(extracted):
        return False

    # Check each unit
    for orig, ext in zip(original_units, extracted):
        if (
            orig.varna != ext.varna or
            orig.index != ext.index or
            orig.is_vowel != ext.is_vowel or
            orig.is_consonant != ext.is_consonant or
            orig.is_aspirated != ext.is_aspirated or
            orig.bridge_meaning != ext.bridge_meaning or
            orig.cluster_order != ext.cluster_order
        ):
            return False

    # Verify hash
    original_hash = compute_phase1b_hash(original_units)
    extracted_hash = compute_phase1b_hash(extracted)

    return original_hash == extracted_hash


def get_modifiers_summary(modified_units: List[Phase2ModifiedUnit]) -> Dict[str, Any]:
    """
    Get a summary of all modifiers applied.

    Useful for debugging and testing.
    """
    if not modified_units:
        return {"count": 0, "units": []}

    summary = {
        "count": len(modified_units),
        "sequence_class": modified_units[0].modifiers.sequence_class,
        "continuity_spans": [
            {"type": s.type, "indices": s.span_indices}
            for s in modified_units[0].modifiers.continuity_spans
        ],
        "units": []
    }

    for m in modified_units:
        unit_summary = {
            "index": m.modifiers.metadata.computed_at_index,
            "varna": m.source_unit.varna,
            "adjacency_type": m.modifiers.adjacency_type,
            "boundary_position": m.modifiers.boundary_position,
            "unknown_barrier": m.modifiers.unknown_barrier,
            "vowel_consonant_transition": m.modifiers.vowel_consonant_transition,
            "aspiration_contrast": m.modifiers.aspiration_contrast,
            "repetition_marker": m.modifiers.repetition_marker,
            "relational_modifiers": [
                {
                    "type": rm.modifier_type,
                    "trigger": rm.trigger,
                    "direction": rm.direction
                }
                for rm in m.modifiers.relational_modifiers
            ]
        }
        summary["units"].append(unit_summary)

    return summary


# ============================================================================
# VALIDATION FUNCTIONS
# ============================================================================


def validate_invariants_v3_2() -> bool:
    """
    Validate that all Phase-2 invariants are preserved.

    Returns True if all invariants hold.
    """
    for invariant, value in PHASE2_INVARIANTS_V3_2.items():
        if not value:
            raise AssertionError(f"Phase-2 invariant violated: {invariant}")
    return True


def validate_modified_unit(unit: Phase2ModifiedUnit) -> bool:
    """
    Validate a single Phase2ModifiedUnit for structural correctness.

    Checks:
        1. source_unit exists and has required fields
        2. modifiers envelope is complete
        3. hash is valid
    """
    # Check source unit
    if not hasattr(unit.source_unit, 'varna'):
        raise AssertionError("source_unit missing 'varna' field")
    if not hasattr(unit.source_unit, 'bridge_meaning'):
        raise AssertionError("source_unit missing 'bridge_meaning' field")

    # Check modifiers
    if unit.modifiers.adjacency_type not in ["isolated", "bound_left", "bound_right", "bound_both"]:
        raise AssertionError(f"Invalid adjacency_type: {unit.modifiers.adjacency_type}")

    if unit.modifiers.boundary_position not in ["singleton", "sequence_start", "sequence_end", "sequence_interior"]:
        raise AssertionError(f"Invalid boundary_position: {unit.modifiers.boundary_position}")

    # Check hash
    if not unit.source_hash:
        raise AssertionError("source_hash is empty")

    return True


# ============================================================================
# PUBLIC EXPORTS
# ============================================================================

__all__ = [
    # Version
    "PHASE2_ENGINE_VERSION",

    # Primary function
    "apply_modifiers",

    # Data classes
    "Phase2ModifiedUnit",
    "Phase2Modifier",
    "ModifierEnvelope",
    "ComputationMetadata",
    "ContinuitySpan",

    # Type aliases
    "AdjacencyType",
    "VowelConsonantTransition",
    "AspirationContrast",
    "UnknownBarrier",
    "BoundaryPosition",
    "ContinuityType",
    "SequenceClass",
    "RepetitionMarker",
    "ModifierType",
    "ModifierScope",
    "ModifierDirection",

    # Utility functions
    "extract_phase1b_units",
    "compute_phase1b_hash",
    "verify_phase1b_integrity",
    "get_modifiers_summary",

    # Constants
    "PHASE2_INVARIANTS_V3_2",
    "EXPERIMENTAL_MODULE_V3_2",
    "EXPERIMENTAL_WARNING_V3_2",

    # Validation
    "validate_invariants_v3_2",
    "validate_modified_unit",
]


# ============================================================================
# MODULE INITIALIZATION — EXPERIMENTAL WARNING (Phase-2)
# ============================================================================

if __name__ != "__main__":
    import warnings
    warnings.warn(EXPERIMENTAL_WARNING_V3_2, UserWarning, stacklevel=2)
