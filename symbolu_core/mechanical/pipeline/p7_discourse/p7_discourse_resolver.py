"""
P7 — Discourse Act Resolver

Deterministic resolver that determines what kind of utterance is allowed for this turn.
No execution, no semantics, no planning, no side effects.

This is a resolution layer that determines what discourse act is permitted.
It produces a read-only verdict and does NOT execute, plan, or perform semantic processing.

Authority Model:
- Consumes PO1 PhaseMinusOneEnvelope, PO2 IntentEnvelope, PO3 AllowedActionSet, P6 RegimeEnvelope
- Cannot override PO1–P6 decisions
- Produces DiscourseEnvelope (read-only, non-actuating)
- Constrains downstream semantic/language generation only

Deterministic Rules (Authoritative, evaluated in order):
1. If regime == HOLD → DEFERRAL
2. If intent == CLARIFY → QUESTION (only if regime allows engagement)
3. If intent == SUPPORT → REFLECTION or ACKNOWLEDGMENT (never EXPLANATION)
4. If intent == INFORM → EXPLANATION (only if regime == INFORM)
5. If intent == ABSTAIN → DEFERRAL
6. Fallback → DEFERRAL

CRITICAL: DEFERRAL is always safe. Discourse act may only restrict, never expand capability.
"""

from __future__ import annotations

from typing import Any, Dict, FrozenSet, Optional

from symbolu_core.mechanical.pipeline.grounding.phase_minus_one_schema import (
    PhaseMinusOneEnvelope,
)
from symbolu_core.mechanical.pipeline.phase_zero.phase_zero_schema import (
    IntentEnvelope,
    IntentType,
)
from symbolu_core.mechanical.pipeline.phase_one.phase_one_schema import AllowedActionSet
from symbolu_core.mechanical.pipeline.phase_p6.p6_schema import (
    RegimeEnvelope,
    OperationalRegime,
)
from symbolu_core.mechanical.pipeline.governance.planner_gate import ActionClass
from symbolu_core.mechanical.pipeline.p7_discourse.p7_discourse_schema import (
    DiscourseAct,
    DiscourseEnvelope,
)


# ============================================================================
# ALLOW-LIST MAPPINGS - Strict regime-to-discourse-act permissions
# ============================================================================

# Which discourse acts are allowed under each operational regime
# This is the strict allow-list: if not in this set, act is REJECTED
REGIME_ALLOWED_ACTS: Dict[OperationalRegime, FrozenSet[DiscourseAct]] = {
    OperationalRegime.HOLD: frozenset({DiscourseAct.DEFERRAL}),
    OperationalRegime.CLARIFY: frozenset({
        DiscourseAct.QUESTION,
        DiscourseAct.DEFERRAL,
    }),
    OperationalRegime.STABILIZE: frozenset({
        DiscourseAct.ACKNOWLEDGMENT,
        DiscourseAct.REFLECTION,
        DiscourseAct.DEFERRAL,
    }),
    OperationalRegime.REFLECT: frozenset({
        DiscourseAct.REFLECTION,
        DiscourseAct.ACKNOWLEDGMENT,
        DiscourseAct.QUESTION,
        DiscourseAct.DEFERRAL,
    }),
    OperationalRegime.DE_ESCALATE: frozenset({
        DiscourseAct.REFLECTION,
        DiscourseAct.ACKNOWLEDGMENT,
        DiscourseAct.DEFERRAL,
    }),
    OperationalRegime.INFORM: frozenset({
        DiscourseAct.EXPLANATION,
        DiscourseAct.REFLECTION,
        DiscourseAct.ACKNOWLEDGMENT,
        DiscourseAct.QUESTION,
        DiscourseAct.INSTRUCTION,
        DiscourseAct.DEFERRAL,
    }),
}

# Regimes that allow any form of engagement (not just DEFERRAL)
ENGAGEMENT_REGIMES: FrozenSet[OperationalRegime] = frozenset({
    OperationalRegime.CLARIFY,
    OperationalRegime.STABILIZE,
    OperationalRegime.REFLECT,
    OperationalRegime.DE_ESCALATE,
    OperationalRegime.INFORM,
})


class P7DiscourseResolver:
    """
    Deterministic discourse act resolver (non-actuating).

    This resolver implements strict, deterministic rules to resolve the discourse
    act for this turn. It does NOT execute any actions, perform semantic
    processing, or enable any execution pathway.

    CRITICAL: This class is purely evaluative. The discourse act selection constrains
    downstream language generation but does not directly produce any output.

    Usage:
        resolver = P7DiscourseResolver()
        envelope = resolver.resolve(
            grounding_envelope=po1_envelope,
            intent_envelope=po2_envelope,
            action_contract=po3_actions,
            regime_envelope=p6_envelope,
            grammar_evidence=optional_evidence,
        )
        # envelope.act indicates QUESTION / REFLECTION / ACKNOWLEDGMENT / EXPLANATION / INSTRUCTION / DEFERRAL
    """

    def __init__(self) -> None:
        """Initialize the P7 discourse resolver."""
        pass  # No state needed - purely deterministic

    def resolve(
        self,
        *,
        grounding_envelope: PhaseMinusOneEnvelope,
        intent_envelope: IntentEnvelope,
        action_contract: AllowedActionSet,
        regime_envelope: RegimeEnvelope,
        grammar_evidence: Optional[Dict[str, Any]] = None,
    ) -> DiscourseEnvelope:
        """
        Resolve discourse act based on deterministic rules.

        This is a pure, deterministic evaluation with no side effects.
        The result is a read-only discourse act verdict.

        CRITICAL: DEFERRAL is always safe. Discourse act may only restrict, never expand.

        Deterministic Rules (evaluated in order):
        1. If regime == HOLD → DEFERRAL
        2. If intent == CLARIFY → QUESTION (only if regime allows engagement)
        3. If intent == SUPPORT → REFLECTION or ACKNOWLEDGMENT (never EXPLANATION)
        4. If intent == INFORM → EXPLANATION (only if regime == INFORM)
        5. If intent == ABSTAIN → DEFERRAL
        6. Fallback → DEFERRAL

        Args:
            grounding_envelope: The PO1 PhaseMinusOneEnvelope (provides grounding constraints).
            intent_envelope: The PO2 IntentEnvelope (provides intent).
            action_contract: The PO3 AllowedActionSet (provides allowed actions).
            regime_envelope: The P6 RegimeEnvelope (provides operational regime).
            grammar_evidence: Optional grammar/linguistic evidence (spaCy signals, etc.)
                             This is EVIDENCE-ONLY and cannot determine the discourse act.

        Returns:
            DiscourseEnvelope with discourse act resolution verdict.

        Raises:
            ValueError: If required inputs are None or invalid.
        """
        # Validate inputs
        if grounding_envelope is None:
            raise ValueError("grounding_envelope cannot be None")
        if intent_envelope is None:
            raise ValueError("intent_envelope cannot be None")
        if action_contract is None:
            raise ValueError("action_contract cannot be None")
        if regime_envelope is None:
            raise ValueError("regime_envelope cannot be None")

        # Extract values for rule evaluation
        intent_type = intent_envelope.intent_type
        regime = regime_envelope.regime
        allowed_actions = action_contract.allowed_actions

        # Normalize grammar evidence
        evidence = grammar_evidence if grammar_evidence is not None else {}

        # Apply deterministic rules in order
        act, allowed, reason = self._apply_rules(
            intent_type=intent_type,
            regime=regime,
            allowed_actions=allowed_actions,
            grammar_evidence=evidence,
        )

        # Validate act against regime allow-list (final check)
        act, allowed, reason = self._validate_against_regime(
            act=act,
            allowed=allowed,
            reason=reason,
            regime=regime,
        )

        # Build debug info
        debug = self._build_debug_info(
            grounding_envelope=grounding_envelope,
            intent_envelope=intent_envelope,
            action_contract=action_contract,
            regime_envelope=regime_envelope,
            grammar_evidence=evidence,
            resolved_act=act,
        )

        return DiscourseEnvelope(
            act=act,
            allowed=allowed,
            reason=reason,
            intent=intent_type,
            regime=regime,
            supporting_evidence=evidence,
            debug=debug,
        )

    def _apply_rules(
        self,
        intent_type: IntentType,
        regime: OperationalRegime,
        allowed_actions: FrozenSet[ActionClass],
        grammar_evidence: Dict[str, Any],
    ) -> tuple[DiscourseAct, bool, str]:
        """
        Apply deterministic rules to resolve discourse act.

        Rules are evaluated in strict order. First matching rule wins.

        Args:
            intent_type: The classified intent from PO2.
            regime: The operational regime from P6.
            allowed_actions: The allowed action classes from PO3.
            grammar_evidence: Optional grammar evidence (evidence-only, cannot decide).

        Returns:
            Tuple of (DiscourseAct, allowed, reason string).
        """
        # Rule 1: If regime == HOLD → DEFERRAL
        if regime == OperationalRegime.HOLD:
            return (
                DiscourseAct.DEFERRAL,
                True,
                "Discourse DEFERRAL: Regime is HOLD, no forward progression allowed"
            )

        # Rule 2: If intent == CLARIFY → QUESTION (only if regime allows engagement)
        if intent_type == IntentType.CLARIFY:
            if regime in ENGAGEMENT_REGIMES:
                return (
                    DiscourseAct.QUESTION,
                    True,
                    "Discourse QUESTION: Intent is CLARIFY, regime allows engagement"
                )
            else:
                return (
                    DiscourseAct.DEFERRAL,
                    True,
                    "Discourse DEFERRAL: Intent is CLARIFY but regime does not allow engagement"
                )

        # Rule 3: If intent == SUPPORT → REFLECTION or ACKNOWLEDGMENT (never EXPLANATION)
        if intent_type == IntentType.SUPPORT:
            # Choose between REFLECTION and ACKNOWLEDGMENT based on regime
            # DE_ESCALATE and REFLECT regimes → REFLECTION (more mirroring)
            # STABILIZE → ACKNOWLEDGMENT (simpler, more conservative)
            # Default to REFLECTION
            if regime == OperationalRegime.STABILIZE:
                return (
                    DiscourseAct.ACKNOWLEDGMENT,
                    True,
                    "Discourse ACKNOWLEDGMENT: Intent is SUPPORT, regime is STABILIZE (conservative)"
                )
            else:
                return (
                    DiscourseAct.REFLECTION,
                    True,
                    "Discourse REFLECTION: Intent is SUPPORT, mirroring/validating user"
                )

        # Rule 4: If intent == INFORM → EXPLANATION (only if regime == INFORM)
        if intent_type == IntentType.INFORM:
            if regime == OperationalRegime.INFORM:
                return (
                    DiscourseAct.EXPLANATION,
                    True,
                    "Discourse EXPLANATION: Intent is INFORM, regime permits informational response"
                )
            else:
                # Cannot provide EXPLANATION outside of INFORM regime
                return (
                    DiscourseAct.DEFERRAL,
                    True,
                    f"Discourse DEFERRAL: Intent is INFORM but regime is {regime.value}, "
                    f"explanation not permitted"
                )

        # Rule 5: If intent == ABSTAIN → DEFERRAL
        if intent_type == IntentType.ABSTAIN:
            return (
                DiscourseAct.DEFERRAL,
                True,
                "Discourse DEFERRAL: Intent is ABSTAIN, no discourse act allowed"
            )

        # Rule 6: If intent == REFLECT → check regime, default to REFLECTION or DEFERRAL
        if intent_type == IntentType.REFLECT:
            if regime in {OperationalRegime.REFLECT, OperationalRegime.DE_ESCALATE, OperationalRegime.INFORM}:
                return (
                    DiscourseAct.REFLECTION,
                    True,
                    "Discourse REFLECTION: Intent is REFLECT, regime permits reflective engagement"
                )
            else:
                return (
                    DiscourseAct.DEFERRAL,
                    True,
                    f"Discourse DEFERRAL: Intent is REFLECT but regime {regime.value} does not permit it"
                )

        # Rule 7: Fallback → DEFERRAL
        # This is the conservative default for unmatched cases
        return (
            DiscourseAct.DEFERRAL,
            True,
            "Discourse DEFERRAL: Conservative fallback - no specific discourse act matched"
        )

    def _validate_against_regime(
        self,
        act: DiscourseAct,
        allowed: bool,
        reason: str,
        regime: OperationalRegime,
    ) -> tuple[DiscourseAct, bool, str]:
        """
        Validate resolved act against regime allow-list.

        If the resolved act is not in the regime's allow-list, force DEFERRAL.

        Args:
            act: The resolved discourse act.
            allowed: Whether the act was allowed by rules.
            reason: The reason string.
            regime: The operational regime.

        Returns:
            Tuple of (DiscourseAct, allowed, reason string).
        """
        allowed_acts = REGIME_ALLOWED_ACTS.get(regime, frozenset({DiscourseAct.DEFERRAL}))

        if act not in allowed_acts:
            return (
                DiscourseAct.DEFERRAL,
                True,
                f"Discourse DEFERRAL: Act {act.value} not permitted under regime {regime.value}"
            )

        return (act, allowed, reason)

    def _build_debug_info(
        self,
        grounding_envelope: PhaseMinusOneEnvelope,
        intent_envelope: IntentEnvelope,
        action_contract: AllowedActionSet,
        regime_envelope: RegimeEnvelope,
        grammar_evidence: Dict[str, Any],
        resolved_act: DiscourseAct,
    ) -> Dict[str, Any]:
        """Build debug information for tracing."""
        return {
            "source_intent": intent_envelope.intent_type.value,
            "source_posture": intent_envelope.response_posture.value,
            "source_regime": regime_envelope.regime.value,
            "overall_policy": grounding_envelope.overall_policy.value,
            "allowed_action_count": action_contract.count(),
            "resolved_act": resolved_act.value,
            "grammar_evidence_present": bool(grammar_evidence),
            "grammar_evidence_keys": list(grammar_evidence.keys()) if grammar_evidence else [],
            "regime_allowed_acts": sorted([a.value for a in REGIME_ALLOWED_ACTS.get(
                regime_envelope.regime, frozenset()
            )]),
        }


# Public exports
__all__ = [
    "P7DiscourseResolver",
    "REGIME_ALLOWED_ACTS",
    "ENGAGEMENT_REGIMES",
]
