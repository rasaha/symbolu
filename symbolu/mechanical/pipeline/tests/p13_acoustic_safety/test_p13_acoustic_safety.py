"""
P13 Unit Tests - Acoustic Safety Envelope

Tests for P13 Acoustic Safety Envelope:
- AcousticSafetyEnvelope dataclass
- P13AcousticSafetyResolver (capping-only)
- Safety violation detection
- Integration with P10/P11/P12

Test Categories (per specification):
A. Regime Enforcement Tests
   - HOLD regime -> BLOCKED, all expressive flags False
   - DE_ESCALATE/STABILIZE -> emphasis False, contours False
   - INFORM/CLARIFY -> appropriate bounds

B. No Amplification Invariants
   - P13 may only reduce or clamp, never amplify
   - Pitch bounds never exceed P10
   - Energy bounds never exceed P10
   - Variance bounds never exceed P10

C. Authority Signaling Prevention
   - REFLEXIVE grounding -> no emphasis
   - RELATIONAL grounding -> no authority signals
   - REFLECTION discourse -> no emphasis

D. HOLD -> BLOCKED Safety Envelope
   - HOLD regime produces BLOCKED envelope
   - All flags False under HOLD
   - Most restrictive bounds under HOLD

E. Determinism Tests
   - Same input -> same output
   - No probabilistic behavior
   - No LLM calls

F. Regression Tests
   - P12 mismatch -> CAUTION risk level
   - P12 critical violations -> BLOCKED
   - Missing P10 -> BLOCKED envelope

G. Cross-Phase Authority Tests
   - P13 cannot override P10 intent
   - P13 reads but doesn't modify upstream
   - P13 envelope is binding on downstream

H. Schema Validation Tests
   - Dataclass construction
   - Invariant validation
   - Serialization

I. Integration Tests
   - maybe_run_p13 behavior
   - Accessor functions
   - Empty/missing data handling

Target: >= 60 tests

CRITICAL ARCHITECTURAL INVARIANT:
    P13 is the last safety lock before sound.
    Phase 1 (acoustic tokenization) must consume P13 verbatim.
    Renderers violating P13 are considered unsafe by design.
"""

from dataclasses import dataclass
from typing import Any, Optional
from unittest.mock import patch, MagicMock

import pytest

from symbolu.mechanical.pipeline.p13_acoustic_safety import (
    # Schema
    AcousticRiskLevel,
    SafetyViolation,
    AcousticSafetyEnvelope,
    P13_VERSION,
    get_blocked_envelope,
    # Constants
    ABSOLUTE_PITCH_MIN,
    ABSOLUTE_PITCH_MAX,
    ABSOLUTE_ENERGY_MIN,
    ABSOLUTE_ENERGY_MAX,
    HOLD_PITCH_MIN,
    HOLD_PITCH_MAX,
    HOLD_ENERGY_MIN,
    HOLD_ENERGY_MAX,
    HOLD_VARIANCE_MAX,
    DE_ESCALATE_VARIANCE_MAX,
    # Resolver
    P13AcousticSafetyResolver,
    detect_emotion_amplification,
    detect_certainty_escalation,
    detect_authority_signaling,
    detect_excessive_variance,
    detect_prosodic_manipulation,
    compute_pitch_bounds,
    compute_energy_bounds,
    compute_variance_bounds,
    compute_expression_flags,
    # Integration
    get_p13_resolver,
    maybe_run_p13,
    run_p13_directly,
    get_p13_safety_envelope,
    get_risk_level,
    is_safe,
    is_caution,
    is_blocked,
    has_violations,
    get_violations,
    allows_emphasis,
    allows_pitch_contours,
    is_fully_restricted,
    get_max_energy,
    get_pitch_variance_limit,
)
from symbolu.mechanical.pipeline.p10_acoustic import (
    AcousticParameterFrame,
    AcousticRegime,
    EmphasisPolicy,
    PausePolicy,
)
from symbolu.mechanical.pipeline.p12_consistency import (
    P12ConsistencyReport,
    create_violation,
    ViolationSeverity,
    ViolationType,
)


# ============================================================================
# TEST HELPERS
# ============================================================================


def make_acoustic_frame(
    regime: AcousticRegime = AcousticRegime.NEUTRAL,
    speech_rate: float = 4.5,
    energy_level: float = 0.45,
    pitch_range: tuple = (100, 130),
    pause_policy: PausePolicy = PausePolicy.MINIMAL,
    pause_duration_ms: tuple = (100, 150),
    emphasis_policy: EmphasisPolicy = EmphasisPolicy.LIMITED,
    max_stressed_tokens: int = 1,
    suppress_emotion: bool = True,
    suppress_emphasis: bool = False,
    suppress_certainty: bool = False,
    source_regime: str = "INFORM",
    source_discourse_act: str = "EXPLANATION",
) -> AcousticParameterFrame:
    """Create a test AcousticParameterFrame."""
    return AcousticParameterFrame(
        regime=regime,
        speech_rate=speech_rate,
        energy_level=energy_level,
        pitch_range=pitch_range,
        pause_policy=pause_policy,
        pause_duration_ms=pause_duration_ms,
        emphasis_policy=emphasis_policy,
        max_stressed_tokens=max_stressed_tokens,
        suppress_emotion=suppress_emotion,
        suppress_emphasis=suppress_emphasis,
        suppress_certainty=suppress_certainty,
        source_regime=source_regime,
        source_discourse_act=source_discourse_act,
    )


def make_hold_acoustic_frame() -> AcousticParameterFrame:
    """Create a valid HOLD regime AcousticParameterFrame (most conservative)."""
    return AcousticParameterFrame(
        regime=AcousticRegime.FLAT,
        speech_rate=3.5,
        energy_level=0.25,
        pitch_range=(95, 105),
        pause_policy=PausePolicy.NORMAL,
        pause_duration_ms=(150, 250),
        emphasis_policy=EmphasisPolicy.NONE,
        max_stressed_tokens=0,
        suppress_emotion=True,
        suppress_emphasis=True,
        suppress_certainty=True,
        source_regime="HOLD",
        source_discourse_act="DEFERRAL",
    )


def make_de_escalate_acoustic_frame() -> AcousticParameterFrame:
    """Create a valid DE_ESCALATE regime AcousticParameterFrame."""
    return AcousticParameterFrame(
        regime=AcousticRegime.SOFT,
        speech_rate=3.5,
        energy_level=0.30,
        pitch_range=(95, 115),
        pause_policy=PausePolicy.NORMAL,
        pause_duration_ms=(150, 250),
        emphasis_policy=EmphasisPolicy.NONE,
        max_stressed_tokens=0,
        suppress_emotion=True,
        suppress_emphasis=True,
        suppress_certainty=True,
        source_regime="DE_ESCALATE",
        source_discourse_act="REFLECTION",
    )


def make_inform_acoustic_frame() -> AcousticParameterFrame:
    """Create a valid INFORM regime AcousticParameterFrame."""
    return AcousticParameterFrame(
        regime=AcousticRegime.NEUTRAL,
        speech_rate=4.5,
        energy_level=0.45,
        pitch_range=(100, 130),
        pause_policy=PausePolicy.MINIMAL,
        pause_duration_ms=(100, 150),
        emphasis_policy=EmphasisPolicy.LIMITED,
        max_stressed_tokens=1,
        suppress_emotion=True,
        suppress_emphasis=False,
        suppress_certainty=False,
        source_regime="INFORM",
        source_discourse_act="EXPLANATION",
    )


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


@dataclass
class MockP12ConsistencyReport:
    """Mock P12 consistency report."""
    is_consistent: bool
    _has_critical: bool = False

    def has_critical_violations(self) -> bool:
        return self._has_critical


@dataclass
class MockPipelineContext:
    """Mock pipeline context for testing."""
    p10_acoustic: Optional[AcousticParameterFrame] = None
    p6_regime: Optional[MockRegimeEnvelope] = None
    p7_discourse_envelope: Optional[MockDiscourseEnvelope] = None
    phase_minus_one: Optional[MockPhaseMinusOneEnvelope] = None
    p12_consistency: Optional[MockP12ConsistencyReport] = None
    p13_safety_envelope: Optional[AcousticSafetyEnvelope] = None


# ============================================================================
# A. REGIME ENFORCEMENT TESTS
# ============================================================================


class TestRegimeEnforcement:
    """Tests for regime enforcement in P13."""

    def test_hold_regime_produces_blocked_risk_level(self):
        """Test: HOLD regime -> BLOCKED risk level."""
        acoustic = make_hold_acoustic_frame()
        ctx = MockPipelineContext(
            p10_acoustic=acoustic,
            p6_regime=MockRegimeEnvelope.create("HOLD"),
            p7_discourse_envelope=MockDiscourseEnvelope.create("DEFERRAL"),
        )
        envelope = run_p13_directly(ctx)

        assert envelope is not None
        assert envelope.risk_level == AcousticRiskLevel.BLOCKED

    def test_hold_regime_all_flags_false(self):
        """Test: HOLD regime -> all expressive flags False."""
        acoustic = make_hold_acoustic_frame()
        ctx = MockPipelineContext(
            p10_acoustic=acoustic,
            p6_regime=MockRegimeEnvelope.create("HOLD"),
            p7_discourse_envelope=MockDiscourseEnvelope.create("DEFERRAL"),
        )
        envelope = run_p13_directly(ctx)

        assert envelope is not None
        assert envelope.allow_emphasis is False
        assert envelope.allow_pitch_contours is False
        assert envelope.allow_rhythm_variation is False
        assert envelope.allow_intonation_shift is False
        assert envelope.is_fully_restricted() is True

    def test_de_escalate_regime_emphasis_false(self):
        """Test: DE_ESCALATE regime -> allow_emphasis False."""
        acoustic = make_de_escalate_acoustic_frame()
        ctx = MockPipelineContext(
            p10_acoustic=acoustic,
            p6_regime=MockRegimeEnvelope.create("DE_ESCALATE"),
            p7_discourse_envelope=MockDiscourseEnvelope.create("REFLECTION"),
            p12_consistency=MockP12ConsistencyReport(is_consistent=True),
        )
        envelope = run_p13_directly(ctx)

        assert envelope is not None
        assert envelope.allow_emphasis is False
        assert envelope.allow_pitch_contours is False

    def test_stabilize_regime_emphasis_false(self):
        """Test: STABILIZE regime -> allow_emphasis False."""
        acoustic = make_acoustic_frame(
            regime=AcousticRegime.SOFT,
            source_regime="STABILIZE",
            suppress_emotion=True,
            suppress_emphasis=True,
            suppress_certainty=True,
        )
        ctx = MockPipelineContext(
            p10_acoustic=acoustic,
            p6_regime=MockRegimeEnvelope.create("STABILIZE"),
            p7_discourse_envelope=MockDiscourseEnvelope.create("REFLECTION"),
            p12_consistency=MockP12ConsistencyReport(is_consistent=True),
        )
        envelope = run_p13_directly(ctx)

        assert envelope is not None
        assert envelope.allow_emphasis is False
        assert envelope.allow_pitch_contours is False

    def test_inform_regime_allows_expression(self):
        """Test: INFORM regime can allow expression (if other conditions met)."""
        acoustic = make_inform_acoustic_frame()
        ctx = MockPipelineContext(
            p10_acoustic=acoustic,
            p6_regime=MockRegimeEnvelope.create("INFORM"),
            p7_discourse_envelope=MockDiscourseEnvelope.create("EXPLANATION"),
            p12_consistency=MockP12ConsistencyReport(is_consistent=True),
        )
        envelope = run_p13_directly(ctx)

        assert envelope is not None
        assert envelope.risk_level == AcousticRiskLevel.SAFE
        # Under INFORM with consistent P12, some expression allowed
        assert envelope.allow_rhythm_variation is True
        assert envelope.allow_intonation_shift is True

    def test_clarify_regime_allows_expression(self):
        """Test: CLARIFY regime can allow expression."""
        acoustic = make_acoustic_frame(source_regime="CLARIFY")
        ctx = MockPipelineContext(
            p10_acoustic=acoustic,
            p6_regime=MockRegimeEnvelope.create("CLARIFY"),
            p7_discourse_envelope=MockDiscourseEnvelope.create("QUESTION"),
            p12_consistency=MockP12ConsistencyReport(is_consistent=True),
        )
        envelope = run_p13_directly(ctx)

        assert envelope is not None
        assert envelope.risk_level == AcousticRiskLevel.SAFE


# ============================================================================
# B. NO AMPLIFICATION INVARIANTS
# ============================================================================


class TestNoAmplification:
    """Tests for no amplification invariants."""

    def test_pitch_bounds_never_exceed_p10(self):
        """Test: Pitch bounds never exceed P10 pitch range."""
        acoustic = make_acoustic_frame(pitch_range=(100, 120))
        ctx = MockPipelineContext(
            p10_acoustic=acoustic,
            p6_regime=MockRegimeEnvelope.create("INFORM"),
            p12_consistency=MockP12ConsistencyReport(is_consistent=True),
        )
        envelope = run_p13_directly(ctx)

        assert envelope is not None
        # Envelope pitch range should be <= P10 pitch range
        assert envelope.allowed_pitch_range[0] >= 100
        assert envelope.allowed_pitch_range[1] <= 120

    def test_energy_bounds_never_exceed_p10(self):
        """Test: Energy bounds never exceed P10 energy."""
        acoustic = make_acoustic_frame(energy_level=0.40)
        ctx = MockPipelineContext(
            p10_acoustic=acoustic,
            p6_regime=MockRegimeEnvelope.create("INFORM"),
            p12_consistency=MockP12ConsistencyReport(is_consistent=True),
        )
        envelope = run_p13_directly(ctx)

        assert envelope is not None
        # Max energy should be <= P10 energy
        assert envelope.allowed_energy_range[1] <= 0.40

    def test_variance_bounds_never_exceed_p10(self):
        """Test: Variance bounds never exceed P10 pitch variance."""
        acoustic = make_acoustic_frame(pitch_range=(100, 115))  # 15 Hz variance
        ctx = MockPipelineContext(
            p10_acoustic=acoustic,
            p6_regime=MockRegimeEnvelope.create("INFORM"),
            p12_consistency=MockP12ConsistencyReport(is_consistent=True),
        )
        envelope = run_p13_directly(ctx)

        assert envelope is not None
        # Max variance should be <= P10 variance (15 Hz)
        assert envelope.allowed_variance_range[1] <= 15

    def test_hold_applies_strictest_bounds(self):
        """Test: HOLD applies strictest bounds regardless of P10."""
        acoustic = make_acoustic_frame(
            pitch_range=(90, 140),  # Wide range in P10
            energy_level=0.60,  # High energy in P10
            source_regime="HOLD",
            suppress_emotion=True,
            suppress_emphasis=True,
            suppress_certainty=True,
        )
        ctx = MockPipelineContext(
            p10_acoustic=acoustic,
            p6_regime=MockRegimeEnvelope.create("HOLD"),
        )
        envelope = run_p13_directly(ctx)

        assert envelope is not None
        # HOLD should clamp to strict bounds
        assert envelope.allowed_pitch_range[1] <= HOLD_PITCH_MAX
        assert envelope.allowed_energy_range[1] <= HOLD_ENERGY_MAX
        assert envelope.allowed_variance_range[1] <= HOLD_VARIANCE_MAX

    def test_bounds_clamped_to_absolute_limits(self):
        """Test: Bounds are always clamped to absolute limits."""
        acoustic = make_inform_acoustic_frame()
        ctx = MockPipelineContext(
            p10_acoustic=acoustic,
            p6_regime=MockRegimeEnvelope.create("INFORM"),
            p12_consistency=MockP12ConsistencyReport(is_consistent=True),
        )
        envelope = run_p13_directly(ctx)

        assert envelope is not None
        # Pitch bounds within absolute limits
        assert envelope.allowed_pitch_range[0] >= ABSOLUTE_PITCH_MIN
        assert envelope.allowed_pitch_range[1] <= ABSOLUTE_PITCH_MAX
        # Energy bounds within absolute limits
        assert envelope.allowed_energy_range[0] >= ABSOLUTE_ENERGY_MIN
        assert envelope.allowed_energy_range[1] <= ABSOLUTE_ENERGY_MAX


# ============================================================================
# C. AUTHORITY SIGNALING PREVENTION
# ============================================================================


class TestAuthoritySignalingPrevention:
    """Tests for authority signaling prevention."""

    def test_reflexive_grounding_no_emphasis(self):
        """Test: REFLEXIVE grounding -> no emphasis allowed."""
        acoustic = make_acoustic_frame(
            emphasis_policy=EmphasisPolicy.LIMITED,
            suppress_emphasis=False,
        )
        ctx = MockPipelineContext(
            p10_acoustic=acoustic,
            p6_regime=MockRegimeEnvelope.create("REFLECT"),
            p7_discourse_envelope=MockDiscourseEnvelope.create("REFLECTION"),
            phase_minus_one=MockPhaseMinusOneEnvelope.create("REFLEXIVE"),
            p12_consistency=MockP12ConsistencyReport(is_consistent=True),
        )
        envelope = run_p13_directly(ctx)

        assert envelope is not None
        assert envelope.allow_emphasis is False

    def test_relational_grounding_no_authority(self):
        """Test: RELATIONAL grounding -> no authority signals."""
        acoustic = make_acoustic_frame(
            emphasis_policy=EmphasisPolicy.LIMITED,
            suppress_emphasis=False,
        )
        ctx = MockPipelineContext(
            p10_acoustic=acoustic,
            p6_regime=MockRegimeEnvelope.create("REFLECT"),
            p7_discourse_envelope=MockDiscourseEnvelope.create("REFLECTION"),
            phase_minus_one=MockPhaseMinusOneEnvelope.create("RELATIONAL"),
            p12_consistency=MockP12ConsistencyReport(is_consistent=True),
        )
        envelope = run_p13_directly(ctx)

        assert envelope is not None
        assert envelope.allow_emphasis is False

    def test_reflection_discourse_no_emphasis(self):
        """Test: REFLECTION discourse -> no emphasis allowed."""
        acoustic = make_acoustic_frame(
            emphasis_policy=EmphasisPolicy.LIMITED,
            suppress_emphasis=False,
        )
        ctx = MockPipelineContext(
            p10_acoustic=acoustic,
            p6_regime=MockRegimeEnvelope.create("REFLECT"),
            p7_discourse_envelope=MockDiscourseEnvelope.create("REFLECTION"),
            p12_consistency=MockP12ConsistencyReport(is_consistent=True),
        )
        envelope = run_p13_directly(ctx)

        assert envelope is not None
        assert envelope.allow_emphasis is False

    def test_deferral_discourse_minimal_motion(self):
        """Test: DEFERRAL discourse -> minimal prosodic motion."""
        acoustic = make_hold_acoustic_frame()
        ctx = MockPipelineContext(
            p10_acoustic=acoustic,
            p6_regime=MockRegimeEnvelope.create("HOLD"),
            p7_discourse_envelope=MockDiscourseEnvelope.create("DEFERRAL"),
        )
        envelope = run_p13_directly(ctx)

        assert envelope is not None
        assert envelope.allow_emphasis is False
        assert envelope.allow_pitch_contours is False

    def test_acknowledgment_discourse_no_emphasis(self):
        """Test: ACKNOWLEDGMENT discourse -> no emphasis."""
        acoustic = make_acoustic_frame(
            source_discourse_act="ACKNOWLEDGMENT",
            emphasis_policy=EmphasisPolicy.LIMITED,
        )
        ctx = MockPipelineContext(
            p10_acoustic=acoustic,
            p6_regime=MockRegimeEnvelope.create("INFORM"),
            p7_discourse_envelope=MockDiscourseEnvelope.create("ACKNOWLEDGMENT"),
            p12_consistency=MockP12ConsistencyReport(is_consistent=True),
        )
        envelope = run_p13_directly(ctx)

        assert envelope is not None
        assert envelope.allow_emphasis is False


# ============================================================================
# D. HOLD -> BLOCKED SAFETY ENVELOPE
# ============================================================================


class TestHoldBlockedEnvelope:
    """Tests for HOLD -> BLOCKED safety envelope."""

    def test_hold_produces_blocked_envelope(self):
        """Test: HOLD regime produces BLOCKED envelope."""
        acoustic = make_hold_acoustic_frame()
        ctx = MockPipelineContext(
            p10_acoustic=acoustic,
            p6_regime=MockRegimeEnvelope.create("HOLD"),
        )
        envelope = run_p13_directly(ctx)

        assert envelope is not None
        assert envelope.is_blocked() is True
        assert envelope.risk_level == AcousticRiskLevel.BLOCKED

    def test_hold_envelope_most_restrictive_pitch(self):
        """Test: HOLD envelope has most restrictive pitch bounds."""
        acoustic = make_hold_acoustic_frame()
        ctx = MockPipelineContext(
            p10_acoustic=acoustic,
            p6_regime=MockRegimeEnvelope.create("HOLD"),
        )
        envelope = run_p13_directly(ctx)

        assert envelope is not None
        assert envelope.allowed_pitch_range[0] >= HOLD_PITCH_MIN
        assert envelope.allowed_pitch_range[1] <= HOLD_PITCH_MAX

    def test_hold_envelope_most_restrictive_energy(self):
        """Test: HOLD envelope has most restrictive energy bounds."""
        acoustic = make_hold_acoustic_frame()
        ctx = MockPipelineContext(
            p10_acoustic=acoustic,
            p6_regime=MockRegimeEnvelope.create("HOLD"),
        )
        envelope = run_p13_directly(ctx)

        assert envelope is not None
        assert envelope.allowed_energy_range[0] >= HOLD_ENERGY_MIN
        assert envelope.allowed_energy_range[1] <= HOLD_ENERGY_MAX

    def test_hold_envelope_most_restrictive_variance(self):
        """Test: HOLD envelope has most restrictive variance bounds."""
        acoustic = make_hold_acoustic_frame()
        ctx = MockPipelineContext(
            p10_acoustic=acoustic,
            p6_regime=MockRegimeEnvelope.create("HOLD"),
        )
        envelope = run_p13_directly(ctx)

        assert envelope is not None
        assert envelope.allowed_variance_range[1] <= HOLD_VARIANCE_MAX

    def test_hold_envelope_fully_restricted_expression(self):
        """Test: HOLD envelope is fully restricted."""
        acoustic = make_hold_acoustic_frame()
        ctx = MockPipelineContext(
            p10_acoustic=acoustic,
            p6_regime=MockRegimeEnvelope.create("HOLD"),
        )
        envelope = run_p13_directly(ctx)

        assert envelope is not None
        assert envelope.is_fully_restricted() is True


# ============================================================================
# E. DETERMINISM TESTS
# ============================================================================


class TestDeterminism:
    """Tests for deterministic behavior."""

    def test_same_input_same_output(self):
        """Test: Same input produces same output."""
        acoustic = make_inform_acoustic_frame()
        ctx = MockPipelineContext(
            p10_acoustic=acoustic,
            p6_regime=MockRegimeEnvelope.create("INFORM"),
            p7_discourse_envelope=MockDiscourseEnvelope.create("EXPLANATION"),
            p12_consistency=MockP12ConsistencyReport(is_consistent=True),
        )

        resolver = P13AcousticSafetyResolver()

        with patch.object(resolver, '_get_timestamp_utc', return_value="2024-01-01T00:00:00+00:00"):
            envelope1 = resolver.resolve(ctx)
            envelope2 = resolver.resolve(ctx)

        assert envelope1.risk_level == envelope2.risk_level
        assert envelope1.allowed_pitch_range == envelope2.allowed_pitch_range
        assert envelope1.allowed_energy_range == envelope2.allowed_energy_range
        assert envelope1.allow_emphasis == envelope2.allow_emphasis
        assert envelope1.timestamp_utc == envelope2.timestamp_utc

    def test_resolver_stateless(self):
        """Test: Resolver is stateless."""
        resolver1 = P13AcousticSafetyResolver()
        resolver2 = P13AcousticSafetyResolver()

        acoustic = make_inform_acoustic_frame()
        ctx = MockPipelineContext(
            p10_acoustic=acoustic,
            p6_regime=MockRegimeEnvelope.create("INFORM"),
            p12_consistency=MockP12ConsistencyReport(is_consistent=True),
        )

        with patch.object(resolver1, '_get_timestamp_utc', return_value="2024-01-01T00:00:00+00:00"):
            with patch.object(resolver2, '_get_timestamp_utc', return_value="2024-01-01T00:00:00+00:00"):
                envelope1 = resolver1.resolve(ctx)
                envelope2 = resolver2.resolve(ctx)

        assert envelope1.risk_level == envelope2.risk_level
        assert envelope1.allowed_pitch_range == envelope2.allowed_pitch_range


# ============================================================================
# F. REGRESSION TESTS (P12 CONSISTENCY)
# ============================================================================


class TestP12ConsistencyIntegration:
    """Tests for P12 consistency integration."""

    def test_p12_mismatch_produces_caution(self):
        """Test: P12 mismatch -> CAUTION risk level."""
        acoustic = make_inform_acoustic_frame()
        ctx = MockPipelineContext(
            p10_acoustic=acoustic,
            p6_regime=MockRegimeEnvelope.create("INFORM"),
            p7_discourse_envelope=MockDiscourseEnvelope.create("EXPLANATION"),
            p12_consistency=MockP12ConsistencyReport(is_consistent=False),
        )
        envelope = run_p13_directly(ctx)

        assert envelope is not None
        assert envelope.risk_level == AcousticRiskLevel.CAUTION

    def test_p12_critical_violations_produces_blocked(self):
        """Test: P12 critical violations -> BLOCKED risk level."""
        acoustic = make_inform_acoustic_frame()
        ctx = MockPipelineContext(
            p10_acoustic=acoustic,
            p6_regime=MockRegimeEnvelope.create("INFORM"),
            p7_discourse_envelope=MockDiscourseEnvelope.create("EXPLANATION"),
            p12_consistency=MockP12ConsistencyReport(is_consistent=False, _has_critical=True),
        )
        envelope = run_p13_directly(ctx)

        assert envelope is not None
        assert envelope.risk_level == AcousticRiskLevel.BLOCKED

    def test_missing_p10_produces_blocked_envelope(self):
        """Test: Missing P10 -> BLOCKED envelope."""
        ctx = MockPipelineContext(p10_acoustic=None)
        envelope = run_p13_directly(ctx)

        assert envelope is not None
        assert envelope.is_blocked() is True
        assert envelope.risk_level == AcousticRiskLevel.BLOCKED

    def test_p12_consistent_allows_safe(self):
        """Test: P12 consistent allows SAFE risk level."""
        acoustic = make_inform_acoustic_frame()
        ctx = MockPipelineContext(
            p10_acoustic=acoustic,
            p6_regime=MockRegimeEnvelope.create("INFORM"),
            p7_discourse_envelope=MockDiscourseEnvelope.create("EXPLANATION"),
            p12_consistency=MockP12ConsistencyReport(is_consistent=True),
        )
        envelope = run_p13_directly(ctx)

        assert envelope is not None
        assert envelope.risk_level == AcousticRiskLevel.SAFE


# ============================================================================
# G. CROSS-PHASE AUTHORITY TESTS
# ============================================================================


class TestCrossPhaseAuthority:
    """Tests for cross-phase authority constraints."""

    def test_p13_reads_p10_not_modifies(self):
        """Test: P13 reads P10 but doesn't modify it."""
        acoustic = make_inform_acoustic_frame()
        original_pitch = acoustic.pitch_range
        original_energy = acoustic.energy_level

        ctx = MockPipelineContext(
            p10_acoustic=acoustic,
            p6_regime=MockRegimeEnvelope.create("INFORM"),
            p12_consistency=MockP12ConsistencyReport(is_consistent=True),
        )
        run_p13_directly(ctx)

        # P10 should be unchanged
        assert ctx.p10_acoustic.pitch_range == original_pitch
        assert ctx.p10_acoustic.energy_level == original_energy

    def test_p13_cannot_override_p10_intent(self):
        """Test: P13 envelope respects P10 intent bounds."""
        # P10 specifies narrow pitch range
        acoustic = make_acoustic_frame(pitch_range=(100, 110))

        ctx = MockPipelineContext(
            p10_acoustic=acoustic,
            p6_regime=MockRegimeEnvelope.create("INFORM"),
            p12_consistency=MockP12ConsistencyReport(is_consistent=True),
        )
        envelope = run_p13_directly(ctx)

        assert envelope is not None
        # P13 should not expand beyond P10
        assert envelope.allowed_pitch_range[1] <= 110

    def test_p13_respects_p10_suppression_flags(self):
        """Test: P13 respects P10 suppression flags."""
        acoustic = make_acoustic_frame(
            suppress_emphasis=True,
            emphasis_policy=EmphasisPolicy.NONE,
        )

        ctx = MockPipelineContext(
            p10_acoustic=acoustic,
            p6_regime=MockRegimeEnvelope.create("INFORM"),
            p12_consistency=MockP12ConsistencyReport(is_consistent=True),
        )
        envelope = run_p13_directly(ctx)

        assert envelope is not None
        # With suppress_emphasis=True, emphasis should be False
        assert envelope.allow_emphasis is False


# ============================================================================
# H. SCHEMA VALIDATION TESTS
# ============================================================================


class TestSchemaValidation:
    """Tests for schema validation."""

    def test_envelope_construction_valid(self):
        """Test: Valid envelope construction."""
        envelope = AcousticSafetyEnvelope(
            allowed_pitch_range=(100, 120),
            allowed_energy_range=(0.25, 0.45),
            allowed_variance_range=(0, 20),
            allow_emphasis=False,
            allow_pitch_contours=True,
            allow_rhythm_variation=True,
            allow_intonation_shift=True,
            risk_level=AcousticRiskLevel.SAFE,
            violations=(),
            source_regime="INFORM",
            source_discourse_act="EXPLANATION",
            source_p10_version="P10-1.0",
            source_p12_consistent=True,
        )

        assert envelope.is_safe() is True
        assert envelope.is_blocked() is False

    def test_envelope_immutability(self):
        """Test: Envelope is frozen/immutable."""
        envelope = get_blocked_envelope()

        with pytest.raises(Exception):  # FrozenInstanceError
            envelope.risk_level = AcousticRiskLevel.SAFE

    def test_envelope_violations_imply_non_safe(self):
        """Test: Violations imply non-SAFE risk level."""
        with pytest.raises(ValueError, match="violations detected but risk_level is SAFE"):
            AcousticSafetyEnvelope(
                allowed_pitch_range=(100, 120),
                allowed_energy_range=(0.25, 0.45),
                allowed_variance_range=(0, 20),
                allow_emphasis=False,
                allow_pitch_contours=True,
                allow_rhythm_variation=True,
                allow_intonation_shift=True,
                risk_level=AcousticRiskLevel.SAFE,  # Should be CAUTION
                violations=(SafetyViolation.EMOTION_AMPLIFICATION,),
                source_regime="INFORM",
                source_discourse_act="EXPLANATION",
                source_p10_version="P10-1.0",
                source_p12_consistent=True,
            )

    def test_envelope_hold_requires_all_flags_false(self):
        """Test: HOLD regime requires all flags False."""
        with pytest.raises(ValueError, match="HOLD regime requires"):
            AcousticSafetyEnvelope(
                allowed_pitch_range=(100, 110),
                allowed_energy_range=(0.25, 0.35),
                allowed_variance_range=(0, 10),
                allow_emphasis=True,  # Should be False for HOLD
                allow_pitch_contours=False,
                allow_rhythm_variation=False,
                allow_intonation_shift=False,
                risk_level=AcousticRiskLevel.BLOCKED,
                violations=(),
                source_regime="HOLD",
                source_discourse_act="DEFERRAL",
                source_p10_version="P10-1.0",
                source_p12_consistent=True,
            )

    def test_envelope_de_escalate_requires_emphasis_false(self):
        """Test: DE_ESCALATE requires emphasis False."""
        with pytest.raises(ValueError, match="DE_ESCALATE regime requires"):
            AcousticSafetyEnvelope(
                allowed_pitch_range=(100, 120),
                allowed_energy_range=(0.25, 0.40),
                allowed_variance_range=(0, 20),
                allow_emphasis=True,  # Should be False for DE_ESCALATE
                allow_pitch_contours=False,
                allow_rhythm_variation=True,
                allow_intonation_shift=True,
                risk_level=AcousticRiskLevel.CAUTION,
                violations=(),
                source_regime="DE_ESCALATE",
                source_discourse_act="REFLECTION",
                source_p10_version="P10-1.0",
                source_p12_consistent=True,
            )

    def test_envelope_to_dict(self):
        """Test: Envelope serialization."""
        envelope = get_blocked_envelope(
            source_regime="HOLD",
            source_discourse_act="DEFERRAL",
        )
        d = envelope.to_dict()

        assert d["risk_level"] == "BLOCKED"
        assert d["source_regime"] == "HOLD"
        assert d["is_blocked"] is True
        assert d["is_fully_restricted"] is True
        assert d["version"] == P13_VERSION

    def test_get_blocked_envelope_helper(self):
        """Test: get_blocked_envelope helper function."""
        envelope = get_blocked_envelope(
            source_regime="HOLD",
            source_discourse_act="DEFERRAL",
            violations=(SafetyViolation.EMOTION_AMPLIFICATION,),
        )

        assert envelope.is_blocked() is True
        assert envelope.has_violations() is True
        assert SafetyViolation.EMOTION_AMPLIFICATION in envelope.violations


# ============================================================================
# I. INTEGRATION TESTS
# ============================================================================


class TestIntegration:
    """Tests for P13 integration functions."""

    def test_maybe_run_p13_attaches_envelope(self):
        """Test: maybe_run_p13 attaches envelope to context."""
        acoustic = make_inform_acoustic_frame()
        ctx = MockPipelineContext(
            p10_acoustic=acoustic,
            p6_regime=MockRegimeEnvelope.create("INFORM"),
            p7_discourse_envelope=MockDiscourseEnvelope.create("EXPLANATION"),
            p12_consistency=MockP12ConsistencyReport(is_consistent=True),
        )

        result_ctx = maybe_run_p13(ctx)

        assert result_ctx.p13_safety_envelope is not None
        assert isinstance(result_ctx.p13_safety_envelope, AcousticSafetyEnvelope)

    def test_maybe_run_p13_idempotent(self):
        """Test: maybe_run_p13 is idempotent."""
        acoustic = make_inform_acoustic_frame()
        ctx = MockPipelineContext(
            p10_acoustic=acoustic,
            p6_regime=MockRegimeEnvelope.create("INFORM"),
            p7_discourse_envelope=MockDiscourseEnvelope.create("EXPLANATION"),
            p12_consistency=MockP12ConsistencyReport(is_consistent=True),
        )

        maybe_run_p13(ctx)
        first_envelope = ctx.p13_safety_envelope
        first_timestamp = first_envelope.timestamp_utc

        # Run again
        maybe_run_p13(ctx)
        second_envelope = ctx.p13_safety_envelope

        # Should be the same object (idempotent)
        assert second_envelope.timestamp_utc == first_timestamp

    def test_maybe_run_p13_no_p10_returns_blocked(self):
        """Test: maybe_run_p13 with no P10 returns BLOCKED envelope."""
        ctx = MockPipelineContext(p10_acoustic=None)
        result_ctx = maybe_run_p13(ctx)

        assert result_ctx.p13_safety_envelope is not None
        assert result_ctx.p13_safety_envelope.is_blocked() is True

    def test_run_p13_directly_no_context_modification(self):
        """Test: run_p13_directly doesn't modify context."""
        acoustic = make_inform_acoustic_frame()
        ctx = MockPipelineContext(
            p10_acoustic=acoustic,
            p6_regime=MockRegimeEnvelope.create("INFORM"),
            p12_consistency=MockP12ConsistencyReport(is_consistent=True),
        )

        envelope = run_p13_directly(ctx)

        assert envelope is not None
        assert ctx.p13_safety_envelope is None  # Not attached

    def test_accessor_functions_no_envelope(self):
        """Test: Accessor functions with no envelope."""
        ctx = MockPipelineContext()

        assert is_blocked(ctx) is True  # Conservative default
        assert is_safe(ctx) is False
        assert has_violations(ctx) is False
        assert get_violations(ctx) == []
        assert allows_emphasis(ctx) is False
        assert is_fully_restricted(ctx) is True
        assert get_max_energy(ctx) == 0.35  # HOLD max
        assert get_pitch_variance_limit(ctx) == 10  # HOLD max

    def test_accessor_functions_with_envelope(self):
        """Test: Accessor functions with envelope."""
        acoustic = make_inform_acoustic_frame()
        ctx = MockPipelineContext(
            p10_acoustic=acoustic,
            p6_regime=MockRegimeEnvelope.create("INFORM"),
            p7_discourse_envelope=MockDiscourseEnvelope.create("EXPLANATION"),
            p12_consistency=MockP12ConsistencyReport(is_consistent=True),
        )
        maybe_run_p13(ctx)

        assert is_safe(ctx) is True
        assert is_blocked(ctx) is False
        assert has_violations(ctx) is False

    def test_singleton_resolver(self):
        """Test: Singleton resolver pattern."""
        r1 = get_p13_resolver()
        r2 = get_p13_resolver()
        assert r1 is r2


# ============================================================================
# J. SAFETY VIOLATION DETECTION TESTS
# ============================================================================


class TestSafetyViolationDetection:
    """Tests for safety violation detection functions."""

    def test_detect_emotion_amplification_under_hold(self):
        """Test: Emotion amplification detected under HOLD."""
        violation = detect_emotion_amplification(
            source_regime="HOLD",
            p10_energy=0.5,  # High energy under HOLD
            p10_emphasis_policy="limited",
            p10_suppress_emotion=False,
        )
        assert violation == SafetyViolation.EMOTION_AMPLIFICATION

    def test_detect_emotion_amplification_suppressed(self):
        """Test: No emotion amplification if suppressed."""
        violation = detect_emotion_amplification(
            source_regime="HOLD",
            p10_energy=0.25,  # Low energy
            p10_emphasis_policy="none",
            p10_suppress_emotion=True,
        )
        assert violation is None

    def test_detect_certainty_escalation_under_reflexive(self):
        """Test: Certainty escalation detected under REFLEXIVE."""
        violation = detect_certainty_escalation(
            source_regime="REFLECT",
            p10_suppress_certainty=False,
            p10_emphasis_policy="limited",
            p10_max_stressed_tokens=1,
            grounding_mode="REFLEXIVE",
        )
        assert violation == SafetyViolation.CERTAINTY_ESCALATION

    def test_detect_certainty_escalation_suppressed(self):
        """Test: No certainty escalation if suppressed."""
        violation = detect_certainty_escalation(
            source_regime="REFLECT",
            p10_suppress_certainty=True,
            p10_emphasis_policy="none",
            p10_max_stressed_tokens=0,
            grounding_mode="REFLEXIVE",
        )
        assert violation is None

    def test_detect_authority_signaling_under_reflexive(self):
        """Test: Authority signaling detected under REFLEXIVE."""
        violation = detect_authority_signaling(
            source_regime="REFLECT",
            source_discourse_act="REFLECTION",
            grounding_mode="REFLEXIVE",
            p10_suppress_emphasis=False,
            p10_emphasis_policy="limited",
            p10_max_stressed_tokens=1,
            p10_energy=0.5,
        )
        assert violation == SafetyViolation.AUTHORITY_SIGNALING

    def test_detect_excessive_variance_under_hold(self):
        """Test: Excessive variance detected under HOLD."""
        violation = detect_excessive_variance(
            source_regime="HOLD",
            p10_pitch_range=(90, 130),  # 40 Hz variance
            p10_energy=0.5,
        )
        assert violation == SafetyViolation.EXCESSIVE_VARIANCE

    def test_detect_excessive_variance_within_bounds(self):
        """Test: No excessive variance if within bounds."""
        violation = detect_excessive_variance(
            source_regime="HOLD",
            p10_pitch_range=(95, 105),  # 10 Hz variance
            p10_energy=0.25,
        )
        assert violation is None

    def test_detect_prosodic_manipulation_high_energy_variance(self):
        """Test: Prosodic manipulation with high energy + variance."""
        violation = detect_prosodic_manipulation(
            source_regime="INFORM",
            source_discourse_act="EXPLANATION",
            p10_pitch_range=(90, 140),  # Very high variance
            p10_energy=0.58,  # Very high energy
            p10_emphasis_policy="limited",
            p10_max_stressed_tokens=1,
        )
        assert violation == SafetyViolation.PROSODIC_MANIPULATION

    def test_detect_prosodic_manipulation_deferral_with_stress(self):
        """Test: Prosodic manipulation in DEFERRAL with stress."""
        violation = detect_prosodic_manipulation(
            source_regime="HOLD",
            source_discourse_act="DEFERRAL",
            p10_pitch_range=(95, 105),
            p10_energy=0.25,
            p10_emphasis_policy="limited",
            p10_max_stressed_tokens=1,  # Should be 0 for DEFERRAL
        )
        assert violation == SafetyViolation.PROSODIC_MANIPULATION


# ============================================================================
# K. BOUNDS COMPUTATION TESTS
# ============================================================================


class TestBoundsComputation:
    """Tests for bounds computation functions."""

    def test_compute_pitch_bounds_hold(self):
        """Test: Pitch bounds for HOLD regime."""
        bounds = compute_pitch_bounds(
            source_regime="HOLD",
            p10_pitch_range=(90, 140),
            risk_level=AcousticRiskLevel.BLOCKED,
        )
        assert bounds[0] >= HOLD_PITCH_MIN
        assert bounds[1] <= HOLD_PITCH_MAX

    def test_compute_pitch_bounds_de_escalate(self):
        """Test: Pitch bounds for DE_ESCALATE regime."""
        bounds = compute_pitch_bounds(
            source_regime="DE_ESCALATE",
            p10_pitch_range=(90, 140),
            risk_level=AcousticRiskLevel.CAUTION,
        )
        assert bounds[1] <= 125  # DE_ESCALATE max

    def test_compute_energy_bounds_hold(self):
        """Test: Energy bounds for HOLD regime."""
        bounds = compute_energy_bounds(
            source_regime="HOLD",
            p10_energy=0.50,
            grounding_mode=None,
            risk_level=AcousticRiskLevel.BLOCKED,
        )
        assert bounds[0] >= HOLD_ENERGY_MIN
        assert bounds[1] <= HOLD_ENERGY_MAX

    def test_compute_energy_bounds_reflexive(self):
        """Test: Energy bounds for REFLEXIVE grounding."""
        bounds = compute_energy_bounds(
            source_regime="REFLECT",
            p10_energy=0.50,
            grounding_mode="REFLEXIVE",
            risk_level=AcousticRiskLevel.CAUTION,
        )
        assert bounds[1] <= 0.40  # REFLEXIVE max

    def test_compute_variance_bounds_hold(self):
        """Test: Variance bounds for HOLD regime."""
        bounds = compute_variance_bounds(
            source_regime="HOLD",
            p10_pitch_range=(90, 130),  # 40 Hz variance
            grounding_mode=None,
            risk_level=AcousticRiskLevel.BLOCKED,
        )
        assert bounds[1] <= HOLD_VARIANCE_MAX

    def test_compute_expression_flags_hold(self):
        """Test: Expression flags for HOLD regime."""
        flags = compute_expression_flags(
            source_regime="HOLD",
            source_discourse_act="DEFERRAL",
            grounding_mode=None,
            p10_emphasis_policy="limited",
            p10_suppress_emphasis=False,
            risk_level=AcousticRiskLevel.BLOCKED,
        )
        assert flags["allow_emphasis"] is False
        assert flags["allow_pitch_contours"] is False
        assert flags["allow_rhythm_variation"] is False
        assert flags["allow_intonation_shift"] is False

    def test_compute_expression_flags_inform(self):
        """Test: Expression flags for INFORM regime."""
        flags = compute_expression_flags(
            source_regime="INFORM",
            source_discourse_act="EXPLANATION",
            grounding_mode=None,
            p10_emphasis_policy="limited",
            p10_suppress_emphasis=False,
            risk_level=AcousticRiskLevel.SAFE,
        )
        # Under SAFE INFORM, rhythm and intonation allowed
        assert flags["allow_rhythm_variation"] is True
        assert flags["allow_intonation_shift"] is True


# ============================================================================
# L. EDGE CASES
# ============================================================================


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_unknown_regime_handled(self):
        """Test: Unknown regime handled gracefully."""
        acoustic = make_acoustic_frame(source_regime="UNKNOWN")
        ctx = MockPipelineContext(
            p10_acoustic=acoustic,
            p6_regime=MockRegimeEnvelope.create("UNKNOWN"),
            p12_consistency=MockP12ConsistencyReport(is_consistent=True),
        )
        envelope = run_p13_directly(ctx)

        # Should produce valid envelope (not crash)
        assert envelope is not None

    def test_missing_grounding_mode_handled(self):
        """Test: Missing grounding mode handled gracefully."""
        acoustic = make_inform_acoustic_frame()
        ctx = MockPipelineContext(
            p10_acoustic=acoustic,
            p6_regime=MockRegimeEnvelope.create("INFORM"),
            phase_minus_one=None,  # No grounding
            p12_consistency=MockP12ConsistencyReport(is_consistent=True),
        )
        envelope = run_p13_directly(ctx)

        assert envelope is not None
        assert envelope.risk_level == AcousticRiskLevel.SAFE

    def test_missing_discourse_handled(self):
        """Test: Missing discourse envelope handled gracefully."""
        acoustic = make_inform_acoustic_frame()
        ctx = MockPipelineContext(
            p10_acoustic=acoustic,
            p6_regime=MockRegimeEnvelope.create("INFORM"),
            p7_discourse_envelope=None,
            p12_consistency=MockP12ConsistencyReport(is_consistent=True),
        )
        envelope = run_p13_directly(ctx)

        assert envelope is not None
        assert envelope.source_discourse_act == "UNKNOWN"

    def test_missing_p12_handled(self):
        """Test: Missing P12 report handled gracefully."""
        acoustic = make_inform_acoustic_frame()
        ctx = MockPipelineContext(
            p10_acoustic=acoustic,
            p6_regime=MockRegimeEnvelope.create("INFORM"),
            p12_consistency=None,
        )
        envelope = run_p13_directly(ctx)

        assert envelope is not None
        # Missing P12 = inconsistent = CAUTION
        assert envelope.risk_level == AcousticRiskLevel.CAUTION

    def test_minimal_context(self):
        """Test: Minimal context with only P10."""
        acoustic = make_inform_acoustic_frame()
        ctx = MockPipelineContext(p10_acoustic=acoustic)
        envelope = run_p13_directly(ctx)

        assert envelope is not None
        # Should produce CAUTION (missing P12)
        assert envelope.risk_level in (AcousticRiskLevel.CAUTION, AcousticRiskLevel.SAFE)


# ============================================================================
# M. MULTIPLE VIOLATIONS TESTS
# ============================================================================


class TestMultipleViolations:
    """Tests for scenarios with multiple violations."""

    def test_multiple_violations_detected(self):
        """Test: Multiple violations can be detected."""
        acoustic = make_acoustic_frame(
            pitch_range=(90, 140),  # High variance
            energy_level=0.55,  # High energy
            source_regime="HOLD",
            suppress_emotion=False,
            suppress_certainty=False,
            suppress_emphasis=False,
            emphasis_policy=EmphasisPolicy.LIMITED,
            max_stressed_tokens=1,
        )
        ctx = MockPipelineContext(
            p10_acoustic=acoustic,
            p6_regime=MockRegimeEnvelope.create("HOLD"),
            p7_discourse_envelope=MockDiscourseEnvelope.create("DEFERRAL"),
        )
        envelope = run_p13_directly(ctx)

        assert envelope is not None
        assert envelope.has_violations() is True
        assert len(envelope.violations) >= 1

    def test_violations_result_in_blocked_or_caution(self):
        """Test: Violations result in BLOCKED or CAUTION."""
        acoustic = make_acoustic_frame(
            energy_level=0.55,
            source_regime="REFLECT",
            suppress_emotion=False,
        )
        ctx = MockPipelineContext(
            p10_acoustic=acoustic,
            p6_regime=MockRegimeEnvelope.create("REFLECT"),
            p12_consistency=MockP12ConsistencyReport(is_consistent=True),
        )
        envelope = run_p13_directly(ctx)

        assert envelope is not None
        assert envelope.risk_level in (AcousticRiskLevel.CAUTION, AcousticRiskLevel.BLOCKED)
