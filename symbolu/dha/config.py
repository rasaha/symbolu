"""
DHA (Delivery Harmonization Algorithm) Configuration
=====================================================

Tier-safe, deterministic, zero-parameter, formula-only configuration.

This module provides configuration structures for the DHA engine.
All configurations use frozen dataclasses for determinism and immutability.

Version: 1.0
Date: 2025-12-22
"""

from dataclasses import dataclass, field
from typing import Literal, Dict, Any
from enum import Enum


# =============================================================================
# Entropy Source Configuration
# =============================================================================

class EntropySource(Enum):
    """
    Entropy source selection for H normalization.

    Option A (default): H = H_G / ln(3)  (Guna entropy)
    Option B: H = H_D / ln(10)  (Dimensional/cross-domain entropy)
    Option C: H = H_K / ln(5)   (Kosha entropy)
    """
    GUNA = "guna"              # Option A: H_G / ln(3)
    DIMENSIONAL = "dimensional"  # Option B: H_D / ln(10)
    KOSHA = "kosha"            # Option C: H_K / ln(5)


# =============================================================================
# Tone Logit Configuration
# =============================================================================

@dataclass(frozen=True)
class ToneLogitConfig:
    """
    Configuration for tone weight logit computation.

    Logit formulas:
        l_sweet = k1*s - k2*t
        l_jolt  = k3*r + k4*C_contr
        l_meta  = k5*H + k6*r

    Where:
        s: Sattva component [0, 1]
        r: Rajas component [0, 1]
        t: Tamas component [0, 1]
        H: Normalized entropy [0, 1]
        C_contr: Contradiction metric [0, 1]

    All coefficients are bounded to prevent extreme outputs.
    """
    # Sweet resonance coefficients
    k1: float = 2.0  # Weight for Sattva in sweet logit
    k2: float = 1.5  # Weight for Tamas (negative) in sweet logit

    # Inverse jolt coefficients
    k3: float = 1.8  # Weight for Rajas in jolt logit
    k4: float = 2.2  # Weight for Contradiction in jolt logit

    # Symbolic metaphor coefficients
    k5: float = 1.5  # Weight for Entropy in meta logit
    k6: float = 1.0  # Weight for Rajas in meta logit

    # Bounds for coefficients
    k_min: float = 0.1
    k_max: float = 5.0

    def __post_init__(self):
        """Validate coefficient bounds."""
        for name in ('k1', 'k2', 'k3', 'k4', 'k5', 'k6'):
            val = getattr(self, name)
            if not (self.k_min <= val <= self.k_max):
                raise ValueError(
                    f"Coefficient {name}={val} out of bounds [{self.k_min}, {self.k_max}]"
                )

    def to_dict(self) -> Dict[str, float]:
        """Convert to dictionary."""
        return {
            "k1": self.k1,
            "k2": self.k2,
            "k3": self.k3,
            "k4": self.k4,
            "k5": self.k5,
            "k6": self.k6,
        }


# =============================================================================
# Intensity Configuration
# =============================================================================

@dataclass(frozen=True)
class IntensityConfig:
    """
    Configuration for intensity scalar computation.

    Formula:
        I = clip(alpha1*C_s + alpha2*M - alpha3*H, I_min, I_max)

    Where:
        C_s: Structural coherence score [0, 1]
        M: Motion/transformation magnitude [0, 1]
        H: Normalized entropy [0, 1]
    """
    # Alpha coefficients
    alpha1: float = 0.4  # Weight for coherence (positive influence)
    alpha2: float = 0.3  # Weight for motion (positive influence)
    alpha3: float = 0.2  # Weight for entropy (negative influence)

    # Output bounds
    I_min: float = 0.3   # Minimum intensity (never fully suppress)
    I_max: float = 1.0   # Maximum intensity

    # Coefficient bounds
    alpha_min: float = 0.0
    alpha_max: float = 1.0

    def __post_init__(self):
        """Validate configuration bounds."""
        for name in ('alpha1', 'alpha2', 'alpha3'):
            val = getattr(self, name)
            if not (self.alpha_min <= val <= self.alpha_max):
                raise ValueError(
                    f"Coefficient {name}={val} out of bounds [{self.alpha_min}, {self.alpha_max}]"
                )

        if self.I_min < 0.0 or self.I_min > 1.0:
            raise ValueError(f"I_min={self.I_min} must be in [0.0, 1.0]")
        if self.I_max < 0.0 or self.I_max > 1.0:
            raise ValueError(f"I_max={self.I_max} must be in [0.0, 1.0]")
        if self.I_min > self.I_max:
            raise ValueError(f"I_min={self.I_min} cannot exceed I_max={self.I_max}")

    def to_dict(self) -> Dict[str, float]:
        """Convert to dictionary."""
        return {
            "alpha1": self.alpha1,
            "alpha2": self.alpha2,
            "alpha3": self.alpha3,
            "I_min": self.I_min,
            "I_max": self.I_max,
        }


# =============================================================================
# Restraint Configuration
# =============================================================================

@dataclass(frozen=True)
class RestraintConfig:
    """
    Configuration for restraint scalar computation.

    Formula:
        R = clamp(1 - risk_bias - escalation_bias, 0, 1)

    The restraint scalar represents how much to hold back delivery.
    Higher restraint = more cautious delivery.
    """
    # Bias values (reduce restraint capacity)
    risk_bias: float = 0.0       # Default: no risk bias
    escalation_bias: float = 0.0  # Default: no escalation bias

    # Bounds
    bias_min: float = 0.0
    bias_max: float = 1.0

    def __post_init__(self):
        """Validate bias bounds."""
        for name in ('risk_bias', 'escalation_bias'):
            val = getattr(self, name)
            if not (self.bias_min <= val <= self.bias_max):
                raise ValueError(
                    f"Bias {name}={val} out of bounds [{self.bias_min}, {self.bias_max}]"
                )

        # Warn if total bias exceeds 1 (would clamp R to 0)
        total = self.risk_bias + self.escalation_bias
        if total > 1.0:
            # This is valid but means maximum restraint
            pass

    def to_dict(self) -> Dict[str, float]:
        """Convert to dictionary."""
        return {
            "risk_bias": self.risk_bias,
            "escalation_bias": self.escalation_bias,
        }


# =============================================================================
# Numerics Configuration
# =============================================================================

@dataclass(frozen=True)
class NumericsConfig:
    """
    Numerical stability and rounding configuration.

    Ensures deterministic float behavior across platforms.
    """
    # Small epsilon for numerical stability
    epsilon: float = 1e-9

    # Decimal places for rounding in audits
    float_precision: int = 6

    # Softmax temperature (1.0 = standard)
    softmax_temperature: float = 1.0

    def __post_init__(self):
        """Validate numerics configuration."""
        if self.epsilon <= 0.0:
            raise ValueError(f"epsilon={self.epsilon} must be positive")
        if self.float_precision < 0:
            raise ValueError(f"float_precision={self.float_precision} must be non-negative")
        if self.softmax_temperature <= 0.0:
            raise ValueError(f"softmax_temperature={self.softmax_temperature} must be positive")

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "epsilon": self.epsilon,
            "float_precision": self.float_precision,
            "softmax_temperature": self.softmax_temperature,
        }


# =============================================================================
# Main DHA Configuration
# =============================================================================

@dataclass(frozen=True)
class DHAConfig:
    """
    Main DHA (Delivery Harmonization Algorithm) configuration.

    DHA is disabled by default via the `enabled` flag.
    When disabled, DHA stage is a no-op and passes through unchanged.

    Attributes:
        enabled: Whether DHA is active (default: False)
        entropy_source: Which entropy source to use for H normalization
        tone_logits: Configuration for tone weight computation
        intensity: Configuration for intensity scalar
        restraint: Configuration for restraint scalar
        numerics: Numerical stability configuration

    Example:
        # Default (disabled)
        config = DHAConfig()
        assert config.enabled is False

        # Enabled with default settings
        config = DHAConfig(enabled=True)

        # Custom configuration
        config = DHAConfig(
            enabled=True,
            entropy_source=EntropySource.KOSHA,
            intensity=IntensityConfig(alpha1=0.5, alpha2=0.3, alpha3=0.2),
        )
    """
    # Master switch (disabled by default)
    enabled: bool = False

    # Entropy source selection (default: Option A = Guna)
    entropy_source: EntropySource = field(default=EntropySource.GUNA)

    # Sub-configurations
    tone_logits: ToneLogitConfig = field(default_factory=ToneLogitConfig)
    intensity: IntensityConfig = field(default_factory=IntensityConfig)
    restraint: RestraintConfig = field(default_factory=RestraintConfig)
    numerics: NumericsConfig = field(default_factory=NumericsConfig)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "enabled": self.enabled,
            "entropy_source": self.entropy_source.value,
            "tone_logits": self.tone_logits.to_dict(),
            "intensity": self.intensity.to_dict(),
            "restraint": self.restraint.to_dict(),
            "numerics": self.numerics.to_dict(),
        }

    @classmethod
    def for_tier(cls, tier: str) -> "DHAConfig":
        """
        Get tier-specific configuration.

        Args:
            tier: One of "enterprise_tier_1", "enterprise_tier_2", "consumer"

        Returns:
            DHAConfig appropriate for the tier.
        """
        if tier == "enterprise_tier_1":
            # Tier 1: Minimal modulation, conservative
            return cls(
                enabled=True,
                entropy_source=EntropySource.GUNA,
                intensity=IntensityConfig(alpha1=0.3, alpha2=0.2, alpha3=0.1, I_min=0.5),
                restraint=RestraintConfig(risk_bias=0.1, escalation_bias=0.0),
            )
        elif tier == "enterprise_tier_2":
            # Tier 2: Moderate modulation
            return cls(
                enabled=True,
                entropy_source=EntropySource.GUNA,
                intensity=IntensityConfig(alpha1=0.4, alpha2=0.3, alpha3=0.2, I_min=0.4),
                restraint=RestraintConfig(risk_bias=0.05, escalation_bias=0.0),
            )
        elif tier == "consumer":
            # Consumer: Full modulation available
            return cls(
                enabled=True,
                entropy_source=EntropySource.GUNA,
                intensity=IntensityConfig(alpha1=0.5, alpha2=0.35, alpha3=0.25, I_min=0.3),
                restraint=RestraintConfig(risk_bias=0.0, escalation_bias=0.0),
            )
        else:
            # Unknown tier: disabled
            return cls(enabled=False)

    @classmethod
    def disabled(cls) -> "DHAConfig":
        """Return a disabled DHA configuration."""
        return cls(enabled=False)


# =============================================================================
# Public Exports
# =============================================================================

__all__ = [
    "DHAConfig",
    "EntropySource",
    "ToneLogitConfig",
    "IntensityConfig",
    "RestraintConfig",
    "NumericsConfig",
]
