"""
Observable Signals for SymbolU v2.7 Evaluation Layer
====================================================

Defines the observable signals passed to the evaluation layer
from upstream pipeline stages.

Version: 2.7
Date: 2025-12-22
"""

from dataclasses import dataclass
import math

# Epsilon for numerical stability
EPSILON: float = 1e-9

# Natural log of 3 (for entropy normalization)
LN_3: float = math.log(3)


# =============================================================================
# Observables Container
# =============================================================================

@dataclass(frozen=True)
class Observables:
    """
    Observable signals from the pipeline, passed to the v2.7 evaluation layer.

    All values are pre-computed upstream and passed in.

    Attributes:
        s: Sattva component of Guna distribution [0, 1]
        r: Rajas component of Guna distribution [0, 1]
        t: Tamas component of Guna distribution [0, 1]
        H: Normalized Guna entropy [0, 1]
        delta_sem: Semantic motion magnitude [0, 1]
        C_contr: Contradiction metric [0, 1]
        F_fail: Failure metric [0, 1]

    Invariant: s + r + t = 1 (normalized Guna distribution)
    """
    s: float  # Sattva
    r: float  # Rajas
    t: float  # Tamas
    H: float  # Normalized entropy
    delta_sem: float  # Semantic motion
    C_contr: float  # Contradiction
    F_fail: float  # Failure

    def __post_init__(self):
        """Validate observable invariants."""
        # Validate Guna distribution sums to 1
        guna_sum = self.s + self.r + self.t
        if abs(guna_sum - 1.0) > EPSILON:
            raise ValueError(f"Guna distribution must sum to 1, got {guna_sum}")

        # Validate all values in [0, 1]
        for name, value in [
            ("s", self.s), ("r", self.r), ("t", self.t),
            ("H", self.H), ("delta_sem", self.delta_sem),
            ("C_contr", self.C_contr), ("F_fail", self.F_fail),
        ]:
            if not (0.0 - EPSILON <= value <= 1.0 + EPSILON):
                raise ValueError(f"{name} must be in [0, 1], got {value}")

    @property
    def guna_tuple(self) -> tuple:
        """Return Guna distribution as tuple (s, r, t)."""
        return (self.s, self.r, self.t)

    @classmethod
    def from_guna_vector(
        cls,
        guna_s: float,
        guna_r: float,
        guna_t: float,
        entropy: float,
        semantic_motion: float,
        contradiction: float = 0.0,
        failure: float = 0.0,
    ) -> "Observables":
        """
        Create Observables from individual values.

        This is a convenience factory that validates inputs.
        """
        return cls(
            s=guna_s,
            r=guna_r,
            t=guna_t,
            H=entropy,
            delta_sem=semantic_motion,
            C_contr=contradiction,
            F_fail=failure,
        )


# =============================================================================
# Entropy Computation (for reference / validation)
# =============================================================================

def compute_guna_entropy(s: float, r: float, t: float) -> float:
    """
    Compute normalized Guna entropy H_t.

    Formula:
        H_t = -Σ_{i∈{S,R,T}} g_i × ln(g_i + ε) / ln(3)

    Args:
        s: Sattva component [0, 1]
        r: Rajas component [0, 1]
        t: Tamas component [0, 1]

    Returns:
        Normalized entropy in [0, 1]
    """
    def safe_log(x: float) -> float:
        return math.log(x + EPSILON)

    raw_entropy = -(
        s * safe_log(s) +
        r * safe_log(r) +
        t * safe_log(t)
    )

    # Normalize by max entropy (ln(3) for uniform distribution)
    normalized = raw_entropy / LN_3

    # Clamp to [0, 1]
    return max(0.0, min(1.0, normalized))


# =============================================================================
# Factory for creating Observables from v2.6 pipeline outputs
# =============================================================================

def observables_from_v26_pipeline(
    guna_vector: tuple,  # (S, R, T) from GunaVector
    wired_H: float,      # H from signal wiring
    wired_M: float,      # M from signal wiring (semantic motion)
    contradiction_score: float = 0.0,
    failure_score: float = 0.0,
) -> Observables:
    """
    Create Observables from v2.6 pipeline outputs.

    This bridges v2.6 Guna modulation to v2.7 evaluation.

    Args:
        guna_vector: (S, R, T) tuple from GunaVector
        wired_H: Entropy from signal wiring
        wired_M: Motion from signal wiring (used as semantic motion)
        contradiction_score: Contradiction metric [0, 1]
        failure_score: Failure metric [0, 1]

    Returns:
        Observables instance ready for v2.7 evaluation
    """
    return Observables(
        s=guna_vector[0],
        r=guna_vector[1],
        t=guna_vector[2],
        H=wired_H,
        delta_sem=wired_M,
        C_contr=contradiction_score,
        F_fail=failure_score,
    )
