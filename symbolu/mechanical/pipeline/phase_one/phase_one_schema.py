"""
PO3 — Intent → Allowed Action Contract Schema Definitions
(Implemented as phase_one for backward compatibility)

PO3 sits between PO2 (Intent Envelope & Response Posture) and the Planner.
It consumes the IntentEnvelope and produces an AllowedActionSet that
strictly bounds what action classes the Planner may propose.

PO phases are pre-acoustic governance layers and precede symbolic processing (P1+).

Design Principles:
- Deterministic: No LLM calls, no probabilistic sampling
- Authority Layer: Constrains planner eligibility, not behavior
- Strict: No fallback logic, no dynamic expansion
- Finite: AllowedActionSet is always a finite, known set

Authority Model:
- PO3 receives authority from PO2 IntentEnvelope
- PO3 constrains what actions the Planner may even consider
- PlannerGate remains final authority on actual action execution
- Authority flows: PO1 → PO2 → PO3 → Planner → PlannerGate
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, FrozenSet

from symbolu.mechanical.pipeline.phase_zero.phase_zero_schema import IntentType
from symbolu.mechanical.pipeline.governance.planner_gate import ActionClass


@dataclass(frozen=True)
class AllowedActionSet:
    """
    PO3 output: The strict set of allowed action classes for the Planner.

    This is an authority constraint, not a suggestion. The Planner may ONLY
    propose actions from this set. Any action outside this set is not eligible
    for consideration.

    Invariants:
    - intent_type is always set (never None)
    - allowed_actions is a finite, immutable set
    - Empty set is valid (for ABSTAIN intent)
    - The set is deterministically derived from intent_type

    Attributes:
        intent_type: The source IntentType from PO2
        allowed_actions: Frozen set of eligible ActionClass values
        run_id: Unique identifier for tracing/debugging
        resolution_reason: Human-readable explanation of the binding
        debug: Additional debug/trace information
    """
    intent_type: IntentType
    allowed_actions: FrozenSet[ActionClass]
    run_id: str = ""
    resolution_reason: str = ""
    debug: Dict[str, Any] = field(default_factory=dict)

    # Architectural phase identifier (informational only, does not affect logic)
    architectural_phase: str = "PO3"

    def __post_init__(self) -> None:
        """Validate AllowedActionSet invariants."""
        # Intent type must be set
        if self.intent_type is None:
            raise ValueError("AllowedActionSet.intent_type cannot be None")

        # Allowed actions must be a frozenset
        if not isinstance(self.allowed_actions, frozenset):
            raise ValueError(
                f"AllowedActionSet.allowed_actions must be a frozenset, "
                f"got {type(self.allowed_actions).__name__}"
            )

        # All elements must be ActionClass
        for action in self.allowed_actions:
            if not isinstance(action, ActionClass):
                raise ValueError(
                    f"AllowedActionSet.allowed_actions must contain only ActionClass, "
                    f"got {type(action).__name__}"
                )

    def is_empty(self) -> bool:
        """Check if no actions are allowed (ABSTAIN case)."""
        return len(self.allowed_actions) == 0

    def is_action_allowed(self, action: ActionClass) -> bool:
        """Check if a specific action is in the allowed set."""
        return action in self.allowed_actions

    def count(self) -> int:
        """Return the number of allowed actions."""
        return len(self.allowed_actions)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for logging/tracing."""
        return {
            "intent_type": self.intent_type.value,
            "allowed_actions": sorted([a.value for a in self.allowed_actions]),
            "action_count": len(self.allowed_actions),
            "is_empty": self.is_empty(),
            "run_id": self.run_id,
            "resolution_reason": self.resolution_reason,
            "debug": self.debug,
        }


# Public exports
__all__ = [
    "AllowedActionSet",
]
