"""
Voice Providers Package.

This package provides a provider-agnostic abstraction layer for
voice services (STT and TTS) with support for multiple providers:

- Cartesia (Sonic TTS, Ink STT)
- Deepgram (Nova-2 STT, Aura TTS)
- ElevenLabs (TTS only)

Usage:
    from symbolu_extensions.voice.providers import (
        ProviderRegistry,
        CartesiaAdapter,
        DeepgramAdapter,
        ElevenLabsAdapter,
    )

    # Create registry and register providers
    registry = ProviderRegistry()
    registry.register("cartesia", CartesiaAdapter(api_key="..."))
    registry.register("deepgram", DeepgramAdapter(api_key="..."))

    # Get providers with automatic failover
    stt = registry.get_stt("cartesia", fallback=["deepgram"])
    tts = registry.get_tts("cartesia", fallback=["elevenlabs"])
"""

from .base import (
    # Enums
    TranscriptType,

    # Data classes
    WordTimestamp,
    TranscriptEvent,
    TTSParams,
    AudioChunk,
    VoiceInfo,

    # Abstract base classes
    STTProvider,
    TTSProvider,

    # Exceptions
    ProviderError,
    STTError,
    TTSError,
    ProviderUnavailableError,
)

from .registry import (
    ProviderRegistry,
    ProviderHealth,
    ProviderStatus,
    CircuitBreaker,
    CircuitState,
)

from .cartesia import (
    CartesiaAdapter,
    CartesiaSTT,
    CartesiaTTS,
)

from .deepgram import (
    DeepgramAdapter,
    DeepgramSTT,
    DeepgramTTS,
)

from .elevenlabs import (
    ElevenLabsAdapter,
    ElevenLabsTTS,
)

__all__ = [
    # Enums
    "TranscriptType",
    "ProviderHealth",
    "CircuitState",

    # Data classes
    "WordTimestamp",
    "TranscriptEvent",
    "TTSParams",
    "AudioChunk",
    "VoiceInfo",
    "ProviderStatus",
    "CircuitBreaker",

    # Abstract base classes
    "STTProvider",
    "TTSProvider",

    # Registry
    "ProviderRegistry",

    # Adapters
    "CartesiaAdapter",
    "CartesiaSTT",
    "CartesiaTTS",
    "DeepgramAdapter",
    "DeepgramSTT",
    "DeepgramTTS",
    "ElevenLabsAdapter",
    "ElevenLabsTTS",

    # Exceptions
    "ProviderError",
    "STTError",
    "TTSError",
    "ProviderUnavailableError",
]
