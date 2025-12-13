"""
P10 - Acoustic Parameterization Engine

P10 is the first sound-adjacent phase, but it does NOT generate sound.
It translates lexically selected words into acoustic control parameters,
without changing meaning, intent, regime, or discourse.

P10's responsibility is to:
- Produce bounded acoustic parameters for downstream prosodic/speech phases
- Obey strict regime -> acoustic mapping rules
- Be fully deterministic (same input -> same output)
- Default safely on any violation

P10 does NOT:
- Select, replace, or reorder words (that's P9)
- Infer emotion
- Introduce emphasis
- Collapse uncertainty
- Override regime or discourse
- Use TTS, SSML, or audio references
- Call LLMs or NLP libraries
- Introduce probabilistic behavior

Architectural Notes:
- P10 is the first sound-adjacent phase
- P10 constrains how words should sound, not what words to use
- P11 will handle prosodic evidence capture
- P12 will handle speech realization
- Authority flows downward; P10 is subordinate to PO1-P9

Components:
- AcousticParameterFrame: Output dataclass capturing acoustic constraints
- P10AcousticResolver: Deterministic acoustic parameterization resolver
- AcousticRegime, EmphasisPolicy, PausePolicy: Control enums

CRITICAL ARCHITECTURAL INVARIANT:
    Sound must obey meaning.
    Meaning must never obey sound.

Usage:
    from symbolu.mechanical.pipeline.p10_acoustic import (
        P10AcousticResolver,
        AcousticParameterFrame,
        AcousticRegime,
    )

    resolver = P10AcousticResolver()
    frame = resolver.resolve(
        lexical_frame=p9_frame,
        discourse_envelope=p7_envelope,
        regime_envelope=p6_envelope,
    )
    # frame contains acoustic constraints for downstream phases

Authority Model:
- P10 receives signals from P9 (LexicalFrame), P7 (discourse), P6 (regime)
- P10 evaluates acoustic parameters based on deterministic rules (read-only gating)
- P10 cannot override PO1-P9 decisions
- Acoustic parameters constrain downstream prosodic/speech generation
"""

from .p10_acoustic_schema import (
    # Enums
    AcousticRegime,
    EmphasisPolicy,
    PausePolicy,
    # Dataclasses
    AcousticParameterFrame,
    # Constants - bounds
    SPEECH_RATE_MIN,
    SPEECH_RATE_MAX,
    ENERGY_LEVEL_MIN,
    ENERGY_LEVEL_MAX,
    PITCH_MIN,
    PITCH_MAX,
    PAUSE_DURATION_MIN,
    PAUSE_DURATION_MAX,
    MAX_STRESSED_TOKENS_MIN,
    MAX_STRESSED_TOKENS_MAX,
    # Helper functions
    clamp_speech_rate,
    clamp_energy_level,
    clamp_pitch,
    clamp_pause_duration,
    validate_pitch_range,
    validate_pause_range,
)
from .p10_acoustic_resolver import (
    P10AcousticResolver,
    # Config constants
    HOLD_ACOUSTIC_CONFIG,
    DE_ESCALATE_ACOUSTIC_CONFIG,
    STABILIZE_ACOUSTIC_CONFIG,
    REFLECT_ACOUSTIC_CONFIG,
    INFORM_ACOUSTIC_CONFIG,
    CLARIFY_ACOUSTIC_CONFIG,
    REGIME_ACOUSTIC_MAP,
    SAFE_DEFAULT_CONFIG,
)


__all__ = [
    # Enums
    "AcousticRegime",
    "EmphasisPolicy",
    "PausePolicy",
    # Dataclasses
    "AcousticParameterFrame",
    # Resolver
    "P10AcousticResolver",
    # Constants - bounds
    "SPEECH_RATE_MIN",
    "SPEECH_RATE_MAX",
    "ENERGY_LEVEL_MIN",
    "ENERGY_LEVEL_MAX",
    "PITCH_MIN",
    "PITCH_MAX",
    "PAUSE_DURATION_MIN",
    "PAUSE_DURATION_MAX",
    "MAX_STRESSED_TOKENS_MIN",
    "MAX_STRESSED_TOKENS_MAX",
    # Config constants
    "HOLD_ACOUSTIC_CONFIG",
    "DE_ESCALATE_ACOUSTIC_CONFIG",
    "STABILIZE_ACOUSTIC_CONFIG",
    "REFLECT_ACOUSTIC_CONFIG",
    "INFORM_ACOUSTIC_CONFIG",
    "CLARIFY_ACOUSTIC_CONFIG",
    "REGIME_ACOUSTIC_MAP",
    "SAFE_DEFAULT_CONFIG",
    # Helper functions
    "clamp_speech_rate",
    "clamp_energy_level",
    "clamp_pitch",
    "clamp_pause_duration",
    "validate_pitch_range",
    "validate_pause_range",
]
