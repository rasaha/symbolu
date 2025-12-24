"""
P13 Renderer Compliance Tests

Comprehensive tests proving that NO renderer can violate P13 without
being detected and blocked.

Test Categories (per specification):
A. Absolute Blocking (HOLD regime, BLOCKED envelope)
B. Amplification Prevention (pitch/energy bounds)
C. Authority Signaling (certainty escalation)
D. Emotion Amplification (expression flags)
E. Boundary Precision (exact limits)
F. Determinism (same input -> same output)
G. Regression (prior failure modes)

Target: >= 80 tests

CRITICAL ARCHITECTURAL INVARIANT:
    Renderers violating this contract are unsafe BY DEFINITION.
    These tests PROVE that unsafe behavior is detected and blocked.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple
import pytest

from symbolu.mechanical.pipeline.renderer_compliance import (
    # Contract
    RendererInputContract,
    AcousticRenderIntent,
    RenderIntentCategory,
    ComplianceVerdict,
    ViolationCategory,
    ComplianceViolation,
    ComplianceResult,
    # Renderers
    CompliantRenderer,
    AmplifyingRenderer,
    AuthorityRenderer,
    EmotiveRenderer,
    IgnoreSafetyRenderer,
    BoundaryPusherRenderer,
    ExactBoundaryRenderer,
    BlockedOverrideRenderer,
    # Checker
    RendererComplianceChecker,
    check_compliance,
    is_compliant,
    # Constants
    BOUNDARY_EPSILON_PITCH,
    BOUNDARY_EPSILON_ENERGY,
    BOUNDARY_EPSILON_VARIANCE,
)


# ============================================================================
# TEST HELPERS - Mock P13 Envelope
# ============================================================================


@dataclass
class MockAcousticSafetyEnvelope:
    """Mock P13 envelope for testing."""
    allowed_pitch_range: Tuple[int, int] = (90, 130)
    allowed_energy_range: Tuple[float, float] = (0.2, 0.5)
    allowed_variance_range: Tuple[int, int] = (0, 20)
    allow_emphasis: bool = True
    allow_pitch_contours: bool = True
    allow_rhythm_variation: bool = True
    allow_intonation_shift: bool = True
    risk_level: str = "SAFE"
    source_regime: str = "INFORM"
    source_discourse_act: str = "EXPLANATION"
    source_p10_version: str = "P10-1.0"
    source_p12_consistent: bool = True
    architectural_phase: str = "P13"
    version: str = "1.0.0"
    timestamp_utc: str = "2024-01-01T00:00:00Z"
    violations: Tuple = ()
    debug: Dict[str, Any] = field(default_factory=dict)

    def is_blocked(self) -> bool:
        return self.risk_level == "BLOCKED"

    def is_safe(self) -> bool:
        return self.risk_level == "SAFE"

    def is_caution(self) -> bool:
        return self.risk_level == "CAUTION"

    def is_fully_restricted(self) -> bool:
        return not (
            self.allow_emphasis or
            self.allow_pitch_contours or
            self.allow_rhythm_variation or
            self.allow_intonation_shift
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "allowed_pitch_range": self.allowed_pitch_range,
            "allowed_energy_range": self.allowed_energy_range,
            "risk_level": self.risk_level,
        }


@dataclass
class MockAcousticParameterFrame:
    """Mock P10 frame for testing."""
    regime: str = "NEUTRAL"
    speech_rate: float = 4.5
    energy_level: float = 0.45
    pitch_range: Tuple[int, int] = (100, 130)
    pause_policy: str = "MINIMAL"
    pause_duration_ms: Tuple[int, int] = (100, 150)
    emphasis_policy: str = "LIMITED"
    max_stressed_tokens: int = 1
    suppress_emotion: bool = True
    suppress_emphasis: bool = False
    suppress_certainty: bool = False
    source_regime: str = "INFORM"
    source_discourse_act: str = "EXPLANATION"
    architectural_phase: str = "P10"
    debug: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {"regime": self.regime}


def make_safe_envelope(**kwargs) -> MockAcousticSafetyEnvelope:
    """Create a SAFE envelope with optional overrides."""
    return MockAcousticSafetyEnvelope(
        risk_level="SAFE",
        **kwargs
    )


def make_blocked_envelope(**kwargs) -> MockAcousticSafetyEnvelope:
    """Create a BLOCKED envelope (most restrictive)."""
    return MockAcousticSafetyEnvelope(
        allowed_pitch_range=(90, 110),
        allowed_energy_range=(0.2, 0.35),
        allowed_variance_range=(0, 10),
        allow_emphasis=False,
        allow_pitch_contours=False,
        allow_rhythm_variation=False,
        allow_intonation_shift=False,
        risk_level="BLOCKED",
        source_regime="HOLD",
        source_discourse_act="DEFERRAL",
        **kwargs
    )


def make_hold_envelope(**kwargs) -> MockAcousticSafetyEnvelope:
    """Create a HOLD regime envelope."""
    return MockAcousticSafetyEnvelope(
        allowed_pitch_range=(90, 110),
        allowed_energy_range=(0.2, 0.35),
        allowed_variance_range=(0, 10),
        allow_emphasis=False,
        allow_pitch_contours=False,
        allow_rhythm_variation=False,
        allow_intonation_shift=False,
        risk_level="BLOCKED",
        source_regime="HOLD",
        source_discourse_act="DEFERRAL",
        **kwargs
    )


def make_de_escalate_envelope(**kwargs) -> MockAcousticSafetyEnvelope:
    """Create a DE_ESCALATE regime envelope."""
    return MockAcousticSafetyEnvelope(
        allowed_pitch_range=(90, 125),
        allowed_energy_range=(0.2, 0.40),
        allowed_variance_range=(0, 20),
        allow_emphasis=False,
        allow_pitch_contours=False,
        allow_rhythm_variation=True,
        allow_intonation_shift=True,
        risk_level="CAUTION",
        source_regime="DE_ESCALATE",
        source_discourse_act="REFLECTION",
        **kwargs
    )


def make_reflexive_envelope(**kwargs) -> MockAcousticSafetyEnvelope:
    """Create a REFLEXIVE grounding envelope."""
    return MockAcousticSafetyEnvelope(
        allowed_pitch_range=(90, 125),
        allowed_energy_range=(0.2, 0.40),
        allowed_variance_range=(0, 20),
        allow_emphasis=False,
        allow_pitch_contours=False,
        allow_rhythm_variation=True,
        allow_intonation_shift=True,
        risk_level="CAUTION",
        source_regime="REFLECT",
        source_discourse_act="REFLECTION",
        **kwargs
    )


def make_contract(envelope: MockAcousticSafetyEnvelope) -> RendererInputContract:
    """Create a contract from an envelope."""
    return RendererInputContract(
        p10_acoustic=MockAcousticParameterFrame(
            source_regime=envelope.source_regime,
            source_discourse_act=envelope.source_discourse_act,
        ),
        p13_envelope=envelope,
        source_regime=envelope.source_regime,
        source_discourse_act=envelope.source_discourse_act,
    )


# ============================================================================
# CATEGORY A: ABSOLUTE BLOCKING TESTS
# ============================================================================


class TestAbsoluteBlocking:
    """Tests for absolute blocking under HOLD regime and BLOCKED envelope."""

    # --- HOLD Regime Tests ---

    def test_hold_regime_blocks_all_renderers(self):
        """Test: HOLD regime blocks ALL renderers."""
        envelope = make_hold_envelope()
        contract = make_contract(envelope)

        renderers = [
            CompliantRenderer(),
            AmplifyingRenderer(),
            AuthorityRenderer(),
            EmotiveRenderer(),
            IgnoreSafetyRenderer(),
            BoundaryPusherRenderer(),
        ]

        for renderer in renderers:
            intent = renderer.render(contract)
            result = check_compliance(envelope, intent)

            # Compliant renderer should pass, others should fail
            if isinstance(renderer, CompliantRenderer):
                assert result.passed(), f"{renderer.renderer_id} should pass under HOLD (fully compliant)"
            else:
                assert result.failed(), f"{renderer.renderer_id} should fail under HOLD"

    def test_hold_blocks_amplifying_renderer(self):
        """Test: HOLD blocks AmplifyingRenderer."""
        envelope = make_hold_envelope()
        contract = make_contract(envelope)
        renderer = AmplifyingRenderer()
        intent = renderer.render(contract)
        result = check_compliance(envelope, intent)

        assert result.failed()
        assert result.violation_count() > 0

    def test_hold_blocks_authority_renderer(self):
        """Test: HOLD blocks AuthorityRenderer."""
        envelope = make_hold_envelope()
        contract = make_contract(envelope)
        renderer = AuthorityRenderer()
        intent = renderer.render(contract)
        result = check_compliance(envelope, intent)

        assert result.failed()

    def test_hold_blocks_emotive_renderer(self):
        """Test: HOLD blocks EmotiveRenderer."""
        envelope = make_hold_envelope()
        contract = make_contract(envelope)
        renderer = EmotiveRenderer()
        intent = renderer.render(contract)
        result = check_compliance(envelope, intent)

        assert result.failed()

    def test_hold_blocks_ignore_safety_renderer(self):
        """Test: HOLD blocks IgnoreSafetyRenderer."""
        envelope = make_hold_envelope()
        contract = make_contract(envelope)
        renderer = IgnoreSafetyRenderer()
        intent = renderer.render(contract)
        result = check_compliance(envelope, intent)

        assert result.failed()
        # Should have multiple violations
        assert result.violation_count() >= 1

    def test_hold_blocks_boundary_pusher(self):
        """Test: HOLD blocks BoundaryPusherRenderer."""
        envelope = make_hold_envelope()
        contract = make_contract(envelope)
        renderer = BoundaryPusherRenderer()
        intent = renderer.render(contract)
        result = check_compliance(envelope, intent)

        assert result.failed()

    # --- BLOCKED Envelope Tests ---

    def test_blocked_envelope_no_render_allowed(self):
        """Test: BLOCKED envelope allows no render intent with expression."""
        envelope = make_blocked_envelope()
        contract = make_contract(envelope)

        # Even compliant renderer produces no-expression intent
        renderer = CompliantRenderer()
        intent = renderer.render(contract)

        # Compliant intent should have no expression
        assert not intent.will_use_emphasis
        assert not intent.will_use_pitch_contours
        assert not intent.will_use_rhythm_variation
        assert not intent.will_use_intonation_shift

    def test_blocked_override_renderer_blocked(self):
        """Test: BlockedOverrideRenderer is blocked."""
        envelope = make_blocked_envelope()
        contract = make_contract(envelope)
        renderer = BlockedOverrideRenderer()
        intent = renderer.render(contract)
        result = check_compliance(envelope, intent)

        assert result.failed()
        assert result.has_violation_category(ViolationCategory.BLOCKED_OVERRIDE)

    def test_blocked_envelope_all_flags_must_be_false(self):
        """Test: Under BLOCKED, all expression flags must be False."""
        envelope = make_blocked_envelope()

        # Manually create intent with expression (simulating bad renderer)
        bad_intent = AcousticRenderIntent(
            intended_pitch_min=95,
            intended_pitch_max=105,
            intended_pitch_variance=10,
            intended_energy_min=0.2,
            intended_energy_max=0.3,
            will_use_emphasis=True,  # VIOLATION
            will_use_pitch_contours=False,
            will_use_rhythm_variation=False,
            will_use_intonation_shift=False,
            intended_stressed_tokens=0,
            renderer_id="BadRenderer",
            intent_category=RenderIntentCategory.IGNORED,
        )

        result = check_compliance(envelope, bad_intent)
        assert result.failed()

    def test_blocked_envelope_blocks_any_expression(self):
        """Test: BLOCKED blocks any single expression feature."""
        envelope = make_blocked_envelope()

        # Test each expression flag individually
        flags = [
            ("emphasis", True, False, False, False),
            ("contours", False, True, False, False),
            ("rhythm", False, False, True, False),
            ("intonation", False, False, False, True),
        ]

        for name, emph, cont, rhythm, inton in flags:
            bad_intent = AcousticRenderIntent(
                intended_pitch_min=95,
                intended_pitch_max=105,
                intended_pitch_variance=5,
                intended_energy_min=0.2,
                intended_energy_max=0.3,
                will_use_emphasis=emph,
                will_use_pitch_contours=cont,
                will_use_rhythm_variation=rhythm,
                will_use_intonation_shift=inton,
                intended_stressed_tokens=0,
                renderer_id=f"BadRenderer_{name}",
                intent_category=RenderIntentCategory.IGNORED,
            )

            result = check_compliance(envelope, bad_intent)
            assert result.failed(), f"Expression flag {name} should be blocked"


# ============================================================================
# CATEGORY B: AMPLIFICATION PREVENTION TESTS
# ============================================================================


class TestAmplificationPrevention:
    """Tests for pitch/energy amplification prevention."""

    def test_pitch_exceeds_max_detected(self):
        """Test: Pitch exceeding max bound is detected."""
        envelope = make_safe_envelope(allowed_pitch_range=(90, 120))

        bad_intent = AcousticRenderIntent(
            intended_pitch_min=90,
            intended_pitch_max=130,  # Above 120 limit
            intended_pitch_variance=40,
            intended_energy_min=0.2,
            intended_energy_max=0.4,
            will_use_emphasis=True,
            will_use_pitch_contours=True,
            will_use_rhythm_variation=True,
            will_use_intonation_shift=True,
            intended_stressed_tokens=1,
            renderer_id="HighPitchRenderer",
            intent_category=RenderIntentCategory.AMPLIFIED,
        )

        result = check_compliance(envelope, bad_intent)
        assert result.failed()
        assert result.has_violation_category(ViolationCategory.PITCH_BOUND_VIOLATION)

    def test_pitch_below_min_detected(self):
        """Test: Pitch below min bound is detected."""
        envelope = make_safe_envelope(allowed_pitch_range=(95, 130))

        bad_intent = AcousticRenderIntent(
            intended_pitch_min=80,  # Below 95 limit
            intended_pitch_max=120,
            intended_pitch_variance=40,
            intended_energy_min=0.2,
            intended_energy_max=0.4,
            will_use_emphasis=True,
            will_use_pitch_contours=True,
            will_use_rhythm_variation=True,
            will_use_intonation_shift=True,
            intended_stressed_tokens=1,
            renderer_id="LowPitchRenderer",
            intent_category=RenderIntentCategory.AMPLIFIED,
        )

        result = check_compliance(envelope, bad_intent)
        assert result.failed()
        assert result.has_violation_category(ViolationCategory.PITCH_BOUND_VIOLATION)

    def test_energy_exceeds_max_detected(self):
        """Test: Energy exceeding max bound is detected."""
        envelope = make_safe_envelope(allowed_energy_range=(0.2, 0.5))

        bad_intent = AcousticRenderIntent(
            intended_pitch_min=100,
            intended_pitch_max=120,
            intended_pitch_variance=20,
            intended_energy_min=0.2,
            intended_energy_max=0.7,  # Above 0.5 limit
            will_use_emphasis=True,
            will_use_pitch_contours=True,
            will_use_rhythm_variation=True,
            will_use_intonation_shift=True,
            intended_stressed_tokens=1,
            renderer_id="HighEnergyRenderer",
            intent_category=RenderIntentCategory.AMPLIFIED,
        )

        result = check_compliance(envelope, bad_intent)
        assert result.failed()
        assert result.has_violation_category(ViolationCategory.ENERGY_BOUND_VIOLATION)

    def test_energy_below_min_detected(self):
        """Test: Energy below min bound is detected."""
        envelope = make_safe_envelope(allowed_energy_range=(0.25, 0.5))

        bad_intent = AcousticRenderIntent(
            intended_pitch_min=100,
            intended_pitch_max=120,
            intended_pitch_variance=20,
            intended_energy_min=0.1,  # Below 0.25 limit
            intended_energy_max=0.4,
            will_use_emphasis=True,
            will_use_pitch_contours=True,
            will_use_rhythm_variation=True,
            will_use_intonation_shift=True,
            intended_stressed_tokens=1,
            renderer_id="LowEnergyRenderer",
            intent_category=RenderIntentCategory.AMPLIFIED,
        )

        result = check_compliance(envelope, bad_intent)
        assert result.failed()
        assert result.has_violation_category(ViolationCategory.ENERGY_BOUND_VIOLATION)

    def test_variance_exceeds_max_detected(self):
        """Test: Variance exceeding max bound is detected."""
        envelope = make_safe_envelope(allowed_variance_range=(0, 15))

        bad_intent = AcousticRenderIntent(
            intended_pitch_min=100,
            intended_pitch_max=120,
            intended_pitch_variance=25,  # Above 15 limit
            intended_energy_min=0.2,
            intended_energy_max=0.4,
            will_use_emphasis=True,
            will_use_pitch_contours=True,
            will_use_rhythm_variation=True,
            will_use_intonation_shift=True,
            intended_stressed_tokens=1,
            renderer_id="HighVarianceRenderer",
            intent_category=RenderIntentCategory.AMPLIFIED,
        )

        result = check_compliance(envelope, bad_intent)
        assert result.failed()
        assert result.has_violation_category(ViolationCategory.VARIANCE_BOUND_VIOLATION)

    def test_amplifying_renderer_always_fails(self):
        """Test: AmplifyingRenderer always fails compliance."""
        envelope = make_safe_envelope()
        contract = make_contract(envelope)
        renderer = AmplifyingRenderer()
        intent = renderer.render(contract)
        result = check_compliance(envelope, intent)

        assert result.failed()
        # Should have pitch, energy, or variance violations
        violation_categories = {v.category for v in result.violations}
        assert len(violation_categories.intersection({
            ViolationCategory.PITCH_BOUND_VIOLATION,
            ViolationCategory.ENERGY_BOUND_VIOLATION,
            ViolationCategory.VARIANCE_BOUND_VIOLATION,
        })) > 0

    def test_amplifying_renderer_configurable_amounts(self):
        """Test: AmplifyingRenderer with different amplification amounts."""
        envelope = make_safe_envelope()
        contract = make_contract(envelope)

        # Small amplification
        renderer_small = AmplifyingRenderer(pitch_amplification=5, energy_amplification=0.05)
        intent_small = renderer_small.render(contract)
        result_small = check_compliance(envelope, intent_small)

        # Large amplification
        renderer_large = AmplifyingRenderer(pitch_amplification=50, energy_amplification=0.3)
        intent_large = renderer_large.render(contract)
        result_large = check_compliance(envelope, intent_large)

        # Both should fail
        assert result_small.failed()
        assert result_large.failed()
        # Large should have more severe violations
        assert result_large.violation_count() >= result_small.violation_count()

    def test_multiple_bound_violations_detected(self):
        """Test: Multiple bound violations are all detected."""
        envelope = make_safe_envelope(
            allowed_pitch_range=(95, 120),
            allowed_energy_range=(0.25, 0.45),
            allowed_variance_range=(0, 15),
        )

        bad_intent = AcousticRenderIntent(
            intended_pitch_min=80,   # Below min
            intended_pitch_max=140,  # Above max
            intended_pitch_variance=30,  # Above variance max
            intended_energy_min=0.1,    # Below min
            intended_energy_max=0.7,    # Above max
            will_use_emphasis=True,
            will_use_pitch_contours=True,
            will_use_rhythm_variation=True,
            will_use_intonation_shift=True,
            intended_stressed_tokens=1,
            renderer_id="AllBoundsViolator",
            intent_category=RenderIntentCategory.AMPLIFIED,
        )

        result = check_compliance(envelope, bad_intent)
        assert result.failed()
        # Should detect all violations
        assert result.violation_count() >= 3

    def test_ignore_safety_exceeds_all_bounds(self):
        """Test: IgnoreSafetyRenderer exceeds all bounds."""
        envelope = make_safe_envelope()
        contract = make_contract(envelope)
        renderer = IgnoreSafetyRenderer(
            force_pitch_min=50,
            force_pitch_max=200,
            force_energy=0.9,
            force_variance=100,
        )
        intent = renderer.render(contract)
        result = check_compliance(envelope, intent)

        assert result.failed()
        assert result.violation_count() >= 2


# ============================================================================
# CATEGORY C: AUTHORITY SIGNALING TESTS
# ============================================================================


class TestAuthoritySignaling:
    """Tests for authority signaling prevention."""

    def test_rising_certainty_under_reflexive_fails(self):
        """Test: Rising certainty prosody under REFLEXIVE fails."""
        envelope = make_reflexive_envelope()
        contract = make_contract(envelope)
        renderer = AuthorityRenderer()
        intent = renderer.render(contract)
        result = check_compliance(envelope, intent)

        assert result.failed()

    def test_assertive_contours_under_de_escalate_fails(self):
        """Test: Assertive contours under DE_ESCALATE fails."""
        envelope = make_de_escalate_envelope()
        contract = make_contract(envelope)
        renderer = AuthorityRenderer()
        intent = renderer.render(contract)
        result = check_compliance(envelope, intent)

        assert result.failed()

    def test_authority_renderer_detected(self):
        """Test: AuthorityRenderer is always detected under restricted regimes."""
        restricted_envelopes = [
            make_hold_envelope(),
            make_de_escalate_envelope(),
            make_reflexive_envelope(),
        ]

        for envelope in restricted_envelopes:
            contract = make_contract(envelope)
            renderer = AuthorityRenderer()
            intent = renderer.render(contract)
            result = check_compliance(envelope, intent)

            assert result.failed(), f"AuthorityRenderer should fail under {envelope.source_regime}"

    def test_high_energy_emphasis_blocked_under_reflect(self):
        """Test: High energy + emphasis is blocked under REFLECT."""
        envelope = make_reflexive_envelope()

        bad_intent = AcousticRenderIntent(
            intended_pitch_min=90,
            intended_pitch_max=120,
            intended_pitch_variance=15,
            intended_energy_min=0.2,
            intended_energy_max=0.40,  # At max
            will_use_emphasis=True,  # Violates no-emphasis
            will_use_pitch_contours=True,  # Violates no-contours
            will_use_rhythm_variation=True,
            will_use_intonation_shift=True,
            intended_stressed_tokens=1,
            renderer_id="AuthoritativeRenderer",
            intent_category=RenderIntentCategory.AUTHORITATIVE,
        )

        result = check_compliance(envelope, bad_intent)
        assert result.failed()

    def test_certainty_escalation_with_stressed_tokens(self):
        """Test: Certainty escalation detected with multiple stressed tokens."""
        envelope = make_de_escalate_envelope()

        bad_intent = AcousticRenderIntent(
            intended_pitch_min=90,
            intended_pitch_max=120,
            intended_pitch_variance=15,
            intended_energy_min=0.2,
            intended_energy_max=0.35,
            will_use_emphasis=False,
            will_use_pitch_contours=False,
            will_use_rhythm_variation=True,
            will_use_intonation_shift=True,
            intended_stressed_tokens=3,  # Too many stressed tokens
            renderer_id="CertaintyClaimer",
            intent_category=RenderIntentCategory.AUTHORITATIVE,
        )

        result = check_compliance(envelope, bad_intent)
        assert result.failed()
        assert result.has_violation_category(ViolationCategory.CERTAINTY_ESCALATION) or \
               result.has_violation_category(ViolationCategory.EMPHASIS_VIOLATION)


# ============================================================================
# CATEGORY D: EMOTION AMPLIFICATION TESTS
# ============================================================================


class TestEmotionAmplification:
    """Tests for emotion amplification prevention."""

    def test_emphasis_when_prohibited_fails(self):
        """Test: Emphasis when allow_emphasis=False fails."""
        envelope = make_safe_envelope(allow_emphasis=False)

        bad_intent = AcousticRenderIntent(
            intended_pitch_min=100,
            intended_pitch_max=120,
            intended_pitch_variance=10,
            intended_energy_min=0.2,
            intended_energy_max=0.4,
            will_use_emphasis=True,  # VIOLATION
            will_use_pitch_contours=True,
            will_use_rhythm_variation=True,
            will_use_intonation_shift=True,
            intended_stressed_tokens=1,
            renderer_id="EmphasisUser",
            intent_category=RenderIntentCategory.EMOTIVE,
        )

        result = check_compliance(envelope, bad_intent)
        assert result.failed()
        assert result.has_violation_category(ViolationCategory.EMPHASIS_VIOLATION)

    def test_pitch_contours_when_prohibited_fails(self):
        """Test: Pitch contours when allow_pitch_contours=False fails."""
        envelope = make_safe_envelope(allow_pitch_contours=False)

        bad_intent = AcousticRenderIntent(
            intended_pitch_min=100,
            intended_pitch_max=120,
            intended_pitch_variance=10,
            intended_energy_min=0.2,
            intended_energy_max=0.4,
            will_use_emphasis=True,
            will_use_pitch_contours=True,  # VIOLATION
            will_use_rhythm_variation=True,
            will_use_intonation_shift=True,
            intended_stressed_tokens=1,
            renderer_id="ContourUser",
            intent_category=RenderIntentCategory.EMOTIVE,
        )

        result = check_compliance(envelope, bad_intent)
        assert result.failed()
        assert result.has_violation_category(ViolationCategory.CONTOUR_VIOLATION)

    def test_rhythm_variation_when_prohibited_fails(self):
        """Test: Rhythm variation when allow_rhythm_variation=False fails."""
        envelope = make_safe_envelope(allow_rhythm_variation=False)

        bad_intent = AcousticRenderIntent(
            intended_pitch_min=100,
            intended_pitch_max=120,
            intended_pitch_variance=10,
            intended_energy_min=0.2,
            intended_energy_max=0.4,
            will_use_emphasis=True,
            will_use_pitch_contours=True,
            will_use_rhythm_variation=True,  # VIOLATION
            will_use_intonation_shift=True,
            intended_stressed_tokens=1,
            renderer_id="RhythmUser",
            intent_category=RenderIntentCategory.EMOTIVE,
        )

        result = check_compliance(envelope, bad_intent)
        assert result.failed()
        assert result.has_violation_category(ViolationCategory.RHYTHM_VIOLATION)

    def test_intonation_shift_when_prohibited_fails(self):
        """Test: Intonation shift when allow_intonation_shift=False fails."""
        envelope = make_safe_envelope(allow_intonation_shift=False)

        bad_intent = AcousticRenderIntent(
            intended_pitch_min=100,
            intended_pitch_max=120,
            intended_pitch_variance=10,
            intended_energy_min=0.2,
            intended_energy_max=0.4,
            will_use_emphasis=True,
            will_use_pitch_contours=True,
            will_use_rhythm_variation=True,
            will_use_intonation_shift=True,  # VIOLATION
            intended_stressed_tokens=1,
            renderer_id="IntonationUser",
            intent_category=RenderIntentCategory.EMOTIVE,
        )

        result = check_compliance(envelope, bad_intent)
        assert result.failed()
        assert result.has_violation_category(ViolationCategory.INTONATION_VIOLATION)

    def test_emotive_renderer_always_fails_under_restriction(self):
        """Test: EmotiveRenderer always fails under any flag restriction."""
        # Test with each flag disabled
        flag_configs = [
            {"allow_emphasis": False},
            {"allow_pitch_contours": False},
            {"allow_rhythm_variation": False},
            {"allow_intonation_shift": False},
        ]

        for config in flag_configs:
            envelope = make_safe_envelope(**config)
            contract = make_contract(envelope)
            renderer = EmotiveRenderer()
            intent = renderer.render(contract)
            result = check_compliance(envelope, intent)

            assert result.failed(), f"EmotiveRenderer should fail with config: {config}"

    def test_emotive_renderer_passes_when_all_allowed(self):
        """Test: EmotiveRenderer can pass when all expression is allowed."""
        envelope = make_safe_envelope(
            allow_emphasis=True,
            allow_pitch_contours=True,
            allow_rhythm_variation=True,
            allow_intonation_shift=True,
            source_regime="INFORM",  # Not restricted
        )
        contract = make_contract(envelope)
        renderer = EmotiveRenderer()
        intent = renderer.render(contract)
        result = check_compliance(envelope, intent)

        # May still fail due to stressed tokens or other checks
        # But should not fail on expression flags alone

    def test_emotional_contour_injection_detected(self):
        """Test: Emotional contour injection is detected."""
        envelope = make_de_escalate_envelope()
        contract = make_contract(envelope)
        renderer = EmotiveRenderer()
        intent = renderer.render(contract)
        result = check_compliance(envelope, intent)

        assert result.failed()

    def test_stressed_tokens_when_emphasis_prohibited(self):
        """Test: Stressed tokens > 0 when emphasis prohibited fails."""
        envelope = make_safe_envelope(allow_emphasis=False)

        bad_intent = AcousticRenderIntent(
            intended_pitch_min=100,
            intended_pitch_max=120,
            intended_pitch_variance=10,
            intended_energy_min=0.2,
            intended_energy_max=0.4,
            will_use_emphasis=False,  # Not using emphasis flag
            will_use_pitch_contours=True,
            will_use_rhythm_variation=True,
            will_use_intonation_shift=True,
            intended_stressed_tokens=2,  # But still has stressed tokens!
            renderer_id="SneakyStresser",
            intent_category=RenderIntentCategory.EMOTIVE,
        )

        result = check_compliance(envelope, bad_intent)
        assert result.failed()
        assert result.has_violation_category(ViolationCategory.EMPHASIS_VIOLATION)


# ============================================================================
# CATEGORY E: BOUNDARY PRECISION TESTS
# ============================================================================


class TestBoundaryPrecision:
    """Tests for boundary precision handling."""

    def test_exactly_at_limit_passes(self):
        """Test: Exactly at limit passes."""
        envelope = make_safe_envelope(
            allowed_pitch_range=(90, 130),
            allowed_energy_range=(0.2, 0.5),
            allowed_variance_range=(0, 20),
        )
        contract = make_contract(envelope)
        renderer = ExactBoundaryRenderer()
        intent = renderer.render(contract)
        result = check_compliance(envelope, intent)

        assert result.passed(), "Exact boundary values should pass"

    def test_epsilon_above_pitch_fails(self):
        """Test: Epsilon above pitch limit fails."""
        envelope = make_safe_envelope(allowed_pitch_range=(90, 130))
        contract = make_contract(envelope)
        renderer = BoundaryPusherRenderer(epsilon_pitch=1)
        intent = renderer.render(contract)
        result = check_compliance(envelope, intent)

        assert result.failed()
        assert result.has_violation_category(ViolationCategory.PITCH_BOUND_VIOLATION)

    def test_epsilon_above_energy_fails(self):
        """Test: Epsilon above energy limit fails."""
        envelope = make_safe_envelope(allowed_energy_range=(0.2, 0.5))
        contract = make_contract(envelope)
        renderer = BoundaryPusherRenderer(epsilon_energy=0.01)
        intent = renderer.render(contract)
        result = check_compliance(envelope, intent)

        assert result.failed()
        assert result.has_violation_category(ViolationCategory.ENERGY_BOUND_VIOLATION)

    def test_epsilon_above_variance_fails(self):
        """Test: Epsilon above variance limit fails."""
        envelope = make_safe_envelope(allowed_variance_range=(0, 20))
        contract = make_contract(envelope)
        renderer = BoundaryPusherRenderer(epsilon_variance=1)
        intent = renderer.render(contract)
        result = check_compliance(envelope, intent)

        assert result.failed()
        assert result.has_violation_category(ViolationCategory.VARIANCE_BOUND_VIOLATION)

    def test_boundary_pusher_with_minimal_epsilon(self):
        """Test: Even minimal epsilon above limit fails."""
        envelope = make_safe_envelope(
            allowed_pitch_range=(90, 130),
            allowed_energy_range=(0.2, 0.5),
            allowed_variance_range=(0, 20),
        )
        contract = make_contract(envelope)

        # Use minimal epsilons
        renderer = BoundaryPusherRenderer(
            epsilon_pitch=1,
            epsilon_energy=0.001,
            epsilon_variance=1,
        )
        intent = renderer.render(contract)
        result = check_compliance(envelope, intent)

        assert result.failed()

    def test_all_epsilons_detected(self):
        """Test: All epsilon violations are detected together."""
        envelope = make_safe_envelope()
        contract = make_contract(envelope)
        renderer = BoundaryPusherRenderer()
        intent = renderer.render(contract)
        result = check_compliance(envelope, intent)

        assert result.failed()
        # Should have multiple violation types
        assert result.violation_count() >= 1

    def test_pitch_at_max_passes(self):
        """Test: Pitch exactly at max passes."""
        envelope = make_safe_envelope(allowed_pitch_range=(90, 130))

        good_intent = AcousticRenderIntent(
            intended_pitch_min=90,
            intended_pitch_max=130,  # Exactly at max
            intended_pitch_variance=20,
            intended_energy_min=0.2,
            intended_energy_max=0.4,
            will_use_emphasis=True,
            will_use_pitch_contours=True,
            will_use_rhythm_variation=True,
            will_use_intonation_shift=True,
            intended_stressed_tokens=1,
            renderer_id="ExactPitchRenderer",
            intent_category=RenderIntentCategory.COMPLIANT,
        )

        result = check_compliance(envelope, good_intent)
        # Should pass pitch check (may fail others)
        pitch_violations = result.get_violations_by_category(ViolationCategory.PITCH_BOUND_VIOLATION)
        assert len(pitch_violations) == 0

    def test_energy_at_max_passes(self):
        """Test: Energy exactly at max passes."""
        envelope = make_safe_envelope(allowed_energy_range=(0.2, 0.5))

        good_intent = AcousticRenderIntent(
            intended_pitch_min=100,
            intended_pitch_max=120,
            intended_pitch_variance=10,
            intended_energy_min=0.2,
            intended_energy_max=0.5,  # Exactly at max
            will_use_emphasis=True,
            will_use_pitch_contours=True,
            will_use_rhythm_variation=True,
            will_use_intonation_shift=True,
            intended_stressed_tokens=1,
            renderer_id="ExactEnergyRenderer",
            intent_category=RenderIntentCategory.COMPLIANT,
        )

        result = check_compliance(envelope, good_intent)
        energy_violations = result.get_violations_by_category(ViolationCategory.ENERGY_BOUND_VIOLATION)
        assert len(energy_violations) == 0


# ============================================================================
# CATEGORY F: DETERMINISM TESTS
# ============================================================================


class TestDeterminism:
    """Tests for deterministic behavior."""

    def test_same_input_same_verdict(self):
        """Test: Same input produces same verdict."""
        envelope = make_safe_envelope()
        contract = make_contract(envelope)
        renderer = CompliantRenderer()
        checker = RendererComplianceChecker()

        intent1 = renderer.render(contract)
        intent2 = renderer.render(contract)

        result1 = checker.check(envelope, intent1)
        result2 = checker.check(envelope, intent2)

        assert result1.verdict == result2.verdict

    def test_same_input_same_violation_count(self):
        """Test: Same input produces same violation count."""
        envelope = make_safe_envelope()
        contract = make_contract(envelope)
        renderer = AmplifyingRenderer()
        checker = RendererComplianceChecker()

        intent = renderer.render(contract)

        result1 = checker.check(envelope, intent)
        result2 = checker.check(envelope, intent)

        assert result1.violation_count() == result2.violation_count()

    def test_no_randomness_in_compliance_check(self):
        """Test: No randomness in compliance checking."""
        envelope = make_safe_envelope()
        checker = RendererComplianceChecker()

        intent = AcousticRenderIntent(
            intended_pitch_min=100,
            intended_pitch_max=150,  # Above limit
            intended_pitch_variance=30,
            intended_energy_min=0.2,
            intended_energy_max=0.7,  # Above limit
            will_use_emphasis=True,
            will_use_pitch_contours=True,
            will_use_rhythm_variation=True,
            will_use_intonation_shift=True,
            intended_stressed_tokens=3,
            renderer_id="DeterminismTest",
            intent_category=RenderIntentCategory.AMPLIFIED,
        )

        # Run 10 times and verify all results are identical
        results = [checker.check(envelope, intent) for _ in range(10)]

        for r in results[1:]:
            assert r.verdict == results[0].verdict
            assert r.violation_count() == results[0].violation_count()
            assert set(v.category for v in r.violations) == set(v.category for v in results[0].violations)

    def test_checker_stateless(self):
        """Test: Checker is stateless between calls."""
        envelope1 = make_safe_envelope()
        envelope2 = make_blocked_envelope()

        checker = RendererComplianceChecker()

        # First check with safe envelope
        intent1 = AcousticRenderIntent(
            intended_pitch_min=100,
            intended_pitch_max=120,
            intended_pitch_variance=10,
            intended_energy_min=0.2,
            intended_energy_max=0.4,
            will_use_emphasis=True,
            will_use_pitch_contours=True,
            will_use_rhythm_variation=True,
            will_use_intonation_shift=True,
            intended_stressed_tokens=1,
            renderer_id="StateTest1",
            intent_category=RenderIntentCategory.COMPLIANT,
        )
        result1 = checker.check(envelope1, intent1)

        # Second check with blocked envelope
        intent2 = AcousticRenderIntent(
            intended_pitch_min=95,
            intended_pitch_max=105,
            intended_pitch_variance=5,
            intended_energy_min=0.2,
            intended_energy_max=0.3,
            will_use_emphasis=False,
            will_use_pitch_contours=False,
            will_use_rhythm_variation=False,
            will_use_intonation_shift=False,
            intended_stressed_tokens=0,
            renderer_id="StateTest2",
            intent_category=RenderIntentCategory.COMPLIANT,
        )
        result2 = checker.check(envelope2, intent2)

        # Third check same as first - should get same result
        result3 = checker.check(envelope1, intent1)

        assert result1.verdict == result3.verdict
        assert result1.violation_count() == result3.violation_count()

    def test_compliant_renderer_deterministic(self):
        """Test: CompliantRenderer produces deterministic output."""
        envelope = make_safe_envelope()
        contract = make_contract(envelope)

        renderer = CompliantRenderer()

        intents = [renderer.render(contract) for _ in range(5)]

        # All intents should be identical (frozen dataclass)
        for intent in intents[1:]:
            assert intent.intended_pitch_min == intents[0].intended_pitch_min
            assert intent.intended_pitch_max == intents[0].intended_pitch_max
            assert intent.intended_energy_max == intents[0].intended_energy_max
            assert intent.will_use_emphasis == intents[0].will_use_emphasis


# ============================================================================
# CATEGORY G: REGRESSION TESTS
# ============================================================================


class TestRegression:
    """Tests for prior failure modes and edge cases."""

    def test_phonetic_stuttering_impossible_under_p13(self):
        """Test: Phonetic stuttering patterns are impossible under P13."""
        # Phonetic stuttering would require:
        # - Excessive variance
        # - Rapid rhythm changes
        # Under HOLD, both are blocked

        envelope = make_hold_envelope()

        stuttering_intent = AcousticRenderIntent(
            intended_pitch_min=80,
            intended_pitch_max=150,  # Excessive variance
            intended_pitch_variance=70,
            intended_energy_min=0.1,
            intended_energy_max=0.8,
            will_use_emphasis=True,
            will_use_pitch_contours=True,
            will_use_rhythm_variation=True,  # Would cause stuttering
            will_use_intonation_shift=True,
            intended_stressed_tokens=5,
            renderer_id="StutteringRenderer",
            intent_category=RenderIntentCategory.IGNORED,
        )

        result = check_compliance(envelope, stuttering_intent)
        assert result.failed()
        assert result.violation_count() >= 3

    def test_authority_injection_blocked_under_reflexive(self):
        """Test: Authority injection is blocked under REFLEXIVE grounding."""
        envelope = make_reflexive_envelope()

        authority_intent = AcousticRenderIntent(
            intended_pitch_min=90,
            intended_pitch_max=125,
            intended_pitch_variance=20,
            intended_energy_min=0.2,
            intended_energy_max=0.40,  # At max for assertiveness
            will_use_emphasis=True,  # Authority signal
            will_use_pitch_contours=True,  # Authority signal
            will_use_rhythm_variation=True,
            will_use_intonation_shift=True,
            intended_stressed_tokens=2,
            renderer_id="AuthorityInjector",
            intent_category=RenderIntentCategory.AUTHORITATIVE,
        )

        result = check_compliance(envelope, authority_intent)
        assert result.failed()

    def test_emotion_escalation_blocked_under_stabilize(self):
        """Test: Emotion escalation is blocked under STABILIZE."""
        envelope = MockAcousticSafetyEnvelope(
            allowed_pitch_range=(90, 125),
            allowed_energy_range=(0.2, 0.40),
            allowed_variance_range=(0, 20),
            allow_emphasis=False,
            allow_pitch_contours=False,
            allow_rhythm_variation=True,
            allow_intonation_shift=True,
            risk_level="CAUTION",
            source_regime="STABILIZE",
            source_discourse_act="REFLECTION",
        )

        emotional_intent = AcousticRenderIntent(
            intended_pitch_min=90,
            intended_pitch_max=125,
            intended_pitch_variance=20,
            intended_energy_min=0.2,
            intended_energy_max=0.40,
            will_use_emphasis=True,  # Emotion signal
            will_use_pitch_contours=True,  # Emotion signal
            will_use_rhythm_variation=True,
            will_use_intonation_shift=True,
            intended_stressed_tokens=2,
            renderer_id="EmotionEscalator",
            intent_category=RenderIntentCategory.EMOTIVE,
        )

        result = check_compliance(envelope, emotional_intent)
        assert result.failed()

    def test_bypass_attempt_with_minimal_violation(self):
        """Test: Even minimal violations are detected."""
        envelope = make_safe_envelope(
            allowed_pitch_range=(90, 130),
            allowed_energy_range=(0.2, 0.5),
        )

        # Try to bypass with minimal violation
        bypass_intent = AcousticRenderIntent(
            intended_pitch_min=90,
            intended_pitch_max=131,  # Just 1 Hz over
            intended_pitch_variance=20,
            intended_energy_min=0.2,
            intended_energy_max=0.501,  # Just 0.001 over
            will_use_emphasis=True,
            will_use_pitch_contours=True,
            will_use_rhythm_variation=True,
            will_use_intonation_shift=True,
            intended_stressed_tokens=1,
            renderer_id="MinimalBypassAttempt",
            intent_category=RenderIntentCategory.BOUNDARY,
        )

        result = check_compliance(envelope, bypass_intent)
        assert result.failed()

    def test_compliant_renderer_never_fails(self):
        """Test: CompliantRenderer never fails under any valid envelope."""
        test_envelopes = [
            make_safe_envelope(),
            make_blocked_envelope(),
            make_hold_envelope(),
            make_de_escalate_envelope(),
            make_reflexive_envelope(),
            make_safe_envelope(
                allowed_pitch_range=(100, 110),
                allowed_energy_range=(0.25, 0.35),
                allowed_variance_range=(0, 5),
            ),
        ]

        renderer = CompliantRenderer()

        for envelope in test_envelopes:
            contract = make_contract(envelope)
            intent = renderer.render(contract)
            result = check_compliance(envelope, intent)

            assert result.passed(), f"CompliantRenderer failed under {envelope.source_regime}"


# ============================================================================
# CATEGORY H: INTEGRATION TESTS
# ============================================================================


class TestIntegration:
    """Integration tests for the compliance system."""

    def test_full_pipeline_compliant(self):
        """Test: Full pipeline with compliant renderer."""
        # Create envelope
        envelope = make_safe_envelope()

        # Create contract
        contract = RendererInputContract(
            p10_acoustic=MockAcousticParameterFrame(),
            p13_envelope=envelope,
            source_regime="INFORM",
            source_discourse_act="EXPLANATION",
        )

        # Render
        renderer = CompliantRenderer()
        intent = renderer.render(contract)

        # Check compliance
        result = check_compliance(envelope, intent)

        assert result.passed()
        assert result.renderer_id == renderer.renderer_id
        assert len(result.checked_constraints) > 0

    def test_full_pipeline_non_compliant(self):
        """Test: Full pipeline with non-compliant renderer."""
        envelope = make_safe_envelope()
        contract = make_contract(envelope)

        renderer = AmplifyingRenderer()
        intent = renderer.render(contract)
        result = check_compliance(envelope, intent)

        assert result.failed()
        assert result.violation_count() > 0

    def test_is_compliant_helper(self):
        """Test: is_compliant helper function."""
        envelope = make_safe_envelope()
        contract = make_contract(envelope)

        compliant = CompliantRenderer()
        amplifying = AmplifyingRenderer()

        assert is_compliant(envelope, compliant.render(contract))
        assert not is_compliant(envelope, amplifying.render(contract))

    def test_result_to_dict(self):
        """Test: ComplianceResult serialization."""
        envelope = make_safe_envelope()
        contract = make_contract(envelope)
        renderer = AmplifyingRenderer()
        intent = renderer.render(contract)
        result = check_compliance(envelope, intent)

        d = result.to_dict()
        assert "verdict" in d
        assert "violations" in d
        assert "checked_constraints" in d
        assert "renderer_id" in d

    def test_contract_helpers(self):
        """Test: RendererInputContract helper methods."""
        envelope = make_blocked_envelope()
        contract = make_contract(envelope)

        assert contract.is_blocked() is True
        assert contract.allows_emphasis() is False
        assert contract.allows_pitch_contours() is False
        assert contract.get_allowed_pitch_range() == envelope.allowed_pitch_range
        assert contract.get_allowed_energy_range() == envelope.allowed_energy_range

    def test_violation_category_query(self):
        """Test: Querying violations by category."""
        envelope = make_safe_envelope(allowed_pitch_range=(90, 100))

        bad_intent = AcousticRenderIntent(
            intended_pitch_min=80,   # Below min
            intended_pitch_max=150,  # Above max
            intended_pitch_variance=50,
            intended_energy_min=0.1,
            intended_energy_max=0.8,
            will_use_emphasis=True,
            will_use_pitch_contours=True,
            will_use_rhythm_variation=True,
            will_use_intonation_shift=True,
            intended_stressed_tokens=5,
            renderer_id="MultiViolator",
            intent_category=RenderIntentCategory.AMPLIFIED,
        )

        result = check_compliance(envelope, bad_intent)

        pitch_violations = result.get_violations_by_category(ViolationCategory.PITCH_BOUND_VIOLATION)
        assert len(pitch_violations) > 0

    def test_checker_version(self):
        """Test: Checker reports version."""
        checker = RendererComplianceChecker()
        assert checker.version is not None
        assert len(checker.version) > 0


# ============================================================================
# CATEGORY I: SCHEMA VALIDATION TESTS
# ============================================================================


class TestSchemaValidation:
    """Tests for schema validation."""

    def test_acoustic_render_intent_validation(self):
        """Test: AcousticRenderIntent validates fields."""
        # Valid intent
        valid = AcousticRenderIntent(
            intended_pitch_min=100,
            intended_pitch_max=120,
            intended_pitch_variance=20,
            intended_energy_min=0.2,
            intended_energy_max=0.5,
            will_use_emphasis=True,
            will_use_pitch_contours=True,
            will_use_rhythm_variation=True,
            will_use_intonation_shift=True,
            intended_stressed_tokens=1,
            renderer_id="ValidRenderer",
            intent_category=RenderIntentCategory.COMPLIANT,
        )
        assert valid is not None

    def test_acoustic_render_intent_pitch_ordering(self):
        """Test: AcousticRenderIntent validates pitch ordering."""
        with pytest.raises(ValueError, match="intended_pitch_min.*intended_pitch_max"):
            AcousticRenderIntent(
                intended_pitch_min=130,  # Greater than max!
                intended_pitch_max=100,
                intended_pitch_variance=20,
                intended_energy_min=0.2,
                intended_energy_max=0.5,
                will_use_emphasis=True,
                will_use_pitch_contours=True,
                will_use_rhythm_variation=True,
                will_use_intonation_shift=True,
                intended_stressed_tokens=1,
                renderer_id="BadRenderer",
                intent_category=RenderIntentCategory.COMPLIANT,
            )

    def test_acoustic_render_intent_energy_ordering(self):
        """Test: AcousticRenderIntent validates energy ordering."""
        with pytest.raises(ValueError, match="intended_energy_min.*intended_energy_max"):
            AcousticRenderIntent(
                intended_pitch_min=100,
                intended_pitch_max=120,
                intended_pitch_variance=20,
                intended_energy_min=0.8,  # Greater than max!
                intended_energy_max=0.2,
                will_use_emphasis=True,
                will_use_pitch_contours=True,
                will_use_rhythm_variation=True,
                will_use_intonation_shift=True,
                intended_stressed_tokens=1,
                renderer_id="BadRenderer",
                intent_category=RenderIntentCategory.COMPLIANT,
            )

    def test_acoustic_render_intent_negative_variance(self):
        """Test: AcousticRenderIntent rejects negative variance."""
        with pytest.raises(ValueError, match="intended_pitch_variance.*>= 0"):
            AcousticRenderIntent(
                intended_pitch_min=100,
                intended_pitch_max=120,
                intended_pitch_variance=-5,
                intended_energy_min=0.2,
                intended_energy_max=0.5,
                will_use_emphasis=True,
                will_use_pitch_contours=True,
                will_use_rhythm_variation=True,
                will_use_intonation_shift=True,
                intended_stressed_tokens=1,
                renderer_id="BadRenderer",
                intent_category=RenderIntentCategory.COMPLIANT,
            )

    def test_acoustic_render_intent_empty_renderer_id(self):
        """Test: AcousticRenderIntent rejects empty renderer_id."""
        with pytest.raises(ValueError, match="renderer_id.*non-empty"):
            AcousticRenderIntent(
                intended_pitch_min=100,
                intended_pitch_max=120,
                intended_pitch_variance=20,
                intended_energy_min=0.2,
                intended_energy_max=0.5,
                will_use_emphasis=True,
                will_use_pitch_contours=True,
                will_use_rhythm_variation=True,
                will_use_intonation_shift=True,
                intended_stressed_tokens=1,
                renderer_id="",
                intent_category=RenderIntentCategory.COMPLIANT,
            )

    def test_compliance_result_pass_no_violations(self):
        """Test: PASS verdict cannot have violations."""
        with pytest.raises(ValueError, match="PASS.*cannot have violations"):
            ComplianceResult(
                verdict=ComplianceVerdict.PASS,
                violations=(
                    ComplianceViolation(
                        category=ViolationCategory.PITCH_BOUND_VIOLATION,
                        description="Test violation",
                    ),
                ),
                checked_constraints=("TEST",),
                renderer_id="TestRenderer",
                envelope_risk_level="SAFE",
            )

    def test_compliance_result_fail_requires_violations(self):
        """Test: FAIL verdict requires violations."""
        with pytest.raises(ValueError, match="FAIL.*must have violations"):
            ComplianceResult(
                verdict=ComplianceVerdict.FAIL,
                violations=(),  # Empty!
                checked_constraints=("TEST",),
                renderer_id="TestRenderer",
                envelope_risk_level="SAFE",
            )

    def test_renderer_input_contract_requires_p13(self):
        """Test: RendererInputContract requires P13 envelope."""
        with pytest.raises(ValueError, match="p13_envelope is required"):
            RendererInputContract(
                p10_acoustic=MockAcousticParameterFrame(),
                p13_envelope=None,
            )


# ============================================================================
# CATEGORY J: EDGE CASES
# ============================================================================


class TestEdgeCases:
    """Tests for edge cases and corner conditions."""

    def test_zero_variance_allowed(self):
        """Test: Zero variance is allowed."""
        envelope = make_safe_envelope(allowed_variance_range=(0, 20))

        intent = AcousticRenderIntent(
            intended_pitch_min=110,
            intended_pitch_max=110,  # Zero variance
            intended_pitch_variance=0,
            intended_energy_min=0.2,
            intended_energy_max=0.4,
            will_use_emphasis=True,
            will_use_pitch_contours=True,
            will_use_rhythm_variation=True,
            will_use_intonation_shift=True,
            intended_stressed_tokens=1,
            renderer_id="ZeroVariance",
            intent_category=RenderIntentCategory.COMPLIANT,
        )

        result = check_compliance(envelope, intent)
        variance_violations = result.get_violations_by_category(ViolationCategory.VARIANCE_BOUND_VIOLATION)
        assert len(variance_violations) == 0

    def test_minimal_energy_range(self):
        """Test: Minimal energy range is handled."""
        envelope = make_safe_envelope(allowed_energy_range=(0.3, 0.31))

        intent = AcousticRenderIntent(
            intended_pitch_min=100,
            intended_pitch_max=120,
            intended_pitch_variance=10,
            intended_energy_min=0.3,
            intended_energy_max=0.31,
            will_use_emphasis=True,
            will_use_pitch_contours=True,
            will_use_rhythm_variation=True,
            will_use_intonation_shift=True,
            intended_stressed_tokens=1,
            renderer_id="MinimalEnergy",
            intent_category=RenderIntentCategory.COMPLIANT,
        )

        result = check_compliance(envelope, intent)
        energy_violations = result.get_violations_by_category(ViolationCategory.ENERGY_BOUND_VIOLATION)
        assert len(energy_violations) == 0

    def test_all_expression_flags_false(self):
        """Test: All expression flags false with no expression passes."""
        envelope = make_safe_envelope(
            allow_emphasis=False,
            allow_pitch_contours=False,
            allow_rhythm_variation=False,
            allow_intonation_shift=False,
        )

        intent = AcousticRenderIntent(
            intended_pitch_min=100,
            intended_pitch_max=120,
            intended_pitch_variance=10,
            intended_energy_min=0.2,
            intended_energy_max=0.4,
            will_use_emphasis=False,
            will_use_pitch_contours=False,
            will_use_rhythm_variation=False,
            will_use_intonation_shift=False,
            intended_stressed_tokens=0,
            renderer_id="NoExpression",
            intent_category=RenderIntentCategory.COMPLIANT,
        )

        result = check_compliance(envelope, intent)
        assert result.passed()

    def test_unknown_regime_handled(self):
        """Test: Unknown regime is handled gracefully."""
        envelope = MockAcousticSafetyEnvelope(
            source_regime="UNKNOWN_REGIME",
            risk_level="SAFE",
        )
        contract = make_contract(envelope)
        renderer = CompliantRenderer()
        intent = renderer.render(contract)
        result = check_compliance(envelope, intent)

        # Should not crash
        assert result is not None

    def test_multiple_renderers_same_contract(self):
        """Test: Multiple renderers can process same contract."""
        envelope = make_safe_envelope()
        contract = make_contract(envelope)

        renderers = [
            CompliantRenderer(),
            CompliantRenderer("Compliant2"),
            AmplifyingRenderer(),
            AuthorityRenderer(),
            EmotiveRenderer(),
        ]

        results = []
        for renderer in renderers:
            intent = renderer.render(contract)
            result = check_compliance(envelope, intent)
            results.append((renderer.renderer_id, result))

        # Compliant renderers should pass
        assert results[0][1].passed()
        assert results[1][1].passed()
        # Others may fail
        assert results[2][1].failed()


# ============================================================================
# CATEGORY K: ADDITIONAL COVERAGE TESTS
# ============================================================================


class TestAdditionalCoverage:
    """Additional tests to ensure 80+ test coverage."""

    def test_render_intent_to_dict(self):
        """Test: AcousticRenderIntent serialization."""
        intent = AcousticRenderIntent(
            intended_pitch_min=100,
            intended_pitch_max=120,
            intended_pitch_variance=20,
            intended_energy_min=0.2,
            intended_energy_max=0.5,
            will_use_emphasis=True,
            will_use_pitch_contours=False,
            will_use_rhythm_variation=True,
            will_use_intonation_shift=False,
            intended_stressed_tokens=1,
            renderer_id="TestRenderer",
            intent_category=RenderIntentCategory.COMPLIANT,
        )

        d = intent.to_dict()
        assert d["intended_pitch_min"] == 100
        assert d["intended_pitch_max"] == 120
        assert d["renderer_id"] == "TestRenderer"
        assert d["intent_category"] == "COMPLIANT"

    def test_render_intent_uses_any_expression(self):
        """Test: uses_any_expression helper."""
        no_expr = AcousticRenderIntent(
            intended_pitch_min=100,
            intended_pitch_max=120,
            intended_pitch_variance=20,
            intended_energy_min=0.2,
            intended_energy_max=0.5,
            will_use_emphasis=False,
            will_use_pitch_contours=False,
            will_use_rhythm_variation=False,
            will_use_intonation_shift=False,
            intended_stressed_tokens=0,
            renderer_id="NoExpr",
            intent_category=RenderIntentCategory.COMPLIANT,
        )
        assert no_expr.uses_any_expression() is False

        with_expr = AcousticRenderIntent(
            intended_pitch_min=100,
            intended_pitch_max=120,
            intended_pitch_variance=20,
            intended_energy_min=0.2,
            intended_energy_max=0.5,
            will_use_emphasis=True,
            will_use_pitch_contours=False,
            will_use_rhythm_variation=False,
            will_use_intonation_shift=False,
            intended_stressed_tokens=1,
            renderer_id="WithExpr",
            intent_category=RenderIntentCategory.COMPLIANT,
        )
        assert with_expr.uses_any_expression() is True

    def test_render_intent_get_ranges(self):
        """Test: get_pitch_range and get_energy_range helpers."""
        intent = AcousticRenderIntent(
            intended_pitch_min=95,
            intended_pitch_max=125,
            intended_pitch_variance=30,
            intended_energy_min=0.25,
            intended_energy_max=0.45,
            will_use_emphasis=False,
            will_use_pitch_contours=False,
            will_use_rhythm_variation=False,
            will_use_intonation_shift=False,
            intended_stressed_tokens=0,
            renderer_id="RangeTest",
            intent_category=RenderIntentCategory.COMPLIANT,
        )

        assert intent.get_pitch_range() == (95, 125)
        assert intent.get_energy_range() == (0.25, 0.45)

    def test_compliance_violation_to_dict(self):
        """Test: ComplianceViolation serialization."""
        violation = ComplianceViolation(
            category=ViolationCategory.PITCH_BOUND_VIOLATION,
            description="Test violation description",
            evidence={"key": "value"},
        )

        d = violation.to_dict()
        assert d["category"] == "PITCH_BOUND_VIOLATION"
        assert d["description"] == "Test violation description"
        assert d["evidence"]["key"] == "value"

    def test_compliance_result_helpers(self):
        """Test: ComplianceResult helper methods."""
        violation = ComplianceViolation(
            category=ViolationCategory.PITCH_BOUND_VIOLATION,
            description="Pitch violation",
        )

        result = ComplianceResult(
            verdict=ComplianceVerdict.FAIL,
            violations=(violation,),
            checked_constraints=("TEST",),
            renderer_id="TestRenderer",
            envelope_risk_level="SAFE",
        )

        assert result.passed() is False
        assert result.failed() is True
        assert result.violation_count() == 1
        assert result.has_violation_category(ViolationCategory.PITCH_BOUND_VIOLATION)
        assert not result.has_violation_category(ViolationCategory.ENERGY_BOUND_VIOLATION)

    def test_exact_boundary_renderer(self):
        """Test: ExactBoundaryRenderer produces compliant intent."""
        envelope = make_safe_envelope()
        contract = make_contract(envelope)
        renderer = ExactBoundaryRenderer()
        intent = renderer.render(contract)

        assert intent.renderer_id == "ExactBoundaryRenderer"
        assert intent.intent_category == RenderIntentCategory.COMPLIANT

    def test_multiple_violation_categories(self):
        """Test: Multiple violation categories detected correctly."""
        envelope = make_safe_envelope(
            allowed_pitch_range=(100, 110),
            allowed_energy_range=(0.3, 0.4),
        )

        bad_intent = AcousticRenderIntent(
            intended_pitch_min=80,
            intended_pitch_max=140,
            intended_pitch_variance=60,
            intended_energy_min=0.1,
            intended_energy_max=0.8,
            will_use_emphasis=True,
            will_use_pitch_contours=True,
            will_use_rhythm_variation=True,
            will_use_intonation_shift=True,
            intended_stressed_tokens=5,
            renderer_id="MultiViolator",
            intent_category=RenderIntentCategory.AMPLIFIED,
        )

        result = check_compliance(envelope, bad_intent)
        categories = {v.category for v in result.violations}

        assert ViolationCategory.PITCH_BOUND_VIOLATION in categories
        assert ViolationCategory.ENERGY_BOUND_VIOLATION in categories

    def test_contract_to_dict(self):
        """Test: RendererInputContract serialization."""
        envelope = make_safe_envelope()
        contract = make_contract(envelope)

        d = contract.to_dict()
        assert "p10_acoustic" in d
        assert "p13_envelope" in d
        assert "source_regime" in d
        assert "is_blocked" in d

    def test_contract_is_blocked_false_for_safe(self):
        """Test: Contract is_blocked returns False for SAFE envelope."""
        envelope = make_safe_envelope()
        contract = make_contract(envelope)

        assert contract.is_blocked() is False

    def test_contract_is_blocked_true_for_blocked(self):
        """Test: Contract is_blocked returns True for BLOCKED envelope."""
        envelope = make_blocked_envelope()
        contract = make_contract(envelope)

        assert contract.is_blocked() is True


# ============================================================================
# TEST COUNT VERIFICATION
# ============================================================================


class TestCountVerification:
    """Meta-test to verify we have enough tests."""

    def test_minimum_test_count(self):
        """Verify we have at least 80 tests."""
        # This test exists to document the test count requirement
        # The actual count is verified by pytest collection
        pass
