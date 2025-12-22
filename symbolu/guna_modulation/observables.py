"""
Observable Signals for SymbolU v2.7 Evaluation Layer
====================================================

Defines the observable signals passed to the evaluation layer
from upstream pipeline stages.

Version: 2.7.3
Date: 2025-12-22

Motion (M) Formalization:
- Explicit semantic, structural, and temporal motion types
- Deterministic computation from pipeline outputs
- No reasoning, inference, or learning
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple, List
import math

# Epsilon for numerical stability
EPSILON: float = 1e-9

# Natural log of 3 (for entropy normalization)
LN_3: float = math.log(3)


# =============================================================================
# Motion Type Enum
# =============================================================================

class MotionType(Enum):
    """
    Type of motion being measured.

    SEMANTIC: Distance in semantic/embedding space
        M = (1/N) × Σ ||S_i - S_query||
        Measures degree of transformation, not intention.

    STRUCTURAL: Domain/ontology transitions
        M = domain_jumps / max_allowed_jumps
        Measures category boundaries crossed.

    TEMPORAL: Aspect change over time (requires LAM)
        M = ||Aspect_t - Aspect_{t-1}||
        Measures state evolution magnitude.
    """
    SEMANTIC = "semantic"
    STRUCTURAL = "structural"
    TEMPORAL = "temporal"


# =============================================================================
# Motion Computation Utilities
# =============================================================================

def compute_semantic_motion(
    embeddings: List[Tuple[float, ...]],
    query_embedding: Tuple[float, ...],
) -> float:
    """
    Compute semantic motion as average distance from query.

    Formula: M = (1/N) × Σ ||S_i - S_query||

    Args:
        embeddings: List of candidate embeddings
        query_embedding: Query/reference embedding

    Returns:
        Normalized motion in [0, 1]
    """
    if not embeddings:
        return 0.0

    def euclidean_distance(a: Tuple[float, ...], b: Tuple[float, ...]) -> float:
        return math.sqrt(sum((ai - bi) ** 2 for ai, bi in zip(a, b)))

    total_distance = sum(
        euclidean_distance(emb, query_embedding)
        for emb in embeddings
    )
    avg_distance = total_distance / len(embeddings)

    # Normalize to [0, 1] - assuming max distance is sqrt(dim)
    # For unit vectors, max distance is sqrt(2)
    max_distance = math.sqrt(2) if embeddings else 1.0
    return min(1.0, avg_distance / max_distance)


def compute_structural_motion(
    domain_jumps: int,
    max_allowed_jumps: int = 5,
) -> float:
    """
    Compute structural motion as ratio of domain transitions.

    Formula: M = domain_jumps / max_allowed_jumps

    Args:
        domain_jumps: Number of ontology/domain boundaries crossed
        max_allowed_jumps: Maximum expected jumps (normalization factor)

    Returns:
        Normalized motion in [0, 1]
    """
    if max_allowed_jumps <= 0:
        return 0.0
    return min(1.0, domain_jumps / max_allowed_jumps)


def compute_temporal_motion(
    aspect_current: Tuple[float, ...],
    aspect_previous: Tuple[float, ...],
) -> float:
    """
    Compute temporal motion as aspect change over time.

    Formula: M = ||Aspect_t - Aspect_{t-1}||

    Args:
        aspect_current: Current aspect vector
        aspect_previous: Previous aspect vector

    Returns:
        Normalized motion in [0, 1]
    """
    if len(aspect_current) != len(aspect_previous):
        raise ValueError("Aspect vectors must have same dimension")

    distance = math.sqrt(sum(
        (a - b) ** 2
        for a, b in zip(aspect_current, aspect_previous)
    ))

    # Normalize - for unit vectors, max change is sqrt(2)
    return min(1.0, distance / math.sqrt(2))


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
        delta_sem: Semantic motion magnitude [0, 1] (primary motion signal)
        C_contr: Contradiction metric [0, 1]
        F_fail: Failure metric [0, 1]
        motion_type: Type of motion being measured (default: SEMANTIC)

    Invariant: s + r + t = 1 (normalized Guna distribution)

    Motion (M) Formalization:
        The delta_sem field is the explicit Motion signal M.
        - SEMANTIC: M = (1/N) × Σ ||S_i - S_query||
        - STRUCTURAL: M = domain_jumps / max_allowed_jumps
        - TEMPORAL: M = ||Aspect_t - Aspect_{t-1}||

        All three are:
        - Deterministic
        - Measurable
        - Non-psychological
    """
    s: float  # Sattva
    r: float  # Rajas
    t: float  # Tamas
    H: float  # Normalized entropy
    delta_sem: float  # Semantic motion (M)
    C_contr: float  # Contradiction
    F_fail: float  # Failure
    motion_type: MotionType = MotionType.SEMANTIC  # Type of motion measured

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

    @property
    def M(self) -> float:
        """
        Motion signal (explicit accessor).

        Alias for delta_sem, providing canonical access to motion.
        """
        return self.delta_sem

    @property
    def motion(self) -> float:
        """Motion signal (explicit accessor)."""
        return self.delta_sem

    @property
    def is_high_motion(self) -> bool:
        """Check if motion exceeds threshold (>0.5)."""
        return self.delta_sem > 0.5

    @property
    def is_low_motion(self) -> bool:
        """Check if motion is below threshold (<0.2)."""
        return self.delta_sem < 0.2

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
        motion_type: MotionType = MotionType.SEMANTIC,
    ) -> "Observables":
        """
        Create Observables from individual values.

        This is a convenience factory that validates inputs.

        Args:
            guna_s: Sattva component [0, 1]
            guna_r: Rajas component [0, 1]
            guna_t: Tamas component [0, 1]
            entropy: Normalized entropy H [0, 1]
            semantic_motion: Motion signal M [0, 1]
            contradiction: Contradiction metric [0, 1]
            failure: Failure metric [0, 1]
            motion_type: Type of motion (SEMANTIC, STRUCTURAL, or TEMPORAL)

        Returns:
            Observables instance
        """
        return cls(
            s=guna_s,
            r=guna_r,
            t=guna_t,
            H=entropy,
            delta_sem=semantic_motion,
            C_contr=contradiction,
            F_fail=failure,
            motion_type=motion_type,
        )

    @classmethod
    def with_semantic_motion(
        cls,
        guna: Tuple[float, float, float],
        entropy: float,
        embeddings: List[Tuple[float, ...]],
        query_embedding: Tuple[float, ...],
        contradiction: float = 0.0,
        failure: float = 0.0,
    ) -> "Observables":
        """
        Create Observables with computed semantic motion.

        Args:
            guna: (S, R, T) tuple
            entropy: Normalized entropy H
            embeddings: Candidate embeddings
            query_embedding: Query embedding
            contradiction: Contradiction metric
            failure: Failure metric

        Returns:
            Observables with semantic motion computed
        """
        motion = compute_semantic_motion(embeddings, query_embedding)
        return cls(
            s=guna[0],
            r=guna[1],
            t=guna[2],
            H=entropy,
            delta_sem=motion,
            C_contr=contradiction,
            F_fail=failure,
            motion_type=MotionType.SEMANTIC,
        )

    @classmethod
    def with_structural_motion(
        cls,
        guna: Tuple[float, float, float],
        entropy: float,
        domain_jumps: int,
        max_jumps: int = 5,
        contradiction: float = 0.0,
        failure: float = 0.0,
    ) -> "Observables":
        """
        Create Observables with computed structural motion.

        Args:
            guna: (S, R, T) tuple
            entropy: Normalized entropy H
            domain_jumps: Number of domain boundaries crossed
            max_jumps: Maximum expected jumps
            contradiction: Contradiction metric
            failure: Failure metric

        Returns:
            Observables with structural motion computed
        """
        motion = compute_structural_motion(domain_jumps, max_jumps)
        return cls(
            s=guna[0],
            r=guna[1],
            t=guna[2],
            H=entropy,
            delta_sem=motion,
            C_contr=contradiction,
            F_fail=failure,
            motion_type=MotionType.STRUCTURAL,
        )

    @classmethod
    def with_temporal_motion(
        cls,
        guna: Tuple[float, float, float],
        entropy: float,
        aspect_current: Tuple[float, ...],
        aspect_previous: Tuple[float, ...],
        contradiction: float = 0.0,
        failure: float = 0.0,
    ) -> "Observables":
        """
        Create Observables with computed temporal motion.

        Args:
            guna: (S, R, T) tuple
            entropy: Normalized entropy H
            aspect_current: Current aspect vector
            aspect_previous: Previous aspect vector
            contradiction: Contradiction metric
            failure: Failure metric

        Returns:
            Observables with temporal motion computed
        """
        motion = compute_temporal_motion(aspect_current, aspect_previous)
        return cls(
            s=guna[0],
            r=guna[1],
            t=guna[2],
            H=entropy,
            delta_sem=motion,
            C_contr=contradiction,
            F_fail=failure,
            motion_type=MotionType.TEMPORAL,
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
