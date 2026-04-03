"""
Base interfaces for voice providers (STT and TTS).

This module defines the abstract interfaces that all voice providers must implement,
enabling provider-agnostic voice agent development.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import AsyncIterator, Dict, List, Optional, Any


class TranscriptType(Enum):
    """Type of transcription event."""
    PARTIAL = "partial"  # Interim result, may change
    FINAL = "final"      # Final result, won't change


@dataclass
class WordTimestamp:
    """Word-level timing information from STT."""
    word: str
    start_time: float  # seconds from audio start
    end_time: float    # seconds from audio start
    confidence: float  # 0.0 to 1.0

    def duration_ms(self) -> float:
        """Get word duration in milliseconds."""
        return (self.end_time - self.start_time) * 1000


@dataclass
class TranscriptEvent:
    """
    Streaming transcription event from STT provider.

    Attributes:
        text: The transcribed text
        transcript_type: Whether this is a partial or final result
        confidence: Overall confidence score (0.0 to 1.0)
        words: Word-level timestamps if available
        language: Detected language code
        is_endpoint: True if this marks the end of an utterance
    """
    text: str
    transcript_type: TranscriptType
    confidence: float
    words: List[WordTimestamp] = field(default_factory=list)
    language: Optional[str] = None
    is_endpoint: bool = False
    timestamp: datetime = field(default_factory=datetime.utcnow)

    @property
    def word_count(self) -> int:
        """Get number of words in transcript."""
        return len(self.text.split())

    @property
    def duration_ms(self) -> Optional[float]:
        """Get total duration in milliseconds if word timestamps available."""
        if not self.words:
            return None
        return (self.words[-1].end_time - self.words[0].start_time) * 1000


@dataclass
class TTSParams:
    """
    TTS synthesis parameters.

    These parameters control voice characteristics and are mapped
    from P10 acoustic parameters and coherence state.
    """
    voice_id: str
    speed: float = 1.0           # 0.5 to 2.0 (1.0 = normal)
    pitch_shift: float = 0.0     # semitones, -12 to +12
    stability: float = 0.7       # 0.0 to 1.0 (voice consistency)
    similarity_boost: float = 0.75  # Voice similarity/clarity
    style: float = 0.5           # 0.0 to 1.0 (expressiveness)

    # Provider-specific extensions
    extra_params: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        # Clamp values to valid ranges
        self.speed = max(0.5, min(2.0, self.speed))
        self.pitch_shift = max(-12.0, min(12.0, self.pitch_shift))
        self.stability = max(0.0, min(1.0, self.stability))
        self.similarity_boost = max(0.0, min(1.0, self.similarity_boost))
        self.style = max(0.0, min(1.0, self.style))

    def with_speed(self, speed: float) -> "TTSParams":
        """Return new TTSParams with modified speed."""
        return TTSParams(
            voice_id=self.voice_id,
            speed=speed,
            pitch_shift=self.pitch_shift,
            stability=self.stability,
            similarity_boost=self.similarity_boost,
            style=self.style,
            extra_params=self.extra_params.copy()
        )

    def with_stability(self, stability: float) -> "TTSParams":
        """Return new TTSParams with modified stability."""
        return TTSParams(
            voice_id=self.voice_id,
            speed=self.speed,
            pitch_shift=self.pitch_shift,
            stability=stability,
            similarity_boost=self.similarity_boost,
            style=self.style,
            extra_params=self.extra_params.copy()
        )


@dataclass
class AudioChunk:
    """
    Streaming audio output chunk from TTS.

    Attributes:
        audio: Raw audio bytes
        sample_rate: Audio sample rate in Hz
        format: Audio format (pcm, opus, mp3)
        duration_ms: Duration of this chunk in milliseconds
        is_final: True if this is the last chunk
    """
    audio: bytes
    sample_rate: int
    format: str  # "pcm", "opus", "mp3"
    duration_ms: float
    is_final: bool = False
    sequence_number: int = 0

    def __len__(self) -> int:
        """Return length of audio data in bytes."""
        return len(self.audio)


@dataclass
class VoiceInfo:
    """Information about an available voice."""
    voice_id: str
    name: str
    language: str
    gender: Optional[str] = None
    description: Optional[str] = None
    preview_url: Optional[str] = None
    is_cloned: bool = False
    extra_metadata: Dict[str, Any] = field(default_factory=dict)


class STTProvider(ABC):
    """
    Abstract Speech-to-Text provider interface.

    All STT providers (Cartesia Ink, Deepgram Nova, Whisper, etc.)
    must implement this interface for provider-agnostic transcription.
    """

    @abstractmethod
    async def transcribe_stream(
        self,
        audio_stream: AsyncIterator[bytes],
        sample_rate: int = 16000,
        language: Optional[str] = None,
        enable_punctuation: bool = True,
        enable_word_timestamps: bool = True
    ) -> AsyncIterator[TranscriptEvent]:
        """
        Stream audio and yield transcription events.

        Args:
            audio_stream: Async iterator yielding audio chunks (PCM bytes)
            sample_rate: Audio sample rate in Hz (default 16000)
            language: Language code (e.g., "en", "es") or None for auto-detect
            enable_punctuation: Whether to add punctuation to transcripts
            enable_word_timestamps: Whether to include word-level timestamps

        Yields:
            TranscriptEvent objects as transcription progresses
        """
        pass

    @abstractmethod
    async def transcribe_file(
        self,
        audio_bytes: bytes,
        sample_rate: int = 16000,
        language: Optional[str] = None
    ) -> TranscriptEvent:
        """
        Transcribe complete audio file (batch mode).

        Args:
            audio_bytes: Complete audio data
            sample_rate: Audio sample rate in Hz
            language: Language code or None for auto-detect

        Returns:
            TranscriptEvent with final transcription
        """
        pass

    @property
    @abstractmethod
    def supported_languages(self) -> List[str]:
        """List of supported language codes (e.g., ['en', 'es', 'fr'])."""
        pass

    @property
    @abstractmethod
    def supports_streaming(self) -> bool:
        """Whether this provider supports streaming transcription."""
        pass

    @property
    def provider_name(self) -> str:
        """Name of this provider for logging/metrics."""
        return self.__class__.__name__


class TTSProvider(ABC):
    """
    Abstract Text-to-Speech provider interface.

    All TTS providers (Cartesia Sonic, ElevenLabs, PlayHT, etc.)
    must implement this interface for provider-agnostic synthesis.
    """

    @abstractmethod
    async def synthesize_stream(
        self,
        text: str,
        params: TTSParams
    ) -> AsyncIterator[AudioChunk]:
        """
        Stream synthesized audio chunks.

        Args:
            text: Text to synthesize
            params: TTS parameters controlling voice characteristics

        Yields:
            AudioChunk objects as synthesis progresses
        """
        pass

    @abstractmethod
    async def synthesize(
        self,
        text: str,
        params: TTSParams
    ) -> bytes:
        """
        Synthesize complete audio (batch mode).

        Args:
            text: Text to synthesize
            params: TTS parameters

        Returns:
            Complete audio as bytes
        """
        pass

    @abstractmethod
    def get_voices(self) -> List[VoiceInfo]:
        """
        List available voices.

        Returns:
            List of VoiceInfo objects describing available voices
        """
        pass

    @property
    @abstractmethod
    def supports_streaming(self) -> bool:
        """Whether this provider supports streaming synthesis."""
        pass

    @property
    @abstractmethod
    def average_latency_ms(self) -> float:
        """Typical time-to-first-audio in milliseconds."""
        pass

    @property
    def provider_name(self) -> str:
        """Name of this provider for logging/metrics."""
        return self.__class__.__name__


class ProviderError(Exception):
    """Base exception for provider errors."""

    def __init__(self, message: str, provider: str, retriable: bool = False):
        super().__init__(message)
        self.provider = provider
        self.retriable = retriable


class STTError(ProviderError):
    """Exception for STT-specific errors."""
    pass


class TTSError(ProviderError):
    """Exception for TTS-specific errors."""
    pass


class ProviderUnavailableError(ProviderError):
    """Exception when a provider is unavailable."""

    def __init__(self, provider: str, reason: str = ""):
        super().__init__(
            f"Provider {provider} is unavailable: {reason}",
            provider=provider,
            retriable=True
        )
