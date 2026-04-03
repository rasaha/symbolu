"""
SOULPI Temporal Analysis & Cross-Domain Intelligence Module
============================================================

This module provides temporal tracking and cross-domain pattern intelligence
for the SymbolU consciousness analysis framework.

Main Classes:
- TemporalBhavaTracker: Tracks consciousness state evolution over time
- CrossDomainIntelligence: Detects universal patterns and transfers them across domains
- CrossDomainPatternTracker (P38): Stateful temporal pattern tracking with lifecycle
  events, boundary trajectories, sequence grammar, and aspect derivation

Version: 2.8 (Phase 3 + P38)
"""

from .temporal_bhava_tracker import TemporalBhavaTracker, TemporalEntry, TemporalState
from .cross_domain_intelligence import CrossDomainIntelligence, PatternConfig
from .cross_domain_pattern_tracker import (
    CrossDomainPatternTracker,
    PatternSnapshot,
    PatternEvent,
    BoundaryProximity,
    SequenceMatch,
    PatternTrackerReport,
)
from .pattern_sequence_rules import PatternSequenceRule, PATTERN_SEQUENCES
from .pattern_aspect_derivation import derive_aspect_vector

__all__ = [
    "TemporalBhavaTracker",
    "TemporalEntry",
    "TemporalState",
    "CrossDomainIntelligence",
    "PatternConfig",
    # P38
    "CrossDomainPatternTracker",
    "PatternSnapshot",
    "PatternEvent",
    "BoundaryProximity",
    "SequenceMatch",
    "PatternTrackerReport",
    "PatternSequenceRule",
    "PATTERN_SEQUENCES",
    "derive_aspect_vector",
]

__version__ = "2.8.0"
