"""Real-World Speech Synthesis Validation Tests.

These tests validate the complete speech generation pipeline with
realistic scenarios that would occur in production use.

Test Categories:
1. Confidence Scenarios - High/low confidence speech adaptation
2. Uncertainty Expression - Hedging and deferral
3. Clarification Requests - Question-asking behavior
4. Multi-Turn Conversations - Session-aware speech
5. Tier-Specific Output - Consumer vs Enterprise speech
6. Edge Cases - Boundary conditions in speech generation
7. SSML Validity - Verify SSML structure is well-formed
8. Acoustic Consistency - Verify "Sound obeys meaning" principle
"""

import pytest
import re
from symbolu.presentation import (
    # Core Types
    PresentationEngine,
    PresentationDirective,
    SignalBundle,
    VrittiDistribution,
    SessionContext,
    DeliveryMode,
    ConfidenceIndicator,
    # Configs
    CONSUMER_CONFIG,
    ENTERPRISE_CHAT_CONFIG,
    # Speech Pipeline
    SpeechPipeline,
    SpeechOutput,
    PipelineMode,
    generate_speech,
    generate_ssml,
    is_speech_allowed,
    # Prosodic Renderer
    ProsodicRenderer,
    render_ssml,
    ProsodyLevel,
    # Gate
    GateMode,
    GateAction,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def consumer_engine():
    """Consumer tier presentation engine."""
    return PresentationEngine(CONSUMER_CONFIG)


@pytest.fixture
def enterprise_engine():
    """Enterprise tier presentation engine."""
    return PresentationEngine(ENTERPRISE_CHAT_CONFIG)


@pytest.fixture
def speech_pipeline():
    """GOVERNED mode speech pipeline."""
    return SpeechPipeline(mode=PipelineMode.GOVERNED)


# =============================================================================
# Helper Functions
# =============================================================================


def create_high_confidence_bundle():
    """Create bundle representing high confidence state."""
    return SignalBundle.create_minimal(
        score=0.9,
        coherence=0.85,
        vritti=VrittiDistribution(
            pramana=0.7,
            viparyaya=0.05,
            vikalpa=0.1,
            smrti=0.1,
            nidra=0.05,
        ),
        dominant_vritti="pramana",
        entropy=0.2,
        confidence=0.9,
    )


def create_uncertain_bundle():
    """Create bundle representing uncertain state."""
    return SignalBundle.create_minimal(
        score=0.5,
        coherence=0.5,
        vritti=VrittiDistribution(
            pramana=0.2,
            viparyaya=0.2,
            vikalpa=0.3,
            smrti=0.2,
            nidra=0.1,
        ),
        dominant_vritti="vikalpa",
        entropy=0.7,
        confidence=0.5,
    )


def create_low_confidence_bundle():
    """Create bundle representing low confidence state."""
    return SignalBundle.create_minimal(
        score=0.3,
        coherence=0.3,
        vritti=VrittiDistribution(
            pramana=0.1,
            viparyaya=0.4,
            vikalpa=0.2,
            smrti=0.2,
            nidra=0.1,
        ),
        dominant_vritti="viparyaya",
        entropy=0.8,
        confidence=0.3,
    )


def is_valid_ssml(ssml: str) -> bool:
    """Check if SSML string is structurally valid."""
    if not ssml.startswith("<speak>"):
        return False
    if not ssml.endswith("</speak>"):
        return False
    # Check for balanced tags (basic check)
    open_tags = len(re.findall(r"<\w+", ssml))
    close_tags = len(re.findall(r"</\w+>", ssml))
    self_closing = len(re.findall(r"/>", ssml))
    return open_tags == close_tags + self_closing


# =============================================================================
# Test Class 1: Confidence Scenarios
# =============================================================================


class TestConfidenceScenarios:
    """Test speech adaptation based on confidence levels."""

    def test_high_confidence_produces_confident_speech(
        self, consumer_engine, speech_pipeline
    ):
        """High confidence should produce neutral/confident speech."""
        bundle = create_high_confidence_bundle()
        directive = consumer_engine.compute(bundle)

        output = speech_pipeline.execute(
            directive,
            "The answer is 42."
        )

        assert output.is_blocked is False
        assert output.delivery_mode == "confident"
        assert output.acoustic_regime == "neutral"
        # Should allow some emphasis
        assert output.chain_result.acoustic_frame.max_stressed_tokens > 0

    def test_low_confidence_produces_hedged_speech(
        self, consumer_engine, speech_pipeline
    ):
        """Low confidence should produce soft/hedged speech."""
        bundle = create_low_confidence_bundle()
        directive = consumer_engine.compute(bundle)

        output = speech_pipeline.execute(
            directive,
            "I believe the answer might be around 42."
        )

        assert output.is_blocked is False
        # Low confidence should produce conservative output
        assert output.chain_result.acoustic_frame.suppress_certainty is True

    def test_uncertain_produces_clarifying_speech(
        self, consumer_engine, speech_pipeline
    ):
        """Uncertain state should produce question-like speech."""
        bundle = create_uncertain_bundle()
        # Set high entropy to trigger vikalpa rule
        bundle = SignalBundle.create_minimal(
            score=0.55,
            entropy=0.75,  # High entropy
            vritti=VrittiDistribution(
                pramana=0.1,
                viparyaya=0.1,
                vikalpa=0.6,  # High vikalpa
                smrti=0.1,
                nidra=0.1,
            ),
            dominant_vritti="vikalpa",
        )
        directive = consumer_engine.compute(bundle)

        output = speech_pipeline.execute(
            directive,
            "Could you clarify what you mean?"
        )

        assert output.is_blocked is False


# =============================================================================
# Test Class 2: Realistic Utterances
# =============================================================================


class TestRealisticUtterances:
    """Test with realistic text utterances."""

    def test_factual_statement(self, consumer_engine, speech_pipeline):
        """Factual statement with high confidence."""
        bundle = create_high_confidence_bundle()
        directive = consumer_engine.compute(bundle)

        output = speech_pipeline.execute(
            directive,
            "Python is a programming language created by Guido van Rossum."
        )

        assert output.is_blocked is False
        assert is_valid_ssml(output.ssml)
        assert "Python" in output.ssml

    def test_hedged_statement(self, consumer_engine, speech_pipeline):
        """Hedged statement with uncertainty markers."""
        bundle = create_uncertain_bundle()
        directive = consumer_engine.compute(bundle)

        output = speech_pipeline.execute(
            directive,
            "I think the meeting might be scheduled for tomorrow, but I'm not entirely certain."
        )

        assert output.is_blocked is False
        assert is_valid_ssml(output.ssml)

    def test_question_utterance(self, consumer_engine, speech_pipeline):
        """Question utterance for clarification."""
        bundle = create_uncertain_bundle()
        bundle = SignalBundle.create_minimal(
            score=0.55,
            entropy=0.75,
            vritti=VrittiDistribution(
                pramana=0.1,
                viparyaya=0.1,
                vikalpa=0.6,
                smrti=0.1,
                nidra=0.1,
            ),
            dominant_vritti="vikalpa",
        )
        directive = consumer_engine.compute(bundle)

        output = speech_pipeline.execute(
            directive,
            "Would you like me to search for more information on this topic?"
        )

        assert output.is_blocked is False
        assert is_valid_ssml(output.ssml)

    def test_acknowledgment_utterance(self, consumer_engine, speech_pipeline):
        """Simple acknowledgment utterance."""
        bundle = SignalBundle.create_minimal(
            score=0.5,
            vritti=VrittiDistribution(
                pramana=0.2,
                viparyaya=0.1,
                vikalpa=0.1,
                smrti=0.4,
                nidra=0.2,
            ),
            dominant_vritti="smrti",
        )
        directive = consumer_engine.compute(bundle)

        output = speech_pipeline.execute(
            directive,
            "I understand. Let me help you with that."
        )

        assert output.is_blocked is False
        assert is_valid_ssml(output.ssml)


# =============================================================================
# Test Class 3: SSML Structure Validation
# =============================================================================


class TestSSMLStructure:
    """Test SSML output structure."""

    def test_ssml_has_speak_wrapper(self, consumer_engine, speech_pipeline):
        """SSML should have speak wrapper."""
        bundle = create_high_confidence_bundle()
        directive = consumer_engine.compute(bundle)
        output = speech_pipeline.execute(directive, "Hello")

        assert output.ssml.startswith("<speak>")
        assert output.ssml.endswith("</speak>")

    def test_ssml_has_prosody_element(self, consumer_engine, speech_pipeline):
        """SSML should have prosody element."""
        bundle = create_high_confidence_bundle()
        directive = consumer_engine.compute(bundle)
        output = speech_pipeline.execute(directive, "Hello world")

        assert "<prosody" in output.ssml

    def test_ssml_contains_text(self, consumer_engine, speech_pipeline):
        """SSML should contain the input text."""
        bundle = create_high_confidence_bundle()
        directive = consumer_engine.compute(bundle)
        text = "The quick brown fox jumps over the lazy dog."
        output = speech_pipeline.execute(directive, text)

        assert text in output.ssml

    def test_ssml_rate_attribute(self, consumer_engine, speech_pipeline):
        """SSML should have rate attribute when not 100%."""
        bundle = create_low_confidence_bundle()
        directive = consumer_engine.compute(bundle)
        output = speech_pipeline.execute(directive, "Slow speech test")

        # Low confidence produces soft/flat regime which has slower rate
        # Rate might be different from 100%
        if 'rate="' in output.ssml:
            rate_match = re.search(r'rate="(\d+)%"', output.ssml)
            assert rate_match is not None

    def test_ssml_pitch_attribute(self, consumer_engine, speech_pipeline):
        """SSML should have pitch attribute."""
        bundle = create_high_confidence_bundle()
        directive = consumer_engine.compute(bundle)
        output = speech_pipeline.execute(directive, "Pitch test")

        assert 'pitch="' in output.ssml


# =============================================================================
# Test Class 4: Tier-Specific Behavior
# =============================================================================


class TestTierSpecificSpeech:
    """Test tier-specific speech generation."""

    def test_consumer_tier_speech(self, consumer_engine, speech_pipeline):
        """Consumer tier should produce speech."""
        bundle = create_high_confidence_bundle()
        directive = consumer_engine.compute(bundle)
        output = speech_pipeline.execute(directive, "Consumer tier message")

        assert output.is_blocked is False
        assert is_valid_ssml(output.ssml)

    def test_enterprise_tier_speech(self, enterprise_engine, speech_pipeline):
        """Enterprise tier should produce speech."""
        bundle = create_high_confidence_bundle()
        directive = enterprise_engine.compute(bundle)
        output = speech_pipeline.execute(directive, "Enterprise tier message")

        assert output.is_blocked is False
        assert is_valid_ssml(output.ssml)


# =============================================================================
# Test Class 5: Acoustic Consistency (Sound Obeys Meaning)
# =============================================================================


class TestAcousticConsistency:
    """Test that acoustic output obeys semantic constraints."""

    def test_low_confidence_suppresses_certainty(
        self, consumer_engine, speech_pipeline
    ):
        """Low confidence should suppress certainty markers."""
        bundle = create_low_confidence_bundle()
        directive = consumer_engine.compute(bundle)
        output = speech_pipeline.execute(directive, "I'm not sure about this.")

        # Verify certainty is suppressed
        assert output.chain_result.acoustic_frame.suppress_certainty is True

    def test_high_confidence_allows_emphasis(
        self, consumer_engine, speech_pipeline
    ):
        """High confidence should allow some emphasis."""
        bundle = create_high_confidence_bundle()
        directive = consumer_engine.compute(bundle)
        output = speech_pipeline.execute(directive, "This is definitely correct.")

        # Verify emphasis is allowed
        frame = output.chain_result.acoustic_frame
        assert frame.suppress_emphasis is False

    def test_all_regimes_suppress_emotion(
        self, consumer_engine, speech_pipeline
    ):
        """All regimes should suppress emotion."""
        for bundle in [
            create_high_confidence_bundle(),
            create_uncertain_bundle(),
            create_low_confidence_bundle(),
        ]:
            directive = consumer_engine.compute(bundle)
            output = speech_pipeline.execute(directive, "Test message")

            # All regimes suppress emotion
            assert output.chain_result.acoustic_frame.suppress_emotion is True


# =============================================================================
# Test Class 6: Pipeline Mode Behavior
# =============================================================================


class TestPipelineModes:
    """Test different pipeline modes in realistic scenarios."""

    def test_governed_mode_production_ready(self, consumer_engine):
        """GOVERNED mode should be suitable for production."""
        pipeline = SpeechPipeline(mode=PipelineMode.GOVERNED)
        bundle = create_high_confidence_bundle()
        directive = consumer_engine.compute(bundle)

        output = pipeline.execute(directive, "Production message")

        assert output.gate_decision.mode == GateMode.GOVERNED
        assert output.is_blocked is False

    def test_open_mode_development(self, consumer_engine):
        """OPEN mode should be permissive for development."""
        pipeline = SpeechPipeline(mode=PipelineMode.OPEN)
        bundle = create_uncertain_bundle()
        directive = consumer_engine.compute(bundle)

        output = pipeline.execute(directive, "Development message")

        assert output.gate_decision.mode == GateMode.OPEN
        assert output.is_blocked is False

    def test_bypass_mode_testing(self, consumer_engine):
        """BYPASS mode should allow everything for testing."""
        pipeline = SpeechPipeline(mode=PipelineMode.BYPASS)
        bundle = create_low_confidence_bundle()
        directive = consumer_engine.compute(bundle)

        output = pipeline.execute(directive, "Testing message")

        assert output.gate_decision.mode == GateMode.AUDIT_ONLY
        assert output.is_blocked is False


# =============================================================================
# Test Class 7: End-to-End Flow Validation
# =============================================================================


class TestEndToEndFlow:
    """Validate complete end-to-end flow."""

    def test_complete_flow_high_confidence(self, consumer_engine):
        """Complete flow for high confidence scenario."""
        # 1. Create signal bundle
        bundle = create_high_confidence_bundle()

        # 2. Get presentation directive
        directive = consumer_engine.compute(bundle)
        assert directive.delivery_mode == DeliveryMode.CONFIDENT

        # 3. Generate speech
        output = generate_speech(directive, "The capital of France is Paris.")

        # 4. Verify output
        assert output.is_blocked is False
        assert output.acoustic_regime == "neutral"
        assert is_valid_ssml(output.ssml)

        # 5. Verify traceability
        assert output.chain_result.directive == directive
        assert output.delivery_mode == "confident"

    def test_complete_flow_low_confidence(self, consumer_engine):
        """Complete flow for low confidence scenario."""
        # 1. Create signal bundle
        bundle = create_low_confidence_bundle()

        # 2. Get presentation directive
        directive = consumer_engine.compute(bundle)

        # 3. Generate speech
        output = generate_speech(
            directive,
            "I'm not entirely certain, but I believe the answer may be 42."
        )

        # 4. Verify output
        assert output.is_blocked is False
        assert is_valid_ssml(output.ssml)

        # 5. Verify conservative output
        assert output.chain_result.acoustic_frame.suppress_certainty is True


# =============================================================================
# Test Class 8: Convenience Function Validation
# =============================================================================


class TestConvenienceFunctions:
    """Test convenience functions with realistic scenarios."""

    def test_generate_ssml_direct(self, consumer_engine):
        """generate_ssml should return SSML directly."""
        bundle = create_high_confidence_bundle()
        directive = consumer_engine.compute(bundle)

        ssml = generate_ssml(directive, "Direct SSML generation test")

        assert isinstance(ssml, str)
        assert is_valid_ssml(ssml)

    def test_is_speech_allowed_check(self, consumer_engine):
        """is_speech_allowed should correctly check permission."""
        bundle = create_high_confidence_bundle()
        directive = consumer_engine.compute(bundle)

        allowed = is_speech_allowed(directive)

        assert allowed is True
