"""
Phase 0: Intent Envelope & Act-Type Selection

Phase 0 sits between Phase −1 (Observer-Observed Grounding) and the Planner.
It consumes the PhaseMinusOneEnvelope and produces an IntentEnvelope that
determines the appropriate response posture.

Components:
- IntentType: Enum classifying communicative intent
- ResponsePosture: Enum for system response posture
- IntentEnvelope: Output dataclass with intent and posture
- PhaseZeroResolver: Deterministic resolution engine

Usage:
    from symbolu.mechanical.pipeline.phase_zero import (
        PhaseZeroResolver,
        IntentEnvelope,
        IntentType,
        ResponsePosture,
    )

    resolver = PhaseZeroResolver()
    intent_envelope = resolver.resolve(phase_minus_one_envelope)
"""

from .phase_zero_schema import (
    IntentType,
    ResponsePosture,
    IntentEnvelope,
    INTENT_TO_POSTURE,
)

from .phase_zero_resolver import PhaseZeroResolver


__all__ = [
    # Enums
    "IntentType",
    "ResponsePosture",
    # Mapping
    "INTENT_TO_POSTURE",
    # Dataclasses
    "IntentEnvelope",
    # Resolver
    "PhaseZeroResolver",
]
