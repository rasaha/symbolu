"""
P8 Unit Tests

Tests for P8 Semantic Slot Resolution:
- SemanticSlot enum
- SemanticFrame dataclass
- P8SemanticResolver
- Integration with PO1/PO2/P6/P7

Test Cases (per specification):
1. QUESTION -> only REQUEST_FOCUS/TARGET/TEMPORAL_CONTEXT slots
2. REFLECTION -> no CAUSE slot (only AGENT/STATE/UNCERTAINTY)
3. EXPLANATION under CAREFUL -> CAUSE blocked
4. DEFERRAL -> only LIMITATION/REQUEST_FOCUS slots
5. Missing grammar evidence -> None slot values
6. Strict allow-list enforcement
7. Determinism (same inputs -> same output)
8. HOLD regime -> only DEFERRAL frame allowed
"""

import pytest
from symbolu.mechanical.pipeline.p8_semantics import (
    P8SemanticResolver,
    SemanticFrame,
    SemanticSlot,
    DISCOURSE_ACT_ALLOWED_SLOTS,
)
from symbolu.mechanical.pipeline.p8_semantics.p8_semantic_integration import (
    get_p8_resolver,
    maybe_run_p8,
    run_p8_directly,
    get_p8_semantic_frame,
    is_semantic_frame_allowed,
    is_deferral_frame,
    get_semantic_frame_reason,
    get_slot_value,
    has_slot,
    get_populated_slots,
    get_discourse_act_from_frame,
)
from symbolu.mechanical.pipeline.p7_discourse.p7_discourse_schema import (
    DiscourseEnvelope,
    DiscourseAct,
)
from symbolu.mechanical.pipeline.phase_zero.phase_zero_schema import (
    IntentEnvelope,
    IntentType,
    ResponsePosture,
)
from symbolu.mechanical.pipeline.phase_p6.p6_schema import (
    RegimeEnvelope,
    OperationalRegime,
)
from symbolu.mechanical.pipeline.phase_po5.po5_schema import ExecutionEligibility
from symbolu.mechanical.pipeline.grounding.phase_minus_one_schema import (
    OverallPolicy,
    PhaseMinusOneEnvelope,
    ClauseGroundingResult,
    GroundingCandidate,
    ObservedEntity,
    ObservationMode,
    ProjectionRisk,
    GroundingStatus,
    ResolutionPolicy,
)


class TestSemanticSlotEnum:
    """Tests for SemanticSlot enum."""

    def test_agent_value(self):
        """Test: AGENT slot exists."""
        assert SemanticSlot.AGENT.value == "AGENT"

    def test_target_value(self):
        """Test: TARGET slot exists."""
        assert SemanticSlot.TARGET.value == "TARGET"

    def test_state_value(self):
        """Test: STATE slot exists."""
        assert SemanticSlot.STATE.value == "STATE"

    def test_cause_value(self):
        """Test: CAUSE slot exists."""
        assert SemanticSlot.CAUSE.value == "CAUSE"

    def test_temporal_context_value(self):
        """Test: TEMPORAL_CONTEXT slot exists."""
        assert SemanticSlot.TEMPORAL_CONTEXT.value == "TEMPORAL_CONTEXT"

    def test_uncertainty_value(self):
        """Test: UNCERTAINTY slot exists."""
        assert SemanticSlot.UNCERTAINTY.value == "UNCERTAINTY"

    def test_limitation_value(self):
        """Test: LIMITATION slot exists."""
        assert SemanticSlot.LIMITATION.value == "LIMITATION"

    def test_request_focus_value(self):
        """Test: REQUEST_FOCUS slot exists."""
        assert SemanticSlot.REQUEST_FOCUS.value == "REQUEST_FOCUS"

    def test_constraint_value(self):
        """Test: CONSTRAINT slot exists."""
        assert SemanticSlot.CONSTRAINT.value == "CONSTRAINT"

    def test_all_slots_exist(self):
        """Test: all nine semantic slots exist."""
        slots = list(SemanticSlot)
        assert len(slots) == 9
        assert SemanticSlot.AGENT in slots
        assert SemanticSlot.TARGET in slots
        assert SemanticSlot.STATE in slots
        assert SemanticSlot.CAUSE in slots
        assert SemanticSlot.TEMPORAL_CONTEXT in slots
        assert SemanticSlot.UNCERTAINTY in slots
        assert SemanticSlot.LIMITATION in slots
        assert SemanticSlot.REQUEST_FOCUS in slots
        assert SemanticSlot.CONSTRAINT in slots


class TestDiscourseActAllowedSlots:
    """Tests for DISCOURSE_ACT_ALLOWED_SLOTS constant."""

    def test_question_allowed_slots(self):
        """Test: QUESTION allows only REQUEST_FOCUS/TARGET/TEMPORAL_CONTEXT."""
        allowed = DISCOURSE_ACT_ALLOWED_SLOTS[DiscourseAct.QUESTION]
        assert allowed == frozenset({
            SemanticSlot.REQUEST_FOCUS,
            SemanticSlot.TARGET,
            SemanticSlot.TEMPORAL_CONTEXT,
        })
        # CAUSE should NOT be allowed for QUESTION
        assert SemanticSlot.CAUSE not in allowed
        # AGENT should NOT be allowed for QUESTION
        assert SemanticSlot.AGENT not in allowed

    def test_reflection_allowed_slots(self):
        """Test: REFLECTION allows only AGENT/STATE/UNCERTAINTY."""
        allowed = DISCOURSE_ACT_ALLOWED_SLOTS[DiscourseAct.REFLECTION]
        assert allowed == frozenset({
            SemanticSlot.AGENT,
            SemanticSlot.STATE,
            SemanticSlot.UNCERTAINTY,
        })
        # CAUSE should NOT be allowed for REFLECTION
        assert SemanticSlot.CAUSE not in allowed

    def test_acknowledgment_allowed_slots(self):
        """Test: ACKNOWLEDGMENT allows only AGENT/STATE."""
        allowed = DISCOURSE_ACT_ALLOWED_SLOTS[DiscourseAct.ACKNOWLEDGMENT]
        assert allowed == frozenset({
            SemanticSlot.AGENT,
            SemanticSlot.STATE,
        })
        # Should NOT have CAUSE, UNCERTAINTY, etc.
        assert SemanticSlot.CAUSE not in allowed
        assert SemanticSlot.UNCERTAINTY not in allowed

    def test_explanation_allowed_slots(self):
        """Test: EXPLANATION allows AGENT/STATE/CAUSE/CONSTRAINT/LIMITATION."""
        allowed = DISCOURSE_ACT_ALLOWED_SLOTS[DiscourseAct.EXPLANATION]
        assert allowed == frozenset({
            SemanticSlot.AGENT,
            SemanticSlot.STATE,
            SemanticSlot.CAUSE,
            SemanticSlot.CONSTRAINT,
            SemanticSlot.LIMITATION,
        })

    def test_instruction_allowed_slots(self):
        """Test: INSTRUCTION allows AGENT/TARGET/CONSTRAINT/TEMPORAL_CONTEXT."""
        allowed = DISCOURSE_ACT_ALLOWED_SLOTS[DiscourseAct.INSTRUCTION]
        assert allowed == frozenset({
            SemanticSlot.AGENT,
            SemanticSlot.TARGET,
            SemanticSlot.CONSTRAINT,
            SemanticSlot.TEMPORAL_CONTEXT,
        })
        # CAUSE should NOT be allowed
        assert SemanticSlot.CAUSE not in allowed

    def test_deferral_allowed_slots(self):
        """Test: DEFERRAL allows only LIMITATION/REQUEST_FOCUS."""
        allowed = DISCOURSE_ACT_ALLOWED_SLOTS[DiscourseAct.DEFERRAL]
        assert allowed == frozenset({
            SemanticSlot.LIMITATION,
            SemanticSlot.REQUEST_FOCUS,
        })
        # Should NOT have explanatory slots
        assert SemanticSlot.CAUSE not in allowed
        assert SemanticSlot.AGENT not in allowed
        assert SemanticSlot.STATE not in allowed


class TestSemanticFrame:
    """Tests for SemanticFrame dataclass."""

    def test_basic_construction_deferral(self):
        """Test: basic frame construction with DEFERRAL act."""
        frame = SemanticFrame(
            discourse_act=DiscourseAct.DEFERRAL,
            slots={
                SemanticSlot.LIMITATION: "test_limitation",
                SemanticSlot.REQUEST_FOCUS: None,
            },
            allowed=True,
            reason="Test DEFERRAL reason",
        )

        assert frame.discourse_act == DiscourseAct.DEFERRAL
        assert frame.allowed is True
        assert frame.architectural_phase == "P8"
        assert "Test DEFERRAL reason" in frame.reason
        assert frame.slots[SemanticSlot.LIMITATION] == "test_limitation"

    def test_basic_construction_question(self):
        """Test: frame construction with QUESTION act."""
        frame = SemanticFrame(
            discourse_act=DiscourseAct.QUESTION,
            slots={
                SemanticSlot.REQUEST_FOCUS: "clarification_needed",
                SemanticSlot.TARGET: None,
                SemanticSlot.TEMPORAL_CONTEXT: None,
            },
            allowed=True,
            reason="Question frame",
        )

        assert frame.discourse_act == DiscourseAct.QUESTION
        assert frame.has_slot(SemanticSlot.REQUEST_FOCUS)
        assert frame.get_slot_value(SemanticSlot.REQUEST_FOCUS) == "clarification_needed"

    def test_basic_construction_reflection(self):
        """Test: frame construction with REFLECTION act."""
        frame = SemanticFrame(
            discourse_act=DiscourseAct.REFLECTION,
            slots={
                SemanticSlot.AGENT: "user_self",
                SemanticSlot.STATE: "reflexive_state",
                SemanticSlot.UNCERTAINTY: None,
            },
            allowed=True,
            reason="Reflection frame",
        )

        assert frame.discourse_act == DiscourseAct.REFLECTION
        assert frame.get_populated_slots() == {
            SemanticSlot.AGENT: "user_self",
            SemanticSlot.STATE: "reflexive_state",
        }

    def test_basic_construction_explanation(self):
        """Test: frame construction with EXPLANATION act."""
        frame = SemanticFrame(
            discourse_act=DiscourseAct.EXPLANATION,
            slots={
                SemanticSlot.AGENT: "user_self",
                SemanticSlot.STATE: "detached_state",
                SemanticSlot.CAUSE: None,
                SemanticSlot.CONSTRAINT: None,
                SemanticSlot.LIMITATION: None,
            },
            allowed=True,
            reason="Explanation frame",
        )

        assert frame.discourse_act == DiscourseAct.EXPLANATION
        assert len(frame.slots) == 5

    def test_immutability(self):
        """Test: SemanticFrame is frozen (immutable)."""
        frame = SemanticFrame(
            discourse_act=DiscourseAct.DEFERRAL,
            slots={SemanticSlot.LIMITATION: None},
            allowed=True,
            reason="Test reason",
        )

        with pytest.raises(Exception):  # FrozenInstanceError
            frame.allowed = False

    def test_empty_reason_raises(self):
        """Test: empty reason raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            SemanticFrame(
                discourse_act=DiscourseAct.DEFERRAL,
                slots={SemanticSlot.LIMITATION: None},
                allowed=True,
                reason="",  # Empty
            )
        assert "non-empty string" in str(exc_info.value)

    def test_none_reason_raises(self):
        """Test: None reason raises ValueError."""
        with pytest.raises(ValueError):
            SemanticFrame(
                discourse_act=DiscourseAct.DEFERRAL,
                slots={SemanticSlot.LIMITATION: None},
                allowed=True,
                reason=None,  # type: ignore
            )

    def test_invalid_slot_for_discourse_act_raises(self):
        """Test: slots not in allow-list raise ValueError."""
        with pytest.raises(ValueError) as exc_info:
            SemanticFrame(
                discourse_act=DiscourseAct.QUESTION,
                slots={
                    SemanticSlot.REQUEST_FOCUS: None,
                    SemanticSlot.CAUSE: "invalid",  # CAUSE not allowed for QUESTION
                },
                allowed=True,
                reason="Test",
            )
        assert "not allowed for discourse act" in str(exc_info.value)

    def test_get_empty_slots(self):
        """Test: get_empty_slots returns slots with None values."""
        frame = SemanticFrame(
            discourse_act=DiscourseAct.REFLECTION,
            slots={
                SemanticSlot.AGENT: "user_self",
                SemanticSlot.STATE: None,
                SemanticSlot.UNCERTAINTY: None,
            },
            allowed=True,
            reason="Test",
        )

        empty = frame.get_empty_slots()
        assert SemanticSlot.STATE in empty
        assert SemanticSlot.UNCERTAINTY in empty
        assert SemanticSlot.AGENT not in empty

    def test_is_deferral_frame(self):
        """Test: is_deferral_frame correctly identifies DEFERRAL frames."""
        deferral_frame = SemanticFrame(
            discourse_act=DiscourseAct.DEFERRAL,
            slots={SemanticSlot.LIMITATION: None},
            allowed=True,
            reason="Test",
        )
        question_frame = SemanticFrame(
            discourse_act=DiscourseAct.QUESTION,
            slots={SemanticSlot.REQUEST_FOCUS: None},
            allowed=True,
            reason="Test",
        )

        assert deferral_frame.is_deferral_frame() is True
        assert question_frame.is_deferral_frame() is False

    def test_to_dict(self):
        """Test: to_dict serialization."""
        frame = SemanticFrame(
            discourse_act=DiscourseAct.DEFERRAL,
            slots={SemanticSlot.LIMITATION: "test"},
            allowed=True,
            reason="Test reason",
        )

        d = frame.to_dict()
        assert d["discourse_act"] == "DEFERRAL"
        assert d["allowed"] is True
        assert d["reason"] == "Test reason"
        assert d["architectural_phase"] == "P8"
        assert "LIMITATION" in d["slots"]


class TestP8SemanticResolver:
    """Tests for P8SemanticResolver."""

    def _make_grounding_envelope(
        self,
        policy: OverallPolicy = OverallPolicy.SINGLE_CONTEXT,
        observed: ObservedEntity = ObservedEntity.SELF,
        mode: ObservationMode = ObservationMode.REFLEXIVE,
    ) -> PhaseMinusOneEnvelope:
        """Create a test PO1 grounding envelope."""
        candidate = GroundingCandidate(
            observed=observed,
            mode=mode,
            projection_risk=ProjectionRisk.LOW,
            analysis_allowed=True,
            confidence=0.9,
            evidence=["test evidence"],
        )
        clause = ClauseGroundingResult(
            clause_text="test clause",
            candidates=[candidate],
            selected=candidate,
            grounding_status=GroundingStatus.CONFIDENT,
            resolution_policy=ResolutionPolicy.NONE,
        )
        return PhaseMinusOneEnvelope(
            overall_policy=policy,
            clauses=[clause],
            selected_primary=candidate,
            original_text="test text",
        )

    def _make_intent_envelope(
        self,
        intent_type: IntentType = IntentType.INFORM,
        response_posture: ResponsePosture = ResponsePosture.ENGAGE_OPEN,
        policy: OverallPolicy = OverallPolicy.SINGLE_CONTEXT,
    ) -> IntentEnvelope:
        """Create a test PO2 intent envelope."""
        return IntentEnvelope(
            intent_type=intent_type,
            response_posture=response_posture,
            planning_allowed=True,
            phase_minus_one_policy=policy,
            resolution_reason="Test intent",
        )

    def _make_regime_envelope(
        self,
        regime: OperationalRegime = OperationalRegime.INFORM,
        intent: IntentType = IntentType.INFORM,
    ) -> RegimeEnvelope:
        """Create a test P6 regime envelope."""
        return RegimeEnvelope(
            regime=regime,
            reason="Test regime reason",
            intent=intent,
            execution_eligibility=ExecutionEligibility.DEFERRED,
            coherence_regime="stable",
        )

    def _make_discourse_envelope(
        self,
        act: DiscourseAct = DiscourseAct.EXPLANATION,
        regime: OperationalRegime = OperationalRegime.INFORM,
        intent: IntentType = IntentType.INFORM,
    ) -> DiscourseEnvelope:
        """Create a test P7 discourse envelope."""
        return DiscourseEnvelope(
            act=act,
            allowed=True,
            reason="Test discourse reason",
            intent=intent,
            regime=regime,
        )

    def test_resolver_initialization(self):
        """Test: resolver initializes without state."""
        resolver = P8SemanticResolver()
        assert resolver is not None

    def test_deferral_produces_limitation_only(self):
        """Test: DEFERRAL discourse act produces only LIMITATION/REQUEST_FOCUS slots."""
        resolver = P8SemanticResolver()

        grounding = self._make_grounding_envelope()
        intent = self._make_intent_envelope(IntentType.ABSTAIN)
        regime = self._make_regime_envelope(OperationalRegime.HOLD, IntentType.ABSTAIN)
        discourse = self._make_discourse_envelope(
            DiscourseAct.DEFERRAL, OperationalRegime.HOLD, IntentType.ABSTAIN
        )

        frame = resolver.resolve(
            grounding_envelope=grounding,
            intent_envelope=intent,
            regime_envelope=regime,
            discourse_envelope=discourse,
        )

        assert frame.discourse_act == DiscourseAct.DEFERRAL
        # Only LIMITATION and REQUEST_FOCUS slots should exist
        assert set(frame.slots.keys()) == {SemanticSlot.LIMITATION, SemanticSlot.REQUEST_FOCUS}
        # No explanatory slots
        assert SemanticSlot.CAUSE not in frame.slots
        assert SemanticSlot.AGENT not in frame.slots
        assert SemanticSlot.STATE not in frame.slots

    def test_question_produces_correct_slots(self):
        """Test: QUESTION discourse act produces only allowed slots."""
        resolver = P8SemanticResolver()

        grounding = self._make_grounding_envelope()
        intent = self._make_intent_envelope(IntentType.CLARIFY)
        regime = self._make_regime_envelope(OperationalRegime.CLARIFY, IntentType.CLARIFY)
        discourse = self._make_discourse_envelope(
            DiscourseAct.QUESTION, OperationalRegime.CLARIFY, IntentType.CLARIFY
        )

        frame = resolver.resolve(
            grounding_envelope=grounding,
            intent_envelope=intent,
            regime_envelope=regime,
            discourse_envelope=discourse,
        )

        assert frame.discourse_act == DiscourseAct.QUESTION
        # Only REQUEST_FOCUS, TARGET, TEMPORAL_CONTEXT should exist
        assert set(frame.slots.keys()) == {
            SemanticSlot.REQUEST_FOCUS,
            SemanticSlot.TARGET,
            SemanticSlot.TEMPORAL_CONTEXT,
        }
        # CAUSE should NOT be present
        assert SemanticSlot.CAUSE not in frame.slots

    def test_reflection_has_no_cause_slot(self):
        """Test: REFLECTION discourse act does NOT have CAUSE slot."""
        resolver = P8SemanticResolver()

        grounding = self._make_grounding_envelope()
        intent = self._make_intent_envelope(IntentType.SUPPORT)
        regime = self._make_regime_envelope(OperationalRegime.REFLECT, IntentType.SUPPORT)
        discourse = self._make_discourse_envelope(
            DiscourseAct.REFLECTION, OperationalRegime.REFLECT, IntentType.SUPPORT
        )

        frame = resolver.resolve(
            grounding_envelope=grounding,
            intent_envelope=intent,
            regime_envelope=regime,
            discourse_envelope=discourse,
        )

        assert frame.discourse_act == DiscourseAct.REFLECTION
        # Should have AGENT, STATE, UNCERTAINTY
        assert set(frame.slots.keys()) == {
            SemanticSlot.AGENT,
            SemanticSlot.STATE,
            SemanticSlot.UNCERTAINTY,
        }
        # CAUSE should NOT be present
        assert SemanticSlot.CAUSE not in frame.slots

    def test_explanation_under_careful_regime_cause_blocked(self):
        """Test: EXPLANATION under STABILIZE regime has CAUSE slot cleared."""
        resolver = P8SemanticResolver()

        grounding = self._make_grounding_envelope()
        intent = self._make_intent_envelope(IntentType.INFORM)
        # Use STABILIZE regime (conservative)
        regime = self._make_regime_envelope(OperationalRegime.STABILIZE, IntentType.INFORM)
        # P7 resolved to EXPLANATION but P8 should clear CAUSE
        discourse = self._make_discourse_envelope(
            DiscourseAct.EXPLANATION, OperationalRegime.STABILIZE, IntentType.INFORM
        )

        # Add grammar evidence with causal marker
        frame = resolver.resolve(
            grounding_envelope=grounding,
            intent_envelope=intent,
            regime_envelope=regime,
            discourse_envelope=discourse,
            grammar_evidence={"causal_marker_detected": True, "causal_type": "because"},
        )

        assert frame.discourse_act == DiscourseAct.EXPLANATION
        # CAUSE slot should exist but be None due to STABILIZE regime
        assert SemanticSlot.CAUSE in frame.slots
        assert frame.slots[SemanticSlot.CAUSE] is None

    def test_hold_regime_only_deferral_allowed(self):
        """Test: HOLD regime only allows DEFERRAL frame."""
        resolver = P8SemanticResolver()

        grounding = self._make_grounding_envelope()
        intent = self._make_intent_envelope(IntentType.INFORM)
        regime = self._make_regime_envelope(OperationalRegime.HOLD, IntentType.INFORM)
        # Even if P7 gives EXPLANATION, P8 should block it under HOLD
        discourse = self._make_discourse_envelope(
            DiscourseAct.EXPLANATION, OperationalRegime.HOLD, IntentType.INFORM
        )

        frame = resolver.resolve(
            grounding_envelope=grounding,
            intent_envelope=intent,
            regime_envelope=regime,
            discourse_envelope=discourse,
        )

        # Should be blocked
        assert frame.allowed is False
        assert "HOLD" in frame.reason

    def test_missing_grammar_evidence_produces_none_values(self):
        """Test: missing grammar evidence produces None slot values."""
        resolver = P8SemanticResolver()

        grounding = self._make_grounding_envelope()
        intent = self._make_intent_envelope(IntentType.INFORM)
        regime = self._make_regime_envelope(OperationalRegime.INFORM, IntentType.INFORM)
        discourse = self._make_discourse_envelope(
            DiscourseAct.EXPLANATION, OperationalRegime.INFORM, IntentType.INFORM
        )

        # No grammar evidence
        frame = resolver.resolve(
            grounding_envelope=grounding,
            intent_envelope=intent,
            regime_envelope=regime,
            discourse_envelope=discourse,
            grammar_evidence=None,
        )

        # Many slots should be None without evidence
        # CAUSE should be None without explicit causal markers
        assert frame.slots.get(SemanticSlot.CAUSE) is None

    def test_determinism_same_input_same_output(self):
        """Test: same inputs produce identical outputs (determinism)."""
        resolver = P8SemanticResolver()

        grounding = self._make_grounding_envelope()
        intent = self._make_intent_envelope(IntentType.INFORM)
        regime = self._make_regime_envelope(OperationalRegime.INFORM, IntentType.INFORM)
        discourse = self._make_discourse_envelope(
            DiscourseAct.EXPLANATION, OperationalRegime.INFORM, IntentType.INFORM
        )

        results = []
        for _ in range(5):
            frame = resolver.resolve(
                grounding_envelope=grounding,
                intent_envelope=intent,
                regime_envelope=regime,
                discourse_envelope=discourse,
            )
            results.append((
                frame.discourse_act,
                frame.allowed,
                frame.reason,
                tuple(sorted((k.value, v) for k, v in frame.slots.items())),
            ))

        # All results must be identical
        assert all(r == results[0] for r in results)

    def test_strict_allow_list_enforcement(self):
        """Test: slots outside allow-list are never created."""
        resolver = P8SemanticResolver()

        grounding = self._make_grounding_envelope()
        intent = self._make_intent_envelope(IntentType.SUPPORT)
        regime = self._make_regime_envelope(OperationalRegime.DE_ESCALATE, IntentType.SUPPORT)
        discourse = self._make_discourse_envelope(
            DiscourseAct.ACKNOWLEDGMENT, OperationalRegime.DE_ESCALATE, IntentType.SUPPORT
        )

        frame = resolver.resolve(
            grounding_envelope=grounding,
            intent_envelope=intent,
            regime_envelope=regime,
            discourse_envelope=discourse,
        )

        # ACKNOWLEDGMENT only allows AGENT and STATE
        assert set(frame.slots.keys()) == {SemanticSlot.AGENT, SemanticSlot.STATE}
        # All other slots must NOT exist
        assert SemanticSlot.CAUSE not in frame.slots
        assert SemanticSlot.TARGET not in frame.slots
        assert SemanticSlot.TEMPORAL_CONTEXT not in frame.slots
        assert SemanticSlot.REQUEST_FOCUS not in frame.slots

    def test_none_grounding_envelope_raises(self):
        """Test: None grounding_envelope raises ValueError."""
        resolver = P8SemanticResolver()

        intent = self._make_intent_envelope()
        regime = self._make_regime_envelope()
        discourse = self._make_discourse_envelope()

        with pytest.raises(ValueError) as exc_info:
            resolver.resolve(
                grounding_envelope=None,  # type: ignore
                intent_envelope=intent,
                regime_envelope=regime,
                discourse_envelope=discourse,
            )
        assert "grounding_envelope cannot be None" in str(exc_info.value)

    def test_none_intent_envelope_raises(self):
        """Test: None intent_envelope raises ValueError."""
        resolver = P8SemanticResolver()

        grounding = self._make_grounding_envelope()
        regime = self._make_regime_envelope()
        discourse = self._make_discourse_envelope()

        with pytest.raises(ValueError) as exc_info:
            resolver.resolve(
                grounding_envelope=grounding,
                intent_envelope=None,  # type: ignore
                regime_envelope=regime,
                discourse_envelope=discourse,
            )
        assert "intent_envelope cannot be None" in str(exc_info.value)

    def test_none_regime_envelope_raises(self):
        """Test: None regime_envelope raises ValueError."""
        resolver = P8SemanticResolver()

        grounding = self._make_grounding_envelope()
        intent = self._make_intent_envelope()
        discourse = self._make_discourse_envelope()

        with pytest.raises(ValueError) as exc_info:
            resolver.resolve(
                grounding_envelope=grounding,
                intent_envelope=intent,
                regime_envelope=None,  # type: ignore
                discourse_envelope=discourse,
            )
        assert "regime_envelope cannot be None" in str(exc_info.value)

    def test_none_discourse_envelope_raises(self):
        """Test: None discourse_envelope raises ValueError."""
        resolver = P8SemanticResolver()

        grounding = self._make_grounding_envelope()
        intent = self._make_intent_envelope()
        regime = self._make_regime_envelope()

        with pytest.raises(ValueError) as exc_info:
            resolver.resolve(
                grounding_envelope=grounding,
                intent_envelope=intent,
                regime_envelope=regime,
                discourse_envelope=None,  # type: ignore
            )
        assert "discourse_envelope cannot be None" in str(exc_info.value)

    def test_agent_resolution_from_grounding(self):
        """Test: AGENT slot is resolved from PO1 grounding."""
        resolver = P8SemanticResolver()

        # Create grounding with SELF observed
        grounding = self._make_grounding_envelope(
            observed=ObservedEntity.SELF,
            mode=ObservationMode.REFLEXIVE,
        )
        intent = self._make_intent_envelope(IntentType.SUPPORT)
        regime = self._make_regime_envelope(OperationalRegime.REFLECT, IntentType.SUPPORT)
        discourse = self._make_discourse_envelope(
            DiscourseAct.REFLECTION, OperationalRegime.REFLECT, IntentType.SUPPORT
        )

        frame = resolver.resolve(
            grounding_envelope=grounding,
            intent_envelope=intent,
            regime_envelope=regime,
            discourse_envelope=discourse,
        )

        # AGENT should be resolved from grounding
        assert frame.slots.get(SemanticSlot.AGENT) == "user_self"

    def test_target_resolution_relational(self):
        """Test: TARGET slot is resolved for RELATIONAL mode."""
        resolver = P8SemanticResolver()

        # Create grounding with RELATIONAL mode
        grounding = self._make_grounding_envelope(
            observed=ObservedEntity.OTHER,
            mode=ObservationMode.RELATIONAL,
        )
        intent = self._make_intent_envelope(IntentType.CLARIFY)
        regime = self._make_regime_envelope(OperationalRegime.CLARIFY, IntentType.CLARIFY)
        discourse = self._make_discourse_envelope(
            DiscourseAct.QUESTION, OperationalRegime.CLARIFY, IntentType.CLARIFY
        )

        frame = resolver.resolve(
            grounding_envelope=grounding,
            intent_envelope=intent,
            regime_envelope=regime,
            discourse_envelope=discourse,
        )

        # TARGET should be resolved for relational mode
        assert frame.slots.get(SemanticSlot.TARGET) == "relational_target"

    def test_instruction_slots(self):
        """Test: INSTRUCTION discourse act has correct slots."""
        resolver = P8SemanticResolver()

        grounding = self._make_grounding_envelope()
        intent = self._make_intent_envelope(IntentType.INFORM)
        regime = self._make_regime_envelope(OperationalRegime.INFORM, IntentType.INFORM)
        discourse = self._make_discourse_envelope(
            DiscourseAct.INSTRUCTION, OperationalRegime.INFORM, IntentType.INFORM
        )

        frame = resolver.resolve(
            grounding_envelope=grounding,
            intent_envelope=intent,
            regime_envelope=regime,
            discourse_envelope=discourse,
        )

        assert frame.discourse_act == DiscourseAct.INSTRUCTION
        # INSTRUCTION allows AGENT, TARGET, CONSTRAINT, TEMPORAL_CONTEXT
        assert set(frame.slots.keys()) == {
            SemanticSlot.AGENT,
            SemanticSlot.TARGET,
            SemanticSlot.CONSTRAINT,
            SemanticSlot.TEMPORAL_CONTEXT,
        }


class TestP8Integration:
    """Tests for P8 integration module."""

    def _make_grounding_envelope(self) -> PhaseMinusOneEnvelope:
        """Create a test PO1 grounding envelope."""
        candidate = GroundingCandidate(
            observed=ObservedEntity.SELF,
            mode=ObservationMode.REFLEXIVE,
            projection_risk=ProjectionRisk.LOW,
            analysis_allowed=True,
            confidence=0.9,
            evidence=["test"],
        )
        clause = ClauseGroundingResult(
            clause_text="test",
            candidates=[candidate],
            selected=candidate,
            grounding_status=GroundingStatus.CONFIDENT,
            resolution_policy=ResolutionPolicy.NONE,
        )
        return PhaseMinusOneEnvelope(
            overall_policy=OverallPolicy.SINGLE_CONTEXT,
            clauses=[clause],
            selected_primary=candidate,
        )

    def _make_intent_envelope(self) -> IntentEnvelope:
        """Create a test PO2 intent envelope."""
        return IntentEnvelope(
            intent_type=IntentType.INFORM,
            response_posture=ResponsePosture.ENGAGE_OPEN,
            planning_allowed=True,
            phase_minus_one_policy=OverallPolicy.SINGLE_CONTEXT,
        )

    def _make_regime_envelope(self) -> RegimeEnvelope:
        """Create a test P6 regime envelope."""
        return RegimeEnvelope(
            regime=OperationalRegime.INFORM,
            reason="Test",
            intent=IntentType.INFORM,
            execution_eligibility=ExecutionEligibility.DEFERRED,
            coherence_regime="stable",
        )

    def _make_discourse_envelope(self) -> DiscourseEnvelope:
        """Create a test P7 discourse envelope."""
        return DiscourseEnvelope(
            act=DiscourseAct.EXPLANATION,
            allowed=True,
            reason="Test",
            intent=IntentType.INFORM,
            regime=OperationalRegime.INFORM,
        )

    def test_get_p8_resolver_singleton(self):
        """Test: get_p8_resolver returns singleton instance."""
        resolver1 = get_p8_resolver()
        resolver2 = get_p8_resolver()
        assert resolver1 is resolver2

    def test_run_p8_directly(self):
        """Test: run_p8_directly works with explicit inputs."""
        grounding = self._make_grounding_envelope()
        intent = self._make_intent_envelope()
        regime = self._make_regime_envelope()
        discourse = self._make_discourse_envelope()

        frame = run_p8_directly(
            grounding_envelope=grounding,
            intent_envelope=intent,
            regime_envelope=regime,
            discourse_envelope=discourse,
        )

        assert frame is not None
        assert isinstance(frame, SemanticFrame)
        assert frame.discourse_act == DiscourseAct.EXPLANATION

    def test_maybe_run_p8_with_context(self):
        """Test: maybe_run_p8 works with mock context."""
        class MockContext:
            def __init__(self):
                self.phase_minus_one = None
                self.phase_zero = None
                self.p6_regime = None
                self.p7_discourse_envelope = None
                self.semantic_frame = None

        ctx = MockContext()
        ctx.phase_minus_one = self._make_grounding_envelope()
        ctx.phase_zero = self._make_intent_envelope()
        ctx.p6_regime = self._make_regime_envelope()
        ctx.p7_discourse_envelope = self._make_discourse_envelope()

        maybe_run_p8(ctx)

        assert ctx.semantic_frame is not None
        assert isinstance(ctx.semantic_frame, SemanticFrame)

    def test_maybe_run_p8_missing_p7_skips(self):
        """Test: maybe_run_p8 skips if P7 is missing."""
        class MockContext:
            def __init__(self):
                self.phase_minus_one = self._make_grounding_envelope()
                self.phase_zero = self._make_intent_envelope()
                self.p6_regime = self._make_regime_envelope()
                self.p7_discourse_envelope = None  # Missing P7
                self.semantic_frame = None

            def _make_grounding_envelope(self):
                return TestP8Integration()._make_grounding_envelope()

            def _make_intent_envelope(self):
                return TestP8Integration()._make_intent_envelope()

            def _make_regime_envelope(self):
                return TestP8Integration()._make_regime_envelope()

        ctx = MockContext()
        maybe_run_p8(ctx)

        # Should not have set semantic_frame
        assert ctx.semantic_frame is None

    def test_get_p8_semantic_frame(self):
        """Test: get_p8_semantic_frame retrieves frame from context."""
        class MockContext:
            def __init__(self):
                self.semantic_frame = SemanticFrame(
                    discourse_act=DiscourseAct.DEFERRAL,
                    slots={SemanticSlot.LIMITATION: None},
                    allowed=True,
                    reason="Test",
                )

        ctx = MockContext()
        frame = get_p8_semantic_frame(ctx)

        assert frame is not None
        assert frame.discourse_act == DiscourseAct.DEFERRAL

    def test_is_semantic_frame_allowed(self):
        """Test: is_semantic_frame_allowed checks allowed flag."""
        class MockContext:
            def __init__(self, allowed: bool):
                self.semantic_frame = SemanticFrame(
                    discourse_act=DiscourseAct.DEFERRAL,
                    slots={SemanticSlot.LIMITATION: None},
                    allowed=allowed,
                    reason="Test",
                )

        ctx_allowed = MockContext(True)
        ctx_not_allowed = MockContext(False)

        assert is_semantic_frame_allowed(ctx_allowed) is True
        assert is_semantic_frame_allowed(ctx_not_allowed) is False

    def test_is_deferral_frame(self):
        """Test: is_deferral_frame checks discourse act."""
        class MockContextDeferral:
            def __init__(self):
                self.semantic_frame = SemanticFrame(
                    discourse_act=DiscourseAct.DEFERRAL,
                    slots={SemanticSlot.LIMITATION: None},
                    allowed=True,
                    reason="Test",
                )

        class MockContextQuestion:
            def __init__(self):
                self.semantic_frame = SemanticFrame(
                    discourse_act=DiscourseAct.QUESTION,
                    slots={SemanticSlot.REQUEST_FOCUS: None},
                    allowed=True,
                    reason="Test",
                )

        assert is_deferral_frame(MockContextDeferral()) is True
        assert is_deferral_frame(MockContextQuestion()) is False

    def test_get_slot_value(self):
        """Test: get_slot_value retrieves specific slot."""
        class MockContext:
            def __init__(self):
                self.semantic_frame = SemanticFrame(
                    discourse_act=DiscourseAct.REFLECTION,
                    slots={
                        SemanticSlot.AGENT: "user_self",
                        SemanticSlot.STATE: None,
                        SemanticSlot.UNCERTAINTY: None,
                    },
                    allowed=True,
                    reason="Test",
                )

        ctx = MockContext()

        assert get_slot_value(ctx, SemanticSlot.AGENT) == "user_self"
        assert get_slot_value(ctx, SemanticSlot.STATE) is None

    def test_has_slot(self):
        """Test: has_slot checks slot existence."""
        class MockContext:
            def __init__(self):
                self.semantic_frame = SemanticFrame(
                    discourse_act=DiscourseAct.REFLECTION,
                    slots={
                        SemanticSlot.AGENT: "user_self",
                        SemanticSlot.STATE: None,
                        SemanticSlot.UNCERTAINTY: None,
                    },
                    allowed=True,
                    reason="Test",
                )

        ctx = MockContext()

        assert has_slot(ctx, SemanticSlot.AGENT) is True
        assert has_slot(ctx, SemanticSlot.CAUSE) is False

    def test_get_populated_slots(self):
        """Test: get_populated_slots returns only non-None slots."""
        class MockContext:
            def __init__(self):
                self.semantic_frame = SemanticFrame(
                    discourse_act=DiscourseAct.REFLECTION,
                    slots={
                        SemanticSlot.AGENT: "user_self",
                        SemanticSlot.STATE: "reflexive_state",
                        SemanticSlot.UNCERTAINTY: None,
                    },
                    allowed=True,
                    reason="Test",
                )

        ctx = MockContext()
        populated = get_populated_slots(ctx)

        assert len(populated) == 2
        assert SemanticSlot.AGENT in populated
        assert SemanticSlot.STATE in populated
        assert SemanticSlot.UNCERTAINTY not in populated


class TestAuthorityModel:
    """Tests for P8 authority model - cannot override upstream constraints."""

    def _make_grounding_envelope(
        self,
        blocked: bool = False,
    ) -> PhaseMinusOneEnvelope:
        """Create a test PO1 grounding envelope."""
        candidate = GroundingCandidate(
            observed=ObservedEntity.SELF,
            mode=ObservationMode.REFLEXIVE,
            projection_risk=ProjectionRisk.LOW,
            analysis_allowed=True,
            confidence=0.9,
            evidence=["test"],
        )
        clause = ClauseGroundingResult(
            clause_text="test",
            candidates=[candidate],
            selected=candidate,
            grounding_status=GroundingStatus.CONFIDENT,
            resolution_policy=ResolutionPolicy.NONE,
        )
        policy = OverallPolicy.BLOCKED if blocked else OverallPolicy.SINGLE_CONTEXT
        return PhaseMinusOneEnvelope(
            overall_policy=policy,
            clauses=[clause],
            selected_primary=candidate,
        )

    def test_p8_cannot_override_hold_regime(self):
        """Test: P8 cannot produce non-DEFERRAL frame under HOLD regime."""
        resolver = P8SemanticResolver()

        grounding = self._make_grounding_envelope()
        intent = IntentEnvelope(
            intent_type=IntentType.INFORM,
            response_posture=ResponsePosture.ENGAGE_OPEN,
            planning_allowed=True,
            phase_minus_one_policy=OverallPolicy.SINGLE_CONTEXT,
        )
        regime = RegimeEnvelope(
            regime=OperationalRegime.HOLD,
            reason="Test",
            intent=IntentType.INFORM,
            execution_eligibility=ExecutionEligibility.PROHIBITED,
            coherence_regime="volatile",
        )
        # Even if P7 gives EXPLANATION
        discourse = DiscourseEnvelope(
            act=DiscourseAct.EXPLANATION,
            allowed=True,
            reason="Test",
            intent=IntentType.INFORM,
            regime=OperationalRegime.HOLD,
        )

        frame = resolver.resolve(
            grounding_envelope=grounding,
            intent_envelope=intent,
            regime_envelope=regime,
            discourse_envelope=discourse,
        )

        # P8 MUST block this
        assert frame.allowed is False
        assert "HOLD" in frame.reason

    def test_p8_respects_deferral_from_p7(self):
        """Test: P8 produces DEFERRAL frame when P7 says DEFERRAL."""
        resolver = P8SemanticResolver()

        grounding = self._make_grounding_envelope()
        intent = IntentEnvelope(
            intent_type=IntentType.ABSTAIN,
            response_posture=ResponsePosture.HOLD,
            planning_allowed=False,
            phase_minus_one_policy=OverallPolicy.SINGLE_CONTEXT,
        )
        regime = RegimeEnvelope(
            regime=OperationalRegime.HOLD,
            reason="Test",
            intent=IntentType.ABSTAIN,
            execution_eligibility=ExecutionEligibility.PROHIBITED,
            coherence_regime="stable",
        )
        discourse = DiscourseEnvelope(
            act=DiscourseAct.DEFERRAL,
            allowed=True,
            reason="Test",
            intent=IntentType.ABSTAIN,
            regime=OperationalRegime.HOLD,
        )

        frame = resolver.resolve(
            grounding_envelope=grounding,
            intent_envelope=intent,
            regime_envelope=regime,
            discourse_envelope=discourse,
        )

        # P8 MUST respect P7's DEFERRAL
        assert frame.discourse_act == DiscourseAct.DEFERRAL
        assert frame.allowed is True


class TestNoLexicalLeakage:
    """Tests to verify P8 does not leak into lexical/word-level processing."""

    def test_slot_values_are_semantic_not_lexical(self):
        """Test: slot values are semantic identifiers, not words/phrases."""
        resolver = P8SemanticResolver()

        grounding_candidate = GroundingCandidate(
            observed=ObservedEntity.SELF,
            mode=ObservationMode.REFLEXIVE,
            projection_risk=ProjectionRisk.LOW,
            analysis_allowed=True,
            confidence=0.9,
            evidence=["test"],
        )
        clause = ClauseGroundingResult(
            clause_text="test",
            candidates=[grounding_candidate],
            selected=grounding_candidate,
            grounding_status=GroundingStatus.CONFIDENT,
            resolution_policy=ResolutionPolicy.NONE,
        )
        grounding = PhaseMinusOneEnvelope(
            overall_policy=OverallPolicy.SINGLE_CONTEXT,
            clauses=[clause],
            selected_primary=grounding_candidate,
        )
        intent = IntentEnvelope(
            intent_type=IntentType.SUPPORT,
            response_posture=ResponsePosture.ACKNOWLEDGE,
            planning_allowed=True,
            phase_minus_one_policy=OverallPolicy.SINGLE_CONTEXT,
        )
        regime = RegimeEnvelope(
            regime=OperationalRegime.REFLECT,
            reason="Test",
            intent=IntentType.SUPPORT,
            execution_eligibility=ExecutionEligibility.DEFERRED,
            coherence_regime="stable",
        )
        discourse = DiscourseEnvelope(
            act=DiscourseAct.REFLECTION,
            allowed=True,
            reason="Test",
            intent=IntentType.SUPPORT,
            regime=OperationalRegime.REFLECT,
        )

        frame = resolver.resolve(
            grounding_envelope=grounding,
            intent_envelope=intent,
            regime_envelope=regime,
            discourse_envelope=discourse,
        )

        # Slot values should be semantic identifiers, not sentences
        for slot, value in frame.slots.items():
            if value is not None:
                # Values should be short identifiers, not full sentences
                assert len(value) < 50, f"Slot {slot} has suspiciously long value: {value}"
                # Values should not contain sentence punctuation
                assert "." not in value, f"Slot {slot} contains period: {value}"
                assert "!" not in value, f"Slot {slot} contains exclamation: {value}"
                assert "?" not in value, f"Slot {slot} contains question mark: {value}"

    def test_frame_does_not_contain_generated_text(self):
        """Test: SemanticFrame does not contain generated output text."""
        frame = SemanticFrame(
            discourse_act=DiscourseAct.EXPLANATION,
            slots={
                SemanticSlot.AGENT: "user_self",
                SemanticSlot.STATE: "detached_state",
                SemanticSlot.CAUSE: None,
                SemanticSlot.CONSTRAINT: None,
                SemanticSlot.LIMITATION: None,
            },
            allowed=True,
            reason="Test semantic frame",
        )

        # Frame should not have any attributes that look like generated output
        d = frame.to_dict()
        assert "output" not in d
        assert "response" not in d
        assert "message" not in d
        assert "text" not in d


class TestGrammarEvidenceOnly:
    """Tests to verify grammar evidence is evidence-only, not authoritative."""

    def test_grammar_evidence_cannot_create_slots(self):
        """Test: grammar evidence cannot create slots outside allow-list."""
        resolver = P8SemanticResolver()

        grounding_candidate = GroundingCandidate(
            observed=ObservedEntity.SELF,
            mode=ObservationMode.REFLEXIVE,
            projection_risk=ProjectionRisk.LOW,
            analysis_allowed=True,
            confidence=0.9,
            evidence=["test"],
        )
        clause = ClauseGroundingResult(
            clause_text="test",
            candidates=[grounding_candidate],
            selected=grounding_candidate,
            grounding_status=GroundingStatus.CONFIDENT,
            resolution_policy=ResolutionPolicy.NONE,
        )
        grounding = PhaseMinusOneEnvelope(
            overall_policy=OverallPolicy.SINGLE_CONTEXT,
            clauses=[clause],
            selected_primary=grounding_candidate,
        )
        intent = IntentEnvelope(
            intent_type=IntentType.CLARIFY,
            response_posture=ResponsePosture.HOLD,
            planning_allowed=True,
            phase_minus_one_policy=OverallPolicy.SINGLE_CONTEXT,
        )
        regime = RegimeEnvelope(
            regime=OperationalRegime.CLARIFY,
            reason="Test",
            intent=IntentType.CLARIFY,
            execution_eligibility=ExecutionEligibility.DEFERRED,
            coherence_regime="stable",
        )
        discourse = DiscourseEnvelope(
            act=DiscourseAct.QUESTION,
            allowed=True,
            reason="Test",
            intent=IntentType.CLARIFY,
            regime=OperationalRegime.CLARIFY,
        )

        # Grammar evidence suggests CAUSE, but QUESTION doesn't allow CAUSE
        grammar_evidence = {
            "causal_marker_detected": True,
            "causal_type": "because",
        }

        frame = resolver.resolve(
            grounding_envelope=grounding,
            intent_envelope=intent,
            regime_envelope=regime,
            discourse_envelope=discourse,
            grammar_evidence=grammar_evidence,
        )

        # CAUSE slot should NOT be present even with grammar evidence
        assert SemanticSlot.CAUSE not in frame.slots

    def test_grammar_evidence_populates_allowed_slots(self):
        """Test: grammar evidence can populate already-allowed slots."""
        resolver = P8SemanticResolver()

        grounding_candidate = GroundingCandidate(
            observed=ObservedEntity.PHENOMENON,
            mode=ObservationMode.DETACHED,
            projection_risk=ProjectionRisk.LOW,
            analysis_allowed=True,
            confidence=0.9,
            evidence=["test"],
        )
        clause = ClauseGroundingResult(
            clause_text="test",
            candidates=[grounding_candidate],
            selected=grounding_candidate,
            grounding_status=GroundingStatus.CONFIDENT,
            resolution_policy=ResolutionPolicy.NONE,
        )
        grounding = PhaseMinusOneEnvelope(
            overall_policy=OverallPolicy.SINGLE_CONTEXT,
            clauses=[clause],
            selected_primary=grounding_candidate,
        )
        intent = IntentEnvelope(
            intent_type=IntentType.INFORM,
            response_posture=ResponsePosture.ENGAGE_OPEN,
            planning_allowed=True,
            phase_minus_one_policy=OverallPolicy.SINGLE_CONTEXT,
        )
        regime = RegimeEnvelope(
            regime=OperationalRegime.INFORM,
            reason="Test",
            intent=IntentType.INFORM,
            execution_eligibility=ExecutionEligibility.DEFERRED,
            coherence_regime="stable",
        )
        discourse = DiscourseEnvelope(
            act=DiscourseAct.EXPLANATION,
            allowed=True,
            reason="Test",
            intent=IntentType.INFORM,
            regime=OperationalRegime.INFORM,
        )

        # Grammar evidence with causal marker
        grammar_evidence = {
            "causal_marker_detected": True,
            "causal_type": "because_clause",
        }

        frame = resolver.resolve(
            grounding_envelope=grounding,
            intent_envelope=intent,
            regime_envelope=regime,
            discourse_envelope=discourse,
            grammar_evidence=grammar_evidence,
        )

        # CAUSE slot should be populated from grammar evidence
        # (EXPLANATION allows CAUSE, and regime is INFORM which permits it)
        assert SemanticSlot.CAUSE in frame.slots
        assert frame.slots[SemanticSlot.CAUSE] == "because_clause"
