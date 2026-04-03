"""
Varna Composition Experiments
=============================

EXPERIMENTAL module for testing varna compositional semantics hypotheses.

This module is NON-FROZEN, NON-CANONICAL, and exists solely to support
falsification experiments. It does NOT modify frozen ontology data.

Key Question:
    Does positional arrangement of the SAME varnas produce different
    pressure trajectories?

If yes -> composition grammar is non-commutative.
If no  -> generation collapses and must be reconsidered.

Phase-6 Extension:
    Tests composition axes:
    - Dominance (consonant reset behavior)
    - Vowel scope (preceding-only vs persist-until-reset)
    - Multi-vowel accumulation (additive baseline)
    - Optional layer-sensitive initialization (future hook)
"""

# Original Phase-5 exports
from agentic.experiments.composition.sequence_analyzer import (
    SequenceAnalyzer,
    PressureState,
    TraceEntry,
    analyze_sequence,
)

# Phase-6 types
from agentic.experiments.composition.composition_types import (
    VowelScope,
    TokenType,
    EventType,
    TrajectoryStep,
    SequenceConfig,
    TrajectoryResult,
    PHASE6_VOWEL_DELTAS,
    PHASE6_VOWELS,
    BASELINE_MAGNITUDE,
)

# Phase-6 analyzer
from agentic.experiments.composition.phase6_analyzer import (
    Phase6Analyzer,
    Phase6AnalyzerError,
    InvalidVarnaError,
    InvalidVowelError,
    EmptySequenceError,
    NoActiveConsonantError,
    analyze_sequence as phase6_analyze_sequence,
    compare_trajectories,
)

__all__ = [
    # Original Phase-5
    "SequenceAnalyzer",
    "PressureState",
    "TraceEntry",
    "analyze_sequence",
    # Phase-6 types
    "VowelScope",
    "TokenType",
    "EventType",
    "TrajectoryStep",
    "SequenceConfig",
    "TrajectoryResult",
    "PHASE6_VOWEL_DELTAS",
    "PHASE6_VOWELS",
    "BASELINE_MAGNITUDE",
    # Phase-6 analyzer
    "Phase6Analyzer",
    "Phase6AnalyzerError",
    "InvalidVarnaError",
    "InvalidVowelError",
    "EmptySequenceError",
    "NoActiveConsonantError",
    "phase6_analyze_sequence",
    "compare_trajectories",
]
