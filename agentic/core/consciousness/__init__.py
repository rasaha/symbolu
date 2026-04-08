"""
Phase 26: Unified Consciousness Formula (UCF) - Core Consciousness Module

This module provides the canonical implementation of the UCF scalar metric
that unifies cognitive stability signals into a single authoritative value.

UCF answers one question: "How internally coherent and stable is the system's
cognitive state right now?"

CRITICAL INVARIANTS:
    - INV-P26-1: UCF is read-only truth, not a decision
    - INV-P26-2: Observer data cannot affect UCF
    - INV-P26-3: UCF monotonic with respect to instability
    - INV-P26-4: UCF never opens gates directly
    - INV-P26-5: Absence of optional inputs never destabilizes output

UCF is:
    - Numeric (float [0.0, 1.0])
    - Deterministic (same inputs -> identical outputs, bitwise)
    - Authoritative as a metric
    - NOT authoritative as a decision

UCF MUST NOT:
    - Decide regime
    - Gate insight
    - Select discourse
    - Influence lexical choice
    - Trigger actions

UCF MAY import:
    - CoherenceState (P10/P12 outputs)
    - Temporal metrics (P18, P19)
    - Identity harmonics (if present)
    - Schema stability metrics (P33)

UCF MUST NOT import:
    - P6-P9 (regime, discourse, semantics, lexical)
    - P21 delivery logic
    - Renderer, DHA, Persona
    - Observer-only phases (P22-P24)
"""

from agentic.core.consciousness.ucf_schema import (
    # Version
    P26_VERSION,
    # Enums
    StabilityBand,
    # Dataclasses
    UnifiedConsciousnessState,
    # Constants
    UCF_WEIGHTS,
    STABILITY_THRESHOLDS,
)

from agentic.core.consciousness.ucf_formula import (
    compute_ucf,
    compute_stability_band,
    clamp,
)

from agentic.core.consciousness.ucf_resolver import (
    UCFResolver,
    get_ucf_resolver,
)

__all__ = [
    # Version
    "P26_VERSION",
    # Enums
    "StabilityBand",
    # Dataclasses
    "UnifiedConsciousnessState",
    # Constants
    "UCF_WEIGHTS",
    "STABILITY_THRESHOLDS",
    # Functions
    "compute_ucf",
    "compute_stability_band",
    "clamp",
    # Classes
    "UCFResolver",
    "get_ucf_resolver",
]
