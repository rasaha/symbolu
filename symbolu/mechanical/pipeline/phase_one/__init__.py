"""
Phase 1: Intent → Allowed Action Binding

Phase 1 sits between Phase 0 (Intent Envelope) and the Planner.
It consumes the IntentEnvelope and produces an AllowedActionSet that
strictly bounds what action classes the Planner may propose.

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
- Phase 1 receives authority from Phase 0 IntentEnvelope
- Phase 1 constrains planner eligibility, not behavior
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
