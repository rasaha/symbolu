"""
P15 Unit Tests - Interaction Mode Resolver

Tests for P15 Interaction Mode Resolver:
- InteractionDirective dataclass
- P15InteractionResolver (deterministic)
- Mode resolution rules
- Integration with upstream phases

Test Categories (per specification):
A. HOLD Regime Tests
   - HOLD always produces READ_ONLY
   - HOLD cannot be escalated to other modes

B. BLOCKED State Tests
   - BLOCKED always produces ACK_ONLY
   - BLOCKED takes precedence over other rules

C. DEFERRAL Discourse Tests
   - DEFERRAL discourse produces ACK_ONLY
   - DEFERRAL cannot be escalated

D. QUESTION Discourse Tests
   - QUESTION discourse produces CLARIFYING mode
   - CLARIFYING allows questions

E. REFLEXIVE + SUPPORTIVE Regime Tests
   - REFLEXIVE + DE_ESCALATE produces SUPPORTIVE
   - REFLEXIVE + STABILIZE produces SUPPORTIVE
   - SUPPORTIVE allows support

F. DETACHED + EXPLANATION Tests
   - DETACHED + EXPLANATION produces INFORMATIVE
   - INFORMATIVE allows information

G. Fallback Tests
   - Unknown combinations produce READ_ONLY
   - Missing data produces READ_ONLY

H. Determinism Tests
   - Same input produces same output
   - Resolver is stateless

I. No Escalation Tests
   - P15 cannot escalate modes
   - P15 cannot override P13 or P14

J. Schema Validation Tests
   - Dataclass construction
   - Invariant validation
   - Serialization

K. Integration Tests
   - maybe_run_p15 behavior
   - Accessor functions
   - Empty/missing data handling

Target: >= 60 tests

CRITICAL: P15 determines interaction posture only.
P15 is deterministic, zero-LLM, no ML.
"""

from dataclasses import dataclass
from typing import Any, Optional
from unittest.mock import patch, MagicMock

import pytest

from symbolu.mechanical.pipeline.p15_interaction import (
    # Schema
    InteractionMode,
    InteractionDirective,
    P15_VERSION,
    get_read_only_directive,
    get_ack_only_directive,
    # Resolver
    P15InteractionResolver,
    resolve_interaction_mode,
    SUPPORTIVE_REGIMES,
    HOLD_REGIMES,
    DEFERRAL_DISCOURSE_ACTS,
    QUESTION_DISCOURSE_ACTS,
    EXPLANATION_DISCOURSE_ACTS,
    REFLEXIVE_GROUNDING_MODES,
    DETACHED_GROUNDING_MODES,
    # Integration
    get_p15_resolver,
    maybe_run_p15,
    run_p15_directly,
    get_interaction_directive,
    get_mode,
    is_read_only,
    is_ack_only,
    is_supportive,
    is_clarifying,
    is_informative,
    allows_questions,
    allows_information,
    allows_support,
    is_blocked,
)


# ============================================================================
# TEST HELPERS
# ============================================================================


@dataclass
class MockRegimeEnvelope:
    """Mock P6 regime envelope."""
    regime: Any

    @dataclass
    class MockRegime:
        value: str

    @classmethod
    def create(cls, regime_value: str) -> "MockRegimeEnvelope":
        return cls(regime=cls.MockRegime(value=regime_value))


@dataclass
class MockDiscourseEnvelope:
    """Mock P7 discourse envelope."""
    act: Any

    @dataclass
    class MockAct:
        value: str

    @classmethod
    def create(cls, act_value: str) -> "MockDiscourseEnvelope":
        return cls(act=cls.MockAct(value=act_value))


@dataclass
class MockGroundingCandidate:
    """Mock grounding candidate."""
    mode: Any

    @dataclass
    class MockMode:
        value: str


@dataclass
class MockPhaseMinusOneEnvelope:
    """Mock PO1 grounding envelope."""
    selected_primary: Optional[MockGroundingCandidate] = None
    _is_blocked: bool = False

    @classmethod
    def create(cls, mode_value: str, blocked: bool = False) -> "MockPhaseMinusOneEnvelope":
        return cls(
            selected_primary=MockGroundingCandidate(
                mode=MockGroundingCandidate.MockMode(value=mode_value)
            ),
            _is_blocked=blocked,
        )

    def is_blocked(self) -> bool:
        return self._is_blocked


@dataclass
class MockP13SafetyEnvelope:
    """Mock P13 safety envelope."""
    _is_blocked: bool = False

    def is_blocked(self) -> bool:
        return self._is_blocked


@dataclass
class MockPipelineContext:
    """Mock pipeline context for testing."""
    p6_regime: Optional[MockRegimeEnvelope] = None
    p7_discourse_envelope: Optional[MockDiscourseEnvelope] = None
    phase_minus_one: Optional[MockPhaseMinusOneEnvelope] = None
    p13_safety_envelope: Optional[MockP13SafetyEnvelope] = None
    interaction_directive: Optional[InteractionDirective] = None


def make_hold_context() -> MockPipelineContext:
    """Create a context for HOLD regime."""
    return MockPipelineContext(
        p6_regime=MockRegimeEnvelope.create("HOLD"),
        p7_discourse_envelope=MockDiscourseEnvelope.create("DEFERRAL"),
        phase_minus_one=MockPhaseMinusOneEnvelope.create("UNKNOWN"),
    )


def make_blocked_context() -> MockPipelineContext:
    """Create a context with BLOCKED state."""
    return MockPipelineContext(
        p6_regime=MockRegimeEnvelope.create("INFORM"),
        p7_discourse_envelope=MockDiscourseEnvelope.create("EXPLANATION"),
        phase_minus_one=MockPhaseMinusOneEnvelope.create("DETACHED", blocked=True),
    )


def make_deferral_context() -> MockPipelineContext:
    """Create a context with DEFERRAL discourse."""
    return MockPipelineContext(
        p6_regime=MockRegimeEnvelope.create("CLARIFY"),
        p7_discourse_envelope=MockDiscourseEnvelope.create("DEFERRAL"),
        phase_minus_one=MockPhaseMinusOneEnvelope.create("UNKNOWN"),
    )


def make_question_context() -> MockPipelineContext:
    """Create a context with QUESTION discourse."""
    return MockPipelineContext(
        p6_regime=MockRegimeEnvelope.create("CLARIFY"),
        p7_discourse_envelope=MockDiscourseEnvelope.create("QUESTION"),
        phase_minus_one=MockPhaseMinusOneEnvelope.create("DETACHED"),
    )


def make_supportive_context() -> MockPipelineContext:
    """Create a context for SUPPORTIVE mode (REFLEXIVE + DE_ESCALATE)."""
    return MockPipelineContext(
        p6_regime=MockRegimeEnvelope.create("DE_ESCALATE"),
        p7_discourse_envelope=MockDiscourseEnvelope.create("REFLECTION"),
        phase_minus_one=MockPhaseMinusOneEnvelope.create("REFLEXIVE"),
    )


def make_supportive_stabilize_context() -> MockPipelineContext:
    """Create a context for SUPPORTIVE mode (REFLEXIVE + STABILIZE)."""
    return MockPipelineContext(
        p6_regime=MockRegimeEnvelope.create("STABILIZE"),
        p7_discourse_envelope=MockDiscourseEnvelope.create("REFLECTION"),
        phase_minus_one=MockPhaseMinusOneEnvelope.create("REFLEXIVE"),
    )


def make_informative_context() -> MockPipelineContext:
    """Create a context for INFORMATIVE mode (DETACHED + EXPLANATION)."""
    return MockPipelineContext(
        p6_regime=MockRegimeEnvelope.create("INFORM"),
        p7_discourse_envelope=MockDiscourseEnvelope.create("EXPLANATION"),
        phase_minus_one=MockPhaseMinusOneEnvelope.create("DETACHED"),
    )


def make_fallback_context() -> MockPipelineContext:
    """Create a context that should fall back to READ_ONLY."""
    return MockPipelineContext(
        p6_regime=MockRegimeEnvelope.create("INFORM"),
        p7_discourse_envelope=MockDiscourseEnvelope.create("ACKNOWLEDGMENT"),
        phase_minus_one=MockPhaseMinusOneEnvelope.create("RELATIONAL"),
    )


# ============================================================================
# A. HOLD REGIME TESTS
# ============================================================================


class TestHoldRegime:
    """Tests for HOLD regime behavior."""

    def test_hold_produces_read_only(self):
        """Test: HOLD regime -> READ_ONLY mode."""
        ctx = make_hold_context()
        directive = run_p15_directly(ctx)

        assert directive is not None
        assert directive.mode == InteractionMode.READ_ONLY

    def test_hold_not_escalatable(self):
        """Test: HOLD cannot be escalated even with QUESTION discourse."""
        ctx = MockPipelineContext(
            p6_regime=MockRegimeEnvelope.create("HOLD"),
            p7_discourse_envelope=MockDiscourseEnvelope.create("QUESTION"),
            phase_minus_one=MockPhaseMinusOneEnvelope.create("DETACHED"),
        )
        directive = run_p15_directly(ctx)

        assert directive is not None
        assert directive.mode == InteractionMode.READ_ONLY

    def test_hold_not_escalatable_to_supportive(self):
        """Test: HOLD cannot be escalated to SUPPORTIVE."""
        ctx = MockPipelineContext(
            p6_regime=MockRegimeEnvelope.create("HOLD"),
            p7_discourse_envelope=MockDiscourseEnvelope.create("REFLECTION"),
            phase_minus_one=MockPhaseMinusOneEnvelope.create("REFLEXIVE"),
        )
        directive = run_p15_directly(ctx)

        assert directive is not None
        assert directive.mode == InteractionMode.READ_ONLY

    def test_hold_not_escalatable_to_informative(self):
        """Test: HOLD cannot be escalated to INFORMATIVE."""
        ctx = MockPipelineContext(
            p6_regime=MockRegimeEnvelope.create("HOLD"),
            p7_discourse_envelope=MockDiscourseEnvelope.create("EXPLANATION"),
            phase_minus_one=MockPhaseMinusOneEnvelope.create("DETACHED"),
        )
        directive = run_p15_directly(ctx)

        assert directive is not None
        assert directive.mode == InteractionMode.READ_ONLY

    def test_hold_source_reason_mentions_hold(self):
        """Test: HOLD mode has appropriate source reason."""
        ctx = make_hold_context()
        directive = run_p15_directly(ctx)

        assert directive is not None
        assert "HOLD" in directive.source_reason

    def test_hold_not_blocked(self):
        """Test: HOLD regime is not blocked."""
        ctx = make_hold_context()
        directive = run_p15_directly(ctx)

        assert directive is not None
        assert directive.blocked is False


# ============================================================================
# B. BLOCKED STATE TESTS
# ============================================================================


class TestBlockedState:
    """Tests for BLOCKED state behavior."""

    def test_blocked_produces_ack_only(self):
        """Test: BLOCKED state -> ACK_ONLY mode."""
        ctx = make_blocked_context()
        directive = run_p15_directly(ctx)

        assert directive is not None
        assert directive.mode == InteractionMode.ACK_ONLY

    def test_blocked_takes_precedence_over_hold(self):
        """Test: BLOCKED takes precedence over HOLD regime."""
        ctx = MockPipelineContext(
            p6_regime=MockRegimeEnvelope.create("HOLD"),
            p7_discourse_envelope=MockDiscourseEnvelope.create("DEFERRAL"),
            phase_minus_one=MockPhaseMinusOneEnvelope.create("UNKNOWN", blocked=True),
        )
        directive = run_p15_directly(ctx)

        assert directive is not None
        assert directive.mode == InteractionMode.ACK_ONLY

    def test_blocked_sets_blocked_flag(self):
        """Test: BLOCKED state sets blocked=True in directive."""
        ctx = make_blocked_context()
        directive = run_p15_directly(ctx)

        assert directive is not None
        assert directive.blocked is True

    def test_blocked_via_p13(self):
        """Test: BLOCKED via P13 safety envelope."""
        ctx = MockPipelineContext(
            p6_regime=MockRegimeEnvelope.create("INFORM"),
            p7_discourse_envelope=MockDiscourseEnvelope.create("EXPLANATION"),
            phase_minus_one=MockPhaseMinusOneEnvelope.create("DETACHED"),
            p13_safety_envelope=MockP13SafetyEnvelope(_is_blocked=True),
        )
        directive = run_p15_directly(ctx)

        assert directive is not None
        assert directive.mode == InteractionMode.ACK_ONLY
        assert directive.blocked is True

    def test_blocked_source_reason_mentions_blocked(self):
        """Test: BLOCKED mode has appropriate source reason."""
        ctx = make_blocked_context()
        directive = run_p15_directly(ctx)

        assert directive is not None
        assert "BLOCKED" in directive.source_reason


# ============================================================================
# C. DEFERRAL DISCOURSE TESTS
# ============================================================================


class TestDeferralDiscourse:
    """Tests for DEFERRAL discourse behavior."""

    def test_deferral_produces_ack_only(self):
        """Test: DEFERRAL discourse -> ACK_ONLY mode."""
        ctx = make_deferral_context()
        directive = run_p15_directly(ctx)

        assert directive is not None
        assert directive.mode == InteractionMode.ACK_ONLY

    def test_deferral_not_blocked(self):
        """Test: DEFERRAL discourse is not blocked."""
        ctx = make_deferral_context()
        directive = run_p15_directly(ctx)

        assert directive is not None
        assert directive.blocked is False

    def test_deferral_source_reason_mentions_deferral(self):
        """Test: DEFERRAL mode has appropriate source reason."""
        ctx = make_deferral_context()
        directive = run_p15_directly(ctx)

        assert directive is not None
        assert "DEFERRAL" in directive.source_reason

    def test_deferral_with_reflexive_still_ack_only(self):
        """Test: DEFERRAL with REFLEXIVE grounding still ACK_ONLY."""
        ctx = MockPipelineContext(
            p6_regime=MockRegimeEnvelope.create("DE_ESCALATE"),
            p7_discourse_envelope=MockDiscourseEnvelope.create("DEFERRAL"),
            phase_minus_one=MockPhaseMinusOneEnvelope.create("REFLEXIVE"),
        )
        directive = run_p15_directly(ctx)

        assert directive is not None
        assert directive.mode == InteractionMode.ACK_ONLY


# ============================================================================
# D. QUESTION DISCOURSE TESTS
# ============================================================================


class TestQuestionDiscourse:
    """Tests for QUESTION discourse behavior."""

    def test_question_produces_clarifying(self):
        """Test: QUESTION discourse -> CLARIFYING mode."""
        ctx = make_question_context()
        directive = run_p15_directly(ctx)

        assert directive is not None
        assert directive.mode == InteractionMode.CLARIFYING

    def test_clarifying_allows_questions(self):
        """Test: CLARIFYING mode allows questions."""
        ctx = make_question_context()
        directive = run_p15_directly(ctx)

        assert directive is not None
        assert directive.allows_questions() is True

    def test_question_source_reason_mentions_question(self):
        """Test: QUESTION mode has appropriate source reason."""
        ctx = make_question_context()
        directive = run_p15_directly(ctx)

        assert directive is not None
        assert "QUESTION" in directive.source_reason

    def test_question_not_blocked(self):
        """Test: QUESTION discourse is not blocked."""
        ctx = make_question_context()
        directive = run_p15_directly(ctx)

        assert directive is not None
        assert directive.blocked is False


# ============================================================================
# E. REFLEXIVE + SUPPORTIVE REGIME TESTS
# ============================================================================


class TestSupportiveMode:
    """Tests for SUPPORTIVE mode behavior."""

    def test_reflexive_de_escalate_produces_supportive(self):
        """Test: REFLEXIVE + DE_ESCALATE -> SUPPORTIVE mode."""
        ctx = make_supportive_context()
        directive = run_p15_directly(ctx)

        assert directive is not None
        assert directive.mode == InteractionMode.SUPPORTIVE

    def test_reflexive_stabilize_produces_supportive(self):
        """Test: REFLEXIVE + STABILIZE -> SUPPORTIVE mode."""
        ctx = make_supportive_stabilize_context()
        directive = run_p15_directly(ctx)

        assert directive is not None
        assert directive.mode == InteractionMode.SUPPORTIVE

    def test_supportive_allows_support(self):
        """Test: SUPPORTIVE mode allows support."""
        ctx = make_supportive_context()
        directive = run_p15_directly(ctx)

        assert directive is not None
        assert directive.allows_support() is True

    def test_supportive_not_clarifying(self):
        """Test: SUPPORTIVE mode does not allow questions."""
        ctx = make_supportive_context()
        directive = run_p15_directly(ctx)

        assert directive is not None
        assert directive.allows_questions() is False

    def test_supportive_source_reason_mentions_reflexive(self):
        """Test: SUPPORTIVE mode has appropriate source reason."""
        ctx = make_supportive_context()
        directive = run_p15_directly(ctx)

        assert directive is not None
        assert "REFLEXIVE" in directive.source_reason

    def test_relational_de_escalate_not_supportive(self):
        """Test: RELATIONAL + DE_ESCALATE does NOT produce SUPPORTIVE."""
        ctx = MockPipelineContext(
            p6_regime=MockRegimeEnvelope.create("DE_ESCALATE"),
            p7_discourse_envelope=MockDiscourseEnvelope.create("REFLECTION"),
            phase_minus_one=MockPhaseMinusOneEnvelope.create("RELATIONAL"),
        )
        directive = run_p15_directly(ctx)

        assert directive is not None
        assert directive.mode != InteractionMode.SUPPORTIVE

    def test_reflexive_inform_not_supportive(self):
        """Test: REFLEXIVE + INFORM does NOT produce SUPPORTIVE."""
        ctx = MockPipelineContext(
            p6_regime=MockRegimeEnvelope.create("INFORM"),
            p7_discourse_envelope=MockDiscourseEnvelope.create("REFLECTION"),
            phase_minus_one=MockPhaseMinusOneEnvelope.create("REFLEXIVE"),
        )
        directive = run_p15_directly(ctx)

        assert directive is not None
        assert directive.mode != InteractionMode.SUPPORTIVE


# ============================================================================
# F. DETACHED + EXPLANATION TESTS
# ============================================================================


class TestInformativeMode:
    """Tests for INFORMATIVE mode behavior."""

    def test_detached_explanation_produces_informative(self):
        """Test: DETACHED + EXPLANATION -> INFORMATIVE mode."""
        ctx = make_informative_context()
        directive = run_p15_directly(ctx)

        assert directive is not None
        assert directive.mode == InteractionMode.INFORMATIVE

    def test_informative_allows_information(self):
        """Test: INFORMATIVE mode allows information."""
        ctx = make_informative_context()
        directive = run_p15_directly(ctx)

        assert directive is not None
        assert directive.allows_information() is True

    def test_informative_allows_support(self):
        """Test: INFORMATIVE mode allows support."""
        ctx = make_informative_context()
        directive = run_p15_directly(ctx)

        assert directive is not None
        assert directive.allows_support() is True

    def test_informative_not_clarifying(self):
        """Test: INFORMATIVE mode does not allow questions."""
        ctx = make_informative_context()
        directive = run_p15_directly(ctx)

        assert directive is not None
        assert directive.allows_questions() is False

    def test_informative_source_reason_mentions_detached(self):
        """Test: INFORMATIVE mode has appropriate source reason."""
        ctx = make_informative_context()
        directive = run_p15_directly(ctx)

        assert directive is not None
        assert "DETACHED" in directive.source_reason

    def test_reflexive_explanation_not_informative(self):
        """Test: REFLEXIVE + EXPLANATION does NOT produce INFORMATIVE."""
        ctx = MockPipelineContext(
            p6_regime=MockRegimeEnvelope.create("INFORM"),
            p7_discourse_envelope=MockDiscourseEnvelope.create("EXPLANATION"),
            phase_minus_one=MockPhaseMinusOneEnvelope.create("REFLEXIVE"),
        )
        directive = run_p15_directly(ctx)

        assert directive is not None
        assert directive.mode != InteractionMode.INFORMATIVE

    def test_detached_reflection_not_informative(self):
        """Test: DETACHED + REFLECTION does NOT produce INFORMATIVE."""
        ctx = MockPipelineContext(
            p6_regime=MockRegimeEnvelope.create("INFORM"),
            p7_discourse_envelope=MockDiscourseEnvelope.create("REFLECTION"),
            phase_minus_one=MockPhaseMinusOneEnvelope.create("DETACHED"),
        )
        directive = run_p15_directly(ctx)

        assert directive is not None
        assert directive.mode != InteractionMode.INFORMATIVE


# ============================================================================
# G. FALLBACK TESTS
# ============================================================================


class TestFallback:
    """Tests for fallback behavior."""

    def test_unknown_combination_produces_read_only(self):
        """Test: Unknown combination -> READ_ONLY mode."""
        ctx = make_fallback_context()
        directive = run_p15_directly(ctx)

        assert directive is not None
        assert directive.mode == InteractionMode.READ_ONLY

    def test_missing_p6_produces_read_only(self):
        """Test: Missing P6 -> READ_ONLY mode."""
        ctx = MockPipelineContext(
            p6_regime=None,
            p7_discourse_envelope=MockDiscourseEnvelope.create("EXPLANATION"),
        )
        directive = run_p15_directly(ctx)

        assert directive is not None
        assert directive.mode == InteractionMode.READ_ONLY

    def test_missing_p7_produces_read_only(self):
        """Test: Missing P7 -> READ_ONLY mode."""
        ctx = MockPipelineContext(
            p6_regime=MockRegimeEnvelope.create("INFORM"),
            p7_discourse_envelope=None,
        )
        directive = run_p15_directly(ctx)

        assert directive is not None
        assert directive.mode == InteractionMode.READ_ONLY

    def test_missing_po1_produces_fallback(self):
        """Test: Missing PO1 -> fallback to READ_ONLY."""
        ctx = MockPipelineContext(
            p6_regime=MockRegimeEnvelope.create("INFORM"),
            p7_discourse_envelope=MockDiscourseEnvelope.create("EXPLANATION"),
            phase_minus_one=None,
        )
        directive = run_p15_directly(ctx)

        assert directive is not None
        # Without DETACHED grounding, EXPLANATION doesn't trigger INFORMATIVE
        assert directive.mode == InteractionMode.READ_ONLY

    def test_empty_context_produces_read_only(self):
        """Test: Empty context -> READ_ONLY mode."""
        ctx = MockPipelineContext()
        directive = run_p15_directly(ctx)

        assert directive is not None
        assert directive.mode == InteractionMode.READ_ONLY

    def test_fallback_source_reason_mentions_fallback(self):
        """Test: Fallback mode has appropriate source reason."""
        ctx = make_fallback_context()
        directive = run_p15_directly(ctx)

        assert directive is not None
        assert "allback" in directive.source_reason.lower()


# ============================================================================
# H. DETERMINISM TESTS
# ============================================================================


class TestDeterminism:
    """Tests for deterministic behavior."""

    def test_same_input_same_output(self):
        """Test: Same input produces same output."""
        ctx = make_informative_context()

        resolver = P15InteractionResolver()

        with patch.object(resolver, '_get_timestamp_utc', return_value="2024-01-01T00:00:00+00:00"):
            directive1 = resolver.resolve(ctx)
            directive2 = resolver.resolve(ctx)

        assert directive1.mode == directive2.mode
        assert directive1.source_reason == directive2.source_reason
        assert directive1.blocked == directive2.blocked

    def test_resolver_stateless(self):
        """Test: Resolver is stateless."""
        resolver1 = P15InteractionResolver()
        resolver2 = P15InteractionResolver()

        ctx = make_informative_context()

        with patch.object(resolver1, '_get_timestamp_utc', return_value="2024-01-01T00:00:00+00:00"):
            with patch.object(resolver2, '_get_timestamp_utc', return_value="2024-01-01T00:00:00+00:00"):
                directive1 = resolver1.resolve(ctx)
                directive2 = resolver2.resolve(ctx)

        assert directive1.mode == directive2.mode

    def test_deterministic_for_hold(self):
        """Test: HOLD produces deterministic output."""
        ctx1 = make_hold_context()
        ctx2 = make_hold_context()

        directive1 = run_p15_directly(ctx1)
        directive2 = run_p15_directly(ctx2)

        assert directive1.mode == directive2.mode
        assert directive1.blocked == directive2.blocked

    def test_deterministic_for_blocked(self):
        """Test: BLOCKED produces deterministic output."""
        ctx1 = make_blocked_context()
        ctx2 = make_blocked_context()

        directive1 = run_p15_directly(ctx1)
        directive2 = run_p15_directly(ctx2)

        assert directive1.mode == directive2.mode
        assert directive1.blocked == directive2.blocked

    def test_resolve_interaction_mode_deterministic(self):
        """Test: Standalone resolve function is deterministic."""
        mode1 = resolve_interaction_mode("INFORM", "EXPLANATION", "DETACHED", False)
        mode2 = resolve_interaction_mode("INFORM", "EXPLANATION", "DETACHED", False)

        assert mode1 == mode2 == InteractionMode.INFORMATIVE


# ============================================================================
# I. NO ESCALATION TESTS
# ============================================================================


class TestNoEscalation:
    """Tests for mode escalation prevention."""

    def test_cannot_escalate_from_blocked(self):
        """Test: Cannot escalate from BLOCKED state."""
        # Even with all triggers for INFORMATIVE, BLOCKED wins
        ctx = MockPipelineContext(
            p6_regime=MockRegimeEnvelope.create("INFORM"),
            p7_discourse_envelope=MockDiscourseEnvelope.create("EXPLANATION"),
            phase_minus_one=MockPhaseMinusOneEnvelope.create("DETACHED", blocked=True),
        )
        directive = run_p15_directly(ctx)

        assert directive.mode == InteractionMode.ACK_ONLY

    def test_cannot_escalate_from_hold(self):
        """Test: Cannot escalate from HOLD regime."""
        # Even with QUESTION discourse, HOLD wins
        ctx = MockPipelineContext(
            p6_regime=MockRegimeEnvelope.create("HOLD"),
            p7_discourse_envelope=MockDiscourseEnvelope.create("QUESTION"),
            phase_minus_one=MockPhaseMinusOneEnvelope.create("DETACHED"),
        )
        directive = run_p15_directly(ctx)

        assert directive.mode == InteractionMode.READ_ONLY

    def test_cannot_escalate_from_deferral(self):
        """Test: Cannot escalate from DEFERRAL discourse."""
        # Even with all triggers for INFORMATIVE, DEFERRAL wins
        ctx = MockPipelineContext(
            p6_regime=MockRegimeEnvelope.create("INFORM"),
            p7_discourse_envelope=MockDiscourseEnvelope.create("DEFERRAL"),
            phase_minus_one=MockPhaseMinusOneEnvelope.create("DETACHED"),
        )
        directive = run_p15_directly(ctx)

        assert directive.mode == InteractionMode.ACK_ONLY

    def test_rule_priority_blocked_over_hold(self):
        """Test: BLOCKED takes priority over HOLD."""
        ctx = MockPipelineContext(
            p6_regime=MockRegimeEnvelope.create("HOLD"),
            p7_discourse_envelope=MockDiscourseEnvelope.create("DEFERRAL"),
            phase_minus_one=MockPhaseMinusOneEnvelope.create("UNKNOWN", blocked=True),
        )
        directive = run_p15_directly(ctx)

        # BLOCKED -> ACK_ONLY (not READ_ONLY from HOLD)
        assert directive.mode == InteractionMode.ACK_ONLY

    def test_rule_priority_hold_over_question(self):
        """Test: HOLD takes priority over QUESTION discourse."""
        mode = resolve_interaction_mode("HOLD", "QUESTION", "DETACHED", False)

        assert mode == InteractionMode.READ_ONLY

    def test_rule_priority_deferral_over_explanation(self):
        """Test: DEFERRAL takes priority over EXPLANATION discourse."""
        mode = resolve_interaction_mode("INFORM", "DEFERRAL", "DETACHED", False)

        assert mode == InteractionMode.ACK_ONLY


# ============================================================================
# J. SCHEMA VALIDATION TESTS
# ============================================================================


class TestSchemaValidation:
    """Tests for schema validation."""

    def test_valid_directive_construction(self):
        """Test: Valid InteractionDirective construction."""
        directive = InteractionDirective(
            mode=InteractionMode.INFORMATIVE,
            source_reason="Test reason",
            blocked=False,
            source_regime="INFORM",
            source_discourse_act="EXPLANATION",
            source_grounding_mode="DETACHED",
        )

        assert directive.mode == InteractionMode.INFORMATIVE
        assert directive.is_informative() is True

    def test_directive_immutability(self):
        """Test: InteractionDirective is frozen/immutable."""
        directive = get_read_only_directive()

        with pytest.raises(Exception):  # FrozenInstanceError
            directive.mode = InteractionMode.INFORMATIVE

    def test_blocked_requires_ack_only(self):
        """Test: blocked=True requires mode=ACK_ONLY."""
        with pytest.raises(ValueError, match="blocked=True requires mode=ACK_ONLY"):
            InteractionDirective(
                mode=InteractionMode.INFORMATIVE,
                source_reason="Test reason",
                blocked=True,
            )

    def test_hold_requires_read_only(self):
        """Test: HOLD regime requires mode=READ_ONLY."""
        with pytest.raises(ValueError, match="HOLD regime requires mode=READ_ONLY"):
            InteractionDirective(
                mode=InteractionMode.INFORMATIVE,
                source_reason="Test reason",
                blocked=False,
                source_regime="HOLD",
            )

    def test_empty_source_reason_rejected(self):
        """Test: Empty source_reason is rejected."""
        with pytest.raises(ValueError, match="source_reason must be a non-empty string"):
            InteractionDirective(
                mode=InteractionMode.READ_ONLY,
                source_reason="",
                blocked=False,
            )

    def test_directive_to_dict(self):
        """Test: InteractionDirective serialization."""
        directive = get_read_only_directive(
            source_regime="HOLD",
            source_discourse_act="DEFERRAL",
        )
        d = directive.to_dict()

        assert d["mode"] == "READ_ONLY"
        assert d["is_read_only"] is True
        assert d["blocked"] is False
        assert d["version"] == P15_VERSION

    def test_get_read_only_directive_helper(self):
        """Test: get_read_only_directive helper function."""
        directive = get_read_only_directive(
            source_reason="Custom reason",
            source_regime="HOLD",
        )

        assert directive.is_read_only() is True
        assert directive.source_reason == "Custom reason"

    def test_get_ack_only_directive_helper(self):
        """Test: get_ack_only_directive helper function."""
        directive = get_ack_only_directive(
            source_reason="Custom blocked reason",
            blocked=True,
        )

        assert directive.is_ack_only() is True
        assert directive.blocked is True


# ============================================================================
# K. INTEGRATION TESTS
# ============================================================================


class TestIntegration:
    """Tests for P15 integration functions."""

    def test_maybe_run_p15_attaches_directive(self):
        """Test: maybe_run_p15 attaches directive to context."""
        ctx = make_informative_context()

        result_ctx = maybe_run_p15(ctx)

        assert result_ctx.interaction_directive is not None
        assert isinstance(result_ctx.interaction_directive, InteractionDirective)

    def test_maybe_run_p15_idempotent(self):
        """Test: maybe_run_p15 is idempotent."""
        ctx = make_informative_context()

        maybe_run_p15(ctx)
        first_directive = ctx.interaction_directive
        first_timestamp = first_directive.timestamp_utc

        # Run again
        maybe_run_p15(ctx)
        second_directive = ctx.interaction_directive

        # Should be the same object (idempotent)
        assert second_directive.timestamp_utc == first_timestamp

    def test_maybe_run_p15_no_p6_returns_read_only(self):
        """Test: maybe_run_p15 with no P6 returns READ_ONLY directive."""
        ctx = MockPipelineContext(p6_regime=None)
        result_ctx = maybe_run_p15(ctx)

        assert result_ctx.interaction_directive is not None
        assert result_ctx.interaction_directive.is_read_only() is True

    def test_run_p15_directly_no_context_modification(self):
        """Test: run_p15_directly doesn't modify context."""
        ctx = make_informative_context()

        directive = run_p15_directly(ctx)

        assert directive is not None
        assert ctx.interaction_directive is None  # Not attached

    def test_accessor_functions_no_directive(self):
        """Test: Accessor functions with no directive."""
        ctx = MockPipelineContext()

        assert is_read_only(ctx) is True  # Conservative default
        assert is_ack_only(ctx) is False
        assert is_supportive(ctx) is False
        assert is_clarifying(ctx) is False
        assert is_informative(ctx) is False
        assert allows_questions(ctx) is False
        assert allows_information(ctx) is False
        assert allows_support(ctx) is False
        assert is_blocked(ctx) is False

    def test_accessor_functions_with_directive(self):
        """Test: Accessor functions with directive."""
        ctx = make_informative_context()
        maybe_run_p15(ctx)

        assert is_read_only(ctx) is False
        assert is_informative(ctx) is True
        assert allows_information(ctx) is True
        assert get_mode(ctx) == InteractionMode.INFORMATIVE

    def test_singleton_resolver(self):
        """Test: Singleton resolver pattern."""
        r1 = get_p15_resolver()
        r2 = get_p15_resolver()
        assert r1 is r2


# ============================================================================
# L. HELPER METHOD TESTS
# ============================================================================


class TestHelperMethods:
    """Tests for InteractionDirective helper methods."""

    def test_is_read_only(self):
        """Test: is_read_only method."""
        directive = get_read_only_directive()
        assert directive.is_read_only() is True
        assert directive.is_ack_only() is False

    def test_is_ack_only(self):
        """Test: is_ack_only method."""
        directive = get_ack_only_directive()
        assert directive.is_ack_only() is True
        assert directive.is_read_only() is False

    def test_is_supportive(self):
        """Test: is_supportive method."""
        directive = InteractionDirective(
            mode=InteractionMode.SUPPORTIVE,
            source_reason="Test",
            blocked=False,
        )
        assert directive.is_supportive() is True

    def test_is_clarifying(self):
        """Test: is_clarifying method."""
        directive = InteractionDirective(
            mode=InteractionMode.CLARIFYING,
            source_reason="Test",
            blocked=False,
        )
        assert directive.is_clarifying() is True

    def test_is_informative(self):
        """Test: is_informative method."""
        directive = InteractionDirective(
            mode=InteractionMode.INFORMATIVE,
            source_reason="Test",
            blocked=False,
        )
        assert directive.is_informative() is True

    def test_allows_questions_only_clarifying(self):
        """Test: Only CLARIFYING allows questions."""
        assert InteractionDirective(
            mode=InteractionMode.CLARIFYING,
            source_reason="Test",
            blocked=False,
        ).allows_questions() is True

        assert get_read_only_directive().allows_questions() is False
        assert get_ack_only_directive().allows_questions() is False

    def test_allows_information_only_informative(self):
        """Test: Only INFORMATIVE allows information."""
        assert InteractionDirective(
            mode=InteractionMode.INFORMATIVE,
            source_reason="Test",
            blocked=False,
        ).allows_information() is True

        assert get_read_only_directive().allows_information() is False

    def test_allows_support(self):
        """Test: SUPPORTIVE and INFORMATIVE allow support."""
        supportive = InteractionDirective(
            mode=InteractionMode.SUPPORTIVE,
            source_reason="Test",
            blocked=False,
        )
        informative = InteractionDirective(
            mode=InteractionMode.INFORMATIVE,
            source_reason="Test",
            blocked=False,
        )

        assert supportive.allows_support() is True
        assert informative.allows_support() is True
        assert get_read_only_directive().allows_support() is False


# ============================================================================
# M. RULE CONSTANTS TESTS
# ============================================================================


class TestRuleConstants:
    """Tests for rule constant sets."""

    def test_supportive_regimes_contains_de_escalate(self):
        """Test: SUPPORTIVE_REGIMES contains DE_ESCALATE."""
        assert "DE_ESCALATE" in SUPPORTIVE_REGIMES

    def test_supportive_regimes_contains_stabilize(self):
        """Test: SUPPORTIVE_REGIMES contains STABILIZE."""
        assert "STABILIZE" in SUPPORTIVE_REGIMES

    def test_hold_regimes_contains_hold(self):
        """Test: HOLD_REGIMES contains HOLD."""
        assert "HOLD" in HOLD_REGIMES

    def test_deferral_discourse_acts_contains_deferral(self):
        """Test: DEFERRAL_DISCOURSE_ACTS contains DEFERRAL."""
        assert "DEFERRAL" in DEFERRAL_DISCOURSE_ACTS

    def test_question_discourse_acts_contains_question(self):
        """Test: QUESTION_DISCOURSE_ACTS contains QUESTION."""
        assert "QUESTION" in QUESTION_DISCOURSE_ACTS

    def test_explanation_discourse_acts_contains_explanation(self):
        """Test: EXPLANATION_DISCOURSE_ACTS contains EXPLANATION."""
        assert "EXPLANATION" in EXPLANATION_DISCOURSE_ACTS

    def test_reflexive_grounding_modes_contains_reflexive(self):
        """Test: REFLEXIVE_GROUNDING_MODES contains REFLEXIVE."""
        assert "REFLEXIVE" in REFLEXIVE_GROUNDING_MODES

    def test_detached_grounding_modes_contains_detached(self):
        """Test: DETACHED_GROUNDING_MODES contains DETACHED."""
        assert "DETACHED" in DETACHED_GROUNDING_MODES


# ============================================================================
# N. DEBUG INFO TESTS
# ============================================================================


class TestDebugInfo:
    """Tests for debug information."""

    def test_debug_contains_rule_applied(self):
        """Test: Debug info contains rule_applied."""
        ctx = make_informative_context()
        directive = run_p15_directly(ctx)

        assert directive is not None
        assert "rule_applied" in directive.debug

    def test_debug_contains_regime(self):
        """Test: Debug info contains regime."""
        ctx = make_informative_context()
        directive = run_p15_directly(ctx)

        assert directive is not None
        assert "regime" in directive.debug
        assert directive.debug["regime"] == "INFORM"

    def test_debug_contains_discourse_act(self):
        """Test: Debug info contains discourse_act."""
        ctx = make_informative_context()
        directive = run_p15_directly(ctx)

        assert directive is not None
        assert "discourse_act" in directive.debug
        assert directive.debug["discourse_act"] == "EXPLANATION"

    def test_debug_contains_grounding_mode(self):
        """Test: Debug info contains grounding_mode."""
        ctx = make_informative_context()
        directive = run_p15_directly(ctx)

        assert directive is not None
        assert "grounding_mode" in directive.debug
        assert directive.debug["grounding_mode"] == "DETACHED"

    def test_debug_rule_6_for_informative(self):
        """Test: INFORMATIVE mode debug shows rule 6."""
        ctx = make_informative_context()
        directive = run_p15_directly(ctx)

        assert directive is not None
        assert directive.debug["rule_applied"] == "rule_6_detached_explanation"

    def test_debug_rule_5_for_supportive(self):
        """Test: SUPPORTIVE mode debug shows rule 5."""
        ctx = make_supportive_context()
        directive = run_p15_directly(ctx)

        assert directive is not None
        assert directive.debug["rule_applied"] == "rule_5_reflexive_supportive"

    def test_debug_rule_4_for_clarifying(self):
        """Test: CLARIFYING mode debug shows rule 4."""
        ctx = make_question_context()
        directive = run_p15_directly(ctx)

        assert directive is not None
        assert directive.debug["rule_applied"] == "rule_4_question_discourse"


# ============================================================================
# O. EDGE CASE TESTS
# ============================================================================


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_unknown_regime_handled(self):
        """Test: Unknown regime handled gracefully."""
        ctx = MockPipelineContext(
            p6_regime=MockRegimeEnvelope.create("UNKNOWN_REGIME"),
            p7_discourse_envelope=MockDiscourseEnvelope.create("UNKNOWN"),
        )
        directive = run_p15_directly(ctx)

        # Should produce valid directive (not crash)
        assert directive is not None

    def test_minimal_context(self):
        """Test: Minimal context produces valid directive."""
        ctx = MockPipelineContext()
        directive = run_p15_directly(ctx)

        assert directive is not None
        assert directive.mode == InteractionMode.READ_ONLY

    def test_all_interaction_modes_valid(self):
        """Test: All InteractionMode enum values are valid."""
        for mode in InteractionMode:
            assert isinstance(mode.value, str)
            assert len(mode.value) > 0

    def test_version_constant_set(self):
        """Test: P15_VERSION constant is set."""
        assert P15_VERSION is not None
        assert isinstance(P15_VERSION, str)
        assert len(P15_VERSION) > 0
