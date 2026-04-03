"""
P19 Schema - Drift Fusion Types and Constants

Defines the data structures for Phase 19: Drift Fusion, a deterministic
diagnostic synthesis phase that fuses symbolic, semantic, and temporal
drift signals into a unified drift profile.

CRITICAL CONSTRAINTS:
    - Deterministic: Same inputs → same outputs (no LLM, no randomness)
    - Read-only: Does not modify system behavior
    - Non-invasive: Zero impact on routing, TTOR, MLCR, Fusion, DHA, Renderer
    - Observation-only: Never used for gating, blocking, or behavior modification

    ❌ Must NOT:
        - Infer intent
        - Infer emotion
        - Select regime
        - Gate actions
        - Trigger any side effects
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Dict, Any


# =============================================================================
# Version
# =============================================================================

P19_VERSION = "1.0.0"


# =============================================================================
# Enums
# =============================================================================

class DriftRiskBand(Enum):
    """Classification of drift risk severity."""
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"


class DriftPatternTag(Enum):
    """Deterministic pattern tags based on rule-based thresholds."""
    SEMANTIC_DRIFT = "semantic_drift"  # semantic_integrity_score < 0.55
    COGNITIVE_DRIFT = "cognitive_drift"  # cognitive_drift_v3 > 0.55
    TEMPORAL_INSTABILITY = "temporal_instability"  # temporal_entropy_volatility > 0.55
    ENTROPY_SHIFT = "entropy_shift"  # |temporal_entropy_diff - 0.5| > 0.25
    LOW_COHERENCE_CONTEXT = "low_coherence_context"  # coherence_fused < 0.45


# =============================================================================
# Constants - Formula Weights
# =============================================================================

# Drift fusion index weights (must sum to 1.0)
W_COGNITIVE_DRIFT = 0.35  # cognitive_drift_v3 direct contribution
W_INTEGRITY = 0.25  # (1 - semantic_integrity_score) inverted
W_VOLATILITY = 0.20  # temporal_entropy_volatility direct contribution
W_ENTROPY_SHIFT = 0.15  # |temporal_entropy_diff - 0.5| deviation from neutral
W_COHERENCE = 0.05  # (1 - coherence_fused) inverted

# Risk band thresholds
RISK_BAND_LOW_THRESHOLD = 0.30  # index < 0.30 → "low"
RISK_BAND_HIGH_THRESHOLD = 0.65  # index >= 0.65 → "high"

# Pattern tag thresholds
TAG_SEMANTIC_DRIFT_THRESHOLD = 0.55  # semantic_integrity < 0.55
TAG_COGNITIVE_DRIFT_THRESHOLD = 0.55  # cognitive_drift > 0.55
TAG_TEMPORAL_INSTABILITY_THRESHOLD = 0.55  # volatility > 0.55
TAG_ENTROPY_SHIFT_THRESHOLD = 0.25  # |diff - 0.5| > 0.25
TAG_LOW_COHERENCE_THRESHOLD = 0.45  # coherence_fused < 0.45


# =============================================================================
# Dataclasses
# =============================================================================

@dataclass(frozen=True)
class P19DriftFusionReport:
    """
    Immutable report of drift fusion computation.

    This is the primary output of Phase 19, containing:
    - drift_fusion_index: Overall drift severity [0.0, 1.0]
    - drift_risk_band: Risk classification (low/moderate/high)
    - drift_pattern_tags: List of detected drift patterns

    Plus the input signals used for computation (for observability).

    Invariants:
        - drift_fusion_index ∈ [0.0, 1.0]
        - drift_risk_band ∈ {"low", "moderate", "high"}
        - All tags are valid DriftPatternTag values
    """

    # Core outputs
    drift_fusion_index: float
    drift_risk_band: str
    drift_pattern_tags: tuple  # Immutable tuple of tag strings

    # Input signals (for observability)
    semantic_integrity_score: Optional[float] = None
    cognitive_drift_v3: Optional[float] = None
    temporal_entropy_diff: Optional[float] = None
    temporal_entropy_volatility: Optional[float] = None
    coherence_fused: Optional[float] = None

    # Debug info
    debug: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Validate invariants."""
        if not (0.0 <= self.drift_fusion_index <= 1.0):
            object.__setattr__(
                self, 'drift_fusion_index',
                max(0.0, min(1.0, self.drift_fusion_index))
            )

        if self.drift_risk_band not in ("low", "moderate", "high"):
            raise ValueError(
                f"drift_risk_band must be 'low', 'moderate', or 'high', "
                f"got '{self.drift_risk_band}'"
            )

    # -------------------------------------------------------------------------
    # Convenience methods
    # -------------------------------------------------------------------------

    def is_low_risk(self) -> bool:
        """Return True if drift risk is low."""
        return self.drift_risk_band == "low"

    def is_moderate_risk(self) -> bool:
        """Return True if drift risk is moderate."""
        return self.drift_risk_band == "moderate"

    def is_high_risk(self) -> bool:
        """Return True if drift risk is high."""
        return self.drift_risk_band == "high"

    def has_semantic_drift(self) -> bool:
        """Return True if semantic_drift tag is present."""
        return DriftPatternTag.SEMANTIC_DRIFT.value in self.drift_pattern_tags

    def has_cognitive_drift(self) -> bool:
        """Return True if cognitive_drift tag is present."""
        return DriftPatternTag.COGNITIVE_DRIFT.value in self.drift_pattern_tags

    def has_temporal_instability(self) -> bool:
        """Return True if temporal_instability tag is present."""
        return DriftPatternTag.TEMPORAL_INSTABILITY.value in self.drift_pattern_tags

    def has_entropy_shift(self) -> bool:
        """Return True if entropy_shift tag is present."""
        return DriftPatternTag.ENTROPY_SHIFT.value in self.drift_pattern_tags

    def has_low_coherence_context(self) -> bool:
        """Return True if low_coherence_context tag is present."""
        return DriftPatternTag.LOW_COHERENCE_CONTEXT.value in self.drift_pattern_tags

    def tag_count(self) -> int:
        """Return the number of drift pattern tags."""
        return len(self.drift_pattern_tags)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize report to dictionary for API/JSON output."""
        return {
            "drift_fusion_index": self.drift_fusion_index,
            "drift_risk_band": self.drift_risk_band,
            "drift_pattern_tags": list(self.drift_pattern_tags),
            "inputs": {
                "semantic_integrity_score": self.semantic_integrity_score,
                "cognitive_drift_v3": self.cognitive_drift_v3,
                "temporal_entropy_diff": self.temporal_entropy_diff,
                "temporal_entropy_volatility": self.temporal_entropy_volatility,
                "coherence_fused": self.coherence_fused,
            },
            "debug": self.debug,
        }


# =============================================================================
# Helper Functions
# =============================================================================

def create_report(
    drift_fusion_index: float,
    drift_risk_band: str,
    drift_pattern_tags: List[str],
    semantic_integrity_score: Optional[float] = None,
    cognitive_drift_v3: Optional[float] = None,
    temporal_entropy_diff: Optional[float] = None,
    temporal_entropy_volatility: Optional[float] = None,
    coherence_fused: Optional[float] = None,
    debug: Optional[Dict[str, Any]] = None,
) -> P19DriftFusionReport:
    """
    Factory function to create a P19DriftFusionReport.

    Args:
        drift_fusion_index: Overall drift index [0.0, 1.0]
        drift_risk_band: Risk band ("low", "moderate", "high")
        drift_pattern_tags: List of pattern tag strings
        semantic_integrity_score: P17 semantic integrity input
        cognitive_drift_v3: P17 cognitive drift input
        temporal_entropy_diff: P18 entropy diff input
        temporal_entropy_volatility: P18 volatility input
        coherence_fused: P16 fused coherence input
        debug: Optional debug dictionary

    Returns:
        P19DriftFusionReport instance
    """
    return P19DriftFusionReport(
        drift_fusion_index=drift_fusion_index,
        drift_risk_band=drift_risk_band,
        drift_pattern_tags=tuple(drift_pattern_tags),
        semantic_integrity_score=semantic_integrity_score,
        cognitive_drift_v3=cognitive_drift_v3,
        temporal_entropy_diff=temporal_entropy_diff,
        temporal_entropy_volatility=temporal_entropy_volatility,
        coherence_fused=coherence_fused,
        debug=debug or {},
    )


def risk_band_from_index(index: float) -> str:
    """
    Determine risk band from drift fusion index.

    Args:
        index: Drift fusion index [0.0, 1.0]

    Returns:
        Risk band string: "low", "moderate", or "high"
    """
    if index < RISK_BAND_LOW_THRESHOLD:
        return "low"
    elif index < RISK_BAND_HIGH_THRESHOLD:
        return "moderate"
    else:
        return "high"
