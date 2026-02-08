"""
Barge-In Handler Tests
======================

Tests for barge-in detection and handling with various strategies.
"""

import pytest
from datetime import datetime, timedelta

from symbolu.voice.orchestration.barge_in import (
    BargeInStrategy,
    BargeInConfig,
    BargeInHandler,
    AdaptiveBargeInHandler,
)
from symbolu.voice.providers.base import (
    TranscriptEvent,
    TranscriptType,
    WordTimestamp,
)


class TestBargeInConfig:
    """Tests for BargeInConfig dataclass."""

    def test_default_config(self):
        """Verify default configuration values."""
        config = BargeInConfig()

        assert config.default_strategy == BargeInStrategy.CONFIRMED
        assert config.word_threshold == 2
        assert config.duration_threshold_ms == 500
        assert config.confidence_threshold == 0.6

    def test_custom_config(self):
        """Verify custom configuration."""
        config = BargeInConfig(
            default_strategy=BargeInStrategy.IMMEDIATE,
            word_threshold=1,
            duration_threshold_ms=300
        )

        assert config.default_strategy == BargeInStrategy.IMMEDIATE
        assert config.word_threshold == 1
        assert config.duration_threshold_ms == 300


class TestBargeInHandler:
    """Tests for BargeInHandler."""

    def create_transcript_event(
        self,
        text: str,
        is_final: bool = False,
        confidence: float = 0.9,
        duration_ms: float = None
    ) -> TranscriptEvent:
        """Helper to create transcript events."""
        words = []
        if duration_ms:
            # Create word timestamps spanning the duration
            word_list = text.split()
            if word_list:
                time_per_word = (duration_ms / 1000) / len(word_list)
                for i, word in enumerate(word_list):
                    words.append(WordTimestamp(
                        word=word,
                        start_time=i * time_per_word,
                        end_time=(i + 1) * time_per_word,
                        confidence=confidence
                    ))

        return TranscriptEvent(
            text=text,
            transcript_type=TranscriptType.FINAL if is_final else TranscriptType.PARTIAL,
            confidence=confidence,
            words=words,
            is_endpoint=is_final
        )

    def test_immediate_strategy_any_speech(self):
        """Verify IMMEDIATE strategy triggers on any speech."""
        handler = BargeInHandler(BargeInConfig(
            default_strategy=BargeInStrategy.IMMEDIATE
        ))

        event = self.create_transcript_event("Hi")
        assert handler.should_interrupt(event) is True

    def test_immediate_strategy_empty_speech(self):
        """Verify IMMEDIATE strategy doesn't trigger on empty speech."""
        handler = BargeInHandler(BargeInConfig(
            default_strategy=BargeInStrategy.IMMEDIATE
        ))

        event = self.create_transcript_event("")
        assert handler.should_interrupt(event) is False

    def test_confirmed_strategy_word_threshold(self):
        """Verify CONFIRMED strategy uses word threshold."""
        handler = BargeInHandler(BargeInConfig(
            default_strategy=BargeInStrategy.CONFIRMED,
            word_threshold=2
        ))

        # Single word - should not interrupt
        event1 = self.create_transcript_event("Wait")
        assert handler.should_interrupt(event1) is False

        # Two words - should interrupt
        event2 = self.create_transcript_event("Wait stop")
        assert handler.should_interrupt(event2) is True

    def test_confirmed_strategy_duration_threshold(self):
        """Verify CONFIRMED strategy uses duration threshold."""
        handler = BargeInHandler(BargeInConfig(
            default_strategy=BargeInStrategy.CONFIRMED,
            word_threshold=10,  # High word threshold
            duration_threshold_ms=300
        ))

        # Short duration - should not interrupt
        event1 = self.create_transcript_event("W", duration_ms=100)
        assert handler.should_interrupt(event1) is False

        # Long duration - should interrupt
        event2 = self.create_transcript_event("W", duration_ms=500)
        assert handler.should_interrupt(event2) is True

    def test_ignore_strategy(self):
        """Verify IGNORE strategy never interrupts."""
        handler = BargeInHandler(BargeInConfig(
            default_strategy=BargeInStrategy.IGNORE
        ))

        event = self.create_transcript_event("Stop everything now please")
        assert handler.should_interrupt(event) is False

    def test_smart_strategy_critical_keywords(self):
        """Verify SMART strategy detects critical keywords."""
        handler = BargeInHandler(BargeInConfig(
            default_strategy=BargeInStrategy.SMART
        ))

        # Critical keyword - should interrupt
        event1 = self.create_transcript_event("stop")
        assert handler.should_interrupt(event1) is True

        event2 = self.create_transcript_event("wait")
        assert handler.should_interrupt(event2) is True

        event3 = self.create_transcript_event("cancel")
        assert handler.should_interrupt(event3) is True

    def test_smart_strategy_continuation_keywords(self):
        """Verify SMART strategy ignores continuation keywords."""
        handler = BargeInHandler(BargeInConfig(
            default_strategy=BargeInStrategy.SMART,
            word_threshold=5  # High threshold so only keywords matter
        ))

        # Continuation keywords - should not interrupt
        event1 = self.create_transcript_event("and")
        assert handler.should_interrupt(event1) is False

        event2 = self.create_transcript_event("um")
        assert handler.should_interrupt(event2) is False

    def test_critical_response_priority(self):
        """Verify critical responses can't be interrupted."""
        handler = BargeInHandler(BargeInConfig(
            default_strategy=BargeInStrategy.IMMEDIATE
        ))

        event = self.create_transcript_event("Stop everything")
        result = handler.should_interrupt(event, response_priority="critical")
        assert result is False

    def test_override_strategy(self):
        """Verify strategy can be overridden per-call."""
        handler = BargeInHandler(BargeInConfig(
            default_strategy=BargeInStrategy.IGNORE
        ))

        event = self.create_transcript_event("Hi there")

        # Default (IGNORE) - should not interrupt
        assert handler.should_interrupt(event) is False

        # Override to IMMEDIATE - should interrupt
        assert handler.should_interrupt(
            event,
            current_strategy=BargeInStrategy.IMMEDIATE
        ) is True

    def test_continuation_context_generation(self):
        """Verify continuation context is generated correctly."""
        handler = BargeInHandler()

        context = handler.get_continuation_context(
            interrupted_text="The weather today is sunny with a high of 75 degrees",
            spoken_portion="The weather today is"
        )

        assert "[Interrupted" in context
        assert "sunny with a high" in context

    def test_continuation_context_empty_remaining(self):
        """Verify empty context when nothing remains."""
        handler = BargeInHandler()

        context = handler.get_continuation_context(
            interrupted_text="Complete message",
            spoken_portion="Complete message"
        )

        assert context == ""

    def test_classify_interruption_question(self):
        """Verify question interruption classification."""
        handler = BargeInHandler()

        event = self.create_transcript_event("What do you mean?")
        classification, confidence = handler.classify_interruption(event)

        assert classification == "question"
        assert confidence > 0.5

    def test_classify_interruption_agreement(self):
        """Verify agreement interruption classification."""
        handler = BargeInHandler()

        event = self.create_transcript_event("Yes, that's right")
        classification, confidence = handler.classify_interruption(event)

        assert classification == "agreement"

    def test_classify_interruption_disagreement(self):
        """Verify disagreement interruption classification."""
        handler = BargeInHandler()

        event = self.create_transcript_event("No, that's wrong")
        classification, confidence = handler.classify_interruption(event)

        assert classification == "disagreement"

    def test_classify_interruption_redirect(self):
        """Verify redirect interruption classification."""
        handler = BargeInHandler()

        event = self.create_transcript_event("Actually, I want something else")
        classification, confidence = handler.classify_interruption(event)

        assert classification == "redirect"

    def test_classify_interruption_unknown(self):
        """Verify unknown interruption classification."""
        handler = BargeInHandler()

        event = self.create_transcript_event("xyz")
        classification, confidence = handler.classify_interruption(event)

        assert classification == "unknown"
        assert confidence < 0.5

    def test_record_agent_speech_end(self):
        """Verify agent speech end recording."""
        handler = BargeInHandler()
        handler.record_agent_speech_end()

        assert handler._last_agent_speech_end is not None

    def test_reset(self):
        """Verify handler reset."""
        handler = BargeInHandler()
        handler.record_agent_speech_end()
        handler._accumulated_text = "test"

        handler.reset()

        assert handler._last_agent_speech_end is None
        assert handler._accumulated_text == ""


class TestAdaptiveBargeInHandler:
    """Tests for AdaptiveBargeInHandler with learning."""

    def test_record_valid_interruption(self):
        """Verify valid interruption feedback."""
        handler = AdaptiveBargeInHandler()

        handler.record_interruption_feedback(was_valid=True)

        assert handler._total_interruptions == 1
        assert handler._false_positive_count == 0

    def test_record_false_positive(self):
        """Verify false positive feedback adjusts thresholds."""
        handler = AdaptiveBargeInHandler()

        handler.record_interruption_feedback(was_valid=False)

        assert handler._total_interruptions == 1
        assert handler._false_positive_count == 1
        assert handler._word_threshold_adjustment > 0
        assert handler._duration_threshold_adjustment > 0

    def test_effective_word_threshold(self):
        """Verify effective threshold includes adjustments."""
        config = BargeInConfig(word_threshold=2)
        handler = AdaptiveBargeInHandler(config)

        original = handler.effective_word_threshold
        assert original == 2

        handler.record_interruption_feedback(was_valid=False)
        adjusted = handler.effective_word_threshold

        assert adjusted > original

    def test_false_positive_rate(self):
        """Verify false positive rate calculation."""
        handler = AdaptiveBargeInHandler()

        # No interruptions yet
        assert handler.false_positive_rate == 0.0

        # 2 valid, 1 invalid
        handler.record_interruption_feedback(was_valid=True)
        handler.record_interruption_feedback(was_valid=True)
        handler.record_interruption_feedback(was_valid=False)

        assert handler.false_positive_rate == pytest.approx(1/3)

    def test_interruption_type_tracking(self):
        """Verify interruption type tracking."""
        handler = AdaptiveBargeInHandler()

        handler.record_interruption_feedback(
            was_valid=True,
            interruption_type="question"
        )
        handler.record_interruption_feedback(
            was_valid=True,
            interruption_type="question"
        )
        handler.record_interruption_feedback(
            was_valid=True,
            interruption_type="redirect"
        )

        assert handler._interruption_types["question"] == 2
        assert handler._interruption_types["redirect"] == 1
