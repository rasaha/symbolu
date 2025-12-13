"""
Vṛtti Mapper - Phase 1 Primitive Motion Quality Assignment
===========================================================

PHASE 1 MODULE - Assigns primitive motion qualities (vṛtti) to acoustic units.

This module maps acoustic units to fundamental motion qualities based purely
on articulatory/phonetic properties. These are NOT emotional or semantic
qualities - they are primitive descriptors of acoustic motion patterns.

ARCHITECTURAL CONSTRAINTS (PHASE 1 INVARIANTS):
    - NO semantics: Vṛtti are motion qualities, not meanings
    - NO intent: This module never infers user purpose
    - NO routing: This module does not direct control flow
    - NO policy: This module does not make behavioral decisions
    - NO LLM calls: Purely deterministic, rule-based processing
    - NO ontology lookup: Rules are self-contained
    - DETERMINISTIC: Same input always produces same output
    - READ-ONLY: Pure transformation with no side effects

Vṛtti Types (Non-Semantic Motion Qualities):
    - INERTIA: Stable, sustained energy (nasals, long vowels)
    - ACTIVATION: Sudden release of energy (stops, plosives)
    - OSCILLATION: Alternating/modulating energy (liquids, glides)
    - TENSION: Constrained/turbulent energy (fricatives, affricates)
    - RELEASE: Opening/relaxing energy (vowels, especially low)

Assignment is based on acoustic/articulatory properties only:
    - Sound class (stop, fricative, nasal, etc.)
    - Vowel properties (height, backness)
    - Cluster structure (consonant count, vowel count)

Version: 1.0 (Phase 1 Acoustic-Symbolic Tokenization)
Date: 2025-12-13
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import List, Dict

from symbolu.formulas.acoustic_unit_mapper import (
    AcousticUnit,
    SoundClass,
    VowelHeight,
    VowelBackness,
)


# ============================================================================
# PHASE 1 INVARIANT DECLARATIONS
# ============================================================================

PHASE_1_INVARIANTS = {
    "NO_SEMANTICS": True,
    "NO_INTENT": True,
    "NO_ROUTING": True,
    "NO_POLICY": True,
    "NO_LLM_CALLS": True,
    "NO_ONTOLOGY_LOOKUP": True,
    "DETERMINISTIC": True,
    "READ_ONLY": True,
}


# ============================================================================
# ENUMS - Vṛtti Motion Types (Non-Semantic)
# ============================================================================


class VrittiType(str, Enum):
    """
    Primitive motion qualities based on acoustic properties.

    These are NOT emotional or semantic categories.
    They describe fundamental patterns of acoustic energy/motion.

    The names derive from Sanskrit phonetics but are used here
    as pure descriptors of articulatory motion patterns.
    """
    INERTIA = "inertia"
    """Stable, sustained energy - nasals (m, n), long vowels, continuants"""

    ACTIVATION = "activation"
    """Sudden release of energy - stops (p, t, k), plosives, abrupt onsets"""

    OSCILLATION = "oscillation"
    """Alternating/modulating energy - liquids (l, r), glides (w, y)"""

    TENSION = "tension"
    """Constrained/turbulent energy - fricatives (f, s, h), affricates"""

    RELEASE = "release"
    """Opening/relaxing energy - open vowels (a), codas, phrase endings"""


# ============================================================================
# DATACLASSES - Vṛtti Assignment Results
# ============================================================================


@dataclass(frozen=True)
class AcousticVritti:
    """
    Vṛtti assignment for a single acoustic unit.

    This pairs an AcousticUnit with its assigned vṛtti type
    and confidence weight. Contains NO semantic information.

    Attributes:
        acoustic_unit: The source AcousticUnit
        vritti_type: The assigned motion quality
        weight: Confidence weight (0.0 to 1.0) based on rule match strength
        rule_trace: Which rule(s) determined this assignment (for debugging)

    Phase 1 Invariants:
        - No meaning field
        - No intent field
        - No emotion field
        - Purely motion-quality descriptors
    """
    acoustic_unit: AcousticUnit
    vritti_type: VrittiType
    weight: float
    rule_trace: str

    def __post_init__(self) -> None:
        """Validate AcousticVritti invariants."""
        if not isinstance(self.acoustic_unit, AcousticUnit):
            raise ValueError("AcousticVritti.acoustic_unit must be AcousticUnit")
        if not isinstance(self.vritti_type, VrittiType):
            raise ValueError("AcousticVritti.vritti_type must be VrittiType")
        if not (0.0 <= self.weight <= 1.0):
            raise ValueError(f"AcousticVritti.weight must be in [0.0, 1.0], got {self.weight}")


# ============================================================================
# VṚTTI ASSIGNMENT RULES (Deterministic)
# ============================================================================

# Sound class to vṛtti mapping (primary rule)
SOUND_CLASS_VRITTI_MAP: Dict[SoundClass, VrittiType] = {
    # Stops release energy suddenly -> ACTIVATION
    SoundClass.STOP: VrittiType.ACTIVATION,

    # Fricatives create turbulent airflow -> TENSION
    SoundClass.FRICATIVE: VrittiType.TENSION,

    # Affricates combine stop + friction -> TENSION (dominant)
    SoundClass.AFFRICATE: VrittiType.TENSION,

    # Nasals sustain through nasal resonance -> INERTIA
    SoundClass.NASAL: VrittiType.INERTIA,

    # Liquids oscillate in articulation -> OSCILLATION
    SoundClass.LIQUID: VrittiType.OSCILLATION,

    # Glides modulate between positions -> OSCILLATION
    SoundClass.GLIDE: VrittiType.OSCILLATION,

    # Vowels release/open -> depends on height (see below)
    SoundClass.VOWEL: VrittiType.RELEASE,

    # Unknown defaults to INERTIA (neutral)
    SoundClass.UNKNOWN: VrittiType.INERTIA,
}

# Vowel height modifiers (refines VOWEL assignments)
VOWEL_HEIGHT_VRITTI_MODIFIER: Dict[VowelHeight, VrittiType] = {
    # Low vowels are most open -> RELEASE
    VowelHeight.LOW: VrittiType.RELEASE,

    # High vowels are more constrained -> TENSION
    VowelHeight.HIGH: VrittiType.TENSION,

    # Mid vowels are neutral -> INERTIA (sustained)
    VowelHeight.MID: VrittiType.INERTIA,

    # Unknown -> default
    VowelHeight.UNKNOWN: VrittiType.RELEASE,
}

# Weight assignments based on rule confidence
WEIGHT_PRIMARY_MATCH = 0.9    # Direct sound class match
WEIGHT_VOWEL_REFINED = 0.85   # Vowel with height refinement
WEIGHT_CLUSTER_MIXED = 0.7    # Mixed consonant-vowel cluster
WEIGHT_DEFAULT = 0.5          # Fallback assignment


# ============================================================================
# CORE MAPPING FUNCTIONS
# ============================================================================


def assign_vritti(unit: AcousticUnit) -> AcousticVritti:
    """
    Assign a vṛtti (motion quality) to a single acoustic unit.

    This is a deterministic, rule-based assignment with NO semantic
    inference. The vṛtti is selected based purely on acoustic properties.

    PHASE 1 INVARIANTS:
        - Deterministic: Same unit always produces same vṛtti
        - No meaning inference: Rules are phonetic only
        - No ontology lookup: Self-contained rules

    Assignment Algorithm:
        1. Get base vṛtti from sound class
        2. If vowel-containing, refine by vowel height
        3. Adjust weight based on cluster structure
        4. Return AcousticVritti with trace

    Args:
        unit: The AcousticUnit to assign vṛtti to

    Returns:
        AcousticVritti with assigned motion quality

    Examples:
        >>> from symbolu.formulas.acoustic_unit_mapper import map_acoustic_units
        >>> units = map_acoustic_units("stop")
        >>> vritti = assign_vritti(units[0])
        >>> isinstance(vritti.vritti_type, VrittiType)
        True
    """
    if not isinstance(unit, AcousticUnit):
        raise TypeError(f"assign_vritti requires AcousticUnit, got {type(unit).__name__}")

    # Step 1: Get base vṛtti from sound class
    base_vritti = SOUND_CLASS_VRITTI_MAP.get(unit.sound_class, VrittiType.INERTIA)
    weight = WEIGHT_PRIMARY_MATCH
    rule_trace = f"sound_class:{unit.sound_class.value}"

    # Step 2: If vowel-containing, refine by vowel height
    if unit.sound_class == SoundClass.VOWEL and unit.vowel_height != VowelHeight.UNKNOWN:
        refined_vritti = VOWEL_HEIGHT_VRITTI_MODIFIER.get(unit.vowel_height, base_vritti)
        base_vritti = refined_vritti
        weight = WEIGHT_VOWEL_REFINED
        rule_trace = f"vowel_height:{unit.vowel_height.value}"

    # Step 3: Handle mixed clusters (both consonant and vowel)
    if unit.consonant_count > 0 and unit.vowel_count > 0:
        # Mixed cluster - weight is lower due to competing influences
        weight = WEIGHT_CLUSTER_MIXED
        rule_trace = f"cluster_mixed:C{unit.consonant_count}V{unit.vowel_count}"

        # For CV clusters, use consonant-dominant vṛtti
        if unit.consonant_count >= unit.vowel_count:
            # Find first consonant and use its vṛtti
            for char in unit.raw_text:
                if char.lower() not in "aeiou":
                    # Re-classify based on consonant
                    consonant_class = _get_consonant_sound_class(char.lower())
                    base_vritti = SOUND_CLASS_VRITTI_MAP.get(consonant_class, base_vritti)
                    rule_trace = f"consonant_dominant:{char.lower()}"
                    break

    # Step 4: Handle pure consonant clusters (no vowel)
    if unit.vowel_count == 0 and unit.consonant_count > 0:
        weight = WEIGHT_PRIMARY_MATCH
        rule_trace = f"consonant_only:{unit.sound_class.value}"

    return AcousticVritti(
        acoustic_unit=unit,
        vritti_type=base_vritti,
        weight=weight,
        rule_trace=rule_trace,
    )


def assign_vritti_sequence(units: List[AcousticUnit]) -> List[AcousticVritti]:
    """
    Assign vṛtti to a sequence of acoustic units.

    This maps assign_vritti over the entire sequence.
    The result maintains the original ordering.

    Args:
        units: List of AcousticUnit to process

    Returns:
        List of AcousticVritti in same order as input
    """
    return [assign_vritti(unit) for unit in units]


def _get_consonant_sound_class(char: str) -> SoundClass:
    """
    Get sound class for a single consonant character.

    Helper for consonant-dominant cluster processing.
    """
    from symbolu.formulas.acoustic_unit_mapper import CONSONANT_CLASS_MAP
    return CONSONANT_CLASS_MAP.get(char, SoundClass.UNKNOWN)


# ============================================================================
# ANALYSIS FUNCTIONS
# ============================================================================


def get_vritti_distribution(vritti_list: List[AcousticVritti]) -> Dict[VrittiType, float]:
    """
    Compute weighted distribution of vṛtti types.

    Returns a dictionary mapping each VrittiType to its
    weighted proportion in the sequence.

    Args:
        vritti_list: List of AcousticVritti assignments

    Returns:
        Dict mapping VrittiType to proportion (0.0 to 1.0)
    """
    if not vritti_list:
        return {vt: 0.0 for vt in VrittiType}

    # Accumulate weighted counts
    weighted_counts: Dict[VrittiType, float] = {vt: 0.0 for vt in VrittiType}
    total_weight = 0.0

    for av in vritti_list:
        weighted_counts[av.vritti_type] += av.weight
        total_weight += av.weight

    # Normalize to proportions
    if total_weight > 0:
        return {vt: count / total_weight for vt, count in weighted_counts.items()}
    else:
        return {vt: 0.0 for vt in VrittiType}


def get_dominant_vritti(vritti_list: List[AcousticVritti]) -> VrittiType:
    """
    Get the dominant (most weighted) vṛtti type.

    Args:
        vritti_list: List of AcousticVritti assignments

    Returns:
        The VrittiType with highest weighted proportion
    """
    dist = get_vritti_distribution(vritti_list)
    return max(dist, key=lambda vt: dist[vt])


def get_vritti_signature(vritti_list: List[AcousticVritti]) -> str:
    """
    Generate a compact vṛtti signature string.

    Format: First letter of each vṛtti type, joined by "-"
    Example: "A-T-R-I" (activation, tension, release, inertia)

    Args:
        vritti_list: List of AcousticVritti assignments

    Returns:
        Compact signature string
    """
    if not vritti_list:
        return ""

    return "-".join(av.vritti_type.value[0].upper() for av in vritti_list)


# ============================================================================
# PUBLIC EXPORTS
# ============================================================================

__all__ = [
    # Primary functions
    "assign_vritti",
    "assign_vritti_sequence",
    # Data classes
    "AcousticVritti",
    # Enums
    "VrittiType",
    # Analysis functions
    "get_vritti_distribution",
    "get_dominant_vritti",
    "get_vritti_signature",
    # Constants
    "PHASE_1_INVARIANTS",
    "SOUND_CLASS_VRITTI_MAP",
    "VOWEL_HEIGHT_VRITTI_MODIFIER",
]
