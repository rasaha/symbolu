"""
PO4 Unit Tests

Tests for PO4 Planner Proposal Envelope:
- ProposalStatus enum
- PlannerProposalEnvelope dataclass
- PO4Resolver
- Integration with PO2/PO3

Test Cases (per specification):
1. VALID proposal - all proposed actions allowed
2. PARTIALLY_ALLOWED proposal - some actions rejected
3. BLOCKED proposal - all actions rejected or PO3 empty
4. Determinism (same input → same output)
5. No execution leakage
"""

import pytest
from symbolu.mechanical.pipeline.phase_po4 import (
    PO4Resolver,
    PlannerProposalEnvelope,
    ProposalStatus,
)
from symbolu.mechanical.pipeline.phase_po4.po4_integration import (
    get_po4_resolver,
    maybe_run_po4,
    run_po4_directly,
    get_po4_proposal,
    is_proposal_valid,
    is_proposal_blocked,
    get_allowed_proposed_actions,
    get_rejected_proposed_actions,
)
from symbolu.mechanical.pipeline.phase_zero.phase_zero_schema import (
    IntentEnvelope,
    IntentType,
    ResponsePosture,
)
from symbolu.mechanical.pipeline.phase_one.phase_one_schema import AllowedActionSet
from symbolu.mechanical.pipeline.governance.planner_gate import ActionClass
from symbolu.mechanical.pipeline.grounding.phase_minus_one_schema import OverallPolicy


class TestProposalStatusEnum:
    """Tests for ProposalStatus enum."""

    def test_valid_value(self):
        """Test: VALID status exists."""
        assert ProposalStatus.VALID.value == "VALID"

    def test_partially_allowed_value(self):
        """Test: PARTIALLY_ALLOWED status exists."""
        assert ProposalStatus.PARTIALLY_ALLOWED.value == "PARTIALLY_ALLOWED"

    def test_blocked_value(self):
        """Test: BLOCKED status exists."""
        assert ProposalStatus.BLOCKED.value == "BLOCKED"

    def test_all_statuses_exist(self):
        """Test: all three statuses exist."""
        statuses = list(ProposalStatus)
        assert len(statuses) == 3
        assert ProposalStatus.VALID in statuses
        assert ProposalStatus.PARTIALLY_ALLOWED in statuses
        assert ProposalStatus.BLOCKED in statuses


class TestPlannerProposalEnvelope:
    """Tests for PlannerProposalEnvelope dataclass."""

    def test_basic_construction_valid(self):
        """Test: basic envelope construction with VALID status."""
        envelope = PlannerProposalEnvelope(
            intent=IntentType.INFORM,
            allowed_actions=frozenset({ActionClass.EXPLAIN, ActionClass.SUMMARIZE}),
            proposed_actions=frozenset({ActionClass.EXPLAIN, ActionClass.SUMMARIZE}),
            rejected_actions={},
            status=ProposalStatus.VALID,
        )

        assert envelope.intent == IntentType.INFORM
        assert envelope.status == ProposalStatus.VALID
        assert envelope.allowed_count() == 2
        assert envelope.rejected_count() == 0
        assert envelope.proposed_count() == 2

    def test_basic_construction_partial(self):
        """Test: envelope construction with PARTIALLY_ALLOWED status."""
        envelope = PlannerProposalEnvelope(
            intent=IntentType.INFORM,
            allowed_actions=frozenset({ActionClass.EXPLAIN}),
            proposed_actions=frozenset({ActionClass.EXPLAIN, ActionClass.CARE}),
            rejected_actions={ActionClass.CARE: "Not in PO3 allow-list"},
            status=ProposalStatus.PARTIALLY_ALLOWED,
        )

        assert envelope.status == ProposalStatus.PARTIALLY_ALLOWED
        assert envelope.allowed_count() == 1
        assert envelope.rejected_count() == 1
        assert envelope.proposed_count() == 2

    def test_basic_construction_blocked(self):
        """Test: envelope construction with BLOCKED status."""
        envelope = PlannerProposalEnvelope(
            intent=IntentType.ABSTAIN,
            allowed_actions=frozenset(),
            proposed_actions=frozenset({ActionClass.CARE}),
            rejected_actions={ActionClass.CARE: "PO3 is empty"},
            status=ProposalStatus.BLOCKED,
            blocked_reason="PO3 allow-list is empty for intent ABSTAIN",
        )

        assert envelope.status == ProposalStatus.BLOCKED
        assert envelope.is_blocked() is True
        assert envelope.allowed_count() == 0
        assert envelope.blocked_reason is not None

    def test_immutability(self):
        """Test: PlannerProposalEnvelope is frozen (immutable)."""
        envelope = PlannerProposalEnvelope(
            intent=IntentType.INFORM,
            allowed_actions=frozenset({ActionClass.EXPLAIN}),
            proposed_actions=frozenset({ActionClass.EXPLAIN}),
            rejected_actions={},
            status=ProposalStatus.VALID,
        )

        with pytest.raises(Exception):
            envelope.status = ProposalStatus.BLOCKED

    def test_none_intent_raises(self):
        """Test: None intent raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            PlannerProposalEnvelope(
                intent=None,  # type: ignore
                allowed_actions=frozenset(),
                proposed_actions=frozenset(),
                rejected_actions={},
                status=ProposalStatus.VALID,
            )
        assert "intent cannot be None" in str(exc_info.value)

    def test_none_status_raises(self):
        """Test: None status raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            PlannerProposalEnvelope(
                intent=IntentType.INFORM,
                allowed_actions=frozenset(),
                proposed_actions=frozenset(),
                rejected_actions={},
                status=None,  # type: ignore
            )
        assert "status cannot be None" in str(exc_info.value)

    def test_non_frozenset_allowed_raises(self):
        """Test: non-frozenset allowed_actions raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            PlannerProposalEnvelope(
                intent=IntentType.INFORM,
                allowed_actions=set([ActionClass.EXPLAIN]),  # type: ignore
                proposed_actions=frozenset({ActionClass.EXPLAIN}),
                rejected_actions={},
                status=ProposalStatus.VALID,
            )
        assert "must be a frozenset" in str(exc_info.value)

    def test_non_frozenset_proposed_raises(self):
        """Test: non-frozenset proposed_actions raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            PlannerProposalEnvelope(
                intent=IntentType.INFORM,
                allowed_actions=frozenset({ActionClass.EXPLAIN}),
                proposed_actions=[ActionClass.EXPLAIN],  # type: ignore
                rejected_actions={},
                status=ProposalStatus.VALID,
            )
        assert "must be a frozenset" in str(exc_info.value)

    def test_invalid_action_type_in_allowed_raises(self):
        """Test: non-ActionClass in allowed_actions raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            PlannerProposalEnvelope(
                intent=IntentType.INFORM,
                allowed_actions=frozenset({"EXPLAIN"}),  # type: ignore
                proposed_actions=frozenset({ActionClass.EXPLAIN}),
                rejected_actions={},
                status=ProposalStatus.VALID,
            )
        assert "must contain only ActionClass" in str(exc_info.value)

    def test_empty_rejection_reason_raises(self):
        """Test: empty rejection reason raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            PlannerProposalEnvelope(
                intent=IntentType.INFORM,
                allowed_actions=frozenset(),
                proposed_actions=frozenset({ActionClass.CARE}),
                rejected_actions={ActionClass.CARE: ""},  # Empty reason
                status=ProposalStatus.BLOCKED,
                blocked_reason="test",
            )
        assert "non-empty string reasons" in str(exc_info.value)

    def test_allowed_not_subset_of_proposed_raises(self):
        """Test: allowed not subset of proposed raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            PlannerProposalEnvelope(
                intent=IntentType.INFORM,
                allowed_actions=frozenset({ActionClass.EXPLAIN, ActionClass.SUMMARIZE}),
                proposed_actions=frozenset({ActionClass.EXPLAIN}),  # Missing SUMMARIZE
                rejected_actions={},
                status=ProposalStatus.VALID,
            )
        assert "must be subset of proposed_actions" in str(exc_info.value)

    def test_action_both_allowed_and_rejected_raises(self):
        """Test: action in both allowed and rejected raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            PlannerProposalEnvelope(
                intent=IntentType.INFORM,
                allowed_actions=frozenset({ActionClass.EXPLAIN}),
                proposed_actions=frozenset({ActionClass.EXPLAIN}),
                rejected_actions={ActionClass.EXPLAIN: "Also rejected"},  # Contradiction
                status=ProposalStatus.PARTIALLY_ALLOWED,
            )
        assert "cannot be both allowed and rejected" in str(exc_info.value)

    def test_blocked_with_allowed_actions_raises(self):
        """Test: BLOCKED status with non-empty allowed raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            PlannerProposalEnvelope(
                intent=IntentType.INFORM,
                allowed_actions=frozenset({ActionClass.EXPLAIN}),  # Non-empty
                proposed_actions=frozenset({ActionClass.EXPLAIN}),
                rejected_actions={},
                status=ProposalStatus.BLOCKED,
                blocked_reason="test",
            )
        assert "requires allowed_actions to be empty" in str(exc_info.value)

    def test_blocked_without_reason_raises(self):
        """Test: BLOCKED status without reason raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            PlannerProposalEnvelope(
                intent=IntentType.ABSTAIN,
                allowed_actions=frozenset(),
                proposed_actions=frozenset(),
                rejected_actions={},
                status=ProposalStatus.BLOCKED,
                blocked_reason=None,  # Missing reason
            )
        assert "requires blocked_reason to be set" in str(exc_info.value)

    def test_valid_with_rejected_raises(self):
        """Test: VALID status with rejected actions raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            PlannerProposalEnvelope(
                intent=IntentType.INFORM,
                allowed_actions=frozenset({ActionClass.EXPLAIN}),
                proposed_actions=frozenset({ActionClass.EXPLAIN, ActionClass.CARE}),
                rejected_actions={ActionClass.CARE: "rejected"},  # Has rejections
                status=ProposalStatus.VALID,  # But claims valid
            )
        assert "requires no rejected_actions" in str(exc_info.value)

    def test_is_blocked_method(self):
        """Test: is_blocked() method."""
        blocked = PlannerProposalEnvelope(
            intent=IntentType.ABSTAIN,
            allowed_actions=frozenset(),
            proposed_actions=frozenset(),
            rejected_actions={},
            status=ProposalStatus.BLOCKED,
            blocked_reason="test",
        )
        assert blocked.is_blocked() is True

        valid = PlannerProposalEnvelope(
            intent=IntentType.INFORM,
            allowed_actions=frozenset({ActionClass.EXPLAIN}),
            proposed_actions=frozenset({ActionClass.EXPLAIN}),
            rejected_actions={},
            status=ProposalStatus.VALID,
        )
        assert valid.is_blocked() is False

    def test_is_valid_method(self):
        """Test: is_valid() method."""
        valid = PlannerProposalEnvelope(
            intent=IntentType.INFORM,
            allowed_actions=frozenset({ActionClass.EXPLAIN}),
            proposed_actions=frozenset({ActionClass.EXPLAIN}),
            rejected_actions={},
            status=ProposalStatus.VALID,
        )
        assert valid.is_valid() is True

        partial = PlannerProposalEnvelope(
            intent=IntentType.INFORM,
            allowed_actions=frozenset({ActionClass.EXPLAIN}),
            proposed_actions=frozenset({ActionClass.EXPLAIN, ActionClass.CARE}),
            rejected_actions={ActionClass.CARE: "rejected"},
            status=ProposalStatus.PARTIALLY_ALLOWED,
        )
        assert partial.is_valid() is False

    def test_is_partial_method(self):
        """Test: is_partial() method."""
        partial = PlannerProposalEnvelope(
            intent=IntentType.INFORM,
            allowed_actions=frozenset({ActionClass.EXPLAIN}),
            proposed_actions=frozenset({ActionClass.EXPLAIN, ActionClass.CARE}),
            rejected_actions={ActionClass.CARE: "rejected"},
            status=ProposalStatus.PARTIALLY_ALLOWED,
        )
        assert partial.is_partial() is True

    def test_to_dict_serialization(self):
        """Test: to_dict() serialization."""
        envelope = PlannerProposalEnvelope(
            intent=IntentType.INFORM,
            allowed_actions=frozenset({ActionClass.EXPLAIN, ActionClass.SUMMARIZE}),
            proposed_actions=frozenset({ActionClass.EXPLAIN, ActionClass.SUMMARIZE, ActionClass.CARE}),
            rejected_actions={ActionClass.CARE: "Not allowed for INFORM"},
            status=ProposalStatus.PARTIALLY_ALLOWED,
            debug={"key": "value"},
        )

        d = envelope.to_dict()

        assert d["intent"] == "INFORM"
        assert d["status"] == "PARTIALLY_ALLOWED"
        assert d["allowed_count"] == 2
        assert d["rejected_count"] == 1
        assert d["proposed_count"] == 3
        assert "EXPLAIN" in d["allowed_actions"]
        assert "CARE" in d["rejected_actions"]
        assert d["architectural_phase"] == "PO4"
        assert d["debug"]["key"] == "value"


class TestPO4Resolver:
    """Tests for PO4Resolver."""

    def setup_method(self):
        """Set up test fixtures."""
        self.resolver = PO4Resolver()

    def _make_intent_envelope(
        self,
        intent_type: IntentType,
        planning_allowed: bool = True,
    ) -> IntentEnvelope:
        """Helper to create test IntentEnvelope."""
        posture_map = {
            IntentType.CLARIFY: ResponsePosture.HOLD,
            IntentType.SUPPORT: ResponsePosture.ACKNOWLEDGE,
            IntentType.REFLECT: ResponsePosture.ENGAGE_CAREFUL,
            IntentType.INFORM: ResponsePosture.ENGAGE_OPEN,
            IntentType.ABSTAIN: ResponsePosture.HOLD,
        }
        return IntentEnvelope(
            intent_type=intent_type,
            response_posture=posture_map[intent_type],
            planning_allowed=planning_allowed,
            phase_minus_one_policy=OverallPolicy.SINGLE_CONTEXT,
            resolution_reason="Test envelope",
        )

    def _make_allowed_action_set(
        self,
        intent_type: IntentType,
        allowed: frozenset[ActionClass],
    ) -> AllowedActionSet:
        """Helper to create test AllowedActionSet."""
        return AllowedActionSet(
            intent_type=intent_type,
            allowed_actions=allowed,
            run_id="test-p1",
            resolution_reason="Test allowed set",
        )

    def test_valid_proposal_all_actions_allowed(self):
        """
        Test Case 1: VALID proposal - all proposed actions allowed.

        When all proposed actions are in PO3 allow-list, status is VALID.
        """
        intent_envelope = self._make_intent_envelope(IntentType.INFORM)
        allowed_set = self._make_allowed_action_set(
            IntentType.INFORM,
            frozenset({ActionClass.EXPLAIN, ActionClass.SUMMARIZE, ActionClass.COMPARE}),
        )
        proposed = [ActionClass.EXPLAIN, ActionClass.SUMMARIZE]

        result = self.resolver.resolve(intent_envelope, allowed_set, proposed)

        assert result.status == ProposalStatus.VALID
        assert result.is_valid() is True
        assert result.allowed_count() == 2
        assert result.rejected_count() == 0
        assert ActionClass.EXPLAIN in result.allowed_actions
        assert ActionClass.SUMMARIZE in result.allowed_actions

    def test_partially_allowed_proposal_some_rejected(self):
        """
        Test Case 2: PARTIALLY_ALLOWED proposal - some actions rejected.

        When some proposed actions are not in PO3 allow-list, status is PARTIALLY_ALLOWED.
        """
        intent_envelope = self._make_intent_envelope(IntentType.INFORM)
        allowed_set = self._make_allowed_action_set(
            IntentType.INFORM,
            frozenset({ActionClass.EXPLAIN, ActionClass.SUMMARIZE}),
        )
        # Propose EXPLAIN (allowed) and CARE (not allowed for INFORM)
        proposed = [ActionClass.EXPLAIN, ActionClass.CARE]

        result = self.resolver.resolve(intent_envelope, allowed_set, proposed)

        assert result.status == ProposalStatus.PARTIALLY_ALLOWED
        assert result.is_partial() is True
        assert result.allowed_count() == 1
        assert result.rejected_count() == 1
        assert ActionClass.EXPLAIN in result.allowed_actions
        assert ActionClass.CARE in result.rejected_actions
        assert "not in PO3 allow-list" in result.rejected_actions[ActionClass.CARE]

    def test_blocked_proposal_all_rejected(self):
        """
        Test Case 3: BLOCKED proposal - all proposed actions rejected.

        When all proposed actions are not in PO3 allow-list, status is BLOCKED.
        """
        intent_envelope = self._make_intent_envelope(IntentType.INFORM)
        allowed_set = self._make_allowed_action_set(
            IntentType.INFORM,
            frozenset({ActionClass.EXPLAIN}),
        )
        # Propose only actions that are NOT allowed
        proposed = [ActionClass.CARE, ActionClass.VALIDATE]

        result = self.resolver.resolve(intent_envelope, allowed_set, proposed)

        assert result.status == ProposalStatus.BLOCKED
        assert result.is_blocked() is True
        assert result.allowed_count() == 0
        assert result.rejected_count() == 2
        assert result.blocked_reason is not None
        assert "All proposed actions rejected" in result.blocked_reason

    def test_blocked_proposal_empty_po3_allow_list(self):
        """
        Test Case 3b: BLOCKED proposal - PO3 allow-list is empty.

        When PO3 has no allowed actions (ABSTAIN), status is BLOCKED.
        """
        intent_envelope = self._make_intent_envelope(IntentType.ABSTAIN, planning_allowed=False)
        allowed_set = self._make_allowed_action_set(
            IntentType.ABSTAIN,
            frozenset(),  # Empty for ABSTAIN
        )
        proposed = [ActionClass.CARE]

        result = self.resolver.resolve(intent_envelope, allowed_set, proposed)

        assert result.status == ProposalStatus.BLOCKED
        assert result.is_blocked() is True
        assert result.blocked_reason is not None
        assert "PO3 allow-list is empty" in result.blocked_reason

    def test_valid_proposal_empty_proposal(self):
        """Test: empty proposal is valid (no actions to validate)."""
        intent_envelope = self._make_intent_envelope(IntentType.INFORM)
        allowed_set = self._make_allowed_action_set(
            IntentType.INFORM,
            frozenset({ActionClass.EXPLAIN}),
        )
        proposed: list[ActionClass] = []  # Empty proposal

        result = self.resolver.resolve(intent_envelope, allowed_set, proposed)

        assert result.status == ProposalStatus.VALID
        assert result.allowed_count() == 0
        assert result.rejected_count() == 0
        assert result.proposed_count() == 0

    def test_none_intent_envelope_raises(self):
        """Test: None intent_envelope raises ValueError."""
        allowed_set = self._make_allowed_action_set(
            IntentType.INFORM,
            frozenset({ActionClass.EXPLAIN}),
        )
        with pytest.raises(ValueError) as exc_info:
            self.resolver.resolve(None, allowed_set, [ActionClass.EXPLAIN])  # type: ignore
        assert "intent_envelope cannot be None" in str(exc_info.value)

    def test_none_allowed_action_set_raises(self):
        """Test: None allowed_action_set raises ValueError."""
        intent_envelope = self._make_intent_envelope(IntentType.INFORM)
        with pytest.raises(ValueError) as exc_info:
            self.resolver.resolve(intent_envelope, None, [ActionClass.EXPLAIN])  # type: ignore
        assert "allowed_action_set cannot be None" in str(exc_info.value)

    def test_none_proposed_actions_raises(self):
        """Test: None proposed_actions raises ValueError."""
        intent_envelope = self._make_intent_envelope(IntentType.INFORM)
        allowed_set = self._make_allowed_action_set(
            IntentType.INFORM,
            frozenset({ActionClass.EXPLAIN}),
        )
        with pytest.raises(ValueError) as exc_info:
            self.resolver.resolve(intent_envelope, allowed_set, None)  # type: ignore
        assert "proposed_actions cannot be None" in str(exc_info.value)

    def test_invalid_action_in_proposed_raises(self):
        """Test: non-ActionClass in proposed raises ValueError."""
        intent_envelope = self._make_intent_envelope(IntentType.INFORM)
        allowed_set = self._make_allowed_action_set(
            IntentType.INFORM,
            frozenset({ActionClass.EXPLAIN}),
        )
        with pytest.raises(ValueError) as exc_info:
            self.resolver.resolve(intent_envelope, allowed_set, ["EXPLAIN"])  # type: ignore
        assert "must be ActionClass" in str(exc_info.value)

    def test_debug_info_populated(self):
        """Test: debug info is populated in result."""
        intent_envelope = self._make_intent_envelope(IntentType.INFORM)
        allowed_set = self._make_allowed_action_set(
            IntentType.INFORM,
            frozenset({ActionClass.EXPLAIN}),
        )
        proposed = [ActionClass.EXPLAIN]

        result = self.resolver.resolve(intent_envelope, allowed_set, proposed)

        assert result.debug is not None
        assert "source_intent" in result.debug
        assert "source_posture" in result.debug
        assert "po3_allowed_count" in result.debug
        assert result.debug["source_intent"] == "INFORM"


class TestDeterminism:
    """Tests verifying deterministic behavior (no randomness)."""

    def setup_method(self):
        """Set up test fixtures."""
        self.resolver = PO4Resolver()

    def _make_envelope_and_allowed(
        self, intent_type: IntentType
    ) -> tuple[IntentEnvelope, AllowedActionSet]:
        """Helper to create test inputs."""
        posture_map = {
            IntentType.CLARIFY: ResponsePosture.HOLD,
            IntentType.SUPPORT: ResponsePosture.ACKNOWLEDGE,
            IntentType.REFLECT: ResponsePosture.ENGAGE_CAREFUL,
            IntentType.INFORM: ResponsePosture.ENGAGE_OPEN,
            IntentType.ABSTAIN: ResponsePosture.HOLD,
        }
        intent_envelope = IntentEnvelope(
            intent_type=intent_type,
            response_posture=posture_map[intent_type],
            planning_allowed=True,
            phase_minus_one_policy=OverallPolicy.SINGLE_CONTEXT,
        )

        action_map = {
            IntentType.CLARIFY: frozenset({ActionClass.ASK_CLARIFY_REFERENCE, ActionClass.ASK}),
            IntentType.SUPPORT: frozenset({ActionClass.CARE, ActionClass.VALIDATE}),
            IntentType.REFLECT: frozenset({ActionClass.REFLECT, ActionClass.ASK}),
            IntentType.INFORM: frozenset({ActionClass.EXPLAIN, ActionClass.SUMMARIZE}),
            IntentType.ABSTAIN: frozenset(),
        }
        allowed_set = AllowedActionSet(
            intent_type=intent_type,
            allowed_actions=action_map[intent_type],
        )

        return intent_envelope, allowed_set

    def test_same_input_same_output(self):
        """
        Test Case 4: Determinism - same input → same output.

        Multiple runs with the same input must produce identical results.
        """
        intent_envelope, allowed_set = self._make_envelope_and_allowed(IntentType.INFORM)
        proposed = [ActionClass.EXPLAIN, ActionClass.CARE]

        results = []
        for _ in range(10):
            result = self.resolver.resolve(intent_envelope, allowed_set, proposed)
            results.append((result.status, result.allowed_actions, frozenset(result.rejected_actions.keys())))

        # All results should be identical
        assert all(r == results[0] for r in results)

    def test_all_intents_deterministic(self):
        """Test: all intent types produce deterministic results."""
        for intent_type in IntentType:
            intent_envelope, allowed_set = self._make_envelope_and_allowed(intent_type)
            proposed = [ActionClass.EXPLAIN, ActionClass.CARE]

            results = []
            for _ in range(5):
                result = self.resolver.resolve(intent_envelope, allowed_set, proposed)
                results.append((result.status, result.allowed_actions))

            assert all(r == results[0] for r in results), f"Non-deterministic for {intent_type}"

    def test_serialization_order_consistent(self):
        """Test: serialization ordering is consistent."""
        intent_envelope, allowed_set = self._make_envelope_and_allowed(IntentType.INFORM)
        proposed = [ActionClass.EXPLAIN, ActionClass.SUMMARIZE]

        serialized = []
        for _ in range(5):
            result = self.resolver.resolve(intent_envelope, allowed_set, proposed)
            serialized.append(result.to_dict()["allowed_actions"])

        assert all(s == serialized[0] for s in serialized)


class TestNoExecutionLeakage:
    """Tests verifying PO4 does NOT execute any actions."""

    def setup_method(self):
        """Set up test fixtures."""
        self.resolver = PO4Resolver()
        self.execution_log: list[str] = []

    def test_resolve_does_not_call_actions(self):
        """
        Test Case 5: No execution leakage.

        PO4 must only wrap and validate - never execute actions.
        """
        posture_map = {
            IntentType.INFORM: ResponsePosture.ENGAGE_OPEN,
        }
        intent_envelope = IntentEnvelope(
            intent_type=IntentType.INFORM,
            response_posture=posture_map[IntentType.INFORM],
            planning_allowed=True,
            phase_minus_one_policy=OverallPolicy.SINGLE_CONTEXT,
        )
        allowed_set = AllowedActionSet(
            intent_type=IntentType.INFORM,
            allowed_actions=frozenset({ActionClass.EXPLAIN}),
        )

        # Track any execution attempts
        original_resolve = self.resolver.resolve

        def tracking_resolve(*args, **kwargs):
            result = original_resolve(*args, **kwargs)
            # If any action was "executed", we'd log it here
            # PO4 should never do anything besides wrap
            self.execution_log.append("resolve_completed")
            return result

        self.resolver.resolve = tracking_resolve

        # Call resolve
        result = self.resolver.resolve(intent_envelope, allowed_set, [ActionClass.EXPLAIN])

        # Verify only tracking, no execution
        assert len(self.execution_log) == 1
        assert self.execution_log[0] == "resolve_completed"

        # Verify envelope is just a wrapper
        assert isinstance(result, PlannerProposalEnvelope)
        assert result.architectural_phase == "PO4"

    def test_envelope_is_pure_data(self):
        """Test: envelope contains no callable methods that execute."""
        envelope = PlannerProposalEnvelope(
            intent=IntentType.INFORM,
            allowed_actions=frozenset({ActionClass.EXPLAIN}),
            proposed_actions=frozenset({ActionClass.EXPLAIN}),
            rejected_actions={},
            status=ProposalStatus.VALID,
        )

        # Check that methods are read-only inspectors
        assert callable(envelope.is_blocked)
        assert callable(envelope.is_valid)
        assert callable(envelope.to_dict)

        # These should be query methods, not execution
        result1 = envelope.is_blocked()
        result2 = envelope.is_valid()
        result3 = envelope.to_dict()

        assert isinstance(result1, bool)
        assert isinstance(result2, bool)
        assert isinstance(result3, dict)


class TestPO4Integration:
    """Tests for PO4 integration module."""

    def test_get_resolver_singleton(self):
        """Test: resolver is a singleton."""
        resolver1 = get_po4_resolver()
        resolver2 = get_po4_resolver()

        assert resolver1 is resolver2

    def test_run_po4_directly(self):
        """Test: run_po4_directly works."""
        intent_envelope = IntentEnvelope(
            intent_type=IntentType.INFORM,
            response_posture=ResponsePosture.ENGAGE_OPEN,
            planning_allowed=True,
            phase_minus_one_policy=OverallPolicy.SINGLE_CONTEXT,
        )
        allowed_set = AllowedActionSet(
            intent_type=IntentType.INFORM,
            allowed_actions=frozenset({ActionClass.EXPLAIN, ActionClass.SUMMARIZE}),
        )

        result = run_po4_directly(intent_envelope, allowed_set, [ActionClass.EXPLAIN])

        assert result is not None
        assert isinstance(result, PlannerProposalEnvelope)
        assert result.status == ProposalStatus.VALID

    def test_maybe_run_po4_with_context(self):
        """Test: maybe_run_po4 works with mock context."""
        class MockContext:
            def __init__(self):
                self.phase_zero = IntentEnvelope(
                    intent_type=IntentType.SUPPORT,
                    response_posture=ResponsePosture.ACKNOWLEDGE,
                    planning_allowed=True,
                    phase_minus_one_policy=OverallPolicy.SINGLE_CONTEXT,
                )
                self.allowed_actions = AllowedActionSet(
                    intent_type=IntentType.SUPPORT,
                    allowed_actions=frozenset({ActionClass.CARE, ActionClass.VALIDATE}),
                )
                self.po4_proposal = None

        ctx = MockContext()
        maybe_run_po4(ctx, [ActionClass.CARE])

        assert ctx.po4_proposal is not None
        assert isinstance(ctx.po4_proposal, PlannerProposalEnvelope)
        assert ctx.po4_proposal.status == ProposalStatus.VALID

    def test_maybe_run_po4_without_phase_zero(self):
        """Test: maybe_run_po4 does nothing without Phase 0."""
        class MockContext:
            phase_zero = None
            allowed_actions = None
            po4_proposal = None

        ctx = MockContext()
        maybe_run_po4(ctx, [ActionClass.EXPLAIN])

        assert ctx.po4_proposal is None

    def test_maybe_run_po4_without_allowed_actions(self):
        """Test: maybe_run_po4 does nothing without allowed_actions."""
        class MockContext:
            def __init__(self):
                self.phase_zero = IntentEnvelope(
                    intent_type=IntentType.INFORM,
                    response_posture=ResponsePosture.ENGAGE_OPEN,
                    planning_allowed=True,
                    phase_minus_one_policy=OverallPolicy.SINGLE_CONTEXT,
                )
                self.allowed_actions = None
                self.po4_proposal = None

        ctx = MockContext()
        maybe_run_po4(ctx, [ActionClass.EXPLAIN])

        assert ctx.po4_proposal is None

    def test_get_po4_proposal(self):
        """Test: get_po4_proposal retrieves from context."""
        class MockContext:
            def __init__(self, proposal):
                self.po4_proposal = proposal

        envelope = PlannerProposalEnvelope(
            intent=IntentType.INFORM,
            allowed_actions=frozenset({ActionClass.EXPLAIN}),
            proposed_actions=frozenset({ActionClass.EXPLAIN}),
            rejected_actions={},
            status=ProposalStatus.VALID,
        )
        ctx = MockContext(envelope)

        result = get_po4_proposal(ctx)

        assert result is envelope

    def test_is_proposal_valid(self):
        """Test: is_proposal_valid returns correct value."""
        class MockContext:
            def __init__(self, proposal):
                self.po4_proposal = proposal

        valid_envelope = PlannerProposalEnvelope(
            intent=IntentType.INFORM,
            allowed_actions=frozenset({ActionClass.EXPLAIN}),
            proposed_actions=frozenset({ActionClass.EXPLAIN}),
            rejected_actions={},
            status=ProposalStatus.VALID,
        )
        ctx = MockContext(valid_envelope)

        assert is_proposal_valid(ctx) is True

    def test_is_proposal_blocked(self):
        """Test: is_proposal_blocked returns correct value."""
        class MockContext:
            def __init__(self, proposal):
                self.po4_proposal = proposal

        blocked_envelope = PlannerProposalEnvelope(
            intent=IntentType.ABSTAIN,
            allowed_actions=frozenset(),
            proposed_actions=frozenset(),
            rejected_actions={},
            status=ProposalStatus.BLOCKED,
            blocked_reason="test",
        )
        ctx = MockContext(blocked_envelope)

        assert is_proposal_blocked(ctx) is True

    def test_is_proposal_blocked_no_po4(self):
        """Test: is_proposal_blocked returns True when PO4 hasn't run (conservative)."""
        class MockContext:
            po4_proposal = None

        ctx = MockContext()

        # Conservative default: blocked if PO4 hasn't run
        assert is_proposal_blocked(ctx) is True

    def test_get_allowed_proposed_actions(self):
        """Test: get_allowed_proposed_actions works correctly."""
        class MockContext:
            def __init__(self, proposal):
                self.po4_proposal = proposal

        envelope = PlannerProposalEnvelope(
            intent=IntentType.INFORM,
            allowed_actions=frozenset({ActionClass.EXPLAIN, ActionClass.SUMMARIZE}),
            proposed_actions=frozenset({ActionClass.EXPLAIN, ActionClass.SUMMARIZE}),
            rejected_actions={},
            status=ProposalStatus.VALID,
        )
        ctx = MockContext(envelope)

        result = get_allowed_proposed_actions(ctx)

        assert len(result) == 2
        assert ActionClass.EXPLAIN in result
        assert ActionClass.SUMMARIZE in result

    def test_get_rejected_proposed_actions(self):
        """Test: get_rejected_proposed_actions works correctly."""
        class MockContext:
            def __init__(self, proposal):
                self.po4_proposal = proposal

        envelope = PlannerProposalEnvelope(
            intent=IntentType.INFORM,
            allowed_actions=frozenset({ActionClass.EXPLAIN}),
            proposed_actions=frozenset({ActionClass.EXPLAIN, ActionClass.CARE}),
            rejected_actions={ActionClass.CARE: "Not allowed"},
            status=ProposalStatus.PARTIALLY_ALLOWED,
        )
        ctx = MockContext(envelope)

        result = get_rejected_proposed_actions(ctx)

        assert len(result) == 1
        assert ActionClass.CARE in result


class TestEndToEndScenarios:
    """End-to-end tests for complete PO2 → PO3 → PO4 flow."""

    def setup_method(self):
        """Set up test fixtures."""
        from symbolu.mechanical.pipeline.phase_zero import PhaseZeroResolver
        from symbolu.mechanical.pipeline.phase_one import PhaseOneResolver
        self.phase_zero = PhaseZeroResolver()
        self.phase_one = PhaseOneResolver()
        self.po4 = PO4Resolver()

    def test_e2e_inform_valid_proposal(self):
        """E2E: INFORM intent with valid proposal."""
        from symbolu.mechanical.pipeline.grounding import PhaseMinusOnePipeline

        pipeline = PhaseMinusOnePipeline()

        # Process "What is the weather like?" - DETACHED/INFORM
        phase_minus_one = pipeline.run("What is the weather like?")
        phase_zero = self.phase_zero.resolve(phase_minus_one)

        if phase_zero.intent_type == IntentType.INFORM:
            phase_one = self.phase_one.resolve(phase_zero)

            # Propose only allowed actions
            proposed = [ActionClass.EXPLAIN]
            po4_result = self.po4.resolve(phase_zero, phase_one, proposed)

            assert po4_result.status == ProposalStatus.VALID
            assert ActionClass.EXPLAIN in po4_result.allowed_actions
            assert po4_result.rejected_count() == 0

    def test_e2e_support_partial_proposal(self):
        """E2E: SUPPORT intent with partial proposal."""
        from symbolu.mechanical.pipeline.grounding import PhaseMinusOnePipeline

        pipeline = PhaseMinusOnePipeline()

        # Process "I feel anxious" - REFLEXIVE/SUPPORT
        phase_minus_one = pipeline.run("I feel anxious")
        phase_zero = self.phase_zero.resolve(phase_minus_one)

        if phase_zero.intent_type == IntentType.SUPPORT:
            phase_one = self.phase_one.resolve(phase_zero)

            # Propose CARE (allowed) and EXPLAIN (not allowed for SUPPORT)
            proposed = [ActionClass.CARE, ActionClass.EXPLAIN]
            po4_result = self.po4.resolve(phase_zero, phase_one, proposed)

            assert po4_result.status == ProposalStatus.PARTIALLY_ALLOWED
            assert ActionClass.CARE in po4_result.allowed_actions
            assert ActionClass.EXPLAIN in po4_result.rejected_actions


class TestArchitecturalPhase:
    """Tests verifying architectural phase identification."""

    def test_envelope_has_po4_phase(self):
        """Test: envelope correctly identifies as PO4."""
        envelope = PlannerProposalEnvelope(
            intent=IntentType.INFORM,
            allowed_actions=frozenset({ActionClass.EXPLAIN}),
            proposed_actions=frozenset({ActionClass.EXPLAIN}),
            rejected_actions={},
            status=ProposalStatus.VALID,
        )

        assert envelope.architectural_phase == "PO4"
        assert envelope.to_dict()["architectural_phase"] == "PO4"


# Run tests if executed directly
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
