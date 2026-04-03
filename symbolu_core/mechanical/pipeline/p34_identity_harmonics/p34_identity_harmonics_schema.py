"""
P34 Identity Harmonics Layer Schema
====================================

Schema definitions for the P34 Identity Harmonics Layer phase within the
Formula/Consciousness Band (P25-P35).

Phase Authority: OBSERVER (witness-only)
Band: Formula/Consciousness (P25-P35)

This phase wraps the identity_harmonics.py formula and produces:
- CIH: Core Identity Harmonic
- AIH: Adaptive Identity Harmonic
- RIH: Relational Identity Harmonic
- IHI: Identity Harmonics Index (combined score)

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


class P34Authority(Enum):
    """
    Authority level for P34 phase decisions.

    P34 is OBSERVER-only (witness, non-actuating).
    """
    OBSERVER = "observer"  # Default - witness only, no actuation
    ANALYTICS = "analytics"  # For dashboard/diagnostic use


# =============================================================================
# DATA CLASSES
# =============================================================================


@dataclass(frozen=True)
class P34Output:
    """
    Output from P34 Identity Harmonics Layer phase.

    This is a frozen (immutable) dataclass wrapping the formula output
    with pipeline-specific metadata.

    Fields:
        core_identity_harmonic: CIH - Stability of identity signals [0.0, 1.0]
        adaptive_identity_harmonic: AIH - Ability to shift coherently [0.0, 1.0]
        relational_identity_harmonic: RIH - Persona-symbolic resonance [0.0, 1.0]
        identity_harmonics_index: IHI - Combined overall score [0.0, 1.0]
        identity_entropy: Entropy of harmonic components [0.0, 1.0]
        identity_stability_score: Derived stability measure [0.0, 1.0]
        identity_flexibility_score: Derived flexibility measure [0.0, 1.0]
        authority: Authority level (always OBSERVER)
        diagnostic_tags: Deterministic diagnostic tags
        processing_trace: Processing trace for debugging
    """
    # Core harmonics
    core_identity_harmonic: float  # CIH [0.0, 1.0]
    adaptive_identity_harmonic: float  # AIH [0.0, 1.0]
    relational_identity_harmonic: float  # RIH [0.0, 1.0]

    # Combined index
    identity_harmonics_index: float  # IHI [0.0, 1.0]

    # Derived metrics
    identity_entropy: float = 0.0  # [0.0, 1.0]
    identity_stability_score: float = 0.5  # [0.0, 1.0]
    identity_flexibility_score: float = 0.5  # [0.0, 1.0]

    # Authority (always observer for P34)
    authority: P34Authority = P34Authority.OBSERVER

    # Diagnostics
    diagnostic_tags: List[str] = field(default_factory=list)
    processing_trace: List[str] = field(default_factory=list)

    def __post_init__(self):
        """Validate and clamp values after initialization."""
        # Clamp all float values to [0, 1]
        object.__setattr__(self, 'core_identity_harmonic',
                          max(0.0, min(1.0, self.core_identity_harmonic)))
        object.__setattr__(self, 'adaptive_identity_harmonic',
                          max(0.0, min(1.0, self.adaptive_identity_harmonic)))
        object.__setattr__(self, 'relational_identity_harmonic',
                          max(0.0, min(1.0, self.relational_identity_harmonic)))
        object.__setattr__(self, 'identity_harmonics_index',
                          max(0.0, min(1.0, self.identity_harmonics_index)))
        object.__setattr__(self, 'identity_entropy',
                          max(0.0, min(1.0, self.identity_entropy)))
        object.__setattr__(self, 'identity_stability_score',
                          max(0.0, min(1.0, self.identity_stability_score)))
        object.__setattr__(self, 'identity_flexibility_score',
                          max(0.0, min(1.0, self.identity_flexibility_score)))

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "phase": "P34",
            "version": VERSION,
            "core_identity_harmonic": self.core_identity_harmonic,
            "adaptive_identity_harmonic": self.adaptive_identity_harmonic,
            "relational_identity_harmonic": self.relational_identity_harmonic,
            "identity_harmonics_index": self.identity_harmonics_index,
            "identity_entropy": self.identity_entropy,
            "identity_stability_score": self.identity_stability_score,
            "identity_flexibility_score": self.identity_flexibility_score,
            "authority": self.authority.value,
            "diagnostic_tags": list(self.diagnostic_tags),
            "processing_trace": list(self.processing_trace),
        }

    def get_harmonic_band(self) -> str:
        """
        Get harmonic band classification based on IHI.

        Returns:
            "HIGH" if IHI >= 0.70
            "MEDIUM" if IHI >= 0.40
            "LOW" otherwise
        """
        if self.identity_harmonics_index >= 0.70:
            return "HIGH"
        elif self.identity_harmonics_index >= 0.40:
            return "MEDIUM"
        else:
            return "LOW"

    def is_identity_stable(self) -> bool:
        """Check if identity is stable (CIH >= 0.65)."""
        return self.core_identity_harmonic >= 0.65

    def is_identity_flexible(self) -> bool:
        """Check if identity is flexible (AIH >= 0.60)."""
        return self.adaptive_identity_harmonic >= 0.60

    def is_identity_resonant(self) -> bool:
        """Check if identity is resonant (RIH >= 0.60)."""
        return self.relational_identity_harmonic >= 0.60


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "VERSION",
    "P34Authority",
    "P34Output",
]
