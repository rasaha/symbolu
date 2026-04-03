"""
P27 Persona Selection Phase Schema
===================================

Schema definitions for the P27 Persona Selection phase within the
Delivery Adaptation Band (P27-P31).

Phase Authority: MEDIUM
Band: Delivery Adaptation (P27-P31)

This phase wraps the Persona Engine as a formal governance phase,
enabling persona selection to be traced, audited, and integrated
with the broader phase architecture.

Inputs:
    - Fusion output text
    - MLCR tier and intent
    - DHA readiness/resistance signals (if available from P28)
    - Domain context

Outputs:
    - Selected persona ID
    - Persona styling directives
    - Selection reasoning trace

Version: 1.0.0
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set

# =============================================================================
# VERSION
# =============================================================================

VERSION = "1.0.0"


# =============================================================================
# ENUMS
# =============================================================================


class P27Authority(Enum):
    """Authority level for P27 phase decisions."""
    HIGH = "high"       # Persona decision is binding
    MEDIUM = "medium"   # Persona can be overridden by DHA
    LOW = "low"         # Persona is advisory only


class PersonaSelectionMode(Enum):
    """Mode for persona selection."""
    AUTOMATIC = "automatic"       # System selects based on signals
    HINT_GUIDED = "hint_guided"   # User hint influences selection
    FORCED = "forced"             # Explicit persona override


class PersonaCategory(Enum):
    """Categories of personas."""
    SAGE = "sage"               # Wise, contemplative
    ANALYST = "analyst"         # Logical, data-driven
    COACH = "coach"             # Supportive, action-oriented
    FRIENDLY = "friendly"       # Warm, approachable
    REGULATOR = "regulator"     # Formal, rule-bound
    NEUTRAL = "neutral"         # Balanced, default


# =============================================================================
# DATA CLASSES
# =============================================================================


@dataclass(frozen=True)
class P27SelectionSignals:
    """
    Input signals for persona selection.

    Aggregates signals from MLCR, Fusion, and context to inform
    persona selection decision.
    """
    # Core text
    query_text: str
    response_text: str

    # MLCR signals
    tier: str = "hybrid"
    intent: str = "general"
    domain: str = "generic"

    # Entropy signals
    emotional_entropy: float = 0.5
    cognitive_entropy: float = 0.5

    # Readiness signals (from DHA if available)
    readiness_score: float = 0.5
    resistance_score: float = 0.3

    # Selection mode
    mode: PersonaSelectionMode = PersonaSelectionMode.AUTOMATIC
    persona_hint: Optional[str] = None

    def __post_init__(self) -> None:
        """Validate signal ranges."""
        # Validate entropy ranges
        if not 0.0 <= self.emotional_entropy <= 1.0:
            object.__setattr__(self, 'emotional_entropy',
                             max(0.0, min(1.0, self.emotional_entropy)))
        if not 0.0 <= self.cognitive_entropy <= 1.0:
            object.__setattr__(self, 'cognitive_entropy',
                             max(0.0, min(1.0, self.cognitive_entropy)))
        # Validate readiness/resistance
        if not 0.0 <= self.readiness_score <= 1.0:
            object.__setattr__(self, 'readiness_score',
                             max(0.0, min(1.0, self.readiness_score)))
        if not 0.0 <= self.resistance_score <= 1.0:
            object.__setattr__(self, 'resistance_score',
                             max(0.0, min(1.0, self.resistance_score)))


@dataclass(frozen=True)
class P27PersonaDirectives:
    """
    Persona styling directives output from P27.

    Provides guidance to downstream phases on how to style output.
    """
    # Core styling
    tone_warmth: float = 0.5        # 0=cool/formal, 1=warm/friendly
    formality_level: float = 0.5    # 0=casual, 1=formal
    directness: float = 0.5         # 0=indirect, 1=direct

    # Linguistic markers
    use_metaphors: bool = False
    use_technical_terms: bool = True
    preferred_pronouns: str = "you"  # "you", "we", "one"

    # Domain adaptations
    domain_vocabulary: Set[str] = field(default_factory=set)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "tone_warmth": self.tone_warmth,
            "formality_level": self.formality_level,
            "directness": self.directness,
            "use_metaphors": self.use_metaphors,
            "use_technical_terms": self.use_technical_terms,
            "preferred_pronouns": self.preferred_pronouns,
            "domain_vocabulary": list(self.domain_vocabulary),
        }


@dataclass(frozen=True)
class P27Output:
    """
    Output from P27 Persona Selection phase.

    Contains the selected persona and associated directives.
    """
    # Selected persona
    persona_id: str
    persona_category: PersonaCategory

    # Selection metadata
    selection_mode: PersonaSelectionMode
    selection_confidence: float = 0.8

    # Authority level for this selection
    authority: P27Authority = P27Authority.MEDIUM

    # Styling directives
    directives: P27PersonaDirectives = field(
        default_factory=lambda: P27PersonaDirectives()
    )

    # Selection reasoning trace
    selection_reasoning: List[str] = field(default_factory=list)

    # Alternative personas considered
    alternatives: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Validate output fields."""
        if not 0.0 <= self.selection_confidence <= 1.0:
            object.__setattr__(self, 'selection_confidence',
                             max(0.0, min(1.0, self.selection_confidence)))

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "phase": "P27",
            "version": VERSION,
            "persona_id": self.persona_id,
            "persona_category": self.persona_category.value,
            "selection_mode": self.selection_mode.value,
            "selection_confidence": self.selection_confidence,
            "authority": self.authority.value,
            "directives": self.directives.to_dict(),
            "selection_reasoning": self.selection_reasoning,
            "alternatives": self.alternatives,
        }


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "VERSION",
    "P27Authority",
    "PersonaSelectionMode",
    "PersonaCategory",
    "P27SelectionSignals",
    "P27PersonaDirectives",
    "P27Output",
]
