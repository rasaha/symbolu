"""
P38 - Pattern Sequence Grammar Definitions
===========================================

Predefined meaningful pattern sequences for anticipatory detection.
Each sequence encodes domain expertise about known pattern trajectories.

Sequences are hand-curated, named, and frozen -- same governance philosophy
as the 13 CDI patterns. Matching supports partial sequences for anticipation.

INVARIANTS:
    - INV-P38-3: No LLM, no ML, no learning
    - All sequences are module-level constants (locked)

Version: 1.0.0
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple, List


P38_SEQUENCE_VERSION = "1.0.0"


@dataclass(frozen=True)
class PatternSequenceRule:
    """A known meaningful pattern sequence.

    Attributes:
        name: Unique sequence identifier.
        category: "escalation" | "resolution" | "entrenchment"
        steps: Ordered pattern names that form the sequence.
        max_gap_turns: Max turns allowed between consecutive steps (0 = must be consecutive).
        min_confidence: Minimum avg confidence across matched steps.
        interpretation: Human-readable explanation of what this sequence means.
    """
    name: str
    category: str
    steps: Tuple[str, ...]
    max_gap_turns: int
    min_confidence: float
    interpretation: str


# =============================================================================
# LOCKED SEQUENCE DEFINITIONS
# =============================================================================

PATTERN_SEQUENCES: List[PatternSequenceRule] = [
    # --- Escalation sequences ---
    PatternSequenceRule(
        name="suppression_escalation",
        category="escalation",
        steps=("acute_anxiety", "emotional_masking", "chronic_stress"),
        max_gap_turns=2,
        min_confidence=0.60,
        interpretation=(
            "Acute distress being suppressed, transitioning to chronic stress pattern"
        ),
    ),
    PatternSequenceRule(
        name="risk_concealment_deepening",
        category="escalation",
        steps=("risk_hiding", "defensive_rationalization"),
        max_gap_turns=1,
        min_confidence=0.65,
        interpretation=(
            "Active risk concealment followed by justification -- high concern signal"
        ),
    ),
    PatternSequenceRule(
        name="stress_to_avoidance",
        category="escalation",
        steps=("tension_corridor", "avoidance_pattern", "emotional_masking"),
        max_gap_turns=2,
        min_confidence=0.60,
        interpretation=(
            "Sustained tension leading to avoidance and emotional shutdown"
        ),
    ),

    # --- Entrenchment sequences ---
    PatternSequenceRule(
        name="entrenchment_spiral",
        category="entrenchment",
        steps=("cognitive_dissonance", "avoidance_pattern", "defensive_rationalization"),
        max_gap_turns=2,
        min_confidence=0.65,
        interpretation=(
            "Internal conflict being avoided rather than resolved, rationalizations forming"
        ),
    ),
    PatternSequenceRule(
        name="chronic_avoidance",
        category="entrenchment",
        steps=("avoidance_pattern", "emotional_masking", "avoidance_pattern"),
        max_gap_turns=2,
        min_confidence=0.60,
        interpretation=(
            "Avoidance recurring after emotional suppression -- deepening entrenchment"
        ),
    ),

    # --- Resolution sequences ---
    PatternSequenceRule(
        name="productive_resolution",
        category="resolution",
        steps=("tension_corridor", "breakthrough_insight", "integrative_growth"),
        max_gap_turns=3,
        min_confidence=0.60,
        interpretation=(
            "Sustained tension resolved through insight, leading to integration"
        ),
    ),
    PatternSequenceRule(
        name="recovery_arc",
        category="resolution",
        steps=("chronic_stress", "recovery_trajectory", "resilience_pattern"),
        max_gap_turns=3,
        min_confidence=0.60,
        interpretation=(
            "Stress pattern resolving through recovery into demonstrated resilience"
        ),
    ),
    PatternSequenceRule(
        name="authentic_breakthrough",
        category="resolution",
        steps=("emotional_masking", "authentic_expression", "breakthrough_insight"),
        max_gap_turns=2,
        min_confidence=0.60,
        interpretation=(
            "Emotional defense dropping, enabling genuine expression and insight"
        ),
    ),
]


# Quick lookup by name
SEQUENCE_BY_NAME = {seq.name: seq for seq in PATTERN_SEQUENCES}


__all__ = [
    "P38_SEQUENCE_VERSION",
    "PatternSequenceRule",
    "PATTERN_SEQUENCES",
    "SEQUENCE_BY_NAME",
]
