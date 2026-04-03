"""
Voice Prosody Package.

This package provides prosody mapping from Sentinel's cognitive state
and P10 acoustic parameters to TTS provider settings.

Key features:
- Map P10 acoustic regimes to TTS parameters
- Coherence-driven voice modulation
- Provider-specific parameter translation
- SSML generation for enhanced prosody control

Usage:
    from symbolu.voice.prosody import (
        P10ProsodyMapper,
        AcousticRegime,
    )

    mapper = P10ProsodyMapper()
    tts_params = mapper.compute_params(
        coherence_state=sentinel.coherence_state,
        safety_contract=sentinel.safety_contract
    )
"""

from .mapper import (
    AcousticRegime,
    ProsodyModulation,
    P10ProsodyConfig,
    P10ProsodyMapper,
)

__all__ = [
    "AcousticRegime",
    "ProsodyModulation",
    "P10ProsodyConfig",
    "P10ProsodyMapper",
]
