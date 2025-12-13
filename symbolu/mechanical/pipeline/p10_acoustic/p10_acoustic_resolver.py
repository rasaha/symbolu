"""
P10 - Acoustic Parameterization Resolver

Deterministic resolver that translates lexically selected words into
acoustic control parameters. No execution, no sound generation, no side effects.

This is an acoustic governance layer that determines acoustic constraints.
It produces a read-only AcousticParameterFrame and does NOT produce sound.

Authority Model:
- Consumes P9 LexicalFrame, P7 DiscourseEnvelope, P6 RegimeEnvelope
- Cannot override PO1-P9 decisions
- Produces AcousticParameterFrame (read-only, non-actuating)
- Constrains downstream prosodic/speech generation only

Resolution Algorithm (Authoritative, exact order):
1. Validate inputs
2. Apply deterministic regime -> acoustic mapping
3. Apply discourse act overrides
4. Enforce hard parameter bounds
5. Return AcousticParameterFrame

CRITICAL INVARIANTS:
- Never select, replace, or reorder words
- Never infer emotion
- Never introduce emphasis (only constrain it)
- Never collapse uncertainty
- Never override regime or discourse
- No TTS, SSML, or audio references
- Deterministic: same input -> same output

ARCHITECTURAL PRINCIPLE:
    Sound must obey meaning.
    Meaning must never obey sound.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from symbolu.mechanical.pipeline.phase_p6.p6_schema import (
    RegimeEnvelope,
    OperationalRegime,
)
from symbolu.mechanical.pipeline.p7_discourse.p7_discourse_schema import (
    DiscourseEnvelope,
    DiscourseAct,
)
from symbolu.mechanical.pipeline.p9_lexical.p9_lexical_schema import LexicalFrame
from symbolu.mechanical.pipeline.p10_acoustic.p10_acoustic_schema import (
    AcousticParameterFrame,
    AcousticRegime,
    EmphasisPolicy,
    PausePolicy,
    SPEECH_RATE_MIN,
    SPEECH_RATE_MAX,
    ENERGY_LEVEL_MIN,
    ENERGY_LEVEL_MAX,
    PITCH_MIN,
    PITCH_MAX,
    clamp_speech_rate,
    clamp_energy_level,
    clamp_pitch,
    clamp_pause_duration,
)


# ============================================================================
# REGIME -> ACOUSTIC MAPPING CONSTANTS
# ============================================================================

# HOLD regime -> FLAT acoustic (most conservative)
HOLD_ACOUSTIC_CONFIG = {
    "regime": AcousticRegime.FLAT,
    "speech_rate": 3.5,
    "energy_level": 0.25,
    "pitch_range": (95, 105),
    "pause_policy": PausePolicy.NORMAL,
    "pause_duration_ms": (150, 250),
    "emphasis_policy": EmphasisPolicy.NONE,
    "max_stressed_tokens": 0,
    "suppress_emotion": True,
    "suppress_emphasis": True,
    "suppress_certainty": True,
}

# DE_ESCALATE regime -> SOFT acoustic
DE_ESCALATE_ACOUSTIC_CONFIG = {
    "regime": AcousticRegime.SOFT,
    "speech_rate": 3.2,
    "energy_level": 0.30,
    "pitch_range": (95, 115),
    "pause_policy": PausePolicy.NORMAL,
    "pause_duration_ms": (150, 250),
    "emphasis_policy": EmphasisPolicy.NONE,
    "max_stressed_tokens": 0,
    "suppress_emotion": True,
    "suppress_emphasis": True,
    "suppress_certainty": True,
}

# STABILIZE regime -> SOFT acoustic (same as DE_ESCALATE)
STABILIZE_ACOUSTIC_CONFIG = {
    "regime": AcousticRegime.SOFT,
    "speech_rate": 3.2,
    "energy_level": 0.30,
    "pitch_range": (95, 115),
    "pause_policy": PausePolicy.NORMAL,
    "pause_duration_ms": (150, 250),
    "emphasis_policy": EmphasisPolicy.NONE,
    "max_stressed_tokens": 0,
    "suppress_emotion": True,
    "suppress_emphasis": True,
    "suppress_certainty": True,
}

# REFLECT regime -> SOFT acoustic (gentle, supportive)
REFLECT_ACOUSTIC_CONFIG = {
    "regime": AcousticRegime.SOFT,
    "speech_rate": 3.5,
    "energy_level": 0.35,
    "pitch_range": (95, 120),
    "pause_policy": PausePolicy.NORMAL,
    "pause_duration_ms": (150, 250),
    "emphasis_policy": EmphasisPolicy.NONE,
    "max_stressed_tokens": 0,
    "suppress_emotion": True,
    "suppress_emphasis": True,
    "suppress_certainty": True,
}

# INFORM regime -> NEUTRAL acoustic
INFORM_ACOUSTIC_CONFIG = {
    "regime": AcousticRegime.NEUTRAL,
    "speech_rate": 4.5,
    "energy_level": 0.45,
    "pitch_range": (100, 130),
    "pause_policy": PausePolicy.MINIMAL,
    "pause_duration_ms": (100, 150),
    "emphasis_policy": EmphasisPolicy.LIMITED,
    "max_stressed_tokens": 1,
    "suppress_emotion": True,
    "suppress_emphasis": False,
    "suppress_certainty": False,
}

# CLARIFY regime -> NEUTRAL acoustic (similar to INFORM)
CLARIFY_ACOUSTIC_CONFIG = {
    "regime": AcousticRegime.NEUTRAL,
    "speech_rate": 4.2,
    "energy_level": 0.40,
    "pitch_range": (100, 125),
    "pause_policy": PausePolicy.MINIMAL,
    "pause_duration_ms": (100, 150),
    "emphasis_policy": EmphasisPolicy.LIMITED,
    "max_stressed_tokens": 1,
    "suppress_emotion": True,
    "suppress_emphasis": False,
    "suppress_certainty": False,
}

# Master mapping from OperationalRegime to acoustic config
REGIME_ACOUSTIC_MAP: Dict[OperationalRegime, Dict[str, Any]] = {
    OperationalRegime.HOLD: HOLD_ACOUSTIC_CONFIG,
    OperationalRegime.DE_ESCALATE: DE_ESCALATE_ACOUSTIC_CONFIG,
    OperationalRegime.STABILIZE: STABILIZE_ACOUSTIC_CONFIG,
    OperationalRegime.REFLECT: REFLECT_ACOUSTIC_CONFIG,
    OperationalRegime.INFORM: INFORM_ACOUSTIC_CONFIG,
    OperationalRegime.CLARIFY: CLARIFY_ACOUSTIC_CONFIG,
}

# SAFE_DEFAULT is HOLD (most conservative)
SAFE_DEFAULT_CONFIG = HOLD_ACOUSTIC_CONFIG


class P10AcousticResolver:
    """
    Deterministic acoustic parameterization resolver (non-actuating).

    This resolver implements strict, deterministic rules to produce acoustic
    control parameters. It does NOT produce sound, generate audio, or enable
    any audio execution pathway.

    CRITICAL: This class is purely evaluative. The acoustic frame constrains
    downstream prosodic/speech generation but does not directly produce output.

    Usage:
        resolver = P10AcousticResolver()
        frame = resolver.resolve(
            lexical_frame=p9_frame,
            discourse_envelope=p7_envelope,
            regime_envelope=p6_envelope,
        )
        # frame contains acoustic constraints for downstream phases

    Invariants:
    - Never modifies lexical selections
    - Never infers emotion
    - Never introduces emphasis (only constrains it)
    - Deterministic: same input -> same output
    - Always returns a valid frame (SAFE_DEFAULT on any error)
    """

    def __init__(self) -> None:
        """Initialize the P10 acoustic resolver."""
        pass  # No state needed - purely deterministic

    def resolve(
        self,
        *,
        lexical_frame: Optional[LexicalFrame],
        discourse_envelope: Optional[DiscourseEnvelope],
        regime_envelope: Optional[RegimeEnvelope],
    ) -> AcousticParameterFrame:
        """
        Resolve acoustic parameters based on deterministic rules.

        This is a pure, deterministic evaluation with no side effects.
        The result is a read-only acoustic parameter frame verdict.

        CRITICAL:
        - Never modify lexical selections
        - Never infer emotion
        - Missing inputs -> SAFE_DEFAULT
        - Out-of-range values -> SAFE_DEFAULT

        Resolution Algorithm (exact order):
        1. Validate inputs (SAFE_DEFAULT on missing)
        2. Get base acoustic config from regime mapping
        3. Apply discourse act overrides
        4. Enforce hard parameter bounds
        5. Return AcousticParameterFrame

        Args:
            lexical_frame: The P9 LexicalFrame (for tracing, not modification).
            discourse_envelope: The P7 DiscourseEnvelope (provides discourse act).
            regime_envelope: The P6 RegimeEnvelope (provides operational regime).

        Returns:
            AcousticParameterFrame with acoustic parameter verdict.
            Never raises - returns SAFE_DEFAULT on any error.
        """
        # Step 1: Validate inputs - SAFE_DEFAULT on missing
        if regime_envelope is None or discourse_envelope is None:
            return self._build_safe_default_frame(
                reason="Missing upstream envelope(s)",
                regime_envelope=regime_envelope,
                discourse_envelope=discourse_envelope,
            )

        # Extract values for rule evaluation
        regime = regime_envelope.regime
        discourse_act = discourse_envelope.act

        # Step 2: Get base acoustic config from regime mapping
        base_config = self._get_regime_acoustic_config(regime)

        # Step 3: Apply discourse act overrides
        config = self._apply_discourse_overrides(
            base_config=base_config,
            discourse_act=discourse_act,
            regime=regime,
        )

        # Step 4: Enforce hard parameter bounds and build frame
        return self._build_frame_with_bounds(
            config=config,
            regime=regime,
            discourse_act=discourse_act,
            lexical_frame=lexical_frame,
        )

    def _get_regime_acoustic_config(
        self,
        regime: OperationalRegime,
    ) -> Dict[str, Any]:
        """
        Get the base acoustic configuration for a regime.

        Args:
            regime: The operational regime.

        Returns:
            Dictionary of acoustic configuration parameters.
        """
        return REGIME_ACOUSTIC_MAP.get(regime, SAFE_DEFAULT_CONFIG).copy()

    def _apply_discourse_overrides(
        self,
        base_config: Dict[str, Any],
        discourse_act: DiscourseAct,
        regime: OperationalRegime,
    ) -> Dict[str, Any]:
        """
        Apply discourse act-specific overrides to acoustic config.

        Discourse Act Overrides (per specification):
        - REFLECTION -> max_stressed_tokens = 0
        - DEFERRAL -> suppress_certainty = True
        - QUESTION -> no pitch-rise logic (we don't implement pitch contours)
        - EXPLANATION -> only if regime allows

        Args:
            base_config: The base acoustic configuration.
            discourse_act: The discourse act from P7.
            regime: The operational regime from P6.

        Returns:
            Modified acoustic configuration.
        """
        config = base_config.copy()

        # REFLECTION: Force max_stressed_tokens = 0
        if discourse_act == DiscourseAct.REFLECTION:
            config["max_stressed_tokens"] = 0
            config["emphasis_policy"] = EmphasisPolicy.NONE

        # DEFERRAL: Force suppress_certainty = True
        if discourse_act == DiscourseAct.DEFERRAL:
            config["suppress_certainty"] = True

        # QUESTION: No special pitch-rise logic (we don't implement contours)
        # Just ensure we don't add any emphasis for questions under careful regimes
        if discourse_act == DiscourseAct.QUESTION:
            if regime in {
                OperationalRegime.HOLD,
                OperationalRegime.STABILIZE,
                OperationalRegime.DE_ESCALATE,
            }:
                config["max_stressed_tokens"] = 0
                config["emphasis_policy"] = EmphasisPolicy.NONE

        # EXPLANATION: Only allow emphasis if regime permits
        if discourse_act == DiscourseAct.EXPLANATION:
            if regime in {
                OperationalRegime.HOLD,
                OperationalRegime.STABILIZE,
                OperationalRegime.DE_ESCALATE,
            }:
                config["max_stressed_tokens"] = 0
                config["emphasis_policy"] = EmphasisPolicy.NONE

        # ACKNOWLEDGMENT: Minimal, no emphasis
        if discourse_act == DiscourseAct.ACKNOWLEDGMENT:
            config["max_stressed_tokens"] = 0
            config["emphasis_policy"] = EmphasisPolicy.NONE

        # INSTRUCTION: Only allow emphasis under INFORM/CLARIFY
        if discourse_act == DiscourseAct.INSTRUCTION:
            if regime not in {OperationalRegime.INFORM, OperationalRegime.CLARIFY}:
                config["max_stressed_tokens"] = 0
                config["emphasis_policy"] = EmphasisPolicy.NONE

        return config

    def _build_frame_with_bounds(
        self,
        config: Dict[str, Any],
        regime: OperationalRegime,
        discourse_act: DiscourseAct,
        lexical_frame: Optional[LexicalFrame],
    ) -> AcousticParameterFrame:
        """
        Build an AcousticParameterFrame with enforced bounds.

        All parameters are clamped to valid ranges before frame construction.

        Args:
            config: The acoustic configuration dictionary.
            regime: The operational regime.
            discourse_act: The discourse act.
            lexical_frame: The P9 lexical frame (for debug tracing).

        Returns:
            AcousticParameterFrame with valid, bounded parameters.
        """
        # Clamp all numeric parameters to bounds
        speech_rate = clamp_speech_rate(config["speech_rate"])
        energy_level = clamp_energy_level(config["energy_level"])

        pitch_low, pitch_high = config["pitch_range"]
        pitch_range = (
            clamp_pitch(pitch_low),
            clamp_pitch(pitch_high),
        )
        # Ensure low <= high
        if pitch_range[0] > pitch_range[1]:
            pitch_range = (pitch_range[1], pitch_range[0])

        pause_low, pause_high = config["pause_duration_ms"]
        pause_duration_ms = (
            clamp_pause_duration(pause_low),
            clamp_pause_duration(pause_high),
        )
        # Ensure low <= high
        if pause_duration_ms[0] > pause_duration_ms[1]:
            pause_duration_ms = (pause_duration_ms[1], pause_duration_ms[0])

        # Clamp max_stressed_tokens
        max_stressed = config["max_stressed_tokens"]
        max_stressed = max(0, min(1, max_stressed))

        # Build debug info
        debug = self._build_debug_info(
            config=config,
            regime=regime,
            discourse_act=discourse_act,
            lexical_frame=lexical_frame,
        )

        return AcousticParameterFrame(
            regime=config["regime"],
            speech_rate=speech_rate,
            energy_level=energy_level,
            pitch_range=pitch_range,
            pause_policy=config["pause_policy"],
            pause_duration_ms=pause_duration_ms,
            emphasis_policy=config["emphasis_policy"],
            max_stressed_tokens=max_stressed,
            suppress_emotion=config["suppress_emotion"],
            suppress_emphasis=config["suppress_emphasis"],
            suppress_certainty=config["suppress_certainty"],
            source_regime=regime.value,
            source_discourse_act=discourse_act.value,
            debug=debug,
        )

    def _build_safe_default_frame(
        self,
        reason: str,
        regime_envelope: Optional[RegimeEnvelope] = None,
        discourse_envelope: Optional[DiscourseEnvelope] = None,
    ) -> AcousticParameterFrame:
        """
        Build a SAFE_DEFAULT frame when inputs are missing or invalid.

        The SAFE_DEFAULT is the HOLD acoustic configuration - the most
        conservative, minimal-expression output.

        Args:
            reason: Reason for falling back to SAFE_DEFAULT.
            regime_envelope: The regime envelope (may be None).
            discourse_envelope: The discourse envelope (may be None).

        Returns:
            SAFE_DEFAULT AcousticParameterFrame.
        """
        config = SAFE_DEFAULT_CONFIG.copy()

        source_regime = (
            regime_envelope.regime.value
            if regime_envelope is not None
            else "HOLD"
        )
        source_discourse_act = (
            discourse_envelope.act.value
            if discourse_envelope is not None
            else "DEFERRAL"
        )

        return AcousticParameterFrame(
            regime=config["regime"],
            speech_rate=config["speech_rate"],
            energy_level=config["energy_level"],
            pitch_range=config["pitch_range"],
            pause_policy=config["pause_policy"],
            pause_duration_ms=config["pause_duration_ms"],
            emphasis_policy=config["emphasis_policy"],
            max_stressed_tokens=config["max_stressed_tokens"],
            suppress_emotion=config["suppress_emotion"],
            suppress_emphasis=config["suppress_emphasis"],
            suppress_certainty=config["suppress_certainty"],
            source_regime=source_regime,
            source_discourse_act=source_discourse_act,
            debug={
                "safe_default_reason": reason,
                "is_safe_default": True,
            },
        )

    def _build_debug_info(
        self,
        config: Dict[str, Any],
        regime: OperationalRegime,
        discourse_act: DiscourseAct,
        lexical_frame: Optional[LexicalFrame],
    ) -> Dict[str, Any]:
        """Build debug information for tracing."""
        return {
            "source_regime": regime.value,
            "source_discourse_act": discourse_act.value,
            "acoustic_regime": config["regime"].value,
            "has_lexical_frame": lexical_frame is not None,
            "lexical_selection_count": (
                lexical_frame.count() if lexical_frame is not None else 0
            ),
            "is_safe_default": False,
        }


# Public exports
__all__ = [
    "P10AcousticResolver",
    # Config constants for testing/inspection
    "HOLD_ACOUSTIC_CONFIG",
    "DE_ESCALATE_ACOUSTIC_CONFIG",
    "STABILIZE_ACOUSTIC_CONFIG",
    "REFLECT_ACOUSTIC_CONFIG",
    "INFORM_ACOUSTIC_CONFIG",
    "CLARIFY_ACOUSTIC_CONFIG",
    "REGIME_ACOUSTIC_MAP",
    "SAFE_DEFAULT_CONFIG",
]
