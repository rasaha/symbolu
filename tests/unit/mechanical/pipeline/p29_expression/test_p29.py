"""
P29 Expression Finalization Phase Unit Tests
==============================================

Comprehensive tests for P29 Expression Finalization phase:
- P29Authority enum
- PolishMode enum
- RhythmQuality enum
- P29InputSignals dataclass
- P29PhonemeAnalysis dataclass
- P29StyleModifications dataclass
- P29Output dataclass
- Integration functions
- Determinism verification
"""

import pytest
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from symbolu.mechanical.pipeline.p29_expression import (
    VERSION,
    P29Authority,
    PolishMode,
    RhythmQuality,
    P29InputSignals,
    P29PhonemeAnalysis,
    P29StyleModifications,
    P29Output,
    maybe_run_p29,
    get_p29_output,
    get_p29_final_text,
    extract_p29_signals,
    run_p29_finalization,
)


# =============================================================================
# MOCK CONTEXT FIXTURES
# =============================================================================


@dataclass
class MockToneProfile:
    """Mock tone profile for testing."""
    profile_type: Any = None

    def __post_init__(self):
        if self.profile_type is None:
            from symbolu.mechanical.pipeline.p28_dha import DeliveryProfileType
            self.profile_type = DeliveryProfileType.BALANCED


@dataclass
class MockP28Output:
    """Mock P28 output for testing."""
    guarded_text: str = "Test guarded text from P28."
    tone_profile: MockToneProfile = field(default_factory=MockToneProfile)


@dataclass
class MockP27Directives:
    """Mock P27 directives for testing."""
    tone_warmth: float = 0.6
    formality_level: float = 0.5
    directness: float = 0.5


@dataclass
class MockP27Output:
    """Mock P27 output for testing."""
    persona_id: str = "coach"
    directives: MockP27Directives = field(default_factory=MockP27Directives)


@dataclass
class MockPipelineContext:
    """Mock pipeline context for testing."""
    p28_dha: Optional[MockP28Output] = None
    p27_persona: Optional[MockP27Output] = None
    p29_expression: Optional[Any] = None
    dha: Optional[Any] = None
    persona: Optional[Any] = None


# =============================================================================
# ENUM TESTS
# =============================================================================


class TestP29AuthorityEnum:
    """Tests for P29Authority enum."""

    def test_all_authorities_exist(self):
        """Test: all authority levels exist."""
        assert P29Authority.HIGH.value == "high"
        assert P29Authority.MEDIUM.value == "medium"
        assert P29Authority.LOW.value == "low"
        assert len(list(P29Authority)) == 3


class TestPolishModeEnum:
    """Tests for PolishMode enum."""

    def test_phoneme_only_value(self):
        """Test: PHONEME_ONLY exists."""
        assert PolishMode.PHONEME_ONLY.value == "phoneme_only"

    def test_style_only_value(self):
        """Test: STYLE_ONLY exists."""
        assert PolishMode.STYLE_ONLY.value == "style_only"

    def test_full_value(self):
        """Test: FULL exists."""
        assert PolishMode.FULL.value == "full"

    def test_passthrough_value(self):
        """Test: PASSTHROUGH exists."""
        assert PolishMode.PASSTHROUGH.value == "passthrough"

    def test_all_modes_exist(self):
        """Test: all four polish modes exist."""
        assert len(list(PolishMode)) == 4


class TestRhythmQualityEnum:
    """Tests for RhythmQuality enum."""

    def test_all_qualities_exist(self):
        """Test: all rhythm qualities exist."""
        assert RhythmQuality.EXCELLENT.value == "excellent"
        assert RhythmQuality.GOOD.value == "good"
        assert RhythmQuality.FAIR.value == "fair"
        assert RhythmQuality.POOR.value == "poor"
        assert len(list(RhythmQuality)) == 4


# =============================================================================
# P29 INPUT SIGNALS TESTS
# =============================================================================


class TestP29InputSignals:
    """Tests for P29InputSignals dataclass."""

    def test_basic_construction(self):
        """Test: basic construction with required fields."""
        signals = P29InputSignals(
            input_text="Test input text",
        )
        assert signals.input_text == "Test input text"
        assert signals.persona_id == "neutral"  # default
        assert signals.polish_mode == PolishMode.FULL  # default

    def test_full_construction(self):
        """Test: construction with all fields."""
        signals = P29InputSignals(
            input_text="Test text",
            persona_id="coach",
            tone_warmth=0.7,
            formality_level=0.4,
            directness=0.6,
            delivery_profile="sweet_resonance",
            polish_mode=PolishMode.STYLE_ONLY,
        )
        assert signals.persona_id == "coach"
        assert signals.delivery_profile == "sweet_resonance"
        assert signals.polish_mode == PolishMode.STYLE_ONLY

    def test_value_clamping(self):
        """Test: values are clamped to [0, 1]."""
        signals = P29InputSignals(
            input_text="test",
            tone_warmth=1.5,
            formality_level=-0.2,
        )
        assert signals.tone_warmth == 1.0
        assert signals.formality_level == 0.0

    def test_immutability(self):
        """Test: P29InputSignals is frozen (immutable)."""
        signals = P29InputSignals(input_text="test")
        with pytest.raises(Exception):
            signals.persona_id = "sage"


# =============================================================================
# P29 PHONEME ANALYSIS TESTS
# =============================================================================


class TestP29PhonemeAnalysis:
    """Tests for P29PhonemeAnalysis dataclass."""

    def test_default_construction(self):
        """Test: construction with defaults."""
        analysis = P29PhonemeAnalysis()
        assert analysis.overall_harmony == 0.0
        assert analysis.dominant_layer == "unknown"
        assert analysis.rhythm_quality == RhythmQuality.GOOD

    def test_custom_construction(self):
        """Test: construction with custom values."""
        analysis = P29PhonemeAnalysis(
            overall_harmony=0.85,
            dominant_layer="vowel",
            bridge_meanings=["flow", "ease"],
            rhythm_quality=RhythmQuality.EXCELLENT,
            words_analyzed=15,
        )
        assert analysis.overall_harmony == 0.85
        assert analysis.rhythm_quality == RhythmQuality.EXCELLENT

    def test_to_dict(self):
        """Test: to_dict serialization."""
        analysis = P29PhonemeAnalysis(
            overall_harmony=0.7,
            rhythm_quality=RhythmQuality.GOOD,
            words_analyzed=10,
        )
        result = analysis.to_dict()

        assert result["overall_harmony"] == 0.7
        assert result["rhythm_quality"] == "good"
        assert result["words_analyzed"] == 10


# =============================================================================
# P29 STYLE MODIFICATIONS TESTS
# =============================================================================


class TestP29StyleModifications:
    """Tests for P29StyleModifications dataclass."""

    def test_default_construction(self):
        """Test: construction with defaults."""
        mods = P29StyleModifications()
        assert mods.warmth_applied == 0.5
        assert mods.modifications == []

    def test_custom_construction(self):
        """Test: construction with custom values."""
        mods = P29StyleModifications(
            warmth_applied=0.8,
            directness_applied=0.4,
            modifications=["Applied SWEET_RESONANCE style"],
        )
        assert mods.warmth_applied == 0.8
        assert len(mods.modifications) == 1

    def test_to_dict(self):
        """Test: to_dict serialization."""
        mods = P29StyleModifications(
            warmth_applied=0.7,
            modifications=["Mod 1", "Mod 2"],
        )
        result = mods.to_dict()

        assert result["warmth_applied"] == 0.7
        assert len(result["modifications"]) == 2


# =============================================================================
# P29 OUTPUT TESTS
# =============================================================================


class TestP29Output:
    """Tests for P29Output dataclass."""

    def test_basic_construction(self):
        """Test: basic construction with required fields."""
        output = P29Output(
            final_text="Final polished text",
        )
        assert output.final_text == "Final polished text"
        assert output.polish_applied is True  # default
        assert output.authority == P29Authority.LOW  # default

    def test_full_construction(self):
        """Test: construction with all fields."""
        phoneme = P29PhonemeAnalysis(overall_harmony=0.8)
        style = P29StyleModifications(warmth_applied=0.7)

        output = P29Output(
            final_text="Polished text",
            polish_applied=True,
            polish_mode=PolishMode.FULL,
            authority=P29Authority.LOW,
            phoneme_analysis=phoneme,
            style_modifications=style,
            processing_trace=["Step 1", "Step 2"],
        )
        assert output.phoneme_analysis is not None
        assert output.style_modifications is not None
        assert len(output.processing_trace) == 2

    def test_to_dict(self):
        """Test: to_dict serialization."""
        output = P29Output(
            final_text="Test output",
            polish_mode=PolishMode.FULL,
            processing_trace=["Trace 1"],
        )
        result = output.to_dict()

        assert result["phase"] == "P29"
        assert result["version"] == VERSION
        assert result["final_text"] == "Test output"
        assert result["polish_mode"] == "full"

    def test_to_dict_with_analysis(self):
        """Test: to_dict with phoneme and style analysis."""
        phoneme = P29PhonemeAnalysis(overall_harmony=0.75)
        style = P29StyleModifications(warmth_applied=0.6)

        output = P29Output(
            final_text="Text",
            phoneme_analysis=phoneme,
            style_modifications=style,
        )
        result = output.to_dict()

        assert result["phoneme_analysis"] is not None
        assert result["phoneme_analysis"]["overall_harmony"] == 0.75
        assert result["style_modifications"] is not None


# =============================================================================
# INTEGRATION FUNCTION TESTS
# =============================================================================


class TestSignalExtraction:
    """Tests for extract_p29_signals function."""

    def test_extract_from_p28_context(self):
        """Test: extraction from P28 context."""
        ctx = MockPipelineContext(
            p28_dha=MockP28Output(guarded_text="P28 guarded text"),
        )
        signals = extract_p29_signals(ctx)

        assert signals is not None
        assert signals.input_text == "P28 guarded text"

    def test_extract_with_p27_context(self):
        """Test: extraction includes P27 persona context."""
        ctx = MockPipelineContext(
            p28_dha=MockP28Output(),
            p27_persona=MockP27Output(
                persona_id="analyst",
                directives=MockP27Directives(tone_warmth=0.3),
            ),
        )
        signals = extract_p29_signals(ctx)

        assert signals is not None
        assert signals.persona_id == "analyst"
        assert signals.tone_warmth == 0.3

    def test_extract_returns_none_without_input(self):
        """Test: extraction returns None without input text."""
        ctx = MockPipelineContext()  # No p28_dha
        signals = extract_p29_signals(ctx)

        assert signals is None


class TestRunP29Finalization:
    """Tests for run_p29_finalization function."""

    def test_passthrough_mode(self):
        """Test: PASSTHROUGH mode returns unmodified text."""
        signals = P29InputSignals(
            input_text="Original text",
            polish_mode=PolishMode.PASSTHROUGH,
        )
        output = run_p29_finalization(signals)

        assert output.final_text == "Original text"
        assert output.polish_applied is False
        assert "Passthrough mode" in " ".join(output.processing_trace)

    def test_finalization_returns_output(self):
        """Test: finalization returns P29Output."""
        signals = P29InputSignals(
            input_text="Text to polish",
            polish_mode=PolishMode.FULL,
        )
        output = run_p29_finalization(signals)

        assert output is not None
        assert isinstance(output, P29Output)
        assert output.final_text != ""

    def test_processing_trace_populated(self):
        """Test: processing trace is populated."""
        signals = P29InputSignals(
            input_text="Test text",
            polish_mode=PolishMode.FULL,
        )
        output = run_p29_finalization(signals)

        assert len(output.processing_trace) > 0


class TestMaybeRunP29:
    """Tests for maybe_run_p29 function."""

    def test_maybe_run_returns_output(self):
        """Test: maybe_run_p29 returns P29Output."""
        ctx = MockPipelineContext(
            p28_dha=MockP28Output(guarded_text="Test input"),
        )
        output = maybe_run_p29(ctx)

        assert output is not None
        assert isinstance(output, P29Output)

    def test_maybe_run_returns_none_without_input(self):
        """Test: maybe_run_p29 returns None without input."""
        ctx = MockPipelineContext()
        output = maybe_run_p29(ctx)

        assert output is None


class TestGetP29Output:
    """Tests for get_p29_output function."""

    def test_get_output_when_present(self):
        """Test: get_p29_output returns output when present."""
        expected = P29Output(final_text="Final text")
        ctx = MockPipelineContext(p29_expression=expected)

        result = get_p29_output(ctx)
        assert result is expected

    def test_get_output_when_absent(self):
        """Test: get_p29_output returns None when absent."""
        ctx = MockPipelineContext()
        result = get_p29_output(ctx)
        assert result is None


class TestGetP29FinalText:
    """Tests for get_p29_final_text function."""

    def test_get_final_text_from_p29(self):
        """Test: get_p29_final_text returns P29 text when present."""
        output = P29Output(final_text="P29 final text")
        ctx = MockPipelineContext(p29_expression=output)

        result = get_p29_final_text(ctx)
        assert result == "P29 final text"

    def test_get_final_text_fallback_to_p28(self):
        """Test: get_p29_final_text falls back to P28."""
        ctx = MockPipelineContext(
            p28_dha=MockP28Output(guarded_text="P28 fallback text"),
        )

        result = get_p29_final_text(ctx)
        assert result == "P28 fallback text"

    def test_get_final_text_empty_when_absent(self):
        """Test: get_p29_final_text returns empty when all absent."""
        ctx = MockPipelineContext()
        result = get_p29_final_text(ctx)
        assert result == ""


# =============================================================================
# DETERMINISM TESTS
# =============================================================================


class TestDeterminism:
    """Tests verifying deterministic behavior."""

    def test_same_input_same_output(self):
        """Test: same signals produce same output."""
        signals = P29InputSignals(
            input_text="Determinism test",
            polish_mode=PolishMode.PASSTHROUGH,
        )

        results = []
        for _ in range(10):
            output = run_p29_finalization(signals)
            results.append(output.final_text)

        assert all(r == results[0] for r in results)


# =============================================================================
# ARCHITECTURAL PHASE TESTS
# =============================================================================


class TestArchitecturalPhase:
    """Tests verifying architectural phase identification."""

    def test_output_identifies_as_p29(self):
        """Test: output correctly identifies as P29."""
        output = P29Output(final_text="Text")

        result = output.to_dict()
        assert result["phase"] == "P29"

    def test_default_authority_is_low(self):
        """Test: default authority is LOW."""
        output = P29Output(final_text="Text")
        assert output.authority == P29Authority.LOW


# =============================================================================
# RUN TESTS
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
