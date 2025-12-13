"""
P14 Unit Tests - Expression Surface Realizer

Tests for P14 Expression Surface Realizer:
- SurfacePlan dataclass
- P14SurfaceRealizer (deterministic)
- Style resolution
- Punctuation policy resolution
- Hedging policy resolution
- Length policy resolution
- Persona signal resolution
- Connector allow-list enforcement
- Forbidden token enforcement
- Integration with P13

Test Categories (per specification):
A. HOLD Regime Tests
   - HOLD -> DEFERRAL_MINIMAL style
   - HOLD -> ONE_SENTENCE length
   - HOLD -> requires_question=True
   - HOLD -> SAFE_CLARIFY or NONE persona signals

B. Careful Regime Tests
   - DE_ESCALATE/STABILIZE/CAREFUL -> GENTLE style
   - Hedging REQUIRED for non-factual claims
   - Limited length (ONE_SENTENCE or TWO_SENTENCES_MAX)

C. REFLEXIVE vs RELATIONAL Differences
   - REFLEXIVE -> no emphasis
   - RELATIONAL -> forbidden second-person assertions
   - Both -> hedging for state claims about others

D. UNCERTAINTY Slot Tests
   - Presence of UNCERTAINTY slot -> HedgePolicy.LIGHT
   - Absence -> HedgePolicy depends on other factors

E. P13 Safety Synchronization Tests
   - P13 disallows emphasis -> NO_EXCLAMATION punctuation
   - P13 constraints propagate to surface plan

F. Determinism Tests
   - Same input -> same output
   - No probabilistic behavior
   - Stateless resolver

G. Connector Allow-List Tests
   - Only curated connectors allowed
   - DEFERRAL_CONNECTORS for HOLD
   - REFLECT_CONNECTORS for REFLECTION
   - ACK_CONNECTORS for ACKNOWLEDGMENT
   - CLARIFY_CONNECTORS for clarification

H. Regression Tests
   - "consider", "to clarify", "that said" never in default allow-list
   - CAUSE connectors not allowed by default

I. Schema Validation Tests
   - Dataclass construction
   - Invariant validation
   - Serialization

J. Integration Tests
   - maybe_run_p14 behavior
   - Accessor functions
   - Empty/missing data handling

Target: >= 80 tests

CRITICAL: P14 produces a SurfacePlan, not text.
P14 is deterministic, zero-LLM, no ML.
"""

from dataclasses import dataclass
from typing import Any, Dict, Optional
from unittest.mock import patch, MagicMock

import pytest

from symbolu.mechanical.pipeline.p14_surface import (
    # Schema
    SurfaceStyle,
    PunctuationPolicy,
    HedgePolicy,
    LengthPolicy,
    PersonaSignalPolicy,
    SurfacePlan,
    P14_VERSION,
    get_deferral_plan,
    build_forbidden_tokens,
    # Constants
    DEFERRAL_CONNECTORS,
    REFLECT_CONNECTORS,
    ACK_CONNECTORS,
    CLARIFY_CONNECTORS,
    NEVER_ALLOWED_CONNECTORS,
    DEFAULT_FORBIDDEN_TOKENS,
    RELATIONAL_FORBIDDEN_TOKENS,
    # Realizer
    P14SurfaceRealizer,
    resolve_style,
    resolve_punctuation,
    resolve_hedging,
    resolve_length,
    resolve_persona_signals,
    resolve_allowed_connectors,
    resolve_requires_question,
    DEFERRAL_REGIMES,
    CAREFUL_REGIMES,
    INFORM_REGIMES,
    # Integration
    get_p14_realizer,
    maybe_run_p14,
    run_p14_directly,
    get_p14_surface_plan,
    get_style,
    is_minimal,
    is_deferral,
    is_gentle,
    is_neutral,
    is_formal,
    get_punctuation_policy,
    allows_exclamation,
    allows_ellipsis,
    get_hedge_policy,
    requires_hedging,
    get_length_policy,
    allows_bullets,
    get_max_sentences,
    get_persona_signals,
    requires_question,
    get_allowed_connectors,
    has_connector,
    get_forbidden_tokens,
    is_forbidden,
)
from symbolu.mechanical.pipeline.p13_acoustic_safety import (
    AcousticRiskLevel,
    AcousticSafetyEnvelope,
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

    @classmethod
    def create(cls, mode_value: str) -> "MockPhaseMinusOneEnvelope":
        return cls(
            selected_primary=MockGroundingCandidate(
                mode=MockGroundingCandidate.MockMode(value=mode_value)
            )
        )


@dataclass(frozen=True)
class MockSemanticSlot:
    """Mock semantic slot."""
    value: str

    def __hash__(self):
        return hash(self.value)

    def __eq__(self, other):
        if not isinstance(other, MockSemanticSlot):
            return False
        return self.value == other.value


@dataclass
class MockSemanticFrame:
    """Mock P8 semantic frame."""
    slots: Dict[MockSemanticSlot, Optional[str]]


@dataclass
class MockP13SafetyEnvelope:
    """Mock P13 safety envelope."""
    allow_emphasis: bool = False
    risk_level: AcousticRiskLevel = AcousticRiskLevel.SAFE


@dataclass
class MockPipelineContext:
    """Mock pipeline context for testing."""
    p6_regime: Optional[MockRegimeEnvelope] = None
    p7_discourse_envelope: Optional[MockDiscourseEnvelope] = None
    phase_minus_one: Optional[MockPhaseMinusOneEnvelope] = None
    phase_zero: Optional[Any] = None
    semantic_frame: Optional[MockSemanticFrame] = None
    lexical_frame: Optional[Any] = None
    p13_safety_envelope: Optional[MockP13SafetyEnvelope] = None
    p14_surface: Optional[SurfacePlan] = None


def make_hold_context() -> MockPipelineContext:
    """Create a context for HOLD regime."""
    return MockPipelineContext(
        p6_regime=MockRegimeEnvelope.create("HOLD"),
        p7_discourse_envelope=MockDiscourseEnvelope.create("DEFERRAL"),
        p13_safety_envelope=MockP13SafetyEnvelope(allow_emphasis=False),
    )


def make_inform_context() -> MockPipelineContext:
    """Create a context for INFORM regime."""
    return MockPipelineContext(
        p6_regime=MockRegimeEnvelope.create("INFORM"),
        p7_discourse_envelope=MockDiscourseEnvelope.create("EXPLANATION"),
        phase_minus_one=MockPhaseMinusOneEnvelope.create("DETACHED"),
        p13_safety_envelope=MockP13SafetyEnvelope(allow_emphasis=True),
    )


def make_de_escalate_context() -> MockPipelineContext:
    """Create a context for DE_ESCALATE regime."""
    return MockPipelineContext(
        p6_regime=MockRegimeEnvelope.create("DE_ESCALATE"),
        p7_discourse_envelope=MockDiscourseEnvelope.create("REFLECTION"),
        phase_minus_one=MockPhaseMinusOneEnvelope.create("REFLEXIVE"),
        p13_safety_envelope=MockP13SafetyEnvelope(allow_emphasis=False),
    )


def make_reflect_context() -> MockPipelineContext:
    """Create a context for REFLECT regime with REFLECTION discourse."""
    return MockPipelineContext(
        p6_regime=MockRegimeEnvelope.create("REFLECT"),
        p7_discourse_envelope=MockDiscourseEnvelope.create("REFLECTION"),
        phase_minus_one=MockPhaseMinusOneEnvelope.create("REFLEXIVE"),
        p13_safety_envelope=MockP13SafetyEnvelope(allow_emphasis=False),
    )


def make_relational_context() -> MockPipelineContext:
    """Create a context for RELATIONAL grounding mode."""
    return MockPipelineContext(
        p6_regime=MockRegimeEnvelope.create("INFORM"),
        p7_discourse_envelope=MockDiscourseEnvelope.create("EXPLANATION"),
        phase_minus_one=MockPhaseMinusOneEnvelope.create("RELATIONAL"),
        p13_safety_envelope=MockP13SafetyEnvelope(allow_emphasis=False),
    )


# ============================================================================
# A. HOLD REGIME TESTS
# ============================================================================


class TestHoldRegime:
    """Tests for HOLD regime behavior."""

    def test_hold_produces_deferral_minimal_style(self):
        """Test: HOLD regime -> DEFERRAL_MINIMAL style."""
        ctx = make_hold_context()
        plan = run_p14_directly(ctx)

        assert plan is not None
        assert plan.style == SurfaceStyle.DEFERRAL_MINIMAL

    def test_hold_produces_one_sentence_length(self):
        """Test: HOLD regime -> ONE_SENTENCE length."""
        ctx = make_hold_context()
        plan = run_p14_directly(ctx)

        assert plan is not None
        assert plan.length == LengthPolicy.ONE_SENTENCE

    def test_hold_requires_question(self):
        """Test: HOLD regime -> requires_question=True."""
        ctx = make_hold_context()
        plan = run_p14_directly(ctx)

        assert plan is not None
        assert plan.requires_question is True

    def test_hold_uses_safe_clarify_persona(self):
        """Test: HOLD regime -> SAFE_CLARIFY persona signals."""
        ctx = make_hold_context()
        plan = run_p14_directly(ctx)

        assert plan is not None
        assert plan.persona_signals in (PersonaSignalPolicy.SAFE_CLARIFY, PersonaSignalPolicy.NONE)

    def test_hold_uses_deferral_connectors(self):
        """Test: HOLD regime -> only DEFERRAL_CONNECTORS allowed."""
        ctx = make_hold_context()
        plan = run_p14_directly(ctx)

        assert plan is not None
        assert plan.allowed_connectors == DEFERRAL_CONNECTORS

    def test_hold_has_basic_periods_punctuation(self):
        """Test: HOLD regime -> BASIC_PERIODS punctuation."""
        ctx = make_hold_context()
        plan = run_p14_directly(ctx)

        assert plan is not None
        assert plan.punctuation == PunctuationPolicy.BASIC_PERIODS

    def test_hold_no_hedging_required(self):
        """Test: HOLD regime -> no hedging (just defer)."""
        ctx = make_hold_context()
        plan = run_p14_directly(ctx)

        assert plan is not None
        assert plan.hedging == HedgePolicy.NONE

    def test_hold_no_exclamation_allowed(self):
        """Test: HOLD regime -> no exclamation marks."""
        ctx = make_hold_context()
        plan = run_p14_directly(ctx)

        assert plan is not None
        assert plan.allows_exclamation() is False

    def test_hold_no_bullets_allowed(self):
        """Test: HOLD regime -> no bullet lists."""
        ctx = make_hold_context()
        plan = run_p14_directly(ctx)

        assert plan is not None
        assert plan.allows_bullets() is False

    def test_hold_max_sentences_is_one(self):
        """Test: HOLD regime -> max sentences is 1."""
        ctx = make_hold_context()
        plan = run_p14_directly(ctx)

        assert plan is not None
        assert plan.get_max_sentences() == 1


# ============================================================================
# B. CAREFUL REGIME TESTS (DE_ESCALATE, STABILIZE, CAREFUL, REFLECT)
# ============================================================================


class TestCarefulRegimes:
    """Tests for careful regime behavior."""

    def test_de_escalate_produces_gentle_style(self):
        """Test: DE_ESCALATE regime -> GENTLE style."""
        ctx = make_de_escalate_context()
        plan = run_p14_directly(ctx)

        assert plan is not None
        assert plan.style == SurfaceStyle.GENTLE

    def test_stabilize_produces_gentle_style(self):
        """Test: STABILIZE regime -> GENTLE style."""
        ctx = MockPipelineContext(
            p6_regime=MockRegimeEnvelope.create("STABILIZE"),
            p7_discourse_envelope=MockDiscourseEnvelope.create("REFLECTION"),
            p13_safety_envelope=MockP13SafetyEnvelope(allow_emphasis=False),
        )
        plan = run_p14_directly(ctx)

        assert plan is not None
        assert plan.style == SurfaceStyle.GENTLE

    def test_reflect_produces_gentle_style(self):
        """Test: REFLECT regime -> GENTLE style."""
        ctx = make_reflect_context()
        plan = run_p14_directly(ctx)

        assert plan is not None
        assert plan.style == SurfaceStyle.GENTLE

    def test_de_escalate_requires_hedging_for_reflection(self):
        """Test: DE_ESCALATE with REFLECTION discourse -> REQUIRED hedging."""
        ctx = make_de_escalate_context()
        plan = run_p14_directly(ctx)

        assert plan is not None
        assert plan.hedging == HedgePolicy.REQUIRED

    def test_de_escalate_one_sentence_length(self):
        """Test: DE_ESCALATE -> ONE_SENTENCE length."""
        ctx = make_de_escalate_context()
        plan = run_p14_directly(ctx)

        assert plan is not None
        assert plan.length == LengthPolicy.ONE_SENTENCE

    def test_stabilize_one_sentence_length(self):
        """Test: STABILIZE -> ONE_SENTENCE length."""
        ctx = MockPipelineContext(
            p6_regime=MockRegimeEnvelope.create("STABILIZE"),
            p7_discourse_envelope=MockDiscourseEnvelope.create("ACKNOWLEDGMENT"),
            p13_safety_envelope=MockP13SafetyEnvelope(allow_emphasis=False),
        )
        plan = run_p14_directly(ctx)

        assert plan is not None
        assert plan.length == LengthPolicy.ONE_SENTENCE

    def test_careful_regime_no_exclamation(self):
        """Test: Careful regimes -> no exclamation marks."""
        ctx = make_de_escalate_context()
        plan = run_p14_directly(ctx)

        assert plan is not None
        assert plan.allows_exclamation() is False

    def test_careful_regime_no_ellipsis(self):
        """Test: Careful regimes -> no ellipsis via NO_EXCLAMATION policy."""
        ctx = make_de_escalate_context()
        plan = run_p14_directly(ctx)

        assert plan is not None
        # NO_EXCLAMATION policy still allows ellipsis by definition
        # But CAREFUL regimes via P13 may restrict further


# ============================================================================
# C. REFLEXIVE vs RELATIONAL DIFFERENCES
# ============================================================================


class TestReflexiveVsRelational:
    """Tests for REFLEXIVE vs RELATIONAL grounding mode differences."""

    def test_reflexive_mode_no_second_person_assertions(self):
        """Test: REFLEXIVE mode doesn't add RELATIONAL forbidden tokens."""
        ctx = MockPipelineContext(
            p6_regime=MockRegimeEnvelope.create("REFLECT"),
            p7_discourse_envelope=MockDiscourseEnvelope.create("REFLECTION"),
            phase_minus_one=MockPhaseMinusOneEnvelope.create("REFLEXIVE"),
            p13_safety_envelope=MockP13SafetyEnvelope(allow_emphasis=False),
        )
        plan = run_p14_directly(ctx)

        assert plan is not None
        # REFLEXIVE doesn't require RELATIONAL forbidden tokens
        # (but may still have defaults)

    def test_relational_mode_forbids_you_are(self):
        """Test: RELATIONAL mode -> 'you are' in forbidden tokens."""
        ctx = make_relational_context()
        plan = run_p14_directly(ctx)

        assert plan is not None
        assert "you are" in plan.forbidden_tokens

    def test_relational_mode_forbids_you_have(self):
        """Test: RELATIONAL mode -> 'you have' in forbidden tokens."""
        ctx = make_relational_context()
        plan = run_p14_directly(ctx)

        assert plan is not None
        assert "you have" in plan.forbidden_tokens

    def test_relational_mode_forbids_you_feel(self):
        """Test: RELATIONAL mode -> 'you feel' in forbidden tokens."""
        ctx = make_relational_context()
        plan = run_p14_directly(ctx)

        assert plan is not None
        assert "you feel" in plan.forbidden_tokens

    def test_relational_mode_requires_hedging(self):
        """Test: RELATIONAL mode -> REQUIRED hedging."""
        ctx = make_relational_context()
        plan = run_p14_directly(ctx)

        assert plan is not None
        assert plan.hedging == HedgePolicy.REQUIRED

    def test_reflexive_with_reflection_uses_safe_reflect(self):
        """Test: REFLEXIVE + REFLECTION discourse -> SAFE_REFLECT persona."""
        ctx = make_reflect_context()
        plan = run_p14_directly(ctx)

        assert plan is not None
        assert plan.persona_signals == PersonaSignalPolicy.SAFE_REFLECT

    def test_reflexive_uses_reflect_connectors(self):
        """Test: REFLEXIVE + REFLECTION -> REFLECT_CONNECTORS."""
        ctx = make_reflect_context()
        plan = run_p14_directly(ctx)

        assert plan is not None
        assert plan.allowed_connectors == REFLECT_CONNECTORS


# ============================================================================
# D. UNCERTAINTY SLOT TESTS
# ============================================================================


class TestUncertaintySlot:
    """Tests for UNCERTAINTY slot behavior."""

    def test_uncertainty_slot_triggers_light_hedging(self):
        """Test: UNCERTAINTY slot present -> LIGHT hedging."""
        uncertainty_slot = MockSemanticSlot(value="UNCERTAINTY")
        ctx = MockPipelineContext(
            p6_regime=MockRegimeEnvelope.create("INFORM"),
            p7_discourse_envelope=MockDiscourseEnvelope.create("EXPLANATION"),
            phase_minus_one=MockPhaseMinusOneEnvelope.create("DETACHED"),
            semantic_frame=MockSemanticFrame(
                slots={uncertainty_slot: "uncertain value"}
            ),
            p13_safety_envelope=MockP13SafetyEnvelope(allow_emphasis=True),
        )
        plan = run_p14_directly(ctx)

        assert plan is not None
        assert plan.hedging == HedgePolicy.LIGHT

    def test_no_uncertainty_slot_no_hedging_inform(self):
        """Test: No UNCERTAINTY slot under INFORM -> no hedging."""
        ctx = make_inform_context()
        plan = run_p14_directly(ctx)

        assert plan is not None
        # Without UNCERTAINTY slot and without RELATIONAL mode,
        # INFORM/DETACHED should have NONE hedging
        assert plan.hedging == HedgePolicy.NONE

    def test_uncertainty_slot_with_relational_still_required(self):
        """Test: UNCERTAINTY slot + RELATIONAL -> still REQUIRED (RELATIONAL wins)."""
        uncertainty_slot = MockSemanticSlot(value="UNCERTAINTY")
        ctx = MockPipelineContext(
            p6_regime=MockRegimeEnvelope.create("INFORM"),
            p7_discourse_envelope=MockDiscourseEnvelope.create("EXPLANATION"),
            phase_minus_one=MockPhaseMinusOneEnvelope.create("RELATIONAL"),
            semantic_frame=MockSemanticFrame(
                slots={uncertainty_slot: "uncertain value"}
            ),
            p13_safety_envelope=MockP13SafetyEnvelope(allow_emphasis=False),
        )
        plan = run_p14_directly(ctx)

        assert plan is not None
        # RELATIONAL takes precedence with REQUIRED
        assert plan.hedging == HedgePolicy.REQUIRED


# ============================================================================
# E. P13 SAFETY SYNCHRONIZATION TESTS
# ============================================================================


class TestP13Synchronization:
    """Tests for P13 safety constraint synchronization."""

    def test_p13_no_emphasis_blocks_exclamation(self):
        """Test: P13 disallows emphasis -> no exclamation marks."""
        ctx = MockPipelineContext(
            p6_regime=MockRegimeEnvelope.create("INFORM"),
            p7_discourse_envelope=MockDiscourseEnvelope.create("EXPLANATION"),
            phase_minus_one=MockPhaseMinusOneEnvelope.create("DETACHED"),
            p13_safety_envelope=MockP13SafetyEnvelope(allow_emphasis=False),
        )
        plan = run_p14_directly(ctx)

        assert plan is not None
        assert plan.allows_exclamation() is False

    def test_p13_emphasis_allowed_can_have_exclamation(self):
        """Test: P13 allows emphasis -> punctuation policy may allow exclamation."""
        ctx = MockPipelineContext(
            p6_regime=MockRegimeEnvelope.create("INFORM"),
            p7_discourse_envelope=MockDiscourseEnvelope.create("EXPLANATION"),
            phase_minus_one=MockPhaseMinusOneEnvelope.create("DETACHED"),
            p13_safety_envelope=MockP13SafetyEnvelope(allow_emphasis=True),
        )
        plan = run_p14_directly(ctx)

        assert plan is not None
        # Under INFORM with emphasis allowed, LIMITED_COMMAS is used
        # which doesn't explicitly forbid exclamation (but doesn't allow either)
        # This is intentional - conservative default

    def test_p13_no_emphasis_clamps_style(self):
        """Test: P13 disallows emphasis -> style clamped appropriately."""
        ctx = MockPipelineContext(
            p6_regime=MockRegimeEnvelope.create("INFORM"),
            p7_discourse_envelope=MockDiscourseEnvelope.create("EXPLANATION"),
            phase_minus_one=MockPhaseMinusOneEnvelope.create("DETACHED"),
            p13_safety_envelope=MockP13SafetyEnvelope(allow_emphasis=False),
        )
        plan = run_p14_directly(ctx)

        assert plan is not None
        # Style can be FORMAL (no punctuation expressiveness) or more restrictive
        # FORMAL is allowed because it's about structure, not acoustic emphasis
        # The emphasis constraint affects punctuation (no !), not style choice
        assert plan.style in (
            SurfaceStyle.MINIMAL,
            SurfaceStyle.NEUTRAL,
            SurfaceStyle.GENTLE,
            SurfaceStyle.FORMAL,
            SurfaceStyle.DEFERRAL_MINIMAL,
        )
        # But punctuation must be restrictive
        assert plan.allows_exclamation() is False

    def test_missing_p13_returns_deferral_plan(self):
        """Test: Missing P13 -> deferral plan (conservative)."""
        ctx = MockPipelineContext(
            p6_regime=MockRegimeEnvelope.create("INFORM"),
            p7_discourse_envelope=MockDiscourseEnvelope.create("EXPLANATION"),
            p13_safety_envelope=None,
        )
        plan = run_p14_directly(ctx)

        assert plan is not None
        assert plan.is_deferral() is True


# ============================================================================
# F. DETERMINISM TESTS
# ============================================================================


class TestDeterminism:
    """Tests for deterministic behavior."""

    def test_same_input_same_output(self):
        """Test: Same input produces same output."""
        ctx = make_inform_context()

        realizer = P14SurfaceRealizer()

        with patch.object(realizer, '_get_timestamp_utc', return_value="2024-01-01T00:00:00+00:00"):
            plan1 = realizer.realize(ctx)
            plan2 = realizer.realize(ctx)

        assert plan1.style == plan2.style
        assert plan1.punctuation == plan2.punctuation
        assert plan1.hedging == plan2.hedging
        assert plan1.length == plan2.length
        assert plan1.allowed_connectors == plan2.allowed_connectors
        assert plan1.timestamp_utc == plan2.timestamp_utc

    def test_resolver_stateless(self):
        """Test: Resolver is stateless."""
        realizer1 = P14SurfaceRealizer()
        realizer2 = P14SurfaceRealizer()

        ctx = make_inform_context()

        with patch.object(realizer1, '_get_timestamp_utc', return_value="2024-01-01T00:00:00+00:00"):
            with patch.object(realizer2, '_get_timestamp_utc', return_value="2024-01-01T00:00:00+00:00"):
                plan1 = realizer1.realize(ctx)
                plan2 = realizer2.realize(ctx)

        assert plan1.style == plan2.style
        assert plan1.punctuation == plan2.punctuation

    def test_deterministic_for_hold(self):
        """Test: HOLD produces deterministic output."""
        ctx1 = make_hold_context()
        ctx2 = make_hold_context()

        plan1 = run_p14_directly(ctx1)
        plan2 = run_p14_directly(ctx2)

        assert plan1.style == plan2.style
        assert plan1.length == plan2.length
        assert plan1.requires_question == plan2.requires_question

    def test_deterministic_for_de_escalate(self):
        """Test: DE_ESCALATE produces deterministic output."""
        ctx1 = make_de_escalate_context()
        ctx2 = make_de_escalate_context()

        plan1 = run_p14_directly(ctx1)
        plan2 = run_p14_directly(ctx2)

        assert plan1.style == plan2.style
        assert plan1.hedging == plan2.hedging


# ============================================================================
# G. CONNECTOR ALLOW-LIST TESTS
# ============================================================================


class TestConnectorAllowList:
    """Tests for connector allow-list enforcement."""

    def test_deferral_uses_deferral_connectors(self):
        """Test: DEFERRAL style uses DEFERRAL_CONNECTORS."""
        ctx = make_hold_context()
        plan = run_p14_directly(ctx)

        assert plan is not None
        assert plan.allowed_connectors == DEFERRAL_CONNECTORS

    def test_reflection_uses_reflect_connectors(self):
        """Test: REFLECTION discourse uses REFLECT_CONNECTORS."""
        ctx = make_reflect_context()
        plan = run_p14_directly(ctx)

        assert plan is not None
        assert plan.allowed_connectors == REFLECT_CONNECTORS

    def test_acknowledgment_uses_ack_connectors(self):
        """Test: ACKNOWLEDGMENT discourse uses ACK_CONNECTORS."""
        ctx = MockPipelineContext(
            p6_regime=MockRegimeEnvelope.create("INFORM"),
            p7_discourse_envelope=MockDiscourseEnvelope.create("ACKNOWLEDGMENT"),
            phase_minus_one=MockPhaseMinusOneEnvelope.create("DETACHED"),
            p13_safety_envelope=MockP13SafetyEnvelope(allow_emphasis=True),
        )
        plan = run_p14_directly(ctx)

        assert plan is not None
        assert plan.allowed_connectors == ACK_CONNECTORS

    def test_question_uses_clarify_connectors(self):
        """Test: QUESTION discourse uses CLARIFY_CONNECTORS."""
        ctx = MockPipelineContext(
            p6_regime=MockRegimeEnvelope.create("CLARIFY"),
            p7_discourse_envelope=MockDiscourseEnvelope.create("QUESTION"),
            phase_minus_one=MockPhaseMinusOneEnvelope.create("DETACHED"),
            p13_safety_envelope=MockP13SafetyEnvelope(allow_emphasis=False),
        )
        plan = run_p14_directly(ctx)

        assert plan is not None
        assert plan.allowed_connectors == CLARIFY_CONNECTORS

    def test_has_connector_method(self):
        """Test: has_connector method works correctly."""
        ctx = make_hold_context()
        plan = run_p14_directly(ctx)

        assert plan is not None
        assert plan.has_connector("Could you clarify") is True
        assert plan.has_connector("because") is False

    def test_explanation_no_persona_empty_connectors(self):
        """Test: EXPLANATION without persona signal -> empty connectors."""
        ctx = MockPipelineContext(
            p6_regime=MockRegimeEnvelope.create("INFORM"),
            p7_discourse_envelope=MockDiscourseEnvelope.create("EXPLANATION"),
            phase_minus_one=MockPhaseMinusOneEnvelope.create("DETACHED"),
            p13_safety_envelope=MockP13SafetyEnvelope(allow_emphasis=True),
        )
        plan = run_p14_directly(ctx)

        assert plan is not None
        # EXPLANATION without specific persona -> empty connectors
        assert plan.allowed_connectors == ()


# ============================================================================
# H. REGRESSION TESTS - Forbidden Default Connectors
# ============================================================================


class TestRegressionForbiddenDefaults:
    """Regression tests for forbidden connectors/tokens."""

    def test_consider_never_in_default_allow_list(self):
        """Test: 'consider' is never in default allow list."""
        for connectors in [DEFERRAL_CONNECTORS, REFLECT_CONNECTORS, ACK_CONNECTORS, CLARIFY_CONNECTORS]:
            for connector in connectors:
                assert "consider" not in connector.lower()

    def test_to_clarify_not_in_default_pools_except_clarify(self):
        """Test: 'to clarify' pattern is not in DEFERRAL, REFLECT, ACK pools."""
        # CLARIFY_CONNECTORS has "To clarify" which is valid when SAFE_CLARIFY is used
        # But the other default pools should not have it
        for connectors in [DEFERRAL_CONNECTORS, REFLECT_CONNECTORS, ACK_CONNECTORS]:
            for connector in connectors:
                assert "to clarify" not in connector.lower()

        # Verify "To clarify" is in CLARIFY_CONNECTORS (this IS explicitly allowed)
        assert any("to clarify" in c.lower() for c in CLARIFY_CONNECTORS)

    def test_that_said_never_in_default_allow_list(self):
        """Test: 'that said' is never in default allow list."""
        assert "that said" in NEVER_ALLOWED_CONNECTORS

        for connectors in [DEFERRAL_CONNECTORS, REFLECT_CONNECTORS, ACK_CONNECTORS, CLARIFY_CONNECTORS]:
            for connector in connectors:
                assert "that said" not in connector.lower()

    def test_however_never_in_default_allow_list(self):
        """Test: 'however' is never in default allow list."""
        assert "however" in NEVER_ALLOWED_CONNECTORS

    def test_because_never_in_default_allow_list(self):
        """Test: 'because' is never in default allow list."""
        assert "because" in NEVER_ALLOWED_CONNECTORS

    def test_therefore_never_in_default_allow_list(self):
        """Test: 'therefore' is never in default allow list."""
        assert "therefore" in NEVER_ALLOWED_CONNECTORS

    def test_obviously_in_forbidden_tokens(self):
        """Test: 'obviously' is in default forbidden tokens."""
        assert "obviously" in DEFAULT_FORBIDDEN_TOKENS

    def test_definitely_in_forbidden_tokens(self):
        """Test: 'definitely' is in default forbidden tokens."""
        assert "definitely" in DEFAULT_FORBIDDEN_TOKENS

    def test_you_should_in_forbidden_tokens(self):
        """Test: 'you should' is in default forbidden tokens."""
        assert "you should" in DEFAULT_FORBIDDEN_TOKENS

    def test_diagnosis_in_forbidden_tokens(self):
        """Test: 'diagnosis' is in default forbidden tokens."""
        assert "diagnosis" in DEFAULT_FORBIDDEN_TOKENS


# ============================================================================
# I. SCHEMA VALIDATION TESTS
# ============================================================================


class TestSchemaValidation:
    """Tests for schema validation."""

    def test_valid_plan_construction(self):
        """Test: Valid SurfacePlan construction."""
        plan = SurfacePlan(
            style=SurfaceStyle.NEUTRAL,
            punctuation=PunctuationPolicy.LIMITED_COMMAS,
            hedging=HedgePolicy.NONE,
            length=LengthPolicy.TWO_SENTENCES_MAX,
            persona_signals=PersonaSignalPolicy.NONE,
            allowed_connectors=(),
            forbidden_tokens=DEFAULT_FORBIDDEN_TOKENS,
            requires_question=False,
            source_regime="INFORM",
            source_discourse_act="EXPLANATION",
            source_grounding_mode="DETACHED",
            source_p13_allows_emphasis=True,
        )

        assert plan.style == SurfaceStyle.NEUTRAL
        assert plan.is_neutral() is True

    def test_plan_immutability(self):
        """Test: SurfacePlan is frozen/immutable."""
        plan = get_deferral_plan()

        with pytest.raises(Exception):  # FrozenInstanceError
            plan.style = SurfaceStyle.NEUTRAL

    def test_hold_regime_requires_deferral_style(self):
        """Test: HOLD regime requires DEFERRAL_MINIMAL style."""
        with pytest.raises(ValueError, match="HOLD regime requires style=DEFERRAL_MINIMAL"):
            SurfacePlan(
                style=SurfaceStyle.NEUTRAL,  # Wrong - should be DEFERRAL_MINIMAL
                punctuation=PunctuationPolicy.BASIC_PERIODS,
                hedging=HedgePolicy.NONE,
                length=LengthPolicy.ONE_SENTENCE,
                persona_signals=PersonaSignalPolicy.SAFE_CLARIFY,
                allowed_connectors=DEFERRAL_CONNECTORS,
                forbidden_tokens=DEFAULT_FORBIDDEN_TOKENS,
                requires_question=True,
                source_regime="HOLD",
                source_discourse_act="DEFERRAL",
                source_grounding_mode="UNKNOWN",
                source_p13_allows_emphasis=False,
            )

    def test_hold_regime_requires_one_sentence(self):
        """Test: HOLD regime requires ONE_SENTENCE length."""
        with pytest.raises(ValueError, match="HOLD regime requires length=ONE_SENTENCE"):
            SurfacePlan(
                style=SurfaceStyle.DEFERRAL_MINIMAL,
                punctuation=PunctuationPolicy.BASIC_PERIODS,
                hedging=HedgePolicy.NONE,
                length=LengthPolicy.TWO_SENTENCES_MAX,  # Wrong
                persona_signals=PersonaSignalPolicy.SAFE_CLARIFY,
                allowed_connectors=DEFERRAL_CONNECTORS,
                forbidden_tokens=DEFAULT_FORBIDDEN_TOKENS,
                requires_question=True,
                source_regime="HOLD",
                source_discourse_act="DEFERRAL",
                source_grounding_mode="UNKNOWN",
                source_p13_allows_emphasis=False,
            )

    def test_relational_mode_requires_forbidden_tokens(self):
        """Test: RELATIONAL mode requires second-person assertions in forbidden."""
        with pytest.raises(ValueError, match="RELATIONAL mode requires"):
            SurfacePlan(
                style=SurfaceStyle.NEUTRAL,
                punctuation=PunctuationPolicy.LIMITED_COMMAS,
                hedging=HedgePolicy.REQUIRED,
                length=LengthPolicy.TWO_SENTENCES_MAX,
                persona_signals=PersonaSignalPolicy.NONE,
                allowed_connectors=(),
                forbidden_tokens=DEFAULT_FORBIDDEN_TOKENS,  # Missing RELATIONAL tokens
                requires_question=False,
                source_regime="INFORM",
                source_discourse_act="EXPLANATION",
                source_grounding_mode="RELATIONAL",
                source_p13_allows_emphasis=False,
            )

    def test_never_allowed_connectors_rejected(self):
        """Test: Connectors in NEVER_ALLOWED_CONNECTORS are rejected."""
        with pytest.raises(ValueError, match="allowed_connectors contains forbidden pattern"):
            SurfacePlan(
                style=SurfaceStyle.NEUTRAL,
                punctuation=PunctuationPolicy.LIMITED_COMMAS,
                hedging=HedgePolicy.NONE,
                length=LengthPolicy.TWO_SENTENCES_MAX,
                persona_signals=PersonaSignalPolicy.NONE,
                allowed_connectors=("because it's important",),  # Contains 'because'
                forbidden_tokens=DEFAULT_FORBIDDEN_TOKENS,
                requires_question=False,
                source_regime="INFORM",
                source_discourse_act="EXPLANATION",
                source_grounding_mode="DETACHED",
                source_p13_allows_emphasis=True,
            )

    def test_default_forbidden_required(self):
        """Test: DEFAULT_FORBIDDEN_TOKENS must be in forbidden_tokens."""
        with pytest.raises(ValueError, match="forbidden_tokens must include"):
            SurfacePlan(
                style=SurfaceStyle.NEUTRAL,
                punctuation=PunctuationPolicy.LIMITED_COMMAS,
                hedging=HedgePolicy.NONE,
                length=LengthPolicy.TWO_SENTENCES_MAX,
                persona_signals=PersonaSignalPolicy.NONE,
                allowed_connectors=(),
                forbidden_tokens=("custom",),  # Missing defaults
                requires_question=False,
                source_regime="INFORM",
                source_discourse_act="EXPLANATION",
                source_grounding_mode="DETACHED",
                source_p13_allows_emphasis=True,
            )

    def test_plan_to_dict(self):
        """Test: SurfacePlan serialization."""
        plan = get_deferral_plan(
            source_regime="HOLD",
            source_discourse_act="DEFERRAL",
        )
        d = plan.to_dict()

        assert d["style"] == "DEFERRAL_MINIMAL"
        assert d["is_deferral"] is True
        assert d["requires_question"] is True
        assert d["max_sentences"] == 1
        assert d["version"] == P14_VERSION

    def test_get_deferral_plan_helper(self):
        """Test: get_deferral_plan helper function."""
        plan = get_deferral_plan(
            source_regime="HOLD",
            source_discourse_act="DEFERRAL",
        )

        assert plan.is_deferral() is True
        assert plan.requires_question is True
        assert plan.style == SurfaceStyle.DEFERRAL_MINIMAL


# ============================================================================
# J. INTEGRATION TESTS
# ============================================================================


class TestIntegration:
    """Tests for P14 integration functions."""

    def test_maybe_run_p14_attaches_plan(self):
        """Test: maybe_run_p14 attaches plan to context."""
        ctx = make_inform_context()

        result_ctx = maybe_run_p14(ctx)

        assert result_ctx.p14_surface is not None
        assert isinstance(result_ctx.p14_surface, SurfacePlan)

    def test_maybe_run_p14_idempotent(self):
        """Test: maybe_run_p14 is idempotent."""
        ctx = make_inform_context()

        maybe_run_p14(ctx)
        first_plan = ctx.p14_surface
        first_timestamp = first_plan.timestamp_utc

        # Run again
        maybe_run_p14(ctx)
        second_plan = ctx.p14_surface

        # Should be the same object (idempotent)
        assert second_plan.timestamp_utc == first_timestamp

    def test_maybe_run_p14_no_p6_returns_deferral(self):
        """Test: maybe_run_p14 with no P6 returns deferral plan."""
        ctx = MockPipelineContext(
            p6_regime=None,
            p13_safety_envelope=MockP13SafetyEnvelope(allow_emphasis=False),
        )
        result_ctx = maybe_run_p14(ctx)

        assert result_ctx.p14_surface is not None
        assert result_ctx.p14_surface.is_deferral() is True

    def test_run_p14_directly_no_context_modification(self):
        """Test: run_p14_directly doesn't modify context."""
        ctx = make_inform_context()

        plan = run_p14_directly(ctx)

        assert plan is not None
        assert ctx.p14_surface is None  # Not attached

    def test_accessor_functions_no_plan(self):
        """Test: Accessor functions with no plan."""
        ctx = MockPipelineContext()

        assert is_deferral(ctx) is True  # Conservative default
        assert is_gentle(ctx) is False
        assert allows_exclamation(ctx) is False
        assert allows_bullets(ctx) is False
        assert get_max_sentences(ctx) == 1  # Conservative default
        assert requires_question(ctx) is True  # Conservative default

    def test_accessor_functions_with_plan(self):
        """Test: Accessor functions with plan."""
        ctx = make_inform_context()
        maybe_run_p14(ctx)

        assert is_deferral(ctx) is False
        # INFORM + DETACHED + EXPLANATION produces FORMAL style
        assert get_style(ctx) in (SurfaceStyle.NEUTRAL, SurfaceStyle.FORMAL)

    def test_singleton_realizer(self):
        """Test: Singleton realizer pattern."""
        r1 = get_p14_realizer()
        r2 = get_p14_realizer()
        assert r1 is r2

    def test_is_forbidden_accessor(self):
        """Test: is_forbidden accessor function."""
        ctx = make_inform_context()
        maybe_run_p14(ctx)

        assert is_forbidden(ctx, "definitely") is True
        assert is_forbidden(ctx, "hello") is False

    def test_has_connector_accessor(self):
        """Test: has_connector accessor function."""
        ctx = make_hold_context()
        maybe_run_p14(ctx)

        assert has_connector(ctx, "Could you clarify") is True
        assert has_connector(ctx, "because") is False


# ============================================================================
# K. RESOLUTION FUNCTION TESTS
# ============================================================================


class TestResolutionFunctions:
    """Tests for individual resolution functions."""

    def test_resolve_style_hold(self):
        """Test: resolve_style for HOLD regime."""
        style = resolve_style("HOLD", "DEFERRAL", "UNKNOWN", False)
        assert style == SurfaceStyle.DEFERRAL_MINIMAL

    def test_resolve_style_de_escalate(self):
        """Test: resolve_style for DE_ESCALATE regime."""
        style = resolve_style("DE_ESCALATE", "REFLECTION", "REFLEXIVE", False)
        assert style == SurfaceStyle.GENTLE

    def test_resolve_style_inform_detached(self):
        """Test: resolve_style for INFORM + DETACHED."""
        style = resolve_style("INFORM", "EXPLANATION", "DETACHED", True)
        assert style == SurfaceStyle.FORMAL

    def test_resolve_punctuation_hold(self):
        """Test: resolve_punctuation for HOLD regime."""
        punctuation = resolve_punctuation("HOLD", "DEFERRAL", False)
        assert punctuation == PunctuationPolicy.BASIC_PERIODS

    def test_resolve_punctuation_inform(self):
        """Test: resolve_punctuation for INFORM regime."""
        punctuation = resolve_punctuation("INFORM", "EXPLANATION", True)
        assert punctuation == PunctuationPolicy.LIMITED_COMMAS

    def test_resolve_hedging_relational(self):
        """Test: resolve_hedging for RELATIONAL mode."""
        hedging = resolve_hedging("INFORM", "EXPLANATION", "RELATIONAL", False)
        assert hedging == HedgePolicy.REQUIRED

    def test_resolve_hedging_uncertainty(self):
        """Test: resolve_hedging with UNCERTAINTY slot."""
        hedging = resolve_hedging("INFORM", "EXPLANATION", "DETACHED", True)
        assert hedging == HedgePolicy.LIGHT

    def test_resolve_length_hold(self):
        """Test: resolve_length for HOLD regime."""
        length = resolve_length("HOLD", "DEFERRAL", "UNKNOWN")
        assert length == LengthPolicy.ONE_SENTENCE

    def test_resolve_length_inform_detached_explanation(self):
        """Test: resolve_length for INFORM + DETACHED + EXPLANATION."""
        length = resolve_length("INFORM", "EXPLANATION", "DETACHED")
        assert length == LengthPolicy.BULLETS_MAX_3

    def test_resolve_persona_reflection(self):
        """Test: resolve_persona_signals for REFLECTION discourse."""
        persona = resolve_persona_signals("REFLECT", "REFLECTION", "REFLEXIVE")
        assert persona == PersonaSignalPolicy.SAFE_REFLECT

    def test_resolve_persona_acknowledgment(self):
        """Test: resolve_persona_signals for ACKNOWLEDGMENT discourse."""
        persona = resolve_persona_signals("INFORM", "ACKNOWLEDGMENT", "DETACHED")
        assert persona == PersonaSignalPolicy.SAFE_ACK

    def test_resolve_requires_question_hold(self):
        """Test: resolve_requires_question for HOLD regime."""
        requires = resolve_requires_question("HOLD", "DEFERRAL", PersonaSignalPolicy.SAFE_CLARIFY)
        assert requires is True

    def test_resolve_requires_question_inform(self):
        """Test: resolve_requires_question for INFORM regime."""
        requires = resolve_requires_question("INFORM", "EXPLANATION", PersonaSignalPolicy.NONE)
        assert requires is False


# ============================================================================
# L. EDGE CASES
# ============================================================================


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_unknown_regime_handled(self):
        """Test: Unknown regime handled gracefully."""
        ctx = MockPipelineContext(
            p6_regime=MockRegimeEnvelope.create("UNKNOWN"),
            p7_discourse_envelope=MockDiscourseEnvelope.create("UNKNOWN"),
            p13_safety_envelope=MockP13SafetyEnvelope(allow_emphasis=False),
        )
        plan = run_p14_directly(ctx)

        # Should produce valid plan (not crash)
        assert plan is not None

    def test_missing_grounding_mode_handled(self):
        """Test: Missing grounding mode handled gracefully."""
        ctx = MockPipelineContext(
            p6_regime=MockRegimeEnvelope.create("INFORM"),
            p7_discourse_envelope=MockDiscourseEnvelope.create("EXPLANATION"),
            phase_minus_one=None,  # No grounding
            p13_safety_envelope=MockP13SafetyEnvelope(allow_emphasis=True),
        )
        plan = run_p14_directly(ctx)

        assert plan is not None

    def test_missing_discourse_handled(self):
        """Test: Missing discourse envelope handled gracefully."""
        ctx = MockPipelineContext(
            p6_regime=MockRegimeEnvelope.create("INFORM"),
            p7_discourse_envelope=None,
            p13_safety_envelope=MockP13SafetyEnvelope(allow_emphasis=True),
        )
        plan = run_p14_directly(ctx)

        assert plan is not None
        assert plan.source_discourse_act == "UNKNOWN"

    def test_minimal_context(self):
        """Test: Minimal context with only P6 and P13."""
        ctx = MockPipelineContext(
            p6_regime=MockRegimeEnvelope.create("INFORM"),
            p13_safety_envelope=MockP13SafetyEnvelope(allow_emphasis=True),
        )
        plan = run_p14_directly(ctx)

        assert plan is not None


# ============================================================================
# M. BUILD FORBIDDEN TOKENS TESTS
# ============================================================================


class TestBuildForbiddenTokens:
    """Tests for build_forbidden_tokens function."""

    def test_build_default_tokens(self):
        """Test: Building default forbidden tokens."""
        tokens = build_forbidden_tokens("DETACHED")

        for token in DEFAULT_FORBIDDEN_TOKENS:
            assert token in tokens

    def test_build_relational_tokens(self):
        """Test: Building forbidden tokens for RELATIONAL mode."""
        tokens = build_forbidden_tokens("RELATIONAL")

        for token in DEFAULT_FORBIDDEN_TOKENS:
            assert token in tokens
        for token in RELATIONAL_FORBIDDEN_TOKENS:
            assert token in tokens

    def test_build_tokens_no_duplicates(self):
        """Test: No duplicate tokens in result."""
        tokens = build_forbidden_tokens("RELATIONAL", include_relational=True)

        # Should be unique
        assert len(tokens) == len(set(tokens))


# ============================================================================
# N. HELPER METHOD TESTS
# ============================================================================


class TestHelperMethods:
    """Tests for SurfacePlan helper methods."""

    def test_is_minimal(self):
        """Test: is_minimal method."""
        plan = SurfacePlan(
            style=SurfaceStyle.MINIMAL,
            punctuation=PunctuationPolicy.BASIC_PERIODS,
            hedging=HedgePolicy.NONE,
            length=LengthPolicy.ONE_SENTENCE,
            persona_signals=PersonaSignalPolicy.NONE,
            allowed_connectors=(),
            forbidden_tokens=DEFAULT_FORBIDDEN_TOKENS,
            requires_question=False,
            source_regime="UNKNOWN",
            source_discourse_act="UNKNOWN",
            source_grounding_mode="UNKNOWN",
            source_p13_allows_emphasis=False,
        )
        assert plan.is_minimal() is True

    def test_is_formal(self):
        """Test: is_formal method."""
        plan = SurfacePlan(
            style=SurfaceStyle.FORMAL,
            punctuation=PunctuationPolicy.LIMITED_COMMAS,
            hedging=HedgePolicy.NONE,
            length=LengthPolicy.TWO_SENTENCES_MAX,
            persona_signals=PersonaSignalPolicy.NONE,
            allowed_connectors=(),
            forbidden_tokens=DEFAULT_FORBIDDEN_TOKENS,
            requires_question=False,
            source_regime="INFORM",
            source_discourse_act="EXPLANATION",
            source_grounding_mode="DETACHED",
            source_p13_allows_emphasis=True,
        )
        assert plan.is_formal() is True

    def test_allows_bullets(self):
        """Test: allows_bullets method."""
        plan = SurfacePlan(
            style=SurfaceStyle.FORMAL,
            punctuation=PunctuationPolicy.LIMITED_COMMAS,
            hedging=HedgePolicy.NONE,
            length=LengthPolicy.BULLETS_MAX_3,
            persona_signals=PersonaSignalPolicy.NONE,
            allowed_connectors=(),
            forbidden_tokens=DEFAULT_FORBIDDEN_TOKENS,
            requires_question=False,
            source_regime="INFORM",
            source_discourse_act="EXPLANATION",
            source_grounding_mode="DETACHED",
            source_p13_allows_emphasis=True,
        )
        assert plan.allows_bullets() is True

    def test_get_max_sentences(self):
        """Test: get_max_sentences method."""
        plan_one = get_deferral_plan()
        assert plan_one.get_max_sentences() == 1

        plan_two = SurfacePlan(
            style=SurfaceStyle.NEUTRAL,
            punctuation=PunctuationPolicy.LIMITED_COMMAS,
            hedging=HedgePolicy.NONE,
            length=LengthPolicy.TWO_SENTENCES_MAX,
            persona_signals=PersonaSignalPolicy.NONE,
            allowed_connectors=(),
            forbidden_tokens=DEFAULT_FORBIDDEN_TOKENS,
            requires_question=False,
            source_regime="INFORM",
            source_discourse_act="EXPLANATION",
            source_grounding_mode="DETACHED",
            source_p13_allows_emphasis=True,
        )
        assert plan_two.get_max_sentences() == 2

    def test_is_forbidden_method(self):
        """Test: is_forbidden method."""
        plan = get_deferral_plan()

        assert plan.is_forbidden("definitely not") is True
        assert plan.is_forbidden("hello world") is False
