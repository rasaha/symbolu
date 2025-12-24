"""
P28 Delivery Harmonization Phase Unit Tests
=============================================

Comprehensive tests for P28 DHA phase:
- P28Authority enum
- DeliveryProfileType enum
- ReadinessLevel enum
- ResistanceLevel enum
- SafetyStatus enum
- P28InputSignals dataclass
- P28ToneProfile dataclass
- P28SafetyResult dataclass
- P28Output dataclass
- Profile mapping logic
- Integration functions
- Determinism verification

Test Cases:
1. Enum validation
2. Signal clamping/validation
3. Delivery profile mapping
4. Readiness/resistance level mapping
5. Tone profile building
6. Safety result handling
7. Serialization (to_dict)
8. Integration function behavior
9. Determinism verification
"""

import pytest
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from symbolu.mechanical.pipeline.p28_dha import (
    VERSION,
    P28Authority,
    DeliveryProfileType,
    ReadinessLevel,
    ResistanceLevel,
    SafetyStatus,
    P28InputSignals,
    P28ToneProfile,
    P28SafetyResult,
    P28Output,
    get_dha_engine,
    get_tone_selector,
    get_readiness_analyzer,
    get_resistance_detector,
    get_safety_filters,
    extract_p28_signals,
    run_p28_adaptation,
    maybe_run_p28,
    get_p28_output,
    get_p28_guarded_text,
    get_p28_tone_profile,
)
from symbolu.mechanical.pipeline.p28_dha.p28_integration import (
    map_delivery_profile,
    map_readiness_level,
    map_resistance_level,
    build_tone_profile,
)


# =============================================================================
# MOCK CONTEXT FIXTURES
# =============================================================================


@dataclass
class MockRequest:
    """Mock UserRequest for testing."""
    text: str = "I'm struggling with my finances."
    user_id: str = "test_user"
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MockMlcr:
    """Mock MLCR result for testing."""
    entries: Dict[str, Any] = field(default_factory=dict)
    explain_log: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MockFusion:
    """Mock Fusion result for testing."""
    merged_output: str = "Here is financial guidance."
    trace: Dict[str, Any] = field(default_factory=dict)


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
    request: Optional[MockRequest] = None
    mlcr: Optional[MockMlcr] = None
    fusion: Optional[MockFusion] = None
    p27_persona: Optional[Any] = None
    p28_dha: Optional[Any] = None


# =============================================================================
# ENUM TESTS
# =============================================================================


class TestP28AuthorityEnum:
    """Tests for P28Authority enum."""

    def test_high_authority_value(self):
        """Test: HIGH authority exists."""
        assert P28Authority.HIGH.value == "high"

    def test_medium_authority_value(self):
        """Test: MEDIUM authority exists."""
        assert P28Authority.MEDIUM.value == "medium"

    def test_low_authority_value(self):
        """Test: LOW authority exists."""
        assert P28Authority.LOW.value == "low"

    def test_all_authorities_exist(self):
        """Test: all three authority levels exist."""
        authorities = list(P28Authority)
        assert len(authorities) == 3


class TestDeliveryProfileTypeEnum:
    """Tests for DeliveryProfileType enum."""

    def test_sweet_resonance_value(self):
        """Test: SWEET_RESONANCE exists."""
        assert DeliveryProfileType.SWEET_RESONANCE.value == "sweet_resonance"

    def test_inverse_jolt_value(self):
        """Test: INVERSE_JOLT exists."""
        assert DeliveryProfileType.INVERSE_JOLT.value == "inverse_jolt"

    def test_symbolic_metaphor_value(self):
        """Test: SYMBOLIC_METAPHOR exists."""
        assert DeliveryProfileType.SYMBOLIC_METAPHOR.value == "symbolic_metaphor"

    def test_balanced_value(self):
        """Test: BALANCED exists."""
        assert DeliveryProfileType.BALANCED.value == "balanced"

    def test_all_profiles_exist(self):
        """Test: all four profile types exist."""
        profiles = list(DeliveryProfileType)
        assert len(profiles) == 4


class TestReadinessLevelEnum:
    """Tests for ReadinessLevel enum."""

    def test_all_levels_exist(self):
        """Test: all readiness levels exist."""
        assert ReadinessLevel.LOW.value == "low"
        assert ReadinessLevel.MEDIUM.value == "medium"
        assert ReadinessLevel.HIGH.value == "high"
        assert len(list(ReadinessLevel)) == 3


class TestResistanceLevelEnum:
    """Tests for ResistanceLevel enum."""

    def test_all_levels_exist(self):
        """Test: all resistance levels exist."""
        assert ResistanceLevel.NONE.value == "none"
        assert ResistanceLevel.LOW.value == "low"
        assert ResistanceLevel.MEDIUM.value == "medium"
        assert ResistanceLevel.HIGH.value == "high"
        assert len(list(ResistanceLevel)) == 4


class TestSafetyStatusEnum:
    """Tests for SafetyStatus enum."""

    def test_all_statuses_exist(self):
        """Test: all safety statuses exist."""
        assert SafetyStatus.PASSED.value == "passed"
        assert SafetyStatus.MODIFIED.value == "modified"
        assert SafetyStatus.BLOCKED.value == "blocked"
        assert len(list(SafetyStatus)) == 3


# =============================================================================
# P28 INPUT SIGNALS TESTS
# =============================================================================


class TestP28InputSignals:
    """Tests for P28InputSignals dataclass."""

    def test_basic_construction(self):
        """Test: basic construction with required fields."""
        signals = P28InputSignals(
            query_text="Test query",
            response_text="Test response",
        )
        assert signals.query_text == "Test query"
        assert signals.response_text == "Test response"
        assert signals.persona_id == "neutral"  # default

    def test_full_construction(self):
        """Test: construction with all fields."""
        signals = P28InputSignals(
            query_text="How can I improve?",
            response_text="Here are some suggestions.",
            persona_id="coach",
            persona_tone_warmth=0.7,
            persona_formality=0.4,
            persona_directness=0.6,
            tier="lower",
            intent="emotional",
            domain="psychology",
            emotional_entropy=0.6,
            dimensional_entropy=0.5,
            readiness_score=0.7,
            resistance_score=0.2,
        )
        assert signals.persona_id == "coach"
        assert signals.emotional_entropy == 0.6

    def test_value_clamping(self):
        """Test: values are clamped to [0, 1]."""
        signals = P28InputSignals(
            query_text="test",
            response_text="test",
            emotional_entropy=1.5,
            readiness_score=-0.2,
            persona_tone_warmth=2.0,
        )
        assert signals.emotional_entropy == 1.0
        assert signals.readiness_score == 0.0
        assert signals.persona_tone_warmth == 1.0

    def test_immutability(self):
        """Test: P28InputSignals is frozen (immutable)."""
        signals = P28InputSignals(
            query_text="test",
            response_text="test",
        )
        with pytest.raises(Exception):
            signals.tier = "upper"


# =============================================================================
# P28 TONE PROFILE TESTS
# =============================================================================


class TestP28ToneProfile:
    """Tests for P28ToneProfile dataclass."""

    def test_default_construction(self):
        """Test: construction with defaults."""
        profile = P28ToneProfile()
        assert profile.profile_type == DeliveryProfileType.BALANCED
        assert profile.warmth == 0.5
        assert profile.directness == 0.5
        assert profile.message_pace == "normal"

    def test_custom_construction(self):
        """Test: construction with custom values."""
        profile = P28ToneProfile(
            profile_type=DeliveryProfileType.SWEET_RESONANCE,
            warmth=0.8,
            directness=0.3,
            empathy=0.9,
            message_pace="slow",
        )
        assert profile.profile_type == DeliveryProfileType.SWEET_RESONANCE
        assert profile.warmth == 0.8
        assert profile.message_pace == "slow"

    def test_to_dict(self):
        """Test: to_dict serialization."""
        profile = P28ToneProfile(
            profile_type=DeliveryProfileType.INVERSE_JOLT,
            warmth=0.3,
            directness=0.8,
        )
        result = profile.to_dict()

        assert result["profile_type"] == "inverse_jolt"
        assert result["warmth"] == 0.3
        assert result["directness"] == 0.8


# =============================================================================
# P28 SAFETY RESULT TESTS
# =============================================================================


class TestP28SafetyResult:
    """Tests for P28SafetyResult dataclass."""

    def test_default_construction(self):
        """Test: construction with defaults (passed)."""
        result = P28SafetyResult()
        assert result.status == SafetyStatus.PASSED
        assert result.original_text is None
        assert result.safety_score == 1.0

    def test_modified_status(self):
        """Test: construction with MODIFIED status."""
        result = P28SafetyResult(
            status=SafetyStatus.MODIFIED,
            original_text="Original content",
            modifications=["Removed sensitive info"],
            safety_score=0.8,
        )
        assert result.status == SafetyStatus.MODIFIED
        assert result.original_text == "Original content"
        assert len(result.modifications) == 1

    def test_to_dict(self):
        """Test: to_dict serialization."""
        result = P28SafetyResult(
            status=SafetyStatus.MODIFIED,
            modifications=["Mod 1", "Mod 2"],
            safety_score=0.7,
        )
        d = result.to_dict()

        assert d["status"] == "modified"
        assert d["has_modifications"] is True
        assert d["modification_count"] == 2
        assert d["safety_score"] == 0.7


# =============================================================================
# P28 OUTPUT TESTS
# =============================================================================


class TestP28Output:
    """Tests for P28Output dataclass."""

    def test_basic_construction(self):
        """Test: basic construction with required fields."""
        output = P28Output(
            adapted_text="Adapted message",
            guarded_text="Guarded message",
        )
        assert output.adapted_text == "Adapted message"
        assert output.guarded_text == "Guarded message"
        assert output.readiness_level == ReadinessLevel.MEDIUM  # default
        assert output.authority == P28Authority.MEDIUM  # default

    def test_guarded_text_fallback(self):
        """Test: guarded_text defaults to adapted_text if empty."""
        output = P28Output(
            adapted_text="Adapted content",
            guarded_text="",
        )
        # Post-init should set guarded_text = adapted_text
        assert output.guarded_text == "Adapted content"

    def test_full_construction(self):
        """Test: construction with all fields."""
        tone = P28ToneProfile(profile_type=DeliveryProfileType.SWEET_RESONANCE)
        safety = P28SafetyResult(status=SafetyStatus.PASSED)

        output = P28Output(
            adapted_text="Adapted",
            guarded_text="Guarded",
            tone_profile=tone,
            readiness_level=ReadinessLevel.HIGH,
            resistance_level=ResistanceLevel.LOW,
            safety_result=safety,
            authority=P28Authority.HIGH,
            adaptation_trace=["Step 1", "Step 2"],
        )
        assert output.readiness_level == ReadinessLevel.HIGH
        assert len(output.adaptation_trace) == 2

    def test_to_dict(self):
        """Test: to_dict serialization."""
        output = P28Output(
            adapted_text="Adapted",
            guarded_text="Guarded",
            readiness_level=ReadinessLevel.HIGH,
            resistance_level=ResistanceLevel.LOW,
            adaptation_trace=["Trace 1"],
        )
        result = output.to_dict()

        assert result["phase"] == "P28"
        assert result["version"] == VERSION
        assert result["adapted_text"] == "Adapted"
        assert result["readiness_level"] == "high"
        assert result["resistance_level"] == "low"


# =============================================================================
# PROFILE MAPPING TESTS
# =============================================================================


class TestDeliveryProfileMapping:
    """Tests for delivery profile mapping logic."""

    def test_high_resistance_low_readiness_maps_inverse_jolt(self):
        """Test: high resistance + low readiness → INVERSE_JOLT."""
        signals = P28InputSignals(
            query_text="I don't want to hear this",
            response_text="Response",
            resistance_score=0.7,
            readiness_score=0.3,
        )
        profile = map_delivery_profile(signals)
        assert profile == DeliveryProfileType.INVERSE_JOLT

    def test_high_emotional_entropy_maps_symbolic_metaphor(self):
        """Test: high emotional entropy → SYMBOLIC_METAPHOR."""
        signals = P28InputSignals(
            query_text="I'm confused",
            response_text="Response",
            emotional_entropy=0.8,
            resistance_score=0.3,
        )
        profile = map_delivery_profile(signals)
        assert profile == DeliveryProfileType.SYMBOLIC_METAPHOR

    def test_high_readiness_low_resistance_maps_sweet_resonance(self):
        """Test: high readiness + low resistance → SWEET_RESONANCE."""
        signals = P28InputSignals(
            query_text="I'm ready to learn",
            response_text="Response",
            readiness_score=0.7,
            resistance_score=0.2,
        )
        profile = map_delivery_profile(signals)
        assert profile == DeliveryProfileType.SWEET_RESONANCE

    def test_default_maps_balanced(self):
        """Test: default signals → BALANCED."""
        signals = P28InputSignals(
            query_text="Regular question",
            response_text="Response",
            readiness_score=0.5,
            resistance_score=0.4,
            emotional_entropy=0.5,
        )
        profile = map_delivery_profile(signals)
        assert profile == DeliveryProfileType.BALANCED


class TestReadinessLevelMapping:
    """Tests for readiness level mapping."""

    def test_low_score_maps_low(self):
        """Test: score < 0.35 → LOW."""
        assert map_readiness_level(0.2) == ReadinessLevel.LOW
        assert map_readiness_level(0.34) == ReadinessLevel.LOW

    def test_medium_score_maps_medium(self):
        """Test: 0.35 <= score < 0.65 → MEDIUM."""
        assert map_readiness_level(0.35) == ReadinessLevel.MEDIUM
        assert map_readiness_level(0.5) == ReadinessLevel.MEDIUM
        assert map_readiness_level(0.64) == ReadinessLevel.MEDIUM

    def test_high_score_maps_high(self):
        """Test: score >= 0.65 → HIGH."""
        assert map_readiness_level(0.65) == ReadinessLevel.HIGH
        assert map_readiness_level(0.9) == ReadinessLevel.HIGH


class TestResistanceLevelMapping:
    """Tests for resistance level mapping."""

    def test_very_low_maps_none(self):
        """Test: score < 0.2 → NONE."""
        assert map_resistance_level(0.1) == ResistanceLevel.NONE
        assert map_resistance_level(0.19) == ResistanceLevel.NONE

    def test_low_score_maps_low(self):
        """Test: 0.2 <= score < 0.4 → LOW."""
        assert map_resistance_level(0.2) == ResistanceLevel.LOW
        assert map_resistance_level(0.39) == ResistanceLevel.LOW

    def test_medium_score_maps_medium(self):
        """Test: 0.4 <= score < 0.6 → MEDIUM."""
        assert map_resistance_level(0.4) == ResistanceLevel.MEDIUM
        assert map_resistance_level(0.59) == ResistanceLevel.MEDIUM

    def test_high_score_maps_high(self):
        """Test: score >= 0.6 → HIGH."""
        assert map_resistance_level(0.6) == ResistanceLevel.HIGH
        assert map_resistance_level(0.9) == ResistanceLevel.HIGH


class TestToneProfileBuilding:
    """Tests for tone profile building."""

    def test_sweet_resonance_modulation(self):
        """Test: SWEET_RESONANCE increases warmth and empathy."""
        signals = P28InputSignals(
            query_text="test",
            response_text="test",
            persona_tone_warmth=0.5,
        )
        profile = build_tone_profile(DeliveryProfileType.SWEET_RESONANCE, signals)

        assert profile.warmth == 0.7  # 0.5 + 0.2
        assert profile.empathy == 0.8
        assert profile.message_pace == "slow"

    def test_inverse_jolt_modulation(self):
        """Test: INVERSE_JOLT increases directness."""
        signals = P28InputSignals(
            query_text="test",
            response_text="test",
            persona_directness=0.5,
            persona_tone_warmth=0.5,
        )
        profile = build_tone_profile(DeliveryProfileType.INVERSE_JOLT, signals)

        assert profile.directness == 0.8  # 0.5 + 0.3
        assert profile.warmth == 0.4  # 0.5 - 0.1
        assert profile.message_pace == "fast"

    def test_symbolic_metaphor_modulation(self):
        """Test: SYMBOLIC_METAPHOR decreases directness."""
        signals = P28InputSignals(
            query_text="test",
            response_text="test",
            persona_directness=0.5,
        )
        profile = build_tone_profile(DeliveryProfileType.SYMBOLIC_METAPHOR, signals)

        assert profile.directness == 0.3  # 0.5 - 0.2
        assert profile.empathy == 0.7


# =============================================================================
# INTEGRATION FUNCTION TESTS
# =============================================================================


class TestSignalExtraction:
    """Tests for extract_p28_signals function."""

    def test_extract_from_minimal_context(self):
        """Test: extraction from minimal context."""
        ctx = MockPipelineContext(
            request=MockRequest(text="Test question"),
            fusion=MockFusion(merged_output="Test response"),
        )
        signals = extract_p28_signals(ctx)

        assert signals is not None
        assert signals.query_text == "Test question"
        assert signals.response_text == "Test response"
        assert signals.persona_id == "neutral"

    def test_extract_with_p27_output(self):
        """Test: extraction with P27 output."""
        ctx = MockPipelineContext(
            request=MockRequest(),
            fusion=MockFusion(),
        )
        p27 = MockP27Output(
            persona_id="coach",
            directives=MockP27Directives(tone_warmth=0.8),
        )
        signals = extract_p28_signals(ctx, p27)

        assert signals is not None
        assert signals.persona_id == "coach"
        assert signals.persona_tone_warmth == 0.8

    def test_extract_with_context_p27_persona(self):
        """Test: extraction uses ctx.p27_persona if no p27_output provided."""
        p27 = MockP27Output(
            persona_id="analyst",
            directives=MockP27Directives(tone_warmth=0.3),
        )
        ctx = MockPipelineContext(
            request=MockRequest(),
            fusion=MockFusion(),
            p27_persona=p27,
        )
        signals = extract_p28_signals(ctx)

        assert signals is not None
        assert signals.persona_id == "analyst"
        assert signals.persona_tone_warmth == 0.3


class TestRunP28Adaptation:
    """Tests for run_p28_adaptation function."""

    def test_adaptation_returns_output(self):
        """Test: adaptation returns P28Output."""
        signals = P28InputSignals(
            query_text="Help me",
            response_text="Here's guidance.",
            readiness_score=0.6,
            resistance_score=0.2,
        )
        output = run_p28_adaptation(signals)

        assert output is not None
        assert isinstance(output, P28Output)
        assert output.adapted_text != ""
        assert len(output.adaptation_trace) > 0

    def test_adaptation_trace_populated(self):
        """Test: adaptation trace is populated."""
        signals = P28InputSignals(
            query_text="Test",
            response_text="Response",
        )
        output = run_p28_adaptation(signals)

        assert len(output.adaptation_trace) > 0
        # Should contain profile selection
        assert any("profile" in t.lower() for t in output.adaptation_trace)


class TestMaybeRunP28:
    """Tests for maybe_run_p28 function."""

    def test_maybe_run_returns_output(self):
        """Test: maybe_run_p28 returns P28Output."""
        ctx = MockPipelineContext(
            request=MockRequest(),
            mlcr=MockMlcr(
                explain_log={
                    "meta": {"tier": "hybrid", "domain": "generic"},
                    "entropy": {"H_D": 0.5, "H_G": 0.5},
                }
            ),
            fusion=MockFusion(),
        )
        output = maybe_run_p28(ctx)

        assert output is not None
        assert isinstance(output, P28Output)

    def test_maybe_run_with_p27_output(self):
        """Test: maybe_run_p28 uses P27 output."""
        ctx = MockPipelineContext(
            request=MockRequest(),
            fusion=MockFusion(),
        )
        p27 = MockP27Output(persona_id="friendly")

        output = maybe_run_p28(ctx, p27_output=p27)

        assert output is not None


class TestGetP28Output:
    """Tests for get_p28_output function."""

    def test_get_output_when_present(self):
        """Test: get_p28_output returns output when present."""
        expected = P28Output(
            adapted_text="Adapted",
            guarded_text="Guarded",
        )
        ctx = MockPipelineContext(p28_dha=expected)

        result = get_p28_output(ctx)
        assert result is expected

    def test_get_output_when_absent(self):
        """Test: get_p28_output returns None when absent."""
        ctx = MockPipelineContext()
        result = get_p28_output(ctx)
        assert result is None


class TestGetP28GuardedText:
    """Tests for get_p28_guarded_text function."""

    def test_get_guarded_text_when_present(self):
        """Test: get_p28_guarded_text returns text when present."""
        output = P28Output(
            adapted_text="Adapted",
            guarded_text="Safe guarded text",
        )
        ctx = MockPipelineContext(p28_dha=output)

        result = get_p28_guarded_text(ctx)
        assert result == "Safe guarded text"

    def test_get_guarded_text_when_absent(self):
        """Test: get_p28_guarded_text returns empty string when absent."""
        ctx = MockPipelineContext()
        result = get_p28_guarded_text(ctx)
        assert result == ""


class TestGetP28ToneProfile:
    """Tests for get_p28_tone_profile function."""

    def test_get_tone_profile_when_present(self):
        """Test: get_p28_tone_profile returns profile when present."""
        tone = P28ToneProfile(profile_type=DeliveryProfileType.SWEET_RESONANCE)
        output = P28Output(
            adapted_text="Text",
            guarded_text="Text",
            tone_profile=tone,
        )
        ctx = MockPipelineContext(p28_dha=output)

        result = get_p28_tone_profile(ctx)
        assert result is not None
        assert result.profile_type == DeliveryProfileType.SWEET_RESONANCE

    def test_get_tone_profile_when_absent(self):
        """Test: get_p28_tone_profile returns None when absent."""
        ctx = MockPipelineContext()
        result = get_p28_tone_profile(ctx)
        assert result is None


# =============================================================================
# SINGLETON TESTS
# =============================================================================


class TestSingletons:
    """Tests for singleton instances."""

    def test_dha_engine_singleton(self):
        """Test: get_dha_engine returns singleton."""
        engine1 = get_dha_engine()
        engine2 = get_dha_engine()
        assert engine1 is engine2

    def test_tone_selector_singleton(self):
        """Test: get_tone_selector returns singleton."""
        selector1 = get_tone_selector()
        selector2 = get_tone_selector()
        assert selector1 is selector2

    def test_readiness_analyzer_singleton(self):
        """Test: get_readiness_analyzer returns singleton."""
        analyzer1 = get_readiness_analyzer()
        analyzer2 = get_readiness_analyzer()
        assert analyzer1 is analyzer2

    def test_resistance_detector_singleton(self):
        """Test: get_resistance_detector returns singleton."""
        detector1 = get_resistance_detector()
        detector2 = get_resistance_detector()
        assert detector1 is detector2

    def test_safety_filters_singleton(self):
        """Test: get_safety_filters returns singleton."""
        filters1 = get_safety_filters()
        filters2 = get_safety_filters()
        assert filters1 is filters2


# =============================================================================
# DETERMINISM TESTS
# =============================================================================


class TestDeterminism:
    """Tests verifying deterministic behavior."""

    def test_same_input_same_profile(self):
        """Test: same signals produce same profile type."""
        signals = P28InputSignals(
            query_text="Test",
            response_text="Response",
            readiness_score=0.7,
            resistance_score=0.2,
        )

        results = []
        for _ in range(10):
            profile = map_delivery_profile(signals)
            results.append(profile)

        assert all(r == results[0] for r in results)

    def test_serialization_consistent(self):
        """Test: serialization is consistent."""
        output = P28Output(
            adapted_text="Adapted",
            guarded_text="Guarded",
            readiness_level=ReadinessLevel.HIGH,
        )

        serialized = []
        for _ in range(5):
            serialized.append(output.to_dict()["readiness_level"])

        assert all(s == serialized[0] for s in serialized)


# =============================================================================
# ARCHITECTURAL PHASE TESTS
# =============================================================================


class TestArchitecturalPhase:
    """Tests verifying architectural phase identification."""

    def test_output_identifies_as_p28(self):
        """Test: output correctly identifies as P28."""
        output = P28Output(
            adapted_text="Text",
            guarded_text="Text",
        )

        result = output.to_dict()
        assert result["phase"] == "P28"

    def test_output_includes_version(self):
        """Test: output includes version."""
        output = P28Output(
            adapted_text="Text",
            guarded_text="Text",
        )

        result = output.to_dict()
        assert result["version"] == VERSION


# =============================================================================
# SAFETY AUTHORITY TESTS
# =============================================================================


class TestSafetyAuthority:
    """Tests verifying safety-related authority escalation."""

    def test_safety_modified_increases_authority(self):
        """Test: safety modification increases authority to HIGH."""
        signals = P28InputSignals(
            query_text="Test",
            response_text="Response",
        )
        # When safety filters modify content, authority should be HIGH
        # This is tested through the full run_p28_adaptation
        output = run_p28_adaptation(signals)

        # If safety passed without modification, authority is MEDIUM
        if output.safety_result.status == SafetyStatus.PASSED:
            assert output.authority == P28Authority.MEDIUM
        else:
            # If modified or blocked, authority is HIGH
            assert output.authority == P28Authority.HIGH


# =============================================================================
# RUN TESTS
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
