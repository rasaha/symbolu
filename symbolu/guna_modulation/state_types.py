"""
State Register Types for SymbolU v2.7
=====================================

Defines the state vector θ_t and associated bounds for the
Deterministic Evaluation & State Evolution Layer.

All types are frozen dataclasses for immutability.

Version: 2.7
Date: 2025-12-22
"""

from dataclasses import dataclass
from typing import Tuple
import math


# =============================================================================
# Constants
# =============================================================================

# Default learning rate (fixed, not configurable per-run)
DEFAULT_ALPHA: float = 0.05

# Policy bias bounds
POLICY_BIAS_MAX: float = 0.1

# Epsilon for numerical stability
EPSILON: float = 1e-9

# Validation epsilon (more relaxed for floating-point comparison)
VALIDATION_EPSILON: float = 1e-6


# =============================================================================
# State Bounds
# =============================================================================

@dataclass(frozen=True)
class StateBounds:
    """
    Hard bounds for all state register components.

    These bounds are fixed and cannot be exceeded by any update.
    """
    # 768-D skip threshold bounds
    tau_768_min: float = 0.1
    tau_768_max: float = 0.9

    # 175B escalation threshold bounds
    tau_175_min: float = 0.3
    tau_175_max: float = 0.95

    # Policy bias bounds (symmetric)
    b_policy_max: float = POLICY_BIAS_MAX

    def clip_tau_768(self, value: float) -> float:
        """Clip τ^768 to valid bounds."""
        return max(self.tau_768_min, min(self.tau_768_max, value))

    def clip_tau_175(self, value: float) -> float:
        """Clip τ^175 to valid bounds."""
        return max(self.tau_175_min, min(self.tau_175_max, value))

    def clip_b_policy(self, value: float) -> float:
        """Clip b^policy to valid bounds."""
        return max(-self.b_policy_max, min(self.b_policy_max, value))


# Default bounds instance
DEFAULT_BOUNDS = StateBounds()


# =============================================================================
# State Register
# =============================================================================

@dataclass(frozen=True)
class StateRegister:
    """
    State vector θ_t for v2.7 deterministic state evolution.

    Components:
        tau_768: Threshold for skipping 768-D embeddings [0.1, 0.9]
        tau_175: Threshold for escalating to 175B model [0.3, 0.95]
        w_tone: Delivery tone weights [sweet, jolt, metaphor], Σ = 1
        w_guna: Guna preference weights [S, R, T], Σ = 1
        b_policy: Bounded bias for tie-breaks [-0.1, 0.1]

    All fields are immutable (frozen dataclass).
    """
    tau_768: float
    tau_175: float
    w_tone: Tuple[float, float, float]
    w_guna: Tuple[float, float, float]
    b_policy: float

    def __post_init__(self):
        """Validate state invariants."""
        # Validate tau_768 range
        if not (0.0 <= self.tau_768 <= 1.0):
            raise ValueError(f"tau_768 must be in [0, 1], got {self.tau_768}")

        # Validate tau_175 range
        if not (0.0 <= self.tau_175 <= 1.0):
            raise ValueError(f"tau_175 must be in [0, 1], got {self.tau_175}")

        # Validate w_tone sums to 1 (relaxed epsilon for floating-point)
        tone_sum = sum(self.w_tone)
        if abs(tone_sum - 1.0) > VALIDATION_EPSILON:
            raise ValueError(f"w_tone must sum to 1, got {tone_sum}")

        # Validate w_guna sums to 1 (relaxed epsilon for floating-point)
        guna_sum = sum(self.w_guna)
        if abs(guna_sum - 1.0) > VALIDATION_EPSILON:
            raise ValueError(f"w_guna must sum to 1, got {guna_sum}")

        # Validate b_policy range
        if abs(self.b_policy) > POLICY_BIAS_MAX + VALIDATION_EPSILON:
            raise ValueError(f"b_policy must be in [-{POLICY_BIAS_MAX}, {POLICY_BIAS_MAX}], got {self.b_policy}")

    @property
    def w_sweet(self) -> float:
        """Tone weight for sweet delivery."""
        return self.w_tone[0]

    @property
    def w_jolt(self) -> float:
        """Tone weight for jolt delivery."""
        return self.w_tone[1]

    @property
    def w_metaphor(self) -> float:
        """Tone weight for metaphor delivery."""
        return self.w_tone[2]

    @property
    def w_S(self) -> float:
        """Guna weight for Sattva."""
        return self.w_guna[0]

    @property
    def w_R(self) -> float:
        """Guna weight for Rajas."""
        return self.w_guna[1]

    @property
    def w_T(self) -> float:
        """Guna weight for Tamas."""
        return self.w_guna[2]


# Default initial state θ_0
DEFAULT_STATE = StateRegister(
    tau_768=0.5,
    tau_175=0.7,
    w_tone=(0.4, 0.3, 0.3),      # [sweet, jolt, metaphor]
    w_guna=(0.33, 0.34, 0.33),   # [S, R, T] - slight R preference
    b_policy=0.0,
)


# =============================================================================
# State Delta (for audit)
# =============================================================================

@dataclass(frozen=True)
class StateDelta:
    """
    Change in state from θ_t to θ_{t+1}.

    Used for audit trail to show exactly what changed.
    """
    delta_tau_768: float
    delta_tau_175: float
    delta_w_tone: Tuple[float, float, float]
    delta_w_guna: Tuple[float, float, float]
    delta_b_policy: float

    @classmethod
    def compute(cls, old: StateRegister, new: StateRegister) -> "StateDelta":
        """Compute delta between two states."""
        return cls(
            delta_tau_768=new.tau_768 - old.tau_768,
            delta_tau_175=new.tau_175 - old.tau_175,
            delta_w_tone=(
                new.w_tone[0] - old.w_tone[0],
                new.w_tone[1] - old.w_tone[1],
                new.w_tone[2] - old.w_tone[2],
            ),
            delta_w_guna=(
                new.w_guna[0] - old.w_guna[0],
                new.w_guna[1] - old.w_guna[1],
                new.w_guna[2] - old.w_guna[2],
            ),
            delta_b_policy=new.b_policy - old.b_policy,
        )

    @property
    def is_zero(self) -> bool:
        """Check if delta is effectively zero (no change)."""
        return (
            abs(self.delta_tau_768) < VALIDATION_EPSILON and
            abs(self.delta_tau_175) < VALIDATION_EPSILON and
            all(abs(d) < VALIDATION_EPSILON for d in self.delta_w_tone) and
            all(abs(d) < VALIDATION_EPSILON for d in self.delta_w_guna) and
            abs(self.delta_b_policy) < VALIDATION_EPSILON
        )


# =============================================================================
# Utility Functions
# =============================================================================

def normalize_weights(weights: Tuple[float, float, float]) -> Tuple[float, float, float]:
    """
    Normalize weights to sum to 1.

    Args:
        weights: Tuple of 3 weights (may not sum to 1)

    Returns:
        Normalized weights that sum to 1
    """
    total = sum(weights) + EPSILON
    return (
        weights[0] / total,
        weights[1] / total,
        weights[2] / total,
    )


def softmax_3(logits: Tuple[float, float, float]) -> Tuple[float, float, float]:
    """
    Compute softmax over 3 logits.

    Deterministic softmax with numerical stability.

    Args:
        logits: Tuple of 3 log-odds values

    Returns:
        Tuple of 3 probabilities summing to 1
    """
    # Shift for numerical stability
    max_logit = max(logits)
    shifted = (logits[0] - max_logit, logits[1] - max_logit, logits[2] - max_logit)

    # Compute exp
    exp_vals = (math.exp(shifted[0]), math.exp(shifted[1]), math.exp(shifted[2]))

    # Normalize
    total = sum(exp_vals)
    return (exp_vals[0] / total, exp_vals[1] / total, exp_vals[2] / total)


def clip(value: float, min_val: float, max_val: float) -> float:
    """Clip value to [min_val, max_val]."""
    return max(min_val, min(max_val, value))
