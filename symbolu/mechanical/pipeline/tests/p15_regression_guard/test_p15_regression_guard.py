"""
P15 Regression Guard Test Suite — Comprehensive Tests

This test suite enforces the architectural invariant:
No phase ≥ 16 may modify, reinterpret, escalate, or override any decision
produced by PO1–P15.

REQUIRED TEST CATEGORIES (per specification):
1.  Intent override blocked
2.  Regime escalation blocked
3.  Discourse act mutation blocked
4.  Allowed-action expansion blocked
5.  BLOCKED → unblocked forbidden
6.  Prediction-based override forbidden
7.  Persona-based override forbidden
8.  Renderer metadata ignored
9.  Determinism: same input → same violations
10. Phase number < 16 → guard inactive

CRITICAL: All tests are DETERMINISTIC with ZERO false positives.
Tests FAIL LOUDLY on any violation of the regression guard contract.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, FrozenSet, List, Optional
import copy

import pytest

from symbolu.mechanical.pipeline.phase15_regression_guard import (
    # Schema
    P15AuthoritySnapshot,
    P15RegressionViolation,
    P15RegressionViolationError,
    ViolationType,
    # Guard
    P15RegressionGuard,
    # Integration
    capture_p15_snapshot,
    enforce_p15_regression_guard,
    get_p15_snapshot,
    has_p15_snapshot,
)
from symbolu.mechanical.pipeline.phase15_regression_guard.p15_integration import (
    capture_snapshot_directly,
    validate_directly,
    validate_p15_snapshot_without_raise,
)


# ============================================================================
# TEST MOCK HELPERS
# ============================================================================


@dataclass
class MockIntentType:
    """Mock intent type enum."""
    value: str


@dataclass
class MockResponsePosture:
    """Mock response posture enum."""
    value: str


@dataclass
class MockPhaseZero:
    """Mock PO2 (phase_zero) envelope for testing."""
    intent_type: MockIntentType
    response_posture: MockResponsePosture

    @classmethod
    def create(
        cls,
        intent: str = "INFORM",
        posture: str = "ENGAGE_OPEN",
    ) -> "MockPhaseZero":
        return cls(
            intent_type=MockIntentType(value=intent),
            response_posture=MockResponsePosture(value=posture),
        )


@dataclass
class MockRegime:
    """Mock operational regime enum."""
    value: str


@dataclass
class MockP6Regime:
    """Mock P6 regime envelope for testing."""
    regime: MockRegime

    @classmethod
    def create(cls, regime: str = "INFORM") -> "MockP6Regime":
        return cls(regime=MockRegime(value=regime))


@dataclass
class MockDiscourseAct:
    """Mock discourse act enum."""
    value: str


@dataclass
class MockP7Discourse:
    """Mock P7 discourse envelope for testing."""
    act: MockDiscourseAct

    @classmethod
    def create(cls, act: str = "EXPLANATION") -> "MockP7Discourse":
        return cls(act=MockDiscourseAct(value=act))


@dataclass(frozen=True)
class MockActionClass:
    """Mock action class enum."""
    value: str


@dataclass
class MockAllowedActions:
    """Mock PO3 allowed actions set for testing."""
    allowed_actions: FrozenSet[MockActionClass]

    @classmethod
    def create(cls, actions: List[str]) -> "MockAllowedActions":
        return cls(
            allowed_actions=frozenset(MockActionClass(value=a) for a in actions)
        )


@dataclass
class MockInteractionMode:
    """Mock interaction mode enum."""
    value: str


@dataclass
class MockInteractionDirective:
    """Mock P15 interaction directive for testing."""
    mode: MockInteractionMode
    blocked: bool

    @classmethod
    def create(
        cls,
        mode: str = "INFORMATIVE",
        blocked: bool = False,
    ) -> "MockInteractionDirective":
        return cls(
            mode=MockInteractionMode(value=mode),
            blocked=blocked,
        )


@dataclass
class MockOverallPolicy:
    """Mock overall policy enum."""
    value: str


@dataclass
class MockGroundingMode:
    """Mock grounding mode."""
    value: str


@dataclass
class MockPhaseMinusOne:
    """Mock PO1 (phase_minus_one) envelope for testing."""
    overall_policy: MockOverallPolicy
    dominant_mode: Optional[MockGroundingMode] = None

    @classmethod
    def create(
        cls,
        policy: str = "PERMITTED",
        mode: str = "DETACHED",
    ) -> "MockPhaseMinusOne":
        return cls(
            overall_policy=MockOverallPolicy(value=policy),
            dominant_mode=MockGroundingMode(value=mode),
        )


@dataclass
class MockPipelineContext:
    """
    Mock pipeline context for testing the P15 regression guard.

    Contains all fields that the guard needs to capture and validate.
    """
    # PO2 (phase_zero) - Intent and posture
    phase_zero: Optional[MockPhaseZero] = None

    # P6 - Regime
    p6_regime: Optional[MockP6Regime] = None

    # P7 - Discourse act
    p7_discourse_envelope: Optional[MockP7Discourse] = None

    # PO3 - Allowed actions
    allowed_actions: Optional[MockAllowedActions] = None

    # P15 - Interaction directive
    interaction_directive: Optional[MockInteractionDirective] = None

    # PO1 - Grounding
    phase_minus_one: Optional[MockPhaseMinusOne] = None

    # Potential authority reintroduction signals (should be None normally)
    authority_certainty: Optional[float] = None
    authority_explanation: Optional[str] = None
    prediction_override: Optional[bool] = None
    persona_authority_override: Optional[bool] = None
    grammar_authority_override: Optional[bool] = None

    # Snapshot storage (added by capture_p15_snapshot)
    _p15_authority_snapshot: Optional[P15AuthoritySnapshot] = None


# ============================================================================
# CONTEXT FACTORY FUNCTIONS
# ============================================================================


def make_complete_context(
    intent: str = "INFORM",
    posture: str = "ENGAGE_OPEN",
    regime: str = "INFORM",
    discourse: str = "EXPLANATION",
    actions: List[str] = None,
    interaction_mode: str = "INFORMATIVE",
    blocked: bool = False,
    grounding_policy: str = "PERMITTED",
    grounding_mode: str = "DETACHED",
) -> MockPipelineContext:
    """
    Create a complete mock pipeline context with all required fields.

    This represents a context AFTER P15 has completed (ready for snapshot).
    """
    if actions is None:
        actions = ["EXPLAIN", "ANALYZE"]

    return MockPipelineContext(
        phase_zero=MockPhaseZero.create(intent=intent, posture=posture),
        p6_regime=MockP6Regime.create(regime=regime),
        p7_discourse_envelope=MockP7Discourse.create(act=discourse),
        allowed_actions=MockAllowedActions.create(actions),
        interaction_directive=MockInteractionDirective.create(
            mode=interaction_mode, blocked=blocked
        ),
        phase_minus_one=MockPhaseMinusOne.create(
            policy=grounding_policy, mode=grounding_mode
        ),
    )


def make_blocked_context() -> MockPipelineContext:
    """Create a context with BLOCKED state."""
    return make_complete_context(
        intent="CLARIFY",
        posture="HOLD",
        regime="HOLD",
        discourse="DEFERRAL",
        actions=[],
        interaction_mode="ACK_ONLY",
        blocked=True,
        grounding_policy="BLOCKED",
    )


def make_informative_context() -> MockPipelineContext:
    """Create a context for INFORMATIVE mode."""
    return make_complete_context(
        intent="INFORM",
        posture="ENGAGE_OPEN",
        regime="INFORM",
        discourse="EXPLANATION",
        actions=["EXPLAIN", "ANALYZE"],
        interaction_mode="INFORMATIVE",
        blocked=False,
    )


def make_supportive_context() -> MockPipelineContext:
    """Create a context for SUPPORTIVE mode."""
    return make_complete_context(
        intent="SUPPORT",
        posture="ACKNOWLEDGE",
        regime="DE_ESCALATE",
        discourse="REFLECTION",
        actions=["CARE", "VALIDATE"],
        interaction_mode="SUPPORTIVE",
        blocked=False,
        grounding_mode="REFLEXIVE",
    )


# ============================================================================
# SCHEMA TESTS
# ============================================================================


class TestP15AuthoritySnapshotSchema:
    """Tests for P15AuthoritySnapshot dataclass."""

    def test_snapshot_construction_valid(self):
        """Snapshot can be constructed with valid values."""
        snapshot = P15AuthoritySnapshot(
            intent="INFORM",
            regime="INFORM",
            discourse_act="EXPLANATION",
            response_posture="ENGAGE_OPEN",
            interaction_mode="INFORMATIVE",
            allowed_actions=frozenset(["EXPLAIN", "ANALYZE"]),
            blocked=False,
        )

        assert snapshot.intent == "INFORM"
        assert snapshot.regime == "INFORM"
        assert snapshot.discourse_act == "EXPLANATION"
        assert snapshot.response_posture == "ENGAGE_OPEN"
        assert snapshot.interaction_mode == "INFORMATIVE"
        assert snapshot.allowed_actions == frozenset(["EXPLAIN", "ANALYZE"])
        assert snapshot.blocked is False

    def test_snapshot_immutable(self):
        """Snapshot is immutable (frozen dataclass)."""
        snapshot = P15AuthoritySnapshot(
            intent="INFORM",
            regime="INFORM",
            discourse_act="EXPLANATION",
            response_posture="ENGAGE_OPEN",
            interaction_mode="INFORMATIVE",
            allowed_actions=frozenset(["EXPLAIN"]),
            blocked=False,
        )

        with pytest.raises(Exception):  # FrozenInstanceError
            snapshot.intent = "SUPPORT"

        with pytest.raises(Exception):
            snapshot.blocked = True

    def test_snapshot_rejects_empty_intent(self):
        """Snapshot rejects empty intent."""
        with pytest.raises(ValueError, match="intent cannot be empty"):
            P15AuthoritySnapshot(
                intent="",
                regime="INFORM",
                discourse_act="EXPLANATION",
                response_posture="ENGAGE_OPEN",
                interaction_mode="INFORMATIVE",
                allowed_actions=frozenset(),
                blocked=False,
            )

    def test_snapshot_rejects_empty_regime(self):
        """Snapshot rejects empty regime."""
        with pytest.raises(ValueError, match="regime cannot be empty"):
            P15AuthoritySnapshot(
                intent="INFORM",
                regime="",
                discourse_act="EXPLANATION",
                response_posture="ENGAGE_OPEN",
                interaction_mode="INFORMATIVE",
                allowed_actions=frozenset(),
                blocked=False,
            )

    def test_snapshot_rejects_non_frozenset_actions(self):
        """Snapshot rejects non-frozenset allowed_actions."""
        with pytest.raises(ValueError, match="must be a frozenset"):
            P15AuthoritySnapshot(
                intent="INFORM",
                regime="INFORM",
                discourse_act="EXPLANATION",
                response_posture="ENGAGE_OPEN",
                interaction_mode="INFORMATIVE",
                allowed_actions=["EXPLAIN"],  # list, not frozenset
                blocked=False,
            )

    def test_snapshot_to_dict(self):
        """Snapshot serializes to dict correctly."""
        snapshot = P15AuthoritySnapshot(
            intent="INFORM",
            regime="INFORM",
            discourse_act="EXPLANATION",
            response_posture="ENGAGE_OPEN",
            interaction_mode="INFORMATIVE",
            allowed_actions=frozenset(["EXPLAIN"]),
            blocked=False,
            grounding_mode="DETACHED",
        )

        d = snapshot.to_dict()
        assert d["intent"] == "INFORM"
        assert d["regime"] == "INFORM"
        assert d["blocked"] is False
        assert "EXPLAIN" in d["allowed_actions"]


class TestP15RegressionViolationSchema:
    """Tests for P15RegressionViolation dataclass."""

    def test_violation_construction_valid(self):
        """Violation can be constructed with valid values."""
        violation = P15RegressionViolation(
            phase=16,
            field="intent",
            expected="INFORM",
            observed="SUPPORT",
            violation_type=ViolationType.INTENT_OVERRIDE,
        )

        assert violation.phase == 16
        assert violation.field == "intent"
        assert violation.expected == "INFORM"
        assert violation.observed == "SUPPORT"
        assert violation.violation_type == ViolationType.INTENT_OVERRIDE

    def test_violation_rejects_phase_below_16(self):
        """Violation rejects phase < 16."""
        with pytest.raises(ValueError, match="phase must be >= 16"):
            P15RegressionViolation(
                phase=15,
                field="intent",
                expected="INFORM",
                observed="SUPPORT",
                violation_type=ViolationType.INTENT_OVERRIDE,
            )

    def test_violation_rejects_empty_field(self):
        """Violation rejects empty field name."""
        with pytest.raises(ValueError, match="field cannot be empty"):
            P15RegressionViolation(
                phase=16,
                field="",
                expected="INFORM",
                observed="SUPPORT",
                violation_type=ViolationType.INTENT_OVERRIDE,
            )

    def test_violation_immutable(self):
        """Violation is immutable (frozen dataclass)."""
        violation = P15RegressionViolation(
            phase=16,
            field="intent",
            expected="INFORM",
            observed="SUPPORT",
            violation_type=ViolationType.INTENT_OVERRIDE,
        )

        with pytest.raises(Exception):
            violation.phase = 17


class TestP15RegressionViolationError:
    """Tests for P15RegressionViolationError exception."""

    def test_error_construction(self):
        """Error can be constructed with violations."""
        violations = [
            P15RegressionViolation(
                phase=16,
                field="intent",
                expected="INFORM",
                observed="SUPPORT",
                violation_type=ViolationType.INTENT_OVERRIDE,
            )
        ]

        error = P15RegressionViolationError(violations=violations, phase=16)

        assert len(error.violations) == 1
        assert error.phase == 16
        assert "INTENT_OVERRIDE" in str(error)

    def test_error_message_includes_all_violations(self):
        """Error message includes all violations."""
        violations = [
            P15RegressionViolation(
                phase=16,
                field="intent",
                expected="INFORM",
                observed="SUPPORT",
                violation_type=ViolationType.INTENT_OVERRIDE,
            ),
            P15RegressionViolation(
                phase=16,
                field="regime",
                expected="INFORM",
                observed="HOLD",
                violation_type=ViolationType.REGIME_ESCALATION,
            ),
        ]

        error = P15RegressionViolationError(violations=violations, phase=16)

        message = str(error)
        assert "2 violation(s)" in message
        assert "INTENT_OVERRIDE" in message
        assert "REGIME_ESCALATION" in message

    def test_error_to_dict(self):
        """Error serializes to dict correctly."""
        violations = [
            P15RegressionViolation(
                phase=16,
                field="intent",
                expected="INFORM",
                observed="SUPPORT",
                violation_type=ViolationType.INTENT_OVERRIDE,
            )
        ]

        error = P15RegressionViolationError(violations=violations, phase=16)
        d = error.to_dict()

        assert d["error_type"] == "P15RegressionViolationError"
        assert d["phase"] == 16
        assert d["violation_count"] == 1


# ============================================================================
# GUARD CAPTURE TESTS
# ============================================================================


class TestP15RegressionGuardCapture:
    """Tests for P15RegressionGuard.capture() method."""

    def test_capture_extracts_all_fields(self):
        """Capture extracts all authority-bearing fields."""
        guard = P15RegressionGuard()
        ctx = make_complete_context()

        snapshot = guard.capture(ctx)

        assert snapshot.intent == "INFORM"
        assert snapshot.regime == "INFORM"
        assert snapshot.discourse_act == "EXPLANATION"
        assert snapshot.response_posture == "ENGAGE_OPEN"
        assert snapshot.interaction_mode == "INFORMATIVE"
        assert snapshot.blocked is False
        assert "EXPLAIN" in snapshot.allowed_actions or "ANALYZE" in snapshot.allowed_actions

    def test_capture_blocked_context(self):
        """Capture correctly identifies blocked state."""
        guard = P15RegressionGuard()
        ctx = make_blocked_context()

        snapshot = guard.capture(ctx)

        assert snapshot.blocked is True
        assert snapshot.interaction_mode == "ACK_ONLY"

    def test_capture_raises_on_missing_phase_zero(self):
        """Capture raises when phase_zero is missing."""
        guard = P15RegressionGuard()
        ctx = make_complete_context()
        ctx.phase_zero = None

        with pytest.raises(ValueError, match="phase_zero is None"):
            guard.capture(ctx)

    def test_capture_raises_on_missing_p6_regime(self):
        """Capture raises when p6_regime is missing."""
        guard = P15RegressionGuard()
        ctx = make_complete_context()
        ctx.p6_regime = None

        with pytest.raises(ValueError, match="p6_regime is None"):
            guard.capture(ctx)

    def test_capture_raises_on_missing_p7_discourse(self):
        """Capture raises when p7_discourse_envelope is missing."""
        guard = P15RegressionGuard()
        ctx = make_complete_context()
        ctx.p7_discourse_envelope = None

        with pytest.raises(ValueError, match="p7_discourse_envelope is None"):
            guard.capture(ctx)

    def test_capture_raises_on_missing_interaction_directive(self):
        """Capture raises when interaction_directive is missing."""
        guard = P15RegressionGuard()
        ctx = make_complete_context()
        ctx.interaction_directive = None

        with pytest.raises(ValueError, match="interaction_directive is None"):
            guard.capture(ctx)


# ============================================================================
# GUARD VALIDATE TESTS - REQUIRED TEST CATEGORIES
# ============================================================================


class TestIntentOverrideBlocked:
    """
    REQUIRED TEST CATEGORY 1: Intent override blocked

    Tests that any attempt to change intent after P15 is detected.
    """

    def test_intent_change_detected(self):
        """Intent change from INFORM to SUPPORT is detected."""
        guard = P15RegressionGuard()
        ctx = make_informative_context()
        snapshot = guard.capture(ctx)

        # Simulate phase 16 changing intent
        ctx.phase_zero = MockPhaseZero.create(intent="SUPPORT")

        violations = guard.validate(snapshot, ctx, current_phase=16)

        assert len(violations) >= 1
        intent_violation = next(
            (v for v in violations if v.field == "intent"), None
        )
        assert intent_violation is not None
        assert intent_violation.violation_type == ViolationType.INTENT_OVERRIDE
        assert intent_violation.expected == "INFORM"
        assert intent_violation.observed == "SUPPORT"

    def test_intent_change_all_types_detected(self):
        """All intent type changes are detected."""
        guard = P15RegressionGuard()
        intent_types = ["CLARIFY", "SUPPORT", "REFLECT", "INFORM", "ABSTAIN"]

        for original_intent in intent_types:
            ctx = make_complete_context(intent=original_intent)
            snapshot = guard.capture(ctx)

            for changed_intent in intent_types:
                if changed_intent != original_intent:
                    ctx.phase_zero = MockPhaseZero.create(intent=changed_intent)
                    violations = guard.validate(snapshot, ctx, current_phase=16)

                    intent_violations = [
                        v for v in violations
                        if v.violation_type == ViolationType.INTENT_OVERRIDE
                    ]
                    assert len(intent_violations) >= 1, (
                        f"Should detect change from {original_intent} to {changed_intent}"
                    )

    def test_intent_unchanged_no_violation(self):
        """No violation when intent is unchanged."""
        guard = P15RegressionGuard()
        ctx = make_informative_context()
        snapshot = guard.capture(ctx)

        # No change - same context
        violations = guard.validate(snapshot, ctx, current_phase=16)

        intent_violations = [
            v for v in violations
            if v.violation_type == ViolationType.INTENT_OVERRIDE
        ]
        assert len(intent_violations) == 0


class TestRegimeEscalationBlocked:
    """
    REQUIRED TEST CATEGORY 2: Regime escalation blocked

    Tests that any attempt to change regime after P15 is detected.
    """

    def test_regime_change_detected(self):
        """Regime change from INFORM to DE_ESCALATE is detected."""
        guard = P15RegressionGuard()
        ctx = make_informative_context()
        snapshot = guard.capture(ctx)

        # Simulate phase 16 changing regime
        ctx.p6_regime = MockP6Regime.create(regime="DE_ESCALATE")

        violations = guard.validate(snapshot, ctx, current_phase=16)

        regime_violation = next(
            (v for v in violations if v.field == "regime"), None
        )
        assert regime_violation is not None
        assert regime_violation.violation_type == ViolationType.REGIME_ESCALATION
        assert regime_violation.expected == "INFORM"
        assert regime_violation.observed == "DE_ESCALATE"

    def test_regime_change_all_types_detected(self):
        """All regime changes are detected."""
        guard = P15RegressionGuard()
        regimes = ["STABILIZE", "REFLECT", "INFORM", "CLARIFY", "DE_ESCALATE", "HOLD"]

        for original_regime in regimes:
            ctx = make_complete_context(regime=original_regime)
            snapshot = guard.capture(ctx)

            for changed_regime in regimes:
                if changed_regime != original_regime:
                    ctx.p6_regime = MockP6Regime.create(regime=changed_regime)
                    violations = guard.validate(snapshot, ctx, current_phase=16)

                    regime_violations = [
                        v for v in violations
                        if v.violation_type == ViolationType.REGIME_ESCALATION
                    ]
                    assert len(regime_violations) >= 1, (
                        f"Should detect change from {original_regime} to {changed_regime}"
                    )

    def test_regime_unchanged_no_violation(self):
        """No violation when regime is unchanged."""
        guard = P15RegressionGuard()
        ctx = make_informative_context()
        snapshot = guard.capture(ctx)

        violations = guard.validate(snapshot, ctx, current_phase=16)

        regime_violations = [
            v for v in violations
            if v.violation_type == ViolationType.REGIME_ESCALATION
        ]
        assert len(regime_violations) == 0


class TestDiscourseActMutationBlocked:
    """
    REQUIRED TEST CATEGORY 3: Discourse act mutation blocked

    Tests that any attempt to change discourse act after P15 is detected.
    """

    def test_discourse_act_change_detected(self):
        """Discourse act change from EXPLANATION to QUESTION is detected."""
        guard = P15RegressionGuard()
        ctx = make_informative_context()
        snapshot = guard.capture(ctx)

        # Simulate phase 16 changing discourse act
        ctx.p7_discourse_envelope = MockP7Discourse.create(act="QUESTION")

        violations = guard.validate(snapshot, ctx, current_phase=16)

        discourse_violation = next(
            (v for v in violations if v.field == "discourse_act"), None
        )
        assert discourse_violation is not None
        assert discourse_violation.violation_type == ViolationType.DISCOURSE_MUTATION
        assert discourse_violation.expected == "EXPLANATION"
        assert discourse_violation.observed == "QUESTION"

    def test_discourse_act_all_types_detected(self):
        """All discourse act changes are detected."""
        guard = P15RegressionGuard()
        acts = ["QUESTION", "REFLECTION", "ACKNOWLEDGMENT", "EXPLANATION", "INSTRUCTION", "DEFERRAL"]

        for original_act in acts:
            ctx = make_complete_context(discourse=original_act)
            snapshot = guard.capture(ctx)

            for changed_act in acts:
                if changed_act != original_act:
                    ctx.p7_discourse_envelope = MockP7Discourse.create(act=changed_act)
                    violations = guard.validate(snapshot, ctx, current_phase=16)

                    discourse_violations = [
                        v for v in violations
                        if v.violation_type == ViolationType.DISCOURSE_MUTATION
                    ]
                    assert len(discourse_violations) >= 1, (
                        f"Should detect change from {original_act} to {changed_act}"
                    )


class TestAllowedActionExpansionBlocked:
    """
    REQUIRED TEST CATEGORY 4: Allowed-action expansion blocked

    Tests that expanding the allowed action set after P15 is detected.
    Note: REDUCING actions is allowed (more restrictive is OK).
    """

    def test_action_expansion_detected(self):
        """Adding new action to allowed set is detected."""
        guard = P15RegressionGuard()
        ctx = make_complete_context(actions=["EXPLAIN"])
        snapshot = guard.capture(ctx)

        # Simulate phase 16 expanding allowed actions
        ctx.allowed_actions = MockAllowedActions.create(["EXPLAIN", "DIAGNOSE"])

        violations = guard.validate(snapshot, ctx, current_phase=16)

        action_violation = next(
            (v for v in violations if v.field == "allowed_actions"), None
        )
        assert action_violation is not None
        assert action_violation.violation_type == ViolationType.ACTION_EXPANSION
        assert "DIAGNOSE" in action_violation.reason

    def test_action_reduction_allowed(self):
        """Reducing allowed actions is NOT a violation (more restrictive)."""
        guard = P15RegressionGuard()
        ctx = make_complete_context(actions=["EXPLAIN", "ANALYZE", "SUMMARIZE"])
        snapshot = guard.capture(ctx)

        # Reduce to fewer actions - this is allowed
        ctx.allowed_actions = MockAllowedActions.create(["EXPLAIN"])

        violations = guard.validate(snapshot, ctx, current_phase=16)

        action_violations = [
            v for v in violations
            if v.violation_type == ViolationType.ACTION_EXPANSION
        ]
        assert len(action_violations) == 0

    def test_action_unchanged_no_violation(self):
        """No violation when actions are unchanged."""
        guard = P15RegressionGuard()
        ctx = make_complete_context(actions=["EXPLAIN", "ANALYZE"])
        snapshot = guard.capture(ctx)

        violations = guard.validate(snapshot, ctx, current_phase=16)

        action_violations = [
            v for v in violations
            if v.violation_type == ViolationType.ACTION_EXPANSION
        ]
        assert len(action_violations) == 0


class TestBlockedUnblockForbidden:
    """
    REQUIRED TEST CATEGORY 5: BLOCKED → unblocked forbidden

    Tests that a blocked state cannot transition to unblocked.
    """

    def test_blocked_to_unblocked_detected(self):
        """Transitioning from blocked=True to blocked=False is detected."""
        guard = P15RegressionGuard()
        ctx = make_blocked_context()
        snapshot = guard.capture(ctx)

        assert snapshot.blocked is True

        # Simulate phase 16 attempting to unblock
        ctx.interaction_directive = MockInteractionDirective.create(
            mode="INFORMATIVE", blocked=False
        )

        violations = guard.validate(snapshot, ctx, current_phase=16)

        blocked_violation = next(
            (v for v in violations if v.field == "blocked"), None
        )
        assert blocked_violation is not None
        assert blocked_violation.violation_type == ViolationType.BLOCKED_UNBLOCK
        assert blocked_violation.expected is True
        assert blocked_violation.observed is False

    def test_blocked_remains_blocked_no_violation(self):
        """No violation when blocked state remains blocked."""
        guard = P15RegressionGuard()
        ctx = make_blocked_context()
        snapshot = guard.capture(ctx)

        violations = guard.validate(snapshot, ctx, current_phase=16)

        blocked_violations = [
            v for v in violations
            if v.violation_type == ViolationType.BLOCKED_UNBLOCK
        ]
        assert len(blocked_violations) == 0

    def test_unblocked_can_become_blocked(self):
        """Transitioning from unblocked to blocked is allowed (not tested by this guard)."""
        guard = P15RegressionGuard()
        ctx = make_informative_context()
        snapshot = guard.capture(ctx)

        assert snapshot.blocked is False

        # Becoming more restrictive (blocked) is not a violation
        ctx.interaction_directive = MockInteractionDirective.create(
            mode="ACK_ONLY", blocked=True
        )

        violations = guard.validate(snapshot, ctx, current_phase=16)

        # No BLOCKED_UNBLOCK violation (that's only for going True -> False)
        blocked_violations = [
            v for v in violations
            if v.violation_type == ViolationType.BLOCKED_UNBLOCK
        ]
        assert len(blocked_violations) == 0


class TestPredictionBasedOverrideForbidden:
    """
    REQUIRED TEST CATEGORY 6: Prediction-based override forbidden

    Tests that prediction-based authority override attempts are detected.
    """

    def test_prediction_override_detected(self):
        """Prediction-based override signal is detected."""
        guard = P15RegressionGuard()
        ctx = make_informative_context()
        snapshot = guard.capture(ctx)

        # Simulate phase 16 adding prediction-based override
        ctx.prediction_override = True

        violations = guard.validate(snapshot, ctx, current_phase=16)

        prediction_violation = next(
            (v for v in violations if v.field == "prediction_override"), None
        )
        assert prediction_violation is not None
        assert prediction_violation.violation_type == ViolationType.AUTHORITY_REINTRODUCTION
        assert "Prediction-based override" in prediction_violation.reason

    def test_grammar_authority_override_detected(self):
        """Grammar-based authority override signal is detected."""
        guard = P15RegressionGuard()
        ctx = make_informative_context()
        snapshot = guard.capture(ctx)

        ctx.grammar_authority_override = True

        violations = guard.validate(snapshot, ctx, current_phase=16)

        grammar_violation = next(
            (v for v in violations if v.field == "grammar_authority_override"), None
        )
        assert grammar_violation is not None
        assert grammar_violation.violation_type == ViolationType.AUTHORITY_REINTRODUCTION

    def test_no_prediction_override_no_violation(self):
        """No violation when no prediction override is present."""
        guard = P15RegressionGuard()
        ctx = make_informative_context()
        snapshot = guard.capture(ctx)

        assert ctx.prediction_override is None

        violations = guard.validate(snapshot, ctx, current_phase=16)

        prediction_violations = [
            v for v in violations
            if v.field == "prediction_override"
        ]
        assert len(prediction_violations) == 0


class TestPersonaBasedOverrideForbidden:
    """
    REQUIRED TEST CATEGORY 7: Persona-based override forbidden

    Tests that persona-based authority override attempts are detected.
    """

    def test_persona_authority_override_detected(self):
        """Persona-based authority override signal is detected."""
        guard = P15RegressionGuard()
        ctx = make_informative_context()
        snapshot = guard.capture(ctx)

        # Simulate phase 16 adding persona-based override
        ctx.persona_authority_override = True

        violations = guard.validate(snapshot, ctx, current_phase=16)

        persona_violation = next(
            (v for v in violations if v.field == "persona_authority_override"), None
        )
        assert persona_violation is not None
        assert persona_violation.violation_type == ViolationType.AUTHORITY_REINTRODUCTION
        assert "Persona-based authority" in persona_violation.reason

    def test_no_persona_override_no_violation(self):
        """No violation when no persona override is present."""
        guard = P15RegressionGuard()
        ctx = make_informative_context()
        snapshot = guard.capture(ctx)

        violations = guard.validate(snapshot, ctx, current_phase=16)

        persona_violations = [
            v for v in violations
            if v.field == "persona_authority_override"
        ]
        assert len(persona_violations) == 0


class TestRendererMetadataIgnored:
    """
    REQUIRED TEST CATEGORY 8: Renderer metadata ignored

    Tests that authority signals from renderer phases are detected
    and blocked.
    """

    def test_authority_certainty_injection_detected(self):
        """Authority certainty injection is detected."""
        guard = P15RegressionGuard()
        ctx = make_informative_context()
        snapshot = guard.capture(ctx)

        # Simulate renderer adding certainty signal
        ctx.authority_certainty = 0.95

        violations = guard.validate(snapshot, ctx, current_phase=16)

        certainty_violation = next(
            (v for v in violations if v.field == "authority_certainty"), None
        )
        assert certainty_violation is not None
        assert certainty_violation.violation_type == ViolationType.AUTHORITY_REINTRODUCTION

    def test_authority_explanation_injection_detected(self):
        """Authority explanation injection is detected."""
        guard = P15RegressionGuard()
        ctx = make_informative_context()
        snapshot = guard.capture(ctx)

        # Simulate renderer adding explanation
        ctx.authority_explanation = "Based on analysis..."

        violations = guard.validate(snapshot, ctx, current_phase=16)

        explanation_violation = next(
            (v for v in violations if v.field == "authority_explanation"), None
        )
        assert explanation_violation is not None
        assert explanation_violation.violation_type == ViolationType.AUTHORITY_REINTRODUCTION

    def test_no_renderer_signals_no_violation(self):
        """No violation when no renderer authority signals present."""
        guard = P15RegressionGuard()
        ctx = make_informative_context()
        snapshot = guard.capture(ctx)

        violations = guard.validate(snapshot, ctx, current_phase=16)

        authority_violations = [
            v for v in violations
            if v.violation_type == ViolationType.AUTHORITY_REINTRODUCTION
        ]
        # Should be zero (no interaction_mode change either)
        # May have interaction_mode violation if that changed
        # Filter to just the metadata fields
        metadata_violations = [
            v for v in authority_violations
            if v.field in ["authority_certainty", "authority_explanation"]
        ]
        assert len(metadata_violations) == 0


class TestDeterminism:
    """
    REQUIRED TEST CATEGORY 9: Determinism - same input → same violations

    Tests that the guard is deterministic: identical inputs produce
    identical violation reports.
    """

    def test_same_input_same_violations(self):
        """Same input produces identical violations."""
        guard = P15RegressionGuard()
        ctx = make_informative_context()
        snapshot = guard.capture(ctx)

        # Create a violation
        ctx.phase_zero = MockPhaseZero.create(intent="SUPPORT")

        violations1 = guard.validate(snapshot, ctx, current_phase=16)
        violations2 = guard.validate(snapshot, ctx, current_phase=16)

        assert len(violations1) == len(violations2)
        for v1, v2 in zip(violations1, violations2):
            assert v1.phase == v2.phase
            assert v1.field == v2.field
            assert v1.expected == v2.expected
            assert v1.observed == v2.observed
            assert v1.violation_type == v2.violation_type

    def test_determinism_multiple_violations(self):
        """Multiple violations are deterministically detected."""
        guard = P15RegressionGuard()
        ctx = make_informative_context()
        snapshot = guard.capture(ctx)

        # Create multiple violations
        ctx.phase_zero = MockPhaseZero.create(intent="SUPPORT", posture="HOLD")
        ctx.p6_regime = MockP6Regime.create(regime="DE_ESCALATE")
        ctx.p7_discourse_envelope = MockP7Discourse.create(act="QUESTION")

        # Run validation 10 times
        all_violations = [
            guard.validate(snapshot, ctx, current_phase=16)
            for _ in range(10)
        ]

        # All should be identical
        first = all_violations[0]
        for violations in all_violations[1:]:
            assert len(violations) == len(first)

    def test_determinism_no_violations(self):
        """No violations case is deterministic."""
        guard = P15RegressionGuard()
        ctx = make_informative_context()
        snapshot = guard.capture(ctx)

        # No changes - no violations
        for _ in range(10):
            violations = guard.validate(snapshot, ctx, current_phase=16)
            assert len(violations) == 0


class TestPhaseNumberGuardInactive:
    """
    REQUIRED TEST CATEGORY 10: Phase number < 16 → guard inactive

    Tests that the guard only activates for phases >= 16.
    """

    def test_phase_15_guard_inactive(self):
        """Guard is inactive for phase 15."""
        guard = P15RegressionGuard()
        ctx = make_informative_context()
        snapshot = guard.capture(ctx)

        # Create a would-be violation
        ctx.phase_zero = MockPhaseZero.create(intent="SUPPORT")

        violations = guard.validate(snapshot, ctx, current_phase=15)

        # No violations because guard is inactive
        assert len(violations) == 0

    def test_phase_14_guard_inactive(self):
        """Guard is inactive for phase 14."""
        guard = P15RegressionGuard()
        ctx = make_informative_context()
        snapshot = guard.capture(ctx)

        ctx.phase_zero = MockPhaseZero.create(intent="SUPPORT")

        violations = guard.validate(snapshot, ctx, current_phase=14)
        assert len(violations) == 0

    def test_phase_1_guard_inactive(self):
        """Guard is inactive for phase 1."""
        guard = P15RegressionGuard()
        ctx = make_informative_context()
        snapshot = guard.capture(ctx)

        ctx.phase_zero = MockPhaseZero.create(intent="SUPPORT")

        violations = guard.validate(snapshot, ctx, current_phase=1)
        assert len(violations) == 0

    def test_phase_16_guard_active(self):
        """Guard is active for phase 16."""
        guard = P15RegressionGuard()
        ctx = make_informative_context()
        snapshot = guard.capture(ctx)

        ctx.phase_zero = MockPhaseZero.create(intent="SUPPORT")

        violations = guard.validate(snapshot, ctx, current_phase=16)
        assert len(violations) >= 1

    def test_phase_17_guard_active(self):
        """Guard is active for phase 17."""
        guard = P15RegressionGuard()
        ctx = make_informative_context()
        snapshot = guard.capture(ctx)

        ctx.phase_zero = MockPhaseZero.create(intent="SUPPORT")

        violations = guard.validate(snapshot, ctx, current_phase=17)
        assert len(violations) >= 1

    def test_phase_100_guard_active(self):
        """Guard is active for any phase >= 16."""
        guard = P15RegressionGuard()
        ctx = make_informative_context()
        snapshot = guard.capture(ctx)

        ctx.phase_zero = MockPhaseZero.create(intent="SUPPORT")

        violations = guard.validate(snapshot, ctx, current_phase=100)
        assert len(violations) >= 1


# ============================================================================
# INTEGRATION TESTS
# ============================================================================


class TestP15IntegrationFunctions:
    """Tests for integration functions."""

    def test_capture_p15_snapshot_stores_on_context(self):
        """capture_p15_snapshot stores snapshot on context."""
        ctx = make_informative_context()

        capture_p15_snapshot(ctx)

        assert has_p15_snapshot(ctx) is True
        snapshot = get_p15_snapshot(ctx)
        assert snapshot is not None
        assert snapshot.intent == "INFORM"

    def test_capture_p15_snapshot_double_capture_raises(self):
        """Double capture raises RuntimeError."""
        ctx = make_informative_context()

        capture_p15_snapshot(ctx)

        with pytest.raises(RuntimeError, match="already been captured"):
            capture_p15_snapshot(ctx)

    def test_enforce_p15_regression_guard_raises_on_violation(self):
        """enforce_p15_regression_guard raises on violation."""
        ctx = make_informative_context()
        capture_p15_snapshot(ctx)

        # Create violation
        ctx.phase_zero = MockPhaseZero.create(intent="SUPPORT")

        with pytest.raises(P15RegressionViolationError) as exc_info:
            enforce_p15_regression_guard(ctx, phase_number=16)

        assert exc_info.value.phase == 16
        assert len(exc_info.value.violations) >= 1

    def test_enforce_p15_regression_guard_no_raise_when_valid(self):
        """enforce_p15_regression_guard does not raise when valid."""
        ctx = make_informative_context()
        capture_p15_snapshot(ctx)

        # No changes - should not raise
        enforce_p15_regression_guard(ctx, phase_number=16)

    def test_enforce_p15_regression_guard_inactive_before_16(self):
        """enforce_p15_regression_guard is no-op for phases < 16."""
        ctx = make_informative_context()
        capture_p15_snapshot(ctx)

        # Create would-be violation
        ctx.phase_zero = MockPhaseZero.create(intent="SUPPORT")

        # Should not raise for phase 15
        enforce_p15_regression_guard(ctx, phase_number=15)

    def test_enforce_p15_regression_guard_missing_snapshot_raises(self):
        """enforce_p15_regression_guard raises when snapshot missing."""
        ctx = make_informative_context()
        # No snapshot captured

        with pytest.raises(RuntimeError, match="snapshot not found"):
            enforce_p15_regression_guard(ctx, phase_number=16)

    def test_validate_p15_snapshot_without_raise(self):
        """validate_p15_snapshot_without_raise returns error without raising."""
        ctx = make_informative_context()
        capture_p15_snapshot(ctx)

        # Create violation
        ctx.phase_zero = MockPhaseZero.create(intent="SUPPORT")

        error = validate_p15_snapshot_without_raise(ctx, phase_number=16)

        assert error is not None
        assert isinstance(error, P15RegressionViolationError)
        assert len(error.violations) >= 1

    def test_validate_p15_snapshot_without_raise_returns_none_when_valid(self):
        """validate_p15_snapshot_without_raise returns None when valid."""
        ctx = make_informative_context()
        capture_p15_snapshot(ctx)

        error = validate_p15_snapshot_without_raise(ctx, phase_number=16)

        assert error is None


# ============================================================================
# COMPREHENSIVE VIOLATION ACCUMULATION TESTS
# ============================================================================


class TestViolationAccumulation:
    """Tests that all violations are collected, not just the first one."""

    def test_multiple_violations_all_collected(self):
        """All violations are collected when multiple fields change."""
        guard = P15RegressionGuard()
        ctx = make_informative_context()
        snapshot = guard.capture(ctx)

        # Create multiple violations
        ctx.phase_zero = MockPhaseZero.create(intent="SUPPORT", posture="HOLD")
        ctx.p6_regime = MockP6Regime.create(regime="DE_ESCALATE")
        ctx.p7_discourse_envelope = MockP7Discourse.create(act="QUESTION")
        ctx.allowed_actions = MockAllowedActions.create(
            ["EXPLAIN", "ANALYZE", "DIAGNOSE"]  # Added DIAGNOSE
        )
        ctx.authority_certainty = 0.9

        violations = guard.validate(snapshot, ctx, current_phase=16)

        # Should have violations for: intent, posture, regime, discourse_act,
        # allowed_actions expansion, authority_certainty
        violation_fields = {v.field for v in violations}

        assert "intent" in violation_fields
        assert "regime" in violation_fields
        assert "discourse_act" in violation_fields
        assert "allowed_actions" in violation_fields
        assert "authority_certainty" in violation_fields

    def test_violation_order_is_consistent(self):
        """Violation order is consistent across multiple runs."""
        guard = P15RegressionGuard()
        ctx = make_informative_context()
        snapshot = guard.capture(ctx)

        ctx.phase_zero = MockPhaseZero.create(intent="SUPPORT")
        ctx.p6_regime = MockP6Regime.create(regime="DE_ESCALATE")

        violations1 = guard.validate(snapshot, ctx, current_phase=16)
        violations2 = guard.validate(snapshot, ctx, current_phase=16)

        fields1 = [v.field for v in violations1]
        fields2 = [v.field for v in violations2]

        assert fields1 == fields2


# ============================================================================
# EDGE CASE TESTS
# ============================================================================


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_empty_allowed_actions_handled(self):
        """Empty allowed actions set is handled correctly."""
        guard = P15RegressionGuard()
        ctx = make_complete_context(actions=[])
        snapshot = guard.capture(ctx)

        assert snapshot.allowed_actions == frozenset()

        # Adding any action is expansion
        ctx.allowed_actions = MockAllowedActions.create(["EXPLAIN"])
        violations = guard.validate(snapshot, ctx, current_phase=16)

        action_violations = [
            v for v in violations
            if v.violation_type == ViolationType.ACTION_EXPANSION
        ]
        assert len(action_violations) >= 1

    def test_null_allowed_actions_handled(self):
        """Null allowed_actions on context is handled."""
        guard = P15RegressionGuard()
        ctx = make_complete_context(actions=["EXPLAIN"])
        ctx.allowed_actions = None

        snapshot = guard.capture(ctx)
        # Should handle gracefully with empty set
        assert snapshot.allowed_actions == frozenset()

    def test_interaction_mode_change_detected(self):
        """Interaction mode change is detected as violation."""
        guard = P15RegressionGuard()
        ctx = make_informative_context()
        snapshot = guard.capture(ctx)

        # Change interaction mode
        ctx.interaction_directive = MockInteractionDirective.create(
            mode="READ_ONLY", blocked=False
        )

        violations = guard.validate(snapshot, ctx, current_phase=16)

        mode_violations = [
            v for v in violations
            if v.field == "interaction_mode"
        ]
        assert len(mode_violations) >= 1

    def test_response_posture_change_detected(self):
        """Response posture change is detected."""
        guard = P15RegressionGuard()
        ctx = make_informative_context()
        snapshot = guard.capture(ctx)

        # Change response posture
        ctx.phase_zero = MockPhaseZero.create(
            intent="INFORM",  # Keep intent same
            posture="HOLD"    # Change posture
        )

        violations = guard.validate(snapshot, ctx, current_phase=16)

        posture_violations = [
            v for v in violations
            if v.field == "response_posture"
        ]
        assert len(posture_violations) >= 1


# ============================================================================
# VIOLATION TYPE COVERAGE TESTS
# ============================================================================


class TestViolationTypeCoverage:
    """Tests that all violation types can be triggered."""

    def test_all_violation_types_can_be_triggered(self):
        """All ViolationType enum values can be triggered."""
        guard = P15RegressionGuard()

        # Test INTENT_OVERRIDE
        ctx = make_informative_context()
        snapshot = guard.capture(ctx)
        ctx.phase_zero = MockPhaseZero.create(intent="SUPPORT")
        violations = guard.validate(snapshot, ctx, current_phase=16)
        assert any(v.violation_type == ViolationType.INTENT_OVERRIDE for v in violations)

        # Test REGIME_ESCALATION
        ctx = make_informative_context()
        snapshot = guard.capture(ctx)
        ctx.p6_regime = MockP6Regime.create(regime="HOLD")
        violations = guard.validate(snapshot, ctx, current_phase=16)
        assert any(v.violation_type == ViolationType.REGIME_ESCALATION for v in violations)

        # Test DISCOURSE_MUTATION
        ctx = make_informative_context()
        snapshot = guard.capture(ctx)
        ctx.p7_discourse_envelope = MockP7Discourse.create(act="DEFERRAL")
        violations = guard.validate(snapshot, ctx, current_phase=16)
        assert any(v.violation_type == ViolationType.DISCOURSE_MUTATION for v in violations)

        # Test POSTURE_MUTATION
        ctx = make_informative_context()
        snapshot = guard.capture(ctx)
        ctx.phase_zero = MockPhaseZero.create(intent="INFORM", posture="HOLD")
        violations = guard.validate(snapshot, ctx, current_phase=16)
        assert any(v.violation_type == ViolationType.POSTURE_MUTATION for v in violations)

        # Test ACTION_EXPANSION
        ctx = make_complete_context(actions=["EXPLAIN"])
        snapshot = guard.capture(ctx)
        ctx.allowed_actions = MockAllowedActions.create(["EXPLAIN", "DIAGNOSE"])
        violations = guard.validate(snapshot, ctx, current_phase=16)
        assert any(v.violation_type == ViolationType.ACTION_EXPANSION for v in violations)

        # Test BLOCKED_UNBLOCK
        ctx = make_blocked_context()
        snapshot = guard.capture(ctx)
        ctx.interaction_directive = MockInteractionDirective.create(blocked=False)
        violations = guard.validate(snapshot, ctx, current_phase=16)
        assert any(v.violation_type == ViolationType.BLOCKED_UNBLOCK for v in violations)

        # Test AUTHORITY_REINTRODUCTION
        ctx = make_informative_context()
        snapshot = guard.capture(ctx)
        ctx.authority_certainty = 0.99
        violations = guard.validate(snapshot, ctx, current_phase=16)
        assert any(v.violation_type == ViolationType.AUTHORITY_REINTRODUCTION for v in violations)


# ============================================================================
# GUARD CONSTANT TESTS
# ============================================================================


class TestGuardConstants:
    """Tests for guard configuration constants."""

    def test_guard_activates_at_phase_16(self):
        """Guard activation threshold is phase 16."""
        guard = P15RegressionGuard()
        assert guard.GUARD_ACTIVE_FROM_PHASE == 16

    def test_snapshot_version_present(self):
        """Snapshot has version field."""
        snapshot = P15AuthoritySnapshot(
            intent="INFORM",
            regime="INFORM",
            discourse_act="EXPLANATION",
            response_posture="ENGAGE_OPEN",
            interaction_mode="INFORMATIVE",
            allowed_actions=frozenset(),
            blocked=False,
        )

        assert snapshot.snapshot_version == "1.0.0"
        assert snapshot.captured_at_phase == 15
