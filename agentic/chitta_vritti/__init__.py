"""Chitta-Vṛtti Module: Cross-Layer Coherence and Cognitive Mode Analysis.

This module computes the 5-element vṛtti distribution p_v[v] from cross-layer
representational coherence. This distribution feeds the core aspect resonance
formula via the R[v,a] coupling matrix.

The five cognitive modes (citta-vṛtti) from Patañjali's Yoga Sutras:
- Pramāṇa: Valid cognition (high coherence, low entropy, stable motion)
- Viparyaya: Misperception (confident opposition between layers)
- Vikalpa: Conceptual branching (high entropy, uneven agreement)
- Smṛti: Memory persistence (unchanged state despite new input)
- Nidrā: Dormancy (missing or weak representations)

Version: 2.8
"""

from agentic.chitta_vritti.types import (
    ChittaVrittiInputs,
    ChittaVrittiResult,
    OptimizedConfig,
    CONSUMER_CONFIG,
    ENTERPRISE_CONFIG,
)
from agentic.chitta_vritti.engine import ChittaVrittiEngine

__all__ = [
    "ChittaVrittiInputs",
    "ChittaVrittiResult",
    "OptimizedConfig",
    "ChittaVrittiEngine",
    "CONSUMER_CONFIG",
    "ENTERPRISE_CONFIG",
]
