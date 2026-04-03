"""
PO5 — Planner Execution Gate Schema Definitions

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

Design Principles:
- Deterministic: No LLM calls, no probabilistic sampling
- Governance-Only: Reads upstream state, produces eligibility verdict
- Authority-Respecting: Cannot override PO1–PO4 constraints
- Non-Actuating: ELIGIBLE is informational only; no executor exists

Authority Model:
- Authority flows: PO1 → PO2 → PO3 → PO4 → PO5 → (NO EXECUTION)
- PO5 receives authority from PO2 IntentEnvelope and PO4 PlannerProposalEnvelope
- PO5 cannot override or expand upstream decisions
- PO5 produces ExecutionEligibilityEnvelope for audit/observability only
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict

from symbolu_core.mechanical.pipeline.phase_zero.phase_zero_schema import IntentType
from symbolu_core.mechanical.pipeline.phase_po4.po4_schema import ProposalStatus


# ============================================================================
# ENUMS - Execution eligibility classification
# ============================================================================


class ExecutionEligibility(str, Enum):
    """
    Execution eligibility status determined by PO5.

    PROHIBITED: Execution is not permitted in this context
    DEFERRED: Execution eligibility is deferred (requires further conditions)
    ELIGIBLE: Execution would be conceptually eligible (informational only)

    CRITICAL: ELIGIBLE is purely informational. No executor exists in the
    Symbol-U architecture at this phase. PO5 is non-actuating.
    """
    PROHIBITED = "PROHIBITED"
    DEFERRED = "DEFERRED"
    ELIGIBLE = "ELIGIBLE"


# ============================================================================
# DATACLASSES - Core envelope object
# ============================================================================


@dataclass(frozen=True)
class ExecutionEligibilityEnvelope:
    """
    PO5 output envelope: Execution eligibility verdict.

    This envelope is read-only and captures the governance decision about
    whether execution would be conceptually permitted. It does NOT enable,
    trigger, or perform any execution.

    Invariants:
    - PROHIBITED ⇒ no execution permitted (hard constraint)
    - DEFERRED ⇒ eligibility requires further conditions
    - ELIGIBLE ⇒ informational only (no executor exists)
    - reason must always be a non-empty string

    Attributes:
        eligibility: The execution eligibility status
        reason: Human-readable explanation of the eligibility decision
        intent: The source IntentType from PO2
        proposal_status: The proposal status from PO4
        architectural_phase: Identifier for this governance phase ("PO5")
        debug: Additional debug/trace information
    """
    eligibility: ExecutionEligibility
    reason: str
    intent: IntentType
    proposal_status: ProposalStatus
    architectural_phase: str = "PO5"

    # Debug/trace information
    debug: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate ExecutionEligibilityEnvelope invariants."""
        # Eligibility must be set
        if self.eligibility is None:
            raise ValueError("ExecutionEligibilityEnvelope.eligibility cannot be None")

        # Reason must be a non-empty string
        if not isinstance(self.reason, str) or not self.reason.strip():
            raise ValueError(
                "ExecutionEligibilityEnvelope.reason must be a non-empty string"
            )

        # Intent must be set
        if self.intent is None:
            raise ValueError("ExecutionEligibilityEnvelope.intent cannot be None")

        # Proposal status must be set
        if self.proposal_status is None:
            raise ValueError(
                "ExecutionEligibilityEnvelope.proposal_status cannot be None"
            )

        # Validate eligibility is a valid enum value
        if not isinstance(self.eligibility, ExecutionEligibility):
            raise ValueError(
                f"ExecutionEligibilityEnvelope.eligibility must be ExecutionEligibility, "
                f"got {type(self.eligibility).__name__}"
            )

        # Validate intent is a valid enum value
        if not isinstance(self.intent, IntentType):
            raise ValueError(
                f"ExecutionEligibilityEnvelope.intent must be IntentType, "
                f"got {type(self.intent).__name__}"
            )

        # Validate proposal_status is a valid enum value
        if not isinstance(self.proposal_status, ProposalStatus):
            raise ValueError(
                f"ExecutionEligibilityEnvelope.proposal_status must be ProposalStatus, "
                f"got {type(self.proposal_status).__name__}"
            )

    def is_prohibited(self) -> bool:
        """Check if execution is prohibited."""
        return self.eligibility == ExecutionEligibility.PROHIBITED

    def is_deferred(self) -> bool:
        """Check if execution eligibility is deferred."""
        return self.eligibility == ExecutionEligibility.DEFERRED

    def is_eligible(self) -> bool:
        """
        Check if execution would be conceptually eligible.

        IMPORTANT: ELIGIBLE is informational only. No executor exists.
        This method does NOT enable or trigger any execution.
        """
        return self.eligibility == ExecutionEligibility.ELIGIBLE

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for logging/tracing."""
        return {
            "eligibility": self.eligibility.value,
            "reason": self.reason,
            "intent": self.intent.value,
            "proposal_status": self.proposal_status.value,
            "architectural_phase": self.architectural_phase,
            "debug": self.debug,
        }


# Public exports
__all__ = [
    # Enums
    "ExecutionEligibility",
    # Dataclasses
    "ExecutionEligibilityEnvelope",
]
