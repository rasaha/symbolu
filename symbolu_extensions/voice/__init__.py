"""
Symbolu Hybrid Voice SDK

A provider-agnostic voice SDK that integrates with the Sentinel agentic
framework to enable cognitive-aware voice agents.

Key Features:
- Multi-provider support (Cartesia, Deepgram, ElevenLabs)
- Coherence-driven voice modulation via P10 prosody mapping
- Safety-aware voice gates for verbal confirmations
- Barge-in detection and handling
- WebSocket-based real-time communication

Architecture:
    ┌─────────────────────────────────────────────────────────────────┐
    │                   Hybrid Voice SDK                               │
    ├─────────────────────────────────────────────────────────────────┤
    │                                                                  │
    │  Audio Stream → [Provider STT] → [Voice Orchestrator] →         │
    │                                        ↓                         │
    │                              [Sentinel Framework]                │
    │                                        ↓                         │
    │  Audio Output ← [Provider TTS] ← [P10 Prosody] ← [Safety Gate] │
    │                                                                  │
    └─────────────────────────────────────────────────────────────────┘

Quick Start:
    from symbolu_extensions.voice import VoiceAgentApp

    app = VoiceAgentApp(
        sentinel_config={
            "llm_provider": "anthropic",
            "llm_model": "claude-sonnet-4-20250514",
        },
        provider_configs={
            "cartesia": {"api_key": "..."},
            "deepgram": {"api_key": "..."},
        }
    )
    app.run(host="0.0.0.0", port=8000)

Modules:
    - providers: Multi-provider abstraction (Cartesia, Deepgram, ElevenLabs)
    - orchestration: Voice interaction management (barge-in, turns, sessions)
    - prosody: P10 acoustic parameter to TTS mapping
    - safety: Safety contract to voice response processing
    - app: Complete voice agent application with WebSocket support

See docs/design/HYBRID_VOICE_SDK_DESIGN.md for detailed documentation.
"""

__version__ = "1.0.0"

# Main application
from .app import (
    VoiceAgentApp,
    VoiceAgentConfig,
)

# Providers
from .providers import (
    # Registry
    ProviderRegistry,
    ProviderHealth,
    ProviderStatus,
    CircuitBreaker,
    CircuitState,

    # Base types
    STTProvider,
    TTSProvider,
    TTSParams,
    AudioChunk,
    TranscriptEvent,
    TranscriptType,
    VoiceInfo,

    # Adapters
    CartesiaAdapter,
    DeepgramAdapter,
    ElevenLabsAdapter,

    # Exceptions
    ProviderError,
    STTError,
    TTSError,
)

# Protocols (for type checking and loose coupling)
from .protocols import (
    SentinelProtocol,
    CoherenceStateProtocol,
    CoherenceMetricsProtocol,
    SafetyContractProtocol,
    LLMClientProtocol,
    BaseSentinelAdapter,
    validate_sentinel,
)

# Orchestration
from .orchestration import (
    VoiceOrchestrator,
    OrchestratorConfig,
    VoiceSession,
    VoiceRequest,
    VoiceResponse,
    SessionState,
    BargeInHandler,
    BargeInStrategy,
    BargeInConfig,
)

# Prosody
from .prosody import (
    P10ProsodyMapper,
    P10ProsodyConfig,
    AcousticRegime,
)

# Safety
from .safety import (
    SafetyVoiceGate,
    SafetyGateConfig,
    SafetyAction,
)

__all__ = [
    # Version
    "__version__",

    # Main application
    "VoiceAgentApp",
    "VoiceAgentConfig",

    # Provider registry
    "ProviderRegistry",
    "ProviderHealth",
    "ProviderStatus",
    "CircuitBreaker",
    "CircuitState",

    # Provider base types
    "STTProvider",
    "TTSProvider",
    "TTSParams",
    "AudioChunk",
    "TranscriptEvent",
    "TranscriptType",
    "VoiceInfo",

    # Provider adapters
    "CartesiaAdapter",
    "DeepgramAdapter",
    "ElevenLabsAdapter",

    # Provider exceptions
    "ProviderError",
    "STTError",
    "TTSError",

    # Protocols (for type checking)
    "SentinelProtocol",
    "CoherenceStateProtocol",
    "CoherenceMetricsProtocol",
    "SafetyContractProtocol",
    "LLMClientProtocol",
    "BaseSentinelAdapter",
    "validate_sentinel",

    # Orchestration
    "VoiceOrchestrator",
    "OrchestratorConfig",
    "VoiceSession",
    "VoiceRequest",
    "VoiceResponse",
    "SessionState",
    "BargeInHandler",
    "BargeInStrategy",
    "BargeInConfig",

    # Prosody
    "P10ProsodyMapper",
    "P10ProsodyConfig",
    "AcousticRegime",

    # Safety
    "SafetyVoiceGate",
    "SafetyGateConfig",
    "SafetyAction",
]
