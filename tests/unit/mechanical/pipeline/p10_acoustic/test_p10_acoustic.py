"""
P10 Unit Tests

Tests for P10 Acoustic Parameterization Engine:
- AcousticParameterFrame dataclass
- Regime -> acoustic mappings
- P10AcousticResolver
- Integration with P6/P7/P9

Test Cases (per specification):
1. Each regime mapping (HOLD, DE_ESCALATE, STABILIZE, REFLECT, INFORM, CLARIFY)
2. Bound enforcement (speech_rate, energy, pitch, pause)
3. SAFE_DEFAULT fallback
4. REFLECTION suppression (max_stressed_tokens = 0)
5. HOLD dominance (most conservative)
6. Determinism (same inputs -> same output)
7. No lexical mutation
8. No emotion amplification
9. Discourse act overrides (DEFERRAL, QUESTION, etc.)
10. Parameter clamping

Target: ≥30 tests

CRITICAL ARCHITECTURAL INVARIANT:
    Sound must obey meaning.
    Meaning must never obey sound.
"""

import pytest
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
    clamp_speech_rate,
    clamp_energy_level,
    clamp_pitch,
    clamp_pause_duration,
    validate_pitch_range,
    validate_pause_range,
    HOLD_ACOUSTIC_CONFIG,
    DE_ESCALATE_ACOUSTIC_CONFIG,
    STABILIZE_ACOUSTIC_CONFIG,
    REFLECT_ACOUSTIC_CONFIG,
    INFORM_ACOUSTIC_CONFIG,
    CLARIFY_ACOUSTIC_CONFIG,
    REGIME_ACOUSTIC_MAP,
    SAFE_DEFAULT_CONFIG,
)
from symbolu.mechanical.pipeline.p10_acoustic.p10_integration import (
    get_p10_resolver,
    maybe_run_p10,
    run_p10_directly,
    get_p10_acoustic_frame,
    get_acoustic_regime,
    is_acoustic_frame_flat,
    is_acoustic_frame_suppressed,
    allows_emphasis,
    get_speech_rate,
    get_energy_level,
    get_pitch_range,
    get_pause_policy,
    get_pause_duration_range,
    get_max_stressed_tokens,
    is_emotion_suppressed,
    is_emphasis_suppressed,
    is_certainty_suppressed,
    get_source_regime,
    get_source_discourse_act,
)
from symbolu.mechanical.pipeline.p9_lexical.p9_lexical_schema import (
    LexicalFrame,
)
from symbolu.mechanical.pipeline.p8_semantics.p8_semantic_schema import (
    SemanticSlot,
)
from symbolu.mechanical.pipeline.p7_discourse.p7_discourse_schema import (
    DiscourseEnvelope,
    DiscourseAct,
)
from symbolu.mechanical.pipeline.phase_zero.phase_zero_schema import (
    IntentType,
)
from symbolu.mechanical.pipeline.phase_p6.p6_schema import (
    RegimeEnvelope,
    OperationalRegime,
)
from symbolu.mechanical.pipeline.phase_po5.po5_schema import ExecutionEligibility


# ============================================================================
# TEST HELPERS
# ============================================================================


def make_lexical_frame(
    selections: dict = None,
    allowed: bool = True,
    discourse_act: str = "EXPLANATION",
    regime: str = "INFORM",
) -> LexicalFrame:
    """Create a test LexicalFrame."""
    if selections is None:
        selections = {SemanticSlot.AGENT: "you"}
    return LexicalFrame(
        selections=selections,
        allowed=allowed,
        reason="Test lexical frame",
        source_discourse_act=discourse_act,
        source_regime=regime,
    )


def make_discourse_envelope(
    act: DiscourseAct = DiscourseAct.EXPLANATION,
    regime: OperationalRegime = OperationalRegime.INFORM,
    intent: IntentType = IntentType.INFORM,
) -> DiscourseEnvelope:
    """Create a test DiscourseEnvelope."""
    return DiscourseEnvelope(
        act=act,
        allowed=True,
        reason="Test discourse",
        intent=intent,
        regime=regime,
    )


def make_regime_envelope(
    regime: OperationalRegime = OperationalRegime.INFORM,
    intent: IntentType = IntentType.INFORM,
) -> RegimeEnvelope:
    """Create a test RegimeEnvelope."""
    return RegimeEnvelope(
        regime=regime,
        reason="Test regime",
        intent=intent,
        execution_eligibility=ExecutionEligibility.DEFERRED,
        coherence_regime="stable",
    )


# ============================================================================
# ACOUSTIC PARAMETER FRAME DATACLASS TESTS
# ============================================================================


class TestAcousticParameterFrame:
    """Tests for AcousticParameterFrame dataclass."""

    def test_basic_construction(self):
        """Test: basic frame construction."""
        frame = AcousticParameterFrame(
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
        assert frame.regime == AcousticRegime.NEUTRAL
        assert frame.architectural_phase == "P10"
        assert frame.speech_rate == 4.5

    def test_immutability(self):
        """Test: AcousticParameterFrame is frozen (immutable)."""
        frame = AcousticParameterFrame(
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
        with pytest.raises(Exception):  # FrozenInstanceError
            frame.speech_rate = 5.0

    def test_speech_rate_out_of_bounds_raises(self):
        """Test: speech rate out of bounds raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            AcousticParameterFrame(
                regime=AcousticRegime.NEUTRAL,
                speech_rate=10.0,  # Out of bounds
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
        assert "speech_rate" in str(exc_info.value)

    def test_speech_rate_below_minimum_raises(self):
        """Test: speech rate below minimum raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            AcousticParameterFrame(
                regime=AcousticRegime.NEUTRAL,
                speech_rate=1.0,  # Below minimum
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
        assert "speech_rate" in str(exc_info.value)

    def test_energy_level_out_of_bounds_raises(self):
        """Test: energy level out of bounds raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            AcousticParameterFrame(
                regime=AcousticRegime.NEUTRAL,
                speech_rate=4.5,
                energy_level=0.9,  # Out of bounds
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
        assert "energy_level" in str(exc_info.value)

    def test_pitch_range_out_of_bounds_raises(self):
        """Test: pitch range out of bounds raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            AcousticParameterFrame(
                regime=AcousticRegime.NEUTRAL,
                speech_rate=4.5,
                energy_level=0.45,
                pitch_range=(50, 200),  # Out of bounds
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
        assert "pitch_range" in str(exc_info.value)

    def test_pitch_range_inverted_raises(self):
        """Test: inverted pitch range raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            AcousticParameterFrame(
                regime=AcousticRegime.NEUTRAL,
                speech_rate=4.5,
                energy_level=0.45,
                pitch_range=(130, 100),  # Inverted
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
        assert "pitch_range" in str(exc_info.value)

    def test_pause_duration_out_of_bounds_raises(self):
        """Test: pause duration out of bounds raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            AcousticParameterFrame(
                regime=AcousticRegime.NEUTRAL,
                speech_rate=4.5,
                energy_level=0.45,
                pitch_range=(100, 130),
                pause_policy=PausePolicy.MINIMAL,
                pause_duration_ms=(50, 500),  # Out of bounds
                emphasis_policy=EmphasisPolicy.LIMITED,
                max_stressed_tokens=1,
                suppress_emotion=True,
                suppress_emphasis=False,
                suppress_certainty=False,
                source_regime="INFORM",
                source_discourse_act="EXPLANATION",
            )
        assert "pause_duration" in str(exc_info.value)

    def test_max_stressed_tokens_out_of_bounds_raises(self):
        """Test: max stressed tokens out of bounds raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            AcousticParameterFrame(
                regime=AcousticRegime.NEUTRAL,
                speech_rate=4.5,
                energy_level=0.45,
                pitch_range=(100, 130),
                pause_policy=PausePolicy.MINIMAL,
                pause_duration_ms=(100, 150),
                emphasis_policy=EmphasisPolicy.LIMITED,
                max_stressed_tokens=5,  # Out of bounds (max is 1)
                suppress_emotion=True,
                suppress_emphasis=False,
                suppress_certainty=False,
                source_regime="INFORM",
                source_discourse_act="EXPLANATION",
            )
        assert "max_stressed_tokens" in str(exc_info.value)

    def test_empty_source_regime_raises(self):
        """Test: empty source_regime raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            AcousticParameterFrame(
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
                source_regime="",  # Empty
                source_discourse_act="EXPLANATION",
            )
        assert "source_regime" in str(exc_info.value)

    def test_is_flat_regime(self):
        """Test: is_flat_regime correctly identifies FLAT regime."""
        flat_frame = AcousticParameterFrame(
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
        neutral_frame = AcousticParameterFrame(
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
        assert flat_frame.is_flat_regime() is True
        assert neutral_frame.is_flat_regime() is False

    def test_is_suppressed(self):
        """Test: is_suppressed correctly identifies fully suppressed frames."""
        suppressed_frame = AcousticParameterFrame(
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
        not_suppressed_frame = AcousticParameterFrame(
            regime=AcousticRegime.NEUTRAL,
            speech_rate=4.5,
            energy_level=0.45,
            pitch_range=(100, 130),
            pause_policy=PausePolicy.MINIMAL,
            pause_duration_ms=(100, 150),
            emphasis_policy=EmphasisPolicy.LIMITED,
            max_stressed_tokens=1,
            suppress_emotion=True,
            suppress_emphasis=False,  # Not suppressed
            suppress_certainty=False,
            source_regime="INFORM",
            source_discourse_act="EXPLANATION",
        )
        assert suppressed_frame.is_suppressed() is True
        assert not_suppressed_frame.is_suppressed() is False

    def test_allows_emphasis(self):
        """Test: allows_emphasis correctly identifies emphasis-allowed frames."""
        allows_frame = AcousticParameterFrame(
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
        no_emphasis_frame = AcousticParameterFrame(
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
        assert allows_frame.allows_emphasis() is True
        assert no_emphasis_frame.allows_emphasis() is False

    def test_to_dict(self):
        """Test: to_dict serialization."""
        frame = AcousticParameterFrame(
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
        d = frame.to_dict()
        assert d["architectural_phase"] == "P10"
        assert d["regime"] == "neutral"
        assert d["speech_rate"] == 4.5
        assert d["pitch_range"] == [100, 130]
        assert "is_flat_regime" in d
        assert "allows_emphasis" in d


# ============================================================================
# CLAMP FUNCTION TESTS
# ============================================================================


class TestClampFunctions:
    """Tests for parameter clamping functions."""

    def test_clamp_speech_rate_within_bounds(self):
        """Test: clamp_speech_rate returns value when in bounds."""
        assert clamp_speech_rate(4.0) == 4.0

    def test_clamp_speech_rate_below_minimum(self):
        """Test: clamp_speech_rate returns minimum when below."""
        assert clamp_speech_rate(1.0) == SPEECH_RATE_MIN

    def test_clamp_speech_rate_above_maximum(self):
        """Test: clamp_speech_rate returns maximum when above."""
        assert clamp_speech_rate(10.0) == SPEECH_RATE_MAX

    def test_clamp_energy_level_within_bounds(self):
        """Test: clamp_energy_level returns value when in bounds."""
        assert clamp_energy_level(0.4) == 0.4

    def test_clamp_energy_level_below_minimum(self):
        """Test: clamp_energy_level returns minimum when below."""
        assert clamp_energy_level(0.1) == ENERGY_LEVEL_MIN

    def test_clamp_energy_level_above_maximum(self):
        """Test: clamp_energy_level returns maximum when above."""
        assert clamp_energy_level(0.9) == ENERGY_LEVEL_MAX

    def test_clamp_pitch_within_bounds(self):
        """Test: clamp_pitch returns value when in bounds."""
        assert clamp_pitch(120) == 120

    def test_clamp_pitch_below_minimum(self):
        """Test: clamp_pitch returns minimum when below."""
        assert clamp_pitch(50) == PITCH_MIN

    def test_clamp_pitch_above_maximum(self):
        """Test: clamp_pitch returns maximum when above."""
        assert clamp_pitch(200) == PITCH_MAX

    def test_clamp_pause_duration_within_bounds(self):
        """Test: clamp_pause_duration returns value when in bounds."""
        assert clamp_pause_duration(200) == 200

    def test_clamp_pause_duration_below_minimum(self):
        """Test: clamp_pause_duration returns minimum when below."""
        assert clamp_pause_duration(50) == PAUSE_DURATION_MIN

    def test_clamp_pause_duration_above_maximum(self):
        """Test: clamp_pause_duration returns maximum when above."""
        assert clamp_pause_duration(500) == PAUSE_DURATION_MAX


# ============================================================================
# VALIDATE RANGE FUNCTION TESTS
# ============================================================================


class TestValidateRangeFunctions:
    """Tests for range validation functions."""

    def test_validate_pitch_range_valid(self):
        """Test: validate_pitch_range returns True for valid range."""
        assert validate_pitch_range((100, 130)) is True

    def test_validate_pitch_range_invalid_low(self):
        """Test: validate_pitch_range returns False for low out of bounds."""
        assert validate_pitch_range((50, 130)) is False

    def test_validate_pitch_range_invalid_high(self):
        """Test: validate_pitch_range returns False for high out of bounds."""
        assert validate_pitch_range((100, 200)) is False

    def test_validate_pitch_range_inverted(self):
        """Test: validate_pitch_range returns False for inverted range."""
        assert validate_pitch_range((130, 100)) is False

    def test_validate_pause_range_valid(self):
        """Test: validate_pause_range returns True for valid range."""
        assert validate_pause_range((100, 200)) is True

    def test_validate_pause_range_invalid(self):
        """Test: validate_pause_range returns False for out of bounds."""
        assert validate_pause_range((50, 500)) is False


# ============================================================================
# CONFIG CONSTANTS TESTS
# ============================================================================


class TestConfigConstants:
    """Tests for acoustic configuration constants."""

    def test_hold_acoustic_config_is_flat(self):
        """Test: HOLD config uses FLAT acoustic regime."""
        assert HOLD_ACOUSTIC_CONFIG["regime"] == AcousticRegime.FLAT

    def test_hold_acoustic_config_suppresses_all(self):
        """Test: HOLD config suppresses emotion, emphasis, and certainty."""
        assert HOLD_ACOUSTIC_CONFIG["suppress_emotion"] is True
        assert HOLD_ACOUSTIC_CONFIG["suppress_emphasis"] is True
        assert HOLD_ACOUSTIC_CONFIG["suppress_certainty"] is True

    def test_hold_acoustic_config_no_emphasis(self):
        """Test: HOLD config has no emphasis."""
        assert HOLD_ACOUSTIC_CONFIG["max_stressed_tokens"] == 0
        assert HOLD_ACOUSTIC_CONFIG["emphasis_policy"] == EmphasisPolicy.NONE

    def test_inform_acoustic_config_is_neutral(self):
        """Test: INFORM config uses NEUTRAL acoustic regime."""
        assert INFORM_ACOUSTIC_CONFIG["regime"] == AcousticRegime.NEUTRAL

    def test_inform_acoustic_config_allows_limited_emphasis(self):
        """Test: INFORM config allows limited emphasis."""
        assert INFORM_ACOUSTIC_CONFIG["max_stressed_tokens"] == 1
        assert INFORM_ACOUSTIC_CONFIG["emphasis_policy"] == EmphasisPolicy.LIMITED

    def test_de_escalate_acoustic_config_is_soft(self):
        """Test: DE_ESCALATE config uses SOFT acoustic regime."""
        assert DE_ESCALATE_ACOUSTIC_CONFIG["regime"] == AcousticRegime.SOFT

    def test_stabilize_acoustic_config_is_soft(self):
        """Test: STABILIZE config uses SOFT acoustic regime."""
        assert STABILIZE_ACOUSTIC_CONFIG["regime"] == AcousticRegime.SOFT

    def test_reflect_acoustic_config_is_soft(self):
        """Test: REFLECT config uses SOFT acoustic regime."""
        assert REFLECT_ACOUSTIC_CONFIG["regime"] == AcousticRegime.SOFT

    def test_clarify_acoustic_config_is_neutral(self):
        """Test: CLARIFY config uses NEUTRAL acoustic regime."""
        assert CLARIFY_ACOUSTIC_CONFIG["regime"] == AcousticRegime.NEUTRAL

    def test_safe_default_is_hold(self):
        """Test: SAFE_DEFAULT is the HOLD configuration."""
        assert SAFE_DEFAULT_CONFIG == HOLD_ACOUSTIC_CONFIG

    def test_all_regimes_in_map(self):
        """Test: all OperationalRegimes are in REGIME_ACOUSTIC_MAP."""
        for regime in OperationalRegime:
            assert regime in REGIME_ACOUSTIC_MAP


# ============================================================================
# P10 ACOUSTIC RESOLVER TESTS
# ============================================================================


class TestP10AcousticResolver:
    """Tests for P10AcousticResolver."""

    def test_resolver_initialization(self):
        """Test: resolver initializes without state."""
        resolver = P10AcousticResolver()
        assert resolver is not None

    def test_hold_regime_returns_flat_frame(self):
        """Test: HOLD regime returns FLAT acoustic frame."""
        resolver = P10AcousticResolver()

        lexical_frame = make_lexical_frame(
            selections={},
            discourse_act="DEFERRAL",
            regime="HOLD",
        )
        discourse = make_discourse_envelope(
            DiscourseAct.DEFERRAL, OperationalRegime.HOLD, IntentType.ABSTAIN
        )
        regime = make_regime_envelope(OperationalRegime.HOLD, IntentType.ABSTAIN)

        frame = resolver.resolve(
            lexical_frame=lexical_frame,
            discourse_envelope=discourse,
            regime_envelope=regime,
        )

        assert frame.regime == AcousticRegime.FLAT
        assert frame.is_flat_regime() is True
        assert frame.is_suppressed() is True

    def test_inform_regime_returns_neutral_frame(self):
        """Test: INFORM regime returns NEUTRAL acoustic frame."""
        resolver = P10AcousticResolver()

        lexical_frame = make_lexical_frame()
        discourse = make_discourse_envelope(
            DiscourseAct.EXPLANATION, OperationalRegime.INFORM, IntentType.INFORM
        )
        regime = make_regime_envelope(OperationalRegime.INFORM, IntentType.INFORM)

        frame = resolver.resolve(
            lexical_frame=lexical_frame,
            discourse_envelope=discourse,
            regime_envelope=regime,
        )

        assert frame.regime == AcousticRegime.NEUTRAL
        assert frame.allows_emphasis() is True

    def test_de_escalate_regime_returns_soft_frame(self):
        """Test: DE_ESCALATE regime returns SOFT acoustic frame."""
        resolver = P10AcousticResolver()

        lexical_frame = make_lexical_frame()
        discourse = make_discourse_envelope(
            DiscourseAct.ACKNOWLEDGMENT, OperationalRegime.DE_ESCALATE, IntentType.SUPPORT
        )
        regime = make_regime_envelope(OperationalRegime.DE_ESCALATE, IntentType.SUPPORT)

        frame = resolver.resolve(
            lexical_frame=lexical_frame,
            discourse_envelope=discourse,
            regime_envelope=regime,
        )

        assert frame.regime == AcousticRegime.SOFT

    def test_stabilize_regime_returns_soft_frame(self):
        """Test: STABILIZE regime returns SOFT acoustic frame."""
        resolver = P10AcousticResolver()

        lexical_frame = make_lexical_frame()
        discourse = make_discourse_envelope(
            DiscourseAct.EXPLANATION, OperationalRegime.STABILIZE, IntentType.INFORM
        )
        regime = make_regime_envelope(OperationalRegime.STABILIZE, IntentType.INFORM)

        frame = resolver.resolve(
            lexical_frame=lexical_frame,
            discourse_envelope=discourse,
            regime_envelope=regime,
        )

        assert frame.regime == AcousticRegime.SOFT

    def test_reflect_regime_returns_soft_frame(self):
        """Test: REFLECT regime returns SOFT acoustic frame."""
        resolver = P10AcousticResolver()

        lexical_frame = make_lexical_frame()
        discourse = make_discourse_envelope(
            DiscourseAct.REFLECTION, OperationalRegime.REFLECT, IntentType.SUPPORT
        )
        regime = make_regime_envelope(OperationalRegime.REFLECT, IntentType.SUPPORT)

        frame = resolver.resolve(
            lexical_frame=lexical_frame,
            discourse_envelope=discourse,
            regime_envelope=regime,
        )

        assert frame.regime == AcousticRegime.SOFT

    def test_clarify_regime_returns_neutral_frame(self):
        """Test: CLARIFY regime returns NEUTRAL acoustic frame."""
        resolver = P10AcousticResolver()

        lexical_frame = make_lexical_frame()
        discourse = make_discourse_envelope(
            DiscourseAct.QUESTION, OperationalRegime.CLARIFY, IntentType.CLARIFY
        )
        regime = make_regime_envelope(OperationalRegime.CLARIFY, IntentType.CLARIFY)

        frame = resolver.resolve(
            lexical_frame=lexical_frame,
            discourse_envelope=discourse,
            regime_envelope=regime,
        )

        assert frame.regime == AcousticRegime.NEUTRAL

    def test_missing_regime_envelope_returns_safe_default(self):
        """Test: missing regime_envelope returns SAFE_DEFAULT frame."""
        resolver = P10AcousticResolver()

        lexical_frame = make_lexical_frame()
        discourse = make_discourse_envelope()

        frame = resolver.resolve(
            lexical_frame=lexical_frame,
            discourse_envelope=discourse,
            regime_envelope=None,  # Missing
        )

        assert frame.regime == AcousticRegime.FLAT
        assert frame.debug.get("is_safe_default") is True

    def test_missing_discourse_envelope_returns_safe_default(self):
        """Test: missing discourse_envelope returns SAFE_DEFAULT frame."""
        resolver = P10AcousticResolver()

        lexical_frame = make_lexical_frame()
        regime = make_regime_envelope()

        frame = resolver.resolve(
            lexical_frame=lexical_frame,
            discourse_envelope=None,  # Missing
            regime_envelope=regime,
        )

        assert frame.regime == AcousticRegime.FLAT
        assert frame.debug.get("is_safe_default") is True

    def test_missing_lexical_frame_still_works(self):
        """Test: missing lexical_frame still produces valid frame."""
        resolver = P10AcousticResolver()

        discourse = make_discourse_envelope()
        regime = make_regime_envelope()

        frame = resolver.resolve(
            lexical_frame=None,  # Missing
            discourse_envelope=discourse,
            regime_envelope=regime,
        )

        # Should still produce valid frame (P10 doesn't require P9)
        assert frame is not None
        assert frame.regime == AcousticRegime.NEUTRAL

    def test_determinism_same_input_same_output(self):
        """Test: same inputs produce identical outputs (determinism)."""
        resolver = P10AcousticResolver()

        lexical_frame = make_lexical_frame()
        discourse = make_discourse_envelope()
        regime = make_regime_envelope()

        results = []
        for _ in range(10):
            frame = resolver.resolve(
                lexical_frame=lexical_frame,
                discourse_envelope=discourse,
                regime_envelope=regime,
            )
            results.append((
                frame.regime,
                frame.speech_rate,
                frame.energy_level,
                frame.pitch_range,
            ))

        # All results must be identical
        assert all(r == results[0] for r in results)

    def test_reflection_suppresses_emphasis(self):
        """Test: REFLECTION discourse act suppresses emphasis."""
        resolver = P10AcousticResolver()

        lexical_frame = make_lexical_frame()
        discourse = make_discourse_envelope(
            DiscourseAct.REFLECTION, OperationalRegime.REFLECT, IntentType.SUPPORT
        )
        regime = make_regime_envelope(OperationalRegime.REFLECT, IntentType.SUPPORT)

        frame = resolver.resolve(
            lexical_frame=lexical_frame,
            discourse_envelope=discourse,
            regime_envelope=regime,
        )

        # REFLECTION must have max_stressed_tokens = 0
        assert frame.max_stressed_tokens == 0
        assert frame.emphasis_policy == EmphasisPolicy.NONE

    def test_deferral_suppresses_certainty(self):
        """Test: DEFERRAL discourse act suppresses certainty."""
        resolver = P10AcousticResolver()

        lexical_frame = make_lexical_frame()
        discourse = make_discourse_envelope(
            DiscourseAct.DEFERRAL, OperationalRegime.STABILIZE, IntentType.ABSTAIN
        )
        regime = make_regime_envelope(OperationalRegime.STABILIZE, IntentType.ABSTAIN)

        frame = resolver.resolve(
            lexical_frame=lexical_frame,
            discourse_envelope=discourse,
            regime_envelope=regime,
        )

        # DEFERRAL must have suppress_certainty = True
        assert frame.suppress_certainty is True

    def test_question_under_hold_no_emphasis(self):
        """Test: QUESTION under HOLD has no emphasis."""
        resolver = P10AcousticResolver()

        lexical_frame = make_lexical_frame()
        discourse = make_discourse_envelope(
            DiscourseAct.QUESTION, OperationalRegime.HOLD, IntentType.CLARIFY
        )
        regime = make_regime_envelope(OperationalRegime.HOLD, IntentType.CLARIFY)

        frame = resolver.resolve(
            lexical_frame=lexical_frame,
            discourse_envelope=discourse,
            regime_envelope=regime,
        )

        assert frame.max_stressed_tokens == 0
        assert frame.emphasis_policy == EmphasisPolicy.NONE

    def test_acknowledgment_no_emphasis(self):
        """Test: ACKNOWLEDGMENT discourse has no emphasis."""
        resolver = P10AcousticResolver()

        lexical_frame = make_lexical_frame()
        discourse = make_discourse_envelope(
            DiscourseAct.ACKNOWLEDGMENT, OperationalRegime.DE_ESCALATE, IntentType.SUPPORT
        )
        regime = make_regime_envelope(OperationalRegime.DE_ESCALATE, IntentType.SUPPORT)

        frame = resolver.resolve(
            lexical_frame=lexical_frame,
            discourse_envelope=discourse,
            regime_envelope=regime,
        )

        assert frame.max_stressed_tokens == 0
        assert frame.emphasis_policy == EmphasisPolicy.NONE

    def test_instruction_under_inform_allows_emphasis(self):
        """Test: INSTRUCTION under INFORM allows emphasis."""
        resolver = P10AcousticResolver()

        lexical_frame = make_lexical_frame()
        discourse = make_discourse_envelope(
            DiscourseAct.INSTRUCTION, OperationalRegime.INFORM, IntentType.INFORM
        )
        regime = make_regime_envelope(OperationalRegime.INFORM, IntentType.INFORM)

        frame = resolver.resolve(
            lexical_frame=lexical_frame,
            discourse_envelope=discourse,
            regime_envelope=regime,
        )

        # INSTRUCTION under INFORM should allow limited emphasis
        assert frame.emphasis_policy == EmphasisPolicy.LIMITED
        assert frame.max_stressed_tokens == 1

    def test_instruction_under_stabilize_no_emphasis(self):
        """Test: INSTRUCTION under STABILIZE has no emphasis."""
        resolver = P10AcousticResolver()

        lexical_frame = make_lexical_frame()
        discourse = make_discourse_envelope(
            DiscourseAct.INSTRUCTION, OperationalRegime.STABILIZE, IntentType.INFORM
        )
        regime = make_regime_envelope(OperationalRegime.STABILIZE, IntentType.INFORM)

        frame = resolver.resolve(
            lexical_frame=lexical_frame,
            discourse_envelope=discourse,
            regime_envelope=regime,
        )

        assert frame.max_stressed_tokens == 0
        assert frame.emphasis_policy == EmphasisPolicy.NONE


# ============================================================================
# P10 INTEGRATION TESTS
# ============================================================================


class TestP10Integration:
    """Tests for P10 integration module."""

    def test_get_p10_resolver_singleton(self):
        """Test: get_p10_resolver returns singleton instance."""
        resolver1 = get_p10_resolver()
        resolver2 = get_p10_resolver()
        assert resolver1 is resolver2

    def test_run_p10_directly(self):
        """Test: run_p10_directly works with explicit inputs."""
        lexical_frame = make_lexical_frame()
        discourse = make_discourse_envelope()
        regime = make_regime_envelope()

        frame = run_p10_directly(
            lexical_frame=lexical_frame,
            discourse_envelope=discourse,
            regime_envelope=regime,
        )

        assert frame is not None
        assert isinstance(frame, AcousticParameterFrame)

    def test_maybe_run_p10_with_context(self):
        """Test: maybe_run_p10 works with mock context."""
        class MockContext:
            def __init__(self):
                self.lexical_frame = make_lexical_frame()
                self.p7_discourse_envelope = make_discourse_envelope()
                self.p6_regime = make_regime_envelope()
                self.p10_acoustic = None

        ctx = MockContext()
        maybe_run_p10(ctx)

        assert ctx.p10_acoustic is not None
        assert isinstance(ctx.p10_acoustic, AcousticParameterFrame)

    def test_maybe_run_p10_missing_all_produces_safe_default(self):
        """Test: maybe_run_p10 with all missing produces SAFE_DEFAULT."""
        class MockContext:
            def __init__(self):
                self.p10_acoustic = None
                # No lexical_frame, p7_discourse_envelope, or p6_regime

        ctx = MockContext()
        maybe_run_p10(ctx)

        # Should still produce a frame (SAFE_DEFAULT)
        assert ctx.p10_acoustic is not None
        assert ctx.p10_acoustic.regime == AcousticRegime.FLAT

    def test_get_p10_acoustic_frame(self):
        """Test: get_p10_acoustic_frame retrieves frame from context."""
        class MockContext:
            def __init__(self):
                self.p10_acoustic = AcousticParameterFrame(
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

        ctx = MockContext()
        frame = get_p10_acoustic_frame(ctx)

        assert frame is not None
        assert frame.regime == AcousticRegime.NEUTRAL

    def test_is_acoustic_frame_flat(self):
        """Test: is_acoustic_frame_flat checks for FLAT regime."""
        class MockContextFlat:
            def __init__(self):
                self.p10_acoustic = AcousticParameterFrame(
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

        class MockContextNeutral:
            def __init__(self):
                self.p10_acoustic = AcousticParameterFrame(
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

        assert is_acoustic_frame_flat(MockContextFlat()) is True
        assert is_acoustic_frame_flat(MockContextNeutral()) is False

    def test_allows_emphasis_integration(self):
        """Test: allows_emphasis checks emphasis permission."""
        class MockContextAllows:
            def __init__(self):
                self.p10_acoustic = AcousticParameterFrame(
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

        class MockContextNoEmphasis:
            def __init__(self):
                self.p10_acoustic = AcousticParameterFrame(
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

        assert allows_emphasis(MockContextAllows()) is True
        assert allows_emphasis(MockContextNoEmphasis()) is False

    def test_get_speech_rate(self):
        """Test: get_speech_rate returns correct value."""
        class MockContext:
            def __init__(self):
                self.p10_acoustic = AcousticParameterFrame(
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

        ctx = MockContext()
        assert get_speech_rate(ctx) == 4.5

    def test_get_energy_level(self):
        """Test: get_energy_level returns correct value."""
        class MockContext:
            def __init__(self):
                self.p10_acoustic = AcousticParameterFrame(
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

        ctx = MockContext()
        assert get_energy_level(ctx) == 0.45

    def test_get_pitch_range(self):
        """Test: get_pitch_range returns correct value."""
        class MockContext:
            def __init__(self):
                self.p10_acoustic = AcousticParameterFrame(
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

        ctx = MockContext()
        assert get_pitch_range(ctx) == (100, 130)

    def test_conservative_defaults_when_p10_not_run(self):
        """Test: conservative defaults when P10 hasn't run."""
        class MockContext:
            pass  # No p10_acoustic attribute

        ctx = MockContext()
        assert is_acoustic_frame_flat(ctx) is True  # Conservative
        assert is_acoustic_frame_suppressed(ctx) is True  # Conservative
        assert allows_emphasis(ctx) is False  # Conservative
        assert get_max_stressed_tokens(ctx) == 0  # Conservative


# ============================================================================
# NO LEXICAL MUTATION TESTS
# ============================================================================


class TestNoLexicalMutation:
    """Tests to verify P10 does not mutate lexical selections."""

    def test_lexical_frame_unchanged_after_p10(self):
        """Test: P10 does not modify the lexical frame."""
        resolver = P10AcousticResolver()

        original_selections = {SemanticSlot.AGENT: "you", SemanticSlot.STATE: "present"}
        lexical_frame = make_lexical_frame(selections=original_selections)
        discourse = make_discourse_envelope()
        regime = make_regime_envelope()

        # Capture original state
        original_count = lexical_frame.count()
        original_selection = lexical_frame.get_selection(SemanticSlot.AGENT)

        # Run P10
        frame = resolver.resolve(
            lexical_frame=lexical_frame,
            discourse_envelope=discourse,
            regime_envelope=regime,
        )

        # Verify lexical frame unchanged
        assert lexical_frame.count() == original_count
        assert lexical_frame.get_selection(SemanticSlot.AGENT) == original_selection

    def test_p10_does_not_add_words(self):
        """Test: P10 does not add any words to output."""
        resolver = P10AcousticResolver()

        lexical_frame = make_lexical_frame()
        discourse = make_discourse_envelope()
        regime = make_regime_envelope()

        frame = resolver.resolve(
            lexical_frame=lexical_frame,
            discourse_envelope=discourse,
            regime_envelope=regime,
        )

        # AcousticParameterFrame has no word-related attributes
        assert not hasattr(frame, 'words')
        assert not hasattr(frame, 'selections')
        assert not hasattr(frame, 'lexical')


# ============================================================================
# NO EMOTION AMPLIFICATION TESTS
# ============================================================================


class TestNoEmotionAmplification:
    """Tests to verify P10 does not amplify emotion."""

    def test_suppress_emotion_always_true(self):
        """Test: suppress_emotion is True in all configurations."""
        resolver = P10AcousticResolver()

        for regime_type in OperationalRegime:
            regime = make_regime_envelope(regime_type, IntentType.INFORM)
            discourse = make_discourse_envelope(
                DiscourseAct.EXPLANATION, regime_type, IntentType.INFORM
            )
            lexical_frame = make_lexical_frame()

            frame = resolver.resolve(
                lexical_frame=lexical_frame,
                discourse_envelope=discourse,
                regime_envelope=regime,
            )

            # suppress_emotion must always be True
            assert frame.suppress_emotion is True, \
                f"suppress_emotion should be True for regime {regime_type}"

    def test_no_emotion_inference_mechanism(self):
        """Test: P10 has no emotion inference mechanism."""
        resolver = P10AcousticResolver()

        # Even with "emotional" discourse, P10 doesn't infer emotion
        lexical_frame = make_lexical_frame()
        discourse = make_discourse_envelope(
            DiscourseAct.REFLECTION, OperationalRegime.REFLECT, IntentType.SUPPORT
        )
        regime = make_regime_envelope(OperationalRegime.REFLECT, IntentType.SUPPORT)

        frame = resolver.resolve(
            lexical_frame=lexical_frame,
            discourse_envelope=discourse,
            regime_envelope=regime,
        )

        # Frame has no emotion attribute
        assert not hasattr(frame, 'emotion')
        assert not hasattr(frame, 'inferred_emotion')
        assert frame.suppress_emotion is True


# ============================================================================
# BOUND ENFORCEMENT TESTS
# ============================================================================


class TestBoundEnforcement:
    """Tests for parameter bound enforcement."""

    def test_all_configs_within_bounds(self):
        """Test: all config constants are within valid bounds."""
        configs = [
            HOLD_ACOUSTIC_CONFIG,
            DE_ESCALATE_ACOUSTIC_CONFIG,
            STABILIZE_ACOUSTIC_CONFIG,
            REFLECT_ACOUSTIC_CONFIG,
            INFORM_ACOUSTIC_CONFIG,
            CLARIFY_ACOUSTIC_CONFIG,
        ]

        for config in configs:
            # Verify speech_rate bounds
            assert SPEECH_RATE_MIN <= config["speech_rate"] <= SPEECH_RATE_MAX

            # Verify energy_level bounds
            assert ENERGY_LEVEL_MIN <= config["energy_level"] <= ENERGY_LEVEL_MAX

            # Verify pitch_range bounds
            pitch_low, pitch_high = config["pitch_range"]
            assert PITCH_MIN <= pitch_low <= PITCH_MAX
            assert PITCH_MIN <= pitch_high <= PITCH_MAX
            assert pitch_low <= pitch_high

            # Verify pause_duration bounds
            pause_low, pause_high = config["pause_duration_ms"]
            assert PAUSE_DURATION_MIN <= pause_low <= PAUSE_DURATION_MAX
            assert PAUSE_DURATION_MIN <= pause_high <= PAUSE_DURATION_MAX
            assert pause_low <= pause_high

            # Verify max_stressed_tokens bounds
            assert MAX_STRESSED_TOKENS_MIN <= config["max_stressed_tokens"] <= MAX_STRESSED_TOKENS_MAX

    def test_resolver_output_always_within_bounds(self):
        """Test: resolver always produces output within bounds."""
        resolver = P10AcousticResolver()

        for regime_type in OperationalRegime:
            for act in DiscourseAct:
                regime = make_regime_envelope(regime_type, IntentType.INFORM)
                discourse = make_discourse_envelope(act, regime_type, IntentType.INFORM)
                lexical_frame = make_lexical_frame()

                frame = resolver.resolve(
                    lexical_frame=lexical_frame,
                    discourse_envelope=discourse,
                    regime_envelope=regime,
                )

                # All parameters must be within bounds
                assert SPEECH_RATE_MIN <= frame.speech_rate <= SPEECH_RATE_MAX
                assert ENERGY_LEVEL_MIN <= frame.energy_level <= ENERGY_LEVEL_MAX
                assert PITCH_MIN <= frame.pitch_range[0] <= PITCH_MAX
                assert PITCH_MIN <= frame.pitch_range[1] <= PITCH_MAX
                assert frame.pitch_range[0] <= frame.pitch_range[1]
                assert PAUSE_DURATION_MIN <= frame.pause_duration_ms[0] <= PAUSE_DURATION_MAX
                assert PAUSE_DURATION_MIN <= frame.pause_duration_ms[1] <= PAUSE_DURATION_MAX
                assert frame.pause_duration_ms[0] <= frame.pause_duration_ms[1]
                assert MAX_STRESSED_TOKENS_MIN <= frame.max_stressed_tokens <= MAX_STRESSED_TOKENS_MAX
