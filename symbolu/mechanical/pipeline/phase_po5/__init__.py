"""
PO5 — Planner Execution Gate

PO5 sits after PO4 (Planner Proposal Envelope) and before any acoustic/symbolic
processing or agent systems.

PO5's responsibility is to:
- Determine if execution is conceptually permitted in this context
- Produce a read-only eligibility verdict

PO5 does NOT:
- Execute actions
- Schedule actions
- Trigger tools
- Modify intent, grounding, or proposals
- Perform reasoning or semantics
- Call LLMs

PO phases are pre-acoustic governance layers and precede symbolic processing (P1+).

Components:
- ExecutionEligibilityEnvelope: Output dataclass capturing eligibility verdict
- ExecutionEligibility: Enum for PROHIBITED/DEFERRED/ELIGIBLE
- PO5ExecutionGate: Deterministic evaluation gate

CRITICAL: ELIGIBLE is informational only. No executor exists in the Symbol-U
architecture at this phase. PO5 is non-actuating.

Usage:
    from symbolu.mechanical.pipeline.phase_po5 import (
        PO5ExecutionGate,
        ExecutionEligibilityEnvelope,
        ExecutionEligibility,
    )

    gate = PO5ExecutionGate()
    envelope = gate.evaluate(intent_envelope, proposal, overall_policy)
    # envelope.eligibility indicates PROHIBITED / DEFERRED / ELIGIBLE
    # ELIGIBLE is informational only; no execution occurs

Authority Model:
- PO5 receives authority from PO2 IntentEnvelope, PO4 PlannerProposalEnvelope
- PO5 evaluates eligibility based on deterministic rules (read-only governance)
- PO5 cannot override PO1–PO4 decisions
- No execution occurs at this phase
"""

from .po5_schema import (
    ExecutionEligibility,
    ExecutionEligibilityEnvelope,
)
from .po5_gate import PO5ExecutionGate


__all__ = [
    # Enums
    "ExecutionEligibility",
    # Dataclasses
    "ExecutionEligibilityEnvelope",
    # Gate
    "PO5ExecutionGate",
]
