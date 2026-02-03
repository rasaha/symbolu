"""
Deepgram provider adapter for Nova-2 (STT) and Aura (TTS).

Deepgram provides highly accurate speech recognition with Nova-2
and natural text-to-speech with Aura.
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


class DeepgramSTT(STTProvider):
    """
    Deepgram Nova-2 STT implementation.

    Nova-2 provides industry-leading accuracy with fast streaming
    transcription and robust noise handling.
    """

    SUPPORTED_LANGUAGES = [
        "en", "en-US", "en-GB", "en-AU", "en-IN",
        "es", "es-ES", "es-419",
        "fr", "fr-FR", "fr-CA",
        "de", "it", "pt", "pt-BR",
        "nl", "ja", "ko", "zh", "zh-CN", "zh-TW",
        "hi", "ru", "pl", "tr", "uk", "vi", "id",
        "sv", "no", "da", "fi"
    ]

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Deepgram STT.

        Args:
            api_key: Deepgram API key. If not provided, reads from
                     DEEPGRAM_API_KEY environment variable.
        """
        self.api_key = api_key or os.getenv("DEEPGRAM_API_KEY")
        if not self.api_key:
            raise ValueError(
                "Deepgram API key required. Set DEEPGRAM_API_KEY env var "
                "or pass api_key parameter."
            )
        self._client = None

    async def _get_client(self):
        """Lazy initialization of Deepgram client."""
        if self._client is None:
            try:
                from deepgram import DeepgramClient
                self._client = DeepgramClient(self.api_key)
            except ImportError:
                raise ImportError(
                    "deepgram-sdk package not installed. "
                    "Install with: pip install deepgram-sdk"
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
        Stream transcription using Deepgram Nova-2.

        Uses Deepgram's live transcription API for real-time results.
        """
        client = await self._get_client()

        try:
            from deepgram import LiveTranscriptionEvents, LiveOptions

            options = LiveOptions(
                model="nova-2",
                language=language or "en",
                sample_rate=sample_rate,
                encoding="linear16",
                punctuate=enable_punctuation,
                interim_results=True,
                endpointing=300,  # ms of silence to detect end
                smart_format=True,
            )

            connection = await client.listen.asynclive.v("1").start(options)

            # Queue for transcript events
            event_queue: asyncio.Queue[Optional[TranscriptEvent]] = asyncio.Queue()

            async def handle_transcript(self_conn, result, **kwargs):
                """Handle incoming transcript from Deepgram."""
                try:
                    channel = result.channel
                    if channel and channel.alternatives:
                        alt = channel.alternatives[0]

                        words = []
                        if hasattr(alt, 'words') and alt.words:
                            words = [
                                WordTimestamp(
                                    word=w.word,
                                    start_time=w.start,
                                    end_time=w.end,
                                    confidence=getattr(w, 'confidence', 0.9)
                                )
                                for w in alt.words
                            ]

                        event = TranscriptEvent(
                            text=alt.transcript,
                            transcript_type=(
                                TranscriptType.FINAL if result.is_final
                                else TranscriptType.PARTIAL
                            ),
                            confidence=alt.confidence if hasattr(alt, 'confidence') else 0.9,
                            words=words,
                            language=getattr(channel, 'detected_language', language),
                            is_endpoint=getattr(result, 'speech_final', result.is_final)
                        )
                        await event_queue.put(event)

                except Exception as e:
                    logger.error(f"Error handling Deepgram transcript: {e}")

            async def handle_error(self_conn, error, **kwargs):
                """Handle Deepgram errors."""
                logger.error(f"Deepgram error: {error}")

            async def handle_close(self_conn, **kwargs):
                """Handle connection close."""
                await event_queue.put(None)  # Signal end

            # Register handlers
            connection.on(LiveTranscriptionEvents.Transcript, handle_transcript)
            connection.on(LiveTranscriptionEvents.Error, handle_error)
            connection.on(LiveTranscriptionEvents.Close, handle_close)

            # Start sending audio in background
            async def send_audio():
                try:
                    async for audio_chunk in audio_stream:
                        await connection.send(audio_chunk)
                except Exception as e:
                    logger.error(f"Error sending audio to Deepgram: {e}")
                finally:
                    await connection.finish()

            send_task = asyncio.create_task(send_audio())

            try:
                # Yield events from queue
                while True:
                    event = await event_queue.get()
                    if event is None:
                        break
                    yield event

            finally:
                send_task.cancel()
                try:
                    await send_task
                except asyncio.CancelledError:
                    pass

        except Exception as e:
            if "connection" in str(e).lower() or "network" in str(e).lower():
                raise ProviderUnavailableError("deepgram", str(e))
            raise STTError(str(e), provider="deepgram")

    async def transcribe_file(
        self,
        audio_bytes: bytes,
        sample_rate: int = 16000,
        language: Optional[str] = None
    ) -> TranscriptEvent:
        """Batch transcription using Deepgram pre-recorded API."""
        client = await self._get_client()

        try:
            from deepgram import PrerecordedOptions

            options = PrerecordedOptions(
                model="nova-2",
                language=language or "en",
                punctuate=True,
                smart_format=True,
            )

            source = {"buffer": audio_bytes, "mimetype": "audio/wav"}
            response = await client.listen.asyncprerecorded.v("1").transcribe_file(
                source, options
            )

            result = response.results
            if result and result.channels:
                channel = result.channels[0]
                if channel.alternatives:
                    alt = channel.alternatives[0]

                    words = []
                    if hasattr(alt, 'words') and alt.words:
                        words = [
                            WordTimestamp(
                                word=w.word,
                                start_time=w.start,
                                end_time=w.end,
                                confidence=getattr(w, 'confidence', 0.9)
                            )
                            for w in alt.words
                        ]

                    return TranscriptEvent(
                        text=alt.transcript,
                        transcript_type=TranscriptType.FINAL,
                        confidence=alt.confidence if hasattr(alt, 'confidence') else 0.9,
                        words=words,
                        language=language,
                        is_endpoint=True
                    )

            return TranscriptEvent(
                text="",
                transcript_type=TranscriptType.FINAL,
                confidence=0.0,
                is_endpoint=True
            )

        except Exception as e:
            raise STTError(str(e), provider="deepgram")

    @property
    def supported_languages(self) -> List[str]:
        return self.SUPPORTED_LANGUAGES.copy()

    @property
    def supports_streaming(self) -> bool:
        return True


class DeepgramTTS(TTSProvider):
    """
    Deepgram Aura TTS implementation.

    Aura provides natural, fast text-to-speech synthesis.
    """

    AURA_VOICES = [
        ("aura-asteria-en", "Asteria", "en-US", "female"),
        ("aura-luna-en", "Luna", "en-US", "female"),
        ("aura-stella-en", "Stella", "en-US", "female"),
        ("aura-athena-en", "Athena", "en-US", "female"),
        ("aura-hera-en", "Hera", "en-US", "female"),
        ("aura-orion-en", "Orion", "en-US", "male"),
        ("aura-arcas-en", "Arcas", "en-US", "male"),
        ("aura-perseus-en", "Perseus", "en-US", "male"),
        ("aura-angus-en", "Angus", "en-US", "male"),
        ("aura-orpheus-en", "Orpheus", "en-US", "male"),
        ("aura-helios-en", "Helios", "en-US", "male"),
        ("aura-zeus-en", "Zeus", "en-US", "male"),
    ]

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Deepgram TTS.

        Args:
            api_key: Deepgram API key. If not provided, reads from
                     DEEPGRAM_API_KEY environment variable.
        """
        self.api_key = api_key or os.getenv("DEEPGRAM_API_KEY")
        if not self.api_key:
            raise ValueError(
                "Deepgram API key required. Set DEEPGRAM_API_KEY env var "
                "or pass api_key parameter."
            )
        self._client = None

    async def _get_client(self):
        """Lazy initialization of Deepgram client."""
        if self._client is None:
            try:
                from deepgram import DeepgramClient
                self._client = DeepgramClient(self.api_key)
            except ImportError:
                raise ImportError(
                    "deepgram-sdk package not installed. "
                    "Install with: pip install deepgram-sdk"
                )
        return self._client

    def _map_params_to_deepgram(self, params: TTSParams) -> Dict[str, Any]:
        """Map generic TTSParams to Deepgram-specific parameters."""
        return {
            "model": params.voice_id,
            # Deepgram Aura doesn't support speed/pitch directly via API
            # but we can use SSML if needed
        }

    async def synthesize_stream(
        self,
        text: str,
        params: TTSParams
    ) -> AsyncIterator[AudioChunk]:
        """
        Stream synthesis using Deepgram Aura.

        Note: Deepgram's TTS API may not support true streaming;
        this implementation buffers and yields chunks.
        """
        # Deepgram Aura doesn't have native streaming, so we synthesize
        # and yield in chunks
        audio_data = await self.synthesize(text, params)

        # Yield in chunks of ~100ms (16kHz * 2 bytes * 0.1s = 3200 bytes)
        chunk_size = 3200
        sequence = 0

        for i in range(0, len(audio_data), chunk_size):
            chunk = audio_data[i:i + chunk_size]
            is_final = (i + chunk_size) >= len(audio_data)

            yield AudioChunk(
                audio=chunk,
                sample_rate=16000,
                format="pcm",
                duration_ms=(len(chunk) / 2) / 16.0,
                is_final=is_final,
                sequence_number=sequence
            )
            sequence += 1

            # Small delay to simulate streaming
            if not is_final:
                await asyncio.sleep(0.01)

    async def synthesize(
        self,
        text: str,
        params: TTSParams
    ) -> bytes:
        """Batch synthesis using Deepgram Aura."""
        client = await self._get_client()

        try:
            from deepgram import SpeakOptions

            options = SpeakOptions(
                model=params.voice_id,
                encoding="linear16",
                sample_rate=16000,
            )

            response = await client.speak.asyncrest.v("1").stream_raw(
                {"text": text},
                options
            )

            return response.read()

        except Exception as e:
            if "connection" in str(e).lower():
                raise ProviderUnavailableError("deepgram", str(e))
            raise TTSError(str(e), provider="deepgram")

    def get_voices(self) -> List[VoiceInfo]:
        """List available Deepgram Aura voices."""
        return [
            VoiceInfo(
                voice_id=voice_id,
                name=name,
                language=language,
                gender=gender,
                description=f"Deepgram Aura {name} voice"
            )
            for voice_id, name, language, gender in self.AURA_VOICES
        ]

    @property
    def supports_streaming(self) -> bool:
        return True  # Simulated streaming

    @property
    def average_latency_ms(self) -> float:
        return 150.0  # Aura's typical latency


class DeepgramAdapter:
    """
    Combined adapter for Deepgram Nova-2 (STT) and Aura (TTS).

    Usage:
        adapter = DeepgramAdapter(api_key="...")
        stt = adapter.stt
        tts = adapter.tts
    """

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Deepgram adapter.

        Args:
            api_key: Deepgram API key. If not provided, reads from
                     DEEPGRAM_API_KEY environment variable.
        """
        self.api_key = api_key or os.getenv("DEEPGRAM_API_KEY")
        self._stt = DeepgramSTT(api_key=self.api_key)
        self._tts = DeepgramTTS(api_key=self.api_key)

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
        return "deepgram"
