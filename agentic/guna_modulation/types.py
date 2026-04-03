"""
Guna Entropy Modulation - Type Definitions
===========================================

Symbol-U v2.6 - Deterministic, Zero-Parameter, Non-Learning System

This module defines all type structures for the Guna-aware entropy modulation layer.

All types are frozen (immutable) dataclasses for determinism.
All collections use immutable types (tuple, frozenset).

EXPLICIT NON-CAPABILITIES:
    - No learning
    - No adaptation
    - No state memory
    - No evaluation of "better" or "worse"
    - No psychology
    - No morality
    - No feedback loops
    - No preference formation

This layer is scalar modulation only.
It controls delivery intensity, not meaning.

Version: 2.6.0
Date: 2025-12-22
"""

from dataclasses import dataclass, field
from typing import Tuple, Dict, Any, Optional
from enum import Enum


# =============================================================================
# Constants (Fixed)
# =============================================================================

H_MID: float = 0.5
"""Midpoint entropy constant for Rajas computation."""

EPSILON: float = 1e-9
"""Numerical stability constant to prevent division by zero."""


# =============================================================================
# Tier Enum
# =============================================================================

class ModulationTier(Enum):
    """
    System tier classification for intensity modulation.

    These are fixed system constants with no evaluative meaning.
    """
    ENTERPRISE_TIER_1 = "enterprise_tier_1"
    ENTERPRISE_TIER_2 = "enterprise_tier_2"
    CONSUMER = "consumer"


# =============================================================================
# Guna Vector
# =============================================================================

@dataclass(frozen=True)
class GunaVector:
    """
    Derived Guna distribution vector [S, R, T].

    This vector:
        - Is descriptive only
        - Is not evaluative
        - Carries no moral meaning
        - Is not learned
        - Is not stored
        - Is not fed back

    Constraint: S + R + T = 1 (normalized)

    Attributes:
        sattva: Normalized Sattva component [0.0, 1.0]
        rajas: Normalized Rajas component [0.0, 1.0]
        tamas: Normalized Tamas component [0.0, 1.0]
    """
    sattva: float  # S - derived from structural coherence
    rajas: float   # R - derived from motion/transformation
    tamas: float   # T - derived from entropy/inertia

    def __post_init__(self):
        """Validate and clamp all values to [0.0, 1.0]."""
        for attr in ("sattva", "rajas", "tamas"):
            val = getattr(self, attr)
            if val < 0.0 or val > 1.0:
                object.__setattr__(self, attr, max(0.0, min(1.0, val)))

    def to_tuple(self) -> Tuple[float, float, float]:
        """Return as ordered tuple (S, R, T)."""
        return (self.sattva, self.rajas, self.tamas)

    def to_dict(self) -> Dict[str, float]:
        """Convert to dictionary."""
        return {
            "sattva": self.sattva,
            "rajas": self.rajas,
            "tamas": self.tamas,
        }

    @property
    def sum(self) -> float:
        """Return sum of components (should be ~1.0 after normalization)."""
        return self.sattva + self.rajas + self.tamas


# =============================================================================
# Pipeline Inputs
# =============================================================================

@dataclass(frozen=True)
class PipelineInputs:
    """
    Upstream pipeline inputs for Guna derivation.

    All inputs are deterministic and already computed upstream.
    This structure captures them for the modulation layer.

    Attributes:
        C_s: Structural coherence [0.0, 1.0]
        M: Motion/transformation magnitude [0.0, 1.0]
        H: Entropy [0.0, 1.0]
    """
    C_s: float  # Structural coherence
    M: float    # Motion / transformation magnitude
    H: float    # Entropy

    def __post_init__(self):
        """Validate and clamp all values to [0.0, 1.0]."""
        for attr in ("C_s", "M", "H"):
            val = getattr(self, attr)
            if val < 0.0 or val > 1.0:
                object.__setattr__(self, attr, max(0.0, min(1.0, val)))

    def to_dict(self) -> Dict[str, float]:
        """Convert to dictionary."""
        return {
            "C_s": self.C_s,
            "M": self.M,
            "H": self.H,
        }


# =============================================================================
# Guna Weights Configuration
# =============================================================================

@dataclass(frozen=True)
class GunaWeights:
    """
    Operator-configured Guna weight constants.

    These are configuration constants, not learned values:
        - w_S, w_R, w_T are operator-supplied constants
        - No defaults imply good/bad
        - No inference is allowed

    Attributes:
        w_S: Sattva weight (operator-configured)
        w_R: Rajas weight (operator-configured)
        w_T: Tamas weight (operator-configured)
    """
    w_S: float  # Sattva weight
    w_R: float  # Rajas weight
    w_T: float  # Tamas weight

    def __post_init__(self):
        """Validate weights are positive."""
        for attr in ("w_S", "w_R", "w_T"):
            val = getattr(self, attr)
            if val < 0.0:
                raise ValueError(f"{attr} must be non-negative, got {val}")

    def to_dict(self) -> Dict[str, float]:
        """Convert to dictionary."""
        return {
            "w_S": self.w_S,
            "w_R": self.w_R,
            "w_T": self.w_T,
        }


# =============================================================================
# Policy Configuration
# =============================================================================

@dataclass(frozen=True)
class PolicyConfig:
    """
    Operator-supplied policy constants.

    These are operator-configured constants with no interpretation:
        - No judgment is allowed
        - No inference is applied

    Attributes:
        r_risk: Risk factor constant [0.0, 1.0]
        r_escalation: Escalation factor constant [0.0, 1.0]
    """
    r_risk: float = 0.0
    r_escalation: float = 0.0

    def __post_init__(self):
        """Validate policy constants are in valid range."""
        for attr in ("r_risk", "r_escalation"):
            val = getattr(self, attr)
            if val < 0.0 or val > 1.0:
                object.__setattr__(self, attr, max(0.0, min(1.0, val)))

    def to_dict(self) -> Dict[str, float]:
        """Convert to dictionary."""
        return {
            "r_risk": self.r_risk,
            "r_escalation": self.r_escalation,
        }


# =============================================================================
# Audit Trace Entry
# =============================================================================

@dataclass(frozen=True)
class ModulationTraceEntry:
    """
    Single entry in the modulation trace for explainability and audit.

    Every computation step must be traceable.

    Attributes:
        step_name: Name of the computation step
        inputs: Input values for this step
        output: Output value from this step
        formula: Formula description used
    """
    step_name: str
    inputs: Tuple[Tuple[str, float], ...]
    output: float
    formula: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "step_name": self.step_name,
            "inputs": dict(self.inputs),
            "output": self.output,
            "formula": self.formula,
        }


# =============================================================================
# Modulation Result
# =============================================================================

@dataclass(frozen=True)
class ModulationResult:
    """
    Complete result from entropy modulation computation.

    Contains:
        - The final entropy modulation factor E
        - The output intensity (BASE_intensity * E)
        - Complete audit trail

    Determinism Guarantee:
        Same inputs always produce same outputs.

    Disable Proof:
        If w_S = w_R = w_T = 1 and P = T = 1, then E = 1
        and OUTPUT_intensity = BASE_intensity (unchanged).

    Attributes:
        guna_vector: Derived Guna vector [S, R, T]
        G: Guna coefficient (linear scalar projection)
        P: Policy scalar
        T: Tier scalar
        E: Entropy modulation factor (G * P * T)
        base_intensity: Input base intensity
        output_intensity: Final output intensity (base * E)
        trace: Complete audit trail
    """
    guna_vector: GunaVector
    G: float  # Guna coefficient
    P: float  # Policy scalar
    T: float  # Tier scalar (note: different from Tamas in guna_vector)
    E: float  # Entropy modulation factor
    base_intensity: float
    output_intensity: float
    trace: Tuple[ModulationTraceEntry, ...]

    def __post_init__(self):
        """Validate result values."""
        # E should be non-negative
        if self.E < 0.0:
            object.__setattr__(self, "E", 0.0)
        # output_intensity should be non-negative
        if self.output_intensity < 0.0:
            object.__setattr__(self, "output_intensity", 0.0)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "guna_vector": self.guna_vector.to_dict(),
            "G": self.G,
            "P": self.P,
            "T": self.T,
            "E": self.E,
            "base_intensity": self.base_intensity,
            "output_intensity": self.output_intensity,
            "trace": [entry.to_dict() for entry in self.trace],
        }

    @property
    def is_disabled(self) -> bool:
        """Check if modulation is effectively disabled (E ≈ 1.0)."""
        # Use 1e-8 tolerance due to epsilon in normalization formula
        return abs(self.E - 1.0) < 1e-8

    @property
    def is_unchanged(self) -> bool:
        """Check if output equals input (modulation had no effect)."""
        # Use 1e-7 tolerance for accumulated floating point error
        return abs(self.output_intensity - self.base_intensity) < 1e-7


# =============================================================================
# Tier Configuration
# =============================================================================

@dataclass(frozen=True)
class TierModulationConfig:
    """
    Tier-specific modulation configuration.

    Fixed system constants per tier.

    Attributes:
        tier: The tier identifier
        tier_scalar: Fixed tier intensity scalar
        guna_weights: Default Guna weights for this tier
        policy_config: Default policy config for this tier
    """
    tier: ModulationTier
    tier_scalar: float
    guna_weights: GunaWeights
    policy_config: PolicyConfig

    def __post_init__(self):
        """Validate tier scalar is positive."""
        if self.tier_scalar <= 0.0:
            raise ValueError(
                f"tier_scalar must be positive, got {self.tier_scalar}"
            )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "tier": self.tier.value,
            "tier_scalar": self.tier_scalar,
            "guna_weights": self.guna_weights.to_dict(),
            "policy_config": self.policy_config.to_dict(),
        }
