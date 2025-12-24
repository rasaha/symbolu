"""
P28 Delivery Harmonization Phase Schema
=========================================

Schema definitions for the P28 Delivery Harmonization & Adaptation (DHA)
phase within the Delivery Adaptation Band (P27-P31).

Phase Authority: MEDIUM
Band: Delivery Adaptation (P27-P31)

This phase wraps the DHA Engine as a formal governance phase,
enabling delivery adaptation to be traced, audited, and integrated
with the broader phase architecture.

Inputs:
    - Fusion output text
    - P27 persona directives
    - MLCR tier and signals
    - Readiness/resistance indicators

Outputs:
    - Adapted message text
    - Delivery profile selection
    - Tone modulation trace
    - Safety filter results

Version: 1.0.0
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

# =============================================================================
# VERSION
# =============================================================================

VERSION = "1.0.0"


# =============================================================================
# ENUMS
# =============================================================================


class P28Authority(Enum):
    """Authority level for P28 phase decisions."""
    HIGH = "high"       # DHA decision is binding (safety critical)
    MEDIUM = "medium"   # DHA can be adjusted by downstream
    LOW = "low"         # DHA is advisory only


class DeliveryProfileType(Enum):
    """Types of delivery profiles."""
    SWEET_RESONANCE = "sweet_resonance"     # Gentle, supportive
    INVERSE_JOLT = "inverse_jolt"           # Direct, challenging
    SYMBOLIC_METAPHOR = "symbolic_metaphor"  # Indirect, metaphorical
    BALANCED = "balanced"                    # Neutral, balanced


class ReadinessLevel(Enum):
    """User readiness levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ResistanceLevel(Enum):
    """User resistance levels."""
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class SafetyStatus(Enum):
    """Safety filter status."""
    PASSED = "passed"
    MODIFIED = "modified"
    BLOCKED = "blocked"


# =============================================================================
# DATA CLASSES
# =============================================================================


@dataclass(frozen=True)
class P28InputSignals:
    """
    Input signals for DHA phase.

    Aggregates signals from MLCR, Fusion, P27, and context.
    """
    # Core text
    query_text: str
    response_text: str

    # P27 persona context
    persona_id: str = "neutral"
    persona_tone_warmth: float = 0.5
    persona_formality: float = 0.5
    persona_directness: float = 0.5

    # MLCR signals
    tier: str = "hybrid"
    intent: str = "general"
    domain: str = "generic"

    # Entropy signals
    emotional_entropy: float = 0.5
    dimensional_entropy: float = 0.5

    # User state signals
    readiness_score: float = 0.5
    resistance_score: float = 0.3

    def __post_init__(self) -> None:
        """Validate signal ranges."""
        for attr in ['emotional_entropy', 'dimensional_entropy',
                     'readiness_score', 'resistance_score',
                     'persona_tone_warmth', 'persona_formality',
                     'persona_directness']:
            value = getattr(self, attr)
            if not 0.0 <= value <= 1.0:
                object.__setattr__(self, attr, max(0.0, min(1.0, value)))


@dataclass(frozen=True)
class P28ToneProfile:
    """
    Tone profile selected by P28.

    Defines the delivery characteristics for the message.
    """
    # Core profile
    profile_type: DeliveryProfileType = DeliveryProfileType.BALANCED

    # Modulation parameters
    warmth: float = 0.5          # 0=cool, 1=warm
    directness: float = 0.5      # 0=indirect, 1=direct
    formality: float = 0.5       # 0=casual, 1=formal
    empathy: float = 0.5         # 0=neutral, 1=high empathy

    # Pacing
    message_pace: str = "normal"  # "slow", "normal", "fast"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "profile_type": self.profile_type.value,
            "warmth": self.warmth,
            "directness": self.directness,
            "formality": self.formality,
            "empathy": self.empathy,
            "message_pace": self.message_pace,
        }


@dataclass(frozen=True)
class P28SafetyResult:
    """
    Safety filter results from P28.

    Documents any safety modifications made to the message.
    """
    status: SafetyStatus = SafetyStatus.PASSED
    original_text: Optional[str] = None
    modifications: List[str] = field(default_factory=list)
    safety_score: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "status": self.status.value,
            "has_modifications": self.status == SafetyStatus.MODIFIED,
            "modification_count": len(self.modifications),
            "safety_score": self.safety_score,
        }


@dataclass(frozen=True)
class P28Output:
    """
    Output from P28 Delivery Harmonization phase.

    Contains the adapted message and delivery profile.
    """
    # Adapted message
    adapted_text: str
    guarded_text: str  # After safety filters

    # Delivery profile
    tone_profile: P28ToneProfile = field(
        default_factory=lambda: P28ToneProfile()
    )

    # Readiness/resistance analysis
    readiness_level: ReadinessLevel = ReadinessLevel.MEDIUM
    resistance_level: ResistanceLevel = ResistanceLevel.LOW

    # Safety results
    safety_result: P28SafetyResult = field(
        default_factory=lambda: P28SafetyResult()
    )

    # Authority level
    authority: P28Authority = P28Authority.MEDIUM

    # Adaptation trace
    adaptation_trace: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Ensure guarded_text has a value."""
        if not self.guarded_text and self.adapted_text:
            object.__setattr__(self, 'guarded_text', self.adapted_text)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "phase": "P28",
            "version": VERSION,
            "adapted_text": self.adapted_text,
            "guarded_text": self.guarded_text,
            "tone_profile": self.tone_profile.to_dict(),
            "readiness_level": self.readiness_level.value,
            "resistance_level": self.resistance_level.value,
            "safety_result": self.safety_result.to_dict(),
            "authority": self.authority.value,
            "adaptation_trace": self.adaptation_trace,
        }


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "VERSION",
    "P28Authority",
    "DeliveryProfileType",
    "ReadinessLevel",
    "ResistanceLevel",
    "SafetyStatus",
    "P28InputSignals",
    "P28ToneProfile",
    "P28SafetyResult",
    "P28Output",
]
