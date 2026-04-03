"""
P26 - Unified Consciousness Formula Schema Definitions

Defines the immutable data structures for Phase 26: Unified Consciousness Formula (UCF).

UCF computes a single scalar that answers:
"How internally coherent and stable is the system's cognitive state right now?"

CRITICAL CONSTRAINTS:
    - Deterministic: Same inputs -> same outputs (bitwise), no LLM, no randomness
    - Read-only: Does not modify system behavior
    - Non-invasive: Zero impact on routing, TTOR, MLCR, Fusion, DHA, Renderer
    - Observation-only: Never used for gating, blocking, or behavior modification
    - Authoritative as metric: UCF is the canonical stability scalar

    ❌ Must NOT:
        - Decide regime
        - Gate insight
        - Select discourse
        - Influence lexical choice
        - Trigger actions
        - Import P6-P9, P21 delivery, Renderer, DHA, Persona
        - Import Observer-only phases (P22-P24)
        - Use observer acoustic data

    ✅ May import (read-only):
        - CoherenceState (P10/P12 outputs)
        - Temporal metrics (P18, P19)
        - Identity harmonics (if present)
        - Schema stability metrics (P33)

Invariants:
    - INV-P26-1: UCF is read-only truth, not a decision
    - INV-P26-2: Observer data cannot affect UCF
    - INV-P26-3: UCF monotonic with respect to instability
    - INV-P26-4: UCF never opens gates directly
    - INV-P26-5: Absence of optional inputs never destabilizes output
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Literal, Optional


# ============================================================================
# VERSION
# ============================================================================

P26_VERSION = "1.0.0"


# ============================================================================
# CONSTANTS - Canonical Formula Weights
# ============================================================================

# UCF formula weights (MUST sum to 1.0)
# These are the canonical v1.0 weights - adjustments must be explicit
UCF_WEIGHTS = {
    "coherence_v3_quality": 0.30,      # Primary coherence quality signal
    "drift_fusion_stability": 0.25,    # Inverted drift fusion (1 - drift_fusion_index)
    "entropy_stability": 0.20,         # Inverted entropy volatility (1 - entropy_volatility)
    "schema_stability": 0.15,          # Schema stability from P33
    "identity_harmonics": 0.10,        # Identity harmonics stability (optional)
}

# Verify weights sum to 1.0 at module load
_weight_sum = sum(UCF_WEIGHTS.values())
assert abs(_weight_sum - 1.0) < 1e-9, f"UCF_WEIGHTS must sum to 1.0, got {_weight_sum}"

# Stability band thresholds (deterministic, no heuristics)
STABILITY_THRESHOLDS = {
    "stable": 0.75,        # ucf >= 0.75 -> "stable"
    "transitional": 0.45,  # 0.45 <= ucf < 0.75 -> "transitional"
    # ucf < 0.45 -> "unstable"
}

# Neutral default for missing optional inputs
NEUTRAL_DEFAULT = 0.5


# ============================================================================
# ENUMS - Stability band classification
# ============================================================================


class StabilityBand(str, Enum):
    """
    Classification of UCF stability based on score thresholds.

    STABLE: UCF >= 0.75 - System is in a stable cognitive state
    TRANSITIONAL: 0.45 <= UCF < 0.75 - System is in transition
    UNSTABLE: UCF < 0.45 - System shows cognitive instability

    These thresholds are deterministic - no heuristics, no exceptions.
    """
    STABLE = "stable"
    TRANSITIONAL = "transitional"
    UNSTABLE = "unstable"


# ============================================================================
# DATACLASSES - Core output structure
# ============================================================================


@dataclass(frozen=True)
class UnifiedConsciousnessState:
    """
    Immutable output of Phase 26: Unified Consciousness Formula computation.

    This is the canonical output of UCF, providing a single scalar stability
    metric along with supporting metadata for observability.

    Fields:
        ucf_score: The unified consciousness score [0.0, 1.0]
                   Higher = more stable, lower = less stable
        stability_band: Classification of stability level
        contributing_factors: Breakdown of each factor's contribution
        confidence: Confidence in the UCF score [0.0, 1.0]
                   Based on data availability (how many inputs were non-null)

    Invariants:
        - ucf_score MUST be in [0.0, 1.0]
        - stability_band MUST match ucf_score per threshold rules
        - contributing_factors values MUST be in [0.0, 1.0]
        - confidence MUST be in [0.0, 1.0]
        - observer_only MUST always be True

    This state is:
        - Deterministic: Same inputs produce identical output
        - Read-only: Never modifies upstream pipeline state
        - Non-authoritative for decisions: Only authoritative as a metric
    """

    # Core output
    ucf_score: float
    stability_band: StabilityBand

    # Observability
    contributing_factors: Dict[str, float]
    confidence: float

    # Debug/trace information
    debug: Dict[str, Any] = field(default_factory=dict)

    # Authority markers - MUST be True
    observer_only: bool = True
    architectural_phase: str = "P26"
    version: str = P26_VERSION

    def __post_init__(self) -> None:
        """Validate UnifiedConsciousnessState invariants."""
        # INV-P26-1: observer_only must always be True
        if not self.observer_only:
            raise ValueError(
                "UnifiedConsciousnessState.observer_only must be True. "
                "P26 is observation-only and non-authoritative for decisions."
            )

        # Validate ucf_score is in [0.0, 1.0]
        if not isinstance(self.ucf_score, (int, float)):
            raise ValueError(
                f"UnifiedConsciousnessState.ucf_score must be numeric, "
                f"got {type(self.ucf_score).__name__}"
            )
        if not 0.0 <= self.ucf_score <= 1.0:
            raise ValueError(
                f"UnifiedConsciousnessState.ucf_score must be in [0.0, 1.0], "
                f"got {self.ucf_score}"
            )

        # Validate stability_band
        if not isinstance(self.stability_band, StabilityBand):
            raise ValueError(
                f"UnifiedConsciousnessState.stability_band must be StabilityBand, "
                f"got {type(self.stability_band).__name__}"
            )

        # Validate stability_band matches ucf_score thresholds
        expected_band = _derive_stability_band(self.ucf_score)
        if self.stability_band != expected_band:
            raise ValueError(
                f"UnifiedConsciousnessState.stability_band mismatch: "
                f"ucf_score={self.ucf_score} should have band={expected_band.value}, "
                f"got {self.stability_band.value}"
            )

        # Validate confidence is in [0.0, 1.0]
        if not isinstance(self.confidence, (int, float)):
            raise ValueError(
                f"UnifiedConsciousnessState.confidence must be numeric, "
                f"got {type(self.confidence).__name__}"
            )
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(
                f"UnifiedConsciousnessState.confidence must be in [0.0, 1.0], "
                f"got {self.confidence}"
            )

        # Validate contributing_factors
        if not isinstance(self.contributing_factors, dict):
            raise ValueError(
                f"UnifiedConsciousnessState.contributing_factors must be dict, "
                f"got {type(self.contributing_factors).__name__}"
            )
        for factor_name, factor_value in self.contributing_factors.items():
            if not isinstance(factor_name, str):
                raise ValueError(
                    f"Factor names must be strings, got {type(factor_name).__name__}"
                )
            if not isinstance(factor_value, (int, float)):
                raise ValueError(
                    f"Factor '{factor_name}' value must be numeric, "
                    f"got {type(factor_value).__name__}"
                )
            if not 0.0 <= factor_value <= 1.0:
                raise ValueError(
                    f"Factor '{factor_name}' value must be in [0.0, 1.0], "
                    f"got {factor_value}"
                )

    # ========================================================================
    # CONVENIENCE METHODS - For downstream observability access
    # ========================================================================

    def is_stable(self) -> bool:
        """Check if UCF indicates stable cognitive state."""
        return self.stability_band == StabilityBand.STABLE

    def is_transitional(self) -> bool:
        """Check if UCF indicates transitional cognitive state."""
        return self.stability_band == StabilityBand.TRANSITIONAL

    def is_unstable(self) -> bool:
        """Check if UCF indicates unstable cognitive state."""
        return self.stability_band == StabilityBand.UNSTABLE

    def is_high_confidence(self) -> bool:
        """Check if confidence in UCF score is high (>= 0.7)."""
        return self.confidence >= 0.7

    def is_low_confidence(self) -> bool:
        """Check if confidence in UCF score is low (< 0.4)."""
        return self.confidence < 0.4

    def get_factor(self, factor_name: str) -> Optional[float]:
        """Get a specific contributing factor value."""
        return self.contributing_factors.get(factor_name)

    def get_dominant_factor(self) -> Optional[str]:
        """Get the factor with highest contribution."""
        if not self.contributing_factors:
            return None
        return max(self.contributing_factors, key=self.contributing_factors.get)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for logging/tracing."""
        return {
            "ucf_score": self.ucf_score,
            "stability_band": self.stability_band.value,
            "contributing_factors": dict(self.contributing_factors),
            "confidence": self.confidence,
            "debug": self.debug,
            "observer_only": self.observer_only,
            "architectural_phase": self.architectural_phase,
            "version": self.version,
        }


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def _derive_stability_band(ucf_score: float) -> StabilityBand:
    """
    Derive stability band from UCF score using canonical thresholds.

    This is the single source of truth for band derivation.
    No heuristics. No exceptions.

    Args:
        ucf_score: UCF score in [0.0, 1.0]

    Returns:
        StabilityBand based on deterministic thresholds
    """
    if ucf_score >= STABILITY_THRESHOLDS["stable"]:
        return StabilityBand.STABLE
    elif ucf_score >= STABILITY_THRESHOLDS["transitional"]:
        return StabilityBand.TRANSITIONAL
    else:
        return StabilityBand.UNSTABLE


def create_ucf_state(
    ucf_score: float,
    contributing_factors: Optional[Dict[str, float]] = None,
    confidence: float = 0.5,
    debug: Optional[Dict[str, Any]] = None,
) -> UnifiedConsciousnessState:
    """
    Factory function to create a UnifiedConsciousnessState.

    This handles the automatic derivation of stability_band from ucf_score.

    Args:
        ucf_score: UCF score in [0.0, 1.0]
        contributing_factors: Dict of factor names to values [0.0, 1.0]
        confidence: Confidence in the score [0.0, 1.0]
        debug: Optional debug/trace information

    Returns:
        A validated UnifiedConsciousnessState instance
    """
    # Clamp ucf_score to [0.0, 1.0]
    clamped_score = max(0.0, min(1.0, ucf_score))

    # Derive stability band
    stability_band = _derive_stability_band(clamped_score)

    return UnifiedConsciousnessState(
        ucf_score=clamped_score,
        stability_band=stability_band,
        contributing_factors=contributing_factors or {},
        confidence=max(0.0, min(1.0, confidence)),
        debug=debug or {},
        observer_only=True,
    )


def create_neutral_state() -> UnifiedConsciousnessState:
    """
    Create a neutral UCF state when insufficient data is available.

    Returns a state with ucf_score=0.5 (transitional) and confidence=0.0.

    Returns:
        A neutral UnifiedConsciousnessState with minimal confidence
    """
    return create_ucf_state(
        ucf_score=NEUTRAL_DEFAULT,
        contributing_factors={},
        confidence=0.0,
        debug={"reason": "neutral_state_insufficient_data"},
    )


# Public exports
__all__ = [
    # Version
    "P26_VERSION",
    # Constants
    "UCF_WEIGHTS",
    "STABILITY_THRESHOLDS",
    "NEUTRAL_DEFAULT",
    # Enums
    "StabilityBand",
    # Dataclasses
    "UnifiedConsciousnessState",
    # Helpers
    "create_ucf_state",
    "create_neutral_state",
]
