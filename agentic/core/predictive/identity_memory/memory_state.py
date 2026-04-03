"""
P36 - Identity Resonance Memory State Schema Definitions

P36 is an observation-only memory phase that persists identity resonance patterns
over time, independent of momentary fluctuations. It is a memory of identity
behavior, NOT a decision system.

P36 answers: "What identity resonance patterns persist over time, independent
of momentary fluctuations?"

P36 does NOT:
- Predict futures (Phase 35 does that)
- Influence regime, discourse, semantics, or tone
- Gate insights or actions
- Modify persona behavior
- Influence P6-P9 (regime, discourse, semantics, lexical)
- Influence DHA, Persona Engine, Renderer
- Influence Phase 32 insight gating
- Influence any action eligibility

P36 MAY:
- Remember stability and drift patterns
- Smooth short-term noise
- Preserve historical identity context
- Be read-only memory
- Be append-only

CRITICAL CONSTRAINTS:
    - Deterministic: Same inputs -> same outputs (no LLM, no randomness)
    - Read-only: Does not modify system behavior
    - Append-only: Never overwrites or deletes history
    - Non-invasive: Zero impact on routing, TTOR, MLCR, Fusion, DHA, Renderer
    - Observation-only: Never used for gating, blocking, or behavior modification
    - No acoustic dependency: P22-P24 observers are FORBIDDEN as direct inputs

INVARIANTS:
    - INV-P36-1: Memory never alters present cognition
    - INV-P36-2: Memory is append-only
    - INV-P36-3: No authority escalation
    - INV-P36-4: Deterministic math only
    - INV-P36-5: Acoustic signals forbidden
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional


# =============================================================================
# VERSION
# =============================================================================

P36_VERSION = "1.0.0"


# =============================================================================
# ENUMS
# =============================================================================


class IdentityStabilityBand(str, Enum):
    """
    Classification of identity stability based on persistence and volatility.

    STABLE: persistence >= 0.75 AND volatility < 0.20
    SOFT: otherwise (default)
    FRAGILE: persistence < 0.40 OR volatility >= 0.45
    """
    STABLE = "stable"
    SOFT = "soft"
    FRAGILE = "fragile"


# =============================================================================
# FORMULA WEIGHTS - LOCKED
# =============================================================================

# Identity Resonance Index weights (must sum to 1.0)
W_UCF_SCORE = 0.40
W_IDENTITY_HARMONICS = 0.30
W_SCHEMA_STABILITY = 0.20
W_INVERSE_DRIFT = 0.10  # (1 - predicted_drift_score)

# Validate weights sum to 1.0
_WEIGHT_SUM = W_UCF_SCORE + W_IDENTITY_HARMONICS + W_SCHEMA_STABILITY + W_INVERSE_DRIFT
assert abs(_WEIGHT_SUM - 1.0) < 1e-9, f"Weights must sum to 1.0, got {_WEIGHT_SUM}"

# Stability band thresholds
PERSISTENCE_STABLE_THRESHOLD = 0.75  # >= 0.75 for stable
PERSISTENCE_FRAGILE_THRESHOLD = 0.40  # < 0.40 for fragile
VOLATILITY_STABLE_THRESHOLD = 0.20  # < 0.20 for stable
VOLATILITY_FRAGILE_THRESHOLD = 0.45  # >= 0.45 for fragile

# Memory configuration
DEFAULT_MEMORY_DEPTH = 5  # Default N snapshots for variance/volatility
MAX_MEMORY_DEPTH = 7  # Maximum allowed memory depth


# =============================================================================
# DATACLASSES
# =============================================================================


@dataclass(frozen=True)
class IdentityResonanceMemoryState:
    """
    Immutable state of identity resonance memory computation.

    This is the primary output of Phase 36, containing:
    - identity_resonance_index: Composite resonance measure [0.0, 1.0]
    - identity_stability_band: Stability classification (stable/soft/fragile)
    - persistence_score: How consistent identity resonance has been [0.0, 1.0]
    - volatility_index: Average change magnitude across transitions [0.0, 1.0]
    - memory_depth: Number of snapshots used for computation
    - memory_timestamp: When this snapshot was created

    Plus the input signals used for computation (for observability).

    INVARIANTS:
        - identity_resonance_index in [0.0, 1.0]
        - persistence_score in [0.0, 1.0]
        - volatility_index in [0.0, 1.0]
        - identity_stability_band in {"stable", "soft", "fragile"}
        - memory_depth <= MAX_MEMORY_DEPTH
        - observer_only is always True
    """

    # Core outputs
    identity_resonance_index: float
    identity_stability_band: str
    persistence_score: float
    volatility_index: float
    memory_depth: int
    memory_timestamp: datetime

    # Input signals (for observability)
    ucf_score: Optional[float] = None
    identity_harmonics_score: Optional[float] = None
    schema_stability: Optional[float] = None
    predicted_drift_score: Optional[float] = None
    drift_risk_band: Optional[str] = None

    # Historical resonance values used for variance calculation
    historical_resonance_values: tuple = field(default_factory=tuple)

    # Debug info
    debug: Dict[str, Any] = field(default_factory=dict)

    # Authority markers - MUST be True
    observer_only: bool = True
    architectural_phase: str = "P36"
    version: str = P36_VERSION

    def __post_init__(self) -> None:
        """Validate invariants."""
        # INV-P36-1/INV-P36-3: observer_only must always be True
        if not self.observer_only:
            raise ValueError(
                "IdentityResonanceMemoryState.observer_only must be True. "
                "P36 is observation-only and non-authoritative."
            )

        # Validate identity_resonance_index in [0.0, 1.0]
        if not isinstance(self.identity_resonance_index, (int, float)):
            raise ValueError(
                f"identity_resonance_index must be numeric, "
                f"got {type(self.identity_resonance_index).__name__}"
            )
        if not (0.0 <= self.identity_resonance_index <= 1.0):
            object.__setattr__(
                self, 'identity_resonance_index',
                max(0.0, min(1.0, self.identity_resonance_index))
            )

        # Validate persistence_score in [0.0, 1.0]
        if not isinstance(self.persistence_score, (int, float)):
            raise ValueError(
                f"persistence_score must be numeric, "
                f"got {type(self.persistence_score).__name__}"
            )
        if not (0.0 <= self.persistence_score <= 1.0):
            object.__setattr__(
                self, 'persistence_score',
                max(0.0, min(1.0, self.persistence_score))
            )

        # Validate volatility_index in [0.0, 1.0]
        if not isinstance(self.volatility_index, (int, float)):
            raise ValueError(
                f"volatility_index must be numeric, "
                f"got {type(self.volatility_index).__name__}"
            )
        if not (0.0 <= self.volatility_index <= 1.0):
            object.__setattr__(
                self, 'volatility_index',
                max(0.0, min(1.0, self.volatility_index))
            )

        # Validate identity_stability_band
        if self.identity_stability_band not in ("stable", "soft", "fragile"):
            raise ValueError(
                f"identity_stability_band must be 'stable', 'soft', or 'fragile', "
                f"got '{self.identity_stability_band}'"
            )

        # Validate memory_depth
        if not isinstance(self.memory_depth, int):
            raise ValueError(
                f"memory_depth must be int, "
                f"got {type(self.memory_depth).__name__}"
            )
        if self.memory_depth < 0 or self.memory_depth > MAX_MEMORY_DEPTH:
            raise ValueError(
                f"memory_depth must be in [0, {MAX_MEMORY_DEPTH}], "
                f"got {self.memory_depth}"
            )

        # Validate memory_timestamp
        if not isinstance(self.memory_timestamp, datetime):
            raise ValueError(
                f"memory_timestamp must be datetime, "
                f"got {type(self.memory_timestamp).__name__}"
            )

    # -------------------------------------------------------------------------
    # Convenience methods
    # -------------------------------------------------------------------------

    def is_stable(self) -> bool:
        """Return True if identity stability band is stable."""
        return self.identity_stability_band == "stable"

    def is_soft(self) -> bool:
        """Return True if identity stability band is soft."""
        return self.identity_stability_band == "soft"

    def is_fragile(self) -> bool:
        """Return True if identity stability band is fragile."""
        return self.identity_stability_band == "fragile"

    def has_sufficient_history(self) -> bool:
        """Return True if memory depth is sufficient for meaningful analysis."""
        return self.memory_depth >= 2

    def to_dict(self) -> Dict[str, Any]:
        """Serialize state to dictionary for API/JSON output."""
        return {
            "identity_resonance_index": self.identity_resonance_index,
            "identity_stability_band": self.identity_stability_band,
            "persistence_score": self.persistence_score,
            "volatility_index": self.volatility_index,
            "memory_depth": self.memory_depth,
            "memory_timestamp": self.memory_timestamp.isoformat(),
            "inputs": {
                "ucf_score": self.ucf_score,
                "identity_harmonics_score": self.identity_harmonics_score,
                "schema_stability": self.schema_stability,
                "predicted_drift_score": self.predicted_drift_score,
                "drift_risk_band": self.drift_risk_band,
            },
            "historical_resonance_values": list(self.historical_resonance_values),
            "debug": self.debug,
            "observer_only": self.observer_only,
            "architectural_phase": self.architectural_phase,
            "version": self.version,
        }


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def create_state(
    identity_resonance_index: float,
    identity_stability_band: str,
    persistence_score: float,
    volatility_index: float,
    memory_depth: int,
    memory_timestamp: Optional[datetime] = None,
    ucf_score: Optional[float] = None,
    identity_harmonics_score: Optional[float] = None,
    schema_stability: Optional[float] = None,
    predicted_drift_score: Optional[float] = None,
    drift_risk_band: Optional[str] = None,
    historical_resonance_values: Optional[tuple] = None,
    debug: Optional[Dict[str, Any]] = None,
) -> IdentityResonanceMemoryState:
    """
    Factory function to create an IdentityResonanceMemoryState.

    Args:
        identity_resonance_index: Composite resonance measure [0.0, 1.0]
        identity_stability_band: Stability band ("stable", "soft", "fragile")
        persistence_score: Consistency measure [0.0, 1.0]
        volatility_index: Change magnitude [0.0, 1.0]
        memory_depth: Number of snapshots used
        memory_timestamp: When this snapshot was created (defaults to now)
        ucf_score: P26 UCF score input
        identity_harmonics_score: P34 identity harmonics input
        schema_stability: P33 schema stability input
        predicted_drift_score: P35 predicted drift input
        drift_risk_band: P35 drift risk band input
        historical_resonance_values: Historical resonance values tuple
        debug: Optional debug dictionary

    Returns:
        IdentityResonanceMemoryState instance
    """
    return IdentityResonanceMemoryState(
        identity_resonance_index=identity_resonance_index,
        identity_stability_band=identity_stability_band,
        persistence_score=persistence_score,
        volatility_index=volatility_index,
        memory_depth=memory_depth,
        memory_timestamp=memory_timestamp or datetime.utcnow(),
        ucf_score=ucf_score,
        identity_harmonics_score=identity_harmonics_score,
        schema_stability=schema_stability,
        predicted_drift_score=predicted_drift_score,
        drift_risk_band=drift_risk_band,
        historical_resonance_values=historical_resonance_values or tuple(),
        debug=debug or {},
        observer_only=True,  # Always True
    )


def stability_band_from_scores(persistence: float, volatility: float) -> str:
    """
    Determine stability band from persistence and volatility scores.

    Rules:
    - "stable" -> persistence >= 0.75 AND volatility < 0.20
    - "fragile" -> persistence < 0.40 OR volatility >= 0.45
    - "soft" -> otherwise

    Args:
        persistence: Persistence score [0.0, 1.0]
        volatility: Volatility index [0.0, 1.0]

    Returns:
        Stability band string: "stable", "soft", or "fragile"
    """
    # Check fragile conditions first (OR logic)
    if persistence < PERSISTENCE_FRAGILE_THRESHOLD or volatility >= VOLATILITY_FRAGILE_THRESHOLD:
        return "fragile"

    # Check stable conditions (AND logic)
    if persistence >= PERSISTENCE_STABLE_THRESHOLD and volatility < VOLATILITY_STABLE_THRESHOLD:
        return "stable"

    # Default to soft
    return "soft"


def create_empty_state() -> IdentityResonanceMemoryState:
    """
    Create an empty state with default values.

    Used when P36 cannot compute meaningful metrics (e.g., missing inputs).

    Returns:
        A minimal IdentityResonanceMemoryState with neutral defaults
    """
    return create_state(
        identity_resonance_index=0.5,  # Neutral default
        identity_stability_band="soft",
        persistence_score=1.0,  # Perfect persistence with no history
        volatility_index=0.0,  # Zero volatility with no history
        memory_depth=0,
        debug={"reason": "empty_state_insufficient_inputs"},
    )


def create_initial_state(
    ucf_score: Optional[float] = None,
    identity_harmonics_score: Optional[float] = None,
    schema_stability: Optional[float] = None,
    predicted_drift_score: Optional[float] = None,
    drift_risk_band: Optional[str] = None,
) -> IdentityResonanceMemoryState:
    """
    Create an initial state when no historical data exists.

    For initial state (< 2 snapshots):
    - volatility = 0.0
    - persistence = 1.0

    Args:
        ucf_score: P26 UCF score input
        identity_harmonics_score: P34 identity harmonics input
        schema_stability: P33 schema stability input
        predicted_drift_score: P35 predicted drift input
        drift_risk_band: P35 drift risk band input

    Returns:
        IdentityResonanceMemoryState with initial values
    """
    from agentic.core.predictive.identity_memory.memory_formula import (
        compute_identity_resonance_index,
    )

    # Compute resonance index from available inputs
    resonance_index = compute_identity_resonance_index(
        ucf_score=ucf_score,
        identity_harmonics_score=identity_harmonics_score,
        schema_stability=schema_stability,
        predicted_drift_score=predicted_drift_score,
    )

    # Initial state: no history so persistence = 1.0, volatility = 0.0
    persistence = 1.0
    volatility = 0.0

    # Determine stability band
    stability_band = stability_band_from_scores(persistence, volatility)

    return create_state(
        identity_resonance_index=resonance_index,
        identity_stability_band=stability_band,
        persistence_score=persistence,
        volatility_index=volatility,
        memory_depth=1,
        ucf_score=ucf_score,
        identity_harmonics_score=identity_harmonics_score,
        schema_stability=schema_stability,
        predicted_drift_score=predicted_drift_score,
        drift_risk_band=drift_risk_band,
        historical_resonance_values=(resonance_index,),
        debug={"reason": "initial_state"},
    )


# Public exports
__all__ = [
    # Version
    "P36_VERSION",
    # Enums
    "IdentityStabilityBand",
    # Constants
    "W_UCF_SCORE",
    "W_IDENTITY_HARMONICS",
    "W_SCHEMA_STABILITY",
    "W_INVERSE_DRIFT",
    "PERSISTENCE_STABLE_THRESHOLD",
    "PERSISTENCE_FRAGILE_THRESHOLD",
    "VOLATILITY_STABLE_THRESHOLD",
    "VOLATILITY_FRAGILE_THRESHOLD",
    "DEFAULT_MEMORY_DEPTH",
    "MAX_MEMORY_DEPTH",
    # Dataclasses
    "IdentityResonanceMemoryState",
    # Helpers
    "create_state",
    "stability_band_from_scores",
    "create_empty_state",
    "create_initial_state",
]
