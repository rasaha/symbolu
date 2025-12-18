"""
Composition Types for Phase-6 Experiments
==========================================

EXPERIMENTAL MODULE - NON-FROZEN, NON-CANONICAL

This module defines types and enums for the Phase-6 composition axis experiments.
These types support testing composition grammar axes:
    - Dominance (consonant reset behavior)
    - Vowel scope (preceding-only vs persist-until-reset)
    - Multi-vowel accumulation
    - Optional layer-sensitive initialization

CONSTRAINTS:
    - NO ML, NO embeddings, NO probability
    - NO ontology edits, NO new phases
    - NO inference - fail fast if data missing
    - READ-ONLY access to Phase-4A ontology
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


# =============================================================================
# Enums
# =============================================================================

class VowelScope(Enum):
    """
    Defines how vowel modulation affects the sequence state.

    PRECEDING_ONLY:
        Vowel modifies the magnitude from the previous consonant's effect.
        The modulation is conceptually "attached" to the preceding consonant.
        Consecutive vowels are allowed - each modifies the same active magnitude.

    PERSIST_UNTIL_RESET:
        Vowel modifies the active magnitude and that modification persists
        until a consonant resets the state. This is the default behavior.
        Consecutive vowels accumulate additively on the active magnitude.
    """
    PRECEDING_ONLY = "preceding_only"
    PERSIST_UNTIL_RESET = "persist_until_reset"


class TokenType(Enum):
    """Type of token in a varna sequence."""
    VARNA = "varna"      # Consonant (from ontology)
    VOWEL = "vowel"      # Vowel (from experiment set)


class EventType(Enum):
    """Type of event produced when processing a token."""
    RESET = "reset"          # Consonant resets magnitude to baseline
    MODULATE = "modulate"    # Vowel modulates active magnitude
    NOOP = "noop"            # No operation (future use)


# =============================================================================
# Data Classes
# =============================================================================

@dataclass(frozen=True)
class TrajectoryStep:
    """
    A single step in the composition trajectory.

    This is the primary output record for Phase-6 experiments.

    Attributes:
        idx: Step index (0-indexed)
        token: The token processed at this step
        token_type: Whether this is a "varna" (consonant) or "vowel"
        magnitude: The active magnitude after processing this step
        event: The type of event ("reset", "modulate", "noop")
        notes: Optional notes for debugging/documentation
    """
    idx: int
    token: str
    token_type: str  # "varna" | "vowel" (string for JSON compatibility)
    magnitude: float
    event: str  # "reset" | "modulate" | "noop"
    notes: str = ""

    def to_dict(self) -> dict:
        """Convert to plain dict for serialization."""
        return {
            "idx": self.idx,
            "token": self.token,
            "token_type": self.token_type,
            "magnitude": self.magnitude,
            "event": self.event,
            "notes": self.notes,
        }


@dataclass
class SequenceConfig:
    """
    Configuration for sequence analysis.

    Attributes:
        vowel_scope: How vowel modulation affects state
        initial_magnitude: Starting magnitude (default 1.0)
        layer: Optional layer for layer-sensitive initialization (future use)
    """
    vowel_scope: VowelScope = VowelScope.PERSIST_UNTIL_RESET
    initial_magnitude: float = 1.0
    layer: Optional[str] = None  # Optional hook for layer-sensitive init


@dataclass
class TrajectoryResult:
    """
    Complete result from sequence analysis.

    Attributes:
        sequence: The input sequence analyzed
        steps: List of trajectory steps
        config: Configuration used for analysis
        final_magnitude: The magnitude at end of sequence
    """
    sequence: tuple
    steps: tuple  # Tuple[TrajectoryStep, ...]
    config: SequenceConfig
    final_magnitude: float

    def get_magnitudes(self) -> list:
        """Get list of magnitudes at each step."""
        return [step.magnitude for step in self.steps]

    def get_events(self) -> list:
        """Get list of events at each step."""
        return [step.event for step in self.steps]

    def to_dict(self) -> dict:
        """Convert to plain dict for serialization."""
        return {
            "sequence": list(self.sequence),
            "steps": [step.to_dict() for step in self.steps],
            "config": {
                "vowel_scope": self.config.vowel_scope.value,
                "initial_magnitude": self.config.initial_magnitude,
                "layer": self.config.layer,
            },
            "final_magnitude": self.final_magnitude,
        }


# =============================================================================
# Vowel Modulation Constants (Phase-6 Baseline)
# =============================================================================

# These are deterministic toy values for Phase-6 experiments.
# The values are intentionally simple for falsification testing.
# a=+0.1, i=+0.2, u=+0.15 as specified in Phase-6 requirements.
PHASE6_VOWEL_DELTAS = {
    "a": 0.1,
    "i": 0.2,
    "u": 0.15,
}

# The supported vowel set for Phase-6 experiments
PHASE6_VOWELS = frozenset({"a", "i", "u"})

# Baseline magnitude for consonant reset
BASELINE_MAGNITUDE = 1.0
