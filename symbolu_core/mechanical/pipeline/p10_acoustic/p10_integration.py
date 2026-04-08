"""
P10 - Acoustic Parameterization Pipeline Integration Module

Provides a thin shim for integrating P10 (Acoustic Parameterization Engine)
into the Symbol-U pipeline. Called immediately after P9, before any
prosodic evidence capture or speech realization.

P10 is the first sound-adjacent phase, but it does NOT generate sound.

Usage in orchestrator:
    from .p10_acoustic.p10_integration import maybe_run_p10

    # After P9 stage
    maybe_run_p10(ctx)
    # ctx.p10_acoustic is now set

Authority Model:
    - P10 consumes P9 LexicalFrame, P7 DiscourseEnvelope, P6 RegimeEnvelope
    - P10 cannot override PO1-P9 decisions
    - P10 produces AcousticParameterFrame (read-only, constrains prosody/speech)
    - P10 does NOT generate audio, use TTS, SSML, or audio references

CRITICAL: P10 is gating-only and deterministic. It constrains downstream
prosodic/speech generation but does not directly produce any output.

ARCHITECTURAL PRINCIPLE:
    Sound must obey meaning.
    Meaning must never obey sound.
"""

from typing import Any, Optional

from symbolu_core.mechanical.pipeline.phase_p6.p6_schema import (
    RegimeEnvelope,
    OperationalRegime,
)
from symbolu_core.mechanical.pipeline.p7_discourse.p7_discourse_schema import (
    DiscourseEnvelope,
)
from symbolu_core.mechanical.pipeline.p9_lexical.p9_lexical_schema import LexicalFrame
from symbolu_core.mechanical.pipeline.p10_acoustic.p10_acoustic_schema import (
    AcousticParameterFrame,
    AcousticRegime,
)
from symbolu_core.mechanical.pipeline.p10_acoustic.p10_acoustic_resolver import (
    P10AcousticResolver,
)


# Singleton P10 resolver instance
_p10_resolver: Optional[P10AcousticResolver] = None


def get_p10_resolver() -> P10AcousticResolver:
    """Get or create the singleton P10 acoustic resolver instance."""
    global _p10_resolver
    if _p10_resolver is None:
        _p10_resolver = P10AcousticResolver()
    return _p10_resolver


def is_acoustic_parameterization_allowed(ctx: Any) -> bool:
    """
    Check if acoustic parameterization is allowed for this context.

    Acoustic parameterization is NOT allowed if:
    - P9 LexicalFrame is not present (P10 requires P9)
    - P7 DiscourseEnvelope is not present
    - P6 RegimeEnvelope is not present

    Args:
        ctx: Pipeline context.

    Returns:
        True if acoustic parameterization is allowed, False otherwise.
    """
    # Check if P9 output is available
    if not hasattr(ctx, 'lexical_frame') or ctx.lexical_frame is None:
        return False

    # Check if P7 output is available (required for P10)
    if not hasattr(ctx, 'p7_discourse_envelope') or ctx.p7_discourse_envelope is None:
        return False

    # Check if P6 output is available (required for P10)
    if not hasattr(ctx, 'p6_regime') or ctx.p6_regime is None:
        return False

    return True


def maybe_run_p10(ctx: Any) -> None:
    """
    Run P10 acoustic parameterization on the pipeline context.

    This is the main integration function to call from the pipeline orchestrator.
    P10 requires P9, P7, and P6 to be present.

    IMPORTANT: This function attaches the result to ctx.p10_acoustic.
    It does NOT return the frame - use get_p10_acoustic_frame(ctx) to retrieve it.

    CRITICAL: P10 is gating-only and deterministic. It constrains downstream
    prosodic/speech generation but does not directly produce any output.

    Rules:
    - Run only if P9, P7, and P6 exist
    - Attach AcousticParameterFrame to ctx.p10_acoustic
    - Must not alter upstream behavior
    - Never raises - uses SAFE_DEFAULT on any error

    Args:
        ctx: Pipeline context with lexical_frame, p7_discourse_envelope,
             and p6_regime.
    """
    # Check if P9 output is available (P10 runs after P9)
    lexical_frame = None
    if hasattr(ctx, 'lexical_frame') and ctx.lexical_frame is not None:
        lexical_frame = ctx.lexical_frame

    # Check if P7 output is available (required for P10)
    discourse_envelope = None
    if hasattr(ctx, 'p7_discourse_envelope'):
        discourse_envelope = ctx.p7_discourse_envelope

    # Check if P6 output is available (required for P10)
    regime_envelope = None
    if hasattr(ctx, 'p6_regime'):
        regime_envelope = ctx.p6_regime

    # Run P10 resolver (always returns a frame, SAFE_DEFAULT on missing inputs)
    resolver = get_p10_resolver()
    frame = resolver.resolve(
        lexical_frame=lexical_frame,
        discourse_envelope=discourse_envelope,
        regime_envelope=regime_envelope,
    )

    # Attach to context (gating capture, no execution)
    ctx.p10_acoustic = frame


def run_p10_directly(
    lexical_frame: Optional[LexicalFrame],
    discourse_envelope: Optional[DiscourseEnvelope],
    regime_envelope: Optional[RegimeEnvelope],
) -> AcousticParameterFrame:
    """
    Run P10 directly with explicit inputs.

    Useful for testing or standalone acoustic parameterization.

    CRITICAL: The acoustic frame constrains downstream prosodic/speech generation
    but does not directly produce any output.

    Args:
        lexical_frame: LexicalFrame from P9 (or None for SAFE_DEFAULT).
        discourse_envelope: DiscourseEnvelope from P7 (or None for SAFE_DEFAULT).
        regime_envelope: RegimeEnvelope from P6 (or None for SAFE_DEFAULT).

    Returns:
        AcousticParameterFrame with acoustic parameter verdict.
        Never raises - returns SAFE_DEFAULT on missing inputs.
    """
    resolver = get_p10_resolver()
    return resolver.resolve(
        lexical_frame=lexical_frame,
        discourse_envelope=discourse_envelope,
        regime_envelope=regime_envelope,
    )


def get_p10_acoustic_frame(ctx: Any) -> Optional[AcousticParameterFrame]:
    """
    Get the P10 acoustic frame from context.

    Args:
        ctx: Pipeline context.

    Returns:
        AcousticParameterFrame or None if not available.
    """
    if not hasattr(ctx, 'p10_acoustic'):
        return None
    return ctx.p10_acoustic


def get_acoustic_regime(ctx: Any) -> Optional[AcousticRegime]:
    """
    Get the acoustic regime from the P10 frame.

    Args:
        ctx: Pipeline context.

    Returns:
        AcousticRegime or None if P10 hasn't run.
    """
    frame = get_p10_acoustic_frame(ctx)
    if frame is None:
        return None
    return frame.regime


def is_acoustic_frame_flat(ctx: Any) -> bool:
    """
    Check if the acoustic frame is FLAT (most conservative).

    Args:
        ctx: Pipeline context.

    Returns:
        True if FLAT regime, False otherwise.
        Returns True (conservative) if P10 hasn't run.
    """
    frame = get_p10_acoustic_frame(ctx)
    if frame is None:
        # Conservative default: if P10 hasn't run, consider FLAT
        return True
    return frame.is_flat_regime()


def is_acoustic_frame_suppressed(ctx: Any) -> bool:
    """
    Check if all acoustic suppressions are active.

    Args:
        ctx: Pipeline context.

    Returns:
        True if all suppressions active, False otherwise.
        Returns True (conservative) if P10 hasn't run.
    """
    frame = get_p10_acoustic_frame(ctx)
    if frame is None:
        # Conservative default: if P10 hasn't run, consider suppressed
        return True
    return frame.is_suppressed()


def allows_emphasis(ctx: Any) -> bool:
    """
    Check if any emphasis is allowed in the acoustic frame.

    Args:
        ctx: Pipeline context.

    Returns:
        True if emphasis allowed, False otherwise.
        Returns False (conservative) if P10 hasn't run.
    """
    frame = get_p10_acoustic_frame(ctx)
    if frame is None:
        # Conservative default: if P10 hasn't run, no emphasis allowed
        return False
    return frame.allows_emphasis()


def get_speech_rate(ctx: Any) -> Optional[float]:
    """
    Get the speech rate from the acoustic frame.

    Args:
        ctx: Pipeline context.

    Returns:
        Speech rate (syllables/sec) or None if P10 hasn't run.
    """
    frame = get_p10_acoustic_frame(ctx)
    if frame is None:
        return None
    return frame.speech_rate


def get_energy_level(ctx: Any) -> Optional[float]:
    """
    Get the energy level from the acoustic frame.

    Args:
        ctx: Pipeline context.

    Returns:
        Energy level (0.0-1.0) or None if P10 hasn't run.
    """
    frame = get_p10_acoustic_frame(ctx)
    if frame is None:
        return None
    return frame.energy_level


def get_pitch_range(ctx: Any) -> Optional[tuple]:
    """
    Get the pitch range from the acoustic frame.

    Args:
        ctx: Pipeline context.

    Returns:
        Pitch range (min_hz, max_hz) or None if P10 hasn't run.
    """
    frame = get_p10_acoustic_frame(ctx)
    if frame is None:
        return None
    return frame.pitch_range


def get_pause_policy(ctx: Any) -> Optional[str]:
    """
    Get the pause policy from the acoustic frame.

    Args:
        ctx: Pipeline context.

    Returns:
        Pause policy value or None if P10 hasn't run.
    """
    frame = get_p10_acoustic_frame(ctx)
    if frame is None:
        return None
    return frame.pause_policy.value


def get_pause_duration_range(ctx: Any) -> Optional[tuple]:
    """
    Get the pause duration range from the acoustic frame.

    Args:
        ctx: Pipeline context.

    Returns:
        Pause duration range (min_ms, max_ms) or None if P10 hasn't run.
    """
    frame = get_p10_acoustic_frame(ctx)
    if frame is None:
        return None
    return frame.pause_duration_ms


def get_max_stressed_tokens(ctx: Any) -> int:
    """
    Get the maximum stressed tokens from the acoustic frame.

    Args:
        ctx: Pipeline context.

    Returns:
        Max stressed tokens (0 if P10 hasn't run - conservative).
    """
    frame = get_p10_acoustic_frame(ctx)
    if frame is None:
        return 0
    return frame.max_stressed_tokens


def is_emotion_suppressed(ctx: Any) -> bool:
    """
    Check if emotion suppression is active.

    Args:
        ctx: Pipeline context.

    Returns:
        True if emotion suppressed, False otherwise.
        Returns True (conservative) if P10 hasn't run.
    """
    frame = get_p10_acoustic_frame(ctx)
    if frame is None:
        return True
    return frame.suppress_emotion


def is_emphasis_suppressed(ctx: Any) -> bool:
    """
    Check if emphasis suppression is active.

    Args:
        ctx: Pipeline context.

    Returns:
        True if emphasis suppressed, False otherwise.
        Returns True (conservative) if P10 hasn't run.
    """
    frame = get_p10_acoustic_frame(ctx)
    if frame is None:
        return True
    return frame.suppress_emphasis


def is_certainty_suppressed(ctx: Any) -> bool:
    """
    Check if certainty suppression is active.

    Args:
        ctx: Pipeline context.

    Returns:
        True if certainty suppressed, False otherwise.
        Returns True (conservative) if P10 hasn't run.
    """
    frame = get_p10_acoustic_frame(ctx)
    if frame is None:
        return True
    return frame.suppress_certainty


def get_source_regime(ctx: Any) -> Optional[str]:
    """
    Get the source regime from the acoustic frame.

    Args:
        ctx: Pipeline context.

    Returns:
        Regime string or None if P10 hasn't run.
    """
    frame = get_p10_acoustic_frame(ctx)
    if frame is None:
        return None
    return frame.source_regime


def get_source_discourse_act(ctx: Any) -> Optional[str]:
    """
    Get the source discourse act from the acoustic frame.

    Args:
        ctx: Pipeline context.

    Returns:
        Discourse act string or None if P10 hasn't run.
    """
    frame = get_p10_acoustic_frame(ctx)
    if frame is None:
        return None
    return frame.source_discourse_act


__all__ = [
    # Core functions
    "get_p10_resolver",
    "is_acoustic_parameterization_allowed",
    "maybe_run_p10",
    "run_p10_directly",
    "get_p10_acoustic_frame",
    # Regime accessors
    "get_acoustic_regime",
    "is_acoustic_frame_flat",
    "is_acoustic_frame_suppressed",
    # Emphasis accessors
    "allows_emphasis",
    "get_max_stressed_tokens",
    # Parameter accessors
    "get_speech_rate",
    "get_energy_level",
    "get_pitch_range",
    "get_pause_policy",
    "get_pause_duration_range",
    # Suppression accessors
    "is_emotion_suppressed",
    "is_emphasis_suppressed",
    "is_certainty_suppressed",
    # Source tracing
    "get_source_regime",
    "get_source_discourse_act",
]
