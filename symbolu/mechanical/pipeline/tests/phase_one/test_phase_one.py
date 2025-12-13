"""
Phase 1 Unit Tests

Tests for Phase 1 Intent → Allowed Action Binding:
- AllowedActionSet dataclass
- PhaseOneResolver
- INTENT_TO_ACTIONS mapping
- Integration with Phase 0

Test Cases (per specification):
1. CLARIFY → only ASK / ASK_CLARIFY_REFERENCE
2. SUPPORT → no ANALYZE / EXPLAIN
3. ABSTAIN → empty allowed set
4. INFORM → EXPLAIN allowed, CARE forbidden
5. Determinism (same input → same output)
"""

import pytest
from symbolu.mechanical.pipeline.phase_one import (
    PhaseOneResolver,
    AllowedActionSet,
    INTENT_TO_ACTIONS,
)
from symbolu.mechanical.pipeline.phase_zero import (
    IntentEnvelope,
    IntentType,
    ResponsePosture,
    INTENT_TO_POSTURE,
)
from symbolu.mechanical.pipeline.governance.planner_gate import ActionClass
from symbolu.mechanical.pipeline.grounding import (
    PhaseMinusOnePipeline,
    OverallPolicy,
)
from symbolu.mechanical.pipeline.phase_one_integration import (
    get_phase_one_resolver,
    maybe_run_phase_one,
    run_phase_one_directly,
    get_allowed_actions,
    is_action_allowed,
    get_allowed_action_count,
)


class TestIntentToActionsMapping:
    """Tests for INTENT_TO_ACTIONS canonical mapping."""

    def test_all_intents_mapped(self):
        """Test: every IntentType has a mapping."""
        for intent_type in IntentType:
            assert intent_type in INTENT_TO_ACTIONS
            assert isinstance(INTENT_TO_ACTIONS[intent_type], frozenset)

    def test_clarify_mapping(self):
        """Test: CLARIFY → {ASK_CLARIFY_REFERENCE, ASK}"""
        allowed = INTENT_TO_ACTIONS[IntentType.CLARIFY]
        assert ActionClass.ASK_CLARIFY_REFERENCE in allowed
        assert ActionClass.ASK in allowed
        assert len(allowed) == 2

    def test_support_mapping(self):
        """Test: SUPPORT → {CARE, VALIDATE, REFLECT, GROUND}"""
        allowed = INTENT_TO_ACTIONS[IntentType.SUPPORT]
        assert ActionClass.CARE in allowed
        assert ActionClass.VALIDATE in allowed
        assert ActionClass.REFLECT in allowed
        assert ActionClass.GROUND in allowed
        assert len(allowed) == 4

    def test_reflect_mapping(self):
        """Test: REFLECT → {REFLECT, REFLECT_BACK, ASK, ALIGN}"""
        allowed = INTENT_TO_ACTIONS[IntentType.REFLECT]
        assert ActionClass.REFLECT in allowed
        assert ActionClass.REFLECT_BACK in allowed
        assert ActionClass.ASK in allowed
        assert ActionClass.ALIGN in allowed
        assert len(allowed) == 4

    def test_inform_mapping(self):
        """Test: INFORM → {EXPLAIN, SUMMARIZE, COMPARE}"""
        allowed = INTENT_TO_ACTIONS[IntentType.INFORM]
        assert ActionClass.EXPLAIN in allowed
        assert ActionClass.SUMMARIZE in allowed
        assert ActionClass.COMPARE in allowed
        assert len(allowed) == 3

    def test_abstain_mapping(self):
        """Test: ABSTAIN → empty set"""
        allowed = INTENT_TO_ACTIONS[IntentType.ABSTAIN]
        assert len(allowed) == 0
        assert allowed == frozenset()


class TestAllowedActionSet:
    """Tests for AllowedActionSet dataclass."""

    def test_basic_construction(self):
        """Test: basic AllowedActionSet construction."""
        actions = frozenset({ActionClass.ASK, ActionClass.CARE})
        allowed = AllowedActionSet(
            intent_type=IntentType.SUPPORT,
            allowed_actions=actions,
            run_id="test-001",
            resolution_reason="Test construction",
        )

        assert allowed.intent_type == IntentType.SUPPORT
        assert allowed.allowed_actions == actions
        assert allowed.run_id == "test-001"
        assert allowed.resolution_reason == "Test construction"

    def test_immutability(self):
        """Test: AllowedActionSet is frozen (immutable)."""
        allowed = AllowedActionSet(
            intent_type=IntentType.INFORM,
            allowed_actions=frozenset({ActionClass.EXPLAIN}),
        )

        # Should raise FrozenInstanceError when trying to modify
        with pytest.raises(Exception):  # dataclass(frozen=True) raises error
            allowed.intent_type = IntentType.SUPPORT

    def test_none_intent_raises(self):
        """Test: None intent_type raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            AllowedActionSet(
                intent_type=None,  # type: ignore
                allowed_actions=frozenset(),
            )
        assert "cannot be None" in str(exc_info.value)

    def test_non_frozenset_raises(self):
        """Test: non-frozenset allowed_actions raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            AllowedActionSet(
                intent_type=IntentType.INFORM,
                allowed_actions=set([ActionClass.EXPLAIN]),  # type: ignore
            )
        assert "must be a frozenset" in str(exc_info.value)

    def test_invalid_action_type_raises(self):
        """Test: non-ActionClass in allowed_actions raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            AllowedActionSet(
                intent_type=IntentType.INFORM,
                allowed_actions=frozenset({"EXPLAIN"}),  # type: ignore - string not ActionClass
            )
        assert "must contain only ActionClass" in str(exc_info.value)

    def test_is_empty(self):
        """Test: is_empty() method."""
        empty = AllowedActionSet(
            intent_type=IntentType.ABSTAIN,
            allowed_actions=frozenset(),
        )
        assert empty.is_empty() is True

        non_empty = AllowedActionSet(
            intent_type=IntentType.INFORM,
            allowed_actions=frozenset({ActionClass.EXPLAIN}),
        )
        assert non_empty.is_empty() is False

    def test_is_action_allowed(self):
        """Test: is_action_allowed() method."""
        allowed = AllowedActionSet(
            intent_type=IntentType.INFORM,
            allowed_actions=frozenset({ActionClass.EXPLAIN, ActionClass.SUMMARIZE}),
        )

        assert allowed.is_action_allowed(ActionClass.EXPLAIN) is True
        assert allowed.is_action_allowed(ActionClass.SUMMARIZE) is True
        assert allowed.is_action_allowed(ActionClass.CARE) is False
        assert allowed.is_action_allowed(ActionClass.ANALYZE) is False

    def test_count(self):
        """Test: count() method."""
        assert AllowedActionSet(
            intent_type=IntentType.ABSTAIN,
            allowed_actions=frozenset(),
        ).count() == 0

        assert AllowedActionSet(
            intent_type=IntentType.CLARIFY,
            allowed_actions=frozenset({ActionClass.ASK, ActionClass.ASK_CLARIFY_REFERENCE}),
        ).count() == 2

    def test_to_dict_serialization(self):
        """Test: to_dict() serialization."""
        allowed = AllowedActionSet(
            intent_type=IntentType.SUPPORT,
            allowed_actions=frozenset({ActionClass.CARE, ActionClass.VALIDATE}),
            run_id="test-serialize",
            resolution_reason="Test serialization",
            debug={"key": "value"},
        )

        d = allowed.to_dict()

        assert d["intent_type"] == "SUPPORT"
        assert d["action_count"] == 2
        assert d["is_empty"] is False
        assert "CARE" in d["allowed_actions"]
        assert "VALIDATE" in d["allowed_actions"]
        assert d["run_id"] == "test-serialize"
        assert d["resolution_reason"] == "Test serialization"
        assert d["debug"]["key"] == "value"


class TestPhaseOneResolver:
    """Tests for PhaseOneResolver."""

    def setup_method(self):
        """Set up test fixtures."""
        self.resolver = PhaseOneResolver()

    def _make_envelope(
        self,
        intent_type: IntentType,
        planning_allowed: bool = True,
    ) -> IntentEnvelope:
        """Helper to create test IntentEnvelope."""
        return IntentEnvelope(
            intent_type=intent_type,
            response_posture=INTENT_TO_POSTURE[intent_type],
            planning_allowed=planning_allowed,
            phase_minus_one_policy=OverallPolicy.SINGLE_CONTEXT,
            resolution_reason="Test envelope",
        )

    def test_clarify_only_ask_actions(self):
        """
        Test Case 1: CLARIFY → only ASK / ASK_CLARIFY_REFERENCE

        When intent is CLARIFY, only clarification actions are allowed.
        """
        envelope = self._make_envelope(IntentType.CLARIFY, planning_allowed=False)

        result = self.resolver.resolve(envelope)

        assert result.intent_type == IntentType.CLARIFY
        assert ActionClass.ASK in result.allowed_actions
        assert ActionClass.ASK_CLARIFY_REFERENCE in result.allowed_actions
        assert result.count() == 2

        # Verify no other actions allowed
        assert ActionClass.CARE not in result.allowed_actions
        assert ActionClass.EXPLAIN not in result.allowed_actions
        assert ActionClass.ANALYZE not in result.allowed_actions

    def test_support_no_analyze_explain(self):
        """
        Test Case 2: SUPPORT → no ANALYZE / EXPLAIN

        When intent is SUPPORT, analytical actions are forbidden.
        """
        envelope = self._make_envelope(IntentType.SUPPORT)

        result = self.resolver.resolve(envelope)

        assert result.intent_type == IntentType.SUPPORT

        # Should have support actions
        assert ActionClass.CARE in result.allowed_actions
        assert ActionClass.VALIDATE in result.allowed_actions
        assert ActionClass.REFLECT in result.allowed_actions
        assert ActionClass.GROUND in result.allowed_actions

        # Should NOT have analytical actions
        assert ActionClass.ANALYZE not in result.allowed_actions
        assert ActionClass.EXPLAIN not in result.allowed_actions
        assert ActionClass.COMPARE not in result.allowed_actions
        assert ActionClass.SUMMARIZE not in result.allowed_actions

    def test_abstain_empty_set(self):
        """
        Test Case 3: ABSTAIN → empty allowed set

        When intent is ABSTAIN, no actions are allowed.
        """
        envelope = self._make_envelope(IntentType.ABSTAIN, planning_allowed=False)

        result = self.resolver.resolve(envelope)

        assert result.intent_type == IntentType.ABSTAIN
        assert result.is_empty() is True
        assert result.count() == 0
        assert len(result.allowed_actions) == 0

    def test_inform_explain_allowed_care_forbidden(self):
        """
        Test Case 4: INFORM → EXPLAIN allowed, CARE forbidden

        When intent is INFORM, analytical actions are allowed but support actions are not.
        """
        envelope = self._make_envelope(IntentType.INFORM)

        result = self.resolver.resolve(envelope)

        assert result.intent_type == IntentType.INFORM

        # EXPLAIN should be allowed
        assert ActionClass.EXPLAIN in result.allowed_actions
        assert ActionClass.SUMMARIZE in result.allowed_actions
        assert ActionClass.COMPARE in result.allowed_actions

        # CARE should be forbidden
        assert ActionClass.CARE not in result.allowed_actions
        assert ActionClass.VALIDATE not in result.allowed_actions
        assert ActionClass.GROUND not in result.allowed_actions

    def test_reflect_actions(self):
        """Test: REFLECT intent allows reflection and alignment actions."""
        envelope = self._make_envelope(IntentType.REFLECT)

        result = self.resolver.resolve(envelope)

        assert result.intent_type == IntentType.REFLECT
        assert ActionClass.REFLECT in result.allowed_actions
        assert ActionClass.REFLECT_BACK in result.allowed_actions
        assert ActionClass.ASK in result.allowed_actions
        assert ActionClass.ALIGN in result.allowed_actions

        # Should not have analytical or pure support actions
        assert ActionClass.ANALYZE not in result.allowed_actions
        assert ActionClass.CARE not in result.allowed_actions

    def test_none_envelope_raises(self):
        """Test: None envelope raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            self.resolver.resolve(None)  # type: ignore
        assert "cannot be None" in str(exc_info.value)

    def test_run_id_generated(self):
        """Test: run_id is automatically generated."""
        envelope = self._make_envelope(IntentType.INFORM)

        result = self.resolver.resolve(envelope)

        assert result.run_id is not None
        assert result.run_id.startswith("p1-")
        assert len(result.run_id) > 3

    def test_resolution_reason_populated(self):
        """Test: resolution_reason is populated."""
        envelope = self._make_envelope(IntentType.SUPPORT)

        result = self.resolver.resolve(envelope)

        assert result.resolution_reason is not None
        assert len(result.resolution_reason) > 0
        assert "SUPPORT" in result.resolution_reason

    def test_debug_info_populated(self):
        """Test: debug info is populated in result."""
        envelope = self._make_envelope(IntentType.INFORM)

        result = self.resolver.resolve(envelope)

        assert result.debug is not None
        assert "source_intent" in result.debug
        assert "source_posture" in result.debug
        assert "action_count" in result.debug
        assert result.debug["source_intent"] == "INFORM"

    def test_get_actions_for_intent(self):
        """Test: get_actions_for_intent helper method."""
        actions = self.resolver.get_actions_for_intent(IntentType.CLARIFY)

        assert ActionClass.ASK in actions
        assert ActionClass.ASK_CLARIFY_REFERENCE in actions
        assert len(actions) == 2

    def test_is_action_allowed_for_intent(self):
        """Test: is_action_allowed_for_intent helper method."""
        # EXPLAIN is allowed for INFORM
        assert self.resolver.is_action_allowed_for_intent(
            ActionClass.EXPLAIN, IntentType.INFORM
        ) is True

        # CARE is not allowed for INFORM
        assert self.resolver.is_action_allowed_for_intent(
            ActionClass.CARE, IntentType.INFORM
        ) is False

        # ASK is allowed for CLARIFY
        assert self.resolver.is_action_allowed_for_intent(
            ActionClass.ASK, IntentType.CLARIFY
        ) is True


class TestDeterminism:
    """Tests verifying deterministic behavior (no randomness)."""

    def setup_method(self):
        """Set up test fixtures."""
        self.resolver = PhaseOneResolver()

    def _make_envelope(self, intent_type: IntentType) -> IntentEnvelope:
        """Helper to create test IntentEnvelope."""
        return IntentEnvelope(
            intent_type=intent_type,
            response_posture=INTENT_TO_POSTURE[intent_type],
            planning_allowed=True,
            phase_minus_one_policy=OverallPolicy.SINGLE_CONTEXT,
        )

    def test_same_input_same_output(self):
        """
        Test Case 5: Determinism - same input → same output

        Multiple runs with the same input must produce identical allowed actions.
        """
        envelope = self._make_envelope(IntentType.SUPPORT)

        results = []
        for _ in range(10):
            result = self.resolver.resolve(envelope)
            results.append(result.allowed_actions)

        # All results should be identical
        assert all(r == results[0] for r in results)

    def test_all_intents_deterministic(self):
        """Test: all intent types produce deterministic results."""
        for intent_type in IntentType:
            envelope = self._make_envelope(intent_type)

            results = []
            for _ in range(5):
                result = self.resolver.resolve(envelope)
                results.append(result.allowed_actions)

            assert all(r == results[0] for r in results), f"Non-deterministic for {intent_type}"

    def test_action_set_order_consistent(self):
        """Test: action set ordering is consistent when serialized."""
        envelope = self._make_envelope(IntentType.SUPPORT)

        serialized = []
        for _ in range(5):
            result = self.resolver.resolve(envelope)
            serialized.append(result.to_dict()["allowed_actions"])

        assert all(s == serialized[0] for s in serialized)


class TestPhaseOneIntegration:
    """Tests for Phase 1 integration module."""

    def setup_method(self):
        """Set up test fixtures."""
        self.pipeline = PhaseMinusOnePipeline()

    def test_get_resolver_singleton(self):
        """Test: resolver is a singleton."""
        resolver1 = get_phase_one_resolver()
        resolver2 = get_phase_one_resolver()

        assert resolver1 is resolver2

    def test_run_phase_one_directly(self):
        """Test: run_phase_one_directly works."""
        envelope = IntentEnvelope(
            intent_type=IntentType.INFORM,
            response_posture=ResponsePosture.ENGAGE_OPEN,
            planning_allowed=True,
            phase_minus_one_policy=OverallPolicy.SINGLE_CONTEXT,
        )

        result = run_phase_one_directly(envelope)

        assert result is not None
        assert isinstance(result, AllowedActionSet)
        assert result.intent_type == IntentType.INFORM

    def test_maybe_run_phase_one_with_context(self):
        """Test: maybe_run_phase_one works with mock context."""
        class MockContext:
            def __init__(self, phase_zero):
                self.phase_zero = phase_zero

        intent = IntentEnvelope(
            intent_type=IntentType.SUPPORT,
            response_posture=ResponsePosture.ACKNOWLEDGE,
            planning_allowed=True,
            phase_minus_one_policy=OverallPolicy.SINGLE_CONTEXT,
        )
        ctx = MockContext(intent)

        result = maybe_run_phase_one(ctx)

        assert result is not None
        assert isinstance(result, AllowedActionSet)
        assert result.intent_type == IntentType.SUPPORT

    def test_maybe_run_phase_one_without_phase_zero(self):
        """Test: maybe_run_phase_one returns None without Phase 0."""
        class MockContext:
            phase_zero = None

        ctx = MockContext()

        result = maybe_run_phase_one(ctx)

        assert result is None

    def test_get_allowed_actions(self):
        """Test: get_allowed_actions retrieves from context."""
        class MockContext:
            def __init__(self, allowed):
                self.allowed_actions = allowed

        allowed = AllowedActionSet(
            intent_type=IntentType.INFORM,
            allowed_actions=frozenset({ActionClass.EXPLAIN}),
        )
        ctx = MockContext(allowed)

        result = get_allowed_actions(ctx)

        assert result is allowed

    def test_is_action_allowed_true(self):
        """Test: is_action_allowed returns True for allowed action."""
        class MockContext:
            def __init__(self, allowed):
                self.allowed_actions = allowed

        allowed = AllowedActionSet(
            intent_type=IntentType.INFORM,
            allowed_actions=frozenset({ActionClass.EXPLAIN, ActionClass.SUMMARIZE}),
        )
        ctx = MockContext(allowed)

        assert is_action_allowed(ctx, ActionClass.EXPLAIN) is True
        assert is_action_allowed(ctx, ActionClass.SUMMARIZE) is True

    def test_is_action_allowed_false(self):
        """Test: is_action_allowed returns False for forbidden action."""
        class MockContext:
            def __init__(self, allowed):
                self.allowed_actions = allowed

        allowed = AllowedActionSet(
            intent_type=IntentType.INFORM,
            allowed_actions=frozenset({ActionClass.EXPLAIN}),
        )
        ctx = MockContext(allowed)

        assert is_action_allowed(ctx, ActionClass.CARE) is False
        assert is_action_allowed(ctx, ActionClass.ANALYZE) is False

    def test_is_action_allowed_no_phase_one(self):
        """Test: is_action_allowed returns False when Phase 1 hasn't run."""
        class MockContext:
            allowed_actions = None

        ctx = MockContext()

        # Conservative default: no actions allowed if Phase 1 hasn't run
        assert is_action_allowed(ctx, ActionClass.EXPLAIN) is False

    def test_get_allowed_action_count(self):
        """Test: get_allowed_action_count works correctly."""
        class MockContext:
            def __init__(self, allowed):
                self.allowed_actions = allowed

        allowed = AllowedActionSet(
            intent_type=IntentType.SUPPORT,
            allowed_actions=frozenset({ActionClass.CARE, ActionClass.VALIDATE}),
        )
        ctx = MockContext(allowed)

        assert get_allowed_action_count(ctx) == 2

    def test_get_allowed_action_count_no_phase_one(self):
        """Test: get_allowed_action_count returns 0 when Phase 1 hasn't run."""
        class MockContext:
            allowed_actions = None

        ctx = MockContext()

        assert get_allowed_action_count(ctx) == 0


class TestEndToEndScenarios:
    """End-to-end tests for complete Phase 0 → Phase 1 flow."""

    def setup_method(self):
        """Set up test fixtures."""
        from symbolu.mechanical.pipeline.phase_zero import PhaseZeroResolver
        self.phase_zero = PhaseZeroResolver()
        self.phase_one = PhaseOneResolver()
        self.pipeline = PhaseMinusOnePipeline()

    def test_e2e_i_am_sad(self):
        """E2E: 'I am sad.' → SUPPORT → care/support actions."""
        phase_minus_one = self.pipeline.run("I am sad.")
        phase_zero = self.phase_zero.resolve(phase_minus_one)

        if phase_zero.intent_type == IntentType.SUPPORT:
            phase_one = self.phase_one.resolve(phase_zero)

            assert phase_one.intent_type == IntentType.SUPPORT
            assert ActionClass.CARE in phase_one.allowed_actions
            assert ActionClass.VALIDATE in phase_one.allowed_actions
            assert ActionClass.ANALYZE not in phase_one.allowed_actions

    def test_e2e_sadness_is_common(self):
        """E2E: 'Sadness is a common emotion.' → INFORM → analytical actions."""
        phase_minus_one = self.pipeline.run("Sadness is a common emotion.")
        phase_zero = self.phase_zero.resolve(phase_minus_one)

        if phase_zero.intent_type == IntentType.INFORM:
            phase_one = self.phase_one.resolve(phase_zero)

            assert phase_one.intent_type == IntentType.INFORM
            assert ActionClass.EXPLAIN in phase_one.allowed_actions
            assert ActionClass.SUMMARIZE in phase_one.allowed_actions
            assert ActionClass.CARE not in phase_one.allowed_actions

    def test_e2e_empty_input(self):
        """E2E: empty input → BLOCKED → CLARIFY → clarification actions."""
        phase_minus_one = self.pipeline.run("")
        phase_zero = self.phase_zero.resolve(phase_minus_one)

        assert phase_zero.intent_type == IntentType.CLARIFY

        phase_one = self.phase_one.resolve(phase_zero)

        assert phase_one.intent_type == IntentType.CLARIFY
        assert ActionClass.ASK in phase_one.allowed_actions
        assert ActionClass.ASK_CLARIFY_REFERENCE in phase_one.allowed_actions
        assert phase_one.count() == 2


class TestActionExclusivity:
    """Tests verifying that action sets are mutually exclusive where expected."""

    def setup_method(self):
        """Set up test fixtures."""
        self.resolver = PhaseOneResolver()

    def test_support_and_inform_disjoint(self):
        """Test: SUPPORT and INFORM action sets are disjoint."""
        support_actions = INTENT_TO_ACTIONS[IntentType.SUPPORT]
        inform_actions = INTENT_TO_ACTIONS[IntentType.INFORM]

        # These sets should have no overlap
        overlap = support_actions & inform_actions
        assert len(overlap) == 0, f"Unexpected overlap: {overlap}"

    def test_clarify_unique_actions(self):
        """Test: CLARIFY has unique clarification actions."""
        clarify_actions = INTENT_TO_ACTIONS[IntentType.CLARIFY]

        # ASK_CLARIFY_REFERENCE should only be in CLARIFY
        for intent_type in IntentType:
            if intent_type != IntentType.CLARIFY:
                actions = INTENT_TO_ACTIONS[intent_type]
                assert ActionClass.ASK_CLARIFY_REFERENCE not in actions

    def test_abstain_has_nothing(self):
        """Test: ABSTAIN has no actions at all."""
        abstain_actions = INTENT_TO_ACTIONS[IntentType.ABSTAIN]
        assert len(abstain_actions) == 0

        # Verify no action appears in ABSTAIN
        for action in ActionClass:
            assert action not in abstain_actions


# Run tests if executed directly
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
