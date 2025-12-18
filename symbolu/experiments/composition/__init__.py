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
"""

from symbolu.experiments.composition.sequence_analyzer import (
    SequenceAnalyzer,
    PressureState,
    TraceEntry,
    analyze_sequence,
)

__all__ = [
    "SequenceAnalyzer",
    "PressureState",
    "TraceEntry",
    "analyze_sequence",
]
