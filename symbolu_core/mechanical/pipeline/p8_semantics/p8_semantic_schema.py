"""
P8 - Semantic Slot Resolution Schema Definitions

P8 is a post-discourse, pre-lexical phase.
It determines WHAT MEANINGS must be expressed, not how they are worded.
It constructs a Semantic Slot Map based on the selected Discourse Act.

P8's responsibility is to:
- Resolve which semantic slots are required for the discourse act
- Produce a read-only SemanticFrame that constrains downstream lexical selection

P8 does NOT:
- Select words, syntax, or sentence structure
- Perform lexical selection
- Execute actions
- Call LLMs
- Introduce probabilistic behavior
- Hallucinate slot values

Design Principles:
- Deterministic: No LLM calls, no probabilistic sampling
- Conservative: Leave slot values as None if information is missing
- Authority-Respecting: Cannot override PO1-P7 constraints
- Strict Allow-List: Only slots allowed by discourse act may be populated

Authority Model:
- Authority flows: PO1 -> PO2 -> PO3 -> PO4 -> PO5 -> P6 -> P7 -> P8 -> (Lexical layers)
- P8 receives signals from PO1 (grounding), PO2 (intent), P6 (regime), P7 (discourse)
- P8 cannot override or expand upstream decisions
- P8 produces SemanticFrame for downstream lexical generation constraints
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, FrozenSet, Optional

from symbolu_core.mechanical.pipeline.p7_discourse.p7_discourse_schema import DiscourseAct


# ============================================================================
# ENUMS - Semantic slot classification
# ============================================================================


class SemanticSlot(str, Enum):
    """
    Abstract meaning containers for semantic slot resolution.

    These are abstract meaning containers, NOT words or syntax.
    P8 determines which slots must be filled, not how to word them.

    AGENT: The entity performing the action or being described
    TARGET: The entity being acted upon or referenced
    STATE: The condition or status being expressed
    CAUSE: The reason or explanation (restricted under CAREFUL regime)
    TEMPORAL_CONTEXT: Time-related information
    UNCERTAINTY: Epistemic markers about certainty level
    LIMITATION: Boundaries or constraints on capability/knowledge
    REQUEST_FOCUS: What information is being requested (for questions)
    CONSTRAINT: Rules or restrictions that apply
    """
    AGENT = "AGENT"
    TARGET = "TARGET"
    STATE = "STATE"
    CAUSE = "CAUSE"
    TEMPORAL_CONTEXT = "TEMPORAL_CONTEXT"
    UNCERTAINTY = "UNCERTAINTY"
    LIMITATION = "LIMITATION"
    REQUEST_FOCUS = "REQUEST_FOCUS"
    CONSTRAINT = "CONSTRAINT"


# ============================================================================
# SLOT ALLOW-LISTS - Strict governance by discourse act
# ============================================================================


# Which semantic slots are allowed for each discourse act
# This is the MANDATORY allow-list: if not in this set, slot is FORBIDDEN
DISCOURSE_ACT_ALLOWED_SLOTS: Dict[DiscourseAct, FrozenSet[SemanticSlot]] = {
    DiscourseAct.QUESTION: frozenset({
        SemanticSlot.REQUEST_FOCUS,
        SemanticSlot.TARGET,
        SemanticSlot.TEMPORAL_CONTEXT,
    }),
    DiscourseAct.REFLECTION: frozenset({
        SemanticSlot.AGENT,
        SemanticSlot.STATE,
        SemanticSlot.UNCERTAINTY,
    }),
    DiscourseAct.ACKNOWLEDGMENT: frozenset({
        SemanticSlot.AGENT,
        SemanticSlot.STATE,
    }),
    DiscourseAct.EXPLANATION: frozenset({
        SemanticSlot.AGENT,
        SemanticSlot.STATE,
        SemanticSlot.CAUSE,
        SemanticSlot.CONSTRAINT,
        SemanticSlot.LIMITATION,
    }),
    DiscourseAct.INSTRUCTION: frozenset({
        SemanticSlot.AGENT,
        SemanticSlot.TARGET,
        SemanticSlot.CONSTRAINT,
        SemanticSlot.TEMPORAL_CONTEXT,
    }),
    DiscourseAct.DEFERRAL: frozenset({
        SemanticSlot.LIMITATION,
        SemanticSlot.REQUEST_FOCUS,
    }),
}


# ============================================================================
# DATACLASSES - Core envelope objects
# ============================================================================


@dataclass(frozen=True)
class SemanticFrame:
    """
    P8 output envelope: Semantic slot resolution verdict.

    This envelope is read-only and captures the semantic slot map that
    constrains all downstream lexical/language generation. It does NOT perform
    any lexical selection, word choice, or syntax construction.

    Invariants:
    - slots dictionary contains ONLY allowed slots for the discourse act
    - slot values are None if information is missing (conservative default)
    - allowed = True only if all constraints are satisfied
    - reason must always be a non-empty string

    Attributes:
        discourse_act: The source DiscourseAct from P7
        slots: Dictionary mapping allowed slots to their values (None if unknown)
        allowed: Whether the semantic frame is permitted (False means constrained)
        reason: Human-readable explanation of the resolution
        evidence: Grammar/linguistic evidence that supported (but didn't determine) values
        architectural_phase: Identifier for this phase ("P8")
        debug: Additional debug/trace information
    """
    discourse_act: DiscourseAct
    slots: Dict[SemanticSlot, Optional[str]]
    allowed: bool
    reason: str
    evidence: Dict[str, Any] = field(default_factory=dict)
    architectural_phase: str = "P8"

    # Debug/trace information
    debug: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate SemanticFrame invariants."""
        # Discourse act must be set
        if self.discourse_act is None:
            raise ValueError("SemanticFrame.discourse_act cannot be None")

        # Reason must be a non-empty string
        if not isinstance(self.reason, str) or not self.reason.strip():
            raise ValueError(
                "SemanticFrame.reason must be a non-empty string"
            )

        # Slots must be a dictionary
        if self.slots is None:
            raise ValueError("SemanticFrame.slots cannot be None")

        # Validate discourse_act is a valid enum value
        if not isinstance(self.discourse_act, DiscourseAct):
            raise ValueError(
                f"SemanticFrame.discourse_act must be DiscourseAct, "
                f"got {type(self.discourse_act).__name__}"
            )

        # Validate all slot keys are valid SemanticSlot enum values
        for slot_key in self.slots:
            if not isinstance(slot_key, SemanticSlot):
                raise ValueError(
                    f"SemanticFrame.slots keys must be SemanticSlot, "
                    f"got {type(slot_key).__name__}"
                )

        # Validate slots are from the allow-list for this discourse act
        allowed_slots = DISCOURSE_ACT_ALLOWED_SLOTS.get(
            self.discourse_act, frozenset()
        )
        for slot_key in self.slots:
            if slot_key not in allowed_slots:
                raise ValueError(
                    f"SemanticFrame: slot {slot_key.value} is not allowed for "
                    f"discourse act {self.discourse_act.value}. "
                    f"Allowed slots: {sorted([s.value for s in allowed_slots])}"
                )

    def is_deferral_frame(self) -> bool:
        """Check if this is a DEFERRAL semantic frame."""
        return self.discourse_act == DiscourseAct.DEFERRAL

    def has_slot(self, slot: SemanticSlot) -> bool:
        """Check if a slot exists in this frame (may be None)."""
        return slot in self.slots

    def get_slot_value(self, slot: SemanticSlot) -> Optional[str]:
        """Get the value of a slot, or None if not present."""
        return self.slots.get(slot)

    def get_populated_slots(self) -> Dict[SemanticSlot, str]:
        """Get only slots that have non-None values."""
        return {k: v for k, v in self.slots.items() if v is not None}

    def get_empty_slots(self) -> FrozenSet[SemanticSlot]:
        """Get slots that exist but have None values."""
        return frozenset(k for k, v in self.slots.items() if v is None)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for logging/tracing."""
        return {
            "discourse_act": self.discourse_act.value,
            "slots": {k.value: v for k, v in self.slots.items()},
            "allowed": self.allowed,
            "reason": self.reason,
            "evidence": self.evidence,
            "architectural_phase": self.architectural_phase,
            "debug": self.debug,
            "populated_count": len(self.get_populated_slots()),
            "empty_count": len(self.get_empty_slots()),
        }


# Public exports
__all__ = [
    # Enums
    "SemanticSlot",
    # Constants
    "DISCOURSE_ACT_ALLOWED_SLOTS",
    # Dataclasses
    "SemanticFrame",
]
