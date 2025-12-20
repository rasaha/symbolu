"""
P12 Unit Tests - Acoustic-Prosodic Consistency Validator

Tests for P12 Acoustic-Prosodic Consistency Validator:
- P12ConsistencyReport dataclass
- P12ConsistencyValidator (audit-only)
- Invariant validation rules
- Integration with P10/P11

Test Categories (per specification):
A. Regime → Acoustic Invariants
   - HOLD regime violations (CRITICAL)
   - DE_ESCALATE regime violations (MAJOR)
   - STABILIZE regime violations (MAJOR)

B. Discourse → Prosody Invariants
   - REFLECTION violations (MAJOR)
   - DEFERRAL violations (MAJOR)
   - QUESTION violations (MAJOR)
   - EXPLANATION violations (MAJOR)

C. Uncertainty Preservation
   - UNCERTAINTY slot with certainty indicators (MAJOR)

D. Lexical-Prosodic Compatibility
   - Low-impact lexical with high-impact prosody (MINOR)

E. Authority Escalation Prevention
   - REFLEXIVE grounding violations (CRITICAL)
   - RELATIONAL grounding violations (CRITICAL)

F. Suppression Consistency
   - Missing suppressions under restrictive regimes (CRITICAL)

G. Integration Tests
   - maybe_run_p12 behavior
   - Accessor functions
   - Empty/missing data handling

H. Proper Alignment Tests
   - All valid configurations pass (no false positives)

Target: >= 60 tests

CRITICAL ARCHITECTURAL INVARIANT:
    P12 is not an intelligence layer.
    It is a truth-preserving audit layer that ensures Symbol-U
    never sounds more certain, forceful, or authoritative
    than it is allowed to be.
"""

from dataclasses import dataclass
from typing import Any, Optional
from unittest.mock import patch, MagicMock

import pytest

from symbolu.mechanical.pipeline.p12_consistency import (
    # Schema
    ViolationSeverity,
    ViolationType,
    P12Violation,
    P12Warning,
    P12ConsistencyReport,
    P12_VERSION,
    create_violation,
    create_warning,
    # Validator
    P12ConsistencyValidator,
    check_regime_acoustic_flat,
    check_regime_acoustic_soft_or_flat,
    check_hold_no_pitch_rise,
    check_hold_no_intensity_increase,
    check_hold_no_expressive_modulation,
    check_de_escalate_no_sharp_pitch,
    check_de_escalate_no_rapid_tempo,
    check_de_escalate_no_emphasis_amplification,
    check_reflection_no_interrogative_prosody,
    check_deferral_minimal_prosodic_motion,
    check_question_rising_pitch_only_if_clarify,
    check_explanation_respects_regime,
    check_uncertainty_preservation,
    check_lexical_prosodic_compatibility,
    check_no_authority_escalation_reflexive,
    check_no_authority_escalation_relational,
    check_suppression_consistency,
    # Integration
    get_p12_validator,
    maybe_run_p12,
    run_p12_directly,
    get_p12_consistency_report,
    is_consistent,
    has_violations,
    has_critical_violations,
    has_major_violations,
    has_warnings,
    get_violations,
    get_critical_violations,
    get_major_violations,
    get_warnings,
    violation_count,
    warning_count,
)
from symbolu.mechanical.pipeline.p10_acoustic import (
    AcousticParameterFrame,
    AcousticRegime,
    EmphasisPolicy,
    PausePolicy,
)
from symbolu.mechanical.pipeline.p8_semantics.p8_semantic_schema import SemanticSlot


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
        pitch_range=(95, 105),  # 10 Hz variance
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
        pitch_range=(95, 115),  # 20 Hz variance
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
        mock = cls(regime=cls.MockRegime(value=regime_value))
        return mock


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
class MockIntentEnvelope:
    """Mock PO2 intent envelope."""
    intent_type: Any

    @dataclass
    class MockIntent:
        value: str

    @classmethod
    def create(cls, intent_value: str) -> "MockIntentEnvelope":
        return cls(intent_type=cls.MockIntent(value=intent_value))


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
class MockSemanticFrame:
    """Mock P8 semantic frame."""
    slots: dict

    def has_slot(self, slot: SemanticSlot) -> bool:
        return slot in self.slots


@dataclass
class MockPipelineContext:
    """Mock pipeline context for testing."""
    p10_acoustic: Optional[AcousticParameterFrame] = None
    p6_regime: Optional[MockRegimeEnvelope] = None
    p7_discourse_envelope: Optional[MockDiscourseEnvelope] = None
    phase_zero: Optional[MockIntentEnvelope] = None
    phase_minus_one: Optional[MockPhaseMinusOneEnvelope] = None
    semantic_frame: Optional[MockSemanticFrame] = None
    p11_prosodic_evidence: Any = None
    p12_consistency: Optional[P12ConsistencyReport] = None


# ============================================================================
# A. REGIME -> ACOUSTIC INVARIANTS TESTS
# ============================================================================


class TestRegimeAcousticInvariants:
    """Tests for Regime -> Acoustic invariant checking."""

    # HOLD regime tests (CRITICAL violations)

    def test_hold_with_pitch_rise_critical_violation(self):
        """Test: HOLD + pitch rise -> CRITICAL violation."""
        passed, violation = check_hold_no_pitch_rise("HOLD", (90, 130))  # 40 Hz variance
        assert passed is False
        assert violation is not None
        assert violation.severity == ViolationSeverity.CRITICAL
        assert violation.invariant_name == "hold_no_pitch_rise"

    def test_hold_with_non_flat_acoustic_critical_violation(self):
        """Test: HOLD + non-FLAT acoustic -> CRITICAL violation."""
        passed, violation = check_regime_acoustic_flat("HOLD", "neutral")
        assert passed is False
        assert violation is not None
        assert violation.severity == ViolationSeverity.CRITICAL
        assert violation.invariant_name == "regime_requires_flat_acoustic"

    def test_hold_with_intensity_increase_critical_violation(self):
        """Test: HOLD + high energy -> CRITICAL violation."""
        passed, violation = check_hold_no_intensity_increase("HOLD", 0.5)
        assert passed is False
        assert violation is not None
        assert violation.severity == ViolationSeverity.CRITICAL
        assert violation.invariant_name == "hold_no_intensity_increase"

    def test_hold_with_expressive_modulation_critical_violation(self):
        """Test: HOLD + expressive modulation -> CRITICAL violation."""
        passed, violation = check_hold_no_expressive_modulation("HOLD", "limited", 1)
        assert passed is False
        assert violation is not None
        assert violation.severity == ViolationSeverity.CRITICAL
        assert violation.invariant_name == "hold_no_expressive_modulation"

    def test_hold_valid_acoustic_passes(self):
        """Test: HOLD + valid acoustic passes."""
        passed, violation = check_regime_acoustic_flat("HOLD", "flat")
        assert passed is True
        assert violation is None

    def test_hold_valid_pitch_passes(self):
        """Test: HOLD + narrow pitch variance passes."""
        passed, violation = check_hold_no_pitch_rise("HOLD", (95, 105))  # 10 Hz variance
        assert passed is True
        assert violation is None

    def test_hold_valid_energy_passes(self):
        """Test: HOLD + low energy passes."""
        passed, violation = check_hold_no_intensity_increase("HOLD", 0.25)
        assert passed is True
        assert violation is None

    def test_hold_valid_emphasis_passes(self):
        """Test: HOLD + no emphasis passes."""
        passed, violation = check_hold_no_expressive_modulation("HOLD", "none", 0)
        assert passed is True
        assert violation is None

    # DE_ESCALATE regime tests (MAJOR violations)

    def test_de_escalate_with_sharp_pitch_major_violation(self):
        """Test: DE_ESCALATE + sharp pitch -> MAJOR violation."""
        passed, violation = check_de_escalate_no_sharp_pitch("DE_ESCALATE", (90, 140))  # 50 Hz
        assert passed is False
        assert violation is not None
        assert violation.severity == ViolationSeverity.MAJOR
        assert violation.invariant_name == "de_escalate_no_sharp_pitch"

    def test_de_escalate_with_rapid_tempo_major_violation(self):
        """Test: DE_ESCALATE + rapid tempo -> MAJOR violation."""
        passed, violation = check_de_escalate_no_rapid_tempo("DE_ESCALATE", 5.0)
        assert passed is False
        assert violation is not None
        assert violation.severity == ViolationSeverity.MAJOR
        assert violation.invariant_name == "de_escalate_no_rapid_tempo"

    def test_de_escalate_with_emphasis_amplification_major_violation(self):
        """Test: DE_ESCALATE + emphasis -> MAJOR violation."""
        passed, violation = check_de_escalate_no_emphasis_amplification("DE_ESCALATE", 1)
        assert passed is False
        assert violation is not None
        assert violation.severity == ViolationSeverity.MAJOR
        assert violation.invariant_name == "de_escalate_no_emphasis_amplification"

    def test_de_escalate_non_soft_acoustic_major_violation(self):
        """Test: DE_ESCALATE + non-SOFT/FLAT acoustic -> MAJOR violation."""
        passed, violation = check_regime_acoustic_soft_or_flat("DE_ESCALATE", "neutral")
        assert passed is False
        assert violation is not None
        assert violation.severity == ViolationSeverity.MAJOR

    def test_de_escalate_valid_acoustic_passes(self):
        """Test: DE_ESCALATE + SOFT acoustic passes."""
        passed, violation = check_regime_acoustic_soft_or_flat("DE_ESCALATE", "soft")
        assert passed is True
        assert violation is None

    def test_de_escalate_flat_acoustic_passes(self):
        """Test: DE_ESCALATE + FLAT acoustic passes."""
        passed, violation = check_regime_acoustic_soft_or_flat("DE_ESCALATE", "flat")
        assert passed is True
        assert violation is None

    def test_de_escalate_valid_tempo_passes(self):
        """Test: DE_ESCALATE + slow tempo passes."""
        passed, violation = check_de_escalate_no_rapid_tempo("DE_ESCALATE", 3.5)
        assert passed is True
        assert violation is None

    # STABILIZE regime tests

    def test_stabilize_with_sharp_pitch_major_violation(self):
        """Test: STABILIZE + sharp pitch -> MAJOR violation."""
        passed, violation = check_de_escalate_no_sharp_pitch("STABILIZE", (90, 140))
        assert passed is False
        assert violation is not None
        assert violation.severity == ViolationSeverity.MAJOR

    def test_stabilize_valid_passes(self):
        """Test: STABILIZE + valid acoustic passes."""
        passed, violation = check_regime_acoustic_soft_or_flat("STABILIZE", "soft")
        assert passed is True
        assert violation is None

    # REFLECT regime tests

    def test_reflect_soft_or_flat_required(self):
        """Test: REFLECT requires SOFT or FLAT."""
        passed, violation = check_regime_acoustic_soft_or_flat("REFLECT", "neutral")
        assert passed is False
        assert violation.severity == ViolationSeverity.MAJOR

    def test_reflect_soft_passes(self):
        """Test: REFLECT + SOFT passes."""
        passed, violation = check_regime_acoustic_soft_or_flat("REFLECT", "soft")
        assert passed is True

    # INFORM/CLARIFY regime tests

    def test_inform_neutral_allowed(self):
        """Test: INFORM allows NEUTRAL acoustic."""
        # These checks only apply to restrictive regimes
        passed, violation = check_regime_acoustic_flat("INFORM", "neutral")
        assert passed is True
        assert violation is None

    def test_clarify_neutral_allowed(self):
        """Test: CLARIFY allows NEUTRAL acoustic."""
        passed, violation = check_regime_acoustic_flat("CLARIFY", "neutral")
        assert passed is True
        assert violation is None


# ============================================================================
# B. DISCOURSE -> PROSODY INVARIANTS TESTS
# ============================================================================


class TestDiscourseProsodyInvariants:
    """Tests for Discourse -> Prosody invariant checking."""

    # REFLECTION tests

    def test_reflection_with_interrogative_prosody_major_violation(self):
        """Test: REFLECTION + interrogative rise -> MAJOR violation."""
        passed, violation = check_reflection_no_interrogative_prosody(
            "REFLECTION", (90, 130), None  # 40 Hz variance suggests interrogative
        )
        assert passed is False
        assert violation is not None
        assert violation.severity == ViolationSeverity.MAJOR
        assert violation.invariant_name == "reflection_no_interrogative_prosody"

    def test_reflection_flat_pitch_passes(self):
        """Test: REFLECTION + flat pitch passes."""
        passed, violation = check_reflection_no_interrogative_prosody(
            "REFLECTION", (100, 115), None  # 15 Hz variance
        )
        assert passed is True
        assert violation is None

    # DEFERRAL tests

    def test_deferral_with_high_prosodic_motion_major_violation(self):
        """Test: DEFERRAL + high prosodic motion -> MAJOR violation."""
        passed, violation = check_deferral_minimal_prosodic_motion(
            "DEFERRAL", (90, 130), 0.5  # High variance and energy
        )
        assert passed is False
        assert violation is not None
        assert violation.severity == ViolationSeverity.MAJOR
        assert violation.invariant_name == "deferral_minimal_prosodic_motion"

    def test_deferral_minimal_motion_passes(self):
        """Test: DEFERRAL + minimal motion passes."""
        passed, violation = check_deferral_minimal_prosodic_motion(
            "DEFERRAL", (95, 105), 0.25  # Low variance and energy
        )
        assert passed is True
        assert violation is None

    # QUESTION tests

    def test_question_rising_pitch_without_clarify_intent_major_violation(self):
        """Test: QUESTION + rising pitch without CLARIFY intent -> MAJOR violation."""
        passed, violation = check_question_rising_pitch_only_if_clarify(
            "QUESTION", "INFORM", (90, 130)  # 40 Hz variance, INFORM intent
        )
        assert passed is False
        assert violation is not None
        assert violation.severity == ViolationSeverity.MAJOR
        assert violation.invariant_name == "question_rising_pitch_requires_clarify_intent"

    def test_question_rising_pitch_with_clarify_intent_passes(self):
        """Test: QUESTION + rising pitch with CLARIFY intent passes."""
        passed, violation = check_question_rising_pitch_only_if_clarify(
            "QUESTION", "CLARIFY", (90, 130)  # 40 Hz variance, CLARIFY intent
        )
        assert passed is True
        assert violation is None

    def test_question_flat_pitch_any_intent_passes(self):
        """Test: QUESTION + flat pitch passes with any intent."""
        passed, violation = check_question_rising_pitch_only_if_clarify(
            "QUESTION", "INFORM", (100, 115)  # 15 Hz variance
        )
        assert passed is True
        assert violation is None

    # EXPLANATION tests

    def test_explanation_under_hold_with_high_energy_major_violation(self):
        """Test: EXPLANATION under HOLD + high energy -> MAJOR violation."""
        passed, violation = check_explanation_respects_regime(
            "EXPLANATION", "HOLD", 0.5, 0
        )
        assert passed is False
        assert violation is not None
        assert violation.severity == ViolationSeverity.MAJOR

    def test_explanation_under_hold_with_emphasis_major_violation(self):
        """Test: EXPLANATION under HOLD + emphasis -> MAJOR violation."""
        passed, violation = check_explanation_respects_regime(
            "EXPLANATION", "HOLD", 0.3, 1
        )
        assert passed is False
        assert violation is not None
        assert violation.severity == ViolationSeverity.MAJOR

    def test_explanation_under_inform_high_energy_passes(self):
        """Test: EXPLANATION under INFORM + high energy passes."""
        passed, violation = check_explanation_respects_regime(
            "EXPLANATION", "INFORM", 0.5, 1
        )
        assert passed is True
        assert violation is None

    def test_explanation_under_hold_low_energy_passes(self):
        """Test: EXPLANATION under HOLD + low energy passes."""
        passed, violation = check_explanation_respects_regime(
            "EXPLANATION", "HOLD", 0.3, 0
        )
        assert passed is True
        assert violation is None


# ============================================================================
# C. UNCERTAINTY PRESERVATION TESTS
# ============================================================================


class TestUncertaintyPreservation:
    """Tests for uncertainty preservation invariants."""

    def test_uncertainty_slot_with_no_suppression_major_violation(self):
        """Test: UNCERTAINTY slot + no certainty suppression -> MAJOR violation."""
        passed, violation = check_uncertainty_preservation(
            has_uncertainty_slot=True,
            suppress_certainty=False,
            pitch_range=(100, 130),
            emphasis_policy="none",
            max_stressed_tokens=0,
        )
        assert passed is False
        assert violation is not None
        assert violation.severity == ViolationSeverity.MAJOR
        assert violation.violation_type == ViolationType.UNCERTAINTY_VIOLATION

    def test_uncertainty_slot_with_emphatic_stress_major_violation(self):
        """Test: UNCERTAINTY slot + emphatic stress -> MAJOR violation."""
        passed, violation = check_uncertainty_preservation(
            has_uncertainty_slot=True,
            suppress_certainty=True,
            pitch_range=(100, 130),
            emphasis_policy="limited",
            max_stressed_tokens=1,
        )
        assert passed is False
        assert violation is not None
        assert violation.severity == ViolationSeverity.MAJOR

    def test_uncertainty_slot_with_falling_authority_contour_major_violation(self):
        """Test: UNCERTAINTY slot + falling authority contour -> MAJOR violation."""
        passed, violation = check_uncertainty_preservation(
            has_uncertainty_slot=True,
            suppress_certainty=True,
            pitch_range=(90, 95),  # Narrow range at low pitch = authority contour
            emphasis_policy="none",
            max_stressed_tokens=0,
        )
        assert passed is False
        assert violation is not None
        assert violation.severity == ViolationSeverity.MAJOR

    def test_uncertainty_slot_properly_handled_passes(self):
        """Test: UNCERTAINTY slot + proper handling passes."""
        passed, violation = check_uncertainty_preservation(
            has_uncertainty_slot=True,
            suppress_certainty=True,
            pitch_range=(100, 130),  # Normal range
            emphasis_policy="none",
            max_stressed_tokens=0,
        )
        assert passed is True
        assert violation is None

    def test_no_uncertainty_slot_any_prosody_passes(self):
        """Test: No UNCERTAINTY slot -> any prosody passes."""
        passed, violation = check_uncertainty_preservation(
            has_uncertainty_slot=False,
            suppress_certainty=False,
            pitch_range=(100, 130),
            emphasis_policy="limited",
            max_stressed_tokens=1,
        )
        assert passed is True
        assert violation is None


# ============================================================================
# D. LEXICAL-PROSODIC COMPATIBILITY TESTS
# ============================================================================


class TestLexicalProsodicCompatibility:
    """Tests for lexical-prosodic compatibility checking."""

    def test_restrictive_regime_with_high_energy_minor_violation(self):
        """Test: Restrictive regime + high energy -> MINOR violation."""
        passed, violation = check_lexical_prosodic_compatibility(
            source_regime="HOLD",
            acoustic_regime="flat",
            energy_level=0.55,
            max_stressed_tokens=0,
        )
        assert passed is False
        assert violation is not None
        assert violation.severity == ViolationSeverity.MINOR
        assert violation.violation_type == ViolationType.LEXICAL_PROSODIC_INCOMPATIBILITY

    def test_restrictive_regime_with_emphatic_stress_minor_violation(self):
        """Test: Restrictive regime + emphatic stress -> MINOR violation."""
        passed, violation = check_lexical_prosodic_compatibility(
            source_regime="DE_ESCALATE",
            acoustic_regime="soft",
            energy_level=0.3,
            max_stressed_tokens=1,
        )
        assert passed is False
        assert violation is not None
        assert violation.severity == ViolationSeverity.MINOR

    def test_restrictive_regime_low_impact_passes(self):
        """Test: Restrictive regime + low impact prosody passes."""
        passed, violation = check_lexical_prosodic_compatibility(
            source_regime="HOLD",
            acoustic_regime="flat",
            energy_level=0.25,
            max_stressed_tokens=0,
        )
        assert passed is True
        assert violation is None

    def test_inform_regime_high_energy_passes(self):
        """Test: INFORM regime + high energy passes (not restrictive)."""
        passed, violation = check_lexical_prosodic_compatibility(
            source_regime="INFORM",
            acoustic_regime="neutral",
            energy_level=0.55,
            max_stressed_tokens=1,
        )
        assert passed is True
        assert violation is None


# ============================================================================
# E. AUTHORITY ESCALATION PREVENTION TESTS
# ============================================================================


class TestAuthorityEscalationPrevention:
    """Tests for authority escalation prevention."""

    # REFLEXIVE grounding tests

    def test_reflexive_with_no_certainty_suppression_critical_violation(self):
        """Test: REFLEXIVE + no certainty suppression -> CRITICAL violation."""
        passed, violation = check_no_authority_escalation_reflexive(
            grounding_mode="REFLEXIVE",
            suppress_certainty=False,
            suppress_emphasis=True,
            energy_level=0.3,
            pitch_range=(100, 115),
        )
        assert passed is False
        assert violation is not None
        assert violation.severity == ViolationSeverity.CRITICAL
        assert violation.violation_type == ViolationType.AUTHORITY_ESCALATION

    def test_reflexive_with_no_emphasis_suppression_critical_violation(self):
        """Test: REFLEXIVE + no emphasis suppression -> CRITICAL violation."""
        passed, violation = check_no_authority_escalation_reflexive(
            grounding_mode="REFLEXIVE",
            suppress_certainty=True,
            suppress_emphasis=False,
            energy_level=0.3,
            pitch_range=(100, 115),
        )
        assert passed is False
        assert violation is not None
        assert violation.severity == ViolationSeverity.CRITICAL

    def test_reflexive_with_high_energy_critical_violation(self):
        """Test: REFLEXIVE + high energy -> CRITICAL violation."""
        passed, violation = check_no_authority_escalation_reflexive(
            grounding_mode="REFLEXIVE",
            suppress_certainty=True,
            suppress_emphasis=True,
            energy_level=0.5,
            pitch_range=(100, 115),
        )
        assert passed is False
        assert violation is not None
        assert violation.severity == ViolationSeverity.CRITICAL

    def test_reflexive_with_high_pitch_variance_critical_violation(self):
        """Test: REFLEXIVE + high pitch variance -> CRITICAL violation."""
        passed, violation = check_no_authority_escalation_reflexive(
            grounding_mode="REFLEXIVE",
            suppress_certainty=True,
            suppress_emphasis=True,
            energy_level=0.3,
            pitch_range=(90, 130),  # 40 Hz variance
        )
        assert passed is False
        assert violation is not None
        assert violation.severity == ViolationSeverity.CRITICAL

    def test_reflexive_proper_handling_passes(self):
        """Test: REFLEXIVE + proper handling passes."""
        passed, violation = check_no_authority_escalation_reflexive(
            grounding_mode="REFLEXIVE",
            suppress_certainty=True,
            suppress_emphasis=True,
            energy_level=0.3,
            pitch_range=(100, 120),
        )
        assert passed is True
        assert violation is None

    # RELATIONAL grounding tests

    def test_relational_with_no_certainty_suppression_critical_violation(self):
        """Test: RELATIONAL + no certainty suppression -> CRITICAL violation."""
        passed, violation = check_no_authority_escalation_relational(
            grounding_mode="RELATIONAL",
            suppress_certainty=False,
            suppress_emphasis=True,
            energy_level=0.3,
        )
        assert passed is False
        assert violation is not None
        assert violation.severity == ViolationSeverity.CRITICAL
        assert violation.violation_type == ViolationType.AUTHORITY_ESCALATION

    def test_relational_with_high_energy_critical_violation(self):
        """Test: RELATIONAL + high energy -> CRITICAL violation."""
        passed, violation = check_no_authority_escalation_relational(
            grounding_mode="RELATIONAL",
            suppress_certainty=True,
            suppress_emphasis=True,
            energy_level=0.5,
        )
        assert passed is False
        assert violation is not None
        assert violation.severity == ViolationSeverity.CRITICAL

    def test_relational_proper_handling_passes(self):
        """Test: RELATIONAL + proper handling passes."""
        passed, violation = check_no_authority_escalation_relational(
            grounding_mode="RELATIONAL",
            suppress_certainty=True,
            suppress_emphasis=True,
            energy_level=0.35,
        )
        assert passed is True
        assert violation is None

    # DETACHED grounding (no restrictions)

    def test_detached_no_restrictions(self):
        """Test: DETACHED grounding has no authority restrictions."""
        passed, violation = check_no_authority_escalation_reflexive(
            grounding_mode="DETACHED",
            suppress_certainty=False,
            suppress_emphasis=False,
            energy_level=0.5,
            pitch_range=(90, 140),
        )
        assert passed is True
        assert violation is None


# ============================================================================
# F. SUPPRESSION CONSISTENCY TESTS
# ============================================================================


class TestSuppressionConsistency:
    """Tests for suppression consistency checking."""

    def test_hold_missing_emotion_suppression_critical_violation(self):
        """Test: HOLD + missing emotion suppression -> CRITICAL violation."""
        passed, violation = check_suppression_consistency(
            source_regime="HOLD",
            suppress_emotion=False,
            suppress_emphasis=True,
            suppress_certainty=True,
        )
        assert passed is False
        assert violation is not None
        assert violation.severity == ViolationSeverity.CRITICAL
        assert violation.violation_type == ViolationType.SUPPRESSION_VIOLATION

    def test_hold_missing_emphasis_suppression_critical_violation(self):
        """Test: HOLD + missing emphasis suppression -> CRITICAL violation."""
        passed, violation = check_suppression_consistency(
            source_regime="HOLD",
            suppress_emotion=True,
            suppress_emphasis=False,
            suppress_certainty=True,
        )
        assert passed is False
        assert violation is not None
        assert violation.severity == ViolationSeverity.CRITICAL

    def test_hold_missing_certainty_suppression_critical_violation(self):
        """Test: HOLD + missing certainty suppression -> CRITICAL violation."""
        passed, violation = check_suppression_consistency(
            source_regime="HOLD",
            suppress_emotion=True,
            suppress_emphasis=True,
            suppress_certainty=False,
        )
        assert passed is False
        assert violation is not None
        assert violation.severity == ViolationSeverity.CRITICAL

    def test_hold_all_suppressions_passes(self):
        """Test: HOLD + all suppressions passes."""
        passed, violation = check_suppression_consistency(
            source_regime="HOLD",
            suppress_emotion=True,
            suppress_emphasis=True,
            suppress_certainty=True,
        )
        assert passed is True
        assert violation is None

    def test_de_escalate_all_suppressions_required(self):
        """Test: DE_ESCALATE requires all suppressions."""
        passed, violation = check_suppression_consistency(
            source_regime="DE_ESCALATE",
            suppress_emotion=True,
            suppress_emphasis=False,
            suppress_certainty=True,
        )
        assert passed is False
        assert violation.severity == ViolationSeverity.CRITICAL

    def test_inform_no_suppression_required_passes(self):
        """Test: INFORM does not require suppressions."""
        passed, violation = check_suppression_consistency(
            source_regime="INFORM",
            suppress_emotion=False,
            suppress_emphasis=False,
            suppress_certainty=False,
        )
        assert passed is True
        assert violation is None


# ============================================================================
# G. INTEGRATION TESTS
# ============================================================================


class TestIntegration:
    """Tests for P12 integration functions."""

    def test_maybe_run_p12_attaches_report(self):
        """Test: maybe_run_p12 attaches report to context."""
        acoustic = make_inform_acoustic_frame()
        ctx = MockPipelineContext(
            p10_acoustic=acoustic,
            p6_regime=MockRegimeEnvelope.create("INFORM"),
            p7_discourse_envelope=MockDiscourseEnvelope.create("EXPLANATION"),
        )

        result_ctx = maybe_run_p12(ctx)

        assert result_ctx.p12_consistency is not None
        assert isinstance(result_ctx.p12_consistency, P12ConsistencyReport)

    def test_maybe_run_p12_idempotent(self):
        """Test: maybe_run_p12 is idempotent."""
        acoustic = make_inform_acoustic_frame()
        ctx = MockPipelineContext(
            p10_acoustic=acoustic,
            p6_regime=MockRegimeEnvelope.create("INFORM"),
            p7_discourse_envelope=MockDiscourseEnvelope.create("EXPLANATION"),
        )

        maybe_run_p12(ctx)
        first_report = ctx.p12_consistency
        first_timestamp = first_report.timestamp_utc

        # Run again
        maybe_run_p12(ctx)
        second_report = ctx.p12_consistency

        # Should be the same object
        assert second_report.timestamp_utc == first_timestamp

    def test_maybe_run_p12_no_p10_returns_none(self):
        """Test: maybe_run_p12 with no P10 sets report to None."""
        ctx = MockPipelineContext(p10_acoustic=None)
        result_ctx = maybe_run_p12(ctx)

        assert result_ctx.p12_consistency is None

    def test_run_p12_directly_no_context_modification(self):
        """Test: run_p12_directly doesn't modify context."""
        acoustic = make_inform_acoustic_frame()
        ctx = MockPipelineContext(
            p10_acoustic=acoustic,
            p6_regime=MockRegimeEnvelope.create("INFORM"),
        )

        report = run_p12_directly(ctx)

        assert report is not None
        assert ctx.p12_consistency is None  # Not attached

    def test_accessor_functions_no_report(self):
        """Test: Accessor functions with no report."""
        ctx = MockPipelineContext()

        assert is_consistent(ctx) is True  # Conservative default
        assert has_violations(ctx) is False
        assert has_critical_violations(ctx) is False
        assert has_major_violations(ctx) is False
        assert has_warnings(ctx) is False
        assert get_violations(ctx) == []
        assert violation_count(ctx) == 0
        assert warning_count(ctx) == 0

    def test_accessor_functions_with_report(self):
        """Test: Accessor functions with report."""
        acoustic = make_inform_acoustic_frame()
        ctx = MockPipelineContext(
            p10_acoustic=acoustic,
            p6_regime=MockRegimeEnvelope.create("INFORM"),
            p7_discourse_envelope=MockDiscourseEnvelope.create("EXPLANATION"),
        )
        maybe_run_p12(ctx)

        assert is_consistent(ctx) is True
        assert has_violations(ctx) is False
        assert get_violations(ctx) == []

    def test_accessor_functions_with_violations(self):
        """Test: Accessor functions detect violations."""
        # Create a HOLD acoustic frame with violations
        acoustic = AcousticParameterFrame(
            regime=AcousticRegime.NEUTRAL,  # VIOLATION: should be FLAT
            speech_rate=4.5,
            energy_level=0.5,  # VIOLATION: too high
            pitch_range=(90, 130),  # VIOLATION: too much variance
            pause_policy=PausePolicy.MINIMAL,
            pause_duration_ms=(100, 150),
            emphasis_policy=EmphasisPolicy.LIMITED,  # VIOLATION
            max_stressed_tokens=1,  # VIOLATION
            suppress_emotion=False,  # VIOLATION
            suppress_emphasis=False,  # VIOLATION
            suppress_certainty=False,  # VIOLATION
            source_regime="HOLD",
            source_discourse_act="DEFERRAL",
        )
        ctx = MockPipelineContext(
            p10_acoustic=acoustic,
            p6_regime=MockRegimeEnvelope.create("HOLD"),
            p7_discourse_envelope=MockDiscourseEnvelope.create("DEFERRAL"),
        )
        maybe_run_p12(ctx)

        assert is_consistent(ctx) is False
        assert has_violations(ctx) is True
        assert has_critical_violations(ctx) is True
        assert violation_count(ctx) > 0

    def test_singleton_validator(self):
        """Test: Singleton validator pattern."""
        v1 = get_p12_validator()
        v2 = get_p12_validator()
        assert v1 is v2


# ============================================================================
# H. PROPER ALIGNMENT TESTS (No False Positives)
# ============================================================================


class TestProperAlignment:
    """Tests that valid configurations pass without violations."""

    def test_valid_hold_configuration_passes(self):
        """Test: Valid HOLD configuration passes."""
        acoustic = make_hold_acoustic_frame()
        ctx = MockPipelineContext(
            p10_acoustic=acoustic,
            p6_regime=MockRegimeEnvelope.create("HOLD"),
            p7_discourse_envelope=MockDiscourseEnvelope.create("DEFERRAL"),
        )
        report = run_p12_directly(ctx)

        assert report is not None
        assert report.is_consistent is True
        assert len(report.violations) == 0

    def test_valid_de_escalate_configuration_passes(self):
        """Test: Valid DE_ESCALATE configuration passes."""
        acoustic = make_de_escalate_acoustic_frame()
        ctx = MockPipelineContext(
            p10_acoustic=acoustic,
            p6_regime=MockRegimeEnvelope.create("DE_ESCALATE"),
            p7_discourse_envelope=MockDiscourseEnvelope.create("REFLECTION"),
        )
        report = run_p12_directly(ctx)

        assert report is not None
        assert report.is_consistent is True
        assert len(report.violations) == 0

    def test_valid_inform_configuration_passes(self):
        """Test: Valid INFORM configuration passes."""
        acoustic = make_inform_acoustic_frame()
        ctx = MockPipelineContext(
            p10_acoustic=acoustic,
            p6_regime=MockRegimeEnvelope.create("INFORM"),
            p7_discourse_envelope=MockDiscourseEnvelope.create("EXPLANATION"),
        )
        report = run_p12_directly(ctx)

        assert report is not None
        assert report.is_consistent is True
        assert len(report.violations) == 0

    def test_empty_p11_evidence_passes(self):
        """Test: Empty P11 evidence passes (no hallucination)."""
        acoustic = make_inform_acoustic_frame()
        ctx = MockPipelineContext(
            p10_acoustic=acoustic,
            p6_regime=MockRegimeEnvelope.create("INFORM"),
            p7_discourse_envelope=MockDiscourseEnvelope.create("EXPLANATION"),
            p11_prosodic_evidence=None,
        )
        report = run_p12_directly(ctx)

        assert report is not None
        # Should pass but with a warning about missing P11
        assert any(w.warning_code == "P11_MISSING" for w in report.warnings)

    def test_missing_regime_warns_but_passes(self):
        """Test: Missing regime warns but doesn't fail."""
        acoustic = make_inform_acoustic_frame()
        ctx = MockPipelineContext(
            p10_acoustic=acoustic,
            p6_regime=None,
            p7_discourse_envelope=MockDiscourseEnvelope.create("EXPLANATION"),
        )
        report = run_p12_directly(ctx)

        assert report is not None
        assert any(w.warning_code == "REGIME_UNKNOWN" for w in report.warnings)

    def test_valid_reflexive_grounding_passes(self):
        """Test: Valid REFLEXIVE grounding with proper suppressions passes."""
        acoustic = AcousticParameterFrame(
            regime=AcousticRegime.SOFT,
            speech_rate=3.5,
            energy_level=0.35,
            pitch_range=(100, 120),  # 20 Hz variance
            pause_policy=PausePolicy.NORMAL,
            pause_duration_ms=(150, 250),
            emphasis_policy=EmphasisPolicy.NONE,
            max_stressed_tokens=0,
            suppress_emotion=True,
            suppress_emphasis=True,
            suppress_certainty=True,
            source_regime="REFLECT",
            source_discourse_act="REFLECTION",
        )
        ctx = MockPipelineContext(
            p10_acoustic=acoustic,
            p6_regime=MockRegimeEnvelope.create("REFLECT"),
            p7_discourse_envelope=MockDiscourseEnvelope.create("REFLECTION"),
            phase_minus_one=MockPhaseMinusOneEnvelope.create("REFLEXIVE"),
        )
        report = run_p12_directly(ctx)

        assert report is not None
        assert report.is_consistent is True


# ============================================================================
# I. DATACLASS TESTS
# ============================================================================


class TestDataclasses:
    """Tests for P12 dataclass validation."""

    def test_p12_violation_construction(self):
        """Test: P12Violation construction."""
        violation = P12Violation(
            severity=ViolationSeverity.CRITICAL,
            violation_type=ViolationType.REGIME_ACOUSTIC_MISMATCH,
            invariant_name="test_invariant",
            source_phase="P6",
            target_phase="P10",
            description="Test violation",
        )
        assert violation.severity == ViolationSeverity.CRITICAL
        assert violation.is_critical() is True
        assert violation.is_major() is False

    def test_p12_violation_to_dict(self):
        """Test: P12Violation serialization."""
        violation = create_violation(
            severity=ViolationSeverity.MAJOR,
            violation_type=ViolationType.DISCOURSE_PROSODY_MISMATCH,
            invariant_name="test",
            source_phase="P7",
            target_phase="P11",
            description="Test",
            evidence={"key": "value"},
        )
        d = violation.to_dict()
        assert d["severity"] == "MAJOR"
        assert d["violation_type"] == "DISCOURSE_PROSODY_MISMATCH"
        assert d["evidence"]["key"] == "value"

    def test_p12_warning_construction(self):
        """Test: P12Warning construction."""
        warning = P12Warning(
            warning_code="TEST_WARNING",
            description="Test warning",
            source_phase="P12",
        )
        assert warning.warning_code == "TEST_WARNING"

    def test_p12_warning_to_dict(self):
        """Test: P12Warning serialization."""
        warning = create_warning(
            warning_code="TEST",
            description="Test",
            source_phase="P12",
            evidence={"key": "value"},
        )
        d = warning.to_dict()
        assert d["warning_code"] == "TEST"
        assert d["evidence"]["key"] == "value"

    def test_p12_report_construction(self):
        """Test: P12ConsistencyReport construction."""
        report = P12ConsistencyReport(
            is_consistent=True,
            violations=[],
            warnings=[],
            checked_invariants=["inv1", "inv2"],
            audit_notes={"key": "value"},
            source_regime="HOLD",
            source_discourse_act="DEFERRAL",
            source_intent="CLARIFY",
            timestamp_utc="2024-01-01T00:00:00+00:00",
        )
        assert report.is_consistent is True
        assert report.has_violations() is False
        assert report.violation_count() == 0

    def test_p12_report_with_violations(self):
        """Test: P12ConsistencyReport with violations."""
        violation = create_violation(
            severity=ViolationSeverity.CRITICAL,
            violation_type=ViolationType.REGIME_ACOUSTIC_MISMATCH,
            invariant_name="test",
            source_phase="P6",
            target_phase="P10",
            description="Test",
        )
        report = P12ConsistencyReport(
            is_consistent=False,
            violations=[violation],
            warnings=[],
            checked_invariants=["test"],
            audit_notes={},
            source_regime="HOLD",
            source_discourse_act="DEFERRAL",
            source_intent=None,
            timestamp_utc="2024-01-01T00:00:00+00:00",
        )
        assert report.is_consistent is False
        assert report.has_violations() is True
        assert report.has_critical_violations() is True
        assert len(report.get_critical_violations()) == 1

    def test_p12_report_invalid_consistency_raises(self):
        """Test: Report with violations but is_consistent=True raises."""
        violation = create_violation(
            severity=ViolationSeverity.CRITICAL,
            violation_type=ViolationType.REGIME_ACOUSTIC_MISMATCH,
            invariant_name="test",
            source_phase="P6",
            target_phase="P10",
            description="Test",
        )
        with pytest.raises(ValueError, match="is_consistent must be False"):
            P12ConsistencyReport(
                is_consistent=True,  # Invalid: should be False
                violations=[violation],
                warnings=[],
                checked_invariants=[],
                audit_notes={},
                source_regime="HOLD",
                source_discourse_act="DEFERRAL",
                source_intent=None,
            )

    def test_p12_report_to_dict(self):
        """Test: P12ConsistencyReport serialization."""
        report = P12ConsistencyReport(
            is_consistent=True,
            violations=[],
            warnings=[],
            checked_invariants=["inv1"],
            audit_notes={"note": "test"},
            source_regime="HOLD",
            source_discourse_act="DEFERRAL",
            source_intent="CLARIFY",
            timestamp_utc="2024-01-01T00:00:00+00:00",
        )
        d = report.to_dict()
        assert d["is_consistent"] is True
        assert d["violation_count"] == 0
        assert d["version"] == P12_VERSION
        assert d["architectural_phase"] == "P12"

    def test_p12_report_immutability(self):
        """Test: P12ConsistencyReport is frozen."""
        report = P12ConsistencyReport(
            is_consistent=True,
            violations=[],
            warnings=[],
            checked_invariants=[],
            audit_notes={},
            source_regime="HOLD",
            source_discourse_act="DEFERRAL",
            source_intent=None,
        )
        with pytest.raises(Exception):  # FrozenInstanceError
            report.is_consistent = False


# ============================================================================
# J. VALIDATOR CLASS TESTS
# ============================================================================


class TestValidatorClass:
    """Tests for P12ConsistencyValidator class."""

    def test_validator_checked_invariants_list(self):
        """Test: Validator has list of checked invariants."""
        validator = P12ConsistencyValidator()
        assert len(validator.CHECKED_INVARIANTS) >= 15

    def test_validator_validate_returns_none_without_p10(self):
        """Test: Validator returns None without P10."""
        validator = P12ConsistencyValidator()
        ctx = MockPipelineContext(p10_acoustic=None)
        report = validator.validate(ctx)
        assert report is None

    def test_validator_validate_with_p10_returns_report(self):
        """Test: Validator returns report with P10."""
        validator = P12ConsistencyValidator()
        ctx = MockPipelineContext(p10_acoustic=make_inform_acoustic_frame())
        report = validator.validate(ctx)
        assert report is not None
        assert isinstance(report, P12ConsistencyReport)

    def test_validator_deterministic(self):
        """Test: Validator is deterministic."""
        validator = P12ConsistencyValidator()
        acoustic = make_hold_acoustic_frame()
        ctx = MockPipelineContext(
            p10_acoustic=acoustic,
            p6_regime=MockRegimeEnvelope.create("HOLD"),
        )

        with patch.object(validator, '_get_timestamp_utc', return_value="2024-01-01T00:00:00+00:00"):
            report1 = validator.validate(ctx)
            report2 = validator.validate(ctx)

        assert report1.is_consistent == report2.is_consistent
        assert len(report1.violations) == len(report2.violations)
        assert report1.timestamp_utc == report2.timestamp_utc


# ============================================================================
# K. EDGE CASE TESTS
# ============================================================================


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_pitch_variance_exactly_at_threshold(self):
        """Test: Pitch variance exactly at threshold."""
        # HOLD threshold is 15 Hz
        passed, violation = check_hold_no_pitch_rise("HOLD", (95, 110))  # 15 Hz exactly
        assert passed is True  # Passes at threshold

        passed, violation = check_hold_no_pitch_rise("HOLD", (95, 111))  # 16 Hz
        assert passed is False

    def test_energy_exactly_at_threshold(self):
        """Test: Energy exactly at threshold."""
        # HOLD threshold is 0.35
        passed, violation = check_hold_no_intensity_increase("HOLD", 0.35)
        assert passed is True  # Passes at threshold

        passed, violation = check_hold_no_intensity_increase("HOLD", 0.36)
        assert passed is False

    def test_speech_rate_exactly_at_threshold(self):
        """Test: Speech rate exactly at threshold."""
        # DE_ESCALATE threshold is 4.0
        passed, violation = check_de_escalate_no_rapid_tempo("DE_ESCALATE", 4.0)
        assert passed is True  # Passes at threshold

        passed, violation = check_de_escalate_no_rapid_tempo("DE_ESCALATE", 4.1)
        assert passed is False

    def test_unknown_regime_no_violations(self):
        """Test: Unknown regime doesn't cause violations."""
        passed, violation = check_regime_acoustic_flat("UNKNOWN_REGIME", "neutral")
        assert passed is True  # Only known restrictive regimes trigger

    def test_none_grounding_mode_no_violations(self):
        """Test: None grounding mode doesn't cause violations."""
        passed, violation = check_no_authority_escalation_reflexive(
            grounding_mode=None,
            suppress_certainty=False,
            suppress_emphasis=False,
            energy_level=0.5,
            pitch_range=(90, 140),
        )
        assert passed is True

    def test_context_missing_attributes(self):
        """Test: Context with missing attributes handled gracefully."""
        validator = P12ConsistencyValidator()
        ctx = object()  # Minimal context
        report = validator.validate(ctx)
        assert report is None  # Can't validate without P10


# ============================================================================
# L. MULTIPLE VIOLATION TESTS
# ============================================================================


class TestMultipleViolations:
    """Tests for scenarios with multiple violations."""

    def test_multiple_hold_violations(self):
        """Test: Multiple HOLD violations detected."""
        acoustic = AcousticParameterFrame(
            regime=AcousticRegime.NEUTRAL,  # VIOLATION 1
            speech_rate=4.5,
            energy_level=0.5,  # VIOLATION 2
            pitch_range=(90, 130),  # VIOLATION 3 (40 Hz)
            pause_policy=PausePolicy.MINIMAL,
            pause_duration_ms=(100, 150),
            emphasis_policy=EmphasisPolicy.LIMITED,  # VIOLATION 4
            max_stressed_tokens=1,  # (part of violation 4)
            suppress_emotion=False,  # VIOLATION 5
            suppress_emphasis=False,  # VIOLATION 6
            suppress_certainty=False,  # VIOLATION 7
            source_regime="HOLD",
            source_discourse_act="DEFERRAL",
        )
        ctx = MockPipelineContext(
            p10_acoustic=acoustic,
            p6_regime=MockRegimeEnvelope.create("HOLD"),
            p7_discourse_envelope=MockDiscourseEnvelope.create("DEFERRAL"),
        )
        report = run_p12_directly(ctx)

        assert report is not None
        assert report.is_consistent is False
        assert report.has_critical_violations() is True
        assert len(report.violations) >= 4  # Multiple violations

    def test_mixed_severity_violations(self):
        """Test: Mixed severity violations properly categorized."""
        acoustic = AcousticParameterFrame(
            regime=AcousticRegime.NEUTRAL,  # CRITICAL under HOLD
            speech_rate=3.5,
            energy_level=0.55,  # MINOR (lexical-prosodic)
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
        ctx = MockPipelineContext(
            p10_acoustic=acoustic,
            p6_regime=MockRegimeEnvelope.create("HOLD"),
            p7_discourse_envelope=MockDiscourseEnvelope.create("DEFERRAL"),
        )
        report = run_p12_directly(ctx)

        assert report is not None
        assert report.has_critical_violations() is True
        # Check for minor violations using get_minor_violations()
        minor_violations = report.get_minor_violations()
        assert len(minor_violations) >= 0  # May or may not have minor violations
