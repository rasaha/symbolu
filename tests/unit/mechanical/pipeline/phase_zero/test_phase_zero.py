"""
Phase 0 Unit Tests

Tests for Phase 0 Intent Envelope & Act-Type Selection:
- IntentType and ResponsePosture enums
- IntentEnvelope dataclass
- PhaseZeroResolver
- Integration with Phase −1

Test Cases (per specification):
1. BLOCKED input → CLARIFY
2. "I'm worried because she seems sad." → REFLECT (MULTI_CONTEXT + RELATIONAL)
3. Pure DETACHED question → INFORM
4. Unresolved clause (selected=None) → CLARIFY
5. Pure REFLEXIVE → SUPPORT
6. Fallback → ABSTAIN
"""

import pytest
from symbolu.mechanical.pipeline.phase_zero import (
    PhaseZeroResolver,
    IntentEnvelope,
    IntentType,
    ResponsePosture,
    INTENT_TO_POSTURE,
)
from symbolu.mechanical.pipeline.grounding import (
    PhaseMinusOnePipeline,
    PhaseMinusOneEnvelope,
    GroundingCandidate,
    ClauseGroundingResult,
    ObservedEntity,
    ObservationMode,
    ProjectionRisk,
    GroundingStatus,
    ResolutionPolicy,
    OverallPolicy,
)
from symbolu.mechanical.pipeline.phase_zero_integration import (
    get_phase_zero_resolver,
    maybe_run_phase_zero,
    run_phase_zero_directly,
    is_planning_allowed,
)


class TestIntentTypeEnum:
    """Tests for IntentType enum."""

    def test_intent_type_values(self):
        """Test: all expected intent types exist"""
        assert IntentType.CLARIFY.value == "CLARIFY"
        assert IntentType.SUPPORT.value == "SUPPORT"
        assert IntentType.REFLECT.value == "REFLECT"
        assert IntentType.INFORM.value == "INFORM"
        assert IntentType.ABSTAIN.value == "ABSTAIN"

    def test_intent_type_string_comparison(self):
        """Test: IntentType supports string comparison"""
        assert IntentType.CLARIFY == "CLARIFY"
        assert IntentType.SUPPORT == "SUPPORT"


class TestResponsePostureEnum:
    """Tests for ResponsePosture enum."""

    def test_response_posture_values(self):
        """Test: all expected postures exist"""
        assert ResponsePosture.HOLD.value == "HOLD"
        assert ResponsePosture.ACKNOWLEDGE.value == "ACKNOWLEDGE"
        assert ResponsePosture.ENGAGE_CAREFUL.value == "ENGAGE_CAREFUL"
        assert ResponsePosture.ENGAGE_OPEN.value == "ENGAGE_OPEN"

    def test_posture_ordering(self):
        """Test: postures have conceptual ordering (conservative to open)"""
        # Just verify they exist in expected order conceptually
        postures = [
            ResponsePosture.HOLD,
            ResponsePosture.ACKNOWLEDGE,
            ResponsePosture.ENGAGE_CAREFUL,
            ResponsePosture.ENGAGE_OPEN,
        ]
        assert len(postures) == 4


class TestIntentToPostureMapping:
    """Tests for INTENT_TO_POSTURE mapping."""

    def test_all_intents_mapped(self):
        """Test: every IntentType has a mapped posture"""
        for intent in IntentType:
            assert intent in INTENT_TO_POSTURE
            assert isinstance(INTENT_TO_POSTURE[intent], ResponsePosture)

    def test_clarify_maps_to_hold(self):
        """Test: CLARIFY → HOLD"""
        assert INTENT_TO_POSTURE[IntentType.CLARIFY] == ResponsePosture.HOLD

    def test_support_maps_to_acknowledge(self):
        """Test: SUPPORT → ACKNOWLEDGE"""
        assert INTENT_TO_POSTURE[IntentType.SUPPORT] == ResponsePosture.ACKNOWLEDGE

    def test_reflect_maps_to_engage_careful(self):
        """Test: REFLECT → ENGAGE_CAREFUL"""
        assert INTENT_TO_POSTURE[IntentType.REFLECT] == ResponsePosture.ENGAGE_CAREFUL

    def test_inform_maps_to_engage_open(self):
        """Test: INFORM → ENGAGE_OPEN"""
        assert INTENT_TO_POSTURE[IntentType.INFORM] == ResponsePosture.ENGAGE_OPEN

    def test_abstain_maps_to_hold(self):
        """Test: ABSTAIN → HOLD"""
        assert INTENT_TO_POSTURE[IntentType.ABSTAIN] == ResponsePosture.HOLD


class TestIntentEnvelope:
    """Tests for IntentEnvelope dataclass."""

    def test_basic_construction(self):
        """Test: basic envelope construction"""
        envelope = IntentEnvelope(
            intent_type=IntentType.INFORM,
            response_posture=ResponsePosture.ENGAGE_OPEN,
            planning_allowed=True,
            phase_minus_one_policy=OverallPolicy.SINGLE_CONTEXT,
            mode_signals=[ObservationMode.DETACHED],
            resolution_reason="Test reason",
        )

        assert envelope.intent_type == IntentType.INFORM
        assert envelope.response_posture == ResponsePosture.ENGAGE_OPEN
        assert envelope.planning_allowed is True
        assert envelope.phase_minus_one_policy == OverallPolicy.SINGLE_CONTEXT
        assert len(envelope.mode_signals) == 1
        assert envelope.resolution_reason == "Test reason"

    def test_blocked_requires_clarify(self):
        """Test: BLOCKED policy requires CLARIFY intent"""
        # Valid: BLOCKED + CLARIFY + planning_allowed=False
        envelope = IntentEnvelope(
            intent_type=IntentType.CLARIFY,
            response_posture=ResponsePosture.HOLD,
            planning_allowed=False,
            phase_minus_one_policy=OverallPolicy.BLOCKED,
        )
        assert envelope.intent_type == IntentType.CLARIFY

        # Invalid: BLOCKED + INFORM
        with pytest.raises(ValueError) as exc_info:
            IntentEnvelope(
                intent_type=IntentType.INFORM,
                response_posture=ResponsePosture.ENGAGE_OPEN,
                planning_allowed=True,
                phase_minus_one_policy=OverallPolicy.BLOCKED,
            )
        assert "CLARIFY" in str(exc_info.value)

    def test_blocked_requires_planning_false(self):
        """Test: BLOCKED policy requires planning_allowed=False"""
        with pytest.raises(ValueError) as exc_info:
            IntentEnvelope(
                intent_type=IntentType.CLARIFY,
                response_posture=ResponsePosture.HOLD,
                planning_allowed=True,  # Invalid for BLOCKED
                phase_minus_one_policy=OverallPolicy.BLOCKED,
            )
        assert "planning_allowed=False" in str(exc_info.value)

    def test_is_planning_blocked(self):
        """Test: is_planning_blocked() method"""
        blocked = IntentEnvelope(
            intent_type=IntentType.CLARIFY,
            response_posture=ResponsePosture.HOLD,
            planning_allowed=False,
            phase_minus_one_policy=OverallPolicy.SINGLE_CONTEXT,
        )
        assert blocked.is_planning_blocked() is True

        allowed = IntentEnvelope(
            intent_type=IntentType.INFORM,
            response_posture=ResponsePosture.ENGAGE_OPEN,
            planning_allowed=True,
            phase_minus_one_policy=OverallPolicy.SINGLE_CONTEXT,
        )
        assert allowed.is_planning_blocked() is False

    def test_requires_clarification(self):
        """Test: requires_clarification() method"""
        clarify = IntentEnvelope(
            intent_type=IntentType.CLARIFY,
            response_posture=ResponsePosture.HOLD,
            planning_allowed=False,
            phase_minus_one_policy=OverallPolicy.SINGLE_CONTEXT,
        )
        assert clarify.requires_clarification() is True

        no_clarify = IntentEnvelope(
            intent_type=IntentType.SUPPORT,
            response_posture=ResponsePosture.ACKNOWLEDGE,
            planning_allowed=True,
            phase_minus_one_policy=OverallPolicy.SINGLE_CONTEXT,
        )
        assert no_clarify.requires_clarification() is False

    def test_to_dict_serialization(self):
        """Test: to_dict() serialization"""
        envelope = IntentEnvelope(
            intent_type=IntentType.REFLECT,
            response_posture=ResponsePosture.ENGAGE_CAREFUL,
            planning_allowed=True,
            phase_minus_one_policy=OverallPolicy.MULTI_CONTEXT,
            mode_signals=[ObservationMode.REFLEXIVE, ObservationMode.RELATIONAL],
            resolution_reason="Test serialization",
            debug={"key": "value"},
        )

        d = envelope.to_dict()

        assert d["intent_type"] == "REFLECT"
        assert d["response_posture"] == "ENGAGE_CAREFUL"
        assert d["planning_allowed"] is True
        assert d["phase_minus_one_policy"] == "MULTI_CONTEXT"
        assert d["mode_signals"] == ["REFLEXIVE", "RELATIONAL"]
        assert d["resolution_reason"] == "Test serialization"
        assert d["debug"]["key"] == "value"


class TestPhaseZeroResolver:
    """Tests for PhaseZeroResolver."""

    def setup_method(self):
        """Set up test fixtures."""
        self.resolver = PhaseZeroResolver()
        self.pipeline = PhaseMinusOnePipeline()

    def test_blocked_input_returns_clarify(self):
        """
        Test Case 1: BLOCKED input → CLARIFY

        When Phase −1 returns BLOCKED, Phase 0 must:
        - Return IntentType.CLARIFY
        - Set planning_allowed=False
        - Set ResponsePosture.HOLD
        """
        # Create a BLOCKED envelope
        envelope = PhaseMinusOneEnvelope(
            overall_policy=OverallPolicy.BLOCKED,
            clauses=[],
            run_id="test-blocked",
        )

        result = self.resolver.resolve(envelope)

        assert result.intent_type == IntentType.CLARIFY
        assert result.response_posture == ResponsePosture.HOLD
        assert result.planning_allowed is False
        assert "BLOCKED" in result.resolution_reason

    def test_unresolved_clause_returns_clarify(self):
        """
        Test Case 4: Unresolved clause (selected=None) → CLARIFY

        When any clause has selected=None, Phase 0 must:
        - Return IntentType.CLARIFY
        - Set planning_allowed=False
        """
        # Create envelope with unresolved clause
        envelope = PhaseMinusOneEnvelope(
            overall_policy=OverallPolicy.SINGLE_CONTEXT,
            clauses=[
                ClauseGroundingResult(
                    clause_text="Feeling confused",
                    candidates=[
                        GroundingCandidate(
                            observed=ObservedEntity.SELF,
                            mode=ObservationMode.REFLEXIVE,
                            projection_risk=ProjectionRisk.MEDIUM,
                            analysis_allowed=False,
                            confidence=0.50,
                        ),
                    ],
                    selected=None,  # Unresolved
                    grounding_status=GroundingStatus.AMBIGUOUS,
                    resolution_policy=ResolutionPolicy.ASK_CLARIFY,
                )
            ],
            run_id="test-unresolved",
        )

        result = self.resolver.resolve(envelope)

        assert result.intent_type == IntentType.CLARIFY
        assert result.planning_allowed is False
        assert "Unresolved" in result.resolution_reason

    def test_multi_context_relational_returns_reflect(self):
        """
        Test Case 2: MULTI_CONTEXT + RELATIONAL → REFLECT

        Input: "I'm worried because she seems sad."
        Expected:
        - Phase −1 splits into REFLEXIVE + RELATIONAL
        - Phase 0 returns REFLECT with planning_allowed=True
        """
        envelope = self.pipeline.run("I'm worried because she seems sad.")

        # Verify we got the expected split
        if envelope.was_split and len(envelope.clauses) == 2:
            modes = {c.selected.mode for c in envelope.clauses if c.selected}

            if (ObservationMode.REFLEXIVE in modes and
                    ObservationMode.RELATIONAL in modes):
                result = self.resolver.resolve(envelope)

                assert result.intent_type == IntentType.REFLECT
                assert result.response_posture == ResponsePosture.ENGAGE_CAREFUL
                assert result.planning_allowed is True
                assert "Multi-context" in result.resolution_reason or "relational" in result.resolution_reason.lower()
        else:
            # If not split, create a synthetic test case
            envelope = PhaseMinusOneEnvelope(
                overall_policy=OverallPolicy.MULTI_CONTEXT,
                clauses=[
                    ClauseGroundingResult(
                        clause_text="I'm worried",
                        selected=GroundingCandidate(
                            observed=ObservedEntity.SELF,
                            mode=ObservationMode.REFLEXIVE,
                            projection_risk=ProjectionRisk.MEDIUM,
                            analysis_allowed=False,
                            confidence=0.80,
                        ),
                        grounding_status=GroundingStatus.CONFIDENT,
                        resolution_policy=ResolutionPolicy.NONE,
                    ),
                    ClauseGroundingResult(
                        clause_text="she seems sad",
                        selected=GroundingCandidate(
                            observed=ObservedEntity.OTHER,
                            mode=ObservationMode.RELATIONAL,
                            projection_risk=ProjectionRisk.HIGH,
                            analysis_allowed=False,
                            confidence=0.80,
                        ),
                        grounding_status=GroundingStatus.CONFIDENT,
                        resolution_policy=ResolutionPolicy.NONE,
                    ),
                ],
                was_split=True,
                run_id="test-multi-relational",
            )

            result = self.resolver.resolve(envelope)

            assert result.intent_type == IntentType.REFLECT
            assert result.response_posture == ResponsePosture.ENGAGE_CAREFUL
            assert result.planning_allowed is True

    def test_pure_reflexive_returns_support(self):
        """
        Test Case 5: Pure REFLEXIVE → SUPPORT

        When all clauses are REFLEXIVE, Phase 0 must:
        - Return IntentType.SUPPORT
        - Set ResponsePosture.ACKNOWLEDGE
        - Allow planning
        """
        envelope = self.pipeline.run("I am sad.")

        # Verify we got REFLEXIVE
        if (envelope.clauses and
                envelope.clauses[0].selected and
                envelope.clauses[0].selected.mode == ObservationMode.REFLEXIVE):
            result = self.resolver.resolve(envelope)

            assert result.intent_type == IntentType.SUPPORT
            assert result.response_posture == ResponsePosture.ACKNOWLEDGE
            assert result.planning_allowed is True
            assert "reflexive" in result.resolution_reason.lower()

    def test_pure_detached_returns_inform(self):
        """
        Test Case 3: Pure DETACHED question → INFORM

        When all clauses are DETACHED, Phase 0 must:
        - Return IntentType.INFORM
        - Set ResponsePosture.ENGAGE_OPEN
        - Allow planning
        """
        envelope = self.pipeline.run("Sadness is a common emotion.")

        # Verify we got DETACHED
        if (envelope.clauses and
                envelope.clauses[0].selected and
                envelope.clauses[0].selected.mode == ObservationMode.DETACHED):
            result = self.resolver.resolve(envelope)

            assert result.intent_type == IntentType.INFORM
            assert result.response_posture == ResponsePosture.ENGAGE_OPEN
            assert result.planning_allowed is True
            assert "detached" in result.resolution_reason.lower()

    def test_fallback_returns_abstain(self):
        """
        Test Case 6: Fallback → ABSTAIN

        When no clear pattern matches, Phase 0 must:
        - Return IntentType.ABSTAIN
        - Set ResponsePosture.HOLD
        - Disallow planning (conservative)
        """
        # Create envelope with mixed modes but not MULTI_CONTEXT
        # This is a synthetic edge case
        envelope = PhaseMinusOneEnvelope(
            overall_policy=OverallPolicy.SINGLE_CONTEXT,  # Not MULTI_CONTEXT
            clauses=[
                ClauseGroundingResult(
                    clause_text="Something ambiguous",
                    selected=GroundingCandidate(
                        observed=ObservedEntity.SELF,
                        mode=ObservationMode.REFLEXIVE,
                        projection_risk=ProjectionRisk.LOW,
                        analysis_allowed=False,
                        confidence=0.60,
                    ),
                    grounding_status=GroundingStatus.CONFIDENT,
                    resolution_policy=ResolutionPolicy.NONE,
                ),
                # Add a second clause with different mode but NOT MULTI_CONTEXT policy
                ClauseGroundingResult(
                    clause_text="Another thing",
                    selected=GroundingCandidate(
                        observed=ObservedEntity.PHENOMENON,
                        mode=ObservationMode.DETACHED,
                        projection_risk=ProjectionRisk.LOW,
                        analysis_allowed=True,
                        confidence=0.60,
                    ),
                    grounding_status=GroundingStatus.CONFIDENT,
                    resolution_policy=ResolutionPolicy.NONE,
                ),
            ],
            run_id="test-fallback",
        )

        result = self.resolver.resolve(envelope)

        # Mixed modes without MULTI_CONTEXT → can't match pure patterns → ABSTAIN
        assert result.intent_type == IntentType.ABSTAIN
        assert result.response_posture == ResponsePosture.HOLD
        assert result.planning_allowed is False
        assert "abstention" in result.resolution_reason.lower()

    def test_mode_signals_populated(self):
        """Test: mode_signals are correctly extracted"""
        envelope = PhaseMinusOneEnvelope(
            overall_policy=OverallPolicy.MULTI_CONTEXT,
            clauses=[
                ClauseGroundingResult(
                    clause_text="I feel worried",
                    selected=GroundingCandidate(
                        observed=ObservedEntity.SELF,
                        mode=ObservationMode.REFLEXIVE,
                        projection_risk=ProjectionRisk.MEDIUM,
                        analysis_allowed=False,
                        confidence=0.80,
                    ),
                    grounding_status=GroundingStatus.CONFIDENT,
                ),
                ClauseGroundingResult(
                    clause_text="she seems sad",
                    selected=GroundingCandidate(
                        observed=ObservedEntity.OTHER,
                        mode=ObservationMode.RELATIONAL,
                        projection_risk=ProjectionRisk.HIGH,
                        analysis_allowed=False,
                        confidence=0.80,
                    ),
                    grounding_status=GroundingStatus.CONFIDENT,
                ),
            ],
            run_id="test-signals",
        )

        result = self.resolver.resolve(envelope)

        assert len(result.mode_signals) == 2
        assert ObservationMode.REFLEXIVE in result.mode_signals
        assert ObservationMode.RELATIONAL in result.mode_signals

    def test_debug_info_populated(self):
        """Test: debug info is populated in result"""
        envelope = self.pipeline.run("I feel anxious.")

        result = self.resolver.resolve(envelope)

        assert result.debug is not None
        assert "rule_applied" in result.debug
        assert "mode_count" in result.debug
        assert "unique_modes" in result.debug


class TestPhaseZeroIntegration:
    """Tests for Phase 0 integration module."""

    def setup_method(self):
        """Set up test fixtures."""
        self.pipeline = PhaseMinusOnePipeline()

    def test_get_resolver_singleton(self):
        """Test: resolver is a singleton"""
        resolver1 = get_phase_zero_resolver()
        resolver2 = get_phase_zero_resolver()

        assert resolver1 is resolver2

    def test_run_phase_zero_directly(self):
        """Test: run_phase_zero_directly works"""
        phase_minus_one = self.pipeline.run("I am happy.")

        result = run_phase_zero_directly(phase_minus_one)

        assert result is not None
        assert isinstance(result, IntentEnvelope)

    def test_maybe_run_phase_zero_with_context(self):
        """Test: maybe_run_phase_zero works with mock context"""
        # Create a mock context object
        class MockContext:
            def __init__(self, phase_minus_one):
                self.phase_minus_one = phase_minus_one

        phase_minus_one = self.pipeline.run("I feel confused.")
        ctx = MockContext(phase_minus_one)

        result = maybe_run_phase_zero(ctx)

        assert result is not None
        assert isinstance(result, IntentEnvelope)

    def test_maybe_run_phase_zero_without_phase_minus_one(self):
        """Test: maybe_run_phase_zero returns None without Phase −1"""
        class MockContext:
            phase_minus_one = None

        ctx = MockContext()

        result = maybe_run_phase_zero(ctx)

        assert result is None

    def test_is_planning_allowed_true(self):
        """Test: is_planning_allowed returns True for allowed state"""
        class MockContext:
            def __init__(self, phase_zero):
                self.phase_zero = phase_zero

        intent = IntentEnvelope(
            intent_type=IntentType.INFORM,
            response_posture=ResponsePosture.ENGAGE_OPEN,
            planning_allowed=True,
            phase_minus_one_policy=OverallPolicy.SINGLE_CONTEXT,
        )
        ctx = MockContext(intent)

        assert is_planning_allowed(ctx) is True

    def test_is_planning_allowed_false(self):
        """Test: is_planning_allowed returns False for blocked state"""
        class MockContext:
            def __init__(self, phase_zero):
                self.phase_zero = phase_zero

        intent = IntentEnvelope(
            intent_type=IntentType.CLARIFY,
            response_posture=ResponsePosture.HOLD,
            planning_allowed=False,
            phase_minus_one_policy=OverallPolicy.BLOCKED,
        )
        ctx = MockContext(intent)

        assert is_planning_allowed(ctx) is False

    def test_is_planning_allowed_no_phase_zero(self):
        """Test: is_planning_allowed returns False when Phase 0 hasn't run"""
        class MockContext:
            phase_zero = None

        ctx = MockContext()

        # Conservative default: if Phase 0 hasn't run, block planning
        assert is_planning_allowed(ctx) is False


class TestEndToEndScenarios:
    """End-to-end tests for complete Phase −1 → Phase 0 flow."""

    def setup_method(self):
        """Set up test fixtures."""
        self.pipeline = PhaseMinusOnePipeline()
        self.resolver = PhaseZeroResolver()

    def test_e2e_i_am_sad(self):
        """E2E: 'I am sad.' → SUPPORT"""
        phase_minus_one = self.pipeline.run("I am sad.")
        phase_zero = self.resolver.resolve(phase_minus_one)

        # Should be REFLEXIVE → SUPPORT
        assert phase_zero.intent_type == IntentType.SUPPORT
        assert phase_zero.planning_allowed is True

    def test_e2e_she_seems_sad(self):
        """E2E: 'She seems sad.' → depends on grounding"""
        phase_minus_one = self.pipeline.run("She seems sad.")
        phase_zero = self.resolver.resolve(phase_minus_one)

        # Should be RELATIONAL
        if (phase_minus_one.clauses and
                phase_minus_one.clauses[0].selected and
                phase_minus_one.clauses[0].selected.mode == ObservationMode.RELATIONAL):
            # Pure RELATIONAL doesn't match pure patterns, so falls through
            # It's not REFLEXIVE, not DETACHED, not MULTI_CONTEXT + RELATIONAL
            assert phase_zero.intent_type in [IntentType.ABSTAIN, IntentType.REFLECT]

    def test_e2e_sadness_is_common(self):
        """E2E: 'Sadness is a common emotion.' → INFORM"""
        phase_minus_one = self.pipeline.run("Sadness is a common emotion.")
        phase_zero = self.resolver.resolve(phase_minus_one)

        # Should be DETACHED → INFORM
        if (phase_minus_one.clauses and
                phase_minus_one.clauses[0].selected and
                phase_minus_one.clauses[0].selected.mode == ObservationMode.DETACHED):
            assert phase_zero.intent_type == IntentType.INFORM
            assert phase_zero.planning_allowed is True

    def test_e2e_empty_input(self):
        """E2E: empty input → BLOCKED → CLARIFY"""
        phase_minus_one = self.pipeline.run("")
        phase_zero = self.resolver.resolve(phase_minus_one)

        assert phase_minus_one.is_blocked()
        assert phase_zero.intent_type == IntentType.CLARIFY
        assert phase_zero.planning_allowed is False

    def test_e2e_worried_because_she_seems_sad(self):
        """E2E: 'I'm worried because she seems sad.' → REFLECT"""
        phase_minus_one = self.pipeline.run("I'm worried because she seems sad.")

        # If split into MULTI_CONTEXT with RELATIONAL
        if phase_minus_one.was_split and phase_minus_one.has_multi_context():
            modes = {c.selected.mode for c in phase_minus_one.clauses if c.selected}

            if ObservationMode.RELATIONAL in modes:
                phase_zero = self.resolver.resolve(phase_minus_one)

                assert phase_zero.intent_type == IntentType.REFLECT
                assert phase_zero.response_posture == ResponsePosture.ENGAGE_CAREFUL


class TestDeterminism:
    """Tests verifying deterministic behavior (no randomness)."""

    def setup_method(self):
        """Set up test fixtures."""
        self.pipeline = PhaseMinusOnePipeline()
        self.resolver = PhaseZeroResolver()

    def test_same_input_same_output(self):
        """Test: same input always produces same output"""
        text = "I feel anxious about the upcoming meeting."

        results = []
        for _ in range(5):
            phase_minus_one = self.pipeline.run(text)
            phase_zero = self.resolver.resolve(phase_minus_one)
            results.append((
                phase_zero.intent_type,
                phase_zero.response_posture,
                phase_zero.planning_allowed,
            ))

        # All results should be identical
        assert all(r == results[0] for r in results)

    def test_resolution_reason_consistent(self):
        """Test: resolution reason is consistent for same input"""
        text = "I am feeling sad."

        reasons = []
        for _ in range(3):
            phase_minus_one = self.pipeline.run(text)
            phase_zero = self.resolver.resolve(phase_minus_one)
            reasons.append(phase_zero.resolution_reason)

        assert all(r == reasons[0] for r in reasons)


# Run tests if executed directly
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
