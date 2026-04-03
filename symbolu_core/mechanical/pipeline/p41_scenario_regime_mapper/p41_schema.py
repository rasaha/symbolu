"""
P41 Schema - Coherence-Regime Scenario Mapper Types

Defines the data structures for Phase 41: Coherence-Regime Scenario Mapper,
a deterministic observer-only phase that maps coherence, drift, and horizon
alignment signals into scenario regime classifications.

PURPOSE:
    Phase 41 translates numeric coherence and alignment signals into a
    scenario classification that later phases (42-44) may simulate.

    It does NOT:
        - Predict outcomes
        - Decide which scenario is correct
        - Gate behavior
        - Influence discourse or tone

    It IS a symbolic categorization layer.

CRITICAL CONSTRAINTS:
    - Deterministic: Same inputs -> same outputs (no LLM, no randomness)
    - Read-only: Does not modify system behavior
    - Observer-only: Never used for gating, blocking, or behavior modification
    - Non-authoritative: Does not influence regime, discourse, or semantics

    Phase 41 MUST NOT:
        - Modify PipelineContext state outside its own output
        - Affect gating, routing, discourse, or action
        - Import P6-P14 or P50+
        - Perform prediction or optimization
        - Interpret meaning or emotion
        - Choose actions or recommend paths

INPUTS (Read-Only):
    Phase 41 MAY read:
        - Phase 10 Coherence v3 score (coherence_score_v3)
        - Phase 12 Coherence v3 Quality (coherence_v3_quality)
        - Phase 19 Drift Fusion Report (drift_fusion_index)
        - Phase 40 Cross-Horizon Alignment (alignment_score)

    Phase 41 MUST NOT read:
        - Raw user text
        - Semantics, intent, discourse, lexical frames
        - Acoustic / vrtti / kosha data
        - Any governance or eligibility phase (>=50)

INVARIANTS:
    - INV-P41-1: Observer-only (no influence on regimes, discourse, routing, or action)
    - INV-P41-2: Deterministic (same inputs -> same outputs)
    - INV-P41-3: Scenario labels only (no probabilities, no forecasts, no optimization)
    - INV-P41-4: Monotonic consistency (lower coherence / alignment cannot yield "better" regimes)
    - INV-P41-5: Absence-safe (missing optional inputs degrade confidence, never improve it)
"""

from dataclasses import dataclass, field
from typing import Any, Dict, Literal, Tuple


# =============================================================================
# Version
# =============================================================================

P41_VERSION = "1.0.0"


# =============================================================================
# Type Aliases
# =============================================================================

ScenarioRegime = Literal[
    "stable_continuity",
    "strained_transition",
    "divergent_instability",
    "ambiguous_mixed",
]


# =============================================================================
# Constants - Mapping Thresholds
# =============================================================================

# Rule A (stable_continuity) thresholds
STABLE_COHERENCE_THRESHOLD = 0.75      # coherence_v3_quality >= 0.75
STABLE_ALIGNMENT_THRESHOLD = 0.75      # alignment_score >= 0.75
STABLE_DRIFT_MAX_THRESHOLD = 0.30      # drift_fusion_index <= 0.30

# Rule B (strained_transition) thresholds
STRAINED_COHERENCE_THRESHOLD = 0.55    # coherence_v3_quality >= 0.55
STRAINED_ALIGNMENT_THRESHOLD = 0.45    # alignment_score >= 0.45
STRAINED_DRIFT_MAX_THRESHOLD = 0.55    # drift_fusion_index <= 0.55

# Rule C (divergent_instability) thresholds
DIVERGENT_ALIGNMENT_THRESHOLD = 0.45   # alignment_score < 0.45
DIVERGENT_DRIFT_THRESHOLD = 0.70       # drift_fusion_index >= 0.70

# Confidence weights
CONFIDENCE_WEIGHT_COHERENCE = 0.40     # 40% weight for coherence_v3_quality
CONFIDENCE_WEIGHT_ALIGNMENT = 0.40     # 40% weight for alignment_score
CONFIDENCE_WEIGHT_STABILITY = 0.20     # 20% weight for (1 - drift_fusion_index)


# =============================================================================
# Supporting Signal Tags
# =============================================================================

# Signal tags (string constants for supporting_signals tuple)
SIGNAL_HIGH_COHERENCE = "high_coherence"
SIGNAL_LOW_COHERENCE = "low_coherence"
SIGNAL_MODERATE_COHERENCE = "moderate_coherence"
SIGNAL_HIGH_ALIGNMENT = "high_alignment"
SIGNAL_LOW_ALIGNMENT = "low_alignment"
SIGNAL_MODERATE_ALIGNMENT = "moderate_alignment"
SIGNAL_LOW_DRIFT = "low_drift"
SIGNAL_HIGH_DRIFT = "high_drift"
SIGNAL_MODERATE_DRIFT = "moderate_drift"
SIGNAL_HORIZON_FRAGMENTATION = "horizon_fragmentation"
SIGNAL_QUALITY_PENALTY_ACTIVE = "quality_penalty_active"
SIGNAL_ABSENCE_PENALTY = "absence_penalty"


# =============================================================================
# Dataclasses
# =============================================================================


@dataclass(frozen=True)
class ScenarioRegimeMap:
    """
    Immutable report of scenario regime classification.

    This is the primary output of Phase 41, containing:
    - scenario_regime: Classification label
    - confidence: Confidence score [0.0, 1.0]
    - supporting_signals: Tuple of string tags indicating which signals contributed
    - observer_only: Always True (enforced)

    Invariants:
        - scenario_regime in {"stable_continuity", "strained_transition",
                              "divergent_instability", "ambiguous_mixed"}
        - confidence in [0.0, 1.0]
        - observer_only == True (cannot be False)
    """

    # Core outputs (all required)
    scenario_regime: ScenarioRegime
    confidence: float
    supporting_signals: Tuple[str, ...]
    observer_only: Literal[True]

    # Input signals (for observability)
    coherence_v3_quality: float = 0.5
    alignment_score: float = 0.5
    drift_fusion_index: float = 0.5

    # Debug info
    debug: Dict[str, Any] = field(default_factory=dict)

    # Metadata
    version: str = P41_VERSION
    architectural_phase: str = "P41"

    def __post_init__(self) -> None:
        """Validate invariants."""
        # observer_only must be True (INV-P41-1)
        if self.observer_only is not True:
            raise ValueError(
                "ScenarioRegimeMap.observer_only must be True. "
                "P41 is observation-only and cannot be used for gating."
            )

        # Validate scenario_regime
        valid_regimes = (
            "stable_continuity",
            "strained_transition",
            "divergent_instability",
            "ambiguous_mixed",
        )
        if self.scenario_regime not in valid_regimes:
            raise ValueError(
                f"ScenarioRegimeMap.scenario_regime must be one of {valid_regimes}, "
                f"got '{self.scenario_regime}'"
            )

        # Validate confidence range (clamp if necessary)
        if not isinstance(self.confidence, (int, float)):
            raise ValueError(
                f"ScenarioRegimeMap.confidence must be numeric, "
                f"got {type(self.confidence).__name__}"
            )
        if not 0.0 <= self.confidence <= 1.0:
            # Clamp to valid range
            clamped = max(0.0, min(1.0, self.confidence))
            object.__setattr__(self, "confidence", clamped)

        # Validate input signals are clamped
        if not 0.0 <= self.coherence_v3_quality <= 1.0:
            clamped = max(0.0, min(1.0, self.coherence_v3_quality))
            object.__setattr__(self, "coherence_v3_quality", clamped)

        if not 0.0 <= self.alignment_score <= 1.0:
            clamped = max(0.0, min(1.0, self.alignment_score))
            object.__setattr__(self, "alignment_score", clamped)

        if not 0.0 <= self.drift_fusion_index <= 1.0:
            clamped = max(0.0, min(1.0, self.drift_fusion_index))
            object.__setattr__(self, "drift_fusion_index", clamped)

    # -------------------------------------------------------------------------
    # Convenience methods
    # -------------------------------------------------------------------------

    def is_stable(self) -> bool:
        """Return True if scenario regime is stable_continuity."""
        return self.scenario_regime == "stable_continuity"

    def is_strained(self) -> bool:
        """Return True if scenario regime is strained_transition."""
        return self.scenario_regime == "strained_transition"

    def is_divergent(self) -> bool:
        """Return True if scenario regime is divergent_instability."""
        return self.scenario_regime == "divergent_instability"

    def is_ambiguous(self) -> bool:
        """Return True if scenario regime is ambiguous_mixed."""
        return self.scenario_regime == "ambiguous_mixed"

    def has_high_confidence(self, threshold: float = 0.75) -> bool:
        """Return True if confidence exceeds threshold."""
        return self.confidence >= threshold

    def has_low_confidence(self, threshold: float = 0.45) -> bool:
        """Return True if confidence is below threshold."""
        return self.confidence < threshold

    def signal_count(self) -> int:
        """Return the number of supporting signals."""
        return len(self.supporting_signals)

    def has_signal(self, signal: str) -> bool:
        """Check if a specific signal is present."""
        return signal in self.supporting_signals

    def to_dict(self) -> Dict[str, Any]:
        """Serialize report to dictionary for API/JSON output."""
        return {
            "scenario_regime": self.scenario_regime,
            "confidence": self.confidence,
            "supporting_signals": list(self.supporting_signals),
            "observer_only": self.observer_only,
            "inputs": {
                "coherence_v3_quality": self.coherence_v3_quality,
                "alignment_score": self.alignment_score,
                "drift_fusion_index": self.drift_fusion_index,
            },
            "debug": self.debug,
            "version": self.version,
            "architectural_phase": self.architectural_phase,
        }


# =============================================================================
# Factory Functions
# =============================================================================


def create_scenario_regime_map(
    scenario_regime: ScenarioRegime,
    confidence: float,
    supporting_signals: Tuple[str, ...],
    coherence_v3_quality: float = 0.5,
    alignment_score: float = 0.5,
    drift_fusion_index: float = 0.5,
    debug: Dict[str, Any] = None,
) -> ScenarioRegimeMap:
    """
    Factory function to create a ScenarioRegimeMap.

    Args:
        scenario_regime: Classification label
        confidence: Confidence score [0.0, 1.0]
        supporting_signals: Tuple of signal tags
        coherence_v3_quality: P12 coherence v3 quality input
        alignment_score: P40 alignment score input
        drift_fusion_index: P19 drift fusion index input
        debug: Optional debug dictionary

    Returns:
        ScenarioRegimeMap instance
    """
    return ScenarioRegimeMap(
        scenario_regime=scenario_regime,
        confidence=confidence,
        supporting_signals=supporting_signals,
        observer_only=True,
        coherence_v3_quality=coherence_v3_quality,
        alignment_score=alignment_score,
        drift_fusion_index=drift_fusion_index,
        debug=debug or {},
    )


# Public exports
__all__ = [
    # Version
    "P41_VERSION",
    # Type Aliases
    "ScenarioRegime",
    # Constants
    "STABLE_COHERENCE_THRESHOLD",
    "STABLE_ALIGNMENT_THRESHOLD",
    "STABLE_DRIFT_MAX_THRESHOLD",
    "STRAINED_COHERENCE_THRESHOLD",
    "STRAINED_ALIGNMENT_THRESHOLD",
    "STRAINED_DRIFT_MAX_THRESHOLD",
    "DIVERGENT_ALIGNMENT_THRESHOLD",
    "DIVERGENT_DRIFT_THRESHOLD",
    "CONFIDENCE_WEIGHT_COHERENCE",
    "CONFIDENCE_WEIGHT_ALIGNMENT",
    "CONFIDENCE_WEIGHT_STABILITY",
    # Signal Tags
    "SIGNAL_HIGH_COHERENCE",
    "SIGNAL_LOW_COHERENCE",
    "SIGNAL_MODERATE_COHERENCE",
    "SIGNAL_HIGH_ALIGNMENT",
    "SIGNAL_LOW_ALIGNMENT",
    "SIGNAL_MODERATE_ALIGNMENT",
    "SIGNAL_LOW_DRIFT",
    "SIGNAL_HIGH_DRIFT",
    "SIGNAL_MODERATE_DRIFT",
    "SIGNAL_HORIZON_FRAGMENTATION",
    "SIGNAL_QUALITY_PENALTY_ACTIVE",
    "SIGNAL_ABSENCE_PENALTY",
    # Dataclasses
    "ScenarioRegimeMap",
    # Factory
    "create_scenario_regime_map",
]
