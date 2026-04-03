"""
Voice Orchestration Package.

This package provides the orchestration layer for voice agents,
managing the complete voice interaction flow with support for:

- Barge-in detection and handling
- Turn management
- Session state tracking
- Integration with Sentinel framework

Usage:
    from symbolu_extensions.voice.orchestration import (
        VoiceOrchestrator,
        VoiceSession,
        VoiceRequest,
        VoiceResponse,
        BargeInHandler,
    )

    orchestrator = VoiceOrchestrator(
        sentinel=sentinel_wrapper,
        stt_provider=stt,
        tts_provider=tts,
        p10_mapper=mapper,
        safety_gate=gate
    )

    session = await orchestrator.start_session()
"""

from .models import (
    # Enums
    SessionState,
    InterruptionType,

    # Data classes
    VoiceSession,
    VoiceRequest,
    VoiceResponse,
    InterruptionEvent,
    TurnMetrics,
)

from .barge_in import (
    BargeInStrategy,
    BargeInConfig,
    BargeInHandler,
    AdaptiveBargeInHandler,
)

from .orchestrator import (
    OrchestratorConfig,
    VoiceOrchestrator,
)

__all__ = [
    # Enums
    "SessionState",
    "InterruptionType",
    "BargeInStrategy",

    # Data classes
    "VoiceSession",
    "VoiceRequest",
    "VoiceResponse",
    "InterruptionEvent",
    "TurnMetrics",

    # Config
    "BargeInConfig",
    "OrchestratorConfig",

    # Handlers
    "BargeInHandler",
    "AdaptiveBargeInHandler",

    # Main orchestrator
    "VoiceOrchestrator",
]
