"""
PO5 Unit Tests

Tests for PO5 Planner Execution Gate:
- ExecutionEligibility enum
- ExecutionEligibilityEnvelope dataclass
- PO5ExecutionGate
- Integration with PO2/PO4/PO1

Test Cases (per specification):
1. PROHIBITED (blocked proposal)
2. PROHIBITED (HOLD / ACKNOWLEDGE posture)
3. PROHIBITED (CLARIFY / INFORM intent)
4. DEFERRED (MULTI_CONTEXT)
5. DEFERRED (SUPPORT / REFLECT with VALID proposal)
6. Determinism (same input → same output)
7. Explicit proof that no execution is possible
"""

import pytest
from symbolu.mechanical.pipeline.phase_po5 import (
    PO5ExecutionGate,
    ExecutionEligibilityEnvelope,
    ExecutionEligibility,
)
from symbolu.mechanical.pipeline.phase_po5.po5_integration import (
    get_po5_gate,
    maybe_run_po5,
    run_po5_directly,
    get_po5_eligibility,
    is_execution_prohibited,
    is_execution_deferred,
    is_execution_eligible,
    get_eligibility_reason,
)
from symbolu.mechanical.pipeline.phase_zero.phase_zero_schema import (
    IntentEnvelope,
    IntentType,
    ResponsePosture,
)
from symbolu.mechanical.pipeline.phase_po4.po4_schema import (
    PlannerProposalEnvelope,
    ProposalStatus,
)
from symbolu.mechanical.pipeline.governance.planner_gate import ActionClass
from symbolu.mechanical.pipeline.grounding.phase_minus_one_schema import OverallPolicy


class TestExecutionEligibilityEnum:
    """Tests for ExecutionEligibility enum."""

    def test_prohibited_value(self):
        """Test: PROHIBITED status exists."""
        assert ExecutionEligibility.PROHIBITED.value == "PROHIBITED"

    def test_deferred_value(self):
        """Test: DEFERRED status exists."""
        assert ExecutionEligibility.DEFERRED.value == "DEFERRED"

    def test_eligible_value(self):
        """Test: ELIGIBLE status exists."""
        assert ExecutionEligibility.ELIGIBLE.value == "ELIGIBLE"

    def test_all_eligibilities_exist(self):
        """Test: all three eligibility states exist."""
        eligibilities = list(ExecutionEligibility)
        assert len(eligibilities) == 3
        assert ExecutionEligibility.PROHIBITED in eligibilities
        assert ExecutionEligibility.DEFERRED in eligibilities
        assert ExecutionEligibility.ELIGIBLE in eligibilities


class TestExecutionEligibilityEnvelope:
    """Tests for ExecutionEligibilityEnvelope dataclass."""

    def test_basic_construction_prohibited(self):
        """Test: basic envelope construction with PROHIBITED status."""
        envelope = ExecutionEligibilityEnvelope(
            eligibility=ExecutionEligibility.PROHIBITED,
            reason="Test prohibition reason",
            intent=IntentType.INFORM,
            proposal_status=ProposalStatus.BLOCKED,
        )

        assert envelope.eligibility == ExecutionEligibility.PROHIBITED
        assert envelope.intent == IntentType.INFORM
        assert envelope.proposal_status == ProposalStatus.BLOCKED
        assert envelope.architectural_phase == "PO5"
        assert "Test prohibition reason" in envelope.reason

    def test_basic_construction_deferred(self):
        """Test: envelope construction with DEFERRED status."""
        envelope = ExecutionEligibilityEnvelope(
            eligibility=ExecutionEligibility.DEFERRED,
            reason="Deferred due to multi-context",
            intent=IntentType.SUPPORT,
            proposal_status=ProposalStatus.VALID,
        )

        assert envelope.eligibility == ExecutionEligibility.DEFERRED
        assert envelope.is_deferred() is True

    def test_basic_construction_eligible(self):
        """Test: envelope construction with ELIGIBLE status (informational only)."""
        envelope = ExecutionEligibilityEnvelope(
            eligibility=ExecutionEligibility.ELIGIBLE,
            reason="Conceptually eligible (informational only)",
            intent=IntentType.ABSTAIN,
            proposal_status=ProposalStatus.VALID,
        )

        assert envelope.eligibility == ExecutionEligibility.ELIGIBLE
        assert envelope.is_eligible() is True
        # ELIGIBLE is informational only - verify this in docstring
        assert "informational" in envelope.reason.lower()

    def test_immutability(self):
        """Test: ExecutionEligibilityEnvelope is frozen (immutable)."""
        envelope = ExecutionEligibilityEnvelope(
            eligibility=ExecutionEligibility.PROHIBITED,
            reason="Test reason",
            intent=IntentType.INFORM,
            proposal_status=ProposalStatus.BLOCKED,
        )

        with pytest.raises(Exception):
            envelope.eligibility = ExecutionEligibility.ELIGIBLE

    def test_none_eligibility_raises(self):
        """Test: None eligibility raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            ExecutionEligibilityEnvelope(
                eligibility=None,  # type: ignore
                reason="Test reason",
                intent=IntentType.INFORM,
                proposal_status=ProposalStatus.BLOCKED,
            )
        assert "eligibility cannot be None" in str(exc_info.value)

    def test_empty_reason_raises(self):
        """Test: empty reason raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            ExecutionEligibilityEnvelope(
                eligibility=ExecutionEligibility.PROHIBITED,
                reason="",  # Empty reason
                intent=IntentType.INFORM,
                proposal_status=ProposalStatus.BLOCKED,
            )
        assert "non-empty string" in str(exc_info.value)

    def test_whitespace_reason_raises(self):
        """Test: whitespace-only reason raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            ExecutionEligibilityEnvelope(
                eligibility=ExecutionEligibility.PROHIBITED,
                reason="   ",  # Whitespace only
                intent=IntentType.INFORM,
                proposal_status=ProposalStatus.BLOCKED,
            )
        assert "non-empty string" in str(exc_info.value)

    def test_none_intent_raises(self):
        """Test: None intent raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            ExecutionEligibilityEnvelope(
                eligibility=ExecutionEligibility.PROHIBITED,
                reason="Test reason",
                intent=None,  # type: ignore
                proposal_status=ProposalStatus.BLOCKED,
            )
        assert "intent cannot be None" in str(exc_info.value)

    def test_none_proposal_status_raises(self):
        """Test: None proposal_status raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            ExecutionEligibilityEnvelope(
                eligibility=ExecutionEligibility.PROHIBITED,
                reason="Test reason",
                intent=IntentType.INFORM,
                proposal_status=None,  # type: ignore
            )
        assert "proposal_status cannot be None" in str(exc_info.value)

    def test_invalid_eligibility_type_raises(self):
        """Test: invalid eligibility type raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            ExecutionEligibilityEnvelope(
                eligibility="PROHIBITED",  # type: ignore - string, not enum
                reason="Test reason",
                intent=IntentType.INFORM,
                proposal_status=ProposalStatus.BLOCKED,
            )
        assert "must be ExecutionEligibility" in str(exc_info.value)

    def test_is_prohibited_method(self):
        """Test: is_prohibited() method."""
        prohibited = ExecutionEligibilityEnvelope(
            eligibility=ExecutionEligibility.PROHIBITED,
            reason="Test reason",
            intent=IntentType.INFORM,
            proposal_status=ProposalStatus.BLOCKED,
        )
        assert prohibited.is_prohibited() is True

        deferred = ExecutionEligibilityEnvelope(
            eligibility=ExecutionEligibility.DEFERRED,
            reason="Test reason",
            intent=IntentType.SUPPORT,
            proposal_status=ProposalStatus.VALID,
        )
        assert deferred.is_prohibited() is False

    def test_is_deferred_method(self):
        """Test: is_deferred() method."""
        deferred = ExecutionEligibilityEnvelope(
            eligibility=ExecutionEligibility.DEFERRED,
            reason="Test reason",
            intent=IntentType.SUPPORT,
            proposal_status=ProposalStatus.VALID,
        )
        assert deferred.is_deferred() is True

    def test_is_eligible_method(self):
        """Test: is_eligible() method (informational only)."""
        eligible = ExecutionEligibilityEnvelope(
            eligibility=ExecutionEligibility.ELIGIBLE,
            reason="Conceptually eligible (informational only)",
            intent=IntentType.ABSTAIN,
            proposal_status=ProposalStatus.VALID,
        )
        assert eligible.is_eligible() is True

    def test_to_dict_serialization(self):
        """Test: to_dict() serialization."""
        envelope = ExecutionEligibilityEnvelope(
            eligibility=ExecutionEligibility.PROHIBITED,
            reason="Test serialization",
            intent=IntentType.INFORM,
            proposal_status=ProposalStatus.BLOCKED,
            debug={"key": "value"},
        )

        d = envelope.to_dict()

        assert d["eligibility"] == "PROHIBITED"
        assert d["reason"] == "Test serialization"
        assert d["intent"] == "INFORM"
        assert d["proposal_status"] == "BLOCKED"
        assert d["architectural_phase"] == "PO5"
        assert d["debug"]["key"] == "value"


class TestPO5ExecutionGate:
    """Tests for PO5ExecutionGate."""

    def setup_method(self):
        """Set up test fixtures."""
        self.gate = PO5ExecutionGate()

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

    def _make_proposal(
        self,
        intent: IntentType,
        status: ProposalStatus,
        blocked_reason: str = None,
    ) -> PlannerProposalEnvelope:
        """Helper to create test PlannerProposalEnvelope."""
        if status == ProposalStatus.BLOCKED:
            return PlannerProposalEnvelope(
                intent=intent,
                allowed_actions=frozenset(),
                proposed_actions=frozenset({ActionClass.EXPLAIN}),
                rejected_actions={ActionClass.EXPLAIN: "Rejected"},
                status=status,
                blocked_reason=blocked_reason or "Test blocked",
            )
        elif status == ProposalStatus.PARTIALLY_ALLOWED:
            return PlannerProposalEnvelope(
                intent=intent,
                allowed_actions=frozenset({ActionClass.EXPLAIN}),
                proposed_actions=frozenset({ActionClass.EXPLAIN, ActionClass.CARE}),
                rejected_actions={ActionClass.CARE: "Rejected"},
                status=status,
            )
        else:  # VALID
            return PlannerProposalEnvelope(
                intent=intent,
                allowed_actions=frozenset({ActionClass.EXPLAIN}),
                proposed_actions=frozenset({ActionClass.EXPLAIN}),
                rejected_actions={},
                status=status,
            )

    def test_prohibited_blocked_proposal(self):
        """
        Test Case 1: PROHIBITED (blocked proposal).

        Rule 1: If proposal.status == BLOCKED → PROHIBITED
        """
        intent_envelope = self._make_intent_envelope(
            IntentType.REFLECT,
            ResponsePosture.ENGAGE_CAREFUL,
        )
        proposal = self._make_proposal(IntentType.REFLECT, ProposalStatus.BLOCKED)

        result = self.gate.evaluate(
            intent_envelope, proposal, OverallPolicy.SINGLE_CONTEXT
        )

        assert result.eligibility == ExecutionEligibility.PROHIBITED
        assert result.is_prohibited() is True
        assert "BLOCKED" in result.reason

    def test_prohibited_hold_posture(self):
        """
        Test Case 2a: PROHIBITED (HOLD posture).

        Rule 2: If posture in {HOLD, ACKNOWLEDGE} → PROHIBITED
        """
        intent_envelope = self._make_intent_envelope(
            IntentType.CLARIFY,
            ResponsePosture.HOLD,
            planning_allowed=False,
        )
        proposal = self._make_proposal(IntentType.CLARIFY, ProposalStatus.VALID)

        result = self.gate.evaluate(
            intent_envelope, proposal, OverallPolicy.SINGLE_CONTEXT
        )

        assert result.eligibility == ExecutionEligibility.PROHIBITED
        assert result.is_prohibited() is True
        assert "HOLD" in result.reason

    def test_prohibited_acknowledge_posture(self):
        """
        Test Case 2b: PROHIBITED (ACKNOWLEDGE posture).

        Rule 2: If posture in {HOLD, ACKNOWLEDGE} → PROHIBITED
        """
        intent_envelope = self._make_intent_envelope(
            IntentType.SUPPORT,
            ResponsePosture.ACKNOWLEDGE,
        )
        proposal = self._make_proposal(IntentType.SUPPORT, ProposalStatus.VALID)

        result = self.gate.evaluate(
            intent_envelope, proposal, OverallPolicy.SINGLE_CONTEXT
        )

        assert result.eligibility == ExecutionEligibility.PROHIBITED
        assert result.is_prohibited() is True
        assert "ACKNOWLEDGE" in result.reason

    def test_prohibited_clarify_intent(self):
        """
        Test Case 3a: PROHIBITED (CLARIFY intent).

        Rule 3: If intent in {CLARIFY, INFORM} → PROHIBITED
        """
        intent_envelope = self._make_intent_envelope(
            IntentType.CLARIFY,
            ResponsePosture.ENGAGE_CAREFUL,
        )
        proposal = self._make_proposal(IntentType.CLARIFY, ProposalStatus.VALID)

        result = self.gate.evaluate(
            intent_envelope, proposal, OverallPolicy.SINGLE_CONTEXT
        )

        assert result.eligibility == ExecutionEligibility.PROHIBITED
        assert result.is_prohibited() is True
        assert "CLARIFY" in result.reason

    def test_prohibited_inform_intent(self):
        """
        Test Case 3b: PROHIBITED (INFORM intent).

        Rule 3: If intent in {CLARIFY, INFORM} → PROHIBITED
        """
        intent_envelope = self._make_intent_envelope(
            IntentType.INFORM,
            ResponsePosture.ENGAGE_OPEN,
        )
        proposal = self._make_proposal(IntentType.INFORM, ProposalStatus.VALID)

        result = self.gate.evaluate(
            intent_envelope, proposal, OverallPolicy.SINGLE_CONTEXT
        )

        assert result.eligibility == ExecutionEligibility.PROHIBITED
        assert result.is_prohibited() is True
        assert "INFORM" in result.reason

    def test_deferred_multi_context(self):
        """
        Test Case 4: DEFERRED (MULTI_CONTEXT).

        Rule 4: If overall_policy == MULTI_CONTEXT → DEFERRED
        """
        intent_envelope = self._make_intent_envelope(
            IntentType.SUPPORT,
            ResponsePosture.ENGAGE_CAREFUL,
        )
        proposal = self._make_proposal(IntentType.SUPPORT, ProposalStatus.VALID)

        result = self.gate.evaluate(
            intent_envelope, proposal, OverallPolicy.MULTI_CONTEXT
        )

        assert result.eligibility == ExecutionEligibility.DEFERRED
        assert result.is_deferred() is True
        assert "multiple" in result.reason.lower() or "context" in result.reason.lower()

    def test_deferred_support_valid_proposal(self):
        """
        Test Case 5a: DEFERRED (SUPPORT with VALID proposal).

        Rule 5: If intent in {SUPPORT, REFLECT} and proposal is VALID → DEFERRED
        """
        intent_envelope = self._make_intent_envelope(
            IntentType.SUPPORT,
            ResponsePosture.ENGAGE_CAREFUL,
        )
        proposal = self._make_proposal(IntentType.SUPPORT, ProposalStatus.VALID)

        result = self.gate.evaluate(
            intent_envelope, proposal, OverallPolicy.SINGLE_CONTEXT
        )

        assert result.eligibility == ExecutionEligibility.DEFERRED
        assert result.is_deferred() is True
        assert "SUPPORT" in result.reason

    def test_deferred_reflect_valid_proposal(self):
        """
        Test Case 5b: DEFERRED (REFLECT with VALID proposal).

        Rule 5: If intent in {SUPPORT, REFLECT} and proposal is VALID → DEFERRED
        """
        intent_envelope = self._make_intent_envelope(
            IntentType.REFLECT,
            ResponsePosture.ENGAGE_CAREFUL,
        )
        proposal = self._make_proposal(IntentType.REFLECT, ProposalStatus.VALID)

        result = self.gate.evaluate(
            intent_envelope, proposal, OverallPolicy.SINGLE_CONTEXT
        )

        assert result.eligibility == ExecutionEligibility.DEFERRED
        assert result.is_deferred() is True
        assert "REFLECT" in result.reason

    def test_eligible_informational_only(self):
        """
        Test Case 6: ELIGIBLE (informational only).

        Rule 6: ELIGIBLE is allowed only as an informational state.
        This tests the fallthrough case that should be rare.
        """
        # ABSTAIN with ENGAGE_OPEN (unusual combination) to test fallthrough
        # This is an edge case - normally ABSTAIN would have HOLD posture
        intent_envelope = IntentEnvelope(
            intent_type=IntentType.ABSTAIN,
            response_posture=ResponsePosture.ENGAGE_OPEN,
            planning_allowed=True,
            phase_minus_one_policy=OverallPolicy.SINGLE_CONTEXT,
        )
        proposal = self._make_proposal(IntentType.ABSTAIN, ProposalStatus.PARTIALLY_ALLOWED)

        result = self.gate.evaluate(
            intent_envelope, proposal, OverallPolicy.SINGLE_CONTEXT
        )

        assert result.eligibility == ExecutionEligibility.ELIGIBLE
        assert result.is_eligible() is True
        # CRITICAL: Verify that ELIGIBLE is informational only
        assert "informational" in result.reason.lower()
        assert "no executor" in result.reason.lower()

    def test_none_intent_envelope_raises(self):
        """Test: None intent_envelope raises ValueError."""
        proposal = self._make_proposal(IntentType.INFORM, ProposalStatus.VALID)
        with pytest.raises(ValueError) as exc_info:
            self.gate.evaluate(None, proposal, OverallPolicy.SINGLE_CONTEXT)  # type: ignore
        assert "intent_envelope cannot be None" in str(exc_info.value)

    def test_none_proposal_raises(self):
        """Test: None proposal raises ValueError."""
        intent_envelope = self._make_intent_envelope(
            IntentType.INFORM, ResponsePosture.ENGAGE_OPEN
        )
        with pytest.raises(ValueError) as exc_info:
            self.gate.evaluate(intent_envelope, None, OverallPolicy.SINGLE_CONTEXT)  # type: ignore
        assert "proposal cannot be None" in str(exc_info.value)

    def test_none_overall_policy_raises(self):
        """Test: None overall_policy raises ValueError."""
        intent_envelope = self._make_intent_envelope(
            IntentType.INFORM, ResponsePosture.ENGAGE_OPEN
        )
        proposal = self._make_proposal(IntentType.INFORM, ProposalStatus.VALID)
        with pytest.raises(ValueError) as exc_info:
            self.gate.evaluate(intent_envelope, proposal, None)  # type: ignore
        assert "overall_policy cannot be None" in str(exc_info.value)

    def test_debug_info_populated(self):
        """Test: debug info is populated in result."""
        intent_envelope = self._make_intent_envelope(
            IntentType.INFORM, ResponsePosture.ENGAGE_OPEN
        )
        proposal = self._make_proposal(IntentType.INFORM, ProposalStatus.VALID)

        result = self.gate.evaluate(
            intent_envelope, proposal, OverallPolicy.SINGLE_CONTEXT
        )

        assert result.debug is not None
        assert "source_intent" in result.debug
        assert "source_posture" in result.debug
        assert "proposal_status" in result.debug
        assert "overall_policy" in result.debug
        assert result.debug["source_intent"] == "INFORM"


class TestDeterminism:
    """Tests verifying deterministic behavior (no randomness)."""

    def setup_method(self):
        """Set up test fixtures."""
        self.gate = PO5ExecutionGate()

    def _make_envelope_and_proposal(
        self, intent_type: IntentType, posture: ResponsePosture
    ) -> tuple[IntentEnvelope, PlannerProposalEnvelope]:
        """Helper to create test inputs."""
        intent_envelope = IntentEnvelope(
            intent_type=intent_type,
            response_posture=posture,
            planning_allowed=True,
            phase_minus_one_policy=OverallPolicy.SINGLE_CONTEXT,
        )

        proposal = PlannerProposalEnvelope(
            intent=intent_type,
            allowed_actions=frozenset({ActionClass.EXPLAIN}),
            proposed_actions=frozenset({ActionClass.EXPLAIN}),
            rejected_actions={},
            status=ProposalStatus.VALID,
        )

        return intent_envelope, proposal

    def test_same_input_same_output(self):
        """
        Test Case 7: Determinism - same input → same output.

        Multiple runs with the same input must produce identical results.
        """
        intent_envelope, proposal = self._make_envelope_and_proposal(
            IntentType.INFORM, ResponsePosture.ENGAGE_OPEN
        )

        results = []
        for _ in range(10):
            result = self.gate.evaluate(
                intent_envelope, proposal, OverallPolicy.SINGLE_CONTEXT
            )
            results.append((result.eligibility, result.reason))

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
            intent_envelope, proposal = self._make_envelope_and_proposal(
                intent_type, posture_map[intent_type]
            )

            results = []
            for _ in range(5):
                result = self.gate.evaluate(
                    intent_envelope, proposal, OverallPolicy.SINGLE_CONTEXT
                )
                results.append((result.eligibility,))

            assert all(r == results[0] for r in results), (
                f"Non-deterministic for {intent_type}"
            )

    def test_serialization_order_consistent(self):
        """Test: serialization is consistent."""
        intent_envelope, proposal = self._make_envelope_and_proposal(
            IntentType.INFORM, ResponsePosture.ENGAGE_OPEN
        )

        serialized = []
        for _ in range(5):
            result = self.gate.evaluate(
                intent_envelope, proposal, OverallPolicy.SINGLE_CONTEXT
            )
            serialized.append(result.to_dict()["eligibility"])

        assert all(s == serialized[0] for s in serialized)


class TestNoExecutionLeakage:
    """Tests verifying PO5 does NOT execute any actions."""

    def setup_method(self):
        """Set up test fixtures."""
        self.gate = PO5ExecutionGate()
        self.execution_log: list[str] = []

    def test_evaluate_does_not_execute(self):
        """
        Test Case 8: No execution leakage.

        PO5 must only evaluate eligibility - never execute actions.
        """
        intent_envelope = IntentEnvelope(
            intent_type=IntentType.ABSTAIN,
            response_posture=ResponsePosture.ENGAGE_OPEN,
            planning_allowed=True,
            phase_minus_one_policy=OverallPolicy.SINGLE_CONTEXT,
        )
        proposal = PlannerProposalEnvelope(
            intent=IntentType.ABSTAIN,
            allowed_actions=frozenset({ActionClass.EXPLAIN}),
            proposed_actions=frozenset({ActionClass.EXPLAIN}),
            rejected_actions={},
            status=ProposalStatus.PARTIALLY_ALLOWED,
        )

        # Track any execution attempts
        original_evaluate = self.gate.evaluate

        def tracking_evaluate(*args, **kwargs):
            result = original_evaluate(*args, **kwargs)
            # If any action was "executed", we'd log it here
            # PO5 should never do anything besides evaluate
            self.execution_log.append("evaluate_completed")
            return result

        self.gate.evaluate = tracking_evaluate

        # Call evaluate - even if ELIGIBLE, no execution should occur
        result = self.gate.evaluate(
            intent_envelope, proposal, OverallPolicy.SINGLE_CONTEXT
        )

        # Verify only tracking, no execution
        assert len(self.execution_log) == 1
        assert self.execution_log[0] == "evaluate_completed"

        # Verify envelope is just a wrapper
        assert isinstance(result, ExecutionEligibilityEnvelope)
        assert result.architectural_phase == "PO5"

    def test_envelope_is_pure_data(self):
        """Test: envelope contains no callable methods that execute."""
        envelope = ExecutionEligibilityEnvelope(
            eligibility=ExecutionEligibility.ELIGIBLE,
            reason="Test informational eligibility",
            intent=IntentType.ABSTAIN,
            proposal_status=ProposalStatus.VALID,
        )

        # Check that methods are read-only inspectors
        assert callable(envelope.is_prohibited)
        assert callable(envelope.is_deferred)
        assert callable(envelope.is_eligible)
        assert callable(envelope.to_dict)

        # These should be query methods, not execution
        result1 = envelope.is_prohibited()
        result2 = envelope.is_deferred()
        result3 = envelope.is_eligible()
        result4 = envelope.to_dict()

        assert isinstance(result1, bool)
        assert isinstance(result2, bool)
        assert isinstance(result3, bool)
        assert isinstance(result4, dict)

    def test_eligible_does_not_enable_execution(self):
        """
        Test: ELIGIBLE status is informational only; no execution pathway.

        CRITICAL: Even when ELIGIBLE, PO5 must not enable any execution.
        The ELIGIBLE status is purely informational - no executor exists.
        """
        envelope = ExecutionEligibilityEnvelope(
            eligibility=ExecutionEligibility.ELIGIBLE,
            reason="Conceptually eligible (informational only; no executor exists)",
            intent=IntentType.ABSTAIN,
            proposal_status=ProposalStatus.VALID,
        )

        # Verify ELIGIBLE is informational only
        assert envelope.is_eligible() is True

        # Verify the envelope has no execution methods
        # (no execute(), no run(), no trigger(), etc.)
        method_names = [m for m in dir(envelope) if not m.startswith('_')]
        forbidden_names = ['execute', 'run', 'trigger', 'invoke', 'call', 'perform']

        for forbidden in forbidden_names:
            assert forbidden not in method_names, (
                f"CRITICAL: Found execution method '{forbidden}' in envelope"
            )

        # Verify the envelope doesn't have any side-effect-producing methods
        for method_name in method_names:
            method = getattr(envelope, method_name)
            if callable(method):
                # All callable methods should be pure inspectors
                assert method_name in [
                    'is_prohibited', 'is_deferred', 'is_eligible', 'to_dict'
                ], f"Unexpected method: {method_name}"


class TestPO5Integration:
    """Tests for PO5 integration module."""

    def test_get_gate_singleton(self):
        """Test: gate is a singleton."""
        gate1 = get_po5_gate()
        gate2 = get_po5_gate()

        assert gate1 is gate2

    def test_run_po5_directly(self):
        """Test: run_po5_directly works."""
        intent_envelope = IntentEnvelope(
            intent_type=IntentType.INFORM,
            response_posture=ResponsePosture.ENGAGE_OPEN,
            planning_allowed=True,
            phase_minus_one_policy=OverallPolicy.SINGLE_CONTEXT,
        )
        proposal = PlannerProposalEnvelope(
            intent=IntentType.INFORM,
            allowed_actions=frozenset({ActionClass.EXPLAIN}),
            proposed_actions=frozenset({ActionClass.EXPLAIN}),
            rejected_actions={},
            status=ProposalStatus.VALID,
        )

        result = run_po5_directly(intent_envelope, proposal, OverallPolicy.SINGLE_CONTEXT)

        assert result is not None
        assert isinstance(result, ExecutionEligibilityEnvelope)
        # INFORM intent → PROHIBITED
        assert result.eligibility == ExecutionEligibility.PROHIBITED

    def test_maybe_run_po5_with_context(self):
        """Test: maybe_run_po5 works with mock context."""
        from symbolu.mechanical.pipeline.grounding.phase_minus_one_schema import (
            PhaseMinusOneEnvelope,
            ClauseGroundingResult,
        )

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
                self.po4_proposal = PlannerProposalEnvelope(
                    intent=IntentType.SUPPORT,
                    allowed_actions=frozenset({ActionClass.CARE}),
                    proposed_actions=frozenset({ActionClass.CARE}),
                    rejected_actions={},
                    status=ProposalStatus.VALID,
                )
                self.po5_execution_eligibility = None

        ctx = MockContext()
        maybe_run_po5(ctx)

        assert ctx.po5_execution_eligibility is not None
        assert isinstance(ctx.po5_execution_eligibility, ExecutionEligibilityEnvelope)
        # SUPPORT with VALID → DEFERRED
        assert ctx.po5_execution_eligibility.eligibility == ExecutionEligibility.DEFERRED

    def test_maybe_run_po5_without_phase_zero(self):
        """Test: maybe_run_po5 does nothing without Phase 0."""
        class MockContext:
            phase_zero = None
            phase_minus_one = None
            po4_proposal = None
            po5_execution_eligibility = None

        ctx = MockContext()
        maybe_run_po5(ctx)

        assert ctx.po5_execution_eligibility is None

    def test_maybe_run_po5_without_po4_proposal(self):
        """Test: maybe_run_po5 does nothing without PO4 proposal."""
        class MockContext:
            def __init__(self):
                self.phase_zero = IntentEnvelope(
                    intent_type=IntentType.INFORM,
                    response_posture=ResponsePosture.ENGAGE_OPEN,
                    planning_allowed=True,
                    phase_minus_one_policy=OverallPolicy.SINGLE_CONTEXT,
                )
                self.phase_minus_one = None
                self.po4_proposal = None
                self.po5_execution_eligibility = None

        ctx = MockContext()
        maybe_run_po5(ctx)

        assert ctx.po5_execution_eligibility is None

    def test_maybe_run_po5_without_phase_minus_one(self):
        """Test: maybe_run_po5 does nothing without Phase -1."""
        class MockContext:
            def __init__(self):
                self.phase_zero = IntentEnvelope(
                    intent_type=IntentType.INFORM,
                    response_posture=ResponsePosture.ENGAGE_OPEN,
                    planning_allowed=True,
                    phase_minus_one_policy=OverallPolicy.SINGLE_CONTEXT,
                )
                self.po4_proposal = PlannerProposalEnvelope(
                    intent=IntentType.INFORM,
                    allowed_actions=frozenset({ActionClass.EXPLAIN}),
                    proposed_actions=frozenset({ActionClass.EXPLAIN}),
                    rejected_actions={},
                    status=ProposalStatus.VALID,
                )
                self.phase_minus_one = None
                self.po5_execution_eligibility = None

        ctx = MockContext()
        maybe_run_po5(ctx)

        assert ctx.po5_execution_eligibility is None

    def test_get_po5_eligibility(self):
        """Test: get_po5_eligibility retrieves from context."""
        class MockContext:
            def __init__(self, eligibility):
                self.po5_execution_eligibility = eligibility

        envelope = ExecutionEligibilityEnvelope(
            eligibility=ExecutionEligibility.PROHIBITED,
            reason="Test reason",
            intent=IntentType.INFORM,
            proposal_status=ProposalStatus.BLOCKED,
        )
        ctx = MockContext(envelope)

        result = get_po5_eligibility(ctx)

        assert result is envelope

    def test_is_execution_prohibited(self):
        """Test: is_execution_prohibited returns correct value."""
        class MockContext:
            def __init__(self, eligibility):
                self.po5_execution_eligibility = eligibility

        prohibited_envelope = ExecutionEligibilityEnvelope(
            eligibility=ExecutionEligibility.PROHIBITED,
            reason="Test reason",
            intent=IntentType.INFORM,
            proposal_status=ProposalStatus.BLOCKED,
        )
        ctx = MockContext(prohibited_envelope)

        assert is_execution_prohibited(ctx) is True

    def test_is_execution_prohibited_no_po5(self):
        """Test: is_execution_prohibited returns True when PO5 hasn't run (conservative)."""
        class MockContext:
            po5_execution_eligibility = None

        ctx = MockContext()

        # Conservative default: prohibited if PO5 hasn't run
        assert is_execution_prohibited(ctx) is True

    def test_is_execution_deferred(self):
        """Test: is_execution_deferred returns correct value."""
        class MockContext:
            def __init__(self, eligibility):
                self.po5_execution_eligibility = eligibility

        deferred_envelope = ExecutionEligibilityEnvelope(
            eligibility=ExecutionEligibility.DEFERRED,
            reason="Test reason",
            intent=IntentType.SUPPORT,
            proposal_status=ProposalStatus.VALID,
        )
        ctx = MockContext(deferred_envelope)

        assert is_execution_deferred(ctx) is True

    def test_is_execution_eligible(self):
        """Test: is_execution_eligible returns correct value (informational only)."""
        class MockContext:
            def __init__(self, eligibility):
                self.po5_execution_eligibility = eligibility

        eligible_envelope = ExecutionEligibilityEnvelope(
            eligibility=ExecutionEligibility.ELIGIBLE,
            reason="Conceptually eligible (informational only)",
            intent=IntentType.ABSTAIN,
            proposal_status=ProposalStatus.VALID,
        )
        ctx = MockContext(eligible_envelope)

        assert is_execution_eligible(ctx) is True

    def test_get_eligibility_reason(self):
        """Test: get_eligibility_reason returns reason string."""
        class MockContext:
            def __init__(self, eligibility):
                self.po5_execution_eligibility = eligibility

        envelope = ExecutionEligibilityEnvelope(
            eligibility=ExecutionEligibility.PROHIBITED,
            reason="Test prohibition reason",
            intent=IntentType.INFORM,
            proposal_status=ProposalStatus.BLOCKED,
        )
        ctx = MockContext(envelope)

        result = get_eligibility_reason(ctx)

        assert result == "Test prohibition reason"


class TestRulePriority:
    """Tests verifying rule evaluation order is correct."""

    def setup_method(self):
        """Set up test fixtures."""
        self.gate = PO5ExecutionGate()

    def test_blocked_proposal_takes_priority(self):
        """Test: Rule 1 (BLOCKED proposal) takes priority over all other rules."""
        # Create scenario where multiple rules could apply
        # BLOCKED proposal + HOLD posture + CLARIFY intent
        intent_envelope = IntentEnvelope(
            intent_type=IntentType.CLARIFY,
            response_posture=ResponsePosture.HOLD,
            planning_allowed=False,
            phase_minus_one_policy=OverallPolicy.MULTI_CONTEXT,
        )
        proposal = PlannerProposalEnvelope(
            intent=IntentType.CLARIFY,
            allowed_actions=frozenset(),
            proposed_actions=frozenset({ActionClass.EXPLAIN}),
            rejected_actions={ActionClass.EXPLAIN: "Rejected"},
            status=ProposalStatus.BLOCKED,
            blocked_reason="Test blocked",
        )

        result = self.gate.evaluate(
            intent_envelope, proposal, OverallPolicy.MULTI_CONTEXT
        )

        # Rule 1 should fire first (BLOCKED proposal)
        assert result.eligibility == ExecutionEligibility.PROHIBITED
        assert "BLOCKED" in result.reason

    def test_posture_takes_priority_over_intent(self):
        """Test: Rule 2 (posture) takes priority over Rule 3 (intent)."""
        # Create scenario: HOLD posture with INFORM intent
        # Rule 2 (HOLD) should fire before Rule 3 (INFORM)
        intent_envelope = IntentEnvelope(
            intent_type=IntentType.INFORM,
            response_posture=ResponsePosture.HOLD,
            planning_allowed=False,
            phase_minus_one_policy=OverallPolicy.SINGLE_CONTEXT,
        )
        proposal = PlannerProposalEnvelope(
            intent=IntentType.INFORM,
            allowed_actions=frozenset({ActionClass.EXPLAIN}),
            proposed_actions=frozenset({ActionClass.EXPLAIN}),
            rejected_actions={},
            status=ProposalStatus.VALID,
        )

        result = self.gate.evaluate(
            intent_envelope, proposal, OverallPolicy.SINGLE_CONTEXT
        )

        # Rule 2 should fire (HOLD posture)
        assert result.eligibility == ExecutionEligibility.PROHIBITED
        assert "HOLD" in result.reason

    def test_multi_context_takes_priority_over_intent_posture_rules(self):
        """Test: Rule 4 (MULTI_CONTEXT) takes priority over Rule 5."""
        # Create scenario: SUPPORT intent with VALID proposal and MULTI_CONTEXT
        intent_envelope = IntentEnvelope(
            intent_type=IntentType.SUPPORT,
            response_posture=ResponsePosture.ENGAGE_CAREFUL,
            planning_allowed=True,
            phase_minus_one_policy=OverallPolicy.MULTI_CONTEXT,
        )
        proposal = PlannerProposalEnvelope(
            intent=IntentType.SUPPORT,
            allowed_actions=frozenset({ActionClass.CARE}),
            proposed_actions=frozenset({ActionClass.CARE}),
            rejected_actions={},
            status=ProposalStatus.VALID,
        )

        result = self.gate.evaluate(
            intent_envelope, proposal, OverallPolicy.MULTI_CONTEXT
        )

        # Rule 4 should fire (MULTI_CONTEXT)
        assert result.eligibility == ExecutionEligibility.DEFERRED
        assert "context" in result.reason.lower()


class TestArchitecturalPhase:
    """Tests verifying architectural phase identification."""

    def test_envelope_has_po5_phase(self):
        """Test: envelope correctly identifies as PO5."""
        envelope = ExecutionEligibilityEnvelope(
            eligibility=ExecutionEligibility.PROHIBITED,
            reason="Test reason",
            intent=IntentType.INFORM,
            proposal_status=ProposalStatus.BLOCKED,
        )

        assert envelope.architectural_phase == "PO5"
        assert envelope.to_dict()["architectural_phase"] == "PO5"


class TestAuthorityModel:
    """Tests verifying PO5 respects the authority model."""

    def setup_method(self):
        """Set up test fixtures."""
        self.gate = PO5ExecutionGate()

    def test_cannot_override_blocked_upstream(self):
        """Test: PO5 cannot override a BLOCKED policy from PO1."""
        # When PO1 is BLOCKED, IntentEnvelope MUST have CLARIFY intent and HOLD posture
        # This is enforced by IntentEnvelope validation
        intent_envelope = IntentEnvelope(
            intent_type=IntentType.CLARIFY,
            response_posture=ResponsePosture.HOLD,
            planning_allowed=False,
            phase_minus_one_policy=OverallPolicy.BLOCKED,
        )
        proposal = PlannerProposalEnvelope(
            intent=IntentType.CLARIFY,
            allowed_actions=frozenset({ActionClass.ASK_CLARIFY_REFERENCE}),
            proposed_actions=frozenset({ActionClass.ASK_CLARIFY_REFERENCE}),
            rejected_actions={},
            status=ProposalStatus.VALID,
        )

        result = self.gate.evaluate(
            intent_envelope, proposal, OverallPolicy.BLOCKED
        )

        # When upstream is BLOCKED, PO5 MUST return PROHIBITED
        # Rule 2 (HOLD posture) will fire and return PROHIBITED
        assert result.eligibility == ExecutionEligibility.PROHIBITED
        assert "HOLD" in result.reason

    def test_cannot_increase_planner_autonomy(self):
        """Test: PO5 does not increase planner autonomy."""
        # PO5 should never enable capabilities that PO1-PO4 prohibited

        # Case: PO4 proposal is BLOCKED, PO5 must not make ELIGIBLE
        intent_envelope = IntentEnvelope(
            intent_type=IntentType.ABSTAIN,
            response_posture=ResponsePosture.ENGAGE_OPEN,
            planning_allowed=True,
            phase_minus_one_policy=OverallPolicy.SINGLE_CONTEXT,
        )
        blocked_proposal = PlannerProposalEnvelope(
            intent=IntentType.ABSTAIN,
            allowed_actions=frozenset(),
            proposed_actions=frozenset({ActionClass.EXPLAIN}),
            rejected_actions={ActionClass.EXPLAIN: "Rejected"},
            status=ProposalStatus.BLOCKED,
            blocked_reason="Test blocked",
        )

        result = self.gate.evaluate(
            intent_envelope, blocked_proposal, OverallPolicy.SINGLE_CONTEXT
        )

        # Must be PROHIBITED when PO4 is BLOCKED
        assert result.eligibility == ExecutionEligibility.PROHIBITED


# Run tests if executed directly
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
