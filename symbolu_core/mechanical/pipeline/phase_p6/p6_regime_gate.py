"""
P6 — Regime Selection & Operational Mode Gate

Deterministic gate that selects operational regime based on upstream signals.
No execution, no semantics, no planning, no side effects.

This is a gating layer that determines what operational mode is safe for this turn.
It produces a read-only verdict and does NOT execute, plan, or perform semantic processing.

Authority Model:
- Consumes PO2 IntentEnvelope, PO5 ExecutionEligibilityEnvelope, PO1 OverallPolicy,
  and Phase-41 coherence regime
- Cannot override PO1–PO5 decisions
- Produces RegimeEnvelope (read-only, non-actuating)
- Constrains downstream language generation only

Deterministic Rules (Authoritative, evaluated in order):
1. If execution.eligibility == PROHIBITED → HOLD
2. If intent.intent == CLARIFY → CLARIFY
3. If overall_policy == MULTI_CONTEXT → REFLECT
4. If coherence_regime in {"volatile", "unstable"} → STABILIZE
5. If intent.intent == SUPPORT → DE_ESCALATE
6. If intent.intent == INFORM → INFORM
7. Fallback → HOLD

CRITICAL: HOLD is always safe. Regime may only restrict, never expand capability.
"""

from __future__ import annotations

from symbolu_core.mechanical.pipeline.phase_zero.phase_zero_schema import (
    IntentEnvelope,
    IntentType,
)
from symbolu_core.mechanical.pipeline.phase_po5.po5_schema import (
    ExecutionEligibilityEnvelope,
    ExecutionEligibility,
)
from symbolu_core.mechanical.pipeline.grounding.phase_minus_one_schema import OverallPolicy
from symbolu_core.mechanical.pipeline.phase_p6.p6_schema import (
    OperationalRegime,
    RegimeEnvelope,
)


# Coherence regimes that trigger STABILIZE
VOLATILE_COHERENCE_REGIMES = frozenset({"volatile", "unstable"})


class P6RegimeGate:
    """
    Deterministic regime selection gate (non-actuating).

    This gate implements strict, deterministic rules to select the operational
    regime for this turn. It does NOT execute any actions, perform semantic
    processing, or enable any execution pathway.

    CRITICAL: This class is purely evaluative. The regime selection constrains
    downstream language generation but does not directly produce any output.

    Usage:
        gate = P6RegimeGate()
        envelope = gate.select(intent_envelope, execution, coherence_regime, overall_policy)
        # envelope.regime indicates STABILIZE / REFLECT / INFORM / CLARIFY / DE_ESCALATE / HOLD
    """

    def __init__(self) -> None:
        """Initialize the P6 regime gate."""
        pass  # No state needed - purely deterministic

    def select(
        self,
        intent_envelope: IntentEnvelope,
        execution: ExecutionEligibilityEnvelope,
        coherence_regime: str,
        overall_policy: OverallPolicy,
    ) -> RegimeEnvelope:
        """
        Select operational regime based on deterministic rules.

        This is a pure, deterministic evaluation with no side effects.
        The result is a read-only regime verdict.

        CRITICAL: HOLD is always safe. Regime may only restrict, never expand.

        Deterministic Rules (evaluated in order):
        1. If execution.eligibility == PROHIBITED → HOLD
        2. If intent.intent == CLARIFY → CLARIFY
        3. If overall_policy == MULTI_CONTEXT → REFLECT
        4. If coherence_regime in {"volatile", "unstable"} → STABILIZE
        5. If intent.intent == SUPPORT → DE_ESCALATE
        6. If intent.intent == INFORM → INFORM
        7. Fallback → HOLD

        Args:
            intent_envelope: The PO2 IntentEnvelope (provides intent).
            execution: The PO5 ExecutionEligibilityEnvelope (provides eligibility).
            coherence_regime: The coherence regime band from Phase-41.
            overall_policy: The PO1 OverallPolicy (provides grounding policy).

        Returns:
            RegimeEnvelope with regime selection verdict.

        Raises:
            ValueError: If inputs are None or invalid.
        """
        # Validate inputs
        if intent_envelope is None:
            raise ValueError("intent_envelope cannot be None")
        if execution is None:
            raise ValueError("execution cannot be None")
        if overall_policy is None:
            raise ValueError("overall_policy cannot be None")
        if coherence_regime is None:
            raise ValueError("coherence_regime cannot be None")

        # Extract values for rule evaluation
        intent_type = intent_envelope.intent_type
        eligibility = execution.eligibility

        # Apply deterministic rules in order
        regime, reason = self._apply_rules(
            intent_type=intent_type,
            eligibility=eligibility,
            coherence_regime=coherence_regime,
            overall_policy=overall_policy,
        )

        # Build debug info
        debug = self._build_debug_info(
            intent_envelope=intent_envelope,
            execution=execution,
            coherence_regime=coherence_regime,
            overall_policy=overall_policy,
            regime=regime,
        )

        return RegimeEnvelope(
            regime=regime,
            reason=reason,
            intent=intent_type,
            execution_eligibility=eligibility,
            coherence_regime=coherence_regime,
            debug=debug,
        )

    def _apply_rules(
        self,
        intent_type: IntentType,
        eligibility: ExecutionEligibility,
        coherence_regime: str,
        overall_policy: OverallPolicy,
    ) -> tuple[OperationalRegime, str]:
        """
        Apply deterministic rules to select regime.

        Rules are evaluated in strict order. First matching rule wins.

        Args:
            intent_type: The classified intent from PO2.
            eligibility: The execution eligibility from PO5.
            coherence_regime: The coherence regime band from Phase-41.
            overall_policy: The overall policy from PO1.

        Returns:
            Tuple of (OperationalRegime, reason string).
        """
        # Rule 1: If execution.eligibility == PROHIBITED → HOLD
        if eligibility == ExecutionEligibility.PROHIBITED:
            return (
                OperationalRegime.HOLD,
                "Regime HOLD: Execution is prohibited by PO5"
            )

        # Rule 2: If intent.intent == CLARIFY → CLARIFY
        if intent_type == IntentType.CLARIFY:
            return (
                OperationalRegime.CLARIFY,
                "Regime CLARIFY: Intent requires clarification"
            )

        # Rule 3: If overall_policy == MULTI_CONTEXT → REFLECT
        if overall_policy == OverallPolicy.MULTI_CONTEXT:
            return (
                OperationalRegime.REFLECT,
                "Regime REFLECT: Multiple grounding contexts require reflective engagement"
            )

        # Rule 4: If coherence_regime in {"volatile", "unstable"} → STABILIZE
        coherence_lower = coherence_regime.lower() if coherence_regime else ""
        if coherence_lower in VOLATILE_COHERENCE_REGIMES:
            return (
                OperationalRegime.STABILIZE,
                f"Regime STABILIZE: Coherence regime is {coherence_regime}, "
                f"stabilization prioritized"
            )

        # Rule 5: If intent.intent == SUPPORT → DE_ESCALATE
        if intent_type == IntentType.SUPPORT:
            return (
                OperationalRegime.DE_ESCALATE,
                "Regime DE_ESCALATE: User expressing internal state, "
                "de-escalation prioritized"
            )

        # Rule 6: If intent.intent == INFORM → INFORM
        if intent_type == IntentType.INFORM:
            return (
                OperationalRegime.INFORM,
                "Regime INFORM: Detached informational response permitted"
            )

        # Rule 7: Fallback → HOLD
        # This is the conservative default for unmatched cases
        return (
            OperationalRegime.HOLD,
            "Regime HOLD: Conservative fallback - no specific regime matched"
        )

    def _build_debug_info(
        self,
        intent_envelope: IntentEnvelope,
        execution: ExecutionEligibilityEnvelope,
        coherence_regime: str,
        overall_policy: OverallPolicy,
        regime: OperationalRegime,
    ) -> dict:
        """Build debug information for tracing."""
        return {
            "source_intent": intent_envelope.intent_type.value,
            "source_posture": intent_envelope.response_posture.value,
            "execution_eligibility": execution.eligibility.value,
            "coherence_regime": coherence_regime,
            "overall_policy": overall_policy.value,
            "selected_regime": regime.value,
            "planning_allowed": intent_envelope.planning_allowed,
            "execution_reason": execution.reason,
        }


# Public exports
__all__ = [
    "P6RegimeGate",
]
