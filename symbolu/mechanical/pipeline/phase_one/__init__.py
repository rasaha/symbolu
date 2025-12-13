"""
PO3 — Intent → Allowed Action Contract
(Implemented as phase_one for backward compatibility)

PO3 sits between PO2 (Intent Envelope & Response Posture) and the Planner.
It consumes the IntentEnvelope and produces an AllowedActionSet that
strictly bounds what action classes the Planner may propose.

PO phases are pre-acoustic governance layers and precede symbolic processing (P1+).

Components:
- AllowedActionSet: Output dataclass with eligible actions
- PhaseOneResolver: Deterministic resolution engine
- INTENT_TO_ACTIONS: Canonical mapping table

Usage:
    from symbolu.mechanical.pipeline.phase_one import (
        PhaseOneResolver,
        AllowedActionSet,
        INTENT_TO_ACTIONS,
    )

    resolver = PhaseOneResolver()
    allowed_actions = resolver.resolve(intent_envelope)

Authority Model:
- PO3 receives authority from PO2 IntentEnvelope
- PO3 constrains planner eligibility, not behavior
- PlannerGate remains final authority on action execution
"""

from .phase_one_schema import AllowedActionSet
from .phase_one_resolver import PhaseOneResolver, INTENT_TO_ACTIONS


__all__ = [
    # Dataclasses
    "AllowedActionSet",
    # Resolver
    "PhaseOneResolver",
    # Mapping
    "INTENT_TO_ACTIONS",
]
