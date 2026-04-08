"""Prosodic Renderer - SSML Generation from Acoustic Parameters.

This module provides prosodic markup generation from AcousticParameterFrame,
bridging the gap between P10 acoustic constraints and actual speech output.

Architecture:
------------
    AcousticParameterFrame → ProsodicRenderer → SSMLOutput
                                   ↓
                            ProsodyDirective

Design Principles:
-----------------
1. Sound must obey meaning (acoustic frame is authoritative)
2. Conservative defaults (minimal prosodic variation when uncertain)
3. Deterministic output (same frame → identical SSML)
4. No semantic interpretation (pure parameter mapping)

SSML Elements Generated:
- <prosody rate="X%" pitch="Yhz">: Speech rate and pitch
- <break time="Xms">: Pause insertion
- <emphasis level="X">: Token emphasis
- Suppression via neutral/flat delivery

Usage:
    from symbolu_core.presentation.prosodic_renderer import ProsodicRenderer, render_ssml

    renderer = ProsodicRenderer()
    output = renderer.render(acoustic_frame, text="Hello world")
    print(output.ssml)  # <speak><prosody ...>Hello world</prosody></speak>
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, unique
from typing import Dict, List, Optional, Any
import re

from symbolu_core.mechanical.pipeline.p10_acoustic.p10_acoustic_schema import (
    AcousticParameterFrame,
    AcousticRegime,
    EmphasisPolicy,
    PausePolicy,
)


# =============================================================================
# PROSODY DIRECTIVE (Internal Representation)
# =============================================================================


@unique
class ProsodyLevel(str, Enum):
    """Prosody intensity levels for SSML mapping."""
    MINIMAL = "minimal"      # Almost no prosodic variation
    REDUCED = "reduced"      # Gentle, soft delivery
    NEUTRAL = "neutral"      # Standard delivery
    ENHANCED = "enhanced"    # Slightly more expressive


@dataclass(frozen=True)
class ProsodyDirective:
    """Internal prosodic instructions derived from acoustic frame.

    This is an intermediate representation between AcousticParameterFrame
    and SSML output, capturing the prosodic intent.

    Attributes:
        rate_percent: Speech rate as percentage (e.g., 90 = 90% of normal)
        pitch_hz: Base pitch in Hz
        pitch_range_semitones: Pitch variation range in semitones
        energy_level: Normalized energy [0, 1]
        pause_before_ms: Pause before utterance in ms
        pause_after_ms: Pause after utterance in ms
        allow_emphasis: Whether emphasis is allowed
        max_emphasized_tokens: Maximum number of emphasized tokens
        prosody_level: Overall prosody intensity
        suppression_flags: Which aspects are suppressed
    """
    rate_percent: int
    pitch_hz: int
    pitch_range_semitones: int
    energy_level: float
    pause_before_ms: int
    pause_after_ms: int
    allow_emphasis: bool
    max_emphasized_tokens: int
    prosody_level: ProsodyLevel
    suppression_flags: Dict[str, bool] = field(default_factory=dict)


# =============================================================================
# SSML OUTPUT
# =============================================================================


@dataclass(frozen=True)
class SSMLOutput:
    """SSML output from prosodic rendering.

    Attributes:
        ssml: The complete SSML string
        plain_text: The original plain text
        prosody_directive: The internal prosody directive used
        acoustic_regime: The source acoustic regime
        debug: Additional debug information
    """
    ssml: str
    plain_text: str
    prosody_directive: ProsodyDirective
    acoustic_regime: AcousticRegime
    debug: Dict[str, Any] = field(default_factory=dict)

    @property
    def has_prosody(self) -> bool:
        """Check if any prosody elements are present."""
        return "<prosody" in self.ssml

    @property
    def has_break(self) -> bool:
        """Check if any break elements are present."""
        return "<break" in self.ssml

    @property
    def has_emphasis(self) -> bool:
        """Check if any emphasis elements are present."""
        return "<emphasis" in self.ssml


# =============================================================================
# REGIME TO PROSODY MAPPING
# =============================================================================

# Rate mapping: AcousticRegime → base rate percentage
REGIME_TO_RATE_PERCENT: Dict[AcousticRegime, int] = {
    AcousticRegime.FLAT: 85,         # Slow, deliberate
    AcousticRegime.SOFT: 90,         # Slightly slower
    AcousticRegime.RESTRAINED: 95,   # Close to normal
    AcousticRegime.NEUTRAL: 100,     # Normal rate
}

# Pitch mapping: AcousticRegime → (base_hz, range_semitones)
REGIME_TO_PITCH: Dict[AcousticRegime, tuple] = {
    AcousticRegime.FLAT: (100, 2),       # Monotone
    AcousticRegime.SOFT: (105, 4),       # Gentle variation
    AcousticRegime.RESTRAINED: (110, 5), # Limited variation
    AcousticRegime.NEUTRAL: (115, 8),    # Natural variation
}

# Pause multiplier by regime
REGIME_TO_PAUSE_MULTIPLIER: Dict[AcousticRegime, float] = {
    AcousticRegime.FLAT: 1.5,        # Longer pauses
    AcousticRegime.SOFT: 1.3,        # Slightly longer
    AcousticRegime.RESTRAINED: 1.1,  # Near normal
    AcousticRegime.NEUTRAL: 1.0,     # Normal pauses
}

# Prosody level by regime
REGIME_TO_PROSODY_LEVEL: Dict[AcousticRegime, ProsodyLevel] = {
    AcousticRegime.FLAT: ProsodyLevel.MINIMAL,
    AcousticRegime.SOFT: ProsodyLevel.REDUCED,
    AcousticRegime.RESTRAINED: ProsodyLevel.REDUCED,
    AcousticRegime.NEUTRAL: ProsodyLevel.NEUTRAL,
}


# =============================================================================
# PROSODIC RENDERER
# =============================================================================


class ProsodicRenderer:
    """Renders SSML from AcousticParameterFrame.

    This renderer converts P10 acoustic constraints into valid SSML
    that can be consumed by speech synthesis systems.

    Example:
        renderer = ProsodicRenderer()
        output = renderer.render(
            frame=acoustic_frame,
            text="I'm not entirely certain about that."
        )
        print(output.ssml)

    The renderer respects all suppression flags and regime constraints
    from the acoustic frame, ensuring "sound obeys meaning."
    """

    def __init__(self) -> None:
        """Initialize the prosodic renderer."""
        pass  # Stateless renderer

    def render(
        self,
        frame: AcousticParameterFrame,
        text: str,
        *,
        emphasis_tokens: Optional[List[str]] = None,
        insert_pauses: bool = True,
    ) -> SSMLOutput:
        """Render SSML from acoustic frame and text.

        Args:
            frame: The AcousticParameterFrame from P10
            text: The plain text to render
            emphasis_tokens: Optional list of tokens to emphasize
            insert_pauses: Whether to insert pause elements

        Returns:
            SSMLOutput with complete SSML string

        Raises:
            ValueError: If frame is None or text is empty
        """
        if frame is None:
            raise ValueError("frame cannot be None")
        if not text or not text.strip():
            raise ValueError("text cannot be empty")

        # 1. Derive prosody directive from frame
        directive = self._derive_prosody_directive(frame)

        # 2. Build SSML elements
        ssml_content = self._build_ssml_content(
            text=text,
            directive=directive,
            emphasis_tokens=emphasis_tokens,
            insert_pauses=insert_pauses,
        )

        # 3. Wrap in <speak> element
        ssml = f"<speak>{ssml_content}</speak>"

        # 4. Build debug info
        debug = {
            "source_regime": frame.regime.value,
            "rate_percent": directive.rate_percent,
            "pitch_hz": directive.pitch_hz,
            "prosody_level": directive.prosody_level.value,
            "allow_emphasis": directive.allow_emphasis,
        }

        return SSMLOutput(
            ssml=ssml,
            plain_text=text,
            prosody_directive=directive,
            acoustic_regime=frame.regime,
            debug=debug,
        )

    def _derive_prosody_directive(
        self,
        frame: AcousticParameterFrame,
    ) -> ProsodyDirective:
        """Derive prosody directive from acoustic frame."""
        regime = frame.regime

        # Get base values from regime
        rate_percent = REGIME_TO_RATE_PERCENT.get(regime, 100)
        pitch_hz, pitch_range = REGIME_TO_PITCH.get(regime, (115, 8))
        pause_multiplier = REGIME_TO_PAUSE_MULTIPLIER.get(regime, 1.0)
        prosody_level = REGIME_TO_PROSODY_LEVEL.get(regime, ProsodyLevel.NEUTRAL)

        # Adjust rate based on speech_rate from frame
        # Frame has speech_rate in syllables/sec [3.0, 5.5]
        # Map to percentage: 4.0 is 100%, scale linearly
        rate_factor = frame.speech_rate / 4.0
        rate_percent = int(rate_percent * rate_factor)
        rate_percent = max(70, min(130, rate_percent))  # Clamp to safe range

        # Adjust pitch from frame
        pitch_low, pitch_high = frame.pitch_range
        pitch_hz = (pitch_low + pitch_high) // 2
        pitch_range = pitch_high - pitch_low

        # Calculate pause durations
        pause_low, pause_high = frame.pause_duration_ms
        base_pause = (pause_low + pause_high) // 2
        pause_ms = int(base_pause * pause_multiplier)

        # Determine emphasis allowance
        allow_emphasis = (
            frame.emphasis_policy != EmphasisPolicy.NONE and
            not frame.suppress_emphasis
        )
        max_emphasized = frame.max_stressed_tokens if allow_emphasis else 0

        # Build suppression flags
        suppression_flags = {
            "emotion": frame.suppress_emotion,
            "emphasis": frame.suppress_emphasis,
            "certainty": frame.suppress_certainty,
        }

        return ProsodyDirective(
            rate_percent=rate_percent,
            pitch_hz=pitch_hz,
            pitch_range_semitones=self._hz_to_semitones(pitch_range),
            energy_level=frame.energy_level,
            pause_before_ms=pause_ms // 2,
            pause_after_ms=pause_ms // 2,
            allow_emphasis=allow_emphasis,
            max_emphasized_tokens=max_emphasized,
            prosody_level=prosody_level,
            suppression_flags=suppression_flags,
        )

    def _hz_to_semitones(self, hz_range: int) -> int:
        """Convert Hz range to approximate semitones."""
        # Rough approximation: 1 semitone ≈ 6% frequency change
        # For a range of 30Hz at 110Hz base, that's ~27% = ~4 semitones
        if hz_range <= 10:
            return 2
        elif hz_range <= 20:
            return 4
        elif hz_range <= 30:
            return 6
        else:
            return 8

    def _build_ssml_content(
        self,
        text: str,
        directive: ProsodyDirective,
        emphasis_tokens: Optional[List[str]],
        insert_pauses: bool,
    ) -> str:
        """Build the SSML content string."""
        parts = []

        # Add opening pause if requested
        if insert_pauses and directive.pause_before_ms > 0:
            parts.append(f'<break time="{directive.pause_before_ms}ms"/>')

        # Build prosody attributes
        prosody_attrs = self._build_prosody_attrs(directive)

        # Process text with optional emphasis
        processed_text = text
        if emphasis_tokens and directive.allow_emphasis:
            processed_text = self._apply_emphasis(
                text, emphasis_tokens, directive.max_emphasized_tokens
            )

        # Wrap in prosody element
        if prosody_attrs:
            parts.append(f'<prosody {prosody_attrs}>{processed_text}</prosody>')
        else:
            parts.append(processed_text)

        # Add closing pause if requested
        if insert_pauses and directive.pause_after_ms > 0:
            parts.append(f'<break time="{directive.pause_after_ms}ms"/>')

        return "".join(parts)

    def _build_prosody_attrs(self, directive: ProsodyDirective) -> str:
        """Build prosody element attributes."""
        attrs = []

        # Rate (only if not 100%)
        if directive.rate_percent != 100:
            attrs.append(f'rate="{directive.rate_percent}%"')

        # Pitch (always include for consistency)
        if directive.pitch_hz > 0:
            attrs.append(f'pitch="{directive.pitch_hz}Hz"')

        # Range (only if limited)
        if directive.pitch_range_semitones < 6:
            attrs.append(f'range="{directive.pitch_range_semitones}st"')

        return " ".join(attrs)

    def _apply_emphasis(
        self,
        text: str,
        tokens: List[str],
        max_tokens: int,
    ) -> str:
        """Apply emphasis to specified tokens in text."""
        result = text
        emphasized_count = 0

        for token in tokens:
            if emphasized_count >= max_tokens:
                break

            # Case-insensitive replacement with word boundaries
            pattern = rf'\b({re.escape(token)})\b'
            if re.search(pattern, result, re.IGNORECASE):
                result = re.sub(
                    pattern,
                    r'<emphasis level="moderate">\1</emphasis>',
                    result,
                    count=1,
                    flags=re.IGNORECASE,
                )
                emphasized_count += 1

        return result


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================


def render_ssml(
    frame: AcousticParameterFrame,
    text: str,
    emphasis_tokens: Optional[List[str]] = None,
) -> SSMLOutput:
    """Convenience function to render SSML from acoustic frame.

    Args:
        frame: The AcousticParameterFrame from P10
        text: The plain text to render
        emphasis_tokens: Optional tokens to emphasize

    Returns:
        SSMLOutput with complete SSML string

    Example:
        >>> output = render_ssml(frame, "Hello world")
        >>> print(output.ssml)
        <speak><prosody rate="100%" pitch="115Hz">Hello world</prosody></speak>
    """
    renderer = ProsodicRenderer()
    return renderer.render(frame, text, emphasis_tokens=emphasis_tokens)


def render_minimal_ssml(text: str) -> str:
    """Render minimal SSML with no prosodic modifications.

    Used for fallback/error cases where acoustic frame is unavailable.

    Args:
        text: The plain text to render

    Returns:
        Basic SSML string
    """
    if not text:
        return "<speak></speak>"
    return f"<speak>{text}</speak>"


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    # Main classes
    "ProsodicRenderer",
    "ProsodyDirective",
    "SSMLOutput",
    "ProsodyLevel",
    # Convenience functions
    "render_ssml",
    "render_minimal_ssml",
    # Mapping constants (for testing)
    "REGIME_TO_RATE_PERCENT",
    "REGIME_TO_PITCH",
    "REGIME_TO_PROSODY_LEVEL",
]
