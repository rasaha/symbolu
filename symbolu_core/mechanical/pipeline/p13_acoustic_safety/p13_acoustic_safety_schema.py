"""
P13 - Acoustic Safety Envelope Schema Definitions

P13 defines the ABSOLUTE SAFETY BOUNDS for acoustic expression.
It is the last safety lock before any acoustic realization.

P13's responsibility is to:
- Define hard upper and lower bounds on acoustic expressiveness
- Prevent emotion amplification
- Prevent authority signaling (certainty, dominance, persuasion)
- Prevent prosodic manipulation
- Guarantee downstream renderers cannot exceed intent

P13 does NOT:
- Generate sound
- Modify P10 parameters
- Interpret prosody
- Infer emotion
- Execute actions
- Call LLMs
- Introduce probabilistic behavior

P13 only CAPS, CONSTRAINS, and VETOES downstream acoustic realization.
P13 is BINDING. Lower phases cannot override it.

Design Principles:
- Deterministic: No LLM calls, no probabilistic sampling
- Safety-First: BLOCKED is always safe
- Authority-Respecting: Cannot override PO1-P12 constraints
- Capping-Only: May only reduce or clamp, never amplify
- Binding: Downstream renderers must respect envelope

Authority Model:
- Authority flows: PO1 -> ... -> P10 -> P11 -> P12 -> P13 -> (Renderers)
- P13 receives signals from P10, P11, P12, P6, P7
- P13 cannot amplify or expand acoustic expressiveness
- P13 produces AcousticSafetyEnvelope (read-only, binding)

CRITICAL ARCHITECTURAL INVARIANT:
    P13 is the last safety lock before sound.
    Phase 1 (acoustic tokenization) must consume P13 verbatim.
    Renderers violating P13 are considered unsafe by design.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Tuple


# ============================================================================
# VERSION CONSTANT
# ============================================================================


P13_VERSION = "1.0.0"


# ============================================================================
# ENUMS - Risk and violation classification
# ============================================================================


class AcousticRiskLevel(str, Enum):
    """
    Risk level classification for acoustic safety.

    SAFE: All safety constraints satisfied, expression is permitted
    CAUTION: Some concerns detected, expression allowed but limited
    BLOCKED: Safety constraints violated, expression must be minimal/flat

    BLOCKED is always safe.
    Risk level may only restrict, never expand capability.
    """
    SAFE = "SAFE"
    CAUTION = "CAUTION"
    BLOCKED = "BLOCKED"


class SafetyViolation(str, Enum):
    """
    Classification of safety violations detected by P13.

    EMOTION_AMPLIFICATION: Attempt to amplify emotional expression
    CERTAINTY_ESCALATION: Attempt to signal unwarranted certainty
    AUTHORITY_SIGNALING: Attempt to signal dominance or authority
    EXCESSIVE_VARIANCE: Parameters vary beyond safe bounds
    PROSODIC_MANIPULATION: Attempt to manipulate through prosody
    """
    EMOTION_AMPLIFICATION = "EMOTION_AMPLIFICATION"
    CERTAINTY_ESCALATION = "CERTAINTY_ESCALATION"
    AUTHORITY_SIGNALING = "AUTHORITY_SIGNALING"
    EXCESSIVE_VARIANCE = "EXCESSIVE_VARIANCE"
    PROSODIC_MANIPULATION = "PROSODIC_MANIPULATION"


# ============================================================================
# HARD SAFETY BOUNDS - These are absolute limits
# ============================================================================


# Absolute pitch bounds (Hz) - never exceed
ABSOLUTE_PITCH_MIN = 90
ABSOLUTE_PITCH_MAX = 140

# Absolute energy bounds (0.0 - 1.0 normalized) - never exceed
ABSOLUTE_ENERGY_MIN = 0.2
ABSOLUTE_ENERGY_MAX = 0.6

# Absolute variance bounds - pitch variance in Hz
ABSOLUTE_VARIANCE_MIN = 0
ABSOLUTE_VARIANCE_MAX = 30

# HOLD regime bounds - most restrictive
HOLD_PITCH_MIN = 90
HOLD_PITCH_MAX = 110
HOLD_ENERGY_MIN = 0.2
HOLD_ENERGY_MAX = 0.35
HOLD_VARIANCE_MAX = 10

# DE_ESCALATE/STABILIZE regime bounds
DE_ESCALATE_PITCH_MIN = 90
DE_ESCALATE_PITCH_MAX = 125
DE_ESCALATE_ENERGY_MIN = 0.2
DE_ESCALATE_ENERGY_MAX = 0.40
DE_ESCALATE_VARIANCE_MAX = 20

# REFLEXIVE grounding bounds
REFLEXIVE_ENERGY_MAX = 0.40
REFLEXIVE_VARIANCE_MAX = 20


# ============================================================================
# DATACLASSES - Core envelope object
# ============================================================================


@dataclass(frozen=True)
class AcousticSafetyEnvelope:
    """
    P13 output envelope: Acoustic safety bounds.

    This envelope is read-only and captures the absolute safety bounds
    for acoustic expression. It is BINDING on all downstream renderers.

    All bounds represent the MAXIMUM allowed expression. Renderers may
    produce output at or below these bounds, never above.

    Invariants:
    - HOLD regime -> all expressive flags False
    - DE_ESCALATE/STABILIZE -> allow_emphasis False, allow_pitch_contours False
    - No envelope may increase intensity beyond P10
    - Empty violations => risk_level SAFE
    - Non-empty violations + risk_level SAFE is invalid

    Attributes (Acoustic Bounds - Maximum Allowed):
        allowed_pitch_range: (min_hz, max_hz) - absolute pitch bounds
        allowed_energy_range: (min, max) - normalized energy bounds
        allowed_variance_range: (min, max) - pitch variance bounds in Hz

    Attributes (Expression Flags - What is Permitted):
        allow_emphasis: Whether emphasis/stress is permitted
        allow_pitch_contours: Whether pitch contours (rise/fall) are permitted
        allow_rhythm_variation: Whether rhythm variation is permitted
        allow_intonation_shift: Whether intonation shifts are permitted

    Attributes (Safety Status):
        risk_level: Current risk classification (SAFE/CAUTION/BLOCKED)
        violations: Tuple of detected safety violations

    Attributes (Provenance):
        source_regime: The operational regime from P6 (for tracing)
        source_discourse_act: The discourse act from P7 (for tracing)
        source_p10_version: Static P10 version string for provenance
        source_p12_consistent: Whether P12 reported consistency

    Attributes (Metadata):
        architectural_phase: Identifier for this phase ("P13")
        version: P13 version string for provenance
        timestamp_utc: ISO-8601 timestamp for audit purposes
        debug: Additional debug/trace information
    """

    # === Acoustic Bounds (Maximum Allowed) ===
    allowed_pitch_range: Tuple[int, int]
    allowed_energy_range: Tuple[float, float]
    allowed_variance_range: Tuple[int, int]

    # === Expression Flags (What is Permitted) ===
    allow_emphasis: bool
    allow_pitch_contours: bool
    allow_rhythm_variation: bool
    allow_intonation_shift: bool

    # === Safety Status ===
    risk_level: AcousticRiskLevel
    violations: Tuple[SafetyViolation, ...]

    # === Provenance ===
    source_regime: str
    source_discourse_act: str
    source_p10_version: str
    source_p12_consistent: bool

    # === Metadata ===
    architectural_phase: str = "P13"
    version: str = P13_VERSION
    timestamp_utc: str = ""
    debug: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate AcousticSafetyEnvelope invariants and bounds."""
        # Validate risk_level is valid enum
        if not isinstance(self.risk_level, AcousticRiskLevel):
            raise ValueError(
                f"AcousticSafetyEnvelope.risk_level must be AcousticRiskLevel, "
                f"got {type(self.risk_level).__name__}"
            )

        # Validate violations is a tuple
        if not isinstance(self.violations, tuple):
            raise ValueError(
                f"AcousticSafetyEnvelope.violations must be tuple, "
                f"got {type(self.violations).__name__}"
            )

        # Validate each violation is a valid enum
        for i, violation in enumerate(self.violations):
            if not isinstance(violation, SafetyViolation):
                raise ValueError(
                    f"AcousticSafetyEnvelope.violations[{i}] must be SafetyViolation, "
                    f"got {type(violation).__name__}"
                )

        # INVARIANT: Empty violations => risk_level SAFE
        # (violations imply non-SAFE risk level)
        if len(self.violations) > 0 and self.risk_level == AcousticRiskLevel.SAFE:
            raise ValueError(
                "AcousticSafetyEnvelope: violations detected but risk_level is SAFE"
            )

        # Validate allowed_pitch_range
        if not isinstance(self.allowed_pitch_range, tuple) or len(self.allowed_pitch_range) != 2:
            raise ValueError(
                f"AcousticSafetyEnvelope.allowed_pitch_range must be a 2-tuple, "
                f"got {type(self.allowed_pitch_range).__name__}"
            )
        pitch_low, pitch_high = self.allowed_pitch_range
        if not isinstance(pitch_low, int) or not isinstance(pitch_high, int):
            raise ValueError(
                "AcousticSafetyEnvelope.allowed_pitch_range values must be int"
            )
        if not (ABSOLUTE_PITCH_MIN <= pitch_low <= ABSOLUTE_PITCH_MAX):
            raise ValueError(
                f"AcousticSafetyEnvelope.allowed_pitch_range[0] must be in "
                f"[{ABSOLUTE_PITCH_MIN}, {ABSOLUTE_PITCH_MAX}], got {pitch_low}"
            )
        if not (ABSOLUTE_PITCH_MIN <= pitch_high <= ABSOLUTE_PITCH_MAX):
            raise ValueError(
                f"AcousticSafetyEnvelope.allowed_pitch_range[1] must be in "
                f"[{ABSOLUTE_PITCH_MIN}, {ABSOLUTE_PITCH_MAX}], got {pitch_high}"
            )
        if pitch_low > pitch_high:
            raise ValueError(
                f"AcousticSafetyEnvelope.allowed_pitch_range[0] must be <= [1], "
                f"got ({pitch_low}, {pitch_high})"
            )

        # Validate allowed_energy_range
        if not isinstance(self.allowed_energy_range, tuple) or len(self.allowed_energy_range) != 2:
            raise ValueError(
                f"AcousticSafetyEnvelope.allowed_energy_range must be a 2-tuple, "
                f"got {type(self.allowed_energy_range).__name__}"
            )
        energy_low, energy_high = self.allowed_energy_range
        if not isinstance(energy_low, (int, float)) or not isinstance(energy_high, (int, float)):
            raise ValueError(
                "AcousticSafetyEnvelope.allowed_energy_range values must be numeric"
            )
        if not (ABSOLUTE_ENERGY_MIN <= energy_low <= ABSOLUTE_ENERGY_MAX):
            raise ValueError(
                f"AcousticSafetyEnvelope.allowed_energy_range[0] must be in "
                f"[{ABSOLUTE_ENERGY_MIN}, {ABSOLUTE_ENERGY_MAX}], got {energy_low}"
            )
        if not (ABSOLUTE_ENERGY_MIN <= energy_high <= ABSOLUTE_ENERGY_MAX):
            raise ValueError(
                f"AcousticSafetyEnvelope.allowed_energy_range[1] must be in "
                f"[{ABSOLUTE_ENERGY_MIN}, {ABSOLUTE_ENERGY_MAX}], got {energy_high}"
            )
        if energy_low > energy_high:
            raise ValueError(
                f"AcousticSafetyEnvelope.allowed_energy_range[0] must be <= [1], "
                f"got ({energy_low}, {energy_high})"
            )

        # Validate allowed_variance_range
        if not isinstance(self.allowed_variance_range, tuple) or len(self.allowed_variance_range) != 2:
            raise ValueError(
                f"AcousticSafetyEnvelope.allowed_variance_range must be a 2-tuple, "
                f"got {type(self.allowed_variance_range).__name__}"
            )
        var_low, var_high = self.allowed_variance_range
        if not isinstance(var_low, int) or not isinstance(var_high, int):
            raise ValueError(
                "AcousticSafetyEnvelope.allowed_variance_range values must be int"
            )
        if not (ABSOLUTE_VARIANCE_MIN <= var_low <= ABSOLUTE_VARIANCE_MAX):
            raise ValueError(
                f"AcousticSafetyEnvelope.allowed_variance_range[0] must be in "
                f"[{ABSOLUTE_VARIANCE_MIN}, {ABSOLUTE_VARIANCE_MAX}], got {var_low}"
            )
        if not (ABSOLUTE_VARIANCE_MIN <= var_high <= ABSOLUTE_VARIANCE_MAX):
            raise ValueError(
                f"AcousticSafetyEnvelope.allowed_variance_range[1] must be in "
                f"[{ABSOLUTE_VARIANCE_MIN}, {ABSOLUTE_VARIANCE_MAX}], got {var_high}"
            )
        if var_low > var_high:
            raise ValueError(
                f"AcousticSafetyEnvelope.allowed_variance_range[0] must be <= [1], "
                f"got ({var_low}, {var_high})"
            )

        # Validate boolean flags
        for attr_name in (
            'allow_emphasis', 'allow_pitch_contours',
            'allow_rhythm_variation', 'allow_intonation_shift'
        ):
            value = getattr(self, attr_name)
            if not isinstance(value, bool):
                raise ValueError(
                    f"AcousticSafetyEnvelope.{attr_name} must be bool, "
                    f"got {type(value).__name__}"
                )

        # Validate source strings
        if not isinstance(self.source_regime, str) or not self.source_regime.strip():
            raise ValueError(
                "AcousticSafetyEnvelope.source_regime must be a non-empty string"
            )
        if not isinstance(self.source_discourse_act, str) or not self.source_discourse_act.strip():
            raise ValueError(
                "AcousticSafetyEnvelope.source_discourse_act must be a non-empty string"
            )
        if not isinstance(self.source_p10_version, str) or not self.source_p10_version.strip():
            raise ValueError(
                "AcousticSafetyEnvelope.source_p10_version must be a non-empty string"
            )

        # Validate source_p12_consistent is bool
        if not isinstance(self.source_p12_consistent, bool):
            raise ValueError(
                f"AcousticSafetyEnvelope.source_p12_consistent must be bool, "
                f"got {type(self.source_p12_consistent).__name__}"
            )

        # INVARIANT: HOLD regime -> all expressive flags False
        if self.source_regime == "HOLD":
            if self.allow_emphasis or self.allow_pitch_contours:
                raise ValueError(
                    "AcousticSafetyEnvelope: HOLD regime requires "
                    "allow_emphasis=False and allow_pitch_contours=False"
                )
            if self.allow_rhythm_variation or self.allow_intonation_shift:
                raise ValueError(
                    "AcousticSafetyEnvelope: HOLD regime requires "
                    "allow_rhythm_variation=False and allow_intonation_shift=False"
                )

        # INVARIANT: DE_ESCALATE/STABILIZE -> emphasis False, contours False
        if self.source_regime in ("DE_ESCALATE", "STABILIZE"):
            if self.allow_emphasis or self.allow_pitch_contours:
                raise ValueError(
                    f"AcousticSafetyEnvelope: {self.source_regime} regime requires "
                    "allow_emphasis=False and allow_pitch_contours=False"
                )

    def is_safe(self) -> bool:
        """Check if risk level is SAFE."""
        return self.risk_level == AcousticRiskLevel.SAFE

    def is_caution(self) -> bool:
        """Check if risk level is CAUTION."""
        return self.risk_level == AcousticRiskLevel.CAUTION

    def is_blocked(self) -> bool:
        """Check if risk level is BLOCKED."""
        return self.risk_level == AcousticRiskLevel.BLOCKED

    def has_violations(self) -> bool:
        """Check if any safety violations were detected."""
        return len(self.violations) > 0

    def has_violation(self, violation: SafetyViolation) -> bool:
        """Check if a specific violation type was detected."""
        return violation in self.violations

    def is_fully_restricted(self) -> bool:
        """Check if all expressive flags are False."""
        return (
            not self.allow_emphasis and
            not self.allow_pitch_contours and
            not self.allow_rhythm_variation and
            not self.allow_intonation_shift
        )

    def get_pitch_variance_limit(self) -> int:
        """Get the maximum allowed pitch variance in Hz."""
        return self.allowed_variance_range[1]

    def get_max_energy(self) -> float:
        """Get the maximum allowed energy level."""
        return self.allowed_energy_range[1]

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for logging/tracing."""
        return {
            # Acoustic bounds
            "allowed_pitch_range": list(self.allowed_pitch_range),
            "allowed_energy_range": list(self.allowed_energy_range),
            "allowed_variance_range": list(self.allowed_variance_range),
            # Expression flags
            "allow_emphasis": self.allow_emphasis,
            "allow_pitch_contours": self.allow_pitch_contours,
            "allow_rhythm_variation": self.allow_rhythm_variation,
            "allow_intonation_shift": self.allow_intonation_shift,
            # Safety status
            "risk_level": self.risk_level.value,
            "violations": [v.value for v in self.violations],
            # Provenance
            "source_regime": self.source_regime,
            "source_discourse_act": self.source_discourse_act,
            "source_p10_version": self.source_p10_version,
            "source_p12_consistent": self.source_p12_consistent,
            # Metadata
            "architectural_phase": self.architectural_phase,
            "version": self.version,
            "timestamp_utc": self.timestamp_utc,
            "debug": self.debug,
            # Computed
            "is_safe": self.is_safe(),
            "is_caution": self.is_caution(),
            "is_blocked": self.is_blocked(),
            "is_fully_restricted": self.is_fully_restricted(),
            "has_violations": self.has_violations(),
        }


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def clamp_pitch_to_absolute(value: int) -> int:
    """Clamp pitch value to absolute safety bounds."""
    return max(ABSOLUTE_PITCH_MIN, min(ABSOLUTE_PITCH_MAX, value))


def clamp_energy_to_absolute(value: float) -> float:
    """Clamp energy value to absolute safety bounds."""
    return max(ABSOLUTE_ENERGY_MIN, min(ABSOLUTE_ENERGY_MAX, value))


def clamp_variance_to_absolute(value: int) -> int:
    """Clamp variance value to absolute safety bounds."""
    return max(ABSOLUTE_VARIANCE_MIN, min(ABSOLUTE_VARIANCE_MAX, value))


def get_blocked_envelope(
    source_regime: str = "HOLD",
    source_discourse_act: str = "DEFERRAL",
    source_p10_version: str = "P10-unknown",
    source_p12_consistent: bool = False,
    violations: Tuple[SafetyViolation, ...] = (),
    timestamp_utc: str = "",
) -> AcousticSafetyEnvelope:
    """
    Create a BLOCKED safety envelope with most restrictive bounds.

    This is the safest possible envelope and is used when:
    - HOLD regime is active
    - Critical safety violations are detected
    - Upstream phases report inconsistency
    """
    return AcousticSafetyEnvelope(
        allowed_pitch_range=(HOLD_PITCH_MIN, HOLD_PITCH_MAX),
        allowed_energy_range=(HOLD_ENERGY_MIN, HOLD_ENERGY_MAX),
        allowed_variance_range=(0, HOLD_VARIANCE_MAX),
        allow_emphasis=False,
        allow_pitch_contours=False,
        allow_rhythm_variation=False,
        allow_intonation_shift=False,
        risk_level=AcousticRiskLevel.BLOCKED,
        violations=violations if violations else (),
        source_regime=source_regime,
        source_discourse_act=source_discourse_act,
        source_p10_version=source_p10_version,
        source_p12_consistent=source_p12_consistent,
        timestamp_utc=timestamp_utc,
    )


# Public exports
__all__ = [
    # Enums
    "AcousticRiskLevel",
    "SafetyViolation",
    # Dataclasses
    "AcousticSafetyEnvelope",
    # Constants - absolute bounds
    "ABSOLUTE_PITCH_MIN",
    "ABSOLUTE_PITCH_MAX",
    "ABSOLUTE_ENERGY_MIN",
    "ABSOLUTE_ENERGY_MAX",
    "ABSOLUTE_VARIANCE_MIN",
    "ABSOLUTE_VARIANCE_MAX",
    # Constants - regime-specific bounds
    "HOLD_PITCH_MIN",
    "HOLD_PITCH_MAX",
    "HOLD_ENERGY_MIN",
    "HOLD_ENERGY_MAX",
    "HOLD_VARIANCE_MAX",
    "DE_ESCALATE_PITCH_MIN",
    "DE_ESCALATE_PITCH_MAX",
    "DE_ESCALATE_ENERGY_MIN",
    "DE_ESCALATE_ENERGY_MAX",
    "DE_ESCALATE_VARIANCE_MAX",
    "REFLEXIVE_ENERGY_MAX",
    "REFLEXIVE_VARIANCE_MAX",
    # Constants - version
    "P13_VERSION",
    # Helper functions
    "clamp_pitch_to_absolute",
    "clamp_energy_to_absolute",
    "clamp_variance_to_absolute",
    "get_blocked_envelope",
]
