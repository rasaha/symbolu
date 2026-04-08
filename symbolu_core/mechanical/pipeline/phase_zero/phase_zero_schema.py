"""
PO2 — Intent Envelope & Response Posture Schema Definitions
(Implemented as phase_zero for backward compatibility)

PO2 sits between PO1 (Observer-Observed Grounding) and the Planner.
It consumes grounding constraints from PO1 and produces a single IntentEnvelope
that determines the appropriate response posture.

PO phases are pre-acoustic governance layers and precede symbolic processing (P1+).

Design Principles:
- Deterministic: No LLM calls, no probabilistic sampling
- Conservative: Defaults to safe postures when uncertain
- Authority-Respecting: Cannot override PO1 constraints
- Serializable: All types support logging/tracing

Authority Model:
- PO1 constraints flow INTO PO2 (read-only)
- PO2 produces IntentEnvelope for downstream consumption
- PO2 cannot override blocked/restricted states from PO1
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from symbolu_core.mechanical.pipeline.grounding.phase_minus_one_schema import (
    PhaseMinusOneEnvelope,
    ObservationMode,
    OverallPolicy,
)


# ============================================================================
# ENUMS - Deterministic intent and response classifications
# ============================================================================


class IntentType(str, Enum):
    """
    Classification of the user's communicative intent.

    Derived deterministically from PO1 grounding analysis.
    Each intent type maps to specific allowed response postures.

    CLARIFY: Grounding is blocked or ambiguous; clarification required
    SUPPORT: User expressing internal state (REFLEXIVE mode)
    REFLECT: Relational context requiring mirroring/acknowledgment
    INFORM: Detached inquiry about external phenomenon
    ABSTAIN: Cannot determine intent; conservative hold
    """
    CLARIFY = "CLARIFY"
    SUPPORT = "SUPPORT"
    REFLECT = "REFLECT"
    INFORM = "INFORM"
    ABSTAIN = "ABSTAIN"


class ResponsePosture(str, Enum):
    """
    System response posture determined by PO2.

    Constrains what kinds of responses the Planner may generate.
    Postures are ordered from most conservative to most analytical.

    HOLD: No action until clarification received (most conservative)
    ACKNOWLEDGE: Validate/mirror without analysis
    ENGAGE_CAREFUL: Engage with care, limited analysis
    ENGAGE_OPEN: Full engagement permitted (least conservative)
    """
    HOLD = "HOLD"
    ACKNOWLEDGE = "ACKNOWLEDGE"
    ENGAGE_CAREFUL = "ENGAGE_CAREFUL"
    ENGAGE_OPEN = "ENGAGE_OPEN"


# ============================================================================
# MAPPING TABLES - Deterministic intent-to-posture mapping
# ============================================================================


# Intent → Default ResponsePosture mapping
INTENT_TO_POSTURE: Dict[IntentType, ResponsePosture] = {
    IntentType.CLARIFY: ResponsePosture.HOLD,
    IntentType.SUPPORT: ResponsePosture.ACKNOWLEDGE,
    IntentType.REFLECT: ResponsePosture.ENGAGE_CAREFUL,
    IntentType.INFORM: ResponsePosture.ENGAGE_OPEN,
    IntentType.ABSTAIN: ResponsePosture.HOLD,
}


# ============================================================================
# DATACLASSES - Core envelope objects
# ============================================================================


@dataclass
class IntentEnvelope:
    """
    PO2 output envelope: Intent classification and response posture.

    This envelope is attached to PipelineContext after PO2 resolution
    and carries forward the determined intent type and response posture
    for the Planner and downstream stages.

    Invariants:
    - intent_type and response_posture are always set (never None)
    - If PO1 was BLOCKED, intent_type MUST be CLARIFY
    - If any clause has selected=None, intent_type MUST be CLARIFY
    - response_posture is deterministically derived from intent_type

    Attributes:
        intent_type: Classified communicative intent
        response_posture: Determined response posture for Planner
        planning_allowed: Whether Planner may proceed with action planning
        phase_minus_one_policy: The upstream PO1 overall policy (preserved)
        mode_signals: Observation modes detected in input (for diagnostics)
        resolution_reason: Human-readable explanation of resolution
        debug: Additional debug/trace information
    """
    intent_type: IntentType
    response_posture: ResponsePosture
    planning_allowed: bool
    phase_minus_one_policy: OverallPolicy
    mode_signals: List[ObservationMode] = field(default_factory=list)
    resolution_reason: str = ""
    debug: Dict[str, Any] = field(default_factory=dict)

    # Architectural phase identifier (informational only, does not affect logic)
    architectural_phase: str = "PO2"

    def __post_init__(self) -> None:
        """Validate envelope invariants."""
        # If BLOCKED upstream, intent MUST be CLARIFY
        if self.phase_minus_one_policy == OverallPolicy.BLOCKED:
            if self.intent_type != IntentType.CLARIFY:
                raise ValueError(
                    f"BLOCKED policy requires CLARIFY intent, got {self.intent_type.value}"
                )
            if self.planning_allowed:
                raise ValueError(
                    "BLOCKED policy must have planning_allowed=False"
                )

    def is_planning_blocked(self) -> bool:
        """Check if planning is blocked (requires clarification)."""
        return not self.planning_allowed

    def requires_clarification(self) -> bool:
        """Check if clarification is required before proceeding."""
        return self.intent_type == IntentType.CLARIFY

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for logging/tracing."""
        return {
            "intent_type": self.intent_type.value,
            "response_posture": self.response_posture.value,
            "planning_allowed": self.planning_allowed,
            "phase_minus_one_policy": self.phase_minus_one_policy.value,
            "mode_signals": [m.value for m in self.mode_signals],
            "resolution_reason": self.resolution_reason,
            "debug": self.debug,
        }


# Public exports
__all__ = [
    # Enums
    "IntentType",
    "ResponsePosture",
    # Mapping
    "INTENT_TO_POSTURE",
    # Dataclasses
    "IntentEnvelope",
]
