"""
P10-P11 Invariance Test Suite

GOVERNANCE INVARIANCE TESTS for Symbol-U pipeline phases P10 and P11.

These tests are NOT unit tests of functions.
They are governance invariance tests.

They prove:
1. P10 never violates bounds
2. P10 obeys regime/discourse constraints
3. P10 never mutates lexical output
4. P10 is deterministic
5. P11 is non-authoritative + non-mutating witness
6. P11 invariant_checks are accurate and complete
7. P11 does not "heal" violations (records them)

Design Principles:
- Deterministic: No LLM calls, no probabilistic sampling
- Zero-LLM: All tests are mechanically verifiable
- No refactoring: Tests do not modify production code

CRITICAL ARCHITECTURAL INVARIANT:
    Sound must obey meaning.
    Meaning must never obey sound.

Run with:
    pytest -q symbolu/mechanical/pipeline/tests/p10_p11/test_p10_p11_invariants.py
"""

import copy
import json
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple
from unittest.mock import patch

import pytest

# P10 imports
from symbolu.mechanical.pipeline.p10_acoustic import (
    P10AcousticResolver,
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
    MAX_STRESSED_TOKENS_MIN,
    MAX_STRESSED_TOKENS_MAX,
    HOLD_ACOUSTIC_CONFIG,
    DE_ESCALATE_ACOUSTIC_CONFIG,
    STABILIZE_ACOUSTIC_CONFIG,
    REFLECT_ACOUSTIC_CONFIG,
    INFORM_ACOUSTIC_CONFIG,
    CLARIFY_ACOUSTIC_CONFIG,
    SAFE_DEFAULT_CONFIG,
)
from symbolu.mechanical.pipeline.p10_acoustic.p10_integration import (
    maybe_run_p10,
    run_p10_directly,
)

# P11 imports
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
    maybe_run_p11,
    run_p11_directly,
)

# Upstream schema imports
from symbolu.mechanical.pipeline.phase_p6.p6_schema import (
    RegimeEnvelope,
    OperationalRegime,
)
from symbolu.mechanical.pipeline.p7_discourse.p7_discourse_schema import (
    DiscourseEnvelope,
    DiscourseAct,
)
from symbolu.mechanical.pipeline.p9_lexical.p9_lexical_schema import (
    LexicalFrame,
)
from symbolu.mechanical.pipeline.p8_semantics.p8_semantic_schema import (
    SemanticSlot,
)
from symbolu.mechanical.pipeline.phase_zero.phase_zero_schema import IntentType
from symbolu.mechanical.pipeline.phase_po5.po5_schema import ExecutionEligibility


# ============================================================================
# TEST SETUP HELPERS
# ============================================================================


@dataclass
class MinimalPipelineContext:
    """
    Minimal PipelineContext for P10/P11 invariance testing.

    Contains only fields needed by P10 and P11:
    - p6_regime: RegimeEnvelope
    - p7_discourse_envelope: DiscourseEnvelope
    - lexical_frame: LexicalFrame
    - phase_zero: Optional intent envelope
    - p10_acoustic: AcousticParameterFrame (set by P10)
    - p11_prosodic_evidence: ProsodicEvidenceFrame (set by P11)
    """
    p6_regime: Optional[RegimeEnvelope] = None
    p7_discourse_envelope: Optional[DiscourseEnvelope] = None
    lexical_frame: Optional[LexicalFrame] = None
    phase_zero: Optional[Any] = None
    p10_acoustic: Optional[AcousticParameterFrame] = None
    p11_prosodic_evidence: Optional[ProsodicEvidenceFrame] = None


@dataclass
class MockPhaseZero:
    """Minimal phase_zero mock for intent tracing."""
    intent_type: IntentType = IntentType.INFORM


def make_ctx(
    regime: OperationalRegime = OperationalRegime.INFORM,
    discourse_act: DiscourseAct = DiscourseAct.EXPLANATION,
    intent: IntentType = IntentType.INFORM,
    lexical_selections: Optional[Dict[SemanticSlot, str]] = None,
    include_phase_zero: bool = True,
) -> MinimalPipelineContext:
    """
    Create a minimal PipelineContext with only fields needed by P10/P11.

    Args:
        regime: The operational regime from P6.
        discourse_act: The discourse act from P7.
        intent: The intent type for tracing.
        lexical_selections: Optional lexical selections for P9 frame.
        include_phase_zero: Whether to include phase_zero mock.

    Returns:
        MinimalPipelineContext with all required fields populated.
    """
    if lexical_selections is None:
        lexical_selections = {
            SemanticSlot.AGENT: "I",
            SemanticSlot.STATE: "understand",
        }

    # Create RegimeEnvelope
    regime_envelope = RegimeEnvelope(
        regime=regime,
        reason="Invariance test",
        intent=intent,
        execution_eligibility=ExecutionEligibility.DEFERRED,
        coherence_regime="stable",
    )

    # Create DiscourseEnvelope
    discourse_envelope = DiscourseEnvelope(
        act=discourse_act,
        allowed=True,
        reason="Invariance test",
        intent=intent,
        regime=regime,
    )

    # Create LexicalFrame
    lexical_frame = LexicalFrame(
        selections=lexical_selections,
        allowed=True,
        reason="Invariance test",
        source_discourse_act=discourse_act.value,
        source_regime=regime.value,
    )

    # Create phase_zero mock if requested
    phase_zero = MockPhaseZero(intent_type=intent) if include_phase_zero else None

    return MinimalPipelineContext(
        p6_regime=regime_envelope,
        p7_discourse_envelope=discourse_envelope,
        lexical_frame=lexical_frame,
        phase_zero=phase_zero,
        p10_acoustic=None,
        p11_prosodic_evidence=None,
    )


def make_acoustic_frame(
    regime: AcousticRegime = AcousticRegime.NEUTRAL,
    speech_rate: float = 4.5,
    energy_level: float = 0.45,
    pitch_range: Tuple[int, int] = (100, 130),
    pause_policy: PausePolicy = PausePolicy.MINIMAL,
    pause_duration_ms: Tuple[int, int] = (100, 150),
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


def make_hold_frame() -> AcousticParameterFrame:
    """Create a HOLD (FLAT) regime AcousticParameterFrame."""
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


# ============================================================================
# I. P10 HARD BOUNDS INVARIANTS (8+ tests)
# ============================================================================


class TestP10HardBoundsInvariants:
    """
    P10 must never produce parameters outside hard bounds.

    For each regime mapping, assert:
    - 3.0 <= speech_rate <= 5.5
    - 0.2 <= energy_level <= 0.6
    - 90 <= pitch_range[0] <= pitch_range[1] <= 140
    - 100 <= pause_duration_ms[0] <= pause_duration_ms[1] <= 300
    - 0 <= max_stressed_tokens <= 1
    """

    def test_hold_regime_bounds(self):
        """HOLD regime produces parameters within all bounds."""
        ctx = make_ctx(regime=OperationalRegime.HOLD, discourse_act=DiscourseAct.DEFERRAL)
        maybe_run_p10(ctx)
        frame = ctx.p10_acoustic

        assert SPEECH_RATE_MIN <= frame.speech_rate <= SPEECH_RATE_MAX
        assert ENERGY_LEVEL_MIN <= frame.energy_level <= ENERGY_LEVEL_MAX
        assert PITCH_MIN <= frame.pitch_range[0] <= frame.pitch_range[1] <= PITCH_MAX
        assert PAUSE_DURATION_MIN <= frame.pause_duration_ms[0] <= frame.pause_duration_ms[1] <= PAUSE_DURATION_MAX
        assert MAX_STRESSED_TOKENS_MIN <= frame.max_stressed_tokens <= MAX_STRESSED_TOKENS_MAX

    def test_de_escalate_regime_bounds(self):
        """DE_ESCALATE regime produces parameters within all bounds."""
        ctx = make_ctx(regime=OperationalRegime.DE_ESCALATE, discourse_act=DiscourseAct.REFLECTION)
        maybe_run_p10(ctx)
        frame = ctx.p10_acoustic

        assert SPEECH_RATE_MIN <= frame.speech_rate <= SPEECH_RATE_MAX
        assert ENERGY_LEVEL_MIN <= frame.energy_level <= ENERGY_LEVEL_MAX
        assert PITCH_MIN <= frame.pitch_range[0] <= frame.pitch_range[1] <= PITCH_MAX
        assert PAUSE_DURATION_MIN <= frame.pause_duration_ms[0] <= frame.pause_duration_ms[1] <= PAUSE_DURATION_MAX
        assert MAX_STRESSED_TOKENS_MIN <= frame.max_stressed_tokens <= MAX_STRESSED_TOKENS_MAX

    def test_stabilize_regime_bounds(self):
        """STABILIZE regime produces parameters within all bounds."""
        ctx = make_ctx(regime=OperationalRegime.STABILIZE, discourse_act=DiscourseAct.ACKNOWLEDGMENT)
        maybe_run_p10(ctx)
        frame = ctx.p10_acoustic

        assert SPEECH_RATE_MIN <= frame.speech_rate <= SPEECH_RATE_MAX
        assert ENERGY_LEVEL_MIN <= frame.energy_level <= ENERGY_LEVEL_MAX
        assert PITCH_MIN <= frame.pitch_range[0] <= frame.pitch_range[1] <= PITCH_MAX
        assert PAUSE_DURATION_MIN <= frame.pause_duration_ms[0] <= frame.pause_duration_ms[1] <= PAUSE_DURATION_MAX
        assert MAX_STRESSED_TOKENS_MIN <= frame.max_stressed_tokens <= MAX_STRESSED_TOKENS_MAX

    def test_reflect_regime_bounds(self):
        """REFLECT regime produces parameters within all bounds."""
        ctx = make_ctx(regime=OperationalRegime.REFLECT, discourse_act=DiscourseAct.REFLECTION)
        maybe_run_p10(ctx)
        frame = ctx.p10_acoustic

        assert SPEECH_RATE_MIN <= frame.speech_rate <= SPEECH_RATE_MAX
        assert ENERGY_LEVEL_MIN <= frame.energy_level <= ENERGY_LEVEL_MAX
        assert PITCH_MIN <= frame.pitch_range[0] <= frame.pitch_range[1] <= PITCH_MAX
        assert PAUSE_DURATION_MIN <= frame.pause_duration_ms[0] <= frame.pause_duration_ms[1] <= PAUSE_DURATION_MAX
        assert MAX_STRESSED_TOKENS_MIN <= frame.max_stressed_tokens <= MAX_STRESSED_TOKENS_MAX

    def test_inform_regime_bounds(self):
        """INFORM regime produces parameters within all bounds."""
        ctx = make_ctx(regime=OperationalRegime.INFORM, discourse_act=DiscourseAct.EXPLANATION)
        maybe_run_p10(ctx)
        frame = ctx.p10_acoustic

        assert SPEECH_RATE_MIN <= frame.speech_rate <= SPEECH_RATE_MAX
        assert ENERGY_LEVEL_MIN <= frame.energy_level <= ENERGY_LEVEL_MAX
        assert PITCH_MIN <= frame.pitch_range[0] <= frame.pitch_range[1] <= PITCH_MAX
        assert PAUSE_DURATION_MIN <= frame.pause_duration_ms[0] <= frame.pause_duration_ms[1] <= PAUSE_DURATION_MAX
        assert MAX_STRESSED_TOKENS_MIN <= frame.max_stressed_tokens <= MAX_STRESSED_TOKENS_MAX

    def test_clarify_regime_bounds(self):
        """CLARIFY regime produces parameters within all bounds."""
        ctx = make_ctx(regime=OperationalRegime.CLARIFY, discourse_act=DiscourseAct.QUESTION)
        maybe_run_p10(ctx)
        frame = ctx.p10_acoustic

        assert SPEECH_RATE_MIN <= frame.speech_rate <= SPEECH_RATE_MAX
        assert ENERGY_LEVEL_MIN <= frame.energy_level <= ENERGY_LEVEL_MAX
        assert PITCH_MIN <= frame.pitch_range[0] <= frame.pitch_range[1] <= PITCH_MAX
        assert PAUSE_DURATION_MIN <= frame.pause_duration_ms[0] <= frame.pause_duration_ms[1] <= PAUSE_DURATION_MAX
        assert MAX_STRESSED_TOKENS_MIN <= frame.max_stressed_tokens <= MAX_STRESSED_TOKENS_MAX

    def test_config_constants_within_bounds(self):
        """All regime config constants are within hard bounds."""
        configs = [
            HOLD_ACOUSTIC_CONFIG,
            DE_ESCALATE_ACOUSTIC_CONFIG,
            STABILIZE_ACOUSTIC_CONFIG,
            REFLECT_ACOUSTIC_CONFIG,
            INFORM_ACOUSTIC_CONFIG,
            CLARIFY_ACOUSTIC_CONFIG,
            SAFE_DEFAULT_CONFIG,
        ]

        for config in configs:
            assert SPEECH_RATE_MIN <= config["speech_rate"] <= SPEECH_RATE_MAX
            assert ENERGY_LEVEL_MIN <= config["energy_level"] <= ENERGY_LEVEL_MAX
            pr = config["pitch_range"]
            assert PITCH_MIN <= pr[0] <= pr[1] <= PITCH_MAX
            pd = config["pause_duration_ms"]
            assert PAUSE_DURATION_MIN <= pd[0] <= pd[1] <= PAUSE_DURATION_MAX
            assert MAX_STRESSED_TOKENS_MIN <= config["max_stressed_tokens"] <= MAX_STRESSED_TOKENS_MAX

    def test_adversarial_missing_regime_returns_safe_default(self):
        """Missing regime envelope returns SAFE_DEFAULT (HOLD frame)."""
        ctx = make_ctx(regime=OperationalRegime.INFORM, discourse_act=DiscourseAct.EXPLANATION)
        ctx.p6_regime = None  # Remove regime envelope

        maybe_run_p10(ctx)
        frame = ctx.p10_acoustic

        # Should be SAFE_DEFAULT (HOLD/FLAT)
        assert frame.regime == AcousticRegime.FLAT
        assert frame.suppress_emotion is True
        assert frame.suppress_emphasis is True
        assert frame.suppress_certainty is True

        # All bounds still respected
        assert SPEECH_RATE_MIN <= frame.speech_rate <= SPEECH_RATE_MAX
        assert ENERGY_LEVEL_MIN <= frame.energy_level <= ENERGY_LEVEL_MAX

    def test_adversarial_missing_discourse_returns_safe_default(self):
        """Missing discourse envelope returns SAFE_DEFAULT (HOLD frame)."""
        ctx = make_ctx(regime=OperationalRegime.INFORM, discourse_act=DiscourseAct.EXPLANATION)
        ctx.p7_discourse_envelope = None  # Remove discourse envelope

        maybe_run_p10(ctx)
        frame = ctx.p10_acoustic

        # Should be SAFE_DEFAULT (HOLD/FLAT)
        assert frame.regime == AcousticRegime.FLAT
        assert frame.suppress_emotion is True
        assert frame.suppress_emphasis is True
        assert frame.suppress_certainty is True


# ============================================================================
# II. P10 REGIME DOMINANCE INVARIANTS (6+ tests)
# ============================================================================


class TestP10RegimeDominanceInvariants:
    """
    P10 must obey strict regime -> acoustic mapping rules.

    HOLD -> FLAT with all suppressions
    DE_ESCALATE -> SOFT with suppressions
    etc.
    """

    def test_hold_forces_flat_regime(self):
        """HOLD regime forces FLAT acoustic regime."""
        ctx = make_ctx(regime=OperationalRegime.HOLD, discourse_act=DiscourseAct.DEFERRAL)
        maybe_run_p10(ctx)
        frame = ctx.p10_acoustic

        assert frame.regime == AcousticRegime.FLAT

    def test_hold_forces_all_suppressions_true(self):
        """HOLD regime forces all suppressions to True."""
        ctx = make_ctx(regime=OperationalRegime.HOLD, discourse_act=DiscourseAct.DEFERRAL)
        maybe_run_p10(ctx)
        frame = ctx.p10_acoustic

        assert frame.suppress_emotion is True
        assert frame.suppress_emphasis is True
        assert frame.suppress_certainty is True

    def test_hold_forces_max_stressed_tokens_zero(self):
        """HOLD regime forces max_stressed_tokens to 0."""
        ctx = make_ctx(regime=OperationalRegime.HOLD, discourse_act=DiscourseAct.DEFERRAL)
        maybe_run_p10(ctx)
        frame = ctx.p10_acoustic

        assert frame.max_stressed_tokens == 0
        assert frame.emphasis_policy == EmphasisPolicy.NONE

    def test_de_escalate_forces_soft_regime(self):
        """DE_ESCALATE regime forces SOFT acoustic regime."""
        ctx = make_ctx(regime=OperationalRegime.DE_ESCALATE, discourse_act=DiscourseAct.REFLECTION)
        maybe_run_p10(ctx)
        frame = ctx.p10_acoustic

        assert frame.regime == AcousticRegime.SOFT

    def test_de_escalate_forces_suppressions(self):
        """DE_ESCALATE regime forces all suppressions to True."""
        ctx = make_ctx(regime=OperationalRegime.DE_ESCALATE, discourse_act=DiscourseAct.REFLECTION)
        maybe_run_p10(ctx)
        frame = ctx.p10_acoustic

        assert frame.suppress_emotion is True
        assert frame.suppress_emphasis is True
        assert frame.suppress_certainty is True

    def test_de_escalate_speech_rate_conservative(self):
        """DE_ESCALATE speech_rate <= INFORM speech_rate."""
        ctx_de_escalate = make_ctx(
            regime=OperationalRegime.DE_ESCALATE,
            discourse_act=DiscourseAct.ACKNOWLEDGMENT
        )
        maybe_run_p10(ctx_de_escalate)

        ctx_inform = make_ctx(
            regime=OperationalRegime.INFORM,
            discourse_act=DiscourseAct.EXPLANATION
        )
        maybe_run_p10(ctx_inform)

        assert ctx_de_escalate.p10_acoustic.speech_rate <= ctx_inform.p10_acoustic.speech_rate

    def test_de_escalate_energy_conservative(self):
        """DE_ESCALATE energy_level <= INFORM energy_level."""
        ctx_de_escalate = make_ctx(
            regime=OperationalRegime.DE_ESCALATE,
            discourse_act=DiscourseAct.ACKNOWLEDGMENT
        )
        maybe_run_p10(ctx_de_escalate)

        ctx_inform = make_ctx(
            regime=OperationalRegime.INFORM,
            discourse_act=DiscourseAct.EXPLANATION
        )
        maybe_run_p10(ctx_inform)

        assert ctx_de_escalate.p10_acoustic.energy_level <= ctx_inform.p10_acoustic.energy_level

    def test_inform_allows_limited_emphasis(self):
        """INFORM regime allows LIMITED emphasis under EXPLANATION."""
        ctx = make_ctx(regime=OperationalRegime.INFORM, discourse_act=DiscourseAct.EXPLANATION)
        maybe_run_p10(ctx)
        frame = ctx.p10_acoustic

        assert frame.emphasis_policy == EmphasisPolicy.LIMITED
        assert frame.max_stressed_tokens == 1
        assert frame.suppress_emphasis is False


# ============================================================================
# III. P10 DISCOURSE OVERRIDES (6+ tests)
# ============================================================================


class TestP10DiscourseOverrides:
    """
    P10 must apply discourse-specific overrides correctly.
    """

    def test_reflection_forces_max_stressed_tokens_zero(self):
        """REFLECTION discourse act forces max_stressed_tokens = 0."""
        ctx = make_ctx(regime=OperationalRegime.INFORM, discourse_act=DiscourseAct.REFLECTION)
        maybe_run_p10(ctx)
        frame = ctx.p10_acoustic

        assert frame.max_stressed_tokens == 0
        assert frame.emphasis_policy == EmphasisPolicy.NONE

    def test_reflection_override_regardless_of_regime(self):
        """REFLECTION forces no stress even under CLARIFY."""
        ctx = make_ctx(regime=OperationalRegime.CLARIFY, discourse_act=DiscourseAct.REFLECTION)
        maybe_run_p10(ctx)
        frame = ctx.p10_acoustic

        assert frame.max_stressed_tokens == 0
        assert frame.emphasis_policy == EmphasisPolicy.NONE

    def test_deferral_forces_suppress_certainty(self):
        """DEFERRAL discourse act forces suppress_certainty = True."""
        ctx = make_ctx(regime=OperationalRegime.INFORM, discourse_act=DiscourseAct.DEFERRAL)
        maybe_run_p10(ctx)
        frame = ctx.p10_acoustic

        assert frame.suppress_certainty is True

    def test_deferral_under_clarify_still_suppresses_certainty(self):
        """DEFERRAL under CLARIFY still forces suppress_certainty = True."""
        ctx = make_ctx(regime=OperationalRegime.CLARIFY, discourse_act=DiscourseAct.DEFERRAL)
        maybe_run_p10(ctx)
        frame = ctx.p10_acoustic

        assert frame.suppress_certainty is True

    def test_question_under_hold_no_emphasis(self):
        """QUESTION under HOLD regime has no emphasis."""
        ctx = make_ctx(regime=OperationalRegime.HOLD, discourse_act=DiscourseAct.QUESTION)
        maybe_run_p10(ctx)
        frame = ctx.p10_acoustic

        assert frame.max_stressed_tokens == 0
        assert frame.emphasis_policy == EmphasisPolicy.NONE

    def test_question_no_pitch_contour_fields(self):
        """QUESTION does not introduce pitch contour fields (schema-level)."""
        ctx = make_ctx(regime=OperationalRegime.INFORM, discourse_act=DiscourseAct.QUESTION)
        maybe_run_p10(ctx)
        frame = ctx.p10_acoustic

        # P10 should not have contour fields - verify it's a valid AcousticParameterFrame
        # with only the defined fields
        frame_dict = frame.to_dict()
        assert "pitch_contour" not in frame_dict
        assert "intonation_pattern" not in frame_dict
        assert "pitch_rise" not in frame_dict

    def test_acknowledgment_forces_no_emphasis(self):
        """ACKNOWLEDGMENT forces max_stressed_tokens = 0."""
        ctx = make_ctx(regime=OperationalRegime.INFORM, discourse_act=DiscourseAct.ACKNOWLEDGMENT)
        maybe_run_p10(ctx)
        frame = ctx.p10_acoustic

        assert frame.max_stressed_tokens == 0
        assert frame.emphasis_policy == EmphasisPolicy.NONE

    def test_instruction_under_hold_no_emphasis(self):
        """INSTRUCTION under restrictive regimes has no emphasis."""
        ctx = make_ctx(regime=OperationalRegime.HOLD, discourse_act=DiscourseAct.INSTRUCTION)
        maybe_run_p10(ctx)
        frame = ctx.p10_acoustic

        assert frame.max_stressed_tokens == 0
        assert frame.emphasis_policy == EmphasisPolicy.NONE


# ============================================================================
# IV. P10 DETERMINISM INVARIANTS (4+ tests)
# ============================================================================


class TestP10DeterminismInvariants:
    """
    P10 must be fully deterministic: same input -> same output.
    """

    def test_same_ctx_produces_identical_frame_twice(self):
        """Running P10 twice on same context produces identical frames."""
        ctx1 = make_ctx(regime=OperationalRegime.INFORM, discourse_act=DiscourseAct.EXPLANATION)
        ctx2 = make_ctx(regime=OperationalRegime.INFORM, discourse_act=DiscourseAct.EXPLANATION)

        maybe_run_p10(ctx1)
        maybe_run_p10(ctx2)

        assert ctx1.p10_acoustic.to_dict() == ctx2.p10_acoustic.to_dict()

    def test_reset_and_rerun_produces_identical_frame(self):
        """Resetting p10_acoustic and rerunning produces identical frame."""
        ctx = make_ctx(regime=OperationalRegime.DE_ESCALATE, discourse_act=DiscourseAct.REFLECTION)
        maybe_run_p10(ctx)
        first_frame = ctx.p10_acoustic

        # Reset and rerun
        ctx.p10_acoustic = None
        maybe_run_p10(ctx)
        second_frame = ctx.p10_acoustic

        # Compare all fields (excluding debug which may have different references)
        assert first_frame.regime == second_frame.regime
        assert first_frame.speech_rate == second_frame.speech_rate
        assert first_frame.energy_level == second_frame.energy_level
        assert first_frame.pitch_range == second_frame.pitch_range
        assert first_frame.pause_policy == second_frame.pause_policy
        assert first_frame.pause_duration_ms == second_frame.pause_duration_ms
        assert first_frame.emphasis_policy == second_frame.emphasis_policy
        assert first_frame.max_stressed_tokens == second_frame.max_stressed_tokens
        assert first_frame.suppress_emotion == second_frame.suppress_emotion
        assert first_frame.suppress_emphasis == second_frame.suppress_emphasis
        assert first_frame.suppress_certainty == second_frame.suppress_certainty

    def test_run_directly_deterministic(self):
        """run_p10_directly is deterministic."""
        ctx1 = make_ctx(regime=OperationalRegime.REFLECT, discourse_act=DiscourseAct.REFLECTION)
        ctx2 = make_ctx(regime=OperationalRegime.REFLECT, discourse_act=DiscourseAct.REFLECTION)

        frame1 = run_p10_directly(
            lexical_frame=ctx1.lexical_frame,
            discourse_envelope=ctx1.p7_discourse_envelope,
            regime_envelope=ctx1.p6_regime,
        )
        frame2 = run_p10_directly(
            lexical_frame=ctx2.lexical_frame,
            discourse_envelope=ctx2.p7_discourse_envelope,
            regime_envelope=ctx2.p6_regime,
        )

        assert frame1.to_dict() == frame2.to_dict()

    def test_all_regimes_deterministic(self):
        """All regime mappings are deterministic."""
        regimes = [
            OperationalRegime.HOLD,
            OperationalRegime.DE_ESCALATE,
            OperationalRegime.STABILIZE,
            OperationalRegime.REFLECT,
            OperationalRegime.INFORM,
            OperationalRegime.CLARIFY,
        ]

        for regime in regimes:
            ctx1 = make_ctx(regime=regime, discourse_act=DiscourseAct.EXPLANATION)
            ctx2 = make_ctx(regime=regime, discourse_act=DiscourseAct.EXPLANATION)

            maybe_run_p10(ctx1)
            maybe_run_p10(ctx2)

            assert ctx1.p10_acoustic.to_dict() == ctx2.p10_acoustic.to_dict(), \
                f"Determinism failed for regime {regime.value}"


# ============================================================================
# V. P10 NON-MUTATION OF LEXICAL (3+ tests)
# ============================================================================


class TestP10NonMutationOfLexical:
    """
    P10 must never mutate lexical output from P9.
    """

    def test_lexical_frame_unchanged_after_p10(self):
        """Lexical frame object is unchanged after P10."""
        lexical_selections = {
            SemanticSlot.AGENT: "I",
            SemanticSlot.STATE: "sad",
            SemanticSlot.UNCERTAINTY: "maybe",
        }
        ctx = make_ctx(
            regime=OperationalRegime.INFORM,
            discourse_act=DiscourseAct.EXPLANATION,
            lexical_selections=lexical_selections,
        )

        # Deep copy before P10
        lexical_before = json.dumps(ctx.lexical_frame.to_dict(), sort_keys=True)

        maybe_run_p10(ctx)

        # Compare after P10
        lexical_after = json.dumps(ctx.lexical_frame.to_dict(), sort_keys=True)
        assert lexical_before == lexical_after

    def test_lexical_selections_order_unchanged(self):
        """Order of lexical_items (selections) unchanged after P10."""
        lexical_selections = {
            SemanticSlot.AGENT: "you",
            SemanticSlot.STATE: "understand",
            SemanticSlot.UNCERTAINTY: "certainly",
        }
        ctx = make_ctx(
            regime=OperationalRegime.DE_ESCALATE,
            discourse_act=DiscourseAct.REFLECTION,
            lexical_selections=lexical_selections,
        )

        selections_before = list(ctx.lexical_frame.selections.items())

        maybe_run_p10(ctx)

        selections_after = list(ctx.lexical_frame.selections.items())
        assert selections_before == selections_after

    def test_no_new_lexical_items_introduced(self):
        """No new lexical items are introduced by P10."""
        lexical_selections = {
            SemanticSlot.AGENT: "we",
        }
        ctx = make_ctx(
            regime=OperationalRegime.INFORM,
            discourse_act=DiscourseAct.EXPLANATION,
            lexical_selections=lexical_selections,
        )

        count_before = len(ctx.lexical_frame.selections)

        maybe_run_p10(ctx)

        count_after = len(ctx.lexical_frame.selections)
        assert count_before == count_after

    def test_lexical_identity_preserved_across_regimes(self):
        """Lexical frame identity preserved regardless of regime."""
        lexical_selections = {
            SemanticSlot.AGENT: "I",
            SemanticSlot.STATE: "feel",
        }

        for regime in [OperationalRegime.HOLD, OperationalRegime.INFORM, OperationalRegime.CLARIFY]:
            ctx = make_ctx(
                regime=regime,
                discourse_act=DiscourseAct.EXPLANATION,
                lexical_selections=lexical_selections,
            )

            lexical_id_before = id(ctx.lexical_frame)
            selections_before = dict(ctx.lexical_frame.selections)

            maybe_run_p10(ctx)

            assert id(ctx.lexical_frame) == lexical_id_before
            assert ctx.lexical_frame.selections == selections_before


# ============================================================================
# VI. P11 COPY-EXACT INVARIANTS (8+ tests)
# ============================================================================


class TestP11CopyExactInvariants:
    """
    P11 must copy every acoustic parameter exactly from P10.
    """

    def test_speech_rate_copied_exactly(self):
        """P11 speech_rate equals P10 speech_rate."""
        ctx = make_ctx(regime=OperationalRegime.INFORM, discourse_act=DiscourseAct.EXPLANATION)
        maybe_run_p10(ctx)
        maybe_run_p11(ctx)

        assert ctx.p11_prosodic_evidence.speech_rate == ctx.p10_acoustic.speech_rate

    def test_energy_level_copied_exactly(self):
        """P11 energy_level equals P10 energy_level."""
        ctx = make_ctx(regime=OperationalRegime.DE_ESCALATE, discourse_act=DiscourseAct.REFLECTION)
        maybe_run_p10(ctx)
        maybe_run_p11(ctx)

        assert ctx.p11_prosodic_evidence.energy_level == ctx.p10_acoustic.energy_level

    def test_pitch_range_copied_exactly(self):
        """P11 pitch_range equals P10 pitch_range."""
        ctx = make_ctx(regime=OperationalRegime.HOLD, discourse_act=DiscourseAct.DEFERRAL)
        maybe_run_p10(ctx)
        maybe_run_p11(ctx)

        assert ctx.p11_prosodic_evidence.pitch_range == ctx.p10_acoustic.pitch_range

    def test_pause_policy_copied_exactly(self):
        """P11 pause_policy equals P10 pause_policy value."""
        ctx = make_ctx(regime=OperationalRegime.INFORM, discourse_act=DiscourseAct.EXPLANATION)
        maybe_run_p10(ctx)
        maybe_run_p11(ctx)

        assert ctx.p11_prosodic_evidence.pause_policy == ctx.p10_acoustic.pause_policy.value

    def test_pause_duration_ms_copied_exactly(self):
        """P11 pause_duration_ms equals P10 pause_duration_ms."""
        ctx = make_ctx(regime=OperationalRegime.STABILIZE, discourse_act=DiscourseAct.ACKNOWLEDGMENT)
        maybe_run_p10(ctx)
        maybe_run_p11(ctx)

        assert ctx.p11_prosodic_evidence.pause_duration_ms == ctx.p10_acoustic.pause_duration_ms

    def test_emphasis_policy_copied_exactly(self):
        """P11 emphasis_policy equals P10 emphasis_policy value."""
        ctx = make_ctx(regime=OperationalRegime.CLARIFY, discourse_act=DiscourseAct.QUESTION)
        maybe_run_p10(ctx)
        maybe_run_p11(ctx)

        assert ctx.p11_prosodic_evidence.emphasis_policy == ctx.p10_acoustic.emphasis_policy.value

    def test_max_stressed_tokens_copied_exactly(self):
        """P11 max_stressed_tokens equals P10 max_stressed_tokens."""
        ctx = make_ctx(regime=OperationalRegime.INFORM, discourse_act=DiscourseAct.EXPLANATION)
        maybe_run_p10(ctx)
        maybe_run_p11(ctx)

        assert ctx.p11_prosodic_evidence.max_stressed_tokens == ctx.p10_acoustic.max_stressed_tokens

    def test_all_suppressions_copied_exactly(self):
        """All suppression flags copied exactly from P10."""
        ctx = make_ctx(regime=OperationalRegime.HOLD, discourse_act=DiscourseAct.DEFERRAL)
        maybe_run_p10(ctx)
        maybe_run_p11(ctx)

        assert ctx.p11_prosodic_evidence.suppress_emotion == ctx.p10_acoustic.suppress_emotion
        assert ctx.p11_prosodic_evidence.suppress_emphasis == ctx.p10_acoustic.suppress_emphasis
        assert ctx.p11_prosodic_evidence.suppress_certainty == ctx.p10_acoustic.suppress_certainty

    def test_source_regime_matches_ctx(self):
        """P11 source_regime matches context."""
        ctx = make_ctx(regime=OperationalRegime.REFLECT, discourse_act=DiscourseAct.REFLECTION)
        maybe_run_p10(ctx)
        maybe_run_p11(ctx)

        assert ctx.p11_prosodic_evidence.source_regime == ctx.p10_acoustic.source_regime
        assert ctx.p11_prosodic_evidence.source_regime == "REFLECT"

    def test_source_discourse_act_matches_ctx(self):
        """P11 source_discourse_act matches context."""
        ctx = make_ctx(regime=OperationalRegime.INFORM, discourse_act=DiscourseAct.INSTRUCTION)
        maybe_run_p10(ctx)
        maybe_run_p11(ctx)

        assert ctx.p11_prosodic_evidence.source_discourse_act == ctx.p10_acoustic.source_discourse_act
        assert ctx.p11_prosodic_evidence.source_discourse_act == "INSTRUCTION"

    def test_source_intent_from_phase_zero(self):
        """P11 source_intent comes from phase_zero when present."""
        ctx = make_ctx(
            regime=OperationalRegime.INFORM,
            discourse_act=DiscourseAct.EXPLANATION,
            intent=IntentType.INFORM,
            include_phase_zero=True,
        )
        maybe_run_p10(ctx)
        maybe_run_p11(ctx)

        assert ctx.p11_prosodic_evidence.source_intent == "INFORM"


# ============================================================================
# VII. P11 MUST NOT MUTATE P10 (3+ tests)
# ============================================================================


class TestP11MustNotMutateP10:
    """
    P11 must never mutate the P10 acoustic frame.
    """

    def test_p10_frame_unchanged_after_p11(self):
        """P10 frame is identical before and after P11."""
        ctx = make_ctx(regime=OperationalRegime.INFORM, discourse_act=DiscourseAct.EXPLANATION)
        maybe_run_p10(ctx)

        # Capture P10 frame state before P11
        p10_before = ctx.p10_acoustic.to_dict()

        maybe_run_p11(ctx)

        # Compare after P11
        p10_after = ctx.p10_acoustic.to_dict()
        assert p10_before == p10_after

    def test_p10_frame_identity_preserved(self):
        """P10 frame object identity is preserved after P11."""
        ctx = make_ctx(regime=OperationalRegime.DE_ESCALATE, discourse_act=DiscourseAct.REFLECTION)
        maybe_run_p10(ctx)

        p10_id_before = id(ctx.p10_acoustic)

        maybe_run_p11(ctx)

        assert id(ctx.p10_acoustic) == p10_id_before

    def test_p10_frame_equals_original_after_p11(self):
        """Deep comparison of P10 frame before and after P11."""
        ctx = make_ctx(regime=OperationalRegime.HOLD, discourse_act=DiscourseAct.DEFERRAL)
        maybe_run_p10(ctx)

        # Deep copy before P11
        p10_speech_rate = ctx.p10_acoustic.speech_rate
        p10_energy_level = ctx.p10_acoustic.energy_level
        p10_pitch_range = ctx.p10_acoustic.pitch_range
        p10_regime = ctx.p10_acoustic.regime
        p10_pause_policy = ctx.p10_acoustic.pause_policy
        p10_emphasis_policy = ctx.p10_acoustic.emphasis_policy
        p10_max_stressed = ctx.p10_acoustic.max_stressed_tokens

        maybe_run_p11(ctx)

        # Verify all values unchanged
        assert ctx.p10_acoustic.speech_rate == p10_speech_rate
        assert ctx.p10_acoustic.energy_level == p10_energy_level
        assert ctx.p10_acoustic.pitch_range == p10_pitch_range
        assert ctx.p10_acoustic.regime == p10_regime
        assert ctx.p10_acoustic.pause_policy == p10_pause_policy
        assert ctx.p10_acoustic.emphasis_policy == p10_emphasis_policy
        assert ctx.p10_acoustic.max_stressed_tokens == p10_max_stressed

    def test_multiple_p11_runs_do_not_mutate_p10(self):
        """Running P11 multiple times does not mutate P10."""
        ctx = make_ctx(regime=OperationalRegime.STABILIZE, discourse_act=DiscourseAct.ACKNOWLEDGMENT)
        maybe_run_p10(ctx)

        p10_dict = ctx.p10_acoustic.to_dict()

        # Run P11 multiple times (though idempotent, verify no mutation)
        maybe_run_p11(ctx)
        assert ctx.p10_acoustic.to_dict() == p10_dict

        # Reset and run again
        ctx.p11_prosodic_evidence = None
        maybe_run_p11(ctx)
        assert ctx.p10_acoustic.to_dict() == p10_dict


# ============================================================================
# VIII. P11 INVARIANT_CHECKS COMPLETENESS + ACCURACY (6+ tests)
# ============================================================================


class TestP11InvariantChecksCompleteness:
    """
    P11 invariant_checks must be complete (all required keys present).
    """

    REQUIRED_INVARIANT_KEYS = frozenset([
        "no_emotion_amplification",
        "no_certainty_injection",
        "no_emphasis_override",
        "pitch_within_bounds",
        "energy_within_bounds",
        "speech_rate_within_bounds",
        "pause_policy_respected",
        "lexical_integrity_preserved",
        "regime_constraints_respected",
    ])

    def test_all_required_invariant_keys_present(self):
        """All required invariant check keys are present."""
        ctx = make_ctx(regime=OperationalRegime.INFORM, discourse_act=DiscourseAct.EXPLANATION)
        maybe_run_p10(ctx)
        maybe_run_p11(ctx)

        checks = ctx.p11_prosodic_evidence.invariant_checks
        for key in self.REQUIRED_INVARIANT_KEYS:
            assert key in checks, f"Missing required invariant key: {key}"

    def test_no_extra_invariant_keys(self):
        """No unexpected invariant keys are present."""
        ctx = make_ctx(regime=OperationalRegime.HOLD, discourse_act=DiscourseAct.DEFERRAL)
        maybe_run_p10(ctx)
        maybe_run_p11(ctx)

        checks = ctx.p11_prosodic_evidence.invariant_checks
        for key in checks:
            assert key in self.REQUIRED_INVARIANT_KEYS, f"Unexpected invariant key: {key}"

    def test_all_invariant_values_are_boolean(self):
        """All invariant check values are boolean."""
        ctx = make_ctx(regime=OperationalRegime.DE_ESCALATE, discourse_act=DiscourseAct.REFLECTION)
        maybe_run_p10(ctx)
        maybe_run_p11(ctx)

        checks = ctx.p11_prosodic_evidence.invariant_checks
        for key, value in checks.items():
            assert isinstance(value, bool), f"Invariant {key} value is not bool: {type(value)}"


class TestP11InvariantChecksAccuracy:
    """
    P11 invariant_checks must be accurate (correct True/False values).
    """

    def test_safe_default_all_invariants_pass(self):
        """SAFE_DEFAULT (HOLD) frame yields all True invariants."""
        ctx = make_ctx(regime=OperationalRegime.HOLD, discourse_act=DiscourseAct.DEFERRAL)
        maybe_run_p10(ctx)
        maybe_run_p11(ctx)

        checks = ctx.p11_prosodic_evidence.invariant_checks
        for key, value in checks.items():
            assert value is True, f"Invariant {key} should be True for SAFE_DEFAULT"
        assert ctx.p11_prosodic_evidence.violations_detected is False

    def test_de_escalate_all_invariants_pass(self):
        """DE_ESCALATE frame yields all True invariants."""
        ctx = make_ctx(regime=OperationalRegime.DE_ESCALATE, discourse_act=DiscourseAct.REFLECTION)
        maybe_run_p10(ctx)
        maybe_run_p11(ctx)

        checks = ctx.p11_prosodic_evidence.invariant_checks
        for key, value in checks.items():
            assert value is True, f"Invariant {key} should be True for DE_ESCALATE"
        assert ctx.p11_prosodic_evidence.violations_detected is False

    def test_corrupt_frame_emotion_suppression_violation(self):
        """Corrupt P10 frame with suppress_emotion=False under HOLD detected."""
        ctx = make_ctx(regime=OperationalRegime.HOLD, discourse_act=DiscourseAct.DEFERRAL)

        # Create corrupt acoustic frame directly
        corrupt_frame = AcousticParameterFrame(
            regime=AcousticRegime.FLAT,
            speech_rate=3.5,
            energy_level=0.25,
            pitch_range=(95, 105),
            pause_policy=PausePolicy.NORMAL,
            pause_duration_ms=(150, 250),
            emphasis_policy=EmphasisPolicy.NONE,
            max_stressed_tokens=0,
            suppress_emotion=False,  # VIOLATION: Should be True for HOLD
            suppress_emphasis=True,
            suppress_certainty=True,
            source_regime="HOLD",
            source_discourse_act="DEFERRAL",
        )
        ctx.p10_acoustic = corrupt_frame

        maybe_run_p11(ctx)

        assert ctx.p11_prosodic_evidence.violations_detected is True
        assert ctx.p11_prosodic_evidence.invariant_checks["no_emotion_amplification"] is False

    def test_corrupt_frame_certainty_suppression_violation(self):
        """Corrupt P10 frame with suppress_certainty=False under HOLD detected."""
        ctx = make_ctx(regime=OperationalRegime.HOLD, discourse_act=DiscourseAct.DEFERRAL)

        corrupt_frame = AcousticParameterFrame(
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
            suppress_certainty=False,  # VIOLATION: Should be True for HOLD
            source_regime="HOLD",
            source_discourse_act="DEFERRAL",
        )
        ctx.p10_acoustic = corrupt_frame

        maybe_run_p11(ctx)

        assert ctx.p11_prosodic_evidence.violations_detected is True
        assert ctx.p11_prosodic_evidence.invariant_checks["no_certainty_injection"] is False

    def test_corrupt_frame_regime_constraint_violation(self):
        """Corrupt P10 frame with wrong acoustic regime detected."""
        ctx = make_ctx(regime=OperationalRegime.HOLD, discourse_act=DiscourseAct.DEFERRAL)

        # HOLD should be FLAT, but we inject NEUTRAL (violation)
        corrupt_frame = AcousticParameterFrame(
            regime=AcousticRegime.NEUTRAL,  # VIOLATION: Should be FLAT for HOLD
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
            source_discourse_act="DEFERRAL",
        )
        ctx.p10_acoustic = corrupt_frame

        maybe_run_p11(ctx)

        assert ctx.p11_prosodic_evidence.violations_detected is True
        assert ctx.p11_prosodic_evidence.invariant_checks["regime_constraints_respected"] is False

    def test_p11_does_not_fix_violations(self):
        """P11 records violations but does NOT fix them."""
        ctx = make_ctx(regime=OperationalRegime.HOLD, discourse_act=DiscourseAct.DEFERRAL)

        # Create corrupt frame
        corrupt_frame = AcousticParameterFrame(
            regime=AcousticRegime.FLAT,
            speech_rate=3.5,
            energy_level=0.25,
            pitch_range=(95, 105),
            pause_policy=PausePolicy.NORMAL,
            pause_duration_ms=(150, 250),
            emphasis_policy=EmphasisPolicy.NONE,
            max_stressed_tokens=0,
            suppress_emotion=False,  # VIOLATION
            suppress_emphasis=False,  # VIOLATION
            suppress_certainty=False,  # VIOLATION
            source_regime="HOLD",
            source_discourse_act="DEFERRAL",
        )
        ctx.p10_acoustic = corrupt_frame

        maybe_run_p11(ctx)

        # P11 should record violations
        assert ctx.p11_prosodic_evidence.violations_detected is True

        # P11 should NOT fix anything - the evidence frame copies the corrupt values
        assert ctx.p11_prosodic_evidence.suppress_emotion is False
        assert ctx.p11_prosodic_evidence.suppress_emphasis is False
        assert ctx.p11_prosodic_evidence.suppress_certainty is False

        # And the P10 frame is unchanged
        assert ctx.p10_acoustic.suppress_emotion is False
        assert ctx.p10_acoustic.suppress_emphasis is False
        assert ctx.p10_acoustic.suppress_certainty is False


# ============================================================================
# IX. P11 DETERMINISM (2+ tests)
# ============================================================================


class TestP11Determinism:
    """
    P11 must be deterministic (same input -> same output, ignoring timestamp).
    """

    def test_same_ctx_produces_identical_evidence_except_timestamp(self):
        """Same context produces identical evidence frame (except timestamp)."""
        with patch(
            'symbolu.mechanical.pipeline.p11_prosodic.p11_prosodic_resolver.datetime'
        ) as mock_datetime:
            mock_datetime.now.return_value.isoformat.return_value = "2024-01-01T00:00:00+00:00"
            mock_datetime.timezone = __import__('datetime').timezone

            ctx1 = make_ctx(regime=OperationalRegime.INFORM, discourse_act=DiscourseAct.EXPLANATION)
            maybe_run_p10(ctx1)
            maybe_run_p11(ctx1)

            ctx2 = make_ctx(regime=OperationalRegime.INFORM, discourse_act=DiscourseAct.EXPLANATION)
            maybe_run_p10(ctx2)
            maybe_run_p11(ctx2)

            # Compare all fields
            ev1 = ctx1.p11_prosodic_evidence
            ev2 = ctx2.p11_prosodic_evidence

            assert ev1.speech_rate == ev2.speech_rate
            assert ev1.energy_level == ev2.energy_level
            assert ev1.pitch_range == ev2.pitch_range
            assert ev1.pause_policy == ev2.pause_policy
            assert ev1.pause_duration_ms == ev2.pause_duration_ms
            assert ev1.emphasis_policy == ev2.emphasis_policy
            assert ev1.max_stressed_tokens == ev2.max_stressed_tokens
            assert ev1.suppress_emotion == ev2.suppress_emotion
            assert ev1.suppress_emphasis == ev2.suppress_emphasis
            assert ev1.suppress_certainty == ev2.suppress_certainty
            assert ev1.source_regime == ev2.source_regime
            assert ev1.source_discourse_act == ev2.source_discourse_act
            assert ev1.invariant_checks == ev2.invariant_checks
            assert ev1.violations_detected == ev2.violations_detected

    def test_invariant_checks_deterministic(self):
        """Invariant checks produce identical results for identical inputs."""
        ctx1 = make_ctx(regime=OperationalRegime.DE_ESCALATE, discourse_act=DiscourseAct.REFLECTION)
        ctx2 = make_ctx(regime=OperationalRegime.DE_ESCALATE, discourse_act=DiscourseAct.REFLECTION)

        maybe_run_p10(ctx1)
        maybe_run_p11(ctx1)

        maybe_run_p10(ctx2)
        maybe_run_p11(ctx2)

        assert ctx1.p11_prosodic_evidence.invariant_checks == ctx2.p11_prosodic_evidence.invariant_checks

    def test_timestamp_is_valid_iso_format(self):
        """P11 timestamp is a valid ISO-8601 string."""
        ctx = make_ctx(regime=OperationalRegime.INFORM, discourse_act=DiscourseAct.EXPLANATION)
        maybe_run_p10(ctx)
        maybe_run_p11(ctx)

        timestamp = ctx.p11_prosodic_evidence.timestamp_utc
        assert isinstance(timestamp, str)
        assert len(timestamp) > 0
        # Basic ISO-8601 format check
        assert "T" in timestamp or "-" in timestamp


# ============================================================================
# ADDITIONAL GOVERNANCE TESTS
# ============================================================================


class TestP11AbsenceSafety:
    """
    P11 must handle absence of P10 safely.
    """

    def test_no_p10_returns_none(self):
        """P11 returns None when P10 is missing."""
        ctx = make_ctx(regime=OperationalRegime.INFORM, discourse_act=DiscourseAct.EXPLANATION)
        # Do NOT run P10

        maybe_run_p11(ctx)

        assert ctx.p11_prosodic_evidence is None

    def test_missing_p10_attribute_returns_none(self):
        """P11 returns None when p10_acoustic attribute is missing."""
        ctx = MinimalPipelineContext()  # No p10_acoustic attribute set

        result = run_p11_directly(ctx)

        assert result is None


class TestP10P11EndToEndIntegration:
    """
    End-to-end integration tests for P10 -> P11 flow.
    """

    def test_full_pipeline_hold_regime(self):
        """Full P10 -> P11 pipeline for HOLD regime."""
        ctx = make_ctx(regime=OperationalRegime.HOLD, discourse_act=DiscourseAct.DEFERRAL)
        maybe_run_p10(ctx)
        maybe_run_p11(ctx)

        # Verify complete chain
        assert ctx.p10_acoustic is not None
        assert ctx.p11_prosodic_evidence is not None
        assert ctx.p10_acoustic.regime == AcousticRegime.FLAT
        assert ctx.p11_prosodic_evidence.violations_detected is False
        assert ctx.p11_prosodic_evidence.is_fully_suppressed() is True

    def test_full_pipeline_inform_regime(self):
        """Full P10 -> P11 pipeline for INFORM regime."""
        ctx = make_ctx(regime=OperationalRegime.INFORM, discourse_act=DiscourseAct.EXPLANATION)
        maybe_run_p10(ctx)
        maybe_run_p11(ctx)

        # Verify complete chain
        assert ctx.p10_acoustic is not None
        assert ctx.p11_prosodic_evidence is not None
        assert ctx.p10_acoustic.regime == AcousticRegime.NEUTRAL
        assert ctx.p11_prosodic_evidence.violations_detected is False
        # INFORM allows emphasis, so not fully suppressed
        assert ctx.p10_acoustic.allows_emphasis() is True

    def test_all_regimes_pass_invariants(self):
        """All valid regime mappings pass all invariants."""
        regimes = [
            OperationalRegime.HOLD,
            OperationalRegime.DE_ESCALATE,
            OperationalRegime.STABILIZE,
            OperationalRegime.REFLECT,
            OperationalRegime.INFORM,
            OperationalRegime.CLARIFY,
        ]

        for regime in regimes:
            ctx = make_ctx(regime=regime, discourse_act=DiscourseAct.EXPLANATION)
            maybe_run_p10(ctx)
            maybe_run_p11(ctx)

            assert ctx.p11_prosodic_evidence.violations_detected is False, \
                f"Regime {regime.value} should not have violations"
