"""
P37 - Adaptive Continuity Engine Model Definitions

P37 is an observation-only phase that computes whether the user's identity
trajectory is continuous, oscillating, or fragmenting over time, using
historical resonance memory + predictive drift.

P37 answers: "Is the identity evolution smooth, strained, or breaking?"

P37 does NOT:
- Predict behavior
- Infer intent
- Trigger interventions
- Modify persona delivery
- Influence regime or discourse
- Change semantics or lexical selection (P8-P9)
- Influence DHA, Persona Engine, Renderer
- Influence insight gating (P32)
- Gate any downstream behavior

P37 MAY:
- Compute continuity scores
- Classify continuity mode
- Detect oscillation
- Emit explanatory tags

CRITICAL CONSTRAINTS:
    - Deterministic: Same inputs -> same outputs (no LLM, no randomness)
    - Read-only: Does not modify system behavior
    - Non-invasive: Zero impact on routing, TTOR, MLCR, Fusion, DHA, Renderer
    - Observation-only: Never used for gating, blocking, or behavior modification
    - No acoustic dependency: P22-P24 observers are FORBIDDEN as direct inputs

INVARIANTS:
    - INV-P37-1: Deterministic (same input -> same output)
    - INV-P37-2: No imports from governance, persona, DHA, renderer
    - INV-P37-3: Output never influences routing or gating
    - INV-P37-4: continuity_score is monotonic w.r.t inputs
    - INV-P37-5: No observer feeds upstream
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, FrozenSet, Tuple


# =============================================================================
# VERSION
# =============================================================================

P37_VERSION = "1.0.0"


# =============================================================================
# FORMULA WEIGHTS - LOCKED
# =============================================================================

# Continuity score weights (must sum to 1.0)
W_PERSISTENCE = 0.40
W_INVERSE_VOLATILITY = 0.30  # (1 - volatility_index)
W_INVERSE_DRIFT = 0.30  # (1 - predicted_drift_score)

# Validate weights sum to 1.0
_WEIGHT_SUM = W_PERSISTENCE + W_INVERSE_VOLATILITY + W_INVERSE_DRIFT
assert abs(_WEIGHT_SUM - 1.0) < 1e-9, f"Weights must sum to 1.0, got {_WEIGHT_SUM}"


# =============================================================================
# MODE CLASSIFICATION THRESHOLDS - LOCKED
# =============================================================================

MODE_STABLE_THRESHOLD = 0.75  # continuity_score >= 0.75 -> "stable"
MODE_STRAINED_THRESHOLD = 0.45  # continuity_score >= 0.45 -> "strained"
# Below MODE_STRAINED_THRESHOLD -> "fragmenting"


# =============================================================================
# OSCILLATION DETECTION THRESHOLDS - LOCKED
# =============================================================================

OSCILLATION_VOLATILITY_THRESHOLD = 0.6  # volatility_index > 0.6
OSCILLATION_MIN_REVERSALS = 2  # >= 2 direction reversals
OSCILLATION_WINDOW_SIZE = 5  # Max snapshots for oscillation detection


# =============================================================================
# CONTRIBUTING FACTOR THRESHOLDS - LOCKED
# =============================================================================

HIGH_DRIFT_THRESHOLD = 0.6  # predicted_drift_score > 0.6
LOW_PERSISTENCE_THRESHOLD = 0.4  # persistence_score < 0.4
HIGH_VOLATILITY_THRESHOLD = 0.6  # volatility_index > 0.6


# =============================================================================
# ALLOWED CONTRIBUTING FACTORS
# =============================================================================

ALLOWED_CONTRIBUTING_FACTORS: FrozenSet[str] = frozenset({
    "high_drift",
    "low_persistence",
    "high_volatility",
    "oscillation",
})


# =============================================================================
# DATACLASSES
# =============================================================================


@dataclass(frozen=True)
class AdaptiveContinuityReport:
    """
    Immutable report of adaptive continuity computation.

    This is the primary output of Phase 37, containing:
    - continuity_score: Overall continuity measure [0.0, 1.0]
    - continuity_mode: Mode classification ("stable" | "strained" | "fragmenting")
    - continuity_pressure: Inverse of continuity_score [0.0, 1.0]
    - oscillation_detected: Whether oscillation pattern detected
    - contributing_factors: Tuple of explanatory tags

    Plus input signals used for computation (for observability).

    INVARIANTS:
        - continuity_score in [0.0, 1.0]
        - continuity_pressure in [0.0, 1.0]
        - continuity_mode in {"stable", "strained", "fragmenting"}
        - observer_only is always True
    """

    # Core outputs
    continuity_score: float
    continuity_mode: str
    continuity_pressure: float
    oscillation_detected: bool
    contributing_factors: Tuple[str, ...]

    # Input signals (for observability)
    p35_predicted_drift_score: float = 0.0
    p35_drift_risk_band: str = "low"
    p36_identity_resonance_index: float = 0.0
    p36_persistence_score: float = 1.0
    p36_volatility_index: float = 0.0

    # Historical data used for oscillation detection
    historical_resonance_count: int = 0

    # Debug info
    debug: Dict[str, Any] = field(default_factory=dict)

    # Authority markers - MUST be True
    observer_only: bool = True
    architectural_phase: str = "P37"
    version: str = P37_VERSION

    def __post_init__(self) -> None:
        """Validate invariants."""
        # INV-P37-3: observer_only must always be True
        if not self.observer_only:
            raise ValueError(
                "AdaptiveContinuityReport.observer_only must be True. "
                "P37 is observation-only and non-authoritative."
            )

        # Validate continuity_score in [0.0, 1.0]
        if not isinstance(self.continuity_score, (int, float)):
            raise ValueError(
                f"continuity_score must be numeric, "
                f"got {type(self.continuity_score).__name__}"
            )
        if not (0.0 <= self.continuity_score <= 1.0):
            object.__setattr__(
                self, 'continuity_score',
                max(0.0, min(1.0, self.continuity_score))
            )

        # Validate continuity_pressure in [0.0, 1.0]
        if not isinstance(self.continuity_pressure, (int, float)):
            raise ValueError(
                f"continuity_pressure must be numeric, "
                f"got {type(self.continuity_pressure).__name__}"
            )
        if not (0.0 <= self.continuity_pressure <= 1.0):
            object.__setattr__(
                self, 'continuity_pressure',
                max(0.0, min(1.0, self.continuity_pressure))
            )

        # Validate continuity_mode
        if self.continuity_mode not in ("stable", "strained", "fragmenting"):
            raise ValueError(
                f"continuity_mode must be 'stable', 'strained', or 'fragmenting', "
                f"got '{self.continuity_mode}'"
            )

        # Validate contributing_factors - must be subset of allowed tags
        if not isinstance(self.contributing_factors, tuple):
            raise ValueError(
                f"contributing_factors must be tuple, "
                f"got {type(self.contributing_factors).__name__}"
            )
        invalid_factors = set(self.contributing_factors) - ALLOWED_CONTRIBUTING_FACTORS
        if invalid_factors:
            raise ValueError(
                f"contributing_factors contains invalid tags: {invalid_factors}"
            )

    # -------------------------------------------------------------------------
    # Convenience methods
    # -------------------------------------------------------------------------

    def is_stable(self) -> bool:
        """Return True if continuity mode is stable."""
        return self.continuity_mode == "stable"

    def is_strained(self) -> bool:
        """Return True if continuity mode is strained."""
        return self.continuity_mode == "strained"

    def is_fragmenting(self) -> bool:
        """Return True if continuity mode is fragmenting."""
        return self.continuity_mode == "fragmenting"

    def has_high_drift(self) -> bool:
        """Return True if high_drift factor is present."""
        return "high_drift" in self.contributing_factors

    def has_low_persistence(self) -> bool:
        """Return True if low_persistence factor is present."""
        return "low_persistence" in self.contributing_factors

    def has_high_volatility(self) -> bool:
        """Return True if high_volatility factor is present."""
        return "high_volatility" in self.contributing_factors

    def has_oscillation(self) -> bool:
        """Return True if oscillation factor is present."""
        return "oscillation" in self.contributing_factors

    def factor_count(self) -> int:
        """Return the number of contributing factors."""
        return len(self.contributing_factors)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize report to dictionary for API/JSON output."""
        return {
            "continuity_score": self.continuity_score,
            "continuity_mode": self.continuity_mode,
            "continuity_pressure": self.continuity_pressure,
            "oscillation_detected": self.oscillation_detected,
            "contributing_factors": list(self.contributing_factors),
            "inputs": {
                "p35_predicted_drift_score": self.p35_predicted_drift_score,
                "p35_drift_risk_band": self.p35_drift_risk_band,
                "p36_identity_resonance_index": self.p36_identity_resonance_index,
                "p36_persistence_score": self.p36_persistence_score,
                "p36_volatility_index": self.p36_volatility_index,
            },
            "historical_resonance_count": self.historical_resonance_count,
            "debug": self.debug,
            "observer_only": self.observer_only,
            "architectural_phase": self.architectural_phase,
            "version": self.version,
        }


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def create_report(
    continuity_score: float,
    continuity_mode: str,
    continuity_pressure: float,
    oscillation_detected: bool,
    contributing_factors: Tuple[str, ...],
    p35_predicted_drift_score: float = 0.0,
    p35_drift_risk_band: str = "low",
    p36_identity_resonance_index: float = 0.0,
    p36_persistence_score: float = 1.0,
    p36_volatility_index: float = 0.0,
    historical_resonance_count: int = 0,
    debug: Dict[str, Any] = None,
) -> AdaptiveContinuityReport:
    """
    Factory function to create an AdaptiveContinuityReport.

    Args:
        continuity_score: Overall continuity measure [0.0, 1.0]
        continuity_mode: Mode classification
        continuity_pressure: Inverse of continuity_score [0.0, 1.0]
        oscillation_detected: Whether oscillation pattern detected
        contributing_factors: Tuple of explanatory tags
        p35_predicted_drift_score: P35 predicted drift score input
        p35_drift_risk_band: P35 drift risk band input
        p36_identity_resonance_index: P36 identity resonance index input
        p36_persistence_score: P36 persistence score input
        p36_volatility_index: P36 volatility index input
        historical_resonance_count: Number of historical snapshots used
        debug: Optional debug dictionary

    Returns:
        AdaptiveContinuityReport instance
    """
    return AdaptiveContinuityReport(
        continuity_score=continuity_score,
        continuity_mode=continuity_mode,
        continuity_pressure=continuity_pressure,
        oscillation_detected=oscillation_detected,
        contributing_factors=contributing_factors,
        p35_predicted_drift_score=p35_predicted_drift_score,
        p35_drift_risk_band=p35_drift_risk_band,
        p36_identity_resonance_index=p36_identity_resonance_index,
        p36_persistence_score=p36_persistence_score,
        p36_volatility_index=p36_volatility_index,
        historical_resonance_count=historical_resonance_count,
        debug=debug or {},
        observer_only=True,  # Always True
    )


def mode_from_score(score: float) -> str:
    """
    Determine continuity mode from continuity score.

    Args:
        score: Continuity score [0.0, 1.0]

    Returns:
        Mode string: "stable", "strained", or "fragmenting"
    """
    if score >= MODE_STABLE_THRESHOLD:
        return "stable"
    elif score >= MODE_STRAINED_THRESHOLD:
        return "strained"
    else:
        return "fragmenting"


def create_empty_report() -> AdaptiveContinuityReport:
    """
    Create an empty report with default values.

    Used when P37 cannot compute meaningful metrics (e.g., missing inputs).

    Returns:
        A minimal AdaptiveContinuityReport with neutral defaults
    """
    return create_report(
        continuity_score=0.5,
        continuity_mode="strained",
        continuity_pressure=0.5,
        oscillation_detected=False,
        contributing_factors=(),
        debug={"reason": "empty_report_insufficient_inputs"},
    )


# Public exports
__all__ = [
    # Version
    "P37_VERSION",
    # Constants
    "W_PERSISTENCE",
    "W_INVERSE_VOLATILITY",
    "W_INVERSE_DRIFT",
    "MODE_STABLE_THRESHOLD",
    "MODE_STRAINED_THRESHOLD",
    "OSCILLATION_VOLATILITY_THRESHOLD",
    "OSCILLATION_MIN_REVERSALS",
    "OSCILLATION_WINDOW_SIZE",
    "HIGH_DRIFT_THRESHOLD",
    "LOW_PERSISTENCE_THRESHOLD",
    "HIGH_VOLATILITY_THRESHOLD",
    "ALLOWED_CONTRIBUTING_FACTORS",
    # Dataclasses
    "AdaptiveContinuityReport",
    # Helpers
    "create_report",
    "mode_from_score",
    "create_empty_report",
]
