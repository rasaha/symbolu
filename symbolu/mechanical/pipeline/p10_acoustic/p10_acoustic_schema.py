"""
P10 - Acoustic Parameterization Schema Definitions

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

Design Principles:
- Deterministic: No LLM calls, no probabilistic sampling
- Conservative: SAFE_DEFAULT (HOLD) on any violation
- Authority-Respecting: Cannot override PO1-P9 constraints
- Bounded: All parameters have strict enforced ranges

Authority Model:
- Authority flows: PO1 -> ... -> P9 -> P10 -> (P11 Prosodic Evidence)
- P10 receives signals from P9 (LexicalFrame), P7 (discourse), P6 (regime)
- P10 cannot override or expand upstream decisions
- P10 produces AcousticParameterFrame for downstream prosody/speech

CRITICAL ARCHITECTURAL INVARIANT:
    Sound must obey meaning.
    Meaning must never obey sound.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Tuple


# ============================================================================
# ENUMS - Acoustic control enums
# ============================================================================


class AcousticRegime(str, Enum):
    """
    Acoustic regime mapping for sound production.

    These regimes control the overall acoustic character of speech output.
    Each regime has strictly defined parameter ranges.
    """
    NEUTRAL = "neutral"         # Standard, informational delivery
    SOFT = "soft"               # Gentle, supportive delivery
    FLAT = "flat"               # Minimally expressive, restrained
    RESTRAINED = "restrained"   # Conservative, careful delivery


class EmphasisPolicy(str, Enum):
    """
    Policy for emphasis/stress application.

    Controls whether and how much emphasis can be applied to tokens.
    """
    NONE = "none"               # No emphasis allowed
    LIMITED = "limited"         # Very limited emphasis (max 1 token)


class PausePolicy(str, Enum):
    """
    Policy for pause insertion between utterance units.

    Controls timing and rhythm of speech output.
    """
    MINIMAL = "minimal"         # Shorter pauses (100-150ms)
    NORMAL = "normal"           # Standard pauses (150-250ms)


# ============================================================================
# HARD PARAMETER BOUNDS - These must NEVER be exceeded
# ============================================================================


# Speech rate bounds (syllables per second)
SPEECH_RATE_MIN = 3.0
SPEECH_RATE_MAX = 5.5

# Energy level bounds (0.0 - 1.0 normalized)
ENERGY_LEVEL_MIN = 0.2
ENERGY_LEVEL_MAX = 0.6

# Pitch range bounds (Hz)
PITCH_MIN = 90
PITCH_MAX = 140

# Pause duration bounds (milliseconds)
PAUSE_DURATION_MIN = 100
PAUSE_DURATION_MAX = 300

# Maximum stressed tokens
MAX_STRESSED_TOKENS_MIN = 0
MAX_STRESSED_TOKENS_MAX = 1


# ============================================================================
# DATACLASSES - Core envelope objects
# ============================================================================


@dataclass(frozen=True)
class AcousticParameterFrame:
    """
    P10 output envelope: Acoustic parameterization verdict.

    This envelope is read-only and captures the acoustic control parameters
    for downstream prosodic evidence capture and speech realization phases.
    It does NOT produce sound - it constrains how sound should be produced.

    All parameters have strict bounds that are validated in __post_init__.
    Out-of-range values will raise ValueError.

    Invariants:
    - All numeric parameters within defined bounds
    - regime must be a valid AcousticRegime
    - pause_policy must be a valid PausePolicy
    - emphasis_policy must be a valid EmphasisPolicy
    - source_regime and source_discourse_act trace upstream

    Attributes:
        regime: The acoustic regime (NEUTRAL, SOFT, FLAT, RESTRAINED)
        speech_rate: Syllables per second (3.0-5.5)
        energy_level: Normalized energy (0.2-0.6)
        pitch_range: (min_hz, max_hz) tuple (90-140 Hz each)
        pause_policy: Pause insertion policy (MINIMAL, NORMAL)
        pause_duration_ms: (min_ms, max_ms) tuple (100-300ms each)
        emphasis_policy: Emphasis application policy (NONE, LIMITED)
        max_stressed_tokens: Maximum tokens that can receive stress (0-1)
        suppress_emotion: Whether emotion inference is suppressed
        suppress_emphasis: Whether emphasis introduction is suppressed
        suppress_certainty: Whether certainty collapse is suppressed
        source_regime: The operational regime from P6 (for tracing)
        source_discourse_act: The discourse act from P7 (for tracing)
        architectural_phase: Identifier for this phase ("P10")
        debug: Additional debug/trace information
    """
    regime: AcousticRegime
    speech_rate: float
    energy_level: float
    pitch_range: Tuple[int, int]

    pause_policy: PausePolicy
    pause_duration_ms: Tuple[int, int]

    emphasis_policy: EmphasisPolicy
    max_stressed_tokens: int

    suppress_emotion: bool
    suppress_emphasis: bool
    suppress_certainty: bool

    source_regime: str  # String value for serialization
    source_discourse_act: str  # String value for serialization
    architectural_phase: str = "P10"

    # Debug/trace information
    debug: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate AcousticParameterFrame invariants and bounds."""
        # Validate regime is valid enum
        if not isinstance(self.regime, AcousticRegime):
            raise ValueError(
                f"AcousticParameterFrame.regime must be AcousticRegime, "
                f"got {type(self.regime).__name__}"
            )

        # Validate speech_rate bounds
        if not isinstance(self.speech_rate, (int, float)):
            raise ValueError(
                f"AcousticParameterFrame.speech_rate must be numeric, "
                f"got {type(self.speech_rate).__name__}"
            )
        if not (SPEECH_RATE_MIN <= self.speech_rate <= SPEECH_RATE_MAX):
            raise ValueError(
                f"AcousticParameterFrame.speech_rate must be in "
                f"[{SPEECH_RATE_MIN}, {SPEECH_RATE_MAX}], got {self.speech_rate}"
            )

        # Validate energy_level bounds
        if not isinstance(self.energy_level, (int, float)):
            raise ValueError(
                f"AcousticParameterFrame.energy_level must be numeric, "
                f"got {type(self.energy_level).__name__}"
            )
        if not (ENERGY_LEVEL_MIN <= self.energy_level <= ENERGY_LEVEL_MAX):
            raise ValueError(
                f"AcousticParameterFrame.energy_level must be in "
                f"[{ENERGY_LEVEL_MIN}, {ENERGY_LEVEL_MAX}], got {self.energy_level}"
            )

        # Validate pitch_range
        if not isinstance(self.pitch_range, tuple) or len(self.pitch_range) != 2:
            raise ValueError(
                f"AcousticParameterFrame.pitch_range must be a 2-tuple, "
                f"got {type(self.pitch_range).__name__}"
            )
        pitch_low, pitch_high = self.pitch_range
        if not (PITCH_MIN <= pitch_low <= PITCH_MAX):
            raise ValueError(
                f"AcousticParameterFrame.pitch_range[0] must be in "
                f"[{PITCH_MIN}, {PITCH_MAX}], got {pitch_low}"
            )
        if not (PITCH_MIN <= pitch_high <= PITCH_MAX):
            raise ValueError(
                f"AcousticParameterFrame.pitch_range[1] must be in "
                f"[{PITCH_MIN}, {PITCH_MAX}], got {pitch_high}"
            )
        if pitch_low > pitch_high:
            raise ValueError(
                f"AcousticParameterFrame.pitch_range[0] must be <= pitch_range[1], "
                f"got ({pitch_low}, {pitch_high})"
            )

        # Validate pause_policy
        if not isinstance(self.pause_policy, PausePolicy):
            raise ValueError(
                f"AcousticParameterFrame.pause_policy must be PausePolicy, "
                f"got {type(self.pause_policy).__name__}"
            )

        # Validate pause_duration_ms
        if not isinstance(self.pause_duration_ms, tuple) or len(self.pause_duration_ms) != 2:
            raise ValueError(
                f"AcousticParameterFrame.pause_duration_ms must be a 2-tuple, "
                f"got {type(self.pause_duration_ms).__name__}"
            )
        pause_low, pause_high = self.pause_duration_ms
        if not (PAUSE_DURATION_MIN <= pause_low <= PAUSE_DURATION_MAX):
            raise ValueError(
                f"AcousticParameterFrame.pause_duration_ms[0] must be in "
                f"[{PAUSE_DURATION_MIN}, {PAUSE_DURATION_MAX}], got {pause_low}"
            )
        if not (PAUSE_DURATION_MIN <= pause_high <= PAUSE_DURATION_MAX):
            raise ValueError(
                f"AcousticParameterFrame.pause_duration_ms[1] must be in "
                f"[{PAUSE_DURATION_MIN}, {PAUSE_DURATION_MAX}], got {pause_high}"
            )
        if pause_low > pause_high:
            raise ValueError(
                f"AcousticParameterFrame.pause_duration_ms[0] must be <= [1], "
                f"got ({pause_low}, {pause_high})"
            )

        # Validate emphasis_policy
        if not isinstance(self.emphasis_policy, EmphasisPolicy):
            raise ValueError(
                f"AcousticParameterFrame.emphasis_policy must be EmphasisPolicy, "
                f"got {type(self.emphasis_policy).__name__}"
            )

        # Validate max_stressed_tokens
        if not isinstance(self.max_stressed_tokens, int):
            raise ValueError(
                f"AcousticParameterFrame.max_stressed_tokens must be int, "
                f"got {type(self.max_stressed_tokens).__name__}"
            )
        if not (MAX_STRESSED_TOKENS_MIN <= self.max_stressed_tokens <= MAX_STRESSED_TOKENS_MAX):
            raise ValueError(
                f"AcousticParameterFrame.max_stressed_tokens must be in "
                f"[{MAX_STRESSED_TOKENS_MIN}, {MAX_STRESSED_TOKENS_MAX}], "
                f"got {self.max_stressed_tokens}"
            )

        # Validate boolean suppressions
        for attr_name in ('suppress_emotion', 'suppress_emphasis', 'suppress_certainty'):
            value = getattr(self, attr_name)
            if not isinstance(value, bool):
                raise ValueError(
                    f"AcousticParameterFrame.{attr_name} must be bool, "
                    f"got {type(value).__name__}"
                )

        # Validate source strings
        if not isinstance(self.source_regime, str) or not self.source_regime.strip():
            raise ValueError(
                "AcousticParameterFrame.source_regime must be a non-empty string"
            )
        if not isinstance(self.source_discourse_act, str) or not self.source_discourse_act.strip():
            raise ValueError(
                "AcousticParameterFrame.source_discourse_act must be a non-empty string"
            )

    def is_flat_regime(self) -> bool:
        """Check if this is a FLAT acoustic regime (most conservative)."""
        return self.regime == AcousticRegime.FLAT

    def is_suppressed(self) -> bool:
        """Check if all suppressions are active."""
        return self.suppress_emotion and self.suppress_emphasis and self.suppress_certainty

    def allows_emphasis(self) -> bool:
        """Check if any emphasis is allowed."""
        return (
            self.emphasis_policy == EmphasisPolicy.LIMITED and
            self.max_stressed_tokens > 0 and
            not self.suppress_emphasis
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for logging/tracing."""
        return {
            "regime": self.regime.value,
            "speech_rate": self.speech_rate,
            "energy_level": self.energy_level,
            "pitch_range": list(self.pitch_range),
            "pause_policy": self.pause_policy.value,
            "pause_duration_ms": list(self.pause_duration_ms),
            "emphasis_policy": self.emphasis_policy.value,
            "max_stressed_tokens": self.max_stressed_tokens,
            "suppress_emotion": self.suppress_emotion,
            "suppress_emphasis": self.suppress_emphasis,
            "suppress_certainty": self.suppress_certainty,
            "source_regime": self.source_regime,
            "source_discourse_act": self.source_discourse_act,
            "architectural_phase": self.architectural_phase,
            "debug": self.debug,
            "is_flat_regime": self.is_flat_regime(),
            "is_suppressed": self.is_suppressed(),
            "allows_emphasis": self.allows_emphasis(),
        }


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def clamp_speech_rate(value: float) -> float:
    """Clamp speech rate to valid bounds."""
    return max(SPEECH_RATE_MIN, min(SPEECH_RATE_MAX, value))


def clamp_energy_level(value: float) -> float:
    """Clamp energy level to valid bounds."""
    return max(ENERGY_LEVEL_MIN, min(ENERGY_LEVEL_MAX, value))


def clamp_pitch(value: int) -> int:
    """Clamp pitch value to valid bounds."""
    return max(PITCH_MIN, min(PITCH_MAX, value))


def clamp_pause_duration(value: int) -> int:
    """Clamp pause duration to valid bounds."""
    return max(PAUSE_DURATION_MIN, min(PAUSE_DURATION_MAX, value))


def validate_pitch_range(pitch_range: Tuple[int, int]) -> bool:
    """Validate that a pitch range is within bounds."""
    if not isinstance(pitch_range, tuple) or len(pitch_range) != 2:
        return False
    low, high = pitch_range
    return (
        PITCH_MIN <= low <= PITCH_MAX and
        PITCH_MIN <= high <= PITCH_MAX and
        low <= high
    )


def validate_pause_range(pause_range: Tuple[int, int]) -> bool:
    """Validate that a pause range is within bounds."""
    if not isinstance(pause_range, tuple) or len(pause_range) != 2:
        return False
    low, high = pause_range
    return (
        PAUSE_DURATION_MIN <= low <= PAUSE_DURATION_MAX and
        PAUSE_DURATION_MIN <= high <= PAUSE_DURATION_MAX and
        low <= high
    )


# Public exports
__all__ = [
    # Enums
    "AcousticRegime",
    "EmphasisPolicy",
    "PausePolicy",
    # Dataclasses
    "AcousticParameterFrame",
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
    # Helper functions
    "clamp_speech_rate",
    "clamp_energy_level",
    "clamp_pitch",
    "clamp_pause_duration",
    "validate_pitch_range",
    "validate_pause_range",
]
