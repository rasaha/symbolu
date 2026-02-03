"""
Voice Provider Interface Tests
==============================

Tests that verify voice provider interfaces are correctly defined
and that all providers implement the required methods.
"""

import pytest
from abc import ABC
from dataclasses import dataclass

from symbolu.voice.providers.base import (
    STTProvider,
    TTSProvider,
    TranscriptEvent,
    TranscriptType,
    WordTimestamp,
    TTSParams,
    AudioChunk,
    VoiceInfo,
    ProviderError,
    STTError,
    TTSError,
    ProviderUnavailableError,
)


class TestSTTProviderInterface:
    """Tests for STTProvider ABC."""

    def test_is_abstract_base_class(self):
        """Verify STTProvider is an ABC."""
        assert issubclass(STTProvider, ABC)

    def test_cannot_instantiate_directly(self):
        """Verify STTProvider cannot be instantiated."""
        with pytest.raises(TypeError):
            STTProvider()

    def test_requires_transcribe_stream_method(self):
        """Verify transcribe_stream method is abstract."""
        assert hasattr(STTProvider, "transcribe_stream")

    def test_requires_transcribe_file_method(self):
        """Verify transcribe_file method is abstract."""
        assert hasattr(STTProvider, "transcribe_file")

    def test_requires_supported_languages_property(self):
        """Verify supported_languages property is abstract."""
        assert hasattr(STTProvider, "supported_languages")

    def test_requires_supports_streaming_property(self):
        """Verify supports_streaming property is abstract."""
        assert hasattr(STTProvider, "supports_streaming")

    def test_has_provider_name_property(self):
        """Verify provider_name has default implementation."""
        # Create minimal concrete implementation
        class ConcreteSTT(STTProvider):
            async def transcribe_stream(self, audio_stream, **kwargs):
                yield TranscriptEvent(
                    text="test",
                    transcript_type=TranscriptType.FINAL,
                    confidence=1.0
                )

            async def transcribe_file(self, audio_bytes, **kwargs):
                return TranscriptEvent(
                    text="test",
                    transcript_type=TranscriptType.FINAL,
                    confidence=1.0
                )

            @property
            def supported_languages(self):
                return ["en"]

            @property
            def supports_streaming(self):
                return True

        provider = ConcreteSTT()
        assert provider.provider_name == "ConcreteSTT"


class TestTTSProviderInterface:
    """Tests for TTSProvider ABC."""

    def test_is_abstract_base_class(self):
        """Verify TTSProvider is an ABC."""
        assert issubclass(TTSProvider, ABC)

    def test_cannot_instantiate_directly(self):
        """Verify TTSProvider cannot be instantiated."""
        with pytest.raises(TypeError):
            TTSProvider()

    def test_requires_synthesize_stream_method(self):
        """Verify synthesize_stream method is abstract."""
        assert hasattr(TTSProvider, "synthesize_stream")

    def test_requires_synthesize_method(self):
        """Verify synthesize method is abstract."""
        assert hasattr(TTSProvider, "synthesize")

    def test_requires_get_voices_method(self):
        """Verify get_voices method is abstract."""
        assert hasattr(TTSProvider, "get_voices")

    def test_requires_supports_streaming_property(self):
        """Verify supports_streaming property is abstract."""
        assert hasattr(TTSProvider, "supports_streaming")

    def test_requires_average_latency_ms_property(self):
        """Verify average_latency_ms property is abstract."""
        assert hasattr(TTSProvider, "average_latency_ms")


class TestTranscriptEvent:
    """Tests for TranscriptEvent dataclass."""

    def test_create_basic_event(self):
        """Verify basic event creation."""
        event = TranscriptEvent(
            text="Hello world",
            transcript_type=TranscriptType.FINAL,
            confidence=0.95
        )
        assert event.text == "Hello world"
        assert event.transcript_type == TranscriptType.FINAL
        assert event.confidence == 0.95
        assert event.words == []
        assert event.is_endpoint is False

    def test_word_count_property(self):
        """Verify word_count property."""
        event = TranscriptEvent(
            text="Hello world test",
            transcript_type=TranscriptType.FINAL,
            confidence=0.9
        )
        assert event.word_count == 3

    def test_duration_ms_with_timestamps(self):
        """Verify duration_ms calculation with word timestamps."""
        words = [
            WordTimestamp(word="Hello", start_time=0.0, end_time=0.5, confidence=0.9),
            WordTimestamp(word="world", start_time=0.5, end_time=1.0, confidence=0.9),
        ]
        event = TranscriptEvent(
            text="Hello world",
            transcript_type=TranscriptType.FINAL,
            confidence=0.9,
            words=words
        )
        assert event.duration_ms == 1000.0  # 1 second = 1000ms

    def test_duration_ms_without_timestamps(self):
        """Verify duration_ms returns None without timestamps."""
        event = TranscriptEvent(
            text="Hello world",
            transcript_type=TranscriptType.FINAL,
            confidence=0.9
        )
        assert event.duration_ms is None


class TestWordTimestamp:
    """Tests for WordTimestamp dataclass."""

    def test_create_timestamp(self):
        """Verify timestamp creation."""
        ts = WordTimestamp(
            word="hello",
            start_time=0.5,
            end_time=0.8,
            confidence=0.95
        )
        assert ts.word == "hello"
        assert ts.start_time == 0.5
        assert ts.end_time == 0.8
        assert ts.confidence == 0.95

    def test_duration_ms_method(self):
        """Verify duration_ms calculation."""
        ts = WordTimestamp(
            word="hello",
            start_time=0.5,
            end_time=0.8,
            confidence=0.95
        )
        assert ts.duration_ms() == pytest.approx(300.0)  # 0.3 seconds = 300ms


class TestTTSParams:
    """Tests for TTSParams dataclass."""

    def test_create_basic_params(self):
        """Verify basic params creation."""
        params = TTSParams(voice_id="test-voice")
        assert params.voice_id == "test-voice"
        assert params.speed == 1.0
        assert params.pitch_shift == 0.0
        assert params.stability == 0.7
        assert params.style == 0.5

    def test_clamping_speed(self):
        """Verify speed is clamped to valid range."""
        params_low = TTSParams(voice_id="test", speed=0.1)
        assert params_low.speed == 0.5  # Clamped to min

        params_high = TTSParams(voice_id="test", speed=5.0)
        assert params_high.speed == 2.0  # Clamped to max

    def test_clamping_pitch_shift(self):
        """Verify pitch_shift is clamped to valid range."""
        params_low = TTSParams(voice_id="test", pitch_shift=-20.0)
        assert params_low.pitch_shift == -12.0  # Clamped to min

        params_high = TTSParams(voice_id="test", pitch_shift=20.0)
        assert params_high.pitch_shift == 12.0  # Clamped to max

    def test_clamping_stability(self):
        """Verify stability is clamped to valid range."""
        params_low = TTSParams(voice_id="test", stability=-0.5)
        assert params_low.stability == 0.0  # Clamped to min

        params_high = TTSParams(voice_id="test", stability=1.5)
        assert params_high.stability == 1.0  # Clamped to max

    def test_with_speed_method(self):
        """Verify with_speed returns new instance."""
        original = TTSParams(voice_id="test", speed=1.0)
        modified = original.with_speed(1.5)

        assert original.speed == 1.0  # Original unchanged
        assert modified.speed == 1.5
        assert modified.voice_id == "test"

    def test_with_stability_method(self):
        """Verify with_stability returns new instance."""
        original = TTSParams(voice_id="test", stability=0.7)
        modified = original.with_stability(0.9)

        assert original.stability == 0.7  # Original unchanged
        assert modified.stability == 0.9


class TestAudioChunk:
    """Tests for AudioChunk dataclass."""

    def test_create_chunk(self):
        """Verify chunk creation."""
        chunk = AudioChunk(
            audio=b"\x00" * 100,
            sample_rate=16000,
            format="pcm",
            duration_ms=50.0
        )
        assert len(chunk) == 100
        assert chunk.sample_rate == 16000
        assert chunk.format == "pcm"
        assert chunk.duration_ms == 50.0
        assert chunk.is_final is False

    def test_len_returns_audio_length(self):
        """Verify __len__ returns audio bytes length."""
        chunk = AudioChunk(
            audio=b"\x00" * 256,
            sample_rate=16000,
            format="pcm",
            duration_ms=8.0
        )
        assert len(chunk) == 256


class TestVoiceInfo:
    """Tests for VoiceInfo dataclass."""

    def test_create_voice_info(self):
        """Verify voice info creation."""
        info = VoiceInfo(
            voice_id="test-voice",
            name="Test Voice",
            language="en-US",
            gender="female"
        )
        assert info.voice_id == "test-voice"
        assert info.name == "Test Voice"
        assert info.language == "en-US"
        assert info.gender == "female"
        assert info.is_cloned is False


class TestProviderExceptions:
    """Tests for provider exceptions."""

    def test_provider_error(self):
        """Verify ProviderError creation."""
        error = ProviderError("Test error", provider="test", retriable=True)
        assert str(error) == "Test error"
        assert error.provider == "test"
        assert error.retriable is True

    def test_stt_error(self):
        """Verify STTError is subclass of ProviderError."""
        error = STTError("STT failed", provider="cartesia")
        assert isinstance(error, ProviderError)
        assert error.provider == "cartesia"

    def test_tts_error(self):
        """Verify TTSError is subclass of ProviderError."""
        error = TTSError("TTS failed", provider="elevenlabs")
        assert isinstance(error, ProviderError)
        assert error.provider == "elevenlabs"

    def test_provider_unavailable_error(self):
        """Verify ProviderUnavailableError creation."""
        error = ProviderUnavailableError("cartesia", "Connection timeout")
        assert "cartesia" in str(error)
        assert error.retriable is True
