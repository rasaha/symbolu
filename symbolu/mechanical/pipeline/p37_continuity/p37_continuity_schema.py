"""
P37 Adaptive Continuity Engine Schema
======================================

Schema definitions for the P37 Adaptive Continuity Engine phase within the
Advanced Pipeline Band (P36-P54).

Phase Authority: PREDICTIVE / READ-ONLY (non-actuating)
Band: Advanced Pipeline (P36-P54)

This phase wraps the adaptive_continuity_engine.py formula and produces:
- NCC: Narrative Continuity Coefficient
- ICC: Identity Continuity Coefficient
- CSS: Continuity Stability Score

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


class P37Authority(Enum):
    """
    Authority level for P37 phase decisions.

    P37 is PREDICTIVE/READ-ONLY (non-actuating).
    """
    PREDICTIVE = "predictive"  # Default - predictive analytics only
    ANALYTICS = "analytics"  # For dashboard/diagnostic use


class ContinuityBand(Enum):
    """Continuity band classification based on CSS."""
    HIGH = "HIGH"  # CSS >= 0.70
    MEDIUM = "MEDIUM"  # CSS >= 0.40
    LOW = "LOW"  # CSS < 0.40


# =============================================================================
# DATA CLASSES
# =============================================================================


@dataclass(frozen=True)
class P37Output:
    """
    Output from P37 Adaptive Continuity Engine phase.

    This is a frozen (immutable) dataclass wrapping the formula output
    with pipeline-specific metadata.

    Fields:
        ncc: Narrative Continuity Coefficient [0.0, 1.0]
        icc: Identity Continuity Coefficient [0.0, 1.0]
        css: Continuity Stability Score [0.0, 1.0]
        continuity_band: Band classification (HIGH/MEDIUM/LOW)
        authority: Authority level (always PREDICTIVE)
        continuity_tags: Deterministic diagnostic tags
        raw_signals: Raw signal values for API exposure
        processing_trace: Processing trace for debugging
    """
    # Core continuity coefficients
    ncc: float  # Narrative Continuity Coefficient [0.0, 1.0]
    icc: float  # Identity Continuity Coefficient [0.0, 1.0]
    css: float  # Continuity Stability Score [0.0, 1.0]

    # Band classification
    continuity_band: ContinuityBand = ContinuityBand.MEDIUM

    # Authority (always predictive for P37)
    authority: P37Authority = P37Authority.PREDICTIVE

    # Diagnostics
    continuity_tags: List[str] = field(default_factory=list)
    raw_signals: Dict[str, float] = field(default_factory=dict)
    processing_trace: List[str] = field(default_factory=list)

    def __post_init__(self):
        """Validate and clamp values after initialization."""
        # Clamp all float values to [0, 1]
        object.__setattr__(self, 'ncc', max(0.0, min(1.0, self.ncc)))
        object.__setattr__(self, 'icc', max(0.0, min(1.0, self.icc)))
        object.__setattr__(self, 'css', max(0.0, min(1.0, self.css)))

        # Derive continuity band from CSS if not set correctly
        if self.css >= 0.70:
            object.__setattr__(self, 'continuity_band', ContinuityBand.HIGH)
        elif self.css >= 0.40:
            object.__setattr__(self, 'continuity_band', ContinuityBand.MEDIUM)
        else:
            object.__setattr__(self, 'continuity_band', ContinuityBand.LOW)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "phase": "P37",
            "version": VERSION,
            "ncc": self.ncc,
            "icc": self.icc,
            "css": self.css,
            "continuity_band": self.continuity_band.value,
            "authority": self.authority.value,
            "continuity_tags": list(self.continuity_tags),
            "raw_signals": dict(self.raw_signals),
            "processing_trace": list(self.processing_trace),
        }

    def is_continuity_strong(self) -> bool:
        """Check if narrative continuity is strong (NCC >= 0.70)."""
        return self.ncc >= 0.70

    def is_identity_continuous(self) -> bool:
        """Check if identity continuity is strong (ICC >= 0.70)."""
        return self.icc >= 0.70

    def is_session_stable(self) -> bool:
        """Check if session is stable (CSS >= 0.65)."""
        return self.css >= 0.65

    def is_narrative_identity_aligned(self) -> bool:
        """Check if narrative and identity are aligned (|NCC - ICC| <= 0.15)."""
        return abs(self.ncc - self.icc) <= 0.15


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "VERSION",
    "P37Authority",
    "ContinuityBand",
    "P37Output",
]
