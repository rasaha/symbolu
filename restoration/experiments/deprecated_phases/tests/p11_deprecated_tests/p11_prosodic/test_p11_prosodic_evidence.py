"""
P11 Unit Tests - Prosodic Evidence Capture

Tests for P11 Prosodic Evidence Capture Engine:
- ProsodicEvidenceFrame dataclass
- P11ProsodicResolver (witness-only)
- Invariant validation
- Integration with P10

Test Categories (per specification):
A. Copy Integrity
   - Every P10 parameter copied exactly
   - No mutation of P10 frame

B. Witness-Only Behavior
   - Violations detected but not corrected
   - P11 never modifies upstream context

C. Determinism
   - Same ctx -> same evidence frame
   - No randomness in timestamps (mock or isolate)

D. Invariant Accuracy
   - HOLD regime -> all suppression invariants True
   - DE_ESCALATE -> no emotion amplification
   - Inject invalid acoustic frame -> violations_detected=True

E. Absence Safety
   - No P10 -> P11 returns None

Target: >= 25 tests

CRITICAL ARCHITECTURAL INVARIANT:
    P11 exists to observe, not to optimize.
    Sound must obey meaning.
    Meaning must never obey sound.
"""

import copy
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional
from unittest.mock import patch, MagicMock

import pytest

from symbolu.mechanical.pipeline.p11_prosodic import (
    ProsodicEvidenceFrame,
    P11ProsodicResolver,
    P11_VERSION,
    check_speech_rate_within_bounds,
    check_energy_within_bounds,
    check_pitch_within_bounds,
    check_pause_policy_respected,
    check_no_emotion_amplification,
    check_no_certainty_injection,
    check_no_emphasis_override,
    check_lexical_integrity_preserved,
    check_regime_constraints_respected,
)
from symbolu.mechanical.pipeline.p11_prosodic.p11_integration import (
    get_p11_resolver,
    maybe_run_p11,
    run_p11_directly,
    get_p11_prosodic_evidence,
    has_violations,
    get_failed_invariants,
    get_invariant_checks,
    is_fully_suppressed,
    get_witnessed_speech_rate,
    get_witnessed_energy_level,
    get_witnessed_pitch_range,
    get_source_p10_version,
    get_timestamp_utc,
)
from symbolu.mechanical.pipeline.p10_acoustic import (
    AcousticParameterFrame,
    AcousticRegime,
    EmphasisPolicy,
    PausePolicy,
    SPEECH_RATE_MIN,
    SPEECH_RATE_MAX,
    ENERGY_LEVEL_MIN,
    ENERGY_LEVEL_MAX,
    PITCH_MIN,
    PITCH_MAX,
    PAUSE_DURATION_MIN,
    PAUSE_DURATION_MAX,
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
    """Create a HOLD regime AcousticParameterFrame (most conservative)."""
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
    """Create a DE_ESCALATE regime AcousticParameterFrame."""
    return AcousticParameterFrame(
        regime=AcousticRegime.SOFT,
        speech_rate=3.2,
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


@dataclass
class MockPipelineContext:
    """Mock pipeline context for testing."""
    p10_acoustic: Optional[AcousticParameterFrame] = None
    p6_regime: Any = None
    p7_discourse_envelope: Any = None
    phase_zero: Any = None
    p11_prosodic_evidence: Optional[ProsodicEvidenceFrame] = None


# ============================================================================
# A. COPY INTEGRITY TESTS
# ============================================================================


class TestCopyIntegrity:
    """Tests that P11 copies P10 parameters exactly without modification."""

    def test_speech_rate_copied_exactly(self):
        """Test: speech_rate is copied exactly from P10."""
        acoustic = make_acoustic_frame(speech_rate=4.2)
        ctx = MockPipelineContext(p10_acoustic=acoustic)
        resolver = P11ProsodicResolver()
        evidence = resolver.capture(ctx)

        assert evidence is not None
        assert evidence.speech_rate == 4.2
        assert evidence.speech_rate == acoustic.speech_rate

    def test_energy_level_copied_exactly(self):
        """Test: energy_level is copied exactly from P10."""
        acoustic = make_acoustic_frame(energy_level=0.35)
        ctx = MockPipelineContext(p10_acoustic=acoustic)
        resolver = P11ProsodicResolver()
        evidence = resolver.capture(ctx)

        assert evidence is not None
        assert evidence.energy_level == 0.35
        assert evidence.energy_level == acoustic.energy_level

    def test_pitch_range_copied_exactly(self):
        """Test: pitch_range is copied exactly from P10."""
        acoustic = make_acoustic_frame(pitch_range=(110, 135))
        ctx = MockPipelineContext(p10_acoustic=acoustic)
        resolver = P11ProsodicResolver()
        evidence = resolver.capture(ctx)

        assert evidence is not None
        assert evidence.pitch_range == (110, 135)
        assert evidence.pitch_range == acoustic.pitch_range

    def test_pause_policy_copied_as_string(self):
        """Test: pause_policy is copied as string value."""
        acoustic = make_acoustic_frame(pause_policy=PausePolicy.NORMAL)
        ctx = MockPipelineContext(p10_acoustic=acoustic)
        resolver = P11ProsodicResolver()
        evidence = resolver.capture(ctx)

        assert evidence is not None
        assert evidence.pause_policy == "normal"
        assert evidence.pause_policy == acoustic.pause_policy.value

    def test_pause_duration_ms_copied_exactly(self):
        """Test: pause_duration_ms is copied exactly from P10."""
        acoustic = make_acoustic_frame(pause_duration_ms=(120, 200))
        ctx = MockPipelineContext(p10_acoustic=acoustic)
        resolver = P11ProsodicResolver()
        evidence = resolver.capture(ctx)

        assert evidence is not None
        assert evidence.pause_duration_ms == (120, 200)
        assert evidence.pause_duration_ms == acoustic.pause_duration_ms

    def test_emphasis_policy_copied_as_string(self):
        """Test: emphasis_policy is copied as string value."""
        acoustic = make_acoustic_frame(emphasis_policy=EmphasisPolicy.LIMITED)
        ctx = MockPipelineContext(p10_acoustic=acoustic)
        resolver = P11ProsodicResolver()
        evidence = resolver.capture(ctx)

        assert evidence is not None
        assert evidence.emphasis_policy == "limited"
        assert evidence.emphasis_policy == acoustic.emphasis_policy.value

    def test_max_stressed_tokens_copied_exactly(self):
        """Test: max_stressed_tokens is copied exactly from P10."""
        acoustic = make_acoustic_frame(max_stressed_tokens=1)
        ctx = MockPipelineContext(p10_acoustic=acoustic)
        resolver = P11ProsodicResolver()
        evidence = resolver.capture(ctx)

        assert evidence is not None
        assert evidence.max_stressed_tokens == 1
        assert evidence.max_stressed_tokens == acoustic.max_stressed_tokens

    def test_suppress_emotion_copied_exactly(self):
        """Test: suppress_emotion is copied exactly from P10."""
        acoustic = make_acoustic_frame(suppress_emotion=True)
        ctx = MockPipelineContext(p10_acoustic=acoustic)
        resolver = P11ProsodicResolver()
        evidence = resolver.capture(ctx)

        assert evidence is not None
        assert evidence.suppress_emotion is True
        assert evidence.suppress_emotion == acoustic.suppress_emotion

    def test_suppress_certainty_copied_exactly(self):
        """Test: suppress_certainty is copied exactly from P10."""
        acoustic = make_acoustic_frame(suppress_certainty=True)
        ctx = MockPipelineContext(p10_acoustic=acoustic)
        resolver = P11ProsodicResolver()
        evidence = resolver.capture(ctx)

        assert evidence is not None
        assert evidence.suppress_certainty is True
        assert evidence.suppress_certainty == acoustic.suppress_certainty

    def test_suppress_emphasis_copied_exactly(self):
        """Test: suppress_emphasis is copied exactly from P10."""
        acoustic = make_acoustic_frame(suppress_emphasis=True)
        ctx = MockPipelineContext(p10_acoustic=acoustic)
        resolver = P11ProsodicResolver()
        evidence = resolver.capture(ctx)

        assert evidence is not None
        assert evidence.suppress_emphasis is True
        assert evidence.suppress_emphasis == acoustic.suppress_emphasis

    def test_all_acoustic_parameters_copied(self):
        """Test: ALL acoustic parameters are copied from P10."""
        acoustic = make_hold_acoustic_frame()
        ctx = MockPipelineContext(p10_acoustic=acoustic)
        resolver = P11ProsodicResolver()
        evidence = resolver.capture(ctx)

        assert evidence is not None
        assert evidence.speech_rate == acoustic.speech_rate
        assert evidence.energy_level == acoustic.energy_level
        assert evidence.pitch_range == acoustic.pitch_range
        assert evidence.pause_policy == acoustic.pause_policy.value
        assert evidence.pause_duration_ms == acoustic.pause_duration_ms
        assert evidence.emphasis_policy == acoustic.emphasis_policy.value
        assert evidence.max_stressed_tokens == acoustic.max_stressed_tokens
        assert evidence.suppress_emotion == acoustic.suppress_emotion
        assert evidence.suppress_certainty == acoustic.suppress_certainty
        assert evidence.suppress_emphasis == acoustic.suppress_emphasis

    def test_p10_frame_not_mutated(self):
        """Test: P10 acoustic frame is NOT mutated by P11 capture."""
        acoustic = make_acoustic_frame()
        original_speech_rate = acoustic.speech_rate
        original_energy_level = acoustic.energy_level
        original_pitch_range = acoustic.pitch_range

        ctx = MockPipelineContext(p10_acoustic=acoustic)
        resolver = P11ProsodicResolver()
        evidence = resolver.capture(ctx)

        # Verify P10 frame is unchanged
        assert acoustic.speech_rate == original_speech_rate
        assert acoustic.energy_level == original_energy_level
        assert acoustic.pitch_range == original_pitch_range


# ============================================================================
# B. WITNESS-ONLY BEHAVIOR TESTS
# ============================================================================


class TestWitnessOnlyBehavior:
    """Tests that P11 only observes and never modifies."""

    def test_violations_detected_but_not_corrected(self):
        """Test: Violations are detected but NOT corrected."""
        # Create a frame that violates invariants under HOLD
        # (suppress_emphasis should be True for HOLD, but we set it False)
        acoustic = AcousticParameterFrame(
            regime=AcousticRegime.FLAT,
            speech_rate=3.5,
            energy_level=0.25,
            pitch_range=(95, 105),
            pause_policy=PausePolicy.NORMAL,
            pause_duration_ms=(150, 250),
            emphasis_policy=EmphasisPolicy.NONE,
            max_stressed_tokens=0,
            suppress_emotion=True,
            suppress_emphasis=False,  # VIOLATION: should be True for HOLD
            suppress_certainty=True,
            source_regime="HOLD",
            source_discourse_act="DEFERRAL",
        )

        ctx = MockPipelineContext(p10_acoustic=acoustic)
        resolver = P11ProsodicResolver()
        evidence = resolver.capture(ctx)

        # Violation should be detected
        assert evidence is not None
        assert evidence.violations_detected is True
        assert "no_emphasis_override" in evidence.get_failed_invariants()

        # But the value is still copied exactly (not corrected)
        assert evidence.suppress_emphasis is False

    def test_p11_never_modifies_context_p10_acoustic(self):
        """Test: P11 never modifies ctx.p10_acoustic."""
        acoustic = make_acoustic_frame()
        ctx = MockPipelineContext(p10_acoustic=acoustic)

        # Store reference
        original_p10 = ctx.p10_acoustic

        resolver = P11ProsodicResolver()
        resolver.capture(ctx)

        # P10 should be the exact same object
        assert ctx.p10_acoustic is original_p10

    def test_p11_cannot_block_pipeline(self):
        """Test: P11 cannot block the pipeline (always returns evidence or None)."""
        # Even with bad data, P11 should return evidence without raising
        acoustic = make_acoustic_frame()
        ctx = MockPipelineContext(p10_acoustic=acoustic)
        resolver = P11ProsodicResolver()
        evidence = resolver.capture(ctx)

        # Should always return a valid frame if P10 exists
        assert evidence is not None
        assert isinstance(evidence, ProsodicEvidenceFrame)

    def test_violations_do_not_affect_downstream_values(self):
        """Test: Detected violations don't change the witnessed values."""
        acoustic = AcousticParameterFrame(
            regime=AcousticRegime.SOFT,  # VIOLATION: should be FLAT for HOLD
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

        ctx = MockPipelineContext(p10_acoustic=acoustic)
        resolver = P11ProsodicResolver()
        evidence = resolver.capture(ctx)

        # Violation detected for regime constraint
        assert evidence is not None
        assert evidence.violations_detected is True
        assert "regime_constraints_respected" in evidence.get_failed_invariants()

        # But the values are still copied exactly
        assert evidence.speech_rate == 3.5
        assert evidence.energy_level == 0.25


# ============================================================================
# C. DETERMINISM TESTS
# ============================================================================


class TestDeterminism:
    """Tests that P11 is deterministic (same input -> same output)."""

    def test_same_ctx_produces_same_evidence_frame(self):
        """Test: Same context produces same evidence frame (except timestamp)."""
        acoustic = make_acoustic_frame()
        ctx1 = MockPipelineContext(p10_acoustic=acoustic)
        ctx2 = MockPipelineContext(p10_acoustic=acoustic)

        resolver = P11ProsodicResolver()

        with patch.object(resolver, '_get_timestamp_utc', return_value="2024-01-01T00:00:00+00:00"):
            evidence1 = resolver.capture(ctx1)
            evidence2 = resolver.capture(ctx2)

        assert evidence1 is not None
        assert evidence2 is not None
        assert evidence1.speech_rate == evidence2.speech_rate
        assert evidence1.energy_level == evidence2.energy_level
        assert evidence1.pitch_range == evidence2.pitch_range
        assert evidence1.invariant_checks == evidence2.invariant_checks
        assert evidence1.violations_detected == evidence2.violations_detected
        assert evidence1.timestamp_utc == evidence2.timestamp_utc

    def test_invariant_checks_are_deterministic(self):
        """Test: Invariant checks produce same results for same input."""
        acoustic = make_hold_acoustic_frame()
        ctx = MockPipelineContext(p10_acoustic=acoustic)

        resolver = P11ProsodicResolver()
        evidence1 = resolver.capture(ctx)
        evidence2 = resolver.capture(ctx)

        assert evidence1 is not None
        assert evidence2 is not None
        assert evidence1.invariant_checks == evidence2.invariant_checks

    def test_no_randomness_in_resolver(self):
        """Test: No randomness in resolver (same acoustic -> same invariants)."""
        acoustic = make_de_escalate_acoustic_frame()

        results = []
        for _ in range(10):
            ctx = MockPipelineContext(p10_acoustic=acoustic)
            resolver = P11ProsodicResolver()
            evidence = resolver.capture(ctx)
            results.append(evidence.invariant_checks)

        # All results should be identical
        for result in results[1:]:
            assert result == results[0]


# ============================================================================
# D. INVARIANT ACCURACY TESTS
# ============================================================================


class TestInvariantAccuracy:
    """Tests that invariant checks are accurate."""

    def test_hold_regime_all_suppression_invariants_true(self):
        """Test: HOLD regime has all suppression invariants True."""
        acoustic = make_hold_acoustic_frame()
        ctx = MockPipelineContext(p10_acoustic=acoustic)
        resolver = P11ProsodicResolver()
        evidence = resolver.capture(ctx)

        assert evidence is not None
        assert evidence.violations_detected is False
        assert evidence.invariant_checks["no_emotion_amplification"] is True
        assert evidence.invariant_checks["no_certainty_injection"] is True
        assert evidence.invariant_checks["no_emphasis_override"] is True

    def test_de_escalate_no_emotion_amplification(self):
        """Test: DE_ESCALATE regime has no emotion amplification."""
        acoustic = make_de_escalate_acoustic_frame()
        ctx = MockPipelineContext(p10_acoustic=acoustic)
        resolver = P11ProsodicResolver()
        evidence = resolver.capture(ctx)

        assert evidence is not None
        assert evidence.invariant_checks["no_emotion_amplification"] is True

    def test_violations_detected_for_wrong_regime_constraint(self):
        """Test: violations_detected=True for wrong regime constraint."""
        # NEUTRAL acoustic under HOLD regime is a violation
        acoustic = AcousticParameterFrame(
            regime=AcousticRegime.NEUTRAL,  # VIOLATION: should be FLAT for HOLD
            speech_rate=4.5,
            energy_level=0.45,
            pitch_range=(100, 130),
            pause_policy=PausePolicy.MINIMAL,
            pause_duration_ms=(100, 150),
            emphasis_policy=EmphasisPolicy.LIMITED,
            max_stressed_tokens=1,
            suppress_emotion=True,
            suppress_emphasis=True,
            suppress_certainty=True,
            source_regime="HOLD",
            source_discourse_act="EXPLANATION",
        )

        ctx = MockPipelineContext(p10_acoustic=acoustic)
        resolver = P11ProsodicResolver()
        evidence = resolver.capture(ctx)

        assert evidence is not None
        assert evidence.violations_detected is True
        assert evidence.invariant_checks["regime_constraints_respected"] is False

    def test_violations_detected_for_missing_suppression(self):
        """Test: violations_detected=True when suppression is missing."""
        # HOLD regime without suppress_emotion is a violation
        acoustic = AcousticParameterFrame(
            regime=AcousticRegime.FLAT,
            speech_rate=3.5,
            energy_level=0.25,
            pitch_range=(95, 105),
            pause_policy=PausePolicy.NORMAL,
            pause_duration_ms=(150, 250),
            emphasis_policy=EmphasisPolicy.NONE,
            max_stressed_tokens=0,
            suppress_emotion=False,  # VIOLATION
            suppress_emphasis=True,
            suppress_certainty=True,
            source_regime="HOLD",
            source_discourse_act="DEFERRAL",
        )

        ctx = MockPipelineContext(p10_acoustic=acoustic)
        resolver = P11ProsodicResolver()
        evidence = resolver.capture(ctx)

        assert evidence is not None
        assert evidence.violations_detected is True
        assert evidence.invariant_checks["no_emotion_amplification"] is False

    def test_speech_rate_bounds_check_passes(self):
        """Test: speech_rate within bounds passes."""
        acoustic = make_acoustic_frame(speech_rate=4.0)
        assert check_speech_rate_within_bounds(acoustic) is True

    def test_energy_bounds_check_passes(self):
        """Test: energy_level within bounds passes."""
        acoustic = make_acoustic_frame(energy_level=0.4)
        assert check_energy_within_bounds(acoustic) is True

    def test_pitch_bounds_check_passes(self):
        """Test: pitch_range within bounds passes."""
        acoustic = make_acoustic_frame(pitch_range=(100, 130))
        assert check_pitch_within_bounds(acoustic) is True

    def test_pause_policy_check_passes(self):
        """Test: pause_duration_ms within bounds passes."""
        acoustic = make_acoustic_frame(pause_duration_ms=(150, 250))
        assert check_pause_policy_respected(acoustic) is True

    def test_lexical_integrity_always_preserved(self):
        """Test: lexical_integrity_preserved is always True (by design)."""
        acoustic = make_acoustic_frame()
        assert check_lexical_integrity_preserved(acoustic) is True


# ============================================================================
# E. ABSENCE SAFETY TESTS
# ============================================================================


class TestAbsenceSafety:
    """Tests for safe handling of missing P10."""

    def test_no_p10_returns_none(self):
        """Test: No P10 acoustic frame returns None."""
        ctx = MockPipelineContext(p10_acoustic=None)
        resolver = P11ProsodicResolver()
        evidence = resolver.capture(ctx)

        assert evidence is None

    def test_missing_p10_attribute_returns_none(self):
        """Test: Missing p10_acoustic attribute returns None."""
        ctx = object()  # No p10_acoustic attribute
        resolver = P11ProsodicResolver()
        evidence = resolver.capture(ctx)

        assert evidence is None

    def test_maybe_run_p11_with_no_p10(self):
        """Test: maybe_run_p11 with no P10 sets evidence to None."""
        ctx = MockPipelineContext(p10_acoustic=None)
        result_ctx = maybe_run_p11(ctx)

        assert result_ctx.p11_prosodic_evidence is None


# ============================================================================
# INTEGRATION TESTS
# ============================================================================


class TestIntegration:
    """Tests for P11 integration functions."""

    def test_maybe_run_p11_attaches_evidence(self):
        """Test: maybe_run_p11 attaches evidence to context."""
        acoustic = make_acoustic_frame()
        ctx = MockPipelineContext(p10_acoustic=acoustic)

        result_ctx = maybe_run_p11(ctx)

        assert result_ctx.p11_prosodic_evidence is not None
        assert isinstance(result_ctx.p11_prosodic_evidence, ProsodicEvidenceFrame)

    def test_maybe_run_p11_idempotent(self):
        """Test: maybe_run_p11 is idempotent (doesn't run twice)."""
        acoustic = make_acoustic_frame()
        ctx = MockPipelineContext(p10_acoustic=acoustic)

        maybe_run_p11(ctx)
        first_evidence = ctx.p11_prosodic_evidence
        first_timestamp = first_evidence.timestamp_utc

        # Run again
        maybe_run_p11(ctx)
        second_evidence = ctx.p11_prosodic_evidence

        # Should be the same object (didn't run again)
        assert second_evidence.timestamp_utc == first_timestamp

    def test_run_p11_directly(self):
        """Test: run_p11_directly returns evidence without modifying context."""
        acoustic = make_acoustic_frame()
        ctx = MockPipelineContext(p10_acoustic=acoustic)

        evidence = run_p11_directly(ctx)

        assert evidence is not None
        assert isinstance(evidence, ProsodicEvidenceFrame)
        # Context should not have evidence attached
        assert ctx.p11_prosodic_evidence is None

    def test_accessor_functions(self):
        """Test: Integration accessor functions work correctly."""
        acoustic = make_acoustic_frame(speech_rate=4.3, energy_level=0.42)
        ctx = MockPipelineContext(p10_acoustic=acoustic)
        maybe_run_p11(ctx)

        assert get_witnessed_speech_rate(ctx) == 4.3
        assert get_witnessed_energy_level(ctx) == 0.42
        assert get_witnessed_pitch_range(ctx) == (100, 130)
        assert get_source_p10_version(ctx) is not None
        assert get_timestamp_utc(ctx) is not None

    def test_has_violations_accessor(self):
        """Test: has_violations accessor works correctly."""
        acoustic = make_hold_acoustic_frame()
        ctx = MockPipelineContext(p10_acoustic=acoustic)
        maybe_run_p11(ctx)

        assert has_violations(ctx) is False

    def test_get_failed_invariants_accessor(self):
        """Test: get_failed_invariants accessor works correctly."""
        acoustic = make_hold_acoustic_frame()
        ctx = MockPipelineContext(p10_acoustic=acoustic)
        maybe_run_p11(ctx)

        failed = get_failed_invariants(ctx)
        assert failed == []


# ============================================================================
# DATACLASS TESTS
# ============================================================================


class TestProsodicEvidenceFrame:
    """Tests for ProsodicEvidenceFrame dataclass."""

    def test_basic_construction(self):
        """Test: basic frame construction."""
        frame = ProsodicEvidenceFrame(
            speech_rate=4.5,
            energy_level=0.45,
            pitch_range=(100, 130),
            pause_policy="minimal",
            pause_duration_ms=(100, 150),
            emphasis_policy="limited",
            max_stressed_tokens=1,
            suppress_emotion=True,
            suppress_certainty=False,
            suppress_emphasis=False,
            source_regime="INFORM",
            source_discourse_act="EXPLANATION",
            source_intent="INFORM",
            source_p10_version="P10-1.0.0",
            timestamp_utc="2024-01-01T00:00:00+00:00",
            invariant_checks={"test": True},
            violations_detected=False,
        )
        assert frame.speech_rate == 4.5
        assert frame.architectural_phase == "P11"

    def test_immutability(self):
        """Test: ProsodicEvidenceFrame is frozen (immutable)."""
        frame = ProsodicEvidenceFrame(
            speech_rate=4.5,
            energy_level=0.45,
            pitch_range=(100, 130),
            pause_policy="minimal",
            pause_duration_ms=(100, 150),
            emphasis_policy="limited",
            max_stressed_tokens=1,
            suppress_emotion=True,
            suppress_certainty=False,
            suppress_emphasis=False,
            source_regime="INFORM",
            source_discourse_act="EXPLANATION",
            source_intent="INFORM",
            source_p10_version="P10-1.0.0",
            timestamp_utc="2024-01-01T00:00:00+00:00",
            invariant_checks={},
            violations_detected=False,
        )
        with pytest.raises(Exception):  # FrozenInstanceError
            frame.speech_rate = 5.0

    def test_has_violations_method(self):
        """Test: has_violations() method works correctly."""
        frame_no_violations = ProsodicEvidenceFrame(
            speech_rate=4.5,
            energy_level=0.45,
            pitch_range=(100, 130),
            pause_policy="minimal",
            pause_duration_ms=(100, 150),
            emphasis_policy="limited",
            max_stressed_tokens=1,
            suppress_emotion=True,
            suppress_certainty=False,
            suppress_emphasis=False,
            source_regime="INFORM",
            source_discourse_act="EXPLANATION",
            source_intent=None,
            source_p10_version="P10-1.0.0",
            timestamp_utc="2024-01-01T00:00:00+00:00",
            invariant_checks={"test": True},
            violations_detected=False,
        )
        assert frame_no_violations.has_violations() is False

        frame_with_violations = ProsodicEvidenceFrame(
            speech_rate=4.5,
            energy_level=0.45,
            pitch_range=(100, 130),
            pause_policy="minimal",
            pause_duration_ms=(100, 150),
            emphasis_policy="limited",
            max_stressed_tokens=1,
            suppress_emotion=True,
            suppress_certainty=False,
            suppress_emphasis=False,
            source_regime="INFORM",
            source_discourse_act="EXPLANATION",
            source_intent=None,
            source_p10_version="P10-1.0.0",
            timestamp_utc="2024-01-01T00:00:00+00:00",
            invariant_checks={"test": False},
            violations_detected=True,
        )
        assert frame_with_violations.has_violations() is True

    def test_get_failed_invariants_method(self):
        """Test: get_failed_invariants() method works correctly."""
        frame = ProsodicEvidenceFrame(
            speech_rate=4.5,
            energy_level=0.45,
            pitch_range=(100, 130),
            pause_policy="minimal",
            pause_duration_ms=(100, 150),
            emphasis_policy="limited",
            max_stressed_tokens=1,
            suppress_emotion=True,
            suppress_certainty=False,
            suppress_emphasis=False,
            source_regime="INFORM",
            source_discourse_act="EXPLANATION",
            source_intent=None,
            source_p10_version="P10-1.0.0",
            timestamp_utc="2024-01-01T00:00:00+00:00",
            invariant_checks={"check1": True, "check2": False, "check3": True},
            violations_detected=True,
        )
        failed = frame.get_failed_invariants()
        assert failed == ["check2"]

    def test_is_fully_suppressed_method(self):
        """Test: is_fully_suppressed() method works correctly."""
        frame_fully_suppressed = ProsodicEvidenceFrame(
            speech_rate=3.5,
            energy_level=0.25,
            pitch_range=(95, 105),
            pause_policy="normal",
            pause_duration_ms=(150, 250),
            emphasis_policy="none",
            max_stressed_tokens=0,
            suppress_emotion=True,
            suppress_certainty=True,
            suppress_emphasis=True,
            source_regime="HOLD",
            source_discourse_act="DEFERRAL",
            source_intent=None,
            source_p10_version="P10-1.0.0",
            timestamp_utc="2024-01-01T00:00:00+00:00",
            invariant_checks={},
            violations_detected=False,
        )
        assert frame_fully_suppressed.is_fully_suppressed() is True

        frame_not_fully_suppressed = ProsodicEvidenceFrame(
            speech_rate=4.5,
            energy_level=0.45,
            pitch_range=(100, 130),
            pause_policy="minimal",
            pause_duration_ms=(100, 150),
            emphasis_policy="limited",
            max_stressed_tokens=1,
            suppress_emotion=True,
            suppress_certainty=False,
            suppress_emphasis=False,
            source_regime="INFORM",
            source_discourse_act="EXPLANATION",
            source_intent=None,
            source_p10_version="P10-1.0.0",
            timestamp_utc="2024-01-01T00:00:00+00:00",
            invariant_checks={},
            violations_detected=False,
        )
        assert frame_not_fully_suppressed.is_fully_suppressed() is False

    def test_to_dict_serialization(self):
        """Test: to_dict() serialization works correctly."""
        frame = ProsodicEvidenceFrame(
            speech_rate=4.5,
            energy_level=0.45,
            pitch_range=(100, 130),
            pause_policy="minimal",
            pause_duration_ms=(100, 150),
            emphasis_policy="limited",
            max_stressed_tokens=1,
            suppress_emotion=True,
            suppress_certainty=False,
            suppress_emphasis=False,
            source_regime="INFORM",
            source_discourse_act="EXPLANATION",
            source_intent="INFORM",
            source_p10_version="P10-1.0.0",
            timestamp_utc="2024-01-01T00:00:00+00:00",
            invariant_checks={"test": True},
            violations_detected=False,
        )
        d = frame.to_dict()

        assert d["speech_rate"] == 4.5
        assert d["energy_level"] == 0.45
        assert d["pitch_range"] == [100, 130]
        assert d["architectural_phase"] == "P11"
        assert d["violations_detected"] is False


# ============================================================================
# INVARIANT CHECK FUNCTION TESTS
# ============================================================================


class TestInvariantCheckFunctions:
    """Tests for individual invariant check functions."""

    def test_check_regime_constraints_hold_flat(self):
        """Test: HOLD regime requires FLAT acoustic regime."""
        acoustic_flat = AcousticParameterFrame(
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
        assert check_regime_constraints_respected(acoustic_flat, "HOLD") is True

        acoustic_neutral = AcousticParameterFrame(
            regime=AcousticRegime.NEUTRAL,
            speech_rate=4.5,
            energy_level=0.45,
            pitch_range=(100, 130),
            pause_policy=PausePolicy.MINIMAL,
            pause_duration_ms=(100, 150),
            emphasis_policy=EmphasisPolicy.LIMITED,
            max_stressed_tokens=1,
            suppress_emotion=True,
            suppress_emphasis=True,
            suppress_certainty=True,
            source_regime="HOLD",
            source_discourse_act="EXPLANATION",
        )
        assert check_regime_constraints_respected(acoustic_neutral, "HOLD") is False

    def test_check_regime_constraints_de_escalate_soft(self):
        """Test: DE_ESCALATE regime allows SOFT or FLAT."""
        acoustic_soft = AcousticParameterFrame(
            regime=AcousticRegime.SOFT,
            speech_rate=3.2,
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
        assert check_regime_constraints_respected(acoustic_soft, "DE_ESCALATE") is True

    def test_check_no_emotion_amplification_restrictive_regimes(self):
        """Test: No emotion amplification under restrictive regimes."""
        acoustic_suppressed = make_hold_acoustic_frame()
        assert check_no_emotion_amplification(acoustic_suppressed, "HOLD") is True
        assert check_no_emotion_amplification(acoustic_suppressed, "DE_ESCALATE") is True
        assert check_no_emotion_amplification(acoustic_suppressed, "STABILIZE") is True
        assert check_no_emotion_amplification(acoustic_suppressed, "REFLECT") is True

        acoustic_not_suppressed = AcousticParameterFrame(
            regime=AcousticRegime.FLAT,
            speech_rate=3.5,
            energy_level=0.25,
            pitch_range=(95, 105),
            pause_policy=PausePolicy.NORMAL,
            pause_duration_ms=(150, 250),
            emphasis_policy=EmphasisPolicy.NONE,
            max_stressed_tokens=0,
            suppress_emotion=False,  # Not suppressed
            suppress_emphasis=True,
            suppress_certainty=True,
            source_regime="HOLD",
            source_discourse_act="DEFERRAL",
        )
        assert check_no_emotion_amplification(acoustic_not_suppressed, "HOLD") is False

    def test_check_no_certainty_injection_restrictive_regimes(self):
        """Test: No certainty injection under restrictive regimes."""
        acoustic_suppressed = make_hold_acoustic_frame()
        assert check_no_certainty_injection(acoustic_suppressed, "HOLD") is True

        acoustic_not_suppressed = AcousticParameterFrame(
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
            suppress_certainty=False,  # Not suppressed
            source_regime="HOLD",
            source_discourse_act="DEFERRAL",
        )
        assert check_no_certainty_injection(acoustic_not_suppressed, "HOLD") is False

    def test_check_inform_regime_allows_neutral(self):
        """Test: INFORM regime allows NEUTRAL acoustic regime."""
        acoustic = make_acoustic_frame(regime=AcousticRegime.NEUTRAL)
        assert check_regime_constraints_respected(acoustic, "INFORM") is True
        assert check_regime_constraints_respected(acoustic, "CLARIFY") is True
