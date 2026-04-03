"""
ElevenLabs provider adapter for TTS.

ElevenLabs provides high-quality, expressive text-to-speech with
voice cloning capabilities and multiple voice models.
"""

import asyncio
import os
from typing import AsyncIterator, List, Optional, Dict, Any
import logging

from .base import (
    TTSProvider,
    TTSParams,
    AudioChunk,
    VoiceInfo,
    TTSError,
    ProviderUnavailableError,
)

logger = logging.getLogger(__name__)


class ElevenLabsTTS(TTSProvider):
    """
    ElevenLabs TTS implementation.

    Provides high-quality voice synthesis with support for
    voice cloning and multiple voice models (Eleven Turbo, Multilingual).
    """

    # Default voices available on ElevenLabs
    DEFAULT_VOICES = [
        ("21m00Tcm4TlvDq8ikWAM", "Rachel", "en-US", "female"),
        ("AZnzlk1XvdvUeBnXmlld", "Domi", "en-US", "female"),
        ("EXAVITQu4vr4xnSDxMaL", "Bella", "en-US", "female"),
        ("ErXwobaYiN019PkySvjV", "Antoni", "en-US", "male"),
        ("MF3mGyEYCl7XYWbV9V6O", "Elli", "en-US", "female"),
        ("TxGEqnHWrfWFTfGW9XjX", "Josh", "en-US", "male"),
        ("VR6AewLTigWG4xSOukaG", "Arnold", "en-US", "male"),
        ("pNInz6obpgDQGcFmaJgB", "Adam", "en-US", "male"),
        ("yoZ06aMxZJJ28mfd3POQ", "Sam", "en-US", "male"),
    ]

    def __init__(self, api_key: Optional[str] = None, model: str = "eleven_turbo_v2"):
        """
        Initialize ElevenLabs TTS.

        Args:
            api_key: ElevenLabs API key. If not provided, reads from
                     ELEVENLABS_API_KEY environment variable.
            model: Model to use for synthesis. Options:
                   - eleven_turbo_v2: Fast, low latency (recommended)
                   - eleven_multilingual_v2: High quality, multilingual
                   - eleven_monolingual_v1: Original model
        """
        self.api_key = api_key or os.getenv("ELEVENLABS_API_KEY")
        if not self.api_key:
            raise ValueError(
                "ElevenLabs API key required. Set ELEVENLABS_API_KEY env var "
                "or pass api_key parameter."
            )
        self.model = model
        self._client = None
        self._voices_cache: Optional[List[VoiceInfo]] = None

    async def _get_client(self):
        """Lazy initialization of ElevenLabs client."""
        if self._client is None:
            try:
                from elevenlabs import AsyncElevenLabs
                self._client = AsyncElevenLabs(api_key=self.api_key)
            except ImportError:
                raise ImportError(
                    "elevenlabs package not installed. "
                    "Install with: pip install elevenlabs"
                )
        return self._client

    def _map_params_to_elevenlabs(self, params: TTSParams) -> Dict[str, Any]:
        """Map generic TTSParams to ElevenLabs-specific parameters."""
        return {
            "voice_id": params.voice_id,
            "model_id": self.model,
            "voice_settings": {
                "stability": params.stability,
                "similarity_boost": params.similarity_boost,
                "style": params.style,
                "use_speaker_boost": True,
            }
        }

    async def synthesize_stream(
        self,
        text: str,
        params: TTSParams
    ) -> AsyncIterator[AudioChunk]:
        """
        Stream synthesis using ElevenLabs.

        Uses streaming API for low-latency audio output.
        """
        client = await self._get_client()
        el_params = self._map_params_to_elevenlabs(params)

        try:
            from elevenlabs import VoiceSettings

            voice_settings = VoiceSettings(
                stability=el_params["voice_settings"]["stability"],
                similarity_boost=el_params["voice_settings"]["similarity_boost"],
                style=el_params["voice_settings"]["style"],
                use_speaker_boost=el_params["voice_settings"]["use_speaker_boost"],
            )

            sequence = 0
            async for chunk in client.text_to_speech.convert_as_stream(
                voice_id=el_params["voice_id"],
                text=text,
                model_id=el_params["model_id"],
                voice_settings=voice_settings,
                output_format="pcm_16000",
            ):
                # ElevenLabs returns raw audio bytes
                if chunk:
                    duration_ms = (len(chunk) / 2) / 16.0

                    yield AudioChunk(
                        audio=chunk,
                        sample_rate=16000,
                        format="pcm",
                        duration_ms=duration_ms,
                        is_final=False,
                        sequence_number=sequence
                    )
                    sequence += 1

            # Yield final empty chunk to signal completion
            yield AudioChunk(
                audio=b"",
                sample_rate=16000,
                format="pcm",
                duration_ms=0,
                is_final=True,
                sequence_number=sequence
            )

        except Exception as e:
            if "connection" in str(e).lower() or "timeout" in str(e).lower():
                raise ProviderUnavailableError("elevenlabs", str(e))
            raise TTSError(str(e), provider="elevenlabs")

    async def synthesize(
        self,
        text: str,
        params: TTSParams
    ) -> bytes:
        """Batch synthesis using ElevenLabs."""
        client = await self._get_client()
        el_params = self._map_params_to_elevenlabs(params)

        try:
            from elevenlabs import VoiceSettings

            voice_settings = VoiceSettings(
                stability=el_params["voice_settings"]["stability"],
                similarity_boost=el_params["voice_settings"]["similarity_boost"],
                style=el_params["voice_settings"]["style"],
                use_speaker_boost=el_params["voice_settings"]["use_speaker_boost"],
            )

            audio = await client.text_to_speech.convert(
                voice_id=el_params["voice_id"],
                text=text,
                model_id=el_params["model_id"],
                voice_settings=voice_settings,
                output_format="pcm_16000",
            )

            # Collect all audio bytes
            audio_bytes = b""
            async for chunk in audio:
                audio_bytes += chunk

            return audio_bytes

        except Exception as e:
            raise TTSError(str(e), provider="elevenlabs")

    def get_voices(self) -> List[VoiceInfo]:
        """List available ElevenLabs voices (default set)."""
        if self._voices_cache is not None:
            return self._voices_cache

        return [
            VoiceInfo(
                voice_id=voice_id,
                name=name,
                language=language,
                gender=gender,
                description=f"ElevenLabs {name} voice"
            )
            for voice_id, name, language, gender in self.DEFAULT_VOICES
        ]

    async def get_voices_async(self) -> List[VoiceInfo]:
        """Async method to get full voice list from API."""
        client = await self._get_client()

        try:
            response = await client.voices.get_all()

            voices = [
                VoiceInfo(
                    voice_id=v.voice_id,
                    name=v.name,
                    language=getattr(v, 'language', 'en'),
                    gender=getattr(v.labels, 'gender', None) if v.labels else None,
                    description=getattr(v, 'description', None),
                    preview_url=getattr(v, 'preview_url', None),
                    is_cloned=v.category == "cloned" if hasattr(v, 'category') else False,
                    extra_metadata={
                        "category": getattr(v, 'category', None),
                        "labels": dict(v.labels) if v.labels else {},
                    }
                )
                for v in response.voices
            ]
            self._voices_cache = voices
            return voices

        except Exception as e:
            logger.warning(f"Failed to fetch ElevenLabs voices: {e}")
            return self.get_voices()

    @property
    def supports_streaming(self) -> bool:
        return True

    @property
    def average_latency_ms(self) -> float:
        # Turbo v2 is faster than multilingual
        if "turbo" in self.model:
            return 120.0
        return 200.0


class ElevenLabsAdapter:
    """
    Adapter for ElevenLabs TTS.

    Note: ElevenLabs doesn't provide STT, so only TTS is available.

    Usage:
        adapter = ElevenLabsAdapter(api_key="...")
        tts = adapter.tts
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "eleven_turbo_v2"
    ):
        """
        Initialize ElevenLabs adapter.

        Args:
            api_key: ElevenLabs API key. If not provided, reads from
                     ELEVENLABS_API_KEY environment variable.
            model: TTS model to use.
        """
        self.api_key = api_key or os.getenv("ELEVENLABS_API_KEY")
        self._tts = ElevenLabsTTS(api_key=self.api_key, model=model)

    @property
    def stt(self):
        """ElevenLabs doesn't provide STT."""
        raise NotImplementedError(
            "ElevenLabs doesn't provide STT. Use Cartesia or Deepgram for STT."
        )

    @property
    def tts(self) -> TTSProvider:
        """Get TTS provider instance."""
        return self._tts

    @property
    def provider_name(self) -> str:
        return "elevenlabs"
