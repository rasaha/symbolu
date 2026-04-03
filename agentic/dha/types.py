"""
DHA (Delivery Harmonization Algorithm) Types
=============================================

Type definitions for DHA inputs and outputs.

All types are frozen (immutable) dataclasses for determinism.
Full audit metadata is included in outputs.

Version: 1.0
Date: 2025-12-22
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional, Tuple
from enum import Enum


# =============================================================================
# Tier Enumeration
# =============================================================================

class Tier(Enum):
    """Tier identifier for DHA configuration."""
    ENTERPRISE_TIER_1 = "enterprise_tier_1"
    ENTERPRISE_TIER_2 = "enterprise_tier_2"
    CONSUMER = "consumer"


# =============================================================================
# Tone Weights
# =============================================================================

@dataclass(frozen=True)
class ToneWeights:
    """
    Tone selection weights computed from deterministic softmax.

    Invariant: sweet + jolt + metaphor = 1.0 (within floating tolerance)
    """
    sweet: float      # Sweet resonance weight [0, 1]
    jolt: float       # Inverse jolt weight [0, 1]
    metaphor: float   # Symbolic metaphor weight [0, 1]

    def __post_init__(self):
        """Validate weight sum."""
        total = self.sweet + self.jolt + self.metaphor
        tolerance = 1e-6
        if abs(total - 1.0) > tolerance:
            raise ValueError(
                f"Tone weights must sum to 1.0, got {total:.9f}"
            )

    def to_dict(self) -> Dict[str, float]:
        """Convert to dictionary."""
        return {
            "sweet": self.sweet,
            "jolt": self.jolt,
            "metaphor": self.metaphor,
        }

    @property
    def dominant_tone(self) -> str:
        """Return the dominant tone (highest weight)."""
        weights = {"sweet": self.sweet, "jolt": self.jolt, "metaphor": self.metaphor}
        return max(weights.keys(), key=lambda k: weights[k])


# =============================================================================
# DHA Inputs
# =============================================================================

@dataclass(frozen=True)
class DHAInputs:
    """
    Input signals for DHA computation.

    All signals are read from the existing pipeline.
    Missing signals use deterministic defaults and set missing_signal flags.

    Attributes:
        C_s: Structural coherence score [0, 1] (from pipeline or default 0.5)
        M: Motion/transformation magnitude [0, 1] (from semantic deltas or default 0.0)
        H_G: Guna entropy [0, 1] (or None if unavailable)
        H_D: Dimensional/cross-domain entropy [0, 1] (or None if unavailable)
        H_K: Kosha entropy [0, 1] (or None if unavailable)
        C_contr: Contradiction metric [0, 1] (or default 0.0)
        s: Sattva component [0, 1] (from Guna distribution)
        r: Rajas component [0, 1] (from Guna distribution)
        t: Tamas component [0, 1] (from Guna distribution)
        tier: Tier identifier
        base_text_ref: Reference/ID for the base output text (for audit trail)
        missing_signals: Set of signal names that used defaults

    Invariant: s + r + t = 1 (normalized Guna distribution)
    """
    # Core signals
    C_s: float = 0.5        # Structural coherence (default: neutral)
    M: float = 0.0          # Motion magnitude (default: no motion)

    # Entropy signals (all optional, use entropy_source to select)
    H_G: Optional[float] = None  # Guna entropy
    H_D: Optional[float] = None  # Dimensional entropy
    H_K: Optional[float] = None  # Kosha entropy

    # Contradiction metric
    C_contr: float = 0.0    # Contradiction (default: no contradiction)

    # Guna distribution (must sum to 1)
    s: float = 0.333333     # Sattva (default: balanced)
    r: float = 0.333333     # Rajas (default: balanced)
    t: float = 0.333334     # Tamas (default: balanced)

    # Context
    tier: Tier = Tier.CONSUMER
    base_text_ref: Optional[str] = None

    # Tracking missing signals
    missing_signals: Tuple[str, ...] = field(default=())

    def __post_init__(self):
        """Validate inputs and clamp to valid ranges."""
        # Clamp all float signals to [0, 1]
        for name in ('C_s', 'M', 'C_contr', 's', 'r', 't'):
            val = getattr(self, name)
            if val < 0.0 or val > 1.0:
                object.__setattr__(self, name, max(0.0, min(1.0, val)))

        # Clamp entropy signals if present
        for name in ('H_G', 'H_D', 'H_K'):
            val = getattr(self, name)
            if val is not None and (val < 0.0 or val > 1.0):
                object.__setattr__(self, name, max(0.0, min(1.0, val)))

        # Validate Guna distribution sums to 1
        guna_sum = self.s + self.r + self.t
        tolerance = 1e-6
        if abs(guna_sum - 1.0) > tolerance:
            # Normalize Guna distribution
            if guna_sum > 0:
                s_norm = self.s / guna_sum
                r_norm = self.r / guna_sum
                t_norm = self.t / guna_sum
                object.__setattr__(self, 's', s_norm)
                object.__setattr__(self, 'r', r_norm)
                object.__setattr__(self, 't', t_norm)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "C_s": self.C_s,
            "M": self.M,
            "H_G": self.H_G,
            "H_D": self.H_D,
            "H_K": self.H_K,
            "C_contr": self.C_contr,
            "s": self.s,
            "r": self.r,
            "t": self.t,
            "tier": self.tier.value,
            "base_text_ref": self.base_text_ref,
            "missing_signals": list(self.missing_signals),
        }

    @property
    def has_missing_signals(self) -> bool:
        """Check if any signals used defaults."""
        return len(self.missing_signals) > 0

    @classmethod
    def from_pipeline_signals(
        cls,
        coherence_score: Optional[float] = None,
        motion_magnitude: Optional[float] = None,
        guna_entropy: Optional[float] = None,
        dimensional_entropy: Optional[float] = None,
        kosha_entropy: Optional[float] = None,
        contradiction: Optional[float] = None,
        sattva: Optional[float] = None,
        rajas: Optional[float] = None,
        tamas: Optional[float] = None,
        tier: str = "consumer",
        base_text_ref: Optional[str] = None,
    ) -> "DHAInputs":
        """
        Factory to create DHAInputs from pipeline signals.

        Handles missing signals gracefully by using defaults
        and tracking which signals were missing.
        """
        missing = []

        # Core signals with defaults
        C_s = coherence_score if coherence_score is not None else 0.5
        if coherence_score is None:
            missing.append("C_s")

        M = motion_magnitude if motion_magnitude is not None else 0.0
        if motion_magnitude is None:
            missing.append("M")

        # Entropy signals (all optional)
        H_G = guna_entropy
        H_D = dimensional_entropy
        H_K = kosha_entropy

        # Track if no entropy available
        if H_G is None and H_D is None and H_K is None:
            missing.append("H")

        # Contradiction with default
        C_contr = contradiction if contradiction is not None else 0.0
        if contradiction is None:
            missing.append("C_contr")

        # Guna distribution with defaults
        if sattva is None or rajas is None or tamas is None:
            s_val = 0.333333
            r_val = 0.333333
            t_val = 0.333334
            missing.append("guna_distribution")
        else:
            s_val = sattva
            r_val = rajas
            t_val = tamas

        # Parse tier
        tier_map = {
            "enterprise_tier_1": Tier.ENTERPRISE_TIER_1,
            "enterprise_tier_2": Tier.ENTERPRISE_TIER_2,
            "consumer": Tier.CONSUMER,
        }
        tier_enum = tier_map.get(tier, Tier.CONSUMER)

        return cls(
            C_s=C_s,
            M=M,
            H_G=H_G,
            H_D=H_D,
            H_K=H_K,
            C_contr=C_contr,
            s=s_val,
            r=r_val,
            t=t_val,
            tier=tier_enum,
            base_text_ref=base_text_ref,
            missing_signals=tuple(missing),
        )


# =============================================================================
# DHA Result
# =============================================================================

@dataclass(frozen=True)
class DHAResult:
    """
    Result from DHA computation.

    Contains all computed values and full audit metadata.

    Attributes:
        tone_weights: Computed tone weights {sweet, jolt, metaphor}
        I: Intensity scalar [I_min, I_max]
        R: Restraint scalar [0, 1]
        D: Delivery modulation factor (T × I × R where T is tone vector norm)
        suppressed: Whether output was suppressed due to extreme values
        audit: Complete audit trail with all intermediates

    The audit dict includes:
        - entropy_source: Which entropy source was used
        - raw_entropy: The raw entropy value before normalization
        - normalized_H: The normalized H value
        - logits: {l_sweet, l_jolt, l_meta}
        - weights: {sweet, jolt, metaphor}
        - I, R, D values
        - tier
        - enabled flag
        - all input signals
        - missing_signals flags
    """
    tone_weights: ToneWeights
    I: float  # Intensity scalar
    R: float  # Restraint scalar
    D: float  # Delivery modulation factor
    suppressed: bool = False
    audit: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Validate result bounds."""
        if not (0.0 <= self.I <= 1.0):
            raise ValueError(f"Intensity I={self.I} must be in [0, 1]")
        if not (0.0 <= self.R <= 1.0):
            raise ValueError(f"Restraint R={self.R} must be in [0, 1]")
        if self.D < 0.0:
            raise ValueError(f"Delivery factor D={self.D} must be non-negative")

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "tone_weights": self.tone_weights.to_dict(),
            "I": self.I,
            "R": self.R,
            "D": self.D,
            "suppressed": self.suppressed,
            "audit": self.audit,
        }

    @property
    def dominant_tone(self) -> str:
        """Return the dominant tone profile."""
        return self.tone_weights.dominant_tone

    @property
    def is_high_intensity(self) -> bool:
        """Check if intensity is high (> 0.7)."""
        return self.I > 0.7

    @property
    def is_restrained(self) -> bool:
        """Check if restraint is active (< 0.8)."""
        return self.R < 0.8


@dataclass(frozen=True)
class DHANoOpResult:
    """
    Result when DHA is disabled (no-op).

    Provides consistent interface with DHA disabled flag.
    """
    enabled: bool = False
    reason: str = "DHA disabled via config"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "enabled": self.enabled,
            "reason": self.reason,
            "dha_applied": False,
        }


# =============================================================================
# Delivery Profile
# =============================================================================

@dataclass(frozen=True)
class DeliveryProfile:
    """
    Delivery profile for renderer consumption.

    Contains the computed tone and modulation parameters
    that the renderer can use to adjust presentation.

    Does NOT change semantic content - only delivery style.
    """
    dominant_tone: str      # "sweet" | "jolt" | "metaphor"
    tone_weights: ToneWeights
    intensity: float        # [0, 1]
    restraint: float        # [0, 1]
    modulation_factor: float  # D = T × I × R

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "dominant_tone": self.dominant_tone,
            "tone_weights": self.tone_weights.to_dict(),
            "intensity": self.intensity,
            "restraint": self.restraint,
            "modulation_factor": self.modulation_factor,
        }


# =============================================================================
# Public Exports
# =============================================================================

__all__ = [
    "Tier",
    "ToneWeights",
    "DHAInputs",
    "DHAResult",
    "DHANoOpResult",
    "DeliveryProfile",
]
