"""
P10 Prosody Mapper - Maps cognitive state to TTS parameters.

This module bridges Sentinel's coherence state and P10 acoustic parameters
to voice provider TTS settings, enabling coherence-driven voice modulation.

Key features:
- Map P10 acoustic regimes to TTS parameters
- Modulate voice based on coherence state
- Provider-specific parameter translation
- SSML generation for enhanced prosody control
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional

from ..providers.base import TTSParams

logger = logging.getLogger(__name__)


class AcousticRegime(Enum):
    """
    Acoustic regimes from P10 pipeline.

    These regimes define the overall character of speech output.
    """
    NEUTRAL = "neutral"       # Normal conversational tone
    SOFT = "soft"             # Gentler, more empathetic delivery
    FLAT = "flat"             # Reduced expressiveness, factual
    RESTRAINED = "restrained" # Careful, measured delivery


@dataclass
class ProsodyModulation:
    """Modulation values for TTS parameters."""
    speed_modifier: float = 1.0      # Multiplier for speed
    stability_modifier: float = 1.0  # Multiplier for stability
    pitch_modifier: float = 0.0      # Additive pitch shift (semitones)
    style_modifier: float = 1.0      # Multiplier for expressiveness
    pause_multiplier: float = 1.0    # Multiplier for pauses


@dataclass
class P10ProsodyConfig:
    """Configuration for P10 prosody mapping."""
    default_voice_id: str = "sonic-english-male"
    default_speed: float = 1.0
    default_stability: float = 0.7
    default_style: float = 0.5

    # Thresholds for coherence-based modulation
    low_coherence_threshold: float = 0.5
    high_uncertainty_threshold: float = 0.6
    degrading_trend_threshold: float = -0.1

    # Maximum modulation limits
    min_speed: float = 0.6
    max_speed: float = 1.4
    min_stability: float = 0.3
    max_stability: float = 1.0


class P10ProsodyMapper:
    """
    Maps P10 acoustic parameters and coherence state to TTS settings.

    This is where Symbolu's cognitive state influences voice output:
    - Low coherence → slower, more deliberate speech
    - High uncertainty → hedging tone, softer delivery
    - High confidence → normal pace, assertive tone
    - Safety concerns → explicit verbal markers

    Usage:
        mapper = P10ProsodyMapper()
        tts_params = mapper.compute_params(
            coherence_state=sentinel.coherence_state,
            safety_contract=sentinel.safety_contract
        )
    """

    # Base mappings from P10 regimes to TTS parameters
    REGIME_MAPPINGS: Dict[AcousticRegime, Dict[str, float]] = {
        AcousticRegime.NEUTRAL: {
            "speed": 1.0,
            "stability": 0.7,
            "pitch_shift": 0,
            "style": 0.5
        },
        AcousticRegime.SOFT: {
            "speed": 0.9,
            "stability": 0.8,
            "pitch_shift": -1,
            "style": 0.3
        },
        AcousticRegime.FLAT: {
            "speed": 1.0,
            "stability": 0.9,
            "pitch_shift": 0,
            "style": 0.1
        },
        AcousticRegime.RESTRAINED: {
            "speed": 0.85,
            "stability": 0.85,
            "pitch_shift": -1,
            "style": 0.2
        }
    }

    # Coherence-based modulations
    COHERENCE_MODULATIONS: Dict[str, ProsodyModulation] = {
        "low_coherence": ProsodyModulation(
            speed_modifier=0.85,
            stability_modifier=1.1,
            pause_multiplier=1.3
        ),
        "high_uncertainty": ProsodyModulation(
            speed_modifier=0.9,
            style_modifier=0.7
        ),
        "degrading_coherence": ProsodyModulation(
            speed_modifier=0.9,
            stability_modifier=1.05
        ),
        "safety_concern": ProsodyModulation(
            speed_modifier=0.85,
            stability_modifier=1.15,
            pause_multiplier=1.2
        )
    }

    def __init__(self, config: Optional[P10ProsodyConfig] = None):
        """
        Initialize P10 prosody mapper.

        Args:
            config: Configuration for prosody mapping
        """
        self.config = config or P10ProsodyConfig()

    def compute_params(
        self,
        coherence_state: Optional[Any] = None,
        safety_contract: Optional[Any] = None,
        p10_regime: AcousticRegime = AcousticRegime.NEUTRAL,
        voice_id: Optional[str] = None,
        extra_params: Optional[Dict[str, Any]] = None
    ) -> TTSParams:
        """
        Compute TTS parameters from cognitive state.

        Priority order:
        1. Safety contract concerns (highest)
        2. Coherence state modulations
        3. P10 regime base settings
        4. Default values (lowest)

        Args:
            coherence_state: Sentinel CoherenceState object
            safety_contract: Sentinel SafetyContract object
            p10_regime: P10 acoustic regime
            voice_id: Override voice ID
            extra_params: Additional provider-specific parameters

        Returns:
            TTSParams configured for the current cognitive state
        """
        # Start with P10 regime base
        base = self.REGIME_MAPPINGS.get(
            p10_regime,
            self.REGIME_MAPPINGS[AcousticRegime.NEUTRAL]
        ).copy()

        # Apply coherence-based modulations
        if coherence_state is not None:
            base = self._apply_coherence_modulations(base, coherence_state)

        # Apply safety contract modulations
        if safety_contract is not None:
            base = self._apply_safety_modulations(base, safety_contract)

        # Clamp values to valid ranges
        base["speed"] = max(
            self.config.min_speed,
            min(self.config.max_speed, base["speed"])
        )
        base["stability"] = max(
            self.config.min_stability,
            min(self.config.max_stability, base["stability"])
        )
        base["style"] = max(0.0, min(1.0, base.get("style", 0.5)))

        return TTSParams(
            voice_id=voice_id or self.config.default_voice_id,
            speed=base["speed"],
            pitch_shift=base.get("pitch_shift", 0),
            stability=base["stability"],
            style=base.get("style", 0.5),
            extra_params=extra_params or {}
        )

    def _apply_coherence_modulations(
        self,
        base: Dict[str, float],
        coherence_state: Any
    ) -> Dict[str, float]:
        """Apply modulations based on coherence state."""
        try:
            metrics = coherence_state.current_metrics

            # Low overall coherence
            if hasattr(metrics, 'overall_coherence'):
                if metrics.overall_coherence < self.config.low_coherence_threshold:
                    mod = self.COHERENCE_MODULATIONS["low_coherence"]
                    base["speed"] *= mod.speed_modifier
                    base["stability"] = min(
                        1.0,
                        base["stability"] * mod.stability_modifier
                    )
                    logger.debug(
                        f"Applied low coherence modulation "
                        f"(coherence={metrics.overall_coherence:.2f})"
                    )

            # High prediction reversal risk
            if hasattr(metrics, 'prediction_reversal_risk'):
                if metrics.prediction_reversal_risk > self.config.high_uncertainty_threshold:
                    mod = self.COHERENCE_MODULATIONS["high_uncertainty"]
                    base["speed"] *= mod.speed_modifier
                    base["style"] = base.get("style", 0.5) * mod.style_modifier
                    logger.debug(
                        f"Applied high uncertainty modulation "
                        f"(reversal_risk={metrics.prediction_reversal_risk:.2f})"
                    )

            # Degrading coherence trend
            if hasattr(metrics, 'drift_direction'):
                if metrics.drift_direction == "degrading":
                    mod = self.COHERENCE_MODULATIONS["degrading_coherence"]
                    base["speed"] *= mod.speed_modifier
                    base["stability"] = min(
                        1.0,
                        base["stability"] * mod.stability_modifier
                    )
                    logger.debug("Applied degrading coherence modulation")

        except AttributeError as e:
            logger.warning(f"Could not access coherence metrics: {e}")

        return base

    def _apply_safety_modulations(
        self,
        base: Dict[str, float],
        safety_contract: Any
    ) -> Dict[str, float]:
        """Apply modulations based on safety contract."""
        try:
            # Safety contract not eligible - more cautious delivery
            if hasattr(safety_contract, 'eligible') and not safety_contract.eligible:
                mod = self.COHERENCE_MODULATIONS["safety_concern"]
                base["speed"] *= mod.speed_modifier
                base["stability"] = min(
                    1.0,
                    base["stability"] * mod.stability_modifier
                )
                logger.debug("Applied safety concern modulation")

        except AttributeError as e:
            logger.warning(f"Could not access safety contract: {e}")

        return base

    def _escape_ssml(self, text: str) -> str:
        """Escape SSML special characters to prevent injection.

        MEDIUM FIX: Prevent SSML injection attacks by escaping special characters.

        Args:
            text: Raw text that may contain SSML-like content

        Returns:
            Escaped text safe for SSML embedding
        """
        import html
        # Escape XML/HTML entities
        escaped = html.escape(text, quote=True)
        return escaped

    def compute_ssml(
        self,
        text: str,
        coherence_state: Optional[Any] = None,
        p10_regime: AcousticRegime = AcousticRegime.NEUTRAL
    ) -> str:
        """
        Add SSML prosody markers based on cognitive state.

        For providers that support SSML, this adds prosody markers
        for enhanced control over speech synthesis.

        Args:
            text: Input text to enhance
            coherence_state: Sentinel CoherenceState object
            p10_regime: P10 acoustic regime

        Returns:
            Text with SSML prosody markers
        """
        # MEDIUM FIX: Escape user text to prevent SSML injection
        ssml_text = self._escape_ssml(text)

        if coherence_state is not None:
            ssml_text = self._add_coherence_ssml(ssml_text, coherence_state)

        ssml_text = self._add_regime_ssml(ssml_text, p10_regime)

        return ssml_text

    def _add_coherence_ssml(self, text: str, coherence_state: Any) -> str:
        """Add SSML markers based on coherence state."""
        try:
            metrics = coherence_state.current_metrics

            # Add pauses after uncertainty markers when reversal risk is high
            if (hasattr(metrics, 'prediction_reversal_risk') and
                    metrics.prediction_reversal_risk > 0.5):
                uncertainty_words = [
                    "perhaps", "maybe", "possibly", "might", "could",
                    "probably", "likely", "seems", "appears"
                ]
                for word in uncertainty_words:
                    text = text.replace(
                        f" {word} ",
                        f' <break time="200ms"/> {word} '
                    )

            # Slower pace for complex explanations when coherence is low
            if (hasattr(metrics, 'overall_coherence') and
                    metrics.overall_coherence < 0.6):
                text = f'<prosody rate="90%">{text}</prosody>'

        except AttributeError:
            pass

        return text

    def _add_regime_ssml(self, text: str, regime: AcousticRegime) -> str:
        """Add SSML markers based on P10 regime."""
        if regime == AcousticRegime.SOFT:
            text = f'<prosody volume="soft">{text}</prosody>'
        elif regime == AcousticRegime.FLAT:
            text = f'<prosody pitch="0st" range="x-low">{text}</prosody>'
        elif regime == AcousticRegime.RESTRAINED:
            text = f'<prosody rate="90%" volume="medium">{text}</prosody>'

        return text

    def get_regime_for_coherence(
        self,
        coherence_state: Any
    ) -> AcousticRegime:
        """
        Automatically select P10 regime based on coherence state.

        Args:
            coherence_state: Sentinel CoherenceState object

        Returns:
            Recommended AcousticRegime
        """
        try:
            metrics = coherence_state.current_metrics

            # Very low coherence - use restrained
            if (hasattr(metrics, 'overall_coherence') and
                    metrics.overall_coherence < 0.4):
                return AcousticRegime.RESTRAINED

            # High uncertainty - use soft
            if (hasattr(metrics, 'prediction_reversal_risk') and
                    metrics.prediction_reversal_risk > 0.7):
                return AcousticRegime.SOFT

            # Factual responses with low emotion - use flat
            if (hasattr(metrics, 'goal_alignment') and
                    metrics.goal_alignment > 0.8 and
                    hasattr(metrics, 'overall_coherence') and
                    metrics.overall_coherence > 0.8):
                # High alignment and coherence - could be factual
                return AcousticRegime.FLAT

        except AttributeError:
            pass

        # Default to neutral
        return AcousticRegime.NEUTRAL

    def to_provider_params(
        self,
        params: TTSParams,
        provider: str
    ) -> Dict[str, Any]:
        """
        Convert generic TTSParams to provider-specific format.

        Args:
            params: Generic TTS parameters
            provider: Provider name ("cartesia", "elevenlabs", "deepgram")

        Returns:
            Provider-specific parameter dictionary
        """
        if provider == "cartesia":
            return self._to_cartesia_params(params)
        elif provider == "elevenlabs":
            return self._to_elevenlabs_params(params)
        elif provider == "deepgram":
            return self._to_deepgram_params(params)
        else:
            # Return generic params
            return {
                "voice_id": params.voice_id,
                "speed": params.speed,
                "pitch_shift": params.pitch_shift,
                "stability": params.stability,
                "style": params.style,
            }

    def _to_cartesia_params(self, params: TTSParams) -> Dict[str, Any]:
        """Convert to Cartesia Sonic parameters."""
        return {
            "voice_id": params.voice_id,
            "speed": params.speed,
            # Cartesia uses emotion instead of style
            "emotion": self._style_to_emotion(params.style),
        }

    def _to_elevenlabs_params(self, params: TTSParams) -> Dict[str, Any]:
        """Convert to ElevenLabs parameters."""
        return {
            "voice_id": params.voice_id,
            "stability": params.stability,
            "similarity_boost": params.similarity_boost,
            "style": params.style,
            "use_speaker_boost": True,
        }

    def _to_deepgram_params(self, params: TTSParams) -> Dict[str, Any]:
        """Convert to Deepgram Aura parameters."""
        return {
            "model": params.voice_id,
            # Deepgram has limited parameter support
        }

    def _style_to_emotion(self, style: float) -> str:
        """Map style value to Cartesia emotion."""
        if style < 0.3:
            return "neutral"
        elif style < 0.6:
            return "friendly"
        else:
            return "enthusiastic"
