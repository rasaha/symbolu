"""
PO4 — Planner Proposal Envelope Schema Definitions

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

Design Principles:
- Deterministic: No LLM calls, no probabilistic sampling
- Governance-Only: Wraps planner outputs, never executes
- Authority-Respecting: Cannot override PO1–PO3 constraints
- Auditable: Full traceability of proposed vs allowed actions

Authority Model:
- Authority flows: PO1 → PO2 → PO3 → PO4 → (Planner execution not yet allowed)
- PO4 receives authority from PO3 AllowedActionSet
- PO4 cannot override or expand PO3 decisions
- PO4 captures planner proposals for governance review
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, FrozenSet, List, Optional

from symbolu.mechanical.pipeline.phase_zero.phase_zero_schema import IntentType
from symbolu.mechanical.pipeline.governance.planner_gate import ActionClass


# ============================================================================
# ENUMS - Proposal validation status
# ============================================================================


class ProposalStatus(str, Enum):
    """
    Status of a planner proposal after PO4 validation.

    VALID: All proposed actions are in the PO3 allow-list
    PARTIALLY_ALLOWED: Some proposed actions are allowed, some rejected
    BLOCKED: No proposed actions are allowed (or PO3 was blocked)
    """
    VALID = "VALID"
    PARTIALLY_ALLOWED = "PARTIALLY_ALLOWED"
    BLOCKED = "BLOCKED"


# ============================================================================
# DATACLASSES - Core envelope object
# ============================================================================


@dataclass(frozen=True)
class PlannerProposalEnvelope:
    """
    PO4 output envelope: Planner proposal captured and validated against PO3.

    This envelope wraps the planner's proposed actions and validates them
    against the PO3 allow-list. It does NOT execute any actions or modify
    any upstream state.

    Invariants:
    - allowed_actions ⊆ PO3 allow-list (subset of PO3 allowed actions)
    - rejected_actions must include reason for each rejection
    - BLOCKED ⇒ allowed_actions is empty
    - All proposed_actions = allowed_actions ∪ rejected_actions.keys()

    Attributes:
        intent: The source IntentType from PO2/PO3
        allowed_actions: Actions that passed PO3 validation (subset of proposed)
        proposed_actions: All actions the planner attempted to propose
        rejected_actions: Actions rejected with reasons (Dict[ActionClass, str])
        status: ProposalStatus indicating validation result
        blocked_reason: If BLOCKED, the reason for blocking
        architectural_phase: Identifier for this governance phase ("PO4")
    """
    intent: IntentType
    allowed_actions: FrozenSet[ActionClass]
    proposed_actions: FrozenSet[ActionClass]
    rejected_actions: Dict[ActionClass, str]
    status: ProposalStatus
    blocked_reason: Optional[str] = None
    architectural_phase: str = "PO4"

    # Debug/trace information
    debug: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate PlannerProposalEnvelope invariants."""
        # Intent must be set
        if self.intent is None:
            raise ValueError("PlannerProposalEnvelope.intent cannot be None")

        # Status must be set
        if self.status is None:
            raise ValueError("PlannerProposalEnvelope.status cannot be None")

        # Validate allowed_actions is a frozenset
        if not isinstance(self.allowed_actions, frozenset):
            raise ValueError(
                f"PlannerProposalEnvelope.allowed_actions must be a frozenset, "
                f"got {type(self.allowed_actions).__name__}"
            )

        # Validate proposed_actions is a frozenset
        if not isinstance(self.proposed_actions, frozenset):
            raise ValueError(
                f"PlannerProposalEnvelope.proposed_actions must be a frozenset, "
                f"got {type(self.proposed_actions).__name__}"
            )

        # Validate rejected_actions is a dict
        if not isinstance(self.rejected_actions, dict):
            raise ValueError(
                f"PlannerProposalEnvelope.rejected_actions must be a dict, "
                f"got {type(self.rejected_actions).__name__}"
            )

        # All elements in allowed_actions must be ActionClass
        for action in self.allowed_actions:
            if not isinstance(action, ActionClass):
                raise ValueError(
                    f"PlannerProposalEnvelope.allowed_actions must contain only ActionClass, "
                    f"got {type(action).__name__}"
                )

        # All elements in proposed_actions must be ActionClass
        for action in self.proposed_actions:
            if not isinstance(action, ActionClass):
                raise ValueError(
                    f"PlannerProposalEnvelope.proposed_actions must contain only ActionClass, "
                    f"got {type(action).__name__}"
                )

        # All keys in rejected_actions must be ActionClass
        for action in self.rejected_actions.keys():
            if not isinstance(action, ActionClass):
                raise ValueError(
                    f"PlannerProposalEnvelope.rejected_actions keys must be ActionClass, "
                    f"got {type(action).__name__}"
                )

        # All values in rejected_actions must be non-empty strings
        for action, reason in self.rejected_actions.items():
            if not isinstance(reason, str) or not reason.strip():
                raise ValueError(
                    f"PlannerProposalEnvelope.rejected_actions must have non-empty string reasons, "
                    f"got '{reason}' for {action.value}"
                )

        # Invariant: allowed_actions must be subset of proposed_actions
        if not self.allowed_actions.issubset(self.proposed_actions):
            extra = self.allowed_actions - self.proposed_actions
            raise ValueError(
                f"allowed_actions must be subset of proposed_actions, "
                f"found extra actions: {[a.value for a in extra]}"
            )

        # Invariant: rejected_actions keys must be subset of proposed_actions
        rejected_set = frozenset(self.rejected_actions.keys())
        if not rejected_set.issubset(self.proposed_actions):
            extra = rejected_set - self.proposed_actions
            raise ValueError(
                f"rejected_actions keys must be subset of proposed_actions, "
                f"found extra actions: {[a.value for a in extra]}"
            )

        # Invariant: allowed and rejected should partition proposed
        # (no action can be both allowed AND rejected)
        overlap = self.allowed_actions & rejected_set
        if overlap:
            raise ValueError(
                f"Action cannot be both allowed and rejected: {[a.value for a in overlap]}"
            )

        # Invariant: BLOCKED ⇒ allowed_actions must be empty
        if self.status == ProposalStatus.BLOCKED and len(self.allowed_actions) > 0:
            raise ValueError(
                "BLOCKED status requires allowed_actions to be empty, "
                f"got {len(self.allowed_actions)} actions"
            )

        # Invariant: BLOCKED ⇒ blocked_reason must be set
        if self.status == ProposalStatus.BLOCKED and not self.blocked_reason:
            raise ValueError("BLOCKED status requires blocked_reason to be set")

        # Invariant: VALID ⇒ no rejected actions
        if self.status == ProposalStatus.VALID and len(self.rejected_actions) > 0:
            raise ValueError(
                "VALID status requires no rejected_actions, "
                f"got {len(self.rejected_actions)} rejected"
            )

    def is_blocked(self) -> bool:
        """Check if the proposal is completely blocked."""
        return self.status == ProposalStatus.BLOCKED

    def is_valid(self) -> bool:
        """Check if all proposed actions were allowed."""
        return self.status == ProposalStatus.VALID

    def is_partial(self) -> bool:
        """Check if only some proposed actions were allowed."""
        return self.status == ProposalStatus.PARTIALLY_ALLOWED

    def allowed_count(self) -> int:
        """Return the number of allowed actions."""
        return len(self.allowed_actions)

    def rejected_count(self) -> int:
        """Return the number of rejected actions."""
        return len(self.rejected_actions)

    def proposed_count(self) -> int:
        """Return the number of proposed actions."""
        return len(self.proposed_actions)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for logging/tracing."""
        return {
            "intent": self.intent.value,
            "status": self.status.value,
            "allowed_actions": sorted([a.value for a in self.allowed_actions]),
            "proposed_actions": sorted([a.value for a in self.proposed_actions]),
            "rejected_actions": {
                a.value: reason for a, reason in self.rejected_actions.items()
            },
            "allowed_count": self.allowed_count(),
            "rejected_count": self.rejected_count(),
            "proposed_count": self.proposed_count(),
            "blocked_reason": self.blocked_reason,
            "architectural_phase": self.architectural_phase,
            "debug": self.debug,
        }


# Public exports
__all__ = [
    # Enums
    "ProposalStatus",
    # Dataclasses
    "PlannerProposalEnvelope",
]
