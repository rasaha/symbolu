"""
P8 - Semantic Slot Resolver

Deterministic resolver that determines what semantic slots must be filled for this turn.
No execution, no lexical selection, no word choice, no side effects.

This is a resolution layer that determines what meanings must be expressed.
It produces a read-only SemanticFrame and does NOT execute, plan, or perform lexical selection.

Authority Model:
- Consumes PO1 PhaseMinusOneEnvelope, PO2 IntentEnvelope, P6 RegimeEnvelope, P7 DiscourseEnvelope
- Cannot override PO1-P7 decisions
- Produces SemanticFrame (read-only, non-actuating)
- Constrains downstream lexical/language generation only

Resolution Algorithm (Authoritative, exact order):
1. If discourse_act == DEFERRAL:
   - Populate LIMITATION only
   - Do not populate any explanatory slots
2. Determine allowed slots from discourse_act
   - Create empty slots only from allow-list
3. Populate slots conservatively
   - Use grounding + intent for AGENT / TARGET
   - Use grammar evidence only if unambiguous
   - Otherwise leave slot value = None
4. Validate against regime
   - If regime == CAREFUL: CAUSE is allowed only if explicitly safe
   - If regime == HOLD: Only DEFERRAL frame allowed
5. Return SemanticFrame
   - allowed = True only if all constraints satisfied
   - otherwise allowed = False with reason

CRITICAL: Never hallucinate slot values. If information is missing, slot value = None.
"""

from __future__ import annotations

from typing import Any, Dict, FrozenSet, Optional

from symbolu_core.mechanical.pipeline.grounding.phase_minus_one_schema import (
    PhaseMinusOneEnvelope,
    ObservedEntity,
    ObservationMode,
)
from symbolu_core.mechanical.pipeline.phase_zero.phase_zero_schema import (
    IntentEnvelope,
    IntentType,
)
from symbolu_core.mechanical.pipeline.phase_p6.p6_schema import (
    RegimeEnvelope,
    OperationalRegime,
)
from symbolu_core.mechanical.pipeline.p7_discourse.p7_discourse_schema import (
    DiscourseEnvelope,
    DiscourseAct,
)
from symbolu_core.mechanical.pipeline.p8_semantics.p8_semantic_schema import (
    SemanticSlot,
    SemanticFrame,
    DISCOURSE_ACT_ALLOWED_SLOTS,
)


# ============================================================================
# REGIME CONSTRAINTS - Additional restrictions based on operational regime
# ============================================================================

# Slots that are restricted under CAREFUL regime
CAREFUL_RESTRICTED_SLOTS: FrozenSet[SemanticSlot] = frozenset({
    SemanticSlot.CAUSE,  # CAUSE requires explicit safety under CAREFUL
})


class P8SemanticResolver:
    """
    Deterministic semantic slot resolver (non-actuating).

    This resolver implements strict, deterministic rules to resolve the semantic
    slots for this turn. It does NOT execute any actions, perform lexical
    selection, or enable any execution pathway.

    CRITICAL: This class is purely evaluative. The semantic frame constrains
    downstream lexical generation but does not directly produce any output.

    Usage:
        resolver = P8SemanticResolver()
        frame = resolver.resolve(
            grounding_envelope=po1_envelope,
            intent_envelope=po2_envelope,
            regime_envelope=p6_envelope,
            discourse_envelope=p7_envelope,
            grammar_evidence=optional_evidence,
        )
        # frame.slots contains the semantic slot map
    """

    def __init__(self) -> None:
        """Initialize the P8 semantic resolver."""
        pass  # No state needed - purely deterministic

    def resolve(
        self,
        *,
        grounding_envelope: PhaseMinusOneEnvelope,
        intent_envelope: IntentEnvelope,
        regime_envelope: RegimeEnvelope,
        discourse_envelope: DiscourseEnvelope,
        grammar_evidence: Optional[Dict[str, Any]] = None,
    ) -> SemanticFrame:
        """
        Resolve semantic slots based on deterministic rules.

        This is a pure, deterministic evaluation with no side effects.
        The result is a read-only semantic frame verdict.

        CRITICAL: Never hallucinate slot values. If information is missing, use None.

        Resolution Algorithm (exact order):
        1. If discourse_act == DEFERRAL: Populate LIMITATION only
        2. Determine allowed slots from discourse_act
        3. Populate slots conservatively (grounding + intent, grammar evidence)
        4. Validate against regime
        5. Return SemanticFrame

        Args:
            grounding_envelope: The PO1 PhaseMinusOneEnvelope (provides grounding).
            intent_envelope: The PO2 IntentEnvelope (provides intent).
            regime_envelope: The P6 RegimeEnvelope (provides operational regime).
            discourse_envelope: The P7 DiscourseEnvelope (provides discourse act).
            grammar_evidence: Optional grammar/linguistic evidence (spaCy signals, etc.)
                             This is EVIDENCE-ONLY and cannot determine or create slots.

        Returns:
            SemanticFrame with semantic slot resolution verdict.

        Raises:
            ValueError: If required inputs are None or invalid.
        """
        # Validate inputs
        if grounding_envelope is None:
            raise ValueError("grounding_envelope cannot be None")
        if intent_envelope is None:
            raise ValueError("intent_envelope cannot be None")
        if regime_envelope is None:
            raise ValueError("regime_envelope cannot be None")
        if discourse_envelope is None:
            raise ValueError("discourse_envelope cannot be None")

        # Extract values for rule evaluation
        discourse_act = discourse_envelope.act
        regime = regime_envelope.regime
        intent_type = intent_envelope.intent_type

        # Normalize grammar evidence
        evidence = grammar_evidence if grammar_evidence is not None else {}

        # Step 1: Handle DEFERRAL specially
        if discourse_act == DiscourseAct.DEFERRAL:
            slots, allowed, reason = self._build_deferral_frame(
                grounding_envelope=grounding_envelope,
                intent_envelope=intent_envelope,
                regime=regime,
                evidence=evidence,
            )
        else:
            # Steps 2-4: Build frame for non-DEFERRAL discourse acts
            slots, allowed, reason = self._build_semantic_frame(
                discourse_act=discourse_act,
                grounding_envelope=grounding_envelope,
                intent_envelope=intent_envelope,
                regime=regime,
                evidence=evidence,
            )

        # Step 4: Validate against regime (final check)
        slots, allowed, reason = self._validate_against_regime(
            discourse_act=discourse_act,
            slots=slots,
            allowed=allowed,
            reason=reason,
            regime=regime,
        )

        # Build debug info
        debug = self._build_debug_info(
            grounding_envelope=grounding_envelope,
            intent_envelope=intent_envelope,
            regime_envelope=regime_envelope,
            discourse_envelope=discourse_envelope,
            grammar_evidence=evidence,
            slots=slots,
        )

        return SemanticFrame(
            discourse_act=discourse_act,
            slots=slots,
            allowed=allowed,
            reason=reason,
            evidence=evidence,
            debug=debug,
        )

    def _build_deferral_frame(
        self,
        grounding_envelope: PhaseMinusOneEnvelope,
        intent_envelope: IntentEnvelope,
        regime: OperationalRegime,
        evidence: Dict[str, Any],
    ) -> tuple[Dict[SemanticSlot, Optional[str]], bool, str]:
        """
        Build a DEFERRAL semantic frame.

        DEFERRAL frames only populate LIMITATION and REQUEST_FOCUS slots.
        No explanatory slots (CAUSE, STATE, etc.) are populated.

        Args:
            grounding_envelope: PO1 grounding envelope.
            intent_envelope: PO2 intent envelope.
            regime: The operational regime.
            evidence: Grammar evidence (evidence-only).

        Returns:
            Tuple of (slots dict, allowed bool, reason string).
        """
        allowed_slots = DISCOURSE_ACT_ALLOWED_SLOTS[DiscourseAct.DEFERRAL]
        slots: Dict[SemanticSlot, Optional[str]] = {}

        # Initialize allowed slots with None values
        for slot in allowed_slots:
            slots[slot] = None

        # Conservative population: only populate LIMITATION if we have clear info
        # LIMITATION indicates why we cannot proceed
        if regime == OperationalRegime.HOLD:
            slots[SemanticSlot.LIMITATION] = "hold_regime"
        elif intent_envelope.intent_type == IntentType.ABSTAIN:
            slots[SemanticSlot.LIMITATION] = "abstain_intent"
        elif grounding_envelope.is_blocked():
            slots[SemanticSlot.LIMITATION] = "blocked_grounding"
        # Otherwise leave as None (conservative)

        reason = "Semantic DEFERRAL: Populating limitation slot only, no explanatory content"

        return slots, True, reason

    def _build_semantic_frame(
        self,
        discourse_act: DiscourseAct,
        grounding_envelope: PhaseMinusOneEnvelope,
        intent_envelope: IntentEnvelope,
        regime: OperationalRegime,
        evidence: Dict[str, Any],
    ) -> tuple[Dict[SemanticSlot, Optional[str]], bool, str]:
        """
        Build a non-DEFERRAL semantic frame.

        Steps:
        1. Get allowed slots from discourse act allow-list
        2. Initialize all allowed slots with None
        3. Populate slots conservatively using grounding and intent
        4. Use grammar evidence only if unambiguous

        Args:
            discourse_act: The discourse act from P7.
            grounding_envelope: PO1 grounding envelope.
            intent_envelope: PO2 intent envelope.
            regime: The operational regime.
            evidence: Grammar evidence (evidence-only).

        Returns:
            Tuple of (slots dict, allowed bool, reason string).
        """
        # Step 2: Get allowed slots for this discourse act
        allowed_slots = DISCOURSE_ACT_ALLOWED_SLOTS.get(
            discourse_act, frozenset()
        )
        slots: Dict[SemanticSlot, Optional[str]] = {}

        # Initialize all allowed slots with None
        for slot in allowed_slots:
            slots[slot] = None

        # Step 3: Populate slots conservatively
        # Use grounding for AGENT / TARGET determination
        if SemanticSlot.AGENT in slots:
            slots[SemanticSlot.AGENT] = self._resolve_agent(
                grounding_envelope, evidence
            )

        if SemanticSlot.TARGET in slots:
            slots[SemanticSlot.TARGET] = self._resolve_target(
                grounding_envelope, evidence
            )

        if SemanticSlot.STATE in slots:
            slots[SemanticSlot.STATE] = self._resolve_state(
                grounding_envelope, intent_envelope, evidence
            )

        if SemanticSlot.REQUEST_FOCUS in slots:
            slots[SemanticSlot.REQUEST_FOCUS] = self._resolve_request_focus(
                grounding_envelope, intent_envelope, evidence
            )

        if SemanticSlot.TEMPORAL_CONTEXT in slots:
            slots[SemanticSlot.TEMPORAL_CONTEXT] = self._resolve_temporal_context(
                evidence
            )

        if SemanticSlot.UNCERTAINTY in slots:
            slots[SemanticSlot.UNCERTAINTY] = self._resolve_uncertainty(
                grounding_envelope, evidence
            )

        if SemanticSlot.LIMITATION in slots:
            slots[SemanticSlot.LIMITATION] = self._resolve_limitation(
                grounding_envelope, regime, evidence
            )

        if SemanticSlot.CONSTRAINT in slots:
            slots[SemanticSlot.CONSTRAINT] = self._resolve_constraint(
                grounding_envelope, evidence
            )

        if SemanticSlot.CAUSE in slots:
            # CAUSE is special - requires regime validation
            slots[SemanticSlot.CAUSE] = self._resolve_cause(
                grounding_envelope, regime, evidence
            )

        reason = f"Semantic {discourse_act.value}: Populated {len([v for v in slots.values() if v is not None])}/{len(slots)} allowed slots"

        return slots, True, reason

    def _resolve_agent(
        self,
        grounding_envelope: PhaseMinusOneEnvelope,
        evidence: Dict[str, Any],
    ) -> Optional[str]:
        """
        Resolve AGENT slot value conservatively.

        Uses PO1 grounding to determine the agent.
        Returns None if information is ambiguous or missing.
        """
        # Check if we have selected primary grounding
        if grounding_envelope.selected_primary is not None:
            observed = grounding_envelope.selected_primary.observed
            if observed == ObservedEntity.SELF:
                return "user_self"
            elif observed == ObservedEntity.OTHER:
                return "other_entity"
            elif observed == ObservedEntity.PHENOMENON:
                return "phenomenon"

        # Check clause groundings if no primary
        for clause in grounding_envelope.clauses:
            if clause.selected is not None:
                observed = clause.selected.observed
                if observed == ObservedEntity.SELF:
                    return "user_self"
                elif observed == ObservedEntity.OTHER:
                    return "other_entity"
                # Don't return phenomenon as agent by default

        # Use grammar evidence only if unambiguous
        if evidence.get("subject_detected") and evidence.get("subject_type"):
            subj_type = evidence.get("subject_type")
            if subj_type in ("first_person", "user"):
                return "user_self"
            elif subj_type == "third_person":
                return "other_entity"

        # Conservative default: None
        return None

    def _resolve_target(
        self,
        grounding_envelope: PhaseMinusOneEnvelope,
        evidence: Dict[str, Any],
    ) -> Optional[str]:
        """
        Resolve TARGET slot value conservatively.

        Uses PO1 grounding and grammar evidence.
        Returns None if information is ambiguous or missing.
        """
        # Check if we have RELATIONAL observation mode
        if grounding_envelope.selected_primary is not None:
            mode = grounding_envelope.selected_primary.mode
            if mode == ObservationMode.RELATIONAL:
                return "relational_target"

        # Use grammar evidence only if unambiguous
        if evidence.get("object_detected") and evidence.get("object_type"):
            return evidence.get("object_type")

        # Conservative default: None
        return None

    def _resolve_state(
        self,
        grounding_envelope: PhaseMinusOneEnvelope,
        intent_envelope: IntentEnvelope,
        evidence: Dict[str, Any],
    ) -> Optional[str]:
        """
        Resolve STATE slot value conservatively.

        Uses intent and grounding signals.
        Returns None if information is missing.
        """
        # Check observation mode for state hints
        if grounding_envelope.selected_primary is not None:
            mode = grounding_envelope.selected_primary.mode
            if mode == ObservationMode.REFLEXIVE:
                return "reflexive_state"
            elif mode == ObservationMode.RELATIONAL:
                return "relational_state"
            elif mode == ObservationMode.DETACHED:
                return "detached_state"

        # Conservative default: None
        return None

    def _resolve_request_focus(
        self,
        grounding_envelope: PhaseMinusOneEnvelope,
        intent_envelope: IntentEnvelope,
        evidence: Dict[str, Any],
    ) -> Optional[str]:
        """
        Resolve REQUEST_FOCUS slot value conservatively.

        Used for QUESTION discourse acts.
        Returns None if focus is unclear.
        """
        # Check intent type for question focus
        if intent_envelope.intent_type == IntentType.CLARIFY:
            return "clarification_needed"

        # Use grammar evidence for question focus
        if evidence.get("question_type"):
            return evidence.get("question_type")

        # Conservative default: None
        return None

    def _resolve_temporal_context(
        self,
        evidence: Dict[str, Any],
    ) -> Optional[str]:
        """
        Resolve TEMPORAL_CONTEXT slot value conservatively.

        Uses grammar evidence for temporal markers.
        Returns None if no clear temporal context.
        """
        # Use grammar evidence only if unambiguous
        if evidence.get("temporal_marker"):
            return evidence.get("temporal_marker")

        # Conservative default: None
        return None

    def _resolve_uncertainty(
        self,
        grounding_envelope: PhaseMinusOneEnvelope,
        evidence: Dict[str, Any],
    ) -> Optional[str]:
        """
        Resolve UNCERTAINTY slot value conservatively.

        Used for REFLECTION discourse acts.
        Returns None if uncertainty is unclear.
        """
        # Check grounding confidence
        stats = grounding_envelope.get_confidence_stats()
        if stats.get("mean", 1.0) < 0.7:
            return "low_confidence"
        elif stats.get("mean", 1.0) < 0.9:
            return "moderate_confidence"

        # Use grammar evidence for hedging markers
        if evidence.get("hedging_detected"):
            return "hedged"

        # Conservative default: None
        return None

    def _resolve_limitation(
        self,
        grounding_envelope: PhaseMinusOneEnvelope,
        regime: OperationalRegime,
        evidence: Dict[str, Any],
    ) -> Optional[str]:
        """
        Resolve LIMITATION slot value conservatively.

        Used for EXPLANATION and DEFERRAL discourse acts.
        Returns None if no clear limitation.
        """
        # Check regime constraints
        if regime == OperationalRegime.HOLD:
            return "hold_regime"

        # Check grounding for blocked state
        if grounding_envelope.is_blocked():
            return "blocked_grounding"

        # Check risk distribution for high projection risk
        risk_dist = grounding_envelope.get_risk_distribution()
        if risk_dist.get("HIGH", 0) > 0:
            return "high_projection_risk"

        # Conservative default: None
        return None

    def _resolve_constraint(
        self,
        grounding_envelope: PhaseMinusOneEnvelope,
        evidence: Dict[str, Any],
    ) -> Optional[str]:
        """
        Resolve CONSTRAINT slot value conservatively.

        Used for EXPLANATION and INSTRUCTION discourse acts.
        Returns None if no clear constraint.
        """
        # Check if analysis is not allowed
        if grounding_envelope.selected_primary is not None:
            if not grounding_envelope.selected_primary.analysis_allowed:
                return "analysis_restricted"

        # Conservative default: None
        return None

    def _resolve_cause(
        self,
        grounding_envelope: PhaseMinusOneEnvelope,
        regime: OperationalRegime,
        evidence: Dict[str, Any],
    ) -> Optional[str]:
        """
        Resolve CAUSE slot value conservatively.

        CAUSE is restricted under CAREFUL regime.
        Returns None if regime doesn't allow or information is missing.
        """
        # CAUSE is restricted under CAREFUL regime
        if regime in {OperationalRegime.HOLD, OperationalRegime.STABILIZE,
                      OperationalRegime.DE_ESCALATE}:
            # Do not populate CAUSE under conservative regimes
            return None

        # Only populate under INFORM regime with explicit evidence
        if regime == OperationalRegime.INFORM:
            # Check grammar evidence for causal markers
            if evidence.get("causal_marker_detected"):
                return evidence.get("causal_type", "causal_relation")

            # Check grounding for causal linkage
            for clause in grounding_envelope.clauses:
                if clause.linkage_hint and clause.linkage_hint.value == "CAUSAL":
                    return "grounding_causal"

        # Conservative default: None
        return None

    def _validate_against_regime(
        self,
        discourse_act: DiscourseAct,
        slots: Dict[SemanticSlot, Optional[str]],
        allowed: bool,
        reason: str,
        regime: OperationalRegime,
    ) -> tuple[Dict[SemanticSlot, Optional[str]], bool, str]:
        """
        Validate resolved slots against regime constraints.

        If regime == HOLD: Only DEFERRAL frame allowed.
        If regime == CAREFUL: CAUSE slot is blocked unless explicitly safe.

        Args:
            discourse_act: The discourse act.
            slots: The resolved slots dictionary.
            allowed: Whether the frame was allowed by rules.
            reason: The reason string.
            regime: The operational regime.

        Returns:
            Tuple of (slots dict, allowed bool, reason string).
        """
        # Rule: If regime == HOLD, only DEFERRAL is allowed
        if regime == OperationalRegime.HOLD:
            if discourse_act != DiscourseAct.DEFERRAL:
                # Clear all slots and return disallowed
                return (
                    {},
                    False,
                    f"Semantic frame BLOCKED: Regime is HOLD but discourse act is {discourse_act.value}"
                )

        # Rule: Under CAREFUL regime, clear CAUSE slot if present
        if regime in {OperationalRegime.STABILIZE, OperationalRegime.DE_ESCALATE}:
            if SemanticSlot.CAUSE in slots and slots[SemanticSlot.CAUSE] is not None:
                slots = dict(slots)  # Make mutable copy
                slots[SemanticSlot.CAUSE] = None
                reason = f"{reason}; CAUSE cleared due to {regime.value} regime"

        return slots, allowed, reason

    def _build_debug_info(
        self,
        grounding_envelope: PhaseMinusOneEnvelope,
        intent_envelope: IntentEnvelope,
        regime_envelope: RegimeEnvelope,
        discourse_envelope: DiscourseEnvelope,
        grammar_evidence: Dict[str, Any],
        slots: Dict[SemanticSlot, Optional[str]],
    ) -> Dict[str, Any]:
        """Build debug information for tracing."""
        return {
            "source_intent": intent_envelope.intent_type.value,
            "source_posture": intent_envelope.response_posture.value,
            "source_regime": regime_envelope.regime.value,
            "source_discourse_act": discourse_envelope.act.value,
            "overall_policy": grounding_envelope.overall_policy.value,
            "grammar_evidence_present": bool(grammar_evidence),
            "grammar_evidence_keys": list(grammar_evidence.keys()) if grammar_evidence else [],
            "slots_populated": [s.value for s, v in slots.items() if v is not None],
            "slots_empty": [s.value for s, v in slots.items() if v is None],
            "total_slots": len(slots),
        }


# Public exports
__all__ = [
    "P8SemanticResolver",
    "CAREFUL_RESTRICTED_SLOTS",
]
