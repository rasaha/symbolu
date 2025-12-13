"""
Renderer Contract Schema Definitions

This module defines the contract between Symbol-U's acoustic pipeline and
any downstream renderer. Renderers are external systems that MUST NOT be trusted.

The RendererInputContract is the complete, immutable specification that
renderers receive. It includes:
- LexicalFrame (P9): The selected words
- AcousticParameterFrame (P10): Acoustic constraints
- ProsodicEvidenceFrame (P11): Prosodic witness attestation
- P12ConsistencyReport (P12): Consistency validation results
- AcousticSafetyEnvelope (P13): BINDING safety bounds

CRITICAL ARCHITECTURAL INVARIANT:
    Renderers may ONLY read these values.
    Renderers may NOT invent new values.
    Renderers violating P13 are unsafe BY DEFINITION.

Authority Model:
    Symbol-U Pipeline -> RendererInputContract -> Renderer
    The contract is AUTHORITATIVE, NON-NEGOTIABLE, and FINAL.
    Renderers have NO authority to modify, reinterpret, or expand.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional, Tuple


# ============================================================================
# VERSION CONSTANT
# ============================================================================


RENDERER_CONTRACT_VERSION = "1.0.0"


# ============================================================================
# ENUMS
# ============================================================================


class RenderIntentCategory(str, Enum):
    """
    Category of acoustic render intent.

    Describes what the renderer intends to do acoustically.
    """
    COMPLIANT = "COMPLIANT"           # Within all bounds
    AMPLIFIED = "AMPLIFIED"           # Exceeds bounds
    AUTHORITATIVE = "AUTHORITATIVE"   # Authority signaling
    EMOTIVE = "EMOTIVE"               # Emotional amplification
    IGNORED = "IGNORED"               # Safety envelope ignored
    BOUNDARY = "BOUNDARY"             # At or near boundaries


class ComplianceVerdict(str, Enum):
    """
    Verdict from compliance checking.

    PASS: Render intent complies with P13 envelope
    FAIL: Render intent violates P13 envelope
    """
    PASS = "PASS"
    FAIL = "FAIL"


class ViolationCategory(str, Enum):
    """
    Category of compliance violation.

    Maps directly to P13 SafetyViolation types.
    """
    EMOTION_AMPLIFICATION = "EMOTION_AMPLIFICATION"
    CERTAINTY_ESCALATION = "CERTAINTY_ESCALATION"
    AUTHORITY_SIGNALING = "AUTHORITY_SIGNALING"
    EXCESSIVE_VARIANCE = "EXCESSIVE_VARIANCE"
    PROSODIC_MANIPULATION = "PROSODIC_MANIPULATION"
    ENVELOPE_BREACH = "ENVELOPE_BREACH"           # Generic P13 breach
    BLOCKED_OVERRIDE = "BLOCKED_OVERRIDE"         # Attempted render under BLOCKED
    HOLD_OVERRIDE = "HOLD_OVERRIDE"               # Attempted render under HOLD
    EMPHASIS_VIOLATION = "EMPHASIS_VIOLATION"     # Emphasis when prohibited
    PITCH_BOUND_VIOLATION = "PITCH_BOUND_VIOLATION"
    ENERGY_BOUND_VIOLATION = "ENERGY_BOUND_VIOLATION"
    VARIANCE_BOUND_VIOLATION = "VARIANCE_BOUND_VIOLATION"
    CONTOUR_VIOLATION = "CONTOUR_VIOLATION"       # Contours when prohibited
    RHYTHM_VIOLATION = "RHYTHM_VIOLATION"         # Rhythm variation when prohibited
    INTONATION_VIOLATION = "INTONATION_VIOLATION" # Intonation shift when prohibited


# ============================================================================
# DATACLASSES - Render Intent Objects
# ============================================================================


@dataclass(frozen=True)
class AcousticRenderIntent:
    """
    Describes what a renderer INTENDS to produce acoustically.

    This is NOT audio - it is a declaration of intent that can be
    validated against the P13 AcousticSafetyEnvelope BEFORE any
    sound is generated.

    Renderers output this object, and the RendererComplianceChecker
    validates it against P13 constraints.

    Attributes (Pitch Intent):
        intended_pitch_min: Minimum pitch renderer will use (Hz)
        intended_pitch_max: Maximum pitch renderer will use (Hz)
        intended_pitch_variance: Maximum pitch variance (Hz)

    Attributes (Energy Intent):
        intended_energy_min: Minimum energy level (0.0-1.0)
        intended_energy_max: Maximum energy level (0.0-1.0)

    Attributes (Expression Intent):
        will_use_emphasis: Whether renderer will add emphasis
        will_use_pitch_contours: Whether renderer will add pitch contours
        will_use_rhythm_variation: Whether renderer will vary rhythm
        will_use_intonation_shift: Whether renderer will shift intonation

    Attributes (Stress Intent):
        intended_stressed_tokens: Number of tokens to stress

    Attributes (Metadata):
        renderer_id: Identifier of the renderer
        intent_category: Category of this intent
        debug: Additional debug information
    """

    # === Pitch Intent ===
    intended_pitch_min: int
    intended_pitch_max: int
    intended_pitch_variance: int

    # === Energy Intent ===
    intended_energy_min: float
    intended_energy_max: float

    # === Expression Intent ===
    will_use_emphasis: bool
    will_use_pitch_contours: bool
    will_use_rhythm_variation: bool
    will_use_intonation_shift: bool

    # === Stress Intent ===
    intended_stressed_tokens: int

    # === Metadata ===
    renderer_id: str
    intent_category: RenderIntentCategory
    debug: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate AcousticRenderIntent fields."""
        # Validate pitch values are integers
        if not isinstance(self.intended_pitch_min, int):
            raise ValueError(
                f"AcousticRenderIntent.intended_pitch_min must be int, "
                f"got {type(self.intended_pitch_min).__name__}"
            )
        if not isinstance(self.intended_pitch_max, int):
            raise ValueError(
                f"AcousticRenderIntent.intended_pitch_max must be int, "
                f"got {type(self.intended_pitch_max).__name__}"
            )
        if not isinstance(self.intended_pitch_variance, int):
            raise ValueError(
                f"AcousticRenderIntent.intended_pitch_variance must be int, "
                f"got {type(self.intended_pitch_variance).__name__}"
            )

        # Validate pitch ordering
        if self.intended_pitch_min > self.intended_pitch_max:
            raise ValueError(
                f"AcousticRenderIntent.intended_pitch_min ({self.intended_pitch_min}) "
                f"must be <= intended_pitch_max ({self.intended_pitch_max})"
            )

        # Validate pitch variance is non-negative
        if self.intended_pitch_variance < 0:
            raise ValueError(
                f"AcousticRenderIntent.intended_pitch_variance must be >= 0, "
                f"got {self.intended_pitch_variance}"
            )

        # Validate energy values are numeric
        if not isinstance(self.intended_energy_min, (int, float)):
            raise ValueError(
                f"AcousticRenderIntent.intended_energy_min must be numeric, "
                f"got {type(self.intended_energy_min).__name__}"
            )
        if not isinstance(self.intended_energy_max, (int, float)):
            raise ValueError(
                f"AcousticRenderIntent.intended_energy_max must be numeric, "
                f"got {type(self.intended_energy_max).__name__}"
            )

        # Validate energy ordering
        if self.intended_energy_min > self.intended_energy_max:
            raise ValueError(
                f"AcousticRenderIntent.intended_energy_min ({self.intended_energy_min}) "
                f"must be <= intended_energy_max ({self.intended_energy_max})"
            )

        # Validate boolean flags
        for attr_name in (
            'will_use_emphasis', 'will_use_pitch_contours',
            'will_use_rhythm_variation', 'will_use_intonation_shift'
        ):
            value = getattr(self, attr_name)
            if not isinstance(value, bool):
                raise ValueError(
                    f"AcousticRenderIntent.{attr_name} must be bool, "
                    f"got {type(value).__name__}"
                )

        # Validate stressed tokens is non-negative int
        if not isinstance(self.intended_stressed_tokens, int):
            raise ValueError(
                f"AcousticRenderIntent.intended_stressed_tokens must be int, "
                f"got {type(self.intended_stressed_tokens).__name__}"
            )
        if self.intended_stressed_tokens < 0:
            raise ValueError(
                f"AcousticRenderIntent.intended_stressed_tokens must be >= 0, "
                f"got {self.intended_stressed_tokens}"
            )

        # Validate renderer_id is non-empty string
        if not isinstance(self.renderer_id, str) or not self.renderer_id.strip():
            raise ValueError(
                "AcousticRenderIntent.renderer_id must be a non-empty string"
            )

        # Validate intent_category
        if not isinstance(self.intent_category, RenderIntentCategory):
            raise ValueError(
                f"AcousticRenderIntent.intent_category must be RenderIntentCategory, "
                f"got {type(self.intent_category).__name__}"
            )

    def get_pitch_range(self) -> Tuple[int, int]:
        """Get intended pitch range as tuple."""
        return (self.intended_pitch_min, self.intended_pitch_max)

    def get_energy_range(self) -> Tuple[float, float]:
        """Get intended energy range as tuple."""
        return (self.intended_energy_min, self.intended_energy_max)

    def uses_any_expression(self) -> bool:
        """Check if any expressive feature is used."""
        return (
            self.will_use_emphasis or
            self.will_use_pitch_contours or
            self.will_use_rhythm_variation or
            self.will_use_intonation_shift
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for logging/tracing."""
        return {
            "intended_pitch_min": self.intended_pitch_min,
            "intended_pitch_max": self.intended_pitch_max,
            "intended_pitch_variance": self.intended_pitch_variance,
            "intended_energy_min": self.intended_energy_min,
            "intended_energy_max": self.intended_energy_max,
            "will_use_emphasis": self.will_use_emphasis,
            "will_use_pitch_contours": self.will_use_pitch_contours,
            "will_use_rhythm_variation": self.will_use_rhythm_variation,
            "will_use_intonation_shift": self.will_use_intonation_shift,
            "intended_stressed_tokens": self.intended_stressed_tokens,
            "renderer_id": self.renderer_id,
            "intent_category": self.intent_category.value,
            "debug": self.debug,
        }


@dataclass(frozen=True)
class ComplianceViolation:
    """
    A single compliance violation detected by the checker.

    Attributes:
        category: The category of violation
        description: Human-readable description
        evidence: Supporting evidence (expected vs actual)
    """
    category: ViolationCategory
    description: str
    evidence: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate ComplianceViolation fields."""
        if not isinstance(self.category, ViolationCategory):
            raise ValueError(
                f"ComplianceViolation.category must be ViolationCategory, "
                f"got {type(self.category).__name__}"
            )
        if not isinstance(self.description, str) or not self.description.strip():
            raise ValueError(
                "ComplianceViolation.description must be a non-empty string"
            )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "category": self.category.value,
            "description": self.description,
            "evidence": self.evidence,
        }


@dataclass(frozen=True)
class ComplianceResult:
    """
    Result of compliance checking.

    Attributes:
        verdict: PASS or FAIL
        violations: List of violations detected (empty if PASS)
        checked_constraints: List of constraint names that were checked
        renderer_id: The renderer that was checked
        envelope_risk_level: The P13 risk level that was enforced
    """
    verdict: ComplianceVerdict
    violations: Tuple[ComplianceViolation, ...]
    checked_constraints: Tuple[str, ...]
    renderer_id: str
    envelope_risk_level: str
    debug: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate ComplianceResult fields."""
        if not isinstance(self.verdict, ComplianceVerdict):
            raise ValueError(
                f"ComplianceResult.verdict must be ComplianceVerdict, "
                f"got {type(self.verdict).__name__}"
            )

        if not isinstance(self.violations, tuple):
            raise ValueError(
                f"ComplianceResult.violations must be tuple, "
                f"got {type(self.violations).__name__}"
            )

        for i, v in enumerate(self.violations):
            if not isinstance(v, ComplianceViolation):
                raise ValueError(
                    f"ComplianceResult.violations[{i}] must be ComplianceViolation, "
                    f"got {type(v).__name__}"
                )

        # INVARIANT: PASS verdict requires empty violations
        if self.verdict == ComplianceVerdict.PASS and len(self.violations) > 0:
            raise ValueError(
                "ComplianceResult: PASS verdict cannot have violations"
            )

        # INVARIANT: FAIL verdict requires non-empty violations
        if self.verdict == ComplianceVerdict.FAIL and len(self.violations) == 0:
            raise ValueError(
                "ComplianceResult: FAIL verdict must have violations"
            )

    def passed(self) -> bool:
        """Check if compliance check passed."""
        return self.verdict == ComplianceVerdict.PASS

    def failed(self) -> bool:
        """Check if compliance check failed."""
        return self.verdict == ComplianceVerdict.FAIL

    def violation_count(self) -> int:
        """Get number of violations."""
        return len(self.violations)

    def has_violation_category(self, category: ViolationCategory) -> bool:
        """Check if a specific violation category is present."""
        return any(v.category == category for v in self.violations)

    def get_violations_by_category(self, category: ViolationCategory) -> Tuple[ComplianceViolation, ...]:
        """Get all violations of a specific category."""
        return tuple(v for v in self.violations if v.category == category)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "verdict": self.verdict.value,
            "violations": [v.to_dict() for v in self.violations],
            "checked_constraints": list(self.checked_constraints),
            "renderer_id": self.renderer_id,
            "envelope_risk_level": self.envelope_risk_level,
            "violation_count": self.violation_count(),
            "debug": self.debug,
        }


@dataclass(frozen=True)
class RendererInputContract:
    """
    The complete, immutable contract between Symbol-U and renderers.

    This contract contains ALL information a renderer needs to produce
    compliant audio output. Renderers MUST NOT invent values outside
    this contract.

    CRITICAL: The AcousticSafetyEnvelope (P13) is BINDING.
    Any renderer violating P13 is UNSAFE BY DEFINITION.

    Attributes:
        p9_lexical: The lexical frame from P9 (selected words) - optional
        p10_acoustic: The acoustic parameter frame from P10
        p11_prosodic: The prosodic evidence frame from P11 - optional
        p12_consistent: Whether P12 reported consistency
        p13_envelope: The BINDING acoustic safety envelope
        source_regime: The operational regime (for reference)
        source_discourse_act: The discourse act (for reference)
        contract_version: Version of this contract schema
    """

    # === Upstream Data (Read-Only) ===
    p10_acoustic: Any  # AcousticParameterFrame
    p13_envelope: Any  # AcousticSafetyEnvelope (BINDING)

    # === Optional Upstream Data ===
    p9_lexical: Optional[Any] = None  # LexicalFrame
    p11_prosodic: Optional[Any] = None  # ProsodicEvidenceFrame
    p12_consistent: bool = False

    # === Reference Data ===
    source_regime: str = "UNKNOWN"
    source_discourse_act: str = "UNKNOWN"

    # === Metadata ===
    contract_version: str = RENDERER_CONTRACT_VERSION

    def __post_init__(self) -> None:
        """Validate RendererInputContract fields."""
        # P10 and P13 are mandatory
        if self.p10_acoustic is None:
            raise ValueError(
                "RendererInputContract.p10_acoustic is required"
            )
        if self.p13_envelope is None:
            raise ValueError(
                "RendererInputContract.p13_envelope is required (BINDING)"
            )

    def is_blocked(self) -> bool:
        """Check if the P13 envelope is BLOCKED."""
        return hasattr(self.p13_envelope, 'is_blocked') and self.p13_envelope.is_blocked()

    def get_allowed_pitch_range(self) -> Tuple[int, int]:
        """Get allowed pitch range from P13 envelope."""
        return self.p13_envelope.allowed_pitch_range

    def get_allowed_energy_range(self) -> Tuple[float, float]:
        """Get allowed energy range from P13 envelope."""
        return self.p13_envelope.allowed_energy_range

    def get_allowed_variance_range(self) -> Tuple[int, int]:
        """Get allowed variance range from P13 envelope."""
        return self.p13_envelope.allowed_variance_range

    def allows_emphasis(self) -> bool:
        """Check if emphasis is allowed by P13."""
        return self.p13_envelope.allow_emphasis

    def allows_pitch_contours(self) -> bool:
        """Check if pitch contours are allowed by P13."""
        return self.p13_envelope.allow_pitch_contours

    def allows_rhythm_variation(self) -> bool:
        """Check if rhythm variation is allowed by P13."""
        return self.p13_envelope.allow_rhythm_variation

    def allows_intonation_shift(self) -> bool:
        """Check if intonation shift is allowed by P13."""
        return self.p13_envelope.allow_intonation_shift

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "p10_acoustic": self.p10_acoustic.to_dict() if hasattr(self.p10_acoustic, 'to_dict') else str(self.p10_acoustic),
            "p13_envelope": self.p13_envelope.to_dict() if hasattr(self.p13_envelope, 'to_dict') else str(self.p13_envelope),
            "p9_lexical": self.p9_lexical.to_dict() if self.p9_lexical and hasattr(self.p9_lexical, 'to_dict') else None,
            "p11_prosodic": self.p11_prosodic.to_dict() if self.p11_prosodic and hasattr(self.p11_prosodic, 'to_dict') else None,
            "p12_consistent": self.p12_consistent,
            "source_regime": self.source_regime,
            "source_discourse_act": self.source_discourse_act,
            "contract_version": self.contract_version,
            "is_blocked": self.is_blocked(),
        }


# ============================================================================
# PUBLIC EXPORTS
# ============================================================================


__all__ = [
    # Version
    "RENDERER_CONTRACT_VERSION",
    # Enums
    "RenderIntentCategory",
    "ComplianceVerdict",
    "ViolationCategory",
    # Dataclasses
    "AcousticRenderIntent",
    "ComplianceViolation",
    "ComplianceResult",
    "RendererInputContract",
]
