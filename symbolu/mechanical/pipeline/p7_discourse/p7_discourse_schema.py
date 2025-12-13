"""
P7 — Discourse Act Resolver Schema Definitions

P7 is a post-regime, pre-semantics phase.
It determines WHAT KIND OF UTTERANCE is allowed, not what it says.
It resolves the Discourse Act for the current turn.

P7's responsibility is to:
- Resolve the discourse act type based on intent, regime, and allowed actions
- Produce a read-only DiscourseEnvelope that constrains downstream language generation

P7 does NOT:
- Select words, syntax, or meaning slots
- Perform semantic interpretation
- Execute actions
- Call LLMs
- Introduce probabilistic behavior

Design Principles:
- Deterministic: No LLM calls, no probabilistic sampling
- Gating-Only: Reads upstream state, produces discourse act verdict
- Authority-Respecting: Cannot override PO1–P6 constraints
- Conservative: DEFERRAL is always safe, act may only restrict capability

Authority Model:
- Authority flows: PO1 → PO2 → PO3 → PO4 → PO5 → P6 → P7 → (Semantic layers)
- P7 receives signals from PO1 (grounding), PO2 (intent), PO3 (actions), P6 (regime)
- P7 cannot override or expand upstream decisions
- P7 produces DiscourseEnvelope for downstream semantic generation constraints
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict

from symbolu.mechanical.pipeline.phase_zero.phase_zero_schema import IntentType
from symbolu.mechanical.pipeline.phase_p6.p6_schema import OperationalRegime


# ============================================================================
# ENUMS - Discourse act classification
# ============================================================================


class DiscourseAct(str, Enum):
    """
    Classification of the allowed discourse act for this turn.

    QUESTION: Requesting clarification or information from user
    REFLECTION: Mirroring/validating user's perspective
    ACKNOWLEDGMENT: Simple recognition without analysis
    EXPLANATION: Providing informational/analytical content
    INSTRUCTION: Giving guidance or directives (restricted)
    DEFERRAL: Cannot proceed with any discourse act (safe default)

    DEFERRAL is always safe.
    Discourse act may only restrict, never expand capability.
    """
    QUESTION = "QUESTION"
    REFLECTION = "REFLECTION"
    ACKNOWLEDGMENT = "ACKNOWLEDGMENT"
    EXPLANATION = "EXPLANATION"
    INSTRUCTION = "INSTRUCTION"
    DEFERRAL = "DEFERRAL"


# ============================================================================
# DATACLASSES - Core envelope object
# ============================================================================


@dataclass(frozen=True)
class DiscourseEnvelope:
    """
    P7 output envelope: Discourse act resolution verdict.

    This envelope is read-only and captures the discourse act selection decision
    that constrains all downstream semantic/language generation. It does NOT perform
    any semantic processing, lexical selection, or execution.

    Invariants:
    - DEFERRAL is always safe
    - Discourse act may only restrict, never expand capability
    - reason must always be a non-empty string
    - act must be a valid DiscourseAct enum value

    Attributes:
        act: The resolved discourse act (QUESTION/REFLECTION/ACKNOWLEDGMENT/EXPLANATION/INSTRUCTION/DEFERRAL)
        allowed: Whether the discourse act is permitted (False means constrained to DEFERRAL)
        reason: Human-readable explanation of the discourse act resolution
        intent: The source IntentType from PO2
        regime: The source OperationalRegime from P6
        supporting_evidence: Grammar/linguistic evidence that supported (but didn't determine) this decision
        architectural_phase: Identifier for this phase ("P7")
        debug: Additional debug/trace information
    """
    act: DiscourseAct
    allowed: bool
    reason: str
    intent: IntentType
    regime: OperationalRegime
    supporting_evidence: Dict[str, Any] = field(default_factory=dict)
    architectural_phase: str = "P7"

    # Debug/trace information
    debug: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate DiscourseEnvelope invariants."""
        # Act must be set
        if self.act is None:
            raise ValueError("DiscourseEnvelope.act cannot be None")

        # Reason must be a non-empty string
        if not isinstance(self.reason, str) or not self.reason.strip():
            raise ValueError(
                "DiscourseEnvelope.reason must be a non-empty string"
            )

        # Intent must be set
        if self.intent is None:
            raise ValueError("DiscourseEnvelope.intent cannot be None")

        # Regime must be set
        if self.regime is None:
            raise ValueError("DiscourseEnvelope.regime cannot be None")

        # Validate act is a valid enum value
        if not isinstance(self.act, DiscourseAct):
            raise ValueError(
                f"DiscourseEnvelope.act must be DiscourseAct, "
                f"got {type(self.act).__name__}"
            )

        # Validate intent is a valid enum value
        if not isinstance(self.intent, IntentType):
            raise ValueError(
                f"DiscourseEnvelope.intent must be IntentType, "
                f"got {type(self.intent).__name__}"
            )

        # Validate regime is a valid enum value
        if not isinstance(self.regime, OperationalRegime):
            raise ValueError(
                f"DiscourseEnvelope.regime must be OperationalRegime, "
                f"got {type(self.regime).__name__}"
            )

        # If act is DEFERRAL, allowed should be True (DEFERRAL is always allowed)
        # But if allowed is False, act MUST be DEFERRAL
        if not self.allowed and self.act != DiscourseAct.DEFERRAL:
            raise ValueError(
                f"DiscourseEnvelope: if allowed=False, act must be DEFERRAL, "
                f"got {self.act.value}"
            )

    def is_deferral(self) -> bool:
        """Check if discourse act is DEFERRAL (most conservative)."""
        return self.act == DiscourseAct.DEFERRAL

    def is_question(self) -> bool:
        """Check if discourse act is QUESTION."""
        return self.act == DiscourseAct.QUESTION

    def is_reflection(self) -> bool:
        """Check if discourse act is REFLECTION."""
        return self.act == DiscourseAct.REFLECTION

    def is_acknowledgment(self) -> bool:
        """Check if discourse act is ACKNOWLEDGMENT."""
        return self.act == DiscourseAct.ACKNOWLEDGMENT

    def is_explanation(self) -> bool:
        """Check if discourse act is EXPLANATION."""
        return self.act == DiscourseAct.EXPLANATION

    def is_instruction(self) -> bool:
        """Check if discourse act is INSTRUCTION."""
        return self.act == DiscourseAct.INSTRUCTION

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for logging/tracing."""
        return {
            "act": self.act.value,
            "allowed": self.allowed,
            "reason": self.reason,
            "intent": self.intent.value,
            "regime": self.regime.value,
            "supporting_evidence": self.supporting_evidence,
            "architectural_phase": self.architectural_phase,
            "debug": self.debug,
        }


# Public exports
__all__ = [
    # Enums
    "DiscourseAct",
    # Dataclasses
    "DiscourseEnvelope",
]
