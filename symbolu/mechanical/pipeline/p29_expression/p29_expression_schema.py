"""
P29 Expression Finalization Phase Schema
==========================================

Schema definitions for the P29 Expression Finalization phase within the
Delivery Adaptation Band (P27-P31).

Phase Authority: LOW
Band: Delivery Adaptation (P27-P31)

This phase handles final linguistic polish after DHA, including:
- Phoneme rhythm optimization via Varṇa
- Style modifier application
- Sentence flow refinement

Inputs:
    - P28 guarded text
    - Persona directives from P27
    - Tone profile from P28

Outputs:
    - Polished text
    - Phoneme analysis results
    - Style modifications applied

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


class P29Authority(Enum):
    """Authority level for P29 phase decisions."""
    HIGH = "high"       # Expression decision is binding
    MEDIUM = "medium"   # Expression can be adjusted
    LOW = "low"         # Expression is advisory (default)


class PolishMode(Enum):
    """Mode for expression polish."""
    PHONEME_ONLY = "phoneme_only"     # Varṇa-based optimization only
    STYLE_ONLY = "style_only"         # Style modifiers only
    FULL = "full"                     # Both phoneme and style
    PASSTHROUGH = "passthrough"       # No modification


class RhythmQuality(Enum):
    """Quality of sentence rhythm."""
    EXCELLENT = "excellent"   # Highly readable, natural flow
    GOOD = "good"             # Readable, minor improvements possible
    FAIR = "fair"             # Some awkward phrasing
    POOR = "poor"             # Needs significant work


# =============================================================================
# DATA CLASSES
# =============================================================================


@dataclass(frozen=True)
class P29InputSignals:
    """
    Input signals for expression finalization phase.
    """
    # Core text from P28
    input_text: str

    # P27 persona context
    persona_id: str = "neutral"
    tone_warmth: float = 0.5
    formality_level: float = 0.5
    directness: float = 0.5

    # P28 delivery profile
    delivery_profile: str = "balanced"

    # Mode selection
    polish_mode: PolishMode = PolishMode.FULL

    def __post_init__(self) -> None:
        """Validate input ranges."""
        for attr in ['tone_warmth', 'formality_level', 'directness']:
            value = getattr(self, attr)
            if not 0.0 <= value <= 1.0:
                object.__setattr__(self, attr, max(0.0, min(1.0, value)))


@dataclass(frozen=True)
class P29PhonemeAnalysis:
    """
    Phoneme analysis results from Varṇa integration.
    """
    # Overall harmony score
    overall_harmony: float = 0.0

    # Dominant phoneme layer
    dominant_layer: str = "unknown"

    # Bridge meanings discovered
    bridge_meanings: List[str] = field(default_factory=list)

    # Rhythm quality assessment
    rhythm_quality: RhythmQuality = RhythmQuality.GOOD

    # Word count analyzed
    words_analyzed: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "overall_harmony": self.overall_harmony,
            "dominant_layer": self.dominant_layer,
            "bridge_meanings": self.bridge_meanings,
            "rhythm_quality": self.rhythm_quality.value,
            "words_analyzed": self.words_analyzed,
        }


@dataclass(frozen=True)
class P29StyleModifications:
    """
    Style modifications applied during polish.
    """
    # Style parameters applied
    warmth_applied: float = 0.5
    directness_applied: float = 0.5
    formality_applied: float = 0.5

    # Modifications made
    modifications: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "warmth_applied": self.warmth_applied,
            "directness_applied": self.directness_applied,
            "formality_applied": self.formality_applied,
            "modifications": self.modifications,
        }


@dataclass(frozen=True)
class P29Output:
    """
    Output from P29 Expression Finalization phase.
    """
    # Final polished text
    final_text: str

    # Polish applied flag
    polish_applied: bool = True

    # Polish mode used
    polish_mode: PolishMode = PolishMode.FULL

    # Authority level
    authority: P29Authority = P29Authority.LOW

    # Phoneme analysis results
    phoneme_analysis: Optional[P29PhonemeAnalysis] = None

    # Style modifications
    style_modifications: Optional[P29StyleModifications] = None

    # Processing trace
    processing_trace: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "phase": "P29",
            "version": VERSION,
            "final_text": self.final_text,
            "polish_applied": self.polish_applied,
            "polish_mode": self.polish_mode.value,
            "authority": self.authority.value,
            "phoneme_analysis": self.phoneme_analysis.to_dict() if self.phoneme_analysis else None,
            "style_modifications": self.style_modifications.to_dict() if self.style_modifications else None,
            "processing_trace": self.processing_trace,
        }


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "VERSION",
    "P29Authority",
    "PolishMode",
    "RhythmQuality",
    "P29InputSignals",
    "P29PhonemeAnalysis",
    "P29StyleModifications",
    "P29Output",
]
