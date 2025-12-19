"""
Tests for Phase 1 & Phase 2 Modules
=====================================

Tests for the new modules added to P29-P31:
- P29: Phoneme Harmony Engine
- P30: Semantic Drift Monitor, Persona Consistency Checker, Authority Cascade Validator
- P31: Multi-Channel Adapter, Progressive Disclosure

Run with: pytest tests/test_phase_modules.py -v
"""

import pytest


# =============================================================================
# P29: PHONEME HARMONY ENGINE TESTS
# =============================================================================


class TestPhonemeHarmonyEngine:
    """Tests for the Phoneme Harmony Engine."""

    def test_import(self):
        """Test that the module can be imported."""
        from symbolu.mechanical.pipeline.p29_expression.phoneme_harmony_engine import (
            PhonemeHarmonyEngine,
            HarmonyAnalysis,
            TransitionQuality,
            analyze_harmony,
        )
        assert PhonemeHarmonyEngine is not None
        assert HarmonyAnalysis is not None

    def test_analyze_simple_text(self):
        """Test harmony analysis on simple text."""
        from symbolu.mechanical.pipeline.p29_expression.phoneme_harmony_engine import (
            PhonemeHarmonyEngine,
            TransitionQuality,
        )

        engine = PhonemeHarmonyEngine()
        result = engine.analyze("The quick brown fox jumps over the lazy dog")

        assert result.word_count == 9
        assert len(result.transitions) == 8  # n-1 transitions
        assert 0 <= result.overall_score <= 1

    def test_analyze_single_word(self):
        """Test harmony analysis on single word (no transitions)."""
        from symbolu.mechanical.pipeline.p29_expression.phoneme_harmony_engine import (
            PhonemeHarmonyEngine,
        )

        engine = PhonemeHarmonyEngine()
        result = engine.analyze("hello")

        assert result.word_count == 1
        assert len(result.transitions) == 0
        assert result.overall_score == 1.0

    def test_detect_harsh_transitions(self):
        """Test that harsh consonant clusters are detected."""
        from symbolu.mechanical.pipeline.p29_expression.phoneme_harmony_engine import (
            PhonemeHarmonyEngine,
            TransitionQuality,
        )

        engine = PhonemeHarmonyEngine()
        # "stopped" ends with 'd', "talking" starts with 't' - both stops
        result = engine.analyze("He stopped talking")

        # Should have transitions detected
        assert len(result.transitions) >= 1

    def test_to_dict(self):
        """Test conversion to dictionary."""
        from symbolu.mechanical.pipeline.p29_expression.phoneme_harmony_engine import (
            PhonemeHarmonyEngine,
        )

        engine = PhonemeHarmonyEngine()
        result = engine.analyze("Hello world")
        result_dict = result.to_dict()

        assert "text" in result_dict
        assert "overall_score" in result_dict
        assert "transitions" in result_dict

    def test_convenience_function(self):
        """Test the convenience function."""
        from symbolu.mechanical.pipeline.p29_expression.phoneme_harmony_engine import (
            analyze_harmony,
        )

        result = analyze_harmony("Simple test text")
        assert result is not None
        assert result.word_count == 3


# =============================================================================
# P30: SEMANTIC DRIFT MONITOR TESTS
# =============================================================================


class TestSemanticDriftMonitor:
    """Tests for the Semantic Drift Monitor."""

    def test_import(self):
        """Test that the module can be imported."""
        from symbolu.mechanical.pipeline.p30_verification.semantic_drift_monitor import (
            SemanticDriftMonitor,
            DriftAnalysis,
            analyze_drift,
        )
        assert SemanticDriftMonitor is not None
        assert DriftAnalysis is not None

    def test_identical_texts(self):
        """Test that identical texts have zero drift."""
        from symbolu.mechanical.pipeline.p30_verification.semantic_drift_monitor import (
            SemanticDriftMonitor,
        )

        monitor = SemanticDriftMonitor()
        text = "The quick brown fox jumps over the lazy dog."
        result = monitor.analyze(text, text)

        assert result.drift_score == 0.0
        assert result.token_preservation == 1.0
        assert result.acceptable is True

    def test_different_texts(self):
        """Test that different texts have measurable drift."""
        from symbolu.mechanical.pipeline.p30_verification.semantic_drift_monitor import (
            SemanticDriftMonitor,
        )

        monitor = SemanticDriftMonitor()
        input_text = "The project was successful and achieved great results."
        output_text = "The initiative failed and produced poor outcomes."

        result = monitor.analyze(input_text, output_text)

        assert result.drift_score > 0
        assert result.sentiment_drift > 0  # Opposite sentiments

    def test_minor_polish(self):
        """Test that minor polish has low drift."""
        from symbolu.mechanical.pipeline.p30_verification.semantic_drift_monitor import (
            SemanticDriftMonitor,
        )

        monitor = SemanticDriftMonitor()
        input_text = "The system performs well under load."
        output_text = "The system performs excellently under heavy load."

        result = monitor.analyze(input_text, output_text)

        assert result.acceptable is True
        assert result.token_preservation > 0.5

    def test_to_dict(self):
        """Test conversion to dictionary."""
        from symbolu.mechanical.pipeline.p30_verification.semantic_drift_monitor import (
            SemanticDriftMonitor,
        )

        monitor = SemanticDriftMonitor()
        result = monitor.analyze("Input text here", "Output text there")
        result_dict = result.to_dict()

        assert "drift_score" in result_dict
        assert "token_preservation" in result_dict
        assert "acceptable" in result_dict

    def test_convenience_function(self):
        """Test the convenience function."""
        from symbolu.mechanical.pipeline.p30_verification.semantic_drift_monitor import (
            analyze_drift,
        )

        result = analyze_drift("Hello world", "Hello there world")
        assert result is not None


# =============================================================================
# P30: PERSONA CONSISTENCY CHECKER TESTS
# =============================================================================


class TestPersonaConsistencyChecker:
    """Tests for the Persona Consistency Checker."""

    def test_import(self):
        """Test that the module can be imported."""
        from symbolu.mechanical.pipeline.p30_verification.persona_consistency_checker import (
            PersonaConsistencyChecker,
            PersonaConsistencyResult,
            check_persona_consistency,
        )
        assert PersonaConsistencyChecker is not None
        assert PersonaConsistencyResult is not None

    def test_warm_text(self):
        """Test detection of warm language."""
        from symbolu.mechanical.pipeline.p30_verification.persona_consistency_checker import (
            PersonaConsistencyChecker,
        )

        checker = PersonaConsistencyChecker()
        text = "I'm so happy and delighted to help you! This is wonderful!"

        result = checker.check(text, warmth_target=0.8)

        assert result.details["detected_warmth"] > 0.5

    def test_formal_text(self):
        """Test detection of formal language."""
        from symbolu.mechanical.pipeline.p30_verification.persona_consistency_checker import (
            PersonaConsistencyChecker,
        )

        checker = PersonaConsistencyChecker()
        text = "Please be advised that pursuant to your request, we shall proceed accordingly."

        result = checker.check(text, formality_target=0.8)

        assert result.details["detected_formality"] > 0.3

    def test_casual_text(self):
        """Test detection of casual language."""
        from symbolu.mechanical.pipeline.p30_verification.persona_consistency_checker import (
            PersonaConsistencyChecker,
        )

        checker = PersonaConsistencyChecker()
        text = "Hey! So basically, you're gonna wanna try this. It's awesome!"

        result = checker.check(text, formality_target=0.2)

        # Should detect casual patterns
        assert result.details["detected_formality"] < 0.6

    def test_technical_detection(self):
        """Test detection of technical terminology."""
        from symbolu.mechanical.pipeline.p30_verification.persona_consistency_checker import (
            PersonaConsistencyChecker,
        )

        checker = PersonaConsistencyChecker()
        text = "The algorithm optimizes the configuration parameters for better performance."

        result = checker.check(text, use_technical=True)

        assert result.details["has_technical"] is True

    def test_metaphor_detection(self):
        """Test detection of metaphorical language."""
        from symbolu.mechanical.pipeline.p30_verification.persona_consistency_checker import (
            PersonaConsistencyChecker,
        )

        checker = PersonaConsistencyChecker()
        text = "Life is like a journey, with paths that lead us through light and darkness."

        result = checker.check(text, use_metaphors=True)

        assert result.details["has_metaphors"] is True

    def test_to_dict(self):
        """Test conversion to dictionary."""
        from symbolu.mechanical.pipeline.p30_verification.persona_consistency_checker import (
            PersonaConsistencyChecker,
        )

        checker = PersonaConsistencyChecker()
        result = checker.check("Hello world")
        result_dict = result.to_dict()

        assert "consistency_score" in result_dict
        assert "warmth_match" in result_dict
        assert "violations" in result_dict


# =============================================================================
# P30: AUTHORITY CASCADE VALIDATOR TESTS
# =============================================================================


class TestAuthorityCascadeValidator:
    """Tests for the Authority Cascade Validator."""

    def test_import(self):
        """Test that the module can be imported."""
        from symbolu.mechanical.pipeline.p30_verification.authority_cascade_validator import (
            AuthorityCascadeValidator,
            CascadeValidation,
            AuthorityLevel,
            PHASE_AUTHORITIES,
        )
        assert AuthorityCascadeValidator is not None
        assert CascadeValidation is not None
        assert len(PHASE_AUTHORITIES) > 0

    def test_authority_levels(self):
        """Test that authority levels are properly defined."""
        from symbolu.mechanical.pipeline.p30_verification.authority_cascade_validator import (
            AuthorityLevel,
            PHASE_AUTHORITIES,
        )

        # P13 should be HIGH authority (safety)
        assert PHASE_AUTHORITIES["P13"].authority == AuthorityLevel.HIGH

        # P31 should be LOW authority (formatting)
        assert PHASE_AUTHORITIES["P31"].authority == AuthorityLevel.LOW

    def test_can_override(self):
        """Test override permission checking."""
        from symbolu.mechanical.pipeline.p30_verification.authority_cascade_validator import (
            AuthorityCascadeValidator,
        )

        validator = AuthorityCascadeValidator()

        # P13 (HIGH) can override P31 (LOW)
        assert validator.can_override("P13", "P31") is True

        # P31 (LOW) cannot override P13 (HIGH)
        assert validator.can_override("P31", "P13") is False

    def test_validate_empty_context(self):
        """Test validation with minimal context."""
        from symbolu.mechanical.pipeline.p30_verification.authority_cascade_validator import (
            AuthorityCascadeValidator,
        )

        class MockContext:
            pass

        validator = AuthorityCascadeValidator()
        ctx = MockContext()

        result = validator.validate(ctx, phases_executed=[])

        assert result is not None
        assert isinstance(result.valid, bool)

    def test_to_dict(self):
        """Test conversion to dictionary."""
        from symbolu.mechanical.pipeline.p30_verification.authority_cascade_validator import (
            AuthorityCascadeValidator,
        )

        class MockContext:
            pass

        validator = AuthorityCascadeValidator()
        result = validator.validate(MockContext(), phases_executed=["P27", "P28"])
        result_dict = result.to_dict()

        assert "valid" in result_dict
        assert "phases_checked" in result_dict
        assert "authority_chain" in result_dict


# =============================================================================
# P31: MULTI-CHANNEL ADAPTER TESTS
# =============================================================================


class TestMultiChannelAdapter:
    """Tests for the Multi-Channel Adapter."""

    def test_import(self):
        """Test that the module can be imported."""
        from symbolu.mechanical.pipeline.p31_envelope.multi_channel_adapter import (
            MultiChannelAdapter,
            ChannelType,
            ChannelOutput,
            adapt_for_channel,
        )
        assert MultiChannelAdapter is not None
        assert ChannelType is not None

    def test_adapt_chat(self):
        """Test adaptation for chat channel."""
        from symbolu.mechanical.pipeline.p31_envelope.multi_channel_adapter import (
            MultiChannelAdapter,
            ChannelType,
        )

        adapter = MultiChannelAdapter()
        text = "Hello! How can I help you today?"

        result = adapter.adapt(text, ChannelType.CHAT)

        assert result.channel_type == ChannelType.CHAT
        assert result.content_type == "text/markdown"
        assert result.formatted_text == text.strip()

    def test_adapt_api(self):
        """Test adaptation for API channel (JSON)."""
        import json
        from symbolu.mechanical.pipeline.p31_envelope.multi_channel_adapter import (
            MultiChannelAdapter,
            ChannelType,
        )

        adapter = MultiChannelAdapter()
        text = "API response content"

        result = adapter.adapt(text, ChannelType.API)

        assert result.channel_type == ChannelType.API
        assert result.content_type == "application/json"

        # Should be valid JSON
        parsed = json.loads(result.formatted_text)
        assert parsed["text"] == text
        assert parsed["success"] is True

    def test_adapt_voice_ssml(self):
        """Test adaptation for voice channel (SSML)."""
        from symbolu.mechanical.pipeline.p31_envelope.multi_channel_adapter import (
            MultiChannelAdapter,
            ChannelType,
        )

        adapter = MultiChannelAdapter()
        text = "Hello. How are you today?"

        result = adapter.adapt(text, ChannelType.VOICE)

        assert result.channel_type == ChannelType.VOICE
        assert result.content_type == "application/ssml+xml"
        assert "<speak" in result.formatted_text
        assert "</speak>" in result.formatted_text

    def test_adapt_email(self):
        """Test adaptation for email channel (HTML)."""
        from symbolu.mechanical.pipeline.p31_envelope.multi_channel_adapter import (
            MultiChannelAdapter,
            ChannelType,
        )

        adapter = MultiChannelAdapter()
        text = "Hello,\n\nThis is a test email.\n\nBest regards"

        result = adapter.adapt(text, ChannelType.EMAIL)

        assert result.channel_type == ChannelType.EMAIL
        assert result.content_type == "text/html"
        assert "<html>" in result.formatted_text
        assert "<p>" in result.formatted_text

    def test_truncation(self):
        """Test that long content is truncated."""
        from symbolu.mechanical.pipeline.p31_envelope.multi_channel_adapter import (
            MultiChannelAdapter,
            ChannelType,
            ChannelConfig,
        )

        adapter = MultiChannelAdapter()
        text = "Word " * 1000  # Very long text

        config = ChannelConfig(
            channel_type=ChannelType.CHAT,
            max_length=100,
        )

        result = adapter.adapt(text, ChannelType.CHAT, config=config)

        assert result.truncated is True
        assert len(result.formatted_text) <= 100

    def test_to_dict(self):
        """Test conversion to dictionary."""
        from symbolu.mechanical.pipeline.p31_envelope.multi_channel_adapter import (
            MultiChannelAdapter,
            ChannelType,
        )

        adapter = MultiChannelAdapter()
        result = adapter.adapt("Hello", ChannelType.CHAT)
        result_dict = result.to_dict()

        assert "channel_type" in result_dict
        assert "formatted_text" in result_dict
        assert "content_type" in result_dict


# =============================================================================
# P31: PROGRESSIVE DISCLOSURE TESTS
# =============================================================================


class TestProgressiveDisclosure:
    """Tests for the Progressive Disclosure Engine."""

    def test_import(self):
        """Test that the module can be imported."""
        from symbolu.mechanical.pipeline.p31_envelope.progressive_disclosure import (
            ProgressiveDisclosureEngine,
            ProgressiveResponse,
            DisclosureLevel,
            create_progressive_response,
        )
        assert ProgressiveDisclosureEngine is not None
        assert ProgressiveResponse is not None

    def test_process_short_text(self):
        """Test processing of short text."""
        from symbolu.mechanical.pipeline.p31_envelope.progressive_disclosure import (
            ProgressiveDisclosureEngine,
            DisclosureLevel,
        )

        engine = ProgressiveDisclosureEngine()
        text = "This is a short response."

        result = engine.process(text)

        assert result.full_response == text
        assert result.tldr is not None
        assert len(result.layers) >= 1

    def test_process_long_text(self):
        """Test processing of longer text with key points."""
        from symbolu.mechanical.pipeline.p31_envelope.progressive_disclosure import (
            ProgressiveDisclosureEngine,
            DisclosureLevel,
        )

        engine = ProgressiveDisclosureEngine()
        text = """
        First, you need to understand the fundamentals. This is important.
        Second, the implementation requires careful planning. Consider all options.
        Third, testing is crucial for success. Always verify your work.
        Finally, documentation helps others understand your code.
        """

        result = engine.process(text)

        assert result.full_response == text
        assert result.tldr is not None
        assert len(result.key_points) > 0

    def test_extract_bullet_points(self):
        """Test extraction of existing bullet points."""
        from symbolu.mechanical.pipeline.p31_envelope.progressive_disclosure import (
            ProgressiveDisclosureEngine,
        )

        engine = ProgressiveDisclosureEngine()
        text = """Here are the main points:
        • First point is important
        • Second point is critical
        • Third point matters too
        """

        result = engine.process(text)

        assert len(result.key_points) >= 2

    def test_get_content_at_level(self):
        """Test getting content at different disclosure levels."""
        from symbolu.mechanical.pipeline.p31_envelope.progressive_disclosure import (
            ProgressiveDisclosureEngine,
            DisclosureLevel,
        )

        engine = ProgressiveDisclosureEngine()
        text = "This is a comprehensive response with multiple important points."

        result = engine.process(text)

        # Should be able to get content at each level
        tldr_content = result.get_content_at_level(DisclosureLevel.TLDR)
        full_content = result.get_content_at_level(DisclosureLevel.FULL)

        assert tldr_content is not None
        assert full_content == text

    def test_content_type_detection(self):
        """Test automatic content type detection."""
        from symbolu.mechanical.pipeline.p31_envelope.progressive_disclosure import (
            ProgressiveDisclosureEngine,
            ContentType,
        )

        engine = ProgressiveDisclosureEngine()

        # Instructions
        instruction_text = "First, do this. Then, try that. Next, follow this step."
        result = engine.process(instruction_text)
        assert result.content_type == ContentType.INSTRUCTIONS

    def test_to_dict(self):
        """Test conversion to dictionary."""
        from symbolu.mechanical.pipeline.p31_envelope.progressive_disclosure import (
            ProgressiveDisclosureEngine,
        )

        engine = ProgressiveDisclosureEngine()
        result = engine.process("Hello world")
        result_dict = result.to_dict()

        assert "tldr" in result_dict
        assert "key_points" in result_dict
        assert "full_response" in result_dict
        assert "layers" in result_dict


# =============================================================================
# INTEGRATION TESTS
# =============================================================================


class TestModuleIntegration:
    """Tests for module integration with phase __init__.py files."""

    def test_p29_exports(self):
        """Test that P29 exports all new modules."""
        from symbolu.mechanical.pipeline.p29_expression import (
            PhonemeHarmonyEngine,
            analyze_harmony,
            TransitionQuality,
        )
        assert PhonemeHarmonyEngine is not None

    def test_p30_exports(self):
        """Test that P30 exports all new modules."""
        from symbolu.mechanical.pipeline.p30_verification import (
            SemanticDriftMonitor,
            analyze_drift,
            PersonaConsistencyChecker,
            check_persona_consistency,
            AuthorityCascadeValidator,
            validate_authority_cascade,
            AuthorityLevel,
        )
        assert SemanticDriftMonitor is not None
        assert PersonaConsistencyChecker is not None
        assert AuthorityCascadeValidator is not None

    def test_p31_exports(self):
        """Test that P31 exports all new modules."""
        from symbolu.mechanical.pipeline.p31_envelope import (
            MultiChannelAdapter,
            adapt_for_channel,
            ChannelType,
            ProgressiveDisclosureEngine,
            create_progressive_response,
            DisclosureLevel,
        )
        assert MultiChannelAdapter is not None
        assert ProgressiveDisclosureEngine is not None


# =============================================================================
# RUN TESTS
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
