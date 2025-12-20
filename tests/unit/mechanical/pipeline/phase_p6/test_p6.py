"""
P6 Unit Tests

Tests for P6 Regime Selection & Operational Mode Gate:
- OperationalRegime enum
- RegimeEnvelope dataclass
- P6RegimeGate
- Integration with PO2/PO5/Phase-41/PO1

Test Cases (per specification):
1. HOLD when execution is PROHIBITED
2. CLARIFY intent forces CLARIFY regime
3. MULTI_CONTEXT → REFLECT
4. Volatile coherence → STABILIZE
5. SUPPORT intent → DE_ESCALATE
6. INFORM intent → INFORM
7. Determinism (same inputs → same regime)
"""

import pytest
from symbolu.mechanical.pipeline.phase_p6 import (
    P6RegimeGate,
    RegimeEnvelope,
    OperationalRegime,
)
from symbolu.mechanical.pipeline.phase_p6.p6_integration import (
    get_p6_gate,
    maybe_run_p6,
    run_p6_directly,
    get_p6_regime,
    is_regime_hold,
    is_regime_stabilize,
    is_regime_reflect,
    is_regime_inform,
    is_regime_clarify,
    is_regime_de_escalate,
    get_regime_reason,
    get_selected_regime,
)
from symbolu.mechanical.pipeline.phase_zero.phase_zero_schema import (
    IntentEnvelope,
    IntentType,
    ResponsePosture,
)
from symbolu.mechanical.pipeline.phase_po5.po5_schema import (
    ExecutionEligibilityEnvelope,
    ExecutionEligibility,
)
from symbolu.mechanical.pipeline.phase_po4.po4_schema import (
    PlannerProposalEnvelope,
    ProposalStatus,
)
from symbolu.mechanical.pipeline.governance.planner_gate import ActionClass
from symbolu.mechanical.pipeline.grounding.phase_minus_one_schema import (
    OverallPolicy,
    PhaseMinusOneEnvelope,
    ClauseGroundingResult,
)


class TestOperationalRegimeEnum:
    """Tests for OperationalRegime enum."""

    def test_stabilize_value(self):
        """Test: STABILIZE status exists."""
        assert OperationalRegime.STABILIZE.value == "STABILIZE"

    def test_reflect_value(self):
        """Test: REFLECT status exists."""
        assert OperationalRegime.REFLECT.value == "REFLECT"

    def test_inform_value(self):
        """Test: INFORM status exists."""
        assert OperationalRegime.INFORM.value == "INFORM"

    def test_clarify_value(self):
        """Test: CLARIFY status exists."""
        assert OperationalRegime.CLARIFY.value == "CLARIFY"

    def test_de_escalate_value(self):
        """Test: DE_ESCALATE status exists."""
        assert OperationalRegime.DE_ESCALATE.value == "DE_ESCALATE"

    def test_hold_value(self):
        """Test: HOLD status exists."""
        assert OperationalRegime.HOLD.value == "HOLD"

    def test_all_regimes_exist(self):
        """Test: all six operational regimes exist."""
        regimes = list(OperationalRegime)
        assert len(regimes) == 6
        assert OperationalRegime.STABILIZE in regimes
        assert OperationalRegime.REFLECT in regimes
        assert OperationalRegime.INFORM in regimes
        assert OperationalRegime.CLARIFY in regimes
        assert OperationalRegime.DE_ESCALATE in regimes
        assert OperationalRegime.HOLD in regimes


class TestRegimeEnvelope:
    """Tests for RegimeEnvelope dataclass."""

    def test_basic_construction_hold(self):
        """Test: basic envelope construction with HOLD regime."""
        envelope = RegimeEnvelope(
            regime=OperationalRegime.HOLD,
            reason="Test HOLD reason",
            intent=IntentType.INFORM,
            execution_eligibility=ExecutionEligibility.PROHIBITED,
            coherence_regime="stable",
        )

        assert envelope.regime == OperationalRegime.HOLD
        assert envelope.intent == IntentType.INFORM
        assert envelope.execution_eligibility == ExecutionEligibility.PROHIBITED
        assert envelope.coherence_regime == "stable"
        assert envelope.architectural_phase == "P6"
        assert "Test HOLD reason" in envelope.reason

    def test_basic_construction_stabilize(self):
        """Test: envelope construction with STABILIZE regime."""
        envelope = RegimeEnvelope(
            regime=OperationalRegime.STABILIZE,
            reason="Stabilization required",
            intent=IntentType.SUPPORT,
            execution_eligibility=ExecutionEligibility.DEFERRED,
            coherence_regime="volatile",
        )

        assert envelope.regime == OperationalRegime.STABILIZE
        assert envelope.is_stabilize() is True

    def test_basic_construction_reflect(self):
        """Test: envelope construction with REFLECT regime."""
        envelope = RegimeEnvelope(
            regime=OperationalRegime.REFLECT,
            reason="Multi-context reflection",
            intent=IntentType.REFLECT,
            execution_eligibility=ExecutionEligibility.DEFERRED,
            coherence_regime="mixed",
        )

        assert envelope.regime == OperationalRegime.REFLECT
        assert envelope.is_reflect() is True

    def test_basic_construction_inform(self):
        """Test: envelope construction with INFORM regime."""
        envelope = RegimeEnvelope(
            regime=OperationalRegime.INFORM,
            reason="Informational response",
            intent=IntentType.INFORM,
            execution_eligibility=ExecutionEligibility.ELIGIBLE,
            coherence_regime="stable",
        )

        assert envelope.regime == OperationalRegime.INFORM
        assert envelope.is_inform() is True

    def test_basic_construction_clarify(self):
        """Test: envelope construction with CLARIFY regime."""
        envelope = RegimeEnvelope(
            regime=OperationalRegime.CLARIFY,
            reason="Clarification needed",
            intent=IntentType.CLARIFY,
            execution_eligibility=ExecutionEligibility.PROHIBITED,
            coherence_regime="stable",
        )

        assert envelope.regime == OperationalRegime.CLARIFY
        assert envelope.is_clarify() is True

    def test_basic_construction_de_escalate(self):
        """Test: envelope construction with DE_ESCALATE regime."""
        envelope = RegimeEnvelope(
            regime=OperationalRegime.DE_ESCALATE,
            reason="De-escalation required",
            intent=IntentType.SUPPORT,
            execution_eligibility=ExecutionEligibility.DEFERRED,
            coherence_regime="stable",
        )

        assert envelope.regime == OperationalRegime.DE_ESCALATE
        assert envelope.is_de_escalate() is True

    def test_immutability(self):
        """Test: RegimeEnvelope is frozen (immutable)."""
        envelope = RegimeEnvelope(
            regime=OperationalRegime.HOLD,
            reason="Test reason",
            intent=IntentType.INFORM,
            execution_eligibility=ExecutionEligibility.PROHIBITED,
            coherence_regime="stable",
        )

        with pytest.raises(Exception):
            envelope.regime = OperationalRegime.INFORM

    def test_none_regime_raises(self):
        """Test: None regime raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            RegimeEnvelope(
                regime=None,  # type: ignore
                reason="Test reason",
                intent=IntentType.INFORM,
                execution_eligibility=ExecutionEligibility.PROHIBITED,
                coherence_regime="stable",
            )
        assert "regime cannot be None" in str(exc_info.value)

    def test_empty_reason_raises(self):
        """Test: empty reason raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            RegimeEnvelope(
                regime=OperationalRegime.HOLD,
                reason="",  # Empty reason
                intent=IntentType.INFORM,
                execution_eligibility=ExecutionEligibility.PROHIBITED,
                coherence_regime="stable",
            )
        assert "non-empty string" in str(exc_info.value)

    def test_whitespace_reason_raises(self):
        """Test: whitespace-only reason raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            RegimeEnvelope(
                regime=OperationalRegime.HOLD,
                reason="   ",  # Whitespace only
                intent=IntentType.INFORM,
                execution_eligibility=ExecutionEligibility.PROHIBITED,
                coherence_regime="stable",
            )
        assert "non-empty string" in str(exc_info.value)

    def test_none_intent_raises(self):
        """Test: None intent raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            RegimeEnvelope(
                regime=OperationalRegime.HOLD,
                reason="Test reason",
                intent=None,  # type: ignore
                execution_eligibility=ExecutionEligibility.PROHIBITED,
                coherence_regime="stable",
            )
        assert "intent cannot be None" in str(exc_info.value)

    def test_none_execution_eligibility_raises(self):
        """Test: None execution_eligibility raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            RegimeEnvelope(
                regime=OperationalRegime.HOLD,
                reason="Test reason",
                intent=IntentType.INFORM,
                execution_eligibility=None,  # type: ignore
                coherence_regime="stable",
            )
        assert "execution_eligibility cannot be None" in str(exc_info.value)

    def test_none_coherence_regime_raises(self):
        """Test: None coherence_regime raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            RegimeEnvelope(
                regime=OperationalRegime.HOLD,
                reason="Test reason",
                intent=IntentType.INFORM,
                execution_eligibility=ExecutionEligibility.PROHIBITED,
                coherence_regime=None,  # type: ignore
            )
        assert "coherence_regime cannot be None" in str(exc_info.value)

    def test_invalid_regime_type_raises(self):
        """Test: invalid regime type raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            RegimeEnvelope(
                regime="HOLD",  # type: ignore - string, not enum
                reason="Test reason",
                intent=IntentType.INFORM,
                execution_eligibility=ExecutionEligibility.PROHIBITED,
                coherence_regime="stable",
            )
        assert "must be OperationalRegime" in str(exc_info.value)

    def test_is_hold_method(self):
        """Test: is_hold() method."""
        hold = RegimeEnvelope(
            regime=OperationalRegime.HOLD,
            reason="Test reason",
            intent=IntentType.INFORM,
            execution_eligibility=ExecutionEligibility.PROHIBITED,
            coherence_regime="stable",
        )
        assert hold.is_hold() is True

        not_hold = RegimeEnvelope(
            regime=OperationalRegime.INFORM,
            reason="Test reason",
            intent=IntentType.INFORM,
            execution_eligibility=ExecutionEligibility.ELIGIBLE,
            coherence_regime="stable",
        )
        assert not_hold.is_hold() is False

    def test_to_dict_serialization(self):
        """Test: to_dict() serialization."""
        envelope = RegimeEnvelope(
            regime=OperationalRegime.HOLD,
            reason="Test serialization",
            intent=IntentType.INFORM,
            execution_eligibility=ExecutionEligibility.PROHIBITED,
            coherence_regime="stable",
            debug={"key": "value"},
        )

        d = envelope.to_dict()

        assert d["regime"] == "HOLD"
        assert d["reason"] == "Test serialization"
        assert d["intent"] == "INFORM"
        assert d["execution_eligibility"] == "PROHIBITED"
        assert d["coherence_regime"] == "stable"
        assert d["architectural_phase"] == "P6"
        assert d["debug"]["key"] == "value"


class TestP6RegimeGate:
    """Tests for P6RegimeGate."""

    def setup_method(self):
        """Set up test fixtures."""
        self.gate = P6RegimeGate()

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

    def _make_execution_envelope(
        self,
        eligibility: ExecutionEligibility,
        intent: IntentType = IntentType.INFORM,
    ) -> ExecutionEligibilityEnvelope:
        """Helper to create test ExecutionEligibilityEnvelope."""
        return ExecutionEligibilityEnvelope(
            eligibility=eligibility,
            reason="Test execution eligibility",
            intent=intent,
            proposal_status=ProposalStatus.VALID,
        )

    def test_hold_when_execution_prohibited(self):
        """
        Test Case 1: HOLD when execution is PROHIBITED.

        Rule 1: If execution.eligibility == PROHIBITED → HOLD
        """
        intent_envelope = self._make_intent_envelope(
            IntentType.REFLECT,
            ResponsePosture.ENGAGE_CAREFUL,
        )
        execution = self._make_execution_envelope(
            ExecutionEligibility.PROHIBITED,
            IntentType.REFLECT,
        )

        result = self.gate.select(
            intent_envelope, execution, "stable", OverallPolicy.SINGLE_CONTEXT
        )

        assert result.regime == OperationalRegime.HOLD
        assert result.is_hold() is True
        assert "prohibited" in result.reason.lower()

    def test_clarify_intent_forces_clarify_regime(self):
        """
        Test Case 2: CLARIFY intent forces CLARIFY regime.

        Rule 2: If intent.intent == CLARIFY → CLARIFY
        """
        intent_envelope = self._make_intent_envelope(
            IntentType.CLARIFY,
            ResponsePosture.ENGAGE_CAREFUL,
        )
        # Use DEFERRED to avoid Rule 1 (PROHIBITED → HOLD)
        execution = self._make_execution_envelope(
            ExecutionEligibility.DEFERRED,
            IntentType.CLARIFY,
        )

        result = self.gate.select(
            intent_envelope, execution, "stable", OverallPolicy.SINGLE_CONTEXT
        )

        assert result.regime == OperationalRegime.CLARIFY
        assert result.is_clarify() is True
        assert "CLARIFY" in result.reason

    def test_multi_context_forces_reflect(self):
        """
        Test Case 3: MULTI_CONTEXT → REFLECT.

        Rule 3: If overall_policy == MULTI_CONTEXT → REFLECT
        """
        intent_envelope = self._make_intent_envelope(
            IntentType.SUPPORT,
            ResponsePosture.ENGAGE_CAREFUL,
        )
        execution = self._make_execution_envelope(
            ExecutionEligibility.DEFERRED,
            IntentType.SUPPORT,
        )

        result = self.gate.select(
            intent_envelope, execution, "stable", OverallPolicy.MULTI_CONTEXT
        )

        assert result.regime == OperationalRegime.REFLECT
        assert result.is_reflect() is True
        assert "REFLECT" in result.reason

    def test_volatile_coherence_forces_stabilize(self):
        """
        Test Case 4a: Volatile coherence → STABILIZE.

        Rule 4: If coherence_regime in {"volatile", "unstable"} → STABILIZE
        """
        intent_envelope = self._make_intent_envelope(
            IntentType.REFLECT,
            ResponsePosture.ENGAGE_CAREFUL,
        )
        execution = self._make_execution_envelope(
            ExecutionEligibility.DEFERRED,
            IntentType.REFLECT,
        )

        result = self.gate.select(
            intent_envelope, execution, "volatile", OverallPolicy.SINGLE_CONTEXT
        )

        assert result.regime == OperationalRegime.STABILIZE
        assert result.is_stabilize() is True
        assert "STABILIZE" in result.reason

    def test_unstable_coherence_forces_stabilize(self):
        """
        Test Case 4b: Unstable coherence → STABILIZE.

        Rule 4: If coherence_regime in {"volatile", "unstable"} → STABILIZE
        """
        intent_envelope = self._make_intent_envelope(
            IntentType.REFLECT,
            ResponsePosture.ENGAGE_CAREFUL,
        )
        execution = self._make_execution_envelope(
            ExecutionEligibility.DEFERRED,
            IntentType.REFLECT,
        )

        result = self.gate.select(
            intent_envelope, execution, "unstable", OverallPolicy.SINGLE_CONTEXT
        )

        assert result.regime == OperationalRegime.STABILIZE
        assert result.is_stabilize() is True

    def test_volatile_case_insensitive(self):
        """Test: volatile regime check is case-insensitive."""
        intent_envelope = self._make_intent_envelope(
            IntentType.REFLECT,
            ResponsePosture.ENGAGE_CAREFUL,
        )
        execution = self._make_execution_envelope(
            ExecutionEligibility.DEFERRED,
            IntentType.REFLECT,
        )

        result = self.gate.select(
            intent_envelope, execution, "VOLATILE", OverallPolicy.SINGLE_CONTEXT
        )

        assert result.regime == OperationalRegime.STABILIZE

    def test_support_intent_forces_de_escalate(self):
        """
        Test Case 5: SUPPORT intent → DE_ESCALATE.

        Rule 5: If intent.intent == SUPPORT → DE_ESCALATE
        """
        intent_envelope = self._make_intent_envelope(
            IntentType.SUPPORT,
            ResponsePosture.ENGAGE_CAREFUL,
        )
        execution = self._make_execution_envelope(
            ExecutionEligibility.DEFERRED,
            IntentType.SUPPORT,
        )

        result = self.gate.select(
            intent_envelope, execution, "stable", OverallPolicy.SINGLE_CONTEXT
        )

        assert result.regime == OperationalRegime.DE_ESCALATE
        assert result.is_de_escalate() is True
        assert "DE_ESCALATE" in result.reason

    def test_inform_intent_forces_inform(self):
        """
        Test Case 6: INFORM intent → INFORM.

        Rule 6: If intent.intent == INFORM → INFORM
        """
        intent_envelope = self._make_intent_envelope(
            IntentType.INFORM,
            ResponsePosture.ENGAGE_OPEN,
        )
        execution = self._make_execution_envelope(
            ExecutionEligibility.DEFERRED,
            IntentType.INFORM,
        )

        result = self.gate.select(
            intent_envelope, execution, "stable", OverallPolicy.SINGLE_CONTEXT
        )

        assert result.regime == OperationalRegime.INFORM
        assert result.is_inform() is True
        assert "INFORM" in result.reason

    def test_fallback_to_hold(self):
        """
        Test Case 7: Fallback → HOLD.

        Rule 7: If no other rule matches, fallback to HOLD.
        """
        # ABSTAIN intent with stable coherence and SINGLE_CONTEXT
        # should fall through to HOLD
        intent_envelope = self._make_intent_envelope(
            IntentType.ABSTAIN,
            ResponsePosture.ENGAGE_OPEN,
        )
        execution = self._make_execution_envelope(
            ExecutionEligibility.ELIGIBLE,
            IntentType.ABSTAIN,
        )

        result = self.gate.select(
            intent_envelope, execution, "stable", OverallPolicy.SINGLE_CONTEXT
        )

        assert result.regime == OperationalRegime.HOLD
        assert result.is_hold() is True
        assert "fallback" in result.reason.lower()

    def test_reflect_intent_with_stable_coherence(self):
        """
        Test: REFLECT intent with stable coherence falls through to HOLD.

        REFLECT intent is not in the rule set as a trigger for any regime,
        so it should fall through to HOLD if coherence is stable.
        """
        intent_envelope = self._make_intent_envelope(
            IntentType.REFLECT,
            ResponsePosture.ENGAGE_CAREFUL,
        )
        execution = self._make_execution_envelope(
            ExecutionEligibility.DEFERRED,
            IntentType.REFLECT,
        )

        result = self.gate.select(
            intent_envelope, execution, "stable", OverallPolicy.SINGLE_CONTEXT
        )

        # REFLECT does not have a specific regime, falls through to HOLD
        assert result.regime == OperationalRegime.HOLD

    def test_none_intent_envelope_raises(self):
        """Test: None intent_envelope raises ValueError."""
        execution = self._make_execution_envelope(ExecutionEligibility.DEFERRED)
        with pytest.raises(ValueError) as exc_info:
            self.gate.select(None, execution, "stable", OverallPolicy.SINGLE_CONTEXT)  # type: ignore
        assert "intent_envelope cannot be None" in str(exc_info.value)

    def test_none_execution_raises(self):
        """Test: None execution raises ValueError."""
        intent_envelope = self._make_intent_envelope(
            IntentType.INFORM, ResponsePosture.ENGAGE_OPEN
        )
        with pytest.raises(ValueError) as exc_info:
            self.gate.select(intent_envelope, None, "stable", OverallPolicy.SINGLE_CONTEXT)  # type: ignore
        assert "execution cannot be None" in str(exc_info.value)

    def test_none_coherence_regime_raises(self):
        """Test: None coherence_regime raises ValueError."""
        intent_envelope = self._make_intent_envelope(
            IntentType.INFORM, ResponsePosture.ENGAGE_OPEN
        )
        execution = self._make_execution_envelope(ExecutionEligibility.DEFERRED)
        with pytest.raises(ValueError) as exc_info:
            self.gate.select(intent_envelope, execution, None, OverallPolicy.SINGLE_CONTEXT)  # type: ignore
        assert "coherence_regime cannot be None" in str(exc_info.value)

    def test_none_overall_policy_raises(self):
        """Test: None overall_policy raises ValueError."""
        intent_envelope = self._make_intent_envelope(
            IntentType.INFORM, ResponsePosture.ENGAGE_OPEN
        )
        execution = self._make_execution_envelope(ExecutionEligibility.DEFERRED)
        with pytest.raises(ValueError) as exc_info:
            self.gate.select(intent_envelope, execution, "stable", None)  # type: ignore
        assert "overall_policy cannot be None" in str(exc_info.value)

    def test_debug_info_populated(self):
        """Test: debug info is populated in result."""
        intent_envelope = self._make_intent_envelope(
            IntentType.INFORM, ResponsePosture.ENGAGE_OPEN
        )
        execution = self._make_execution_envelope(
            ExecutionEligibility.DEFERRED,
            IntentType.INFORM,
        )

        result = self.gate.select(
            intent_envelope, execution, "stable", OverallPolicy.SINGLE_CONTEXT
        )

        assert result.debug is not None
        assert "source_intent" in result.debug
        assert "source_posture" in result.debug
        assert "execution_eligibility" in result.debug
        assert "coherence_regime" in result.debug
        assert "overall_policy" in result.debug
        assert result.debug["source_intent"] == "INFORM"


class TestDeterminism:
    """Tests verifying deterministic behavior (no randomness)."""

    def setup_method(self):
        """Set up test fixtures."""
        self.gate = P6RegimeGate()

    def _make_inputs(
        self, intent_type: IntentType, posture: ResponsePosture, eligibility: ExecutionEligibility
    ) -> tuple[IntentEnvelope, ExecutionEligibilityEnvelope]:
        """Helper to create test inputs."""
        intent_envelope = IntentEnvelope(
            intent_type=intent_type,
            response_posture=posture,
            planning_allowed=True,
            phase_minus_one_policy=OverallPolicy.SINGLE_CONTEXT,
        )

        execution = ExecutionEligibilityEnvelope(
            eligibility=eligibility,
            reason="Test eligibility",
            intent=intent_type,
            proposal_status=ProposalStatus.VALID,
        )

        return intent_envelope, execution

    def test_same_input_same_output(self):
        """
        Test: Determinism - same input → same output.

        Multiple runs with the same input must produce identical results.
        """
        intent_envelope, execution = self._make_inputs(
            IntentType.INFORM, ResponsePosture.ENGAGE_OPEN, ExecutionEligibility.DEFERRED
        )

        results = []
        for _ in range(10):
            result = self.gate.select(
                intent_envelope, execution, "stable", OverallPolicy.SINGLE_CONTEXT
            )
            results.append((result.regime, result.reason))

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
            intent_envelope, execution = self._make_inputs(
                intent_type, posture_map[intent_type], ExecutionEligibility.DEFERRED
            )

            results = []
            for _ in range(5):
                result = self.gate.select(
                    intent_envelope, execution, "stable", OverallPolicy.SINGLE_CONTEXT
                )
                results.append((result.regime,))

            assert all(r == results[0] for r in results), (
                f"Non-deterministic for {intent_type}"
            )

    def test_serialization_order_consistent(self):
        """Test: serialization is consistent."""
        intent_envelope, execution = self._make_inputs(
            IntentType.INFORM, ResponsePosture.ENGAGE_OPEN, ExecutionEligibility.DEFERRED
        )

        serialized = []
        for _ in range(5):
            result = self.gate.select(
                intent_envelope, execution, "stable", OverallPolicy.SINGLE_CONTEXT
            )
            serialized.append(result.to_dict()["regime"])

        assert all(s == serialized[0] for s in serialized)


class TestRulePriority:
    """Tests verifying rule evaluation order is correct."""

    def setup_method(self):
        """Set up test fixtures."""
        self.gate = P6RegimeGate()

    def test_prohibited_takes_priority(self):
        """Test: Rule 1 (PROHIBITED) takes priority over all other rules."""
        # Create scenario where multiple rules could apply
        # PROHIBITED + CLARIFY intent + MULTI_CONTEXT
        intent_envelope = IntentEnvelope(
            intent_type=IntentType.CLARIFY,
            response_posture=ResponsePosture.ENGAGE_CAREFUL,
            planning_allowed=False,
            phase_minus_one_policy=OverallPolicy.MULTI_CONTEXT,
        )
        execution = ExecutionEligibilityEnvelope(
            eligibility=ExecutionEligibility.PROHIBITED,
            reason="Prohibited by PO5",
            intent=IntentType.CLARIFY,
            proposal_status=ProposalStatus.BLOCKED,
        )

        result = self.gate.select(
            intent_envelope, execution, "volatile", OverallPolicy.MULTI_CONTEXT
        )

        # Rule 1 should fire first (PROHIBITED)
        assert result.regime == OperationalRegime.HOLD
        assert "prohibited" in result.reason.lower()

    def test_clarify_takes_priority_over_multi_context(self):
        """Test: Rule 2 (CLARIFY) takes priority over Rule 3 (MULTI_CONTEXT)."""
        intent_envelope = IntentEnvelope(
            intent_type=IntentType.CLARIFY,
            response_posture=ResponsePosture.ENGAGE_CAREFUL,
            planning_allowed=False,
            phase_minus_one_policy=OverallPolicy.MULTI_CONTEXT,
        )
        execution = ExecutionEligibilityEnvelope(
            eligibility=ExecutionEligibility.DEFERRED,
            reason="Deferred",
            intent=IntentType.CLARIFY,
            proposal_status=ProposalStatus.VALID,
        )

        result = self.gate.select(
            intent_envelope, execution, "stable", OverallPolicy.MULTI_CONTEXT
        )

        # Rule 2 should fire (CLARIFY intent)
        assert result.regime == OperationalRegime.CLARIFY
        assert "CLARIFY" in result.reason

    def test_multi_context_takes_priority_over_coherence(self):
        """Test: Rule 3 (MULTI_CONTEXT) takes priority over Rule 4 (volatile coherence)."""
        intent_envelope = IntentEnvelope(
            intent_type=IntentType.SUPPORT,
            response_posture=ResponsePosture.ENGAGE_CAREFUL,
            planning_allowed=True,
            phase_minus_one_policy=OverallPolicy.MULTI_CONTEXT,
        )
        execution = ExecutionEligibilityEnvelope(
            eligibility=ExecutionEligibility.DEFERRED,
            reason="Deferred",
            intent=IntentType.SUPPORT,
            proposal_status=ProposalStatus.VALID,
        )

        result = self.gate.select(
            intent_envelope, execution, "volatile", OverallPolicy.MULTI_CONTEXT
        )

        # Rule 3 should fire (MULTI_CONTEXT)
        assert result.regime == OperationalRegime.REFLECT

    def test_coherence_takes_priority_over_support(self):
        """Test: Rule 4 (volatile coherence) takes priority over Rule 5 (SUPPORT intent)."""
        intent_envelope = IntentEnvelope(
            intent_type=IntentType.SUPPORT,
            response_posture=ResponsePosture.ENGAGE_CAREFUL,
            planning_allowed=True,
            phase_minus_one_policy=OverallPolicy.SINGLE_CONTEXT,
        )
        execution = ExecutionEligibilityEnvelope(
            eligibility=ExecutionEligibility.DEFERRED,
            reason="Deferred",
            intent=IntentType.SUPPORT,
            proposal_status=ProposalStatus.VALID,
        )

        result = self.gate.select(
            intent_envelope, execution, "volatile", OverallPolicy.SINGLE_CONTEXT
        )

        # Rule 4 should fire (volatile coherence)
        assert result.regime == OperationalRegime.STABILIZE

    def test_support_takes_priority_over_inform(self):
        """Test: Rule 5 (SUPPORT) would only apply for SUPPORT intent, not INFORM."""
        # This test verifies that SUPPORT and INFORM have distinct handling
        intent_envelope = IntentEnvelope(
            intent_type=IntentType.SUPPORT,
            response_posture=ResponsePosture.ENGAGE_CAREFUL,
            planning_allowed=True,
            phase_minus_one_policy=OverallPolicy.SINGLE_CONTEXT,
        )
        execution = ExecutionEligibilityEnvelope(
            eligibility=ExecutionEligibility.DEFERRED,
            reason="Deferred",
            intent=IntentType.SUPPORT,
            proposal_status=ProposalStatus.VALID,
        )

        result = self.gate.select(
            intent_envelope, execution, "stable", OverallPolicy.SINGLE_CONTEXT
        )

        # Rule 5 should fire (SUPPORT intent)
        assert result.regime == OperationalRegime.DE_ESCALATE


class TestArchitecturalPhase:
    """Tests verifying architectural phase identification."""

    def test_envelope_has_p6_phase(self):
        """Test: envelope correctly identifies as P6."""
        envelope = RegimeEnvelope(
            regime=OperationalRegime.HOLD,
            reason="Test reason",
            intent=IntentType.INFORM,
            execution_eligibility=ExecutionEligibility.PROHIBITED,
            coherence_regime="stable",
        )

        assert envelope.architectural_phase == "P6"
        assert envelope.to_dict()["architectural_phase"] == "P6"


class TestAuthorityModel:
    """Tests verifying P6 respects the authority model."""

    def setup_method(self):
        """Set up test fixtures."""
        self.gate = P6RegimeGate()

    def test_cannot_override_prohibited_upstream(self):
        """Test: P6 cannot override PROHIBITED from PO5."""
        # When PO5 is PROHIBITED, P6 MUST return HOLD
        intent_envelope = IntentEnvelope(
            intent_type=IntentType.INFORM,
            response_posture=ResponsePosture.ENGAGE_OPEN,
            planning_allowed=True,
            phase_minus_one_policy=OverallPolicy.SINGLE_CONTEXT,
        )
        execution = ExecutionEligibilityEnvelope(
            eligibility=ExecutionEligibility.PROHIBITED,
            reason="Prohibited by upstream",
            intent=IntentType.INFORM,
            proposal_status=ProposalStatus.BLOCKED,
        )

        result = self.gate.select(
            intent_envelope, execution, "stable", OverallPolicy.SINGLE_CONTEXT
        )

        # When upstream is PROHIBITED, P6 MUST return HOLD
        assert result.regime == OperationalRegime.HOLD

    def test_cannot_expand_capability(self):
        """Test: P6 may only restrict, never expand capability."""
        # This test verifies that HOLD is always safe and conservative
        # Even in favorable conditions, P6 doesn't expand capability

        intent_envelope = IntentEnvelope(
            intent_type=IntentType.ABSTAIN,
            response_posture=ResponsePosture.ENGAGE_OPEN,
            planning_allowed=True,
            phase_minus_one_policy=OverallPolicy.SINGLE_CONTEXT,
        )
        execution = ExecutionEligibilityEnvelope(
            eligibility=ExecutionEligibility.ELIGIBLE,
            reason="Eligible (informational only)",
            intent=IntentType.ABSTAIN,
            proposal_status=ProposalStatus.VALID,
        )

        result = self.gate.select(
            intent_envelope, execution, "stable", OverallPolicy.SINGLE_CONTEXT
        )

        # ABSTAIN with no specific regime should fall back to HOLD
        # P6 defaults to conservative HOLD rather than expanding capability
        assert result.regime == OperationalRegime.HOLD


class TestP6Integration:
    """Tests for P6 integration module."""

    def test_get_gate_singleton(self):
        """Test: gate is a singleton."""
        gate1 = get_p6_gate()
        gate2 = get_p6_gate()

        assert gate1 is gate2

    def test_run_p6_directly(self):
        """Test: run_p6_directly works."""
        intent_envelope = IntentEnvelope(
            intent_type=IntentType.INFORM,
            response_posture=ResponsePosture.ENGAGE_OPEN,
            planning_allowed=True,
            phase_minus_one_policy=OverallPolicy.SINGLE_CONTEXT,
        )
        execution = ExecutionEligibilityEnvelope(
            eligibility=ExecutionEligibility.DEFERRED,
            reason="Test eligibility",
            intent=IntentType.INFORM,
            proposal_status=ProposalStatus.VALID,
        )

        result = run_p6_directly(
            intent_envelope, execution, "stable", OverallPolicy.SINGLE_CONTEXT
        )

        assert result is not None
        assert isinstance(result, RegimeEnvelope)
        # INFORM intent → INFORM regime
        assert result.regime == OperationalRegime.INFORM

    def test_maybe_run_p6_with_context(self):
        """Test: maybe_run_p6 works with mock context."""
        class MockCoherenceState:
            current_regime_band = "stable"

        class MockContext:
            def __init__(self):
                self.phase_minus_one = PhaseMinusOneEnvelope(
                    overall_policy=OverallPolicy.SINGLE_CONTEXT,
                    clauses=[
                        ClauseGroundingResult(clause_text="test")
                    ],
                )
                self.phase_zero = IntentEnvelope(
                    intent_type=IntentType.SUPPORT,
                    response_posture=ResponsePosture.ENGAGE_CAREFUL,
                    planning_allowed=True,
                    phase_minus_one_policy=OverallPolicy.SINGLE_CONTEXT,
                )
                self.po5_execution_eligibility = ExecutionEligibilityEnvelope(
                    eligibility=ExecutionEligibility.DEFERRED,
                    reason="Deferred",
                    intent=IntentType.SUPPORT,
                    proposal_status=ProposalStatus.VALID,
                )
                self.coherence_state = MockCoherenceState()
                self.p6_regime = None

        ctx = MockContext()
        maybe_run_p6(ctx)

        assert ctx.p6_regime is not None
        assert isinstance(ctx.p6_regime, RegimeEnvelope)
        # SUPPORT intent → DE_ESCALATE
        assert ctx.p6_regime.regime == OperationalRegime.DE_ESCALATE

    def test_maybe_run_p6_without_phase_zero(self):
        """Test: maybe_run_p6 does nothing without Phase 0."""
        class MockContext:
            phase_zero = None
            phase_minus_one = None
            po5_execution_eligibility = None
            p6_regime = None

        ctx = MockContext()
        maybe_run_p6(ctx)

        assert ctx.p6_regime is None

    def test_maybe_run_p6_without_po5(self):
        """Test: maybe_run_p6 does nothing without PO5."""
        class MockContext:
            def __init__(self):
                self.phase_zero = IntentEnvelope(
                    intent_type=IntentType.INFORM,
                    response_posture=ResponsePosture.ENGAGE_OPEN,
                    planning_allowed=True,
                    phase_minus_one_policy=OverallPolicy.SINGLE_CONTEXT,
                )
                self.phase_minus_one = None
                self.po5_execution_eligibility = None
                self.p6_regime = None

        ctx = MockContext()
        maybe_run_p6(ctx)

        assert ctx.p6_regime is None

    def test_maybe_run_p6_without_phase_minus_one(self):
        """Test: maybe_run_p6 does nothing without Phase -1."""
        class MockContext:
            def __init__(self):
                self.phase_zero = IntentEnvelope(
                    intent_type=IntentType.INFORM,
                    response_posture=ResponsePosture.ENGAGE_OPEN,
                    planning_allowed=True,
                    phase_minus_one_policy=OverallPolicy.SINGLE_CONTEXT,
                )
                self.po5_execution_eligibility = ExecutionEligibilityEnvelope(
                    eligibility=ExecutionEligibility.DEFERRED,
                    reason="Test",
                    intent=IntentType.INFORM,
                    proposal_status=ProposalStatus.VALID,
                )
                self.phase_minus_one = None
                self.p6_regime = None

        ctx = MockContext()
        maybe_run_p6(ctx)

        assert ctx.p6_regime is None

    def test_maybe_run_p6_with_volatile_coherence(self):
        """Test: maybe_run_p6 detects volatile coherence from Phase-41."""
        class MockCoherenceState:
            current_regime_band = "volatile"

        class MockContext:
            def __init__(self):
                self.phase_minus_one = PhaseMinusOneEnvelope(
                    overall_policy=OverallPolicy.SINGLE_CONTEXT,
                    clauses=[
                        ClauseGroundingResult(clause_text="test")
                    ],
                )
                self.phase_zero = IntentEnvelope(
                    intent_type=IntentType.SUPPORT,
                    response_posture=ResponsePosture.ENGAGE_CAREFUL,
                    planning_allowed=True,
                    phase_minus_one_policy=OverallPolicy.SINGLE_CONTEXT,
                )
                self.po5_execution_eligibility = ExecutionEligibilityEnvelope(
                    eligibility=ExecutionEligibility.DEFERRED,
                    reason="Deferred",
                    intent=IntentType.SUPPORT,
                    proposal_status=ProposalStatus.VALID,
                )
                self.coherence_state = MockCoherenceState()
                self.p6_regime = None

        ctx = MockContext()
        maybe_run_p6(ctx)

        assert ctx.p6_regime is not None
        # Volatile coherence → STABILIZE (takes priority over SUPPORT → DE_ESCALATE)
        assert ctx.p6_regime.regime == OperationalRegime.STABILIZE

    def test_maybe_run_p6_without_coherence_state(self):
        """Test: maybe_run_p6 works without coherence state (uses 'unknown')."""
        class MockContext:
            def __init__(self):
                self.phase_minus_one = PhaseMinusOneEnvelope(
                    overall_policy=OverallPolicy.SINGLE_CONTEXT,
                    clauses=[
                        ClauseGroundingResult(clause_text="test")
                    ],
                )
                self.phase_zero = IntentEnvelope(
                    intent_type=IntentType.INFORM,
                    response_posture=ResponsePosture.ENGAGE_OPEN,
                    planning_allowed=True,
                    phase_minus_one_policy=OverallPolicy.SINGLE_CONTEXT,
                )
                self.po5_execution_eligibility = ExecutionEligibilityEnvelope(
                    eligibility=ExecutionEligibility.DEFERRED,
                    reason="Deferred",
                    intent=IntentType.INFORM,
                    proposal_status=ProposalStatus.VALID,
                )
                self.coherence_state = None  # No coherence state
                self.p6_regime = None

        ctx = MockContext()
        maybe_run_p6(ctx)

        assert ctx.p6_regime is not None
        assert ctx.p6_regime.coherence_regime == "unknown"

    def test_get_p6_regime(self):
        """Test: get_p6_regime retrieves from context."""
        class MockContext:
            def __init__(self, regime):
                self.p6_regime = regime

        envelope = RegimeEnvelope(
            regime=OperationalRegime.HOLD,
            reason="Test reason",
            intent=IntentType.INFORM,
            execution_eligibility=ExecutionEligibility.PROHIBITED,
            coherence_regime="stable",
        )
        ctx = MockContext(envelope)

        result = get_p6_regime(ctx)

        assert result is envelope

    def test_is_regime_hold(self):
        """Test: is_regime_hold returns correct value."""
        class MockContext:
            def __init__(self, regime):
                self.p6_regime = regime

        hold_envelope = RegimeEnvelope(
            regime=OperationalRegime.HOLD,
            reason="Test reason",
            intent=IntentType.INFORM,
            execution_eligibility=ExecutionEligibility.PROHIBITED,
            coherence_regime="stable",
        )
        ctx = MockContext(hold_envelope)

        assert is_regime_hold(ctx) is True

    def test_is_regime_hold_no_p6(self):
        """Test: is_regime_hold returns True when P6 hasn't run (conservative)."""
        class MockContext:
            p6_regime = None

        ctx = MockContext()

        # Conservative default: HOLD if P6 hasn't run
        assert is_regime_hold(ctx) is True

    def test_is_regime_stabilize(self):
        """Test: is_regime_stabilize returns correct value."""
        class MockContext:
            def __init__(self, regime):
                self.p6_regime = regime

        stabilize_envelope = RegimeEnvelope(
            regime=OperationalRegime.STABILIZE,
            reason="Test reason",
            intent=IntentType.SUPPORT,
            execution_eligibility=ExecutionEligibility.DEFERRED,
            coherence_regime="volatile",
        )
        ctx = MockContext(stabilize_envelope)

        assert is_regime_stabilize(ctx) is True

    def test_is_regime_reflect(self):
        """Test: is_regime_reflect returns correct value."""
        class MockContext:
            def __init__(self, regime):
                self.p6_regime = regime

        reflect_envelope = RegimeEnvelope(
            regime=OperationalRegime.REFLECT,
            reason="Test reason",
            intent=IntentType.REFLECT,
            execution_eligibility=ExecutionEligibility.DEFERRED,
            coherence_regime="mixed",
        )
        ctx = MockContext(reflect_envelope)

        assert is_regime_reflect(ctx) is True

    def test_is_regime_inform(self):
        """Test: is_regime_inform returns correct value."""
        class MockContext:
            def __init__(self, regime):
                self.p6_regime = regime

        inform_envelope = RegimeEnvelope(
            regime=OperationalRegime.INFORM,
            reason="Test reason",
            intent=IntentType.INFORM,
            execution_eligibility=ExecutionEligibility.ELIGIBLE,
            coherence_regime="stable",
        )
        ctx = MockContext(inform_envelope)

        assert is_regime_inform(ctx) is True

    def test_is_regime_clarify(self):
        """Test: is_regime_clarify returns correct value."""
        class MockContext:
            def __init__(self, regime):
                self.p6_regime = regime

        clarify_envelope = RegimeEnvelope(
            regime=OperationalRegime.CLARIFY,
            reason="Test reason",
            intent=IntentType.CLARIFY,
            execution_eligibility=ExecutionEligibility.PROHIBITED,
            coherence_regime="stable",
        )
        ctx = MockContext(clarify_envelope)

        assert is_regime_clarify(ctx) is True

    def test_is_regime_de_escalate(self):
        """Test: is_regime_de_escalate returns correct value."""
        class MockContext:
            def __init__(self, regime):
                self.p6_regime = regime

        de_escalate_envelope = RegimeEnvelope(
            regime=OperationalRegime.DE_ESCALATE,
            reason="Test reason",
            intent=IntentType.SUPPORT,
            execution_eligibility=ExecutionEligibility.DEFERRED,
            coherence_regime="stable",
        )
        ctx = MockContext(de_escalate_envelope)

        assert is_regime_de_escalate(ctx) is True

    def test_get_regime_reason(self):
        """Test: get_regime_reason returns reason string."""
        class MockContext:
            def __init__(self, regime):
                self.p6_regime = regime

        envelope = RegimeEnvelope(
            regime=OperationalRegime.HOLD,
            reason="Test regime reason",
            intent=IntentType.INFORM,
            execution_eligibility=ExecutionEligibility.PROHIBITED,
            coherence_regime="stable",
        )
        ctx = MockContext(envelope)

        result = get_regime_reason(ctx)

        assert result == "Test regime reason"

    def test_get_selected_regime(self):
        """Test: get_selected_regime returns the regime enum."""
        class MockContext:
            def __init__(self, regime):
                self.p6_regime = regime

        envelope = RegimeEnvelope(
            regime=OperationalRegime.INFORM,
            reason="Test reason",
            intent=IntentType.INFORM,
            execution_eligibility=ExecutionEligibility.ELIGIBLE,
            coherence_regime="stable",
        )
        ctx = MockContext(envelope)

        result = get_selected_regime(ctx)

        assert result == OperationalRegime.INFORM


class TestNoSemanticsOrExecution:
    """Tests verifying P6 does NOT perform semantics, planning, or execution."""

    def setup_method(self):
        """Set up test fixtures."""
        self.gate = P6RegimeGate()
        self.operation_log: list[str] = []

    def test_select_does_not_execute(self):
        """Test: P6 select() does not execute any actions."""
        intent_envelope = IntentEnvelope(
            intent_type=IntentType.INFORM,
            response_posture=ResponsePosture.ENGAGE_OPEN,
            planning_allowed=True,
            phase_minus_one_policy=OverallPolicy.SINGLE_CONTEXT,
        )
        execution = ExecutionEligibilityEnvelope(
            eligibility=ExecutionEligibility.ELIGIBLE,
            reason="Eligible (informational)",
            intent=IntentType.INFORM,
            proposal_status=ProposalStatus.VALID,
        )

        # Track any operation attempts
        original_select = self.gate.select

        def tracking_select(*args, **kwargs):
            result = original_select(*args, **kwargs)
            # If any action was "executed", we'd log it here
            # P6 should never do anything besides select regime
            self.operation_log.append("select_completed")
            return result

        self.gate.select = tracking_select

        # Call select
        result = self.gate.select(
            intent_envelope, execution, "stable", OverallPolicy.SINGLE_CONTEXT
        )

        # Verify only tracking, no execution
        assert len(self.operation_log) == 1
        assert self.operation_log[0] == "select_completed"

        # Verify envelope is just a wrapper
        assert isinstance(result, RegimeEnvelope)
        assert result.architectural_phase == "P6"

    def test_envelope_is_pure_data(self):
        """Test: envelope contains no callable methods that execute."""
        envelope = RegimeEnvelope(
            regime=OperationalRegime.INFORM,
            reason="Test informational regime",
            intent=IntentType.INFORM,
            execution_eligibility=ExecutionEligibility.ELIGIBLE,
            coherence_regime="stable",
        )

        # Check that methods are read-only inspectors
        assert callable(envelope.is_hold)
        assert callable(envelope.is_stabilize)
        assert callable(envelope.is_reflect)
        assert callable(envelope.is_inform)
        assert callable(envelope.is_clarify)
        assert callable(envelope.is_de_escalate)
        assert callable(envelope.to_dict)

        # These should be query methods, not execution
        result1 = envelope.is_hold()
        result2 = envelope.is_inform()
        result3 = envelope.to_dict()

        assert isinstance(result1, bool)
        assert isinstance(result2, bool)
        assert isinstance(result3, dict)

    def test_no_forbidden_methods(self):
        """Test: envelope has no execution methods."""
        envelope = RegimeEnvelope(
            regime=OperationalRegime.INFORM,
            reason="Test regime",
            intent=IntentType.INFORM,
            execution_eligibility=ExecutionEligibility.ELIGIBLE,
            coherence_regime="stable",
        )

        # Verify the envelope has no execution methods
        method_names = [m for m in dir(envelope) if not m.startswith('_')]
        forbidden_names = ['execute', 'run', 'trigger', 'invoke', 'call', 'perform', 'plan', 'schedule']

        for forbidden in forbidden_names:
            assert forbidden not in method_names, (
                f"CRITICAL: Found forbidden method '{forbidden}' in envelope"
            )


# Run tests if executed directly
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
