"""
P22 - Acoustic-Vrtti Witness Extractor Schema Definitions

This phase is witness-only and has zero authority over cognition or delivery.

P22 observes acoustic motion signatures of the user's input without influencing
meaning, intent, regime, discourse, or semantics. It exists to:
    - Acknowledge how sound moves, not what it means
    - Preserve acoustic truth without authority
    - Allow later delivery layers to optionally soften or neutralize expression

P22 MUST NOT:
    - Infer intent
    - Infer emotion
    - Infer meaning
    - Modify regime, discourse, semantics, or lexicon
    - Feed data back into P1-P21
    - Gate, block, or allow anything
    - Change system behavior

P22 MUST:
    - Be deterministic
    - Be read-only
    - Be witness-only
    - Operate after P21
    - Never touch delivery decisions

CRITICAL ARCHITECTURAL INVARIANT:
    P22 is purely observational. It witnesses acoustic motion without authority.
    The witness report is immutable and has no downstream effect on routing.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Literal, Optional


# ============================================================================
# VERSION CONSTANT
# ============================================================================


P22_VERSION = "1.0.0"


# ============================================================================
# ENUMS - Motion Primitive Classification (LOCKED)
# ============================================================================


class MotionPrimitive(str, Enum):
    """
    Closed set of motion primitives for acoustic observation.

    This phase is witness-only and has zero authority over cognition or delivery.

    These are pure motion descriptors based on acoustic/articulatory properties.
    No emotional labels. No kosha names. No semantic tags.

    Attributes:
        INERTIA: Stable, sustained motion - continuants, nasals
        EXPANSION: Outward, releasing motion - sudden onsets, open vowels
        CONTRACTION: Inward, constraining motion - closures, stops
        OSCILLATION: Alternating, modulating motion - liquids, glides
        FRICTION: Turbulent, resistant motion - fricatives, affricates
        NEUTRAL: No significant motion characteristic
    """
    INERTIA = "inertia"
    EXPANSION = "expansion"
    CONTRACTION = "contraction"
    OSCILLATION = "oscillation"
    FRICTION = "friction"
    NEUTRAL = "neutral"


class MotionBalance(str, Enum):
    """
    Classification of overall motion balance in the acoustic signal.

    This phase is witness-only and has zero authority over cognition or delivery.

    Describes the distribution pattern of motion primitives, not emotional state.

    Attributes:
        BALANCED: Even distribution of motion types
        CONSTRICTED: Dominated by contraction/friction
        AGITATED: Dominated by expansion/activation
        OSCILLATORY: Dominated by alternating patterns
    """
    BALANCED = "balanced"
    CONSTRICTED = "constricted"
    AGITATED = "agitated"
    OSCILLATORY = "oscillatory"


# ============================================================================
# DATACLASSES - Witness Report (IMMUTABLE)
# ============================================================================


@dataclass(frozen=True)
class P22AcousticVrittiWitness:
    """
    Immutable witness report of acoustic motion signatures.

    This phase is witness-only and has zero authority over cognition or delivery.

    This dataclass captures the observed acoustic motion properties without
    any interpretation, intent inference, or semantic content.

    Invariants:
        - All fields are read-only (frozen dataclass)
        - witness_only is always True
        - No semantic, intent, or emotion fields
        - Values are deterministic given same input

    Attributes (Observation):
        acoustic_signature: Compact fingerprint (e.g., "VL-SM-VH")
        unit_count: Number of acoustic units observed
        vritti_vector: Normalized motion values (no interpretation)
        dominant_motion: Strongest motion primitive by magnitude
        motion_balance: Overall balance classification
        pressure_band: Coarse magnitude only ("low", "moderate", "high")

    Attributes (Metadata):
        witness_only: Always True - enforces witness-only semantics
        architectural_phase: Identifier for this phase ("P22")
        version: P22 version string for provenance
    """

    # === Observation ===
    acoustic_signature: str
    unit_count: int
    vritti_vector: Dict[str, float]
    dominant_motion: Optional[MotionPrimitive]
    motion_balance: MotionBalance
    pressure_band: Literal["low", "moderate", "high"]

    # === Metadata ===
    witness_only: bool = True
    architectural_phase: str = "P22"
    version: str = P22_VERSION

    def __post_init__(self) -> None:
        """
        Validate P22AcousticVrittiWitness invariants.

        This phase is witness-only and has zero authority over cognition or delivery.
        """
        # Validate witness_only is True
        if not self.witness_only:
            raise ValueError(
                "P22AcousticVrittiWitness.witness_only must be True"
            )

        # Validate unit_count is non-negative
        if not isinstance(self.unit_count, int) or self.unit_count < 0:
            raise ValueError(
                f"P22AcousticVrittiWitness.unit_count must be non-negative int, "
                f"got {self.unit_count}"
            )

        # Validate vritti_vector is dict
        if not isinstance(self.vritti_vector, dict):
            raise ValueError(
                f"P22AcousticVrittiWitness.vritti_vector must be dict, "
                f"got {type(self.vritti_vector).__name__}"
            )

        # Validate vritti_vector values are in [0.0, 1.0]
        for key, value in self.vritti_vector.items():
            if not isinstance(value, (int, float)):
                raise ValueError(
                    f"P22AcousticVrittiWitness.vritti_vector[{key!r}] must be float, "
                    f"got {type(value).__name__}"
                )
            if not (0.0 <= value <= 1.0):
                raise ValueError(
                    f"P22AcousticVrittiWitness.vritti_vector[{key!r}] must be in [0.0, 1.0], "
                    f"got {value}"
                )

        # Validate dominant_motion is MotionPrimitive or None
        if self.dominant_motion is not None and not isinstance(self.dominant_motion, MotionPrimitive):
            raise ValueError(
                f"P22AcousticVrittiWitness.dominant_motion must be MotionPrimitive or None, "
                f"got {type(self.dominant_motion).__name__}"
            )

        # Validate motion_balance is MotionBalance
        if not isinstance(self.motion_balance, MotionBalance):
            raise ValueError(
                f"P22AcousticVrittiWitness.motion_balance must be MotionBalance, "
                f"got {type(self.motion_balance).__name__}"
            )

        # Validate pressure_band
        if self.pressure_band not in ("low", "moderate", "high"):
            raise ValueError(
                f"P22AcousticVrittiWitness.pressure_band must be 'low', 'moderate', or 'high', "
                f"got {self.pressure_band!r}"
            )

    def is_neutral(self) -> bool:
        """Check if witness report indicates neutral acoustic state."""
        return (
            self.dominant_motion == MotionPrimitive.NEUTRAL or
            self.dominant_motion is None
        )

    def is_balanced(self) -> bool:
        """Check if motion is balanced."""
        return self.motion_balance == MotionBalance.BALANCED

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize to dictionary for logging/tracing.

        This phase is witness-only and has zero authority over cognition or delivery.
        """
        return {
            # Observation
            "acoustic_signature": self.acoustic_signature,
            "unit_count": self.unit_count,
            "vritti_vector": dict(self.vritti_vector),
            "dominant_motion": self.dominant_motion.value if self.dominant_motion else None,
            "motion_balance": self.motion_balance.value,
            "pressure_band": self.pressure_band,
            # Metadata
            "witness_only": self.witness_only,
            "architectural_phase": self.architectural_phase,
            "version": self.version,
        }


# ============================================================================
# EXCEPTIONS
# ============================================================================


class P22InvariantViolation(Exception):
    """
    Exception raised when P22 invariants are violated.

    This phase is witness-only and has zero authority over cognition or delivery.

    This is raised when:
        - P22 attempts to read forbidden data (intent, regime, discourse, semantics)
        - P22 attempts to write to ctx outside p22_*
        - P22 output is used for gating or policy
        - Non-determinism is detected
    """

    def __init__(self, message: str, violation_type: str = "UNKNOWN") -> None:
        """
        Initialize the violation exception.

        Args:
            message: Human-readable description of the violation
            violation_type: Category of violation (FORBIDDEN_ACCESS, WRITE_ATTEMPT, etc.)
        """
        super().__init__(message)
        self.violation_type = violation_type
        self.message = message

    def __str__(self) -> str:
        return f"[P22:{self.violation_type}] {self.message}"


# ============================================================================
# FACTORY FUNCTIONS
# ============================================================================


def create_empty_witness() -> P22AcousticVrittiWitness:
    """
    Create an empty/neutral witness report.

    This phase is witness-only and has zero authority over cognition or delivery.

    Used when delivery mode is SUPPRESSED or input is empty.

    Returns:
        P22AcousticVrittiWitness with all neutral values
    """
    return P22AcousticVrittiWitness(
        acoustic_signature="",
        unit_count=0,
        vritti_vector={
            "inertia": 0.0,
            "expansion": 0.0,
            "contraction": 0.0,
            "oscillation": 0.0,
            "friction": 0.0,
            "neutral": 1.0,
        },
        dominant_motion=MotionPrimitive.NEUTRAL,
        motion_balance=MotionBalance.BALANCED,
        pressure_band="low",
    )


# ============================================================================
# PUBLIC EXPORTS
# ============================================================================


__all__ = [
    # Version
    "P22_VERSION",
    # Enums
    "MotionPrimitive",
    "MotionBalance",
    # Dataclasses
    "P22AcousticVrittiWitness",
    # Exceptions
    "P22InvariantViolation",
    # Factory functions
    "create_empty_witness",
]
