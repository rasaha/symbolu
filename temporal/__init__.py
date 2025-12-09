"""
SOULPI Temporal Analysis & Cross-Domain Intelligence Module
============================================================

This module provides temporal tracking and cross-domain pattern intelligence
for the SymbolU consciousness analysis framework.

Main Classes:
- TemporalBhavaTracker: Tracks consciousness state evolution over time
- CrossDomainIntelligence: Detects universal patterns and transfers them across domains

Version: 2.7 (Phase 3)
"""

from .temporal_bhava_tracker import TemporalBhavaTracker, TemporalEntry
from .cross_domain_intelligence import CrossDomainIntelligence, PatternConfig

__all__ = [
    "TemporalBhavaTracker",
    "TemporalEntry",
    "CrossDomainIntelligence",
    "PatternConfig",
]

__version__ = "2.7.0"
