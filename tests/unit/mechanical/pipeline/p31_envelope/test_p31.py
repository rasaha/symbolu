"""
P31 Output Envelope Phase Unit Tests
======================================

Comprehensive tests for P31 Output Envelope phase:
- P31Authority enum
- EnvelopeFormat enum
- DeliveryChannel enum
- P31Metadata dataclass
- P31Output dataclass
- Integration functions
- Format detection
- Channel detection
- Metadata extraction
- Determinism verification
"""

import pytest
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from symbolu.mechanical.pipeline.p31_envelope import (
    VERSION,
    P31Authority,
    EnvelopeFormat,
    DeliveryChannel,
    P31Metadata,
    P31Output,
    maybe_run_p31,
    get_p31_output,
    get_final_output,
    extract_metadata,
    detect_format,
    detect_channel,
    run_p31_envelope,
)


# =============================================================================
# MOCK CONTEXT FIXTURES
# =============================================================================


@dataclass
class MockRequest:
    """Mock request for testing."""
    text: str = "Test query"
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MockToneProfile:
    """Mock tone profile for testing."""
    class ProfileType:
        value = "balanced"
    profile_type = ProfileType()


@dataclass
class MockP30Output:
    """Mock P30 output for testing."""
    verified_text: str = "Verified text from P30"
    verification_status: Any = None

    def __post_init__(self):
        from symbolu.mechanical.pipeline.p30_verification import VerificationStatus
        if self.verification_status is None:
            self.verification_status = VerificationStatus.PASSED


@dataclass
class MockP29Output:
    """Mock P29 output for testing."""
    final_text: str = "Final text from P29"


@dataclass
class MockP28Output:
    """Mock P28 output for testing."""
    guarded_text: str = "Guarded text from P28"
    tone_profile: MockToneProfile = field(default_factory=MockToneProfile)


@dataclass
class MockP27Output:
    """Mock P27 output for testing."""
    persona_id: str = "coach"


@dataclass
class MockMlcr:
    """Mock MLCR for testing."""
    explain_log: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MockPipelineContext:
    """Mock pipeline context for testing."""
    request: Optional[MockRequest] = None
    p30_verification: Optional[MockP30Output] = None
    p29_expression: Optional[MockP29Output] = None
    p28_dha: Optional[MockP28Output] = None
    p27_persona: Optional[MockP27Output] = None
    p31_envelope: Optional[Any] = None
    mlcr: Optional[MockMlcr] = None
    dha: Optional[Any] = None
    fusion: Optional[Any] = None
    hrm_map: Optional[Any] = None
    lam_map: Optional[Any] = None
    lcm_map: Optional[Any] = None


# =============================================================================
# ENUM TESTS
# =============================================================================


class TestP31AuthorityEnum:
    """Tests for P31Authority enum."""

    def test_all_authorities_exist(self):
        """Test: all authority levels exist."""
        assert P31Authority.HIGH.value == "high"
        assert P31Authority.MEDIUM.value == "medium"
        assert P31Authority.LOW.value == "low"
        assert len(list(P31Authority)) == 3


class TestEnvelopeFormatEnum:
    """Tests for EnvelopeFormat enum."""

    def test_plain_value(self):
        """Test: PLAIN exists."""
        assert EnvelopeFormat.PLAIN.value == "plain"

    def test_markdown_value(self):
        """Test: MARKDOWN exists."""
        assert EnvelopeFormat.MARKDOWN.value == "markdown"

    def test_json_value(self):
        """Test: JSON exists."""
        assert EnvelopeFormat.JSON.value == "json"

    def test_html_value(self):
        """Test: HTML exists."""
        assert EnvelopeFormat.HTML.value == "html"

    def test_ssml_value(self):
        """Test: SSML exists."""
        assert EnvelopeFormat.SSML.value == "ssml"

    def test_all_formats_exist(self):
        """Test: all five formats exist."""
        assert len(list(EnvelopeFormat)) == 5


class TestDeliveryChannelEnum:
    """Tests for DeliveryChannel enum."""

    def test_chat_value(self):
        """Test: CHAT exists."""
        assert DeliveryChannel.CHAT.value == "chat"

    def test_api_value(self):
        """Test: API exists."""
        assert DeliveryChannel.API.value == "api"

    def test_voice_value(self):
        """Test: VOICE exists."""
        assert DeliveryChannel.VOICE.value == "voice"

    def test_email_value(self):
        """Test: EMAIL exists."""
        assert DeliveryChannel.EMAIL.value == "email"

    def test_report_value(self):
        """Test: REPORT exists."""
        assert DeliveryChannel.REPORT.value == "report"

    def test_all_channels_exist(self):
        """Test: all five channels exist."""
        assert len(list(DeliveryChannel)) == 5


# =============================================================================
# P31 METADATA TESTS
# =============================================================================


class TestP31Metadata:
    """Tests for P31Metadata dataclass."""

    def test_default_construction(self):
        """Test: construction with defaults."""
        metadata = P31Metadata()
        assert metadata.pipeline_version == "3.1"
        assert metadata.phases_executed == []
        assert metadata.verification_passed is True

    def test_full_construction(self):
        """Test: construction with all fields."""
        metadata = P31Metadata(
            pipeline_version="3.1",
            phases_executed=["MLCR", "P27", "P28", "P29", "P30"],
            persona_id="coach",
            delivery_profile="sweet_resonance",
            verification_passed=True,
            render_timestamp=1234567890.0,
            custom={"tier": "hybrid"},
        )
        assert len(metadata.phases_executed) == 5
        assert metadata.persona_id == "coach"
        assert metadata.custom["tier"] == "hybrid"

    def test_to_dict(self):
        """Test: to_dict serialization."""
        metadata = P31Metadata(
            phases_executed=["P27", "P28"],
            persona_id="analyst",
            custom={"domain": "finance"},
        )
        result = metadata.to_dict()

        assert result["pipeline_version"] == "3.1"
        assert result["persona_id"] == "analyst"
        assert result["custom"]["domain"] == "finance"


# =============================================================================
# P31 OUTPUT TESTS
# =============================================================================


class TestP31Output:
    """Tests for P31Output dataclass."""

    def test_basic_construction(self):
        """Test: basic construction with required fields."""
        output = P31Output(
            envelope_text="Enveloped text",
        )
        assert output.envelope_text == "Enveloped text"
        assert output.envelope_format == EnvelopeFormat.PLAIN  # default
        assert output.delivery_channel == DeliveryChannel.CHAT  # default
        assert output.authority == P31Authority.LOW  # default

    def test_full_construction(self):
        """Test: construction with all fields."""
        metadata = P31Metadata(persona_id="coach")
        output = P31Output(
            envelope_text="Text",
            envelope_format=EnvelopeFormat.JSON,
            delivery_channel=DeliveryChannel.API,
            authority=P31Authority.LOW,
            metadata=metadata,
            processing_trace=["Step 1", "Step 2"],
        )
        assert output.envelope_format == EnvelopeFormat.JSON
        assert output.delivery_channel == DeliveryChannel.API
        assert output.metadata is not None

    def test_to_dict(self):
        """Test: to_dict serialization."""
        output = P31Output(
            envelope_text="Test output",
            envelope_format=EnvelopeFormat.MARKDOWN,
            delivery_channel=DeliveryChannel.EMAIL,
        )
        result = output.to_dict()

        assert result["phase"] == "P31"
        assert result["version"] == VERSION
        assert result["envelope_text"] == "Test output"
        assert result["envelope_format"] == "markdown"
        assert result["delivery_channel"] == "email"

    def test_to_api_response(self):
        """Test: to_api_response conversion."""
        metadata = P31Metadata(persona_id="sage")
        output = P31Output(
            envelope_text="API response text",
            envelope_format=EnvelopeFormat.JSON,
            metadata=metadata,
        )
        result = output.to_api_response()

        assert result["text"] == "API response text"
        assert result["format"] == "json"
        assert "meta" in result
        assert result["meta"]["persona_id"] == "sage"


# =============================================================================
# INTEGRATION FUNCTION TESTS
# =============================================================================


class TestExtractMetadata:
    """Tests for extract_metadata function."""

    def test_extract_from_minimal_context(self):
        """Test: extraction from minimal context."""
        ctx = MockPipelineContext()
        metadata = extract_metadata(ctx)

        assert metadata is not None
        assert metadata.pipeline_version == "3.1"
        assert metadata.render_timestamp is not None

    def test_extract_tracks_phases(self):
        """Test: extraction tracks executed phases."""
        ctx = MockPipelineContext(
            p27_persona=MockP27Output(persona_id="coach"),
            p28_dha=MockP28Output(),
            p29_expression=MockP29Output(),
            p30_verification=MockP30Output(),
        )
        metadata = extract_metadata(ctx)

        assert "P27" in metadata.phases_executed
        assert "P28" in metadata.phases_executed
        assert "P29" in metadata.phases_executed
        assert "P30" in metadata.phases_executed
        assert metadata.persona_id == "coach"

    def test_extract_includes_mlcr_metadata(self):
        """Test: extraction includes MLCR metadata."""
        ctx = MockPipelineContext(
            mlcr=MockMlcr(
                explain_log={
                    "meta": {"tier": "hybrid", "intent": "general", "domain": "psychology"}
                }
            ),
        )
        metadata = extract_metadata(ctx)

        assert metadata.custom.get("tier") == "hybrid"
        assert metadata.custom.get("domain") == "psychology"


class TestDetectFormat:
    """Tests for detect_format function."""

    def test_detect_plain_default(self):
        """Test: default format is PLAIN."""
        ctx = MockPipelineContext()
        fmt = detect_format(ctx)
        assert fmt == EnvelopeFormat.PLAIN

    def test_detect_from_request_metadata(self):
        """Test: format detected from request metadata."""
        ctx = MockPipelineContext(
            request=MockRequest(metadata={"output_format": "json"})
        )
        fmt = detect_format(ctx)
        assert fmt == EnvelopeFormat.JSON

    def test_detect_markdown(self):
        """Test: markdown format detection."""
        ctx = MockPipelineContext(
            request=MockRequest(metadata={"output_format": "markdown"})
        )
        fmt = detect_format(ctx)
        assert fmt == EnvelopeFormat.MARKDOWN

    def test_detect_ssml(self):
        """Test: SSML format detection."""
        ctx = MockPipelineContext(
            request=MockRequest(metadata={"output_format": "ssml"})
        )
        fmt = detect_format(ctx)
        assert fmt == EnvelopeFormat.SSML


class TestDetectChannel:
    """Tests for detect_channel function."""

    def test_detect_chat_default(self):
        """Test: default channel is CHAT."""
        ctx = MockPipelineContext()
        channel = detect_channel(ctx)
        assert channel == DeliveryChannel.CHAT

    def test_detect_from_request_metadata(self):
        """Test: channel detected from request metadata."""
        ctx = MockPipelineContext(
            request=MockRequest(metadata={"delivery_channel": "api"})
        )
        channel = detect_channel(ctx)
        assert channel == DeliveryChannel.API

    def test_detect_voice(self):
        """Test: voice channel detection."""
        ctx = MockPipelineContext(
            request=MockRequest(metadata={"delivery_channel": "voice"})
        )
        channel = detect_channel(ctx)
        assert channel == DeliveryChannel.VOICE

    def test_detect_email(self):
        """Test: email channel detection."""
        ctx = MockPipelineContext(
            request=MockRequest(metadata={"delivery_channel": "email"})
        )
        channel = detect_channel(ctx)
        assert channel == DeliveryChannel.EMAIL


class TestRunP31Envelope:
    """Tests for run_p31_envelope function."""

    def test_envelope_returns_output(self):
        """Test: envelope returns P31Output."""
        ctx = MockPipelineContext()
        output = run_p31_envelope("Test text", ctx)

        assert output is not None
        assert isinstance(output, P31Output)
        assert output.envelope_text == "Test text"

    def test_envelope_includes_metadata(self):
        """Test: envelope includes metadata."""
        ctx = MockPipelineContext()
        output = run_p31_envelope("Test text", ctx)

        assert output.metadata is not None

    def test_envelope_processing_trace_populated(self):
        """Test: processing trace is populated."""
        ctx = MockPipelineContext()
        output = run_p31_envelope("Test text", ctx)

        assert len(output.processing_trace) > 0


class TestMaybeRunP31:
    """Tests for maybe_run_p31 function."""

    def test_maybe_run_from_p30(self):
        """Test: maybe_run_p31 uses P30 text."""
        ctx = MockPipelineContext(
            p30_verification=MockP30Output(verified_text="P30 text"),
        )
        output = maybe_run_p31(ctx)

        assert output is not None
        assert output.envelope_text == "P30 text"

    def test_maybe_run_fallback_to_p29(self):
        """Test: maybe_run_p31 falls back to P29."""
        ctx = MockPipelineContext(
            p29_expression=MockP29Output(final_text="P29 fallback"),
        )
        output = maybe_run_p31(ctx)

        assert output is not None
        assert output.envelope_text == "P29 fallback"

    def test_maybe_run_fallback_to_p28(self):
        """Test: maybe_run_p31 falls back to P28."""
        ctx = MockPipelineContext(
            p28_dha=MockP28Output(guarded_text="P28 fallback"),
        )
        output = maybe_run_p31(ctx)

        assert output is not None
        assert output.envelope_text == "P28 fallback"

    def test_maybe_run_returns_none_without_input(self):
        """Test: maybe_run_p31 returns None without input."""
        ctx = MockPipelineContext()
        output = maybe_run_p31(ctx)

        assert output is None


class TestGetP31Output:
    """Tests for get_p31_output function."""

    def test_get_output_when_present(self):
        """Test: get_p31_output returns output when present."""
        expected = P31Output(envelope_text="Enveloped")
        ctx = MockPipelineContext(p31_envelope=expected)

        result = get_p31_output(ctx)
        assert result is expected

    def test_get_output_when_absent(self):
        """Test: get_p31_output returns None when absent."""
        ctx = MockPipelineContext()
        result = get_p31_output(ctx)
        assert result is None


class TestGetFinalOutput:
    """Tests for get_final_output function."""

    def test_get_final_from_p31(self):
        """Test: get_final_output returns P31 text when present."""
        output = P31Output(envelope_text="Final enveloped text")
        ctx = MockPipelineContext(p31_envelope=output)

        result = get_final_output(ctx)
        assert result == "Final enveloped text"

    def test_get_final_fallback_to_p30(self):
        """Test: get_final_output falls back to P30."""
        ctx = MockPipelineContext(
            p30_verification=MockP30Output(verified_text="P30 fallback"),
        )

        result = get_final_output(ctx)
        assert result == "P30 fallback"

    def test_get_final_fallback_to_p29(self):
        """Test: get_final_output falls back to P29."""
        ctx = MockPipelineContext(
            p29_expression=MockP29Output(final_text="P29 fallback"),
        )

        result = get_final_output(ctx)
        assert result == "P29 fallback"

    def test_get_final_fallback_to_p28(self):
        """Test: get_final_output falls back to P28."""
        ctx = MockPipelineContext(
            p28_dha=MockP28Output(guarded_text="P28 fallback"),
        )

        result = get_final_output(ctx)
        assert result == "P28 fallback"

    def test_get_final_empty_when_all_absent(self):
        """Test: get_final_output returns empty when all absent."""
        ctx = MockPipelineContext()
        result = get_final_output(ctx)
        assert result == ""


# =============================================================================
# DETERMINISM TESTS
# =============================================================================


class TestDeterminism:
    """Tests verifying deterministic behavior."""

    def test_same_input_same_output(self):
        """Test: same text produces same output."""
        ctx = MockPipelineContext()

        results = []
        for _ in range(10):
            output = run_p31_envelope("Test text", ctx)
            results.append(output.envelope_format)

        assert all(r == results[0] for r in results)


# =============================================================================
# ARCHITECTURAL PHASE TESTS
# =============================================================================


class TestArchitecturalPhase:
    """Tests verifying architectural phase identification."""

    def test_output_identifies_as_p31(self):
        """Test: output correctly identifies as P31."""
        output = P31Output(envelope_text="Text")

        result = output.to_dict()
        assert result["phase"] == "P31"

    def test_default_authority_is_low(self):
        """Test: default authority is LOW."""
        output = P31Output(envelope_text="Text")
        assert output.authority == P31Authority.LOW


# =============================================================================
# RUN TESTS
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
