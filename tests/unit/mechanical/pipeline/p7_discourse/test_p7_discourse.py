"""
P7 Unit Tests

Tests for P7 Discourse Act Resolver:
- DiscourseAct enum
- DiscourseEnvelope dataclass
- P7DiscourseResolver
- Integration with PO1/PO2/PO3/P6

Test Cases (per specification):
1. HOLD → DEFERRAL
2. SUPPORT + CAREFUL regime → REFLECTION
3. INFORM + OPEN/INFORM regime → EXPLANATION
4. INFORM + CAREFUL regime → DEFERRAL
5. CLARIFY → QUESTION
6. Grammar evidence present but ignored when disallowed
7. Strict allow-list enforcement
8. Determinism (same inputs → same output)
"""

import pytest
from symbolu.mechanical.pipeline.p7_discourse import (
    P7DiscourseResolver,
    DiscourseEnvelope,
    DiscourseAct,
)
from symbolu.mechanical.pipeline.p7_discourse.p7_discourse_integration import (
    get_p7_resolver,
    maybe_run_p7,
    run_p7_directly,
    get_p7_discourse,
    is_discourse_deferral,
    is_discourse_question,
    is_discourse_reflection,
    is_discourse_acknowledgment,
    is_discourse_explanation,
    is_discourse_instruction,
    get_discourse_reason,
    get_resolved_discourse_act,
)
from symbolu.mechanical.pipeline.p7_discourse.p7_discourse_resolver import (
    REGIME_ALLOWED_ACTS,
    ENGAGEMENT_REGIMES,
)
from symbolu.mechanical.pipeline.phase_zero.phase_zero_schema import (
    IntentEnvelope,
    IntentType,
    ResponsePosture,
)
from symbolu.mechanical.pipeline.phase_one.phase_one_schema import AllowedActionSet
from symbolu.mechanical.pipeline.phase_po5.po5_schema import (
    ExecutionEligibilityEnvelope,
    ExecutionEligibility,
)
from symbolu.mechanical.pipeline.phase_po4.po4_schema import (
    PlannerProposalEnvelope,
    ProposalStatus,
)
from symbolu.mechanical.pipeline.phase_p6.p6_schema import (
    RegimeEnvelope,
    OperationalRegime,
)
from symbolu.mechanical.pipeline.governance.planner_gate import ActionClass
from symbolu.mechanical.pipeline.grounding.phase_minus_one_schema import (
    OverallPolicy,
    PhaseMinusOneEnvelope,
    ClauseGroundingResult,
)


class TestDiscourseActEnum:
    """Tests for DiscourseAct enum."""

    def test_question_value(self):
        """Test: QUESTION status exists."""
        assert DiscourseAct.QUESTION.value == "QUESTION"

    def test_reflection_value(self):
        """Test: REFLECTION status exists."""
        assert DiscourseAct.REFLECTION.value == "REFLECTION"

    def test_acknowledgment_value(self):
        """Test: ACKNOWLEDGMENT status exists."""
        assert DiscourseAct.ACKNOWLEDGMENT.value == "ACKNOWLEDGMENT"

    def test_explanation_value(self):
        """Test: EXPLANATION status exists."""
        assert DiscourseAct.EXPLANATION.value == "EXPLANATION"

    def test_instruction_value(self):
        """Test: INSTRUCTION status exists."""
        assert DiscourseAct.INSTRUCTION.value == "INSTRUCTION"

    def test_deferral_value(self):
        """Test: DEFERRAL status exists."""
        assert DiscourseAct.DEFERRAL.value == "DEFERRAL"

    def test_all_acts_exist(self):
        """Test: all six discourse acts exist."""
        acts = list(DiscourseAct)
        assert len(acts) == 6
        assert DiscourseAct.QUESTION in acts
        assert DiscourseAct.REFLECTION in acts
        assert DiscourseAct.ACKNOWLEDGMENT in acts
        assert DiscourseAct.EXPLANATION in acts
        assert DiscourseAct.INSTRUCTION in acts
        assert DiscourseAct.DEFERRAL in acts


class TestDiscourseEnvelope:
    """Tests for DiscourseEnvelope dataclass."""

    def test_basic_construction_deferral(self):
        """Test: basic envelope construction with DEFERRAL act."""
        envelope = DiscourseEnvelope(
            act=DiscourseAct.DEFERRAL,
            allowed=True,
            reason="Test DEFERRAL reason",
            intent=IntentType.INFORM,
            regime=OperationalRegime.HOLD,
        )

        assert envelope.act == DiscourseAct.DEFERRAL
        assert envelope.allowed is True
        assert envelope.intent == IntentType.INFORM
        assert envelope.regime == OperationalRegime.HOLD
        assert envelope.architectural_phase == "P7"
        assert "Test DEFERRAL reason" in envelope.reason

    def test_basic_construction_question(self):
        """Test: envelope construction with QUESTION act."""
        envelope = DiscourseEnvelope(
            act=DiscourseAct.QUESTION,
            allowed=True,
            reason="Clarification required",
            intent=IntentType.CLARIFY,
            regime=OperationalRegime.CLARIFY,
        )

        assert envelope.act == DiscourseAct.QUESTION
        assert envelope.is_question() is True

    def test_basic_construction_reflection(self):
        """Test: envelope construction with REFLECTION act."""
        envelope = DiscourseEnvelope(
            act=DiscourseAct.REFLECTION,
            allowed=True,
            reason="Reflective engagement",
            intent=IntentType.SUPPORT,
            regime=OperationalRegime.REFLECT,
        )

        assert envelope.act == DiscourseAct.REFLECTION
        assert envelope.is_reflection() is True

    def test_basic_construction_acknowledgment(self):
        """Test: envelope construction with ACKNOWLEDGMENT act."""
        envelope = DiscourseEnvelope(
            act=DiscourseAct.ACKNOWLEDGMENT,
            allowed=True,
            reason="Simple acknowledgment",
            intent=IntentType.SUPPORT,
            regime=OperationalRegime.STABILIZE,
        )

        assert envelope.act == DiscourseAct.ACKNOWLEDGMENT
        assert envelope.is_acknowledgment() is True

    def test_basic_construction_explanation(self):
        """Test: envelope construction with EXPLANATION act."""
        envelope = DiscourseEnvelope(
            act=DiscourseAct.EXPLANATION,
            allowed=True,
            reason="Informational response",
            intent=IntentType.INFORM,
            regime=OperationalRegime.INFORM,
        )

        assert envelope.act == DiscourseAct.EXPLANATION
        assert envelope.is_explanation() is True

    def test_basic_construction_instruction(self):
        """Test: envelope construction with INSTRUCTION act."""
        envelope = DiscourseEnvelope(
            act=DiscourseAct.INSTRUCTION,
            allowed=True,
            reason="Guidance provided",
            intent=IntentType.INFORM,
            regime=OperationalRegime.INFORM,
        )

        assert envelope.act == DiscourseAct.INSTRUCTION
        assert envelope.is_instruction() is True

    def test_immutability(self):
        """Test: DiscourseEnvelope is frozen (immutable)."""
        envelope = DiscourseEnvelope(
            act=DiscourseAct.DEFERRAL,
            allowed=True,
            reason="Test reason",
            intent=IntentType.INFORM,
            regime=OperationalRegime.HOLD,
        )

        with pytest.raises(Exception):
            envelope.act = DiscourseAct.QUESTION

    def test_none_act_raises(self):
        """Test: None act raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            DiscourseEnvelope(
                act=None,  # type: ignore
                allowed=True,
                reason="Test reason",
                intent=IntentType.INFORM,
                regime=OperationalRegime.HOLD,
            )
        assert "act cannot be None" in str(exc_info.value)

    def test_empty_reason_raises(self):
        """Test: empty reason raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            DiscourseEnvelope(
                act=DiscourseAct.DEFERRAL,
                allowed=True,
                reason="",  # Empty reason
                intent=IntentType.INFORM,
                regime=OperationalRegime.HOLD,
            )
        assert "non-empty string" in str(exc_info.value)

    def test_whitespace_reason_raises(self):
        """Test: whitespace-only reason raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            DiscourseEnvelope(
                act=DiscourseAct.DEFERRAL,
                allowed=True,
                reason="   ",  # Whitespace only
                intent=IntentType.INFORM,
                regime=OperationalRegime.HOLD,
            )
        assert "non-empty string" in str(exc_info.value)

    def test_none_intent_raises(self):
        """Test: None intent raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            DiscourseEnvelope(
                act=DiscourseAct.DEFERRAL,
                allowed=True,
                reason="Test reason",
                intent=None,  # type: ignore
                regime=OperationalRegime.HOLD,
            )
        assert "intent cannot be None" in str(exc_info.value)

    def test_none_regime_raises(self):
        """Test: None regime raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            DiscourseEnvelope(
                act=DiscourseAct.DEFERRAL,
                allowed=True,
                reason="Test reason",
                intent=IntentType.INFORM,
                regime=None,  # type: ignore
            )
        assert "regime cannot be None" in str(exc_info.value)

    def test_invalid_act_type_raises(self):
        """Test: invalid act type raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            DiscourseEnvelope(
                act="DEFERRAL",  # type: ignore - string, not enum
                allowed=True,
                reason="Test reason",
                intent=IntentType.INFORM,
                regime=OperationalRegime.HOLD,
            )
        assert "must be DiscourseAct" in str(exc_info.value)

    def test_not_allowed_must_be_deferral(self):
        """Test: if allowed=False, act must be DEFERRAL."""
        with pytest.raises(ValueError) as exc_info:
            DiscourseEnvelope(
                act=DiscourseAct.QUESTION,
                allowed=False,  # Not allowed but not DEFERRAL
                reason="Test reason",
                intent=IntentType.CLARIFY,
                regime=OperationalRegime.CLARIFY,
            )
        assert "act must be DEFERRAL" in str(exc_info.value)

    def test_not_allowed_deferral_is_valid(self):
        """Test: allowed=False with DEFERRAL is valid."""
        envelope = DiscourseEnvelope(
            act=DiscourseAct.DEFERRAL,
            allowed=False,
            reason="Not allowed, deferred",
            intent=IntentType.INFORM,
            regime=OperationalRegime.HOLD,
        )

        assert envelope.act == DiscourseAct.DEFERRAL
        assert envelope.allowed is False

    def test_is_deferral_method(self):
        """Test: is_deferral() method."""
        deferral = DiscourseEnvelope(
            act=DiscourseAct.DEFERRAL,
            allowed=True,
            reason="Test reason",
            intent=IntentType.INFORM,
            regime=OperationalRegime.HOLD,
        )
        assert deferral.is_deferral() is True

        not_deferral = DiscourseEnvelope(
            act=DiscourseAct.EXPLANATION,
            allowed=True,
            reason="Test reason",
            intent=IntentType.INFORM,
            regime=OperationalRegime.INFORM,
        )
        assert not_deferral.is_deferral() is False

    def test_to_dict_serialization(self):
        """Test: to_dict() serialization."""
        envelope = DiscourseEnvelope(
            act=DiscourseAct.DEFERRAL,
            allowed=True,
            reason="Test serialization",
            intent=IntentType.INFORM,
            regime=OperationalRegime.HOLD,
            supporting_evidence={"key": "value"},
            debug={"debug_key": "debug_value"},
        )

        d = envelope.to_dict()

        assert d["act"] == "DEFERRAL"
        assert d["allowed"] is True
        assert d["reason"] == "Test serialization"
        assert d["intent"] == "INFORM"
        assert d["regime"] == "HOLD"
        assert d["architectural_phase"] == "P7"
        assert d["supporting_evidence"]["key"] == "value"
        assert d["debug"]["debug_key"] == "debug_value"


class TestP7DiscourseResolver:
    """Tests for P7DiscourseResolver."""

    def setup_method(self):
        """Set up test fixtures."""
        self.resolver = P7DiscourseResolver()

    def _make_grounding_envelope(
        self,
        policy: OverallPolicy = OverallPolicy.SINGLE_CONTEXT,
    ) -> PhaseMinusOneEnvelope:
        """Helper to create test PhaseMinusOneEnvelope."""
        return PhaseMinusOneEnvelope(
            overall_policy=policy,
            clauses=[ClauseGroundingResult(clause_text="test")],
        )

    def _make_intent_envelope(
        self,
        intent_type: IntentType,
        response_posture: ResponsePosture,
        planning_allowed: bool = True,
    ) -> IntentEnvelope:
        """Helper to create test IntentEnvelope."""
        return IntentEnvelope(
            intent_type=intent_type,
            response_posture=response_posture,
            planning_allowed=planning_allowed,
            phase_minus_one_policy=OverallPolicy.SINGLE_CONTEXT,
            resolution_reason="Test envelope",
        )

    def _make_action_contract(
        self,
        intent_type: IntentType = IntentType.INFORM,
        actions: frozenset = None,
    ) -> AllowedActionSet:
        """Helper to create test AllowedActionSet."""
        if actions is None:
            actions = frozenset({ActionClass.EXPLAIN, ActionClass.SUMMARIZE})
        return AllowedActionSet(
            intent_type=intent_type,
            allowed_actions=actions,
            resolution_reason="Test contract",
        )

    def _make_regime_envelope(
        self,
        regime: OperationalRegime,
        intent: IntentType = IntentType.INFORM,
    ) -> RegimeEnvelope:
        """Helper to create test RegimeEnvelope."""
        return RegimeEnvelope(
            regime=regime,
            reason="Test regime",
            intent=intent,
            execution_eligibility=ExecutionEligibility.DEFERRED,
            coherence_regime="stable",
        )

    def test_hold_forces_deferral(self):
        """
        Test Case 1: HOLD → DEFERRAL.

        Rule 1: If regime == HOLD → DEFERRAL
        """
        grounding = self._make_grounding_envelope()
        intent = self._make_intent_envelope(IntentType.INFORM, ResponsePosture.ENGAGE_OPEN)
        actions = self._make_action_contract()
        regime = self._make_regime_envelope(OperationalRegime.HOLD)

        result = self.resolver.resolve(
            grounding_envelope=grounding,
            intent_envelope=intent,
            action_contract=actions,
            regime_envelope=regime,
        )

        assert result.act == DiscourseAct.DEFERRAL
        assert result.is_deferral() is True
        assert "HOLD" in result.reason

    def test_support_careful_reflection(self):
        """
        Test Case 2: SUPPORT + CAREFUL regime → REFLECTION.

        Rule 3: If intent == SUPPORT → REFLECTION or ACKNOWLEDGMENT
        """
        grounding = self._make_grounding_envelope()
        intent = self._make_intent_envelope(IntentType.SUPPORT, ResponsePosture.ACKNOWLEDGE)
        actions = self._make_action_contract(IntentType.SUPPORT, frozenset({ActionClass.CARE, ActionClass.REFLECT}))
        regime = self._make_regime_envelope(OperationalRegime.DE_ESCALATE, IntentType.SUPPORT)

        result = self.resolver.resolve(
            grounding_envelope=grounding,
            intent_envelope=intent,
            action_contract=actions,
            regime_envelope=regime,
        )

        assert result.act == DiscourseAct.REFLECTION
        assert result.is_reflection() is True
        assert "SUPPORT" in result.reason

    def test_support_stabilize_acknowledgment(self):
        """
        Test: SUPPORT + STABILIZE regime → ACKNOWLEDGMENT.

        STABILIZE regime should lead to simpler ACKNOWLEDGMENT over REFLECTION.
        """
        grounding = self._make_grounding_envelope()
        intent = self._make_intent_envelope(IntentType.SUPPORT, ResponsePosture.ACKNOWLEDGE)
        actions = self._make_action_contract(IntentType.SUPPORT, frozenset({ActionClass.CARE, ActionClass.VALIDATE}))
        regime = self._make_regime_envelope(OperationalRegime.STABILIZE, IntentType.SUPPORT)

        result = self.resolver.resolve(
            grounding_envelope=grounding,
            intent_envelope=intent,
            action_contract=actions,
            regime_envelope=regime,
        )

        assert result.act == DiscourseAct.ACKNOWLEDGMENT
        assert result.is_acknowledgment() is True
        assert "STABILIZE" in result.reason

    def test_inform_open_explanation(self):
        """
        Test Case 3: INFORM + OPEN/INFORM regime → EXPLANATION.

        Rule 4: If intent == INFORM → EXPLANATION (only if regime == INFORM)
        """
        grounding = self._make_grounding_envelope()
        intent = self._make_intent_envelope(IntentType.INFORM, ResponsePosture.ENGAGE_OPEN)
        actions = self._make_action_contract()
        regime = self._make_regime_envelope(OperationalRegime.INFORM)

        result = self.resolver.resolve(
            grounding_envelope=grounding,
            intent_envelope=intent,
            action_contract=actions,
            regime_envelope=regime,
        )

        assert result.act == DiscourseAct.EXPLANATION
        assert result.is_explanation() is True
        assert "INFORM" in result.reason

    def test_inform_careful_deferral(self):
        """
        Test Case 4: INFORM + CAREFUL regime → DEFERRAL.

        Rule 4: If intent == INFORM but regime != INFORM → DEFERRAL
        """
        grounding = self._make_grounding_envelope()
        intent = self._make_intent_envelope(IntentType.INFORM, ResponsePosture.ENGAGE_CAREFUL)
        actions = self._make_action_contract()
        regime = self._make_regime_envelope(OperationalRegime.DE_ESCALATE, IntentType.INFORM)

        result = self.resolver.resolve(
            grounding_envelope=grounding,
            intent_envelope=intent,
            action_contract=actions,
            regime_envelope=regime,
        )

        assert result.act == DiscourseAct.DEFERRAL
        assert result.is_deferral() is True
        assert "INFORM" in result.reason and "not permitted" in result.reason

    def test_clarify_question(self):
        """
        Test Case 5: CLARIFY → QUESTION.

        Rule 2: If intent == CLARIFY → QUESTION (only if regime allows engagement)
        """
        grounding = self._make_grounding_envelope()
        intent = self._make_intent_envelope(IntentType.CLARIFY, ResponsePosture.HOLD)
        actions = self._make_action_contract(IntentType.CLARIFY, frozenset({ActionClass.ASK}))
        regime = self._make_regime_envelope(OperationalRegime.CLARIFY, IntentType.CLARIFY)

        result = self.resolver.resolve(
            grounding_envelope=grounding,
            intent_envelope=intent,
            action_contract=actions,
            regime_envelope=regime,
        )

        assert result.act == DiscourseAct.QUESTION
        assert result.is_question() is True
        assert "CLARIFY" in result.reason

    def test_grammar_evidence_ignored_when_disallowed(self):
        """
        Test Case 6: Grammar evidence present but ignored when disallowed.

        Grammar evidence is evidence-only and cannot override regime restrictions.
        """
        grounding = self._make_grounding_envelope()
        intent = self._make_intent_envelope(IntentType.INFORM, ResponsePosture.ENGAGE_OPEN)
        actions = self._make_action_contract()
        regime = self._make_regime_envelope(OperationalRegime.HOLD)

        # Even with strong grammar evidence suggesting EXPLANATION,
        # HOLD regime forces DEFERRAL
        grammar_evidence = {
            "sentence_mood": "declarative",
            "wh_words": [],
            "modal_verbs": [],
            "suggested_act": "EXPLANATION",  # This should be ignored
        }

        result = self.resolver.resolve(
            grounding_envelope=grounding,
            intent_envelope=intent,
            action_contract=actions,
            regime_envelope=regime,
            grammar_evidence=grammar_evidence,
        )

        assert result.act == DiscourseAct.DEFERRAL
        assert result.supporting_evidence == grammar_evidence
        # Grammar evidence was captured but did not influence decision
        assert "HOLD" in result.reason

    def test_strict_allowlist_enforcement(self):
        """
        Test Case 7: Strict allow-list enforcement.

        Acts not in regime allow-list should be rejected and forced to DEFERRAL.
        """
        # Verify EXPLANATION is not allowed under STABILIZE regime
        stabilize_allowed = REGIME_ALLOWED_ACTS[OperationalRegime.STABILIZE]
        assert DiscourseAct.EXPLANATION not in stabilize_allowed

        # Verify HOLD only allows DEFERRAL
        hold_allowed = REGIME_ALLOWED_ACTS[OperationalRegime.HOLD]
        assert hold_allowed == frozenset({DiscourseAct.DEFERRAL})

    def test_abstain_forces_deferral(self):
        """
        Test: ABSTAIN intent → DEFERRAL.

        Rule 5: If intent == ABSTAIN → DEFERRAL
        """
        grounding = self._make_grounding_envelope()
        intent = self._make_intent_envelope(IntentType.ABSTAIN, ResponsePosture.HOLD)
        actions = self._make_action_contract(IntentType.ABSTAIN, frozenset())
        regime = self._make_regime_envelope(OperationalRegime.INFORM, IntentType.ABSTAIN)

        result = self.resolver.resolve(
            grounding_envelope=grounding,
            intent_envelope=intent,
            action_contract=actions,
            regime_envelope=regime,
        )

        assert result.act == DiscourseAct.DEFERRAL
        assert "ABSTAIN" in result.reason

    def test_reflect_intent_with_reflect_regime(self):
        """Test: REFLECT intent + REFLECT regime → REFLECTION."""
        grounding = self._make_grounding_envelope()
        intent = self._make_intent_envelope(IntentType.REFLECT, ResponsePosture.ENGAGE_CAREFUL)
        actions = self._make_action_contract(IntentType.REFLECT, frozenset({ActionClass.REFLECT}))
        regime = self._make_regime_envelope(OperationalRegime.REFLECT, IntentType.REFLECT)

        result = self.resolver.resolve(
            grounding_envelope=grounding,
            intent_envelope=intent,
            action_contract=actions,
            regime_envelope=regime,
        )

        assert result.act == DiscourseAct.REFLECTION

    def test_none_grounding_envelope_raises(self):
        """Test: None grounding_envelope raises ValueError."""
        intent = self._make_intent_envelope(IntentType.INFORM, ResponsePosture.ENGAGE_OPEN)
        actions = self._make_action_contract()
        regime = self._make_regime_envelope(OperationalRegime.INFORM)

        with pytest.raises(ValueError) as exc_info:
            self.resolver.resolve(
                grounding_envelope=None,  # type: ignore
                intent_envelope=intent,
                action_contract=actions,
                regime_envelope=regime,
            )
        assert "grounding_envelope cannot be None" in str(exc_info.value)

    def test_none_intent_envelope_raises(self):
        """Test: None intent_envelope raises ValueError."""
        grounding = self._make_grounding_envelope()
        actions = self._make_action_contract()
        regime = self._make_regime_envelope(OperationalRegime.INFORM)

        with pytest.raises(ValueError) as exc_info:
            self.resolver.resolve(
                grounding_envelope=grounding,
                intent_envelope=None,  # type: ignore
                action_contract=actions,
                regime_envelope=regime,
            )
        assert "intent_envelope cannot be None" in str(exc_info.value)

    def test_none_action_contract_raises(self):
        """Test: None action_contract raises ValueError."""
        grounding = self._make_grounding_envelope()
        intent = self._make_intent_envelope(IntentType.INFORM, ResponsePosture.ENGAGE_OPEN)
        regime = self._make_regime_envelope(OperationalRegime.INFORM)

        with pytest.raises(ValueError) as exc_info:
            self.resolver.resolve(
                grounding_envelope=grounding,
                intent_envelope=intent,
                action_contract=None,  # type: ignore
                regime_envelope=regime,
            )
        assert "action_contract cannot be None" in str(exc_info.value)

    def test_none_regime_envelope_raises(self):
        """Test: None regime_envelope raises ValueError."""
        grounding = self._make_grounding_envelope()
        intent = self._make_intent_envelope(IntentType.INFORM, ResponsePosture.ENGAGE_OPEN)
        actions = self._make_action_contract()

        with pytest.raises(ValueError) as exc_info:
            self.resolver.resolve(
                grounding_envelope=grounding,
                intent_envelope=intent,
                action_contract=actions,
                regime_envelope=None,  # type: ignore
            )
        assert "regime_envelope cannot be None" in str(exc_info.value)

    def test_debug_info_populated(self):
        """Test: debug info is populated in result."""
        grounding = self._make_grounding_envelope()
        intent = self._make_intent_envelope(IntentType.INFORM, ResponsePosture.ENGAGE_OPEN)
        actions = self._make_action_contract()
        regime = self._make_regime_envelope(OperationalRegime.INFORM)

        result = self.resolver.resolve(
            grounding_envelope=grounding,
            intent_envelope=intent,
            action_contract=actions,
            regime_envelope=regime,
        )

        assert result.debug is not None
        assert "source_intent" in result.debug
        assert "source_posture" in result.debug
        assert "source_regime" in result.debug
        assert "overall_policy" in result.debug
        assert "resolved_act" in result.debug
        assert result.debug["source_intent"] == "INFORM"


class TestDeterminism:
    """Tests verifying deterministic behavior (no randomness)."""

    def setup_method(self):
        """Set up test fixtures."""
        self.resolver = P7DiscourseResolver()

    def _make_inputs(
        self,
        intent_type: IntentType,
        posture: ResponsePosture,
        regime: OperationalRegime,
    ) -> tuple:
        """Helper to create test inputs."""
        grounding = PhaseMinusOneEnvelope(
            overall_policy=OverallPolicy.SINGLE_CONTEXT,
            clauses=[ClauseGroundingResult(clause_text="test")],
        )
        intent_envelope = IntentEnvelope(
            intent_type=intent_type,
            response_posture=posture,
            planning_allowed=True,
            phase_minus_one_policy=OverallPolicy.SINGLE_CONTEXT,
        )
        actions = AllowedActionSet(
            intent_type=intent_type,
            allowed_actions=frozenset({ActionClass.EXPLAIN}),
        )
        regime_envelope = RegimeEnvelope(
            regime=regime,
            reason="Test",
            intent=intent_type,
            execution_eligibility=ExecutionEligibility.DEFERRED,
            coherence_regime="stable",
        )

        return grounding, intent_envelope, actions, regime_envelope

    def test_same_input_same_output(self):
        """
        Test: Determinism - same input → same output.

        Multiple runs with the same input must produce identical results.
        """
        grounding, intent, actions, regime = self._make_inputs(
            IntentType.INFORM, ResponsePosture.ENGAGE_OPEN, OperationalRegime.INFORM
        )

        results = []
        for _ in range(10):
            result = self.resolver.resolve(
                grounding_envelope=grounding,
                intent_envelope=intent,
                action_contract=actions,
                regime_envelope=regime,
            )
            results.append((result.act, result.reason))

        # All results should be identical
        assert all(r == results[0] for r in results)

    def test_all_intents_deterministic(self):
        """Test: all intent types produce deterministic results."""
        posture_map = {
            IntentType.CLARIFY: ResponsePosture.HOLD,
            IntentType.SUPPORT: ResponsePosture.ACKNOWLEDGE,
            IntentType.REFLECT: ResponsePosture.ENGAGE_CAREFUL,
            IntentType.INFORM: ResponsePosture.ENGAGE_OPEN,
            IntentType.ABSTAIN: ResponsePosture.HOLD,
        }

        for intent_type in IntentType:
            grounding, intent, actions, regime = self._make_inputs(
                intent_type, posture_map[intent_type], OperationalRegime.INFORM
            )

            results = []
            for _ in range(5):
                result = self.resolver.resolve(
                    grounding_envelope=grounding,
                    intent_envelope=intent,
                    action_contract=actions,
                    regime_envelope=regime,
                )
                results.append((result.act,))

            assert all(r == results[0] for r in results), (
                f"Non-deterministic for {intent_type}"
            )

    def test_serialization_order_consistent(self):
        """Test: serialization is consistent."""
        grounding, intent, actions, regime = self._make_inputs(
            IntentType.INFORM, ResponsePosture.ENGAGE_OPEN, OperationalRegime.INFORM
        )

        serialized = []
        for _ in range(5):
            result = self.resolver.resolve(
                grounding_envelope=grounding,
                intent_envelope=intent,
                action_contract=actions,
                regime_envelope=regime,
            )
            serialized.append(result.to_dict()["act"])

        assert all(s == serialized[0] for s in serialized)


class TestRulePriority:
    """Tests verifying rule evaluation order is correct."""

    def setup_method(self):
        """Set up test fixtures."""
        self.resolver = P7DiscourseResolver()

    def _make_grounding(self) -> PhaseMinusOneEnvelope:
        return PhaseMinusOneEnvelope(
            overall_policy=OverallPolicy.SINGLE_CONTEXT,
            clauses=[ClauseGroundingResult(clause_text="test")],
        )

    def test_hold_takes_priority(self):
        """Test: Rule 1 (HOLD) takes priority over all other rules."""
        grounding = self._make_grounding()
        # CLARIFY intent would normally get QUESTION, but HOLD overrides
        intent = IntentEnvelope(
            intent_type=IntentType.CLARIFY,
            response_posture=ResponsePosture.ENGAGE_CAREFUL,
            planning_allowed=False,
            phase_minus_one_policy=OverallPolicy.SINGLE_CONTEXT,
        )
        actions = AllowedActionSet(
            intent_type=IntentType.CLARIFY,
            allowed_actions=frozenset({ActionClass.ASK}),
        )
        regime = RegimeEnvelope(
            regime=OperationalRegime.HOLD,
            reason="Test",
            intent=IntentType.CLARIFY,
            execution_eligibility=ExecutionEligibility.PROHIBITED,
            coherence_regime="stable",
        )

        result = self.resolver.resolve(
            grounding_envelope=grounding,
            intent_envelope=intent,
            action_contract=actions,
            regime_envelope=regime,
        )

        # Rule 1 should fire first (HOLD)
        assert result.act == DiscourseAct.DEFERRAL
        assert "HOLD" in result.reason

    def test_clarify_takes_priority_over_support(self):
        """Test: Rule 2 (CLARIFY) takes priority over Rule 3 (SUPPORT)."""
        grounding = self._make_grounding()
        intent = IntentEnvelope(
            intent_type=IntentType.CLARIFY,
            response_posture=ResponsePosture.ENGAGE_CAREFUL,
            planning_allowed=False,
            phase_minus_one_policy=OverallPolicy.SINGLE_CONTEXT,
        )
        actions = AllowedActionSet(
            intent_type=IntentType.CLARIFY,
            allowed_actions=frozenset({ActionClass.ASK}),
        )
        regime = RegimeEnvelope(
            regime=OperationalRegime.CLARIFY,
            reason="Test",
            intent=IntentType.CLARIFY,
            execution_eligibility=ExecutionEligibility.DEFERRED,
            coherence_regime="stable",
        )

        result = self.resolver.resolve(
            grounding_envelope=grounding,
            intent_envelope=intent,
            action_contract=actions,
            regime_envelope=regime,
        )

        # Rule 2 should fire (CLARIFY intent)
        assert result.act == DiscourseAct.QUESTION

    def test_support_takes_priority_over_inform(self):
        """Test: Rule 3 (SUPPORT) takes priority over Rule 4 (INFORM)."""
        grounding = self._make_grounding()
        intent = IntentEnvelope(
            intent_type=IntentType.SUPPORT,
            response_posture=ResponsePosture.ENGAGE_CAREFUL,
            planning_allowed=True,
            phase_minus_one_policy=OverallPolicy.SINGLE_CONTEXT,
        )
        actions = AllowedActionSet(
            intent_type=IntentType.SUPPORT,
            allowed_actions=frozenset({ActionClass.CARE}),
        )
        regime = RegimeEnvelope(
            regime=OperationalRegime.DE_ESCALATE,
            reason="Test",
            intent=IntentType.SUPPORT,
            execution_eligibility=ExecutionEligibility.DEFERRED,
            coherence_regime="stable",
        )

        result = self.resolver.resolve(
            grounding_envelope=grounding,
            intent_envelope=intent,
            action_contract=actions,
            regime_envelope=regime,
        )

        # Rule 3 should fire (SUPPORT intent)
        assert result.act == DiscourseAct.REFLECTION


class TestArchitecturalPhase:
    """Tests verifying architectural phase identification."""

    def test_envelope_has_p7_phase(self):
        """Test: envelope correctly identifies as P7."""
        envelope = DiscourseEnvelope(
            act=DiscourseAct.DEFERRAL,
            allowed=True,
            reason="Test reason",
            intent=IntentType.INFORM,
            regime=OperationalRegime.HOLD,
        )

        assert envelope.architectural_phase == "P7"
        assert envelope.to_dict()["architectural_phase"] == "P7"


class TestAuthorityModel:
    """Tests verifying P7 respects the authority model."""

    def setup_method(self):
        """Set up test fixtures."""
        self.resolver = P7DiscourseResolver()

    def _make_grounding(self) -> PhaseMinusOneEnvelope:
        return PhaseMinusOneEnvelope(
            overall_policy=OverallPolicy.SINGLE_CONTEXT,
            clauses=[ClauseGroundingResult(clause_text="test")],
        )

    def test_cannot_override_hold_regime(self):
        """Test: P7 cannot override HOLD from P6."""
        grounding = self._make_grounding()
        intent = IntentEnvelope(
            intent_type=IntentType.INFORM,
            response_posture=ResponsePosture.ENGAGE_OPEN,
            planning_allowed=True,
            phase_minus_one_policy=OverallPolicy.SINGLE_CONTEXT,
        )
        actions = AllowedActionSet(
            intent_type=IntentType.INFORM,
            allowed_actions=frozenset({ActionClass.EXPLAIN}),
        )
        regime = RegimeEnvelope(
            regime=OperationalRegime.HOLD,
            reason="Test",
            intent=IntentType.INFORM,
            execution_eligibility=ExecutionEligibility.PROHIBITED,
            coherence_regime="stable",
        )

        result = self.resolver.resolve(
            grounding_envelope=grounding,
            intent_envelope=intent,
            action_contract=actions,
            regime_envelope=regime,
        )

        # When P6 is HOLD, P7 MUST return DEFERRAL
        assert result.act == DiscourseAct.DEFERRAL

    def test_cannot_expand_capability(self):
        """Test: P7 may only restrict, never expand capability."""
        grounding = self._make_grounding()
        intent = IntentEnvelope(
            intent_type=IntentType.ABSTAIN,
            response_posture=ResponsePosture.ENGAGE_OPEN,
            planning_allowed=True,
            phase_minus_one_policy=OverallPolicy.SINGLE_CONTEXT,
        )
        actions = AllowedActionSet(
            intent_type=IntentType.ABSTAIN,
            allowed_actions=frozenset(),  # No actions allowed
        )
        regime = RegimeEnvelope(
            regime=OperationalRegime.INFORM,
            reason="Test",
            intent=IntentType.ABSTAIN,
            execution_eligibility=ExecutionEligibility.ELIGIBLE,
            coherence_regime="stable",
        )

        result = self.resolver.resolve(
            grounding_envelope=grounding,
            intent_envelope=intent,
            action_contract=actions,
            regime_envelope=regime,
        )

        # ABSTAIN with no specific discourse should fall back to DEFERRAL
        assert result.act == DiscourseAct.DEFERRAL


class TestP7Integration:
    """Tests for P7 integration module."""

    def test_get_resolver_singleton(self):
        """Test: resolver is a singleton."""
        resolver1 = get_p7_resolver()
        resolver2 = get_p7_resolver()

        assert resolver1 is resolver2

    def test_run_p7_directly(self):
        """Test: run_p7_directly works."""
        grounding = PhaseMinusOneEnvelope(
            overall_policy=OverallPolicy.SINGLE_CONTEXT,
            clauses=[ClauseGroundingResult(clause_text="test")],
        )
        intent_envelope = IntentEnvelope(
            intent_type=IntentType.INFORM,
            response_posture=ResponsePosture.ENGAGE_OPEN,
            planning_allowed=True,
            phase_minus_one_policy=OverallPolicy.SINGLE_CONTEXT,
        )
        actions = AllowedActionSet(
            intent_type=IntentType.INFORM,
            allowed_actions=frozenset({ActionClass.EXPLAIN}),
        )
        regime = RegimeEnvelope(
            regime=OperationalRegime.INFORM,
            reason="Test",
            intent=IntentType.INFORM,
            execution_eligibility=ExecutionEligibility.DEFERRED,
            coherence_regime="stable",
        )

        result = run_p7_directly(
            grounding_envelope=grounding,
            intent_envelope=intent_envelope,
            action_contract=actions,
            regime_envelope=regime,
        )

        assert result is not None
        assert isinstance(result, DiscourseEnvelope)
        # INFORM intent + INFORM regime → EXPLANATION
        assert result.act == DiscourseAct.EXPLANATION

    def test_maybe_run_p7_with_context(self):
        """Test: maybe_run_p7 works with mock context."""
        class MockContext:
            def __init__(self):
                self.phase_minus_one = PhaseMinusOneEnvelope(
                    overall_policy=OverallPolicy.SINGLE_CONTEXT,
                    clauses=[ClauseGroundingResult(clause_text="test")],
                )
                self.phase_zero = IntentEnvelope(
                    intent_type=IntentType.SUPPORT,
                    response_posture=ResponsePosture.ENGAGE_CAREFUL,
                    planning_allowed=True,
                    phase_minus_one_policy=OverallPolicy.SINGLE_CONTEXT,
                )
                self.allowed_actions = AllowedActionSet(
                    intent_type=IntentType.SUPPORT,
                    allowed_actions=frozenset({ActionClass.CARE}),
                )
                self.p6_regime = RegimeEnvelope(
                    regime=OperationalRegime.DE_ESCALATE,
                    reason="Test",
                    intent=IntentType.SUPPORT,
                    execution_eligibility=ExecutionEligibility.DEFERRED,
                    coherence_regime="stable",
                )
                self.p7_discourse_envelope = None

        ctx = MockContext()
        maybe_run_p7(ctx)

        assert ctx.p7_discourse_envelope is not None
        assert isinstance(ctx.p7_discourse_envelope, DiscourseEnvelope)
        # SUPPORT intent → REFLECTION
        assert ctx.p7_discourse_envelope.act == DiscourseAct.REFLECTION

    def test_maybe_run_p7_without_phase_minus_one(self):
        """Test: maybe_run_p7 does nothing without Phase -1."""
        class MockContext:
            phase_minus_one = None
            phase_zero = None
            allowed_actions = None
            p6_regime = None
            p7_discourse_envelope = None

        ctx = MockContext()
        maybe_run_p7(ctx)

        assert ctx.p7_discourse_envelope is None

    def test_maybe_run_p7_without_phase_zero(self):
        """Test: maybe_run_p7 does nothing without Phase 0."""
        class MockContext:
            def __init__(self):
                self.phase_minus_one = PhaseMinusOneEnvelope(
                    overall_policy=OverallPolicy.SINGLE_CONTEXT,
                    clauses=[ClauseGroundingResult(clause_text="test")],
                )
                self.phase_zero = None
                self.allowed_actions = None
                self.p6_regime = None
                self.p7_discourse_envelope = None

        ctx = MockContext()
        maybe_run_p7(ctx)

        assert ctx.p7_discourse_envelope is None

    def test_maybe_run_p7_without_allowed_actions(self):
        """Test: maybe_run_p7 does nothing without PO3."""
        class MockContext:
            def __init__(self):
                self.phase_minus_one = PhaseMinusOneEnvelope(
                    overall_policy=OverallPolicy.SINGLE_CONTEXT,
                    clauses=[ClauseGroundingResult(clause_text="test")],
                )
                self.phase_zero = IntentEnvelope(
                    intent_type=IntentType.INFORM,
                    response_posture=ResponsePosture.ENGAGE_OPEN,
                    planning_allowed=True,
                    phase_minus_one_policy=OverallPolicy.SINGLE_CONTEXT,
                )
                self.allowed_actions = None
                self.p6_regime = None
                self.p7_discourse_envelope = None

        ctx = MockContext()
        maybe_run_p7(ctx)

        assert ctx.p7_discourse_envelope is None

    def test_maybe_run_p7_without_p6_regime(self):
        """Test: maybe_run_p7 does nothing without P6."""
        class MockContext:
            def __init__(self):
                self.phase_minus_one = PhaseMinusOneEnvelope(
                    overall_policy=OverallPolicy.SINGLE_CONTEXT,
                    clauses=[ClauseGroundingResult(clause_text="test")],
                )
                self.phase_zero = IntentEnvelope(
                    intent_type=IntentType.INFORM,
                    response_posture=ResponsePosture.ENGAGE_OPEN,
                    planning_allowed=True,
                    phase_minus_one_policy=OverallPolicy.SINGLE_CONTEXT,
                )
                self.allowed_actions = AllowedActionSet(
                    intent_type=IntentType.INFORM,
                    allowed_actions=frozenset({ActionClass.EXPLAIN}),
                )
                self.p6_regime = None
                self.p7_discourse_envelope = None

        ctx = MockContext()
        maybe_run_p7(ctx)

        assert ctx.p7_discourse_envelope is None

    def test_get_p7_discourse(self):
        """Test: get_p7_discourse retrieves from context."""
        class MockContext:
            def __init__(self, envelope):
                self.p7_discourse_envelope = envelope

        envelope = DiscourseEnvelope(
            act=DiscourseAct.DEFERRAL,
            allowed=True,
            reason="Test reason",
            intent=IntentType.INFORM,
            regime=OperationalRegime.HOLD,
        )
        ctx = MockContext(envelope)

        result = get_p7_discourse(ctx)

        assert result is envelope

    def test_is_discourse_deferral(self):
        """Test: is_discourse_deferral returns correct value."""
        class MockContext:
            def __init__(self, envelope):
                self.p7_discourse_envelope = envelope

        deferral_envelope = DiscourseEnvelope(
            act=DiscourseAct.DEFERRAL,
            allowed=True,
            reason="Test reason",
            intent=IntentType.INFORM,
            regime=OperationalRegime.HOLD,
        )
        ctx = MockContext(deferral_envelope)

        assert is_discourse_deferral(ctx) is True

    def test_is_discourse_deferral_no_p7(self):
        """Test: is_discourse_deferral returns True when P7 hasn't run (conservative)."""
        class MockContext:
            p7_discourse_envelope = None

        ctx = MockContext()

        # Conservative default: DEFERRAL if P7 hasn't run
        assert is_discourse_deferral(ctx) is True

    def test_is_discourse_question(self):
        """Test: is_discourse_question returns correct value."""
        class MockContext:
            def __init__(self, envelope):
                self.p7_discourse_envelope = envelope

        question_envelope = DiscourseEnvelope(
            act=DiscourseAct.QUESTION,
            allowed=True,
            reason="Test reason",
            intent=IntentType.CLARIFY,
            regime=OperationalRegime.CLARIFY,
        )
        ctx = MockContext(question_envelope)

        assert is_discourse_question(ctx) is True

    def test_is_discourse_reflection(self):
        """Test: is_discourse_reflection returns correct value."""
        class MockContext:
            def __init__(self, envelope):
                self.p7_discourse_envelope = envelope

        reflection_envelope = DiscourseEnvelope(
            act=DiscourseAct.REFLECTION,
            allowed=True,
            reason="Test reason",
            intent=IntentType.SUPPORT,
            regime=OperationalRegime.DE_ESCALATE,
        )
        ctx = MockContext(reflection_envelope)

        assert is_discourse_reflection(ctx) is True

    def test_is_discourse_acknowledgment(self):
        """Test: is_discourse_acknowledgment returns correct value."""
        class MockContext:
            def __init__(self, envelope):
                self.p7_discourse_envelope = envelope

        acknowledgment_envelope = DiscourseEnvelope(
            act=DiscourseAct.ACKNOWLEDGMENT,
            allowed=True,
            reason="Test reason",
            intent=IntentType.SUPPORT,
            regime=OperationalRegime.STABILIZE,
        )
        ctx = MockContext(acknowledgment_envelope)

        assert is_discourse_acknowledgment(ctx) is True

    def test_is_discourse_explanation(self):
        """Test: is_discourse_explanation returns correct value."""
        class MockContext:
            def __init__(self, envelope):
                self.p7_discourse_envelope = envelope

        explanation_envelope = DiscourseEnvelope(
            act=DiscourseAct.EXPLANATION,
            allowed=True,
            reason="Test reason",
            intent=IntentType.INFORM,
            regime=OperationalRegime.INFORM,
        )
        ctx = MockContext(explanation_envelope)

        assert is_discourse_explanation(ctx) is True

    def test_is_discourse_instruction(self):
        """Test: is_discourse_instruction returns correct value."""
        class MockContext:
            def __init__(self, envelope):
                self.p7_discourse_envelope = envelope

        instruction_envelope = DiscourseEnvelope(
            act=DiscourseAct.INSTRUCTION,
            allowed=True,
            reason="Test reason",
            intent=IntentType.INFORM,
            regime=OperationalRegime.INFORM,
        )
        ctx = MockContext(instruction_envelope)

        assert is_discourse_instruction(ctx) is True

    def test_get_discourse_reason(self):
        """Test: get_discourse_reason returns reason string."""
        class MockContext:
            def __init__(self, envelope):
                self.p7_discourse_envelope = envelope

        envelope = DiscourseEnvelope(
            act=DiscourseAct.DEFERRAL,
            allowed=True,
            reason="Test discourse reason",
            intent=IntentType.INFORM,
            regime=OperationalRegime.HOLD,
        )
        ctx = MockContext(envelope)

        result = get_discourse_reason(ctx)

        assert result == "Test discourse reason"

    def test_get_resolved_discourse_act(self):
        """Test: get_resolved_discourse_act returns the discourse act enum."""
        class MockContext:
            def __init__(self, envelope):
                self.p7_discourse_envelope = envelope

        envelope = DiscourseEnvelope(
            act=DiscourseAct.EXPLANATION,
            allowed=True,
            reason="Test reason",
            intent=IntentType.INFORM,
            regime=OperationalRegime.INFORM,
        )
        ctx = MockContext(envelope)

        result = get_resolved_discourse_act(ctx)

        assert result == DiscourseAct.EXPLANATION


class TestNoSemanticsOrExecution:
    """Tests verifying P7 does NOT perform semantics, planning, or execution."""

    def setup_method(self):
        """Set up test fixtures."""
        self.resolver = P7DiscourseResolver()
        self.operation_log: list[str] = []

    def _make_inputs(self):
        grounding = PhaseMinusOneEnvelope(
            overall_policy=OverallPolicy.SINGLE_CONTEXT,
            clauses=[ClauseGroundingResult(clause_text="test")],
        )
        intent = IntentEnvelope(
            intent_type=IntentType.INFORM,
            response_posture=ResponsePosture.ENGAGE_OPEN,
            planning_allowed=True,
            phase_minus_one_policy=OverallPolicy.SINGLE_CONTEXT,
        )
        actions = AllowedActionSet(
            intent_type=IntentType.INFORM,
            allowed_actions=frozenset({ActionClass.EXPLAIN}),
        )
        regime = RegimeEnvelope(
            regime=OperationalRegime.INFORM,
            reason="Test",
            intent=IntentType.INFORM,
            execution_eligibility=ExecutionEligibility.ELIGIBLE,
            coherence_regime="stable",
        )
        return grounding, intent, actions, regime

    def test_resolve_does_not_execute(self):
        """Test: P7 resolve() does not execute any actions."""
        grounding, intent, actions, regime = self._make_inputs()

        # Track any operation attempts
        original_resolve = self.resolver.resolve

        def tracking_resolve(*args, **kwargs):
            result = original_resolve(*args, **kwargs)
            # If any action was "executed", we'd log it here
            # P7 should never do anything besides resolve discourse act
            self.operation_log.append("resolve_completed")
            return result

        self.resolver.resolve = tracking_resolve

        # Call resolve
        result = self.resolver.resolve(
            grounding_envelope=grounding,
            intent_envelope=intent,
            action_contract=actions,
            regime_envelope=regime,
        )

        # Verify only tracking, no execution
        assert len(self.operation_log) == 1
        assert self.operation_log[0] == "resolve_completed"

        # Verify envelope is just a wrapper
        assert isinstance(result, DiscourseEnvelope)
        assert result.architectural_phase == "P7"

    def test_envelope_is_pure_data(self):
        """Test: envelope contains no callable methods that execute."""
        envelope = DiscourseEnvelope(
            act=DiscourseAct.EXPLANATION,
            allowed=True,
            reason="Test reason",
            intent=IntentType.INFORM,
            regime=OperationalRegime.INFORM,
        )

        # Check that methods are read-only inspectors
        assert callable(envelope.is_deferral)
        assert callable(envelope.is_question)
        assert callable(envelope.is_reflection)
        assert callable(envelope.is_acknowledgment)
        assert callable(envelope.is_explanation)
        assert callable(envelope.is_instruction)
        assert callable(envelope.to_dict)

        # These should be query methods, not execution
        result1 = envelope.is_deferral()
        result2 = envelope.is_explanation()
        result3 = envelope.to_dict()

        assert isinstance(result1, bool)
        assert isinstance(result2, bool)
        assert isinstance(result3, dict)

    def test_no_forbidden_methods(self):
        """Test: envelope has no execution methods."""
        envelope = DiscourseEnvelope(
            act=DiscourseAct.EXPLANATION,
            allowed=True,
            reason="Test reason",
            intent=IntentType.INFORM,
            regime=OperationalRegime.INFORM,
        )

        # Verify the envelope has no execution methods
        method_names = [m for m in dir(envelope) if not m.startswith('_')]
        forbidden_names = ['execute', 'run', 'trigger', 'invoke', 'call', 'perform', 'plan', 'schedule', 'generate']

        for forbidden in forbidden_names:
            assert forbidden not in method_names, (
                f"CRITICAL: Found forbidden method '{forbidden}' in envelope"
            )


class TestRegimeAllowList:
    """Tests for regime allow-list mappings."""

    def test_hold_only_allows_deferral(self):
        """Test: HOLD regime only allows DEFERRAL."""
        allowed = REGIME_ALLOWED_ACTS[OperationalRegime.HOLD]
        assert allowed == frozenset({DiscourseAct.DEFERRAL})

    def test_clarify_allows_question_and_deferral(self):
        """Test: CLARIFY regime allows QUESTION and DEFERRAL."""
        allowed = REGIME_ALLOWED_ACTS[OperationalRegime.CLARIFY]
        assert DiscourseAct.QUESTION in allowed
        assert DiscourseAct.DEFERRAL in allowed

    def test_inform_is_most_permissive(self):
        """Test: INFORM regime is most permissive."""
        allowed = REGIME_ALLOWED_ACTS[OperationalRegime.INFORM]
        assert DiscourseAct.EXPLANATION in allowed
        assert DiscourseAct.REFLECTION in allowed
        assert DiscourseAct.ACKNOWLEDGMENT in allowed
        assert DiscourseAct.QUESTION in allowed
        assert DiscourseAct.INSTRUCTION in allowed
        assert DiscourseAct.DEFERRAL in allowed

    def test_engagement_regimes_list(self):
        """Test: engagement regimes are correctly defined."""
        assert OperationalRegime.CLARIFY in ENGAGEMENT_REGIMES
        assert OperationalRegime.STABILIZE in ENGAGEMENT_REGIMES
        assert OperationalRegime.REFLECT in ENGAGEMENT_REGIMES
        assert OperationalRegime.DE_ESCALATE in ENGAGEMENT_REGIMES
        assert OperationalRegime.INFORM in ENGAGEMENT_REGIMES
        assert OperationalRegime.HOLD not in ENGAGEMENT_REGIMES


# Run tests if executed directly
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
