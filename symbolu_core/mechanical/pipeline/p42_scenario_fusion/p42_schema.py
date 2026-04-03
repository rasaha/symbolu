"""
Phase 42: Scenario Fusion Field Schema

Frozen dataclass for consolidated scenario field output.

Invariants:
    INV-P42-1: Observer-only (no downstream authority impact)
    INV-P42-2: Deterministic aggregation (no randomness, no learned weights)
    INV-P42-3: No regime creation (cannot invent new regimes)
    INV-P42-4: Monotonic ambiguity (more disagreement -> higher entropy)
    INV-P42-5: Absence-safe (empty input produces no output)
"""

from dataclasses import dataclass, field
from typing import Any, Dict, Literal, Tuple

# Version identifier for this phase
P42_VERSION = "1.0.0"

# Valid scenario regimes (inherited from Phase 41)
ScenarioRegime = Literal[
    "stable_continuity",
    "strained_transition",
    "divergent_instability",
    "ambiguous_mixed",
]

VALID_REGIMES: Tuple[str, ...] = (
    "stable_continuity",
    "strained_transition",
    "divergent_instability",
    "ambiguous_mixed",
)

# Number of possible regimes (used for entropy normalization)
NUM_REGIMES = 4

# Threshold for dominant regime selection
DOMINANT_THRESHOLD = 0.60


@dataclass(frozen=True)
class ScenarioFusionField:
    """
    Immutable consolidated scenario field from fused regime observations.

    This is an observer-only output that aggregates multiple ScenarioRegimeMap
    observations into a unified scenario field representation.

    Invariants:
        - dominant_regime must be one of the 4 valid regimes
        - regime_distribution must sum to 1.0 (normalized)
        - fusion_confidence in [0.0, 1.0]
        - regime_entropy in [0.0, 1.0]
        - observer_only must be True (enforced)
    """

    # Core outputs (all required)
    dominant_regime: ScenarioRegime
    regime_distribution: Dict[str, float]
    fusion_confidence: float
    regime_entropy: float
    observer_only: Literal[True]

    # Metadata
    input_count: int = 0
    debug: Dict[str, Any] = field(default_factory=dict)
    version: str = P42_VERSION
    architectural_phase: str = "P42"

    def __post_init__(self) -> None:
        """Validate invariants on construction."""
        # INV-P42-1: observer_only must be True
        if self.observer_only is not True:
            raise ValueError("observer_only must be True (INV-P42-1)")

        # INV-P42-3: dominant_regime must be valid (no regime creation)
        if self.dominant_regime not in VALID_REGIMES:
            raise ValueError(
                f"Invalid dominant_regime: {self.dominant_regime}. "
                f"Must be one of {VALID_REGIMES} (INV-P42-3)"
            )

        # Validate regime_distribution keys
        for key in self.regime_distribution:
            if key not in VALID_REGIMES:
                raise ValueError(
                    f"Invalid regime in distribution: {key}. "
                    f"Must be one of {VALID_REGIMES} (INV-P42-3)"
                )

        # Clamp fusion_confidence to [0.0, 1.0]
        if not 0.0 <= self.fusion_confidence <= 1.0:
            clamped = max(0.0, min(1.0, self.fusion_confidence))
            object.__setattr__(self, "fusion_confidence", clamped)

        # Clamp regime_entropy to [0.0, 1.0]
        if not 0.0 <= self.regime_entropy <= 1.0:
            clamped = max(0.0, min(1.0, self.regime_entropy))
            object.__setattr__(self, "regime_entropy", clamped)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for observability."""
        return {
            "dominant_regime": self.dominant_regime,
            "regime_distribution": dict(self.regime_distribution),
            "fusion_confidence": self.fusion_confidence,
            "regime_entropy": self.regime_entropy,
            "input_count": self.input_count,
            "observer_only": self.observer_only,
            "version": self.version,
            "architectural_phase": self.architectural_phase,
            "debug": dict(self.debug) if self.debug else {},
        }


def create_scenario_fusion_field(
    dominant_regime: ScenarioRegime,
    regime_distribution: Dict[str, float],
    fusion_confidence: float,
    regime_entropy: float,
    input_count: int = 0,
    debug: Dict[str, Any] | None = None,
) -> ScenarioFusionField:
    """
    Factory function to create ScenarioFusionField safely.

    Always sets observer_only=True (enforced by design).
    """
    return ScenarioFusionField(
        dominant_regime=dominant_regime,
        regime_distribution=regime_distribution,
        fusion_confidence=fusion_confidence,
        regime_entropy=regime_entropy,
        observer_only=True,
        input_count=input_count,
        debug=debug or {},
    )
