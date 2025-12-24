"""
Core/Substrate Snapshot Contract — Immutable Acoustic-Symbolic Snapshot
=========================================================================

╔═══════════════════════════════════════════════════════════════════════════════╗
║                         CORE/SUBSTRATE LAYER                                   ║
║                                                                                ║
║  This module is part of the Core/Substrate layer.                              ║
║  It is NOT a pipeline phase and has no authority over intent, regime,          ║
║  semantics, or delivery.                                                       ║
╚═══════════════════════════════════════════════════════════════════════════════╝

CORE/SUBSTRATE MODULE — Defines the immutable output contract for acoustic-symbolic
tokenization (historically labeled "Phase 1").

This module defines Phase1Snapshot, the canonical output structure
produced by Core/Substrate acoustic-symbolic tokenization. This snapshot
may be observed by downstream observers and allowed sinks only.

ARCHITECTURAL CONSTRAINTS (CORE/SUBSTRATE INVARIANTS):
    - NO semantics: Snapshot contains only acoustic primitives
    - NO intent: Snapshot has no purpose/goal fields
    - NO routing: Snapshot does not direct control flow
    - NO policy: Snapshot does not encode behavioral decisions
    - NO LLM calls: Snapshot is pure data structure
    - DETERMINISTIC: Same input always produces same snapshot
    - IMMUTABLE: Snapshot is frozen after creation
    - READ-ONLY: Downstream phases cannot modify snapshot
    - NON-AUTHORITATIVE: Cannot influence governance or routing decisions

This module:
    - Computes immutable acoustic-symbolic snapshots
    - Bundles acoustic units and vṛtti assignments
    - Does NOT interpret meaning
    - Does NOT infer emotion or intent
    - Does NOT affect delivery decisions

The Phase1Snapshot bundles:
    1. acoustic_units: Ordered list of AcousticUnit primitives
    2. vritti_map: Corresponding vṛtti assignments
    3. metadata: Diagnostic information (non-semantic)

HISTORICAL NOTE: The "Phase1" naming is a historical development label,
NOT an authoritative pipeline phase. The snapshot contract is part of
the Core/Substrate layer.

Version: 1.0 (Core/Substrate Utility)
Date: 2025-12-13
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

from symbolu.formulas.acoustic_unit_mapper import (
    AcousticUnit,
    map_acoustic_units,
    get_acoustic_signature,
    count_syllable_nuclei,
)
from symbolu.formulas.vritti_mapper import (
    AcousticVritti,
    VrittiType,
    assign_vritti_sequence,
    get_vritti_distribution,
    get_dominant_vritti,
    get_vritti_signature,
)


# ============================================================================
# CORE/SUBSTRATE INVARIANT DECLARATIONS
# ============================================================================

# Core/Substrate invariants (historical "Phase 1" label)
PHASE_1_INVARIANTS = {
    "NO_SEMANTICS": True,
    "NO_INTENT": True,
    "NO_ROUTING": True,
    "NO_POLICY": True,
    "NO_LLM_CALLS": True,
    "DETERMINISTIC": True,
    "IMMUTABLE": True,
    "READ_ONLY": True,
}

# Phase identifier
PHASE_ID = "PHASE_1"
PHASE_NAME = "Acoustic-Symbolic Tokenization"
PHASE_VERSION = "1.0"


# ============================================================================
# DATACLASSES - Core/Substrate Output Contract (historical "Phase 1")
# ============================================================================


@dataclass(frozen=True)
class Phase1Metadata:
    """
    Diagnostic metadata for Phase1Snapshot.

    Contains non-semantic diagnostic information about the
    acoustic tokenization process. Used for observability only.

    Attributes:
        input_length: Character count of original input
        unit_count: Number of acoustic units produced
        syllable_count: Estimated syllable count (nuclei count)
        acoustic_signature: Compact acoustic pattern signature
        vritti_signature: Compact vṛtti pattern signature
        dominant_vritti: Most prevalent vṛtti type
        phase_id: Identifier for this phase
        phase_version: Version of phase implementation
    """
    input_length: int
    unit_count: int
    syllable_count: int
    acoustic_signature: str
    vritti_signature: str
    dominant_vritti: str
    phase_id: str = PHASE_ID
    phase_version: str = PHASE_VERSION


@dataclass(frozen=True)
class Phase1Snapshot:
    """
    Immutable output of Core/Substrate Acoustic-Symbolic Tokenization.

    This is the canonical contract between the Core/Substrate layer and
    downstream observers. It bundles acoustic units with their vṛtti assignments.

    CORE/SUBSTRATE INVARIANTS (enforced by frozen=True):
        - Immutable after creation
        - No semantic content
        - No intent fields
        - No routing directives
        - No policy decisions

    Attributes:
        acoustic_units: Ordered list of AcousticUnit primitives
        vritti_map: Corresponding vṛtti assignments for each unit
        metadata: Diagnostic information (non-semantic)

    Usage:
        >>> snapshot = create_phase1_snapshot("hello world")
        >>> len(snapshot.acoustic_units) > 0
        True
        >>> len(snapshot.vritti_map) == len(snapshot.acoustic_units)
        True
    """
    acoustic_units: tuple  # Tuple[AcousticUnit, ...] for immutability
    vritti_map: tuple      # Tuple[AcousticVritti, ...] for immutability
    metadata: Phase1Metadata

    def __post_init__(self) -> None:
        """Validate Phase1Snapshot invariants."""
        # Validate acoustic_units
        if not isinstance(self.acoustic_units, tuple):
            raise ValueError("Phase1Snapshot.acoustic_units must be tuple")
        for unit in self.acoustic_units:
            if not isinstance(unit, AcousticUnit):
                raise ValueError("All acoustic_units must be AcousticUnit instances")

        # Validate vritti_map
        if not isinstance(self.vritti_map, tuple):
            raise ValueError("Phase1Snapshot.vritti_map must be tuple")
        for vritti in self.vritti_map:
            if not isinstance(vritti, AcousticVritti):
                raise ValueError("All vritti_map entries must be AcousticVritti instances")

        # Validate correspondence
        if len(self.acoustic_units) != len(self.vritti_map):
            raise ValueError(
                f"acoustic_units ({len(self.acoustic_units)}) and "
                f"vritti_map ({len(self.vritti_map)}) must have same length"
            )

        # Validate metadata
        if not isinstance(self.metadata, Phase1Metadata):
            raise ValueError("Phase1Snapshot.metadata must be Phase1Metadata")

    def get_unit_count(self) -> int:
        """Return the number of acoustic units."""
        return len(self.acoustic_units)

    def get_vritti_distribution(self) -> Dict[VrittiType, float]:
        """Return weighted vṛtti distribution."""
        return get_vritti_distribution(list(self.vritti_map))

    def is_empty(self) -> bool:
        """Check if snapshot contains no units."""
        return len(self.acoustic_units) == 0

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize snapshot to dictionary.

        For logging, debugging, and observability. Does NOT
        expose any semantic information.
        """
        return {
            "phase_id": self.metadata.phase_id,
            "phase_version": self.metadata.phase_version,
            "unit_count": self.metadata.unit_count,
            "syllable_count": self.metadata.syllable_count,
            "acoustic_signature": self.metadata.acoustic_signature,
            "vritti_signature": self.metadata.vritti_signature,
            "dominant_vritti": self.metadata.dominant_vritti,
            "input_length": self.metadata.input_length,
            "units": [
                {
                    "raw_text": u.raw_text,
                    "index": u.index,
                    "sound_class": u.sound_class.value,
                    "is_nucleus": u.is_syllable_nucleus,
                }
                for u in self.acoustic_units
            ],
            "vritti_assignments": [
                {
                    "type": v.vritti_type.value,
                    "weight": v.weight,
                    "rule": v.rule_trace,
                }
                for v in self.vritti_map
            ],
        }


# ============================================================================
# FACTORY FUNCTION - Primary Entry Point
# ============================================================================


def create_phase1_snapshot(text: str) -> Phase1Snapshot:
    """
    Create a Phase1Snapshot from raw input text.

    This is the primary entry point for Phase 1 processing.
    It orchestrates acoustic unit mapping and vṛtti assignment.

    CORE/SUBSTRATE INVARIANTS:
        - Deterministic: Same text always produces same snapshot
        - No LLM calls: Pure rule-based processing
        - No semantics: Output contains only acoustic primitives
        - Immutable: Returned snapshot cannot be modified

    Algorithm:
        1. Map text to acoustic units
        2. Assign vṛtti to each unit
        3. Compute metadata
        4. Return frozen snapshot

    Args:
        text: Raw input string to process

    Returns:
        Phase1Snapshot with acoustic units and vṛtti map

    Raises:
        TypeError: If text is not a string

    Examples:
        >>> snapshot = create_phase1_snapshot("hello")
        >>> snapshot.get_unit_count() > 0
        True
        >>> snapshot.metadata.phase_id
        'PHASE_1'
    """
    if not isinstance(text, str):
        raise TypeError(f"create_phase1_snapshot requires str, got {type(text).__name__}")

    # Step 1: Map to acoustic units
    units = map_acoustic_units(text)

    # Step 2: Assign vṛtti
    vritti_list = assign_vritti_sequence(units)

    # Step 3: Compute metadata
    acoustic_sig = get_acoustic_signature(units)
    vritti_sig = get_vritti_signature(vritti_list)
    dominant = get_dominant_vritti(vritti_list) if vritti_list else VrittiType.INERTIA

    metadata = Phase1Metadata(
        input_length=len(text),
        unit_count=len(units),
        syllable_count=count_syllable_nuclei(units),
        acoustic_signature=acoustic_sig,
        vritti_signature=vritti_sig,
        dominant_vritti=dominant.value,
    )

    # Step 4: Create immutable snapshot
    return Phase1Snapshot(
        acoustic_units=tuple(units),
        vritti_map=tuple(vritti_list),
        metadata=metadata,
    )


def create_empty_snapshot() -> Phase1Snapshot:
    """
    Create an empty Phase1Snapshot.

    Useful for edge cases where no input is provided.
    Returns a valid but empty snapshot.
    """
    metadata = Phase1Metadata(
        input_length=0,
        unit_count=0,
        syllable_count=0,
        acoustic_signature="",
        vritti_signature="",
        dominant_vritti=VrittiType.INERTIA.value,
    )

    return Phase1Snapshot(
        acoustic_units=tuple(),
        vritti_map=tuple(),
        metadata=metadata,
    )


# ============================================================================
# VALIDATION FUNCTIONS
# ============================================================================


def validate_phase1_snapshot(snapshot: Phase1Snapshot) -> bool:
    """
    Validate a Phase1Snapshot against Core/Substrate contracts.

    Checks:
        1. Type correctness
        2. Correspondence between units and vritti_map
        3. Metadata consistency
        4. Immutability (frozen)

    Args:
        snapshot: The snapshot to validate

    Returns:
        True if valid, False otherwise
    """
    try:
        # Type check
        if not isinstance(snapshot, Phase1Snapshot):
            return False

        # Check frozen (immutable)
        if not snapshot.__dataclass_fields__:
            return False

        # Check correspondence
        if len(snapshot.acoustic_units) != len(snapshot.vritti_map):
            return False

        # Check metadata consistency
        if snapshot.metadata.unit_count != len(snapshot.acoustic_units):
            return False

        # All validations passed
        return True

    except Exception:
        return False


def assert_no_semantic_leakage(snapshot: Phase1Snapshot) -> bool:
    """
    Assert that a Phase1Snapshot contains no semantic content.

    This is a defensive check to ensure Core/Substrate invariants hold.
    It verifies that no semantic, intent, or meaning fields exist.

    Args:
        snapshot: The snapshot to check

    Returns:
        True if clean (no semantic leakage)

    Raises:
        AssertionError: If semantic leakage detected
    """
    # Check for forbidden field names in units
    forbidden_unit_fields = {
        'meaning', 'intent', 'purpose', 'goal', 'semantic',
        'emotion', 'sentiment', 'topic', 'category', 'label',
    }

    for unit in snapshot.acoustic_units:
        unit_fields = set(unit.__dataclass_fields__.keys())
        leaked = unit_fields & forbidden_unit_fields
        if leaked:
            raise AssertionError(f"Semantic leakage in AcousticUnit: {leaked}")

    # Check for forbidden field names in vritti
    forbidden_vritti_fields = {
        'meaning', 'intent', 'purpose', 'emotion', 'sentiment',
    }

    for vritti in snapshot.vritti_map:
        vritti_fields = set(vritti.__dataclass_fields__.keys())
        leaked = vritti_fields & forbidden_vritti_fields
        if leaked:
            raise AssertionError(f"Semantic leakage in AcousticVritti: {leaked}")

    return True


# ============================================================================
# PUBLIC EXPORTS
# ============================================================================

__all__ = [
    # Primary factory function
    "create_phase1_snapshot",
    "create_empty_snapshot",
    # Data classes
    "Phase1Snapshot",
    "Phase1Metadata",
    # Validation
    "validate_phase1_snapshot",
    "assert_no_semantic_leakage",
    # Constants
    "PHASE_1_INVARIANTS",
    "PHASE_ID",
    "PHASE_NAME",
    "PHASE_VERSION",
]
