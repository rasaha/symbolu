"""
Lightweight Phase Transformer — canonical, auditable, dependency-light reference.

This package is the canonical research implementation of Phase attention. It is
built from scratch against ``docs/PHASE_QUAD_LOCAL_ATTENTION_ALGORITHM.md`` and
the production ``PhaseAttentionLayer`` (reference only — never copied).

It deliberately excludes: quadratic attention, Top-K/Quad retrieval, the
production BindingCacheQuadQuery, controllers, governance, and ontological
systems. See ``reference_equations.md`` for the frozen mathematics.

Stages (each independently frozen — see frozen_manifest.json):
    v1.0  Phase Core            (phase_core)
    v1.1  Streaming Phase       (streaming)
    v1.2  Decay Phase           (phase_core decay + config)
    v1.3  Phase Transformer     (phase_block)
    v1.4  Local + Phase         (local_window, phase_block)
    v1.5  Phase + Binding        (binding_slots)  [structure + complexity frozen]
"""

from .config import PhaseConfig, TransformerConfig
from .phase_core import LightweightPhaseAttention, PhaseState, PhaseOutput

__all__ = [
    "PhaseConfig",
    "TransformerConfig",
    "LightweightPhaseAttention",
    "PhaseState",
    "PhaseOutput",
]

__version__ = "1.2.0"
