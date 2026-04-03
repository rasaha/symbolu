"""Chitta-Vṛtti Module: Cross-Layer Coherence and Cognitive Mode Analysis.

CANONICAL RUNTIME VRITTI AUTHORITY (cross-layer coherence level)
================================================================
This module is the canonical source of runtime vṛtti computation at the
cross-layer coherence level. All runtime consumers needing coherence-derived
vṛtti distributions should use this module.

Complementary vritti source:
- agentic/core/smi/vritti_mapping.py computes phonemic/syllable-level vritti
  (syllable → consonant → kosha → vritti). That is a different abstraction
  level and is NOT a duplicate — it is complementary.

Training-time note:
- sovereign/vritti.py may maintain a separate PyTorch-differentiable vritti
  implementation for gradient requirements. That is intentional divergence
  for training, not runtime duplication.

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
