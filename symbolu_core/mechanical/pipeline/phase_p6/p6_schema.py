"""
P6 — Regime Selection & Operational Mode Gate Schema Definitions

P6 is the first post-governance, pre-language phase.
It determines what operational regime is safe for this turn based on
already-computed signals from PO1-PO5.

P6's responsibility is to:
- Select an operational regime based on intent, eligibility, coherence, and stability
- Produce a read-only RegimeEnvelope that constrains downstream language generation

P6 does NOT:
- Perform semantic interpretation
- Choose words or discourse acts
- Execute actions
- Modify intent or grounding
- Call LLMs
- Introduce probabilistic behavior

Design Principles:
- Deterministic: No LLM calls, no probabilistic sampling
- Gating-Only: Reads upstream state, produces regime verdict
- Authority-Respecting: Cannot override PO1–PO5 constraints
- Conservative: HOLD is always safe, regime may only restrict capability

Authority Model:
- Authority flows: PO1 → PO2 → PO3 → PO4 → PO5 → P6 → (Language layers)
- P6 receives signals from PO2 IntentEnvelope, PO5 ExecutionEligibilityEnvelope,
  and Phase-41 coherence regime
- P6 cannot override or expand upstream decisions
- P6 produces RegimeEnvelope for downstream language generation constraints
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict

from symbolu_core.mechanical.pipeline.phase_zero.phase_zero_schema import IntentType
from symbolu_core.mechanical.pipeline.phase_po5.po5_schema import ExecutionEligibility


# ============================================================================
# ENUMS - Operational regime classification
# ============================================================================


class OperationalRegime(str, Enum):
    """
    Operational regime determining what mode of operation is safe for this turn.

    STABILIZE: Session volatility detected, focus on grounding/stability
    REFLECT: Multi-context or relational mirroring required
    INFORM: Detached informational response permitted
    CLARIFY: Clarification required before proceeding
    DE_ESCALATE: User expressing internal state, de-escalation prioritized
    HOLD: Most conservative mode, no forward progression

    HOLD is always safe.
    Regime may only restrict, never expand capability.
    """
    STABILIZE = "STABILIZE"
    REFLECT = "REFLECT"
    INFORM = "INFORM"
    CLARIFY = "CLARIFY"
    DE_ESCALATE = "DE_ESCALATE"
    HOLD = "HOLD"


# ============================================================================
# DATACLASSES - Core envelope object
# ============================================================================


@dataclass(frozen=True)
class RegimeEnvelope:
    """
    P6 output envelope: Operational regime verdict.

    This envelope is read-only and captures the regime selection decision
    that constrains all downstream language generation. It does NOT perform
    any semantic processing, lexical selection, or execution.

    Invariants:
    - HOLD is always safe
    - Regime may only restrict, never expand capability
    - reason must always be a non-empty string

    Attributes:
        regime: The selected operational regime
        reason: Human-readable explanation of the regime selection
        intent: The source IntentType from PO2
        execution_eligibility: The execution eligibility from PO5
        coherence_regime: The coherence regime band from Phase-41
        architectural_phase: Identifier for this phase ("P6")
        debug: Additional debug/trace information
    """
    regime: OperationalRegime
    reason: str
    intent: IntentType
    execution_eligibility: ExecutionEligibility
    coherence_regime: str
    architectural_phase: str = "P6"

    # Debug/trace information
    debug: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate RegimeEnvelope invariants."""
        # Regime must be set
        if self.regime is None:
            raise ValueError("RegimeEnvelope.regime cannot be None")

        # Reason must be a non-empty string
        if not isinstance(self.reason, str) or not self.reason.strip():
            raise ValueError(
                "RegimeEnvelope.reason must be a non-empty string"
            )

        # Intent must be set
        if self.intent is None:
            raise ValueError("RegimeEnvelope.intent cannot be None")

        # Execution eligibility must be set
        if self.execution_eligibility is None:
            raise ValueError(
                "RegimeEnvelope.execution_eligibility cannot be None"
            )

        # Coherence regime must be set (can be empty string for missing data)
        if self.coherence_regime is None:
            raise ValueError(
                "RegimeEnvelope.coherence_regime cannot be None"
            )

        # Validate regime is a valid enum value
        if not isinstance(self.regime, OperationalRegime):
            raise ValueError(
                f"RegimeEnvelope.regime must be OperationalRegime, "
                f"got {type(self.regime).__name__}"
            )

        # Validate intent is a valid enum value
        if not isinstance(self.intent, IntentType):
            raise ValueError(
                f"RegimeEnvelope.intent must be IntentType, "
                f"got {type(self.intent).__name__}"
            )

        # Validate execution_eligibility is a valid enum value
        if not isinstance(self.execution_eligibility, ExecutionEligibility):
            raise ValueError(
                f"RegimeEnvelope.execution_eligibility must be ExecutionEligibility, "
                f"got {type(self.execution_eligibility).__name__}"
            )

    def is_hold(self) -> bool:
        """Check if regime is HOLD (most conservative)."""
        return self.regime == OperationalRegime.HOLD

    def is_stabilize(self) -> bool:
        """Check if regime is STABILIZE."""
        return self.regime == OperationalRegime.STABILIZE

    def is_reflect(self) -> bool:
        """Check if regime is REFLECT."""
        return self.regime == OperationalRegime.REFLECT

    def is_inform(self) -> bool:
        """Check if regime is INFORM."""
        return self.regime == OperationalRegime.INFORM

    def is_clarify(self) -> bool:
        """Check if regime is CLARIFY."""
        return self.regime == OperationalRegime.CLARIFY

    def is_de_escalate(self) -> bool:
        """Check if regime is DE_ESCALATE."""
        return self.regime == OperationalRegime.DE_ESCALATE

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for logging/tracing."""
        return {
            "regime": self.regime.value,
            "reason": self.reason,
            "intent": self.intent.value,
            "execution_eligibility": self.execution_eligibility.value,
            "coherence_regime": self.coherence_regime,
            "architectural_phase": self.architectural_phase,
            "debug": self.debug,
        }


# Public exports
__all__ = [
    # Enums
    "OperationalRegime",
    # Dataclasses
    "RegimeEnvelope",
]
