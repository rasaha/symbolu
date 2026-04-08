"""
DHA (Delivery Harmonization Algorithm) Engine
==============================================

Main computation engine for delivery modulation parameters.

This engine:
- Runs after Fusion and before Renderer
- Computes delivery modulation from closed-form formulas
- Outputs full audit metadata
- Does NOT modify semantic content
- Does NOT do psychology inference
- Does NOT do moral judgments
- Introduces NO learning, feedback loops, or state

Version: 1.0
Date: 2025-12-22
"""

import logging
from typing import Any, Dict, Optional, Tuple, Union

from .config import DHAConfig, EntropySource
from .types import (
    DHAInputs,
    DHAResult,
    DHANoOpResult,
    ToneWeights,
    DeliveryProfile,
)
from .math import (
    get_normalized_entropy,
    compute_tone_logits,
    softmax3,
    compute_intensity,
    compute_restraint,
    compute_delivery_factor_simple,
    round_for_audit,
    round_dict_for_audit,
    clamp,
)

logger = logging.getLogger(__name__)


# =============================================================================
# DHA Engine
# =============================================================================

class DHAEngine:
    """
    Delivery Harmonization Algorithm Engine.

    Computes delivery modulation parameters from upstream signals
    using closed-form, deterministic formulas.

    Architecture:
        Fusion → DHA → Renderer

    Key Properties:
        - Tier-safe: Different configs per tier
        - Deterministic: Same inputs = same outputs
        - Zero-parameter: No learned parameters
        - Formula-only: Closed-form computations
        - Full audit: Complete metadata trail

    Usage:
        engine = DHAEngine(config)
        base_output, result = engine.apply(base_output, signals)

        # Or with pipeline context
        engine = DHAEngine.from_tier("enterprise_tier_1")
        base_output, result = engine.apply(base_output, signals)

    Example:
        config = DHAConfig(enabled=True)
        engine = DHAEngine(config)

        signals = DHAInputs.from_pipeline_signals(
            coherence_score=0.8,
            motion_magnitude=0.3,
            guna_entropy=0.5,
            sattva=0.5, rajas=0.3, tamas=0.2,
            tier="consumer"
        )

        base_output = "This is the response."
        output, result = engine.apply(base_output, signals)
        print(f"D = {result.D}")
        print(f"Dominant tone: {result.dominant_tone}")
    """

    def __init__(self, config: Optional[DHAConfig] = None):
        """
        Initialize DHA Engine.

        Args:
            config: DHA configuration (default: disabled)
        """
        self.config = config or DHAConfig()
        self._run_count = 0

    @classmethod
    def from_tier(cls, tier: str) -> "DHAEngine":
        """
        Create engine with tier-specific configuration.

        Args:
            tier: One of "enterprise_tier_1", "enterprise_tier_2", "consumer"

        Returns:
            DHAEngine with tier-appropriate config
        """
        config = DHAConfig.for_tier(tier)
        return cls(config)

    def apply(
        self,
        base_output: Any,
        signals: DHAInputs,
        config_override: Optional[DHAConfig] = None,
    ) -> Tuple[Any, Union[DHAResult, DHANoOpResult]]:
        """
        Apply DHA to base output.

        This is the main entry point for the engine.

        IMPORTANT:
        - Does NOT modify base_output semantically
        - Computes modulation parameters only
        - Attaches metadata for renderer consumption
        - Provides delivery profile as output

        Args:
            base_output: The base output from Fusion (unchanged)
            signals: Input signals from pipeline
            config_override: Optional config override for this call

        Returns:
            Tuple of (base_output, DHAResult or DHANoOpResult)
            - base_output is returned unchanged
            - Result contains computed modulation parameters and audit
        """
        config = config_override or self.config
        self._run_count += 1

        # Check if DHA is enabled
        if not config.enabled:
            logger.debug("DHA disabled via config, returning no-op result")
            return base_output, DHANoOpResult(
                enabled=False,
                reason="DHA disabled via config",
            )

        try:
            result = self._compute(signals, config)
            logger.debug(
                f"DHA computed: D={result.D:.4f}, "
                f"tone={result.dominant_tone}, "
                f"I={result.I:.4f}, R={result.R:.4f}"
            )
            return base_output, result

        except Exception as e:
            logger.error(f"DHA computation failed: {e}")
            # Return no-op on error to maintain pipeline stability
            return base_output, DHANoOpResult(
                enabled=True,
                reason=f"DHA computation failed: {str(e)}",
            )

    def _compute(self, signals: DHAInputs, config: DHAConfig) -> DHAResult:
        """
        Core DHA computation.

        Implements all formulas:
            1. H normalization based on entropy source
            2. Tone logits: l_sweet, l_jolt, l_meta
            3. Tone weights: softmax([l_sweet, l_jolt, l_meta])
            4. Intensity: I = clip(alpha1*C_s + alpha2*M - alpha3*H, I_min, I_max)
            5. Restraint: R = clamp(1 - risk_bias - escalation_bias, 0, 1)
            6. Delivery factor: D = T × I × R

        Args:
            signals: Input signals
            config: DHA configuration

        Returns:
            DHAResult with all computed values and audit
        """
        numerics = config.numerics
        precision = numerics.float_precision

        # =====================================================================
        # Step 1: Normalize entropy based on source
        # =====================================================================
        entropy_source_str = config.entropy_source.value
        normalized_H, source_used, raw_entropy = get_normalized_entropy(
            H_G=signals.H_G,
            H_D=signals.H_D,
            H_K=signals.H_K,
            source=entropy_source_str,
        )

        # =====================================================================
        # Step 2: Compute tone logits
        # =====================================================================
        tone_cfg = config.tone_logits
        l_sweet, l_jolt, l_meta = compute_tone_logits(
            s=signals.s,
            r=signals.r,
            t=signals.t,
            H=normalized_H,
            C_contr=signals.C_contr,
            k1=tone_cfg.k1,
            k2=tone_cfg.k2,
            k3=tone_cfg.k3,
            k4=tone_cfg.k4,
            k5=tone_cfg.k5,
            k6=tone_cfg.k6,
        )

        # =====================================================================
        # Step 3: Compute tone weights via softmax
        # =====================================================================
        w_sweet, w_jolt, w_meta = softmax3(
            l_sweet, l_jolt, l_meta,
            temperature=numerics.softmax_temperature,
        )

        # Create ToneWeights (validates sum = 1)
        tone_weights = ToneWeights(
            sweet=w_sweet,
            jolt=w_jolt,
            metaphor=w_meta,
        )

        # =====================================================================
        # Step 4: Compute intensity scalar
        # =====================================================================
        intensity_cfg = config.intensity
        I = compute_intensity(
            C_s=signals.C_s,
            M=signals.M,
            H=normalized_H,
            alpha1=intensity_cfg.alpha1,
            alpha2=intensity_cfg.alpha2,
            alpha3=intensity_cfg.alpha3,
            I_min=intensity_cfg.I_min,
            I_max=intensity_cfg.I_max,
        )

        # =====================================================================
        # Step 5: Compute restraint scalar
        # =====================================================================
        restraint_cfg = config.restraint
        R = compute_restraint(
            risk_bias=restraint_cfg.risk_bias,
            escalation_bias=restraint_cfg.escalation_bias,
        )

        # =====================================================================
        # Step 6: Compute delivery modulation factor
        # =====================================================================
        # D = T × I × R where T is implicit (using weights directly)
        # For simplicity, D = I × R (T = 1 for normalized weights)
        D = compute_delivery_factor_simple(I, R)

        # =====================================================================
        # Step 7: Check for suppression (extreme low D)
        # =====================================================================
        suppressed = D < 0.1  # Threshold for effective suppression

        # =====================================================================
        # Step 8: Build audit trail
        # =====================================================================
        audit = {
            # Configuration used
            "enabled": True,
            "entropy_source_config": config.entropy_source.value,

            # Entropy normalization
            "entropy_source_used": source_used,
            "raw_entropy": round_for_audit(raw_entropy, precision),
            "normalized_H": round_for_audit(normalized_H, precision),

            # Inputs
            "inputs": {
                "C_s": round_for_audit(signals.C_s, precision),
                "M": round_for_audit(signals.M, precision),
                "H_G": round_for_audit(signals.H_G, precision) if signals.H_G else None,
                "H_D": round_for_audit(signals.H_D, precision) if signals.H_D else None,
                "H_K": round_for_audit(signals.H_K, precision) if signals.H_K else None,
                "C_contr": round_for_audit(signals.C_contr, precision),
                "s": round_for_audit(signals.s, precision),
                "r": round_for_audit(signals.r, precision),
                "t": round_for_audit(signals.t, precision),
            },

            # Tone computation
            "logits": {
                "l_sweet": round_for_audit(l_sweet, precision),
                "l_jolt": round_for_audit(l_jolt, precision),
                "l_meta": round_for_audit(l_meta, precision),
            },
            "weights": {
                "sweet": round_for_audit(w_sweet, precision),
                "jolt": round_for_audit(w_jolt, precision),
                "metaphor": round_for_audit(w_meta, precision),
            },

            # Scalars
            "I": round_for_audit(I, precision),
            "R": round_for_audit(R, precision),
            "D": round_for_audit(D, precision),

            # Context
            "tier": signals.tier.value,
            "base_text_ref": signals.base_text_ref,
            "missing_signals": list(signals.missing_signals),
            "has_missing_signals": signals.has_missing_signals,
            "suppressed": suppressed,
        }

        return DHAResult(
            tone_weights=tone_weights,
            I=I,
            R=R,
            D=D,
            suppressed=suppressed,
            audit=audit,
        )

    def get_delivery_profile(self, result: DHAResult) -> DeliveryProfile:
        """
        Extract delivery profile from DHA result.

        This profile can be passed to the renderer for
        presentation adjustments (without changing semantics).

        Args:
            result: DHAResult from apply()

        Returns:
            DeliveryProfile for renderer consumption
        """
        return DeliveryProfile(
            dominant_tone=result.dominant_tone,
            tone_weights=result.tone_weights,
            intensity=result.I,
            restraint=result.R,
            modulation_factor=result.D,
        )

    def get_stats(self) -> Dict[str, Any]:
        """Get engine statistics."""
        return {
            "run_count": self._run_count,
            "config_enabled": self.config.enabled,
            "entropy_source": self.config.entropy_source.value,
        }


# =============================================================================
# Convenience Functions
# =============================================================================

def apply_dha(
    base_output: Any,
    signals: DHAInputs,
    config: Optional[DHAConfig] = None,
) -> Tuple[Any, Union[DHAResult, DHANoOpResult]]:
    """
    Convenience function to apply DHA.

    Args:
        base_output: Base output from Fusion
        signals: Input signals
        config: Optional DHA configuration

    Returns:
        Tuple of (base_output, result)
    """
    engine = DHAEngine(config)
    return engine.apply(base_output, signals)


def compute_dha(
    coherence_score: float = 0.5,
    motion_magnitude: float = 0.0,
    guna_entropy: float = 0.0,
    contradiction: float = 0.0,
    sattva: float = 0.333,
    rajas: float = 0.333,
    tamas: float = 0.334,
    tier: str = "consumer",
    enabled: bool = True,
) -> Union[DHAResult, DHANoOpResult]:
    """
    Quick DHA computation with minimal parameters.

    Args:
        coherence_score: C_s [0, 1]
        motion_magnitude: M [0, 1]
        guna_entropy: H_G [0, 1]
        contradiction: C_contr [0, 1]
        sattva: s [0, 1]
        rajas: r [0, 1]
        tamas: t [0, 1]
        tier: Tier identifier
        enabled: Whether DHA is enabled

    Returns:
        DHAResult or DHANoOpResult
    """
    config = DHAConfig(enabled=enabled)
    signals = DHAInputs.from_pipeline_signals(
        coherence_score=coherence_score,
        motion_magnitude=motion_magnitude,
        guna_entropy=guna_entropy,
        contradiction=contradiction,
        sattva=sattva,
        rajas=rajas,
        tamas=tamas,
        tier=tier,
    )

    _, result = apply_dha(None, signals, config)
    return result


# =============================================================================
# Public Exports
# =============================================================================

__all__ = [
    "DHAEngine",
    "apply_dha",
    "compute_dha",
]
