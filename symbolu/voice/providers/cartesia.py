"""
Cartesia provider adapter for Sonic (TTS) and Ink (STT).

Cartesia provides ultra-low latency voice synthesis with Sonic (<90ms TTFA)
and accurate streaming transcription with Ink.
"""

import asyncio
import os
from typing import AsyncIterator, List, Optional, Dict, Any
import logging

from .base import (
    STTProvider,
    TTSProvider,
    TranscriptEvent,
    TranscriptType,
    WordTimestamp,
    TTSParams,
    AudioChunk,
    VoiceInfo,
    STTError,
    TTSError,
    ProviderUnavailableError,
)

logger = logging.getLogger(__name__)


class CartesiaSTT(STTProvider):
    """
    Cartesia Ink STT implementation.

    Ink provides fast, accurate streaming speech-to-text with
    the lowest time-to-complete-transcript among streaming models.
    """

    SUPPORTED_LANGUAGES = [
        "en", "es", "fr", "de", "it", "pt", "ja", "ko", "zh",
        "hi", "bn", "ta", "te", "mr", "gu", "kn", "ml", "pa",
        "ru", "ar", "nl", "pl", "tr", "vi", "th", "id"
    ]

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Cartesia STT.

        Args:
            api_key: Cartesia API key. If not provided, reads from
                     CARTESIA_API_KEY environment variable.
        """
        self.api_key = api_key or os.getenv("CARTESIA_API_KEY")
        if not self.api_key:
            raise ValueError(
                "Cartesia API key required. Set CARTESIA_API_KEY env var "
                "or pass api_key parameter."
            )
        self._client = None

    async def _get_client(self):
        """Lazy initialization of Cartesia client."""
        if self._client is None:
            try:
                from cartesia import AsyncCartesia
                self._client = AsyncCartesia(api_key=self.api_key)
            except ImportError:
                raise ImportError(
                    "cartesia package not installed. "
                    "Install with: pip install cartesia"
                )
        return self._client

    async def transcribe_stream(
        self,
        audio_stream: AsyncIterator[bytes],
        sample_rate: int = 16000,
        language: Optional[str] = None,
        enable_punctuation: bool = True,
        enable_word_timestamps: bool = True
    ) -> AsyncIterator[TranscriptEvent]:
        """
        Stream transcription using Cartesia Ink.

        Yields TranscriptEvents as audio is processed, including
        partial results for real-time feedback.
        """
        client = await self._get_client()

        try:
            async with client.stt.stream(
                sample_rate=sample_rate,
                language=language or "en",
                punctuate=enable_punctuation,
                word_timestamps=enable_word_timestamps
            ) as stream:
                # Send audio chunks to stream
                async def send_audio():
                    try:
                        async for audio_chunk in audio_stream:
                            await stream.send(audio_chunk)
                    finally:
                        await stream.finish()

                # Start sending in background
                send_task = asyncio.create_task(send_audio())

                try:
                    # Receive transcription events
                    async for event in stream.receive():
                        words = []
                        if hasattr(event, 'words') and event.words:
                            words = [
                                WordTimestamp(
                                    word=w.word,
                                    start_time=w.start,
                                    end_time=w.end,
                                    confidence=getattr(w, 'confidence', 0.9)
                                )
                                for w in event.words
                            ]

                        yield TranscriptEvent(
                            text=event.text,
                            transcript_type=(
                                TranscriptType.FINAL if event.is_final
                                else TranscriptType.PARTIAL
                            ),
                            confidence=getattr(event, 'confidence', 0.9),
                            words=words,
                            language=getattr(event, 'language', language),
                            is_endpoint=getattr(event, 'is_endpoint', event.is_final)
                        )

                except Exception as e:
                    logger.error(f"Cartesia STT stream error: {e}")
                    raise STTError(str(e), provider="cartesia", retriable=True)

                finally:
                    send_task.cancel()
                    try:
                        await send_task
                    except asyncio.CancelledError:
                        pass

        except Exception as e:
            if "connection" in str(e).lower():
                raise ProviderUnavailableError("cartesia", str(e))
            raise STTError(str(e), provider="cartesia")

    async def transcribe_file(
        self,
        audio_bytes: bytes,
        sample_rate: int = 16000,
        language: Optional[str] = None
    ) -> TranscriptEvent:
        """Batch transcription of complete audio."""
        client = await self._get_client()

        try:
            result = await client.stt.transcribe(
                audio=audio_bytes,
                sample_rate=sample_rate,
                language=language or "en"
            )

            words = []
            if hasattr(result, 'words') and result.words:
                words = [
                    WordTimestamp(
                        word=w.word,
                        start_time=w.start,
                        end_time=w.end,
                        confidence=getattr(w, 'confidence', 0.9)
                    )
                    for w in result.words
                ]

            return TranscriptEvent(
                text=result.text,
                transcript_type=TranscriptType.FINAL,
                confidence=getattr(result, 'confidence', 0.9),
                words=words,
                language=getattr(result, 'language', language),
                is_endpoint=True
            )

        except Exception as e:
            raise STTError(str(e), provider="cartesia")

    @property
    def supported_languages(self) -> List[str]:
        return self.SUPPORTED_LANGUAGES.copy()

    @property
    def supports_streaming(self) -> bool:
        return True


class CartesiaTTS(TTSProvider):
    """
    Cartesia Sonic TTS implementation.

    Sonic provides ultra-low latency (<90ms TTFA) text-to-speech
    with natural, expressive voices.
    """

    DEFAULT_VOICES = {
        "en-US-male": "sonic-english-male",
        "en-US-female": "sonic-english-female",
        "en-GB-male": "sonic-english-uk-male",
        "en-GB-female": "sonic-english-uk-female",
    }

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Cartesia TTS.

        Args:
            api_key: Cartesia API key. If not provided, reads from
                     CARTESIA_API_KEY environment variable.
        """
        self.api_key = api_key or os.getenv("CARTESIA_API_KEY")
        if not self.api_key:
            raise ValueError(
                "Cartesia API key required. Set CARTESIA_API_KEY env var "
                "or pass api_key parameter."
            )
        self._client = None
        self._voices_cache: Optional[List[VoiceInfo]] = None

    async def _get_client(self):
        """Lazy initialization of Cartesia client."""
        if self._client is None:
            try:
                from cartesia import AsyncCartesia
                self._client = AsyncCartesia(api_key=self.api_key)
            except ImportError:
                raise ImportError(
                    "cartesia package not installed. "
                    "Install with: pip install cartesia"
                )
        return self._client

    def _map_params_to_cartesia(self, params: TTSParams) -> Dict[str, Any]:
        """Map generic TTSParams to Cartesia-specific parameters."""
        return {
            "voice_id": params.voice_id,
            "speed": params.speed,
            # Cartesia uses different parameter names
            "emotion": self._style_to_emotion(params.style),
            **params.extra_params
        }

    def _style_to_emotion(self, style: float) -> Optional[str]:
        """Map style parameter to Cartesia emotion."""
        if style < 0.3:
            return "neutral"
        elif style < 0.6:
            return "friendly"
        else:
            return "enthusiastic"

    async def synthesize_stream(
        self,
        text: str,
        params: TTSParams
    ) -> AsyncIterator[AudioChunk]:
        """
        Stream synthesis using Cartesia Sonic.

        Yields AudioChunks with ultra-low latency (<90ms TTFA).
        """
        client = await self._get_client()
        cartesia_params = self._map_params_to_cartesia(params)

        try:
            sequence = 0
            async for chunk in client.tts.stream(
                text=text,
                voice_id=cartesia_params["voice_id"],
                speed=cartesia_params["speed"],
                output_format="pcm_16000"
            ):
                # Calculate duration: 16-bit audio at 16kHz
                # 2 bytes per sample, 16000 samples per second
                duration_ms = (len(chunk.audio) / 2) / 16.0

                yield AudioChunk(
                    audio=chunk.audio,
                    sample_rate=16000,
                    format="pcm",
                    duration_ms=duration_ms,
                    is_final=getattr(chunk, 'is_final', False),
                    sequence_number=sequence
                )
                sequence += 1

        except Exception as e:
            if "connection" in str(e).lower():
                raise ProviderUnavailableError("cartesia", str(e))
            raise TTSError(str(e), provider="cartesia")

    async def synthesize(
        self,
        text: str,
        params: TTSParams
    ) -> bytes:
        """Batch synthesis of complete audio."""
        client = await self._get_client()
        cartesia_params = self._map_params_to_cartesia(params)

        try:
            result = await client.tts.synthesize(
                text=text,
                voice_id=cartesia_params["voice_id"],
                speed=cartesia_params["speed"],
                output_format="pcm_16000"
            )
            return result.audio

        except Exception as e:
            raise TTSError(str(e), provider="cartesia")

    def get_voices(self) -> List[VoiceInfo]:
        """List available Cartesia voices."""
        if self._voices_cache is not None:
            return self._voices_cache

        # Return default voices synchronously
        # Full list would require async API call
        voices = [
            VoiceInfo(
                voice_id="sonic-english-male",
                name="Sonic English Male",
                language="en-US",
                gender="male",
                description="Natural American English male voice"
            ),
            VoiceInfo(
                voice_id="sonic-english-female",
                name="Sonic English Female",
                language="en-US",
                gender="female",
                description="Natural American English female voice"
            ),
            VoiceInfo(
                voice_id="sonic-english-uk-male",
                name="Sonic English UK Male",
                language="en-GB",
                gender="male",
                description="Natural British English male voice"
            ),
            VoiceInfo(
                voice_id="sonic-english-uk-female",
                name="Sonic English UK Female",
                language="en-GB",
                gender="female",
                description="Natural British English female voice"
            ),
        ]

        return voices

    async def get_voices_async(self) -> List[VoiceInfo]:
        """Async method to get full voice list from API."""
        client = await self._get_client()

        try:
            voices_response = await client.voices.list()
            voices = [
                VoiceInfo(
                    voice_id=v.id,
                    name=v.name,
                    language=getattr(v, 'language', 'en'),
                    gender=getattr(v, 'gender', None),
                    description=getattr(v, 'description', None),
                    preview_url=getattr(v, 'preview_url', None),
                    is_cloned=getattr(v, 'is_cloned', False)
                )
                for v in voices_response
            ]
            self._voices_cache = voices
            return voices

        except Exception as e:
            logger.warning(f"Failed to fetch Cartesia voices: {e}")
            return self.get_voices()  # Return defaults

    @property
    def supports_streaming(self) -> bool:
        return True

    @property
    def average_latency_ms(self) -> float:
        return 90.0  # Sonic's typical TTFA


class CartesiaAdapter:
    """
    Combined adapter for Cartesia Sonic (TTS) and Ink (STT).

    Usage:
        adapter = CartesiaAdapter(api_key="...")
        stt = adapter.stt
        tts = adapter.tts
    """

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Cartesia adapter.

        Args:
            api_key: Cartesia API key. If not provided, reads from
                     CARTESIA_API_KEY environment variable.
        """
        self.api_key = api_key or os.getenv("CARTESIA_API_KEY")
        self._stt = CartesiaSTT(api_key=self.api_key)
        self._tts = CartesiaTTS(api_key=self.api_key)

    @property
    def stt(self) -> STTProvider:
        """Get STT provider instance."""
        return self._stt

    @property
    def tts(self) -> TTSProvider:
        """Get TTS provider instance."""
        return self._tts

    @property
    def provider_name(self) -> str:
        return "cartesia"
