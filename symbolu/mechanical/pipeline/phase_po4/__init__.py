"""
PO4 — Planner Proposal Envelope

PO4 sits after PO3 (Intent → Allowed Action Contract) and before any
planner execution or symbolic reasoning.

PO4's responsibility is to:
- Capture what the planner is attempting to do
- Enforce that proposals are consistent with PO3 allow-lists
- Prevent execution, reasoning, or side effects
- Provide full auditability of proposed vs allowed actions

PO4 does NOT:
- Execute actions
- Modify intent
- Modify grounding
- Perform reasoning
- Call LLMs

PO phases are pre-acoustic governance layers and precede symbolic processing (P1+).

Components:
- PlannerProposalEnvelope: Output dataclass capturing validated proposals
- ProposalStatus: Enum for VALID/PARTIALLY_ALLOWED/BLOCKED
- PO4Resolver: Deterministic resolution engine

Usage:
    from symbolu.mechanical.pipeline.phase_po4 import (
        PO4Resolver,
        PlannerProposalEnvelope,
        ProposalStatus,
    )

    resolver = PO4Resolver()
    envelope = resolver.resolve(intent_envelope, allowed_action_set, proposed_actions)
    # envelope.status indicates VALID / PARTIALLY_ALLOWED / BLOCKED

Authority Model:
- PO4 receives authority from PO2 IntentEnvelope and PO3 AllowedActionSet
- PO4 wraps and validates planner proposals (read-only governance)
- PO4 cannot override PO1–PO3 decisions
- No execution occurs at this phase
"""

from .po4_schema import (
    ProposalStatus,
    PlannerProposalEnvelope,
)
from .po4_resolver import PO4Resolver


__all__ = [
    # Enums
    "ProposalStatus",
    # Dataclasses
    "PlannerProposalEnvelope",
    # Resolver
    "PO4Resolver",
]
