"""
Phase 43: Scenario What-If Simulator Schema

Frozen dataclasses for what-if scenario variations.

Phase 43 answers:
    "If the current scenario field were perturbed in controlled ways,
     what alternative scenario trajectories could exist?"

It does NOT:
    - Pick a preferred future
    - Forecast likelihood
    - Influence governance, discourse, or delivery
    - Feed any upstream decision logic

Invariants:
    INV-P43-1: Simulation only (no prediction, no likelihoods)
    INV-P43-2: Deterministic perturbations (no randomness, seeded noise only if fixed)
    INV-P43-3: Bounded exploration (exactly four variants, no more)
    INV-P43-4: No authority impact (results never influence regime, discourse, or action)
    INV-P43-5: Absence-safe (no base input -> no output)
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Tuple

# Version identifier for this phase
P43_VERSION = "1.0.0"

# Valid perturbation types (exactly four, no others allowed)
PerturbationType = Literal[
    "entropy_shift",
    "confidence_drop",
    "regime_flip",
    "noise_injection",
]

VALID_PERTURBATIONS: Tuple[str, ...] = (
    "entropy_shift",
    "confidence_drop",
    "regime_flip",
    "noise_injection",
)

# Number of variants (exactly 4, enforced by INV-P43-3)
NUM_VARIANTS = 4

# Valid scenario regimes (inherited from Phase 42)
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

# Threshold for dominant regime selection (same as P42)
DOMINANT_THRESHOLD = 0.60

# Perturbation parameters (fixed, deterministic)
ENTROPY_SHIFT_DELTA = 0.15
CONFIDENCE_DROP_DELTA = 0.20
NOISE_INJECTION_DELTA = 0.05


@dataclass(frozen=True)
class ScenarioVariant:
    """
    A single what-if scenario variant.

    Represents the result of applying one perturbation type to the
    base scenario fusion field.

    Invariants:
        - variant_id must be unique within a ScenarioWhatIfSet
        - perturbation_type must be one of the 4 valid types
        - resulting_regime must be one of the 4 valid regimes
        - delta values represent change from base, not absolute values
    """

    variant_id: str
    perturbation_type: PerturbationType
    resulting_regime: ScenarioRegime
    delta_entropy: float
    delta_confidence: float

    def __post_init__(self) -> None:
        """Validate invariants on construction."""
        # Validate perturbation_type
        if self.perturbation_type not in VALID_PERTURBATIONS:
            raise ValueError(
                f"Invalid perturbation_type: {self.perturbation_type}. "
                f"Must be one of {VALID_PERTURBATIONS}"
            )

        # Validate resulting_regime
        if self.resulting_regime not in VALID_REGIMES:
            raise ValueError(
                f"Invalid resulting_regime: {self.resulting_regime}. "
                f"Must be one of {VALID_REGIMES}"
            )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for observability."""
        return {
            "variant_id": self.variant_id,
            "perturbation_type": self.perturbation_type,
            "resulting_regime": self.resulting_regime,
            "delta_entropy": self.delta_entropy,
            "delta_confidence": self.delta_confidence,
        }


@dataclass(frozen=True)
class ScenarioWhatIfSet:
    """
    Immutable set of what-if scenario variants.

    This is an observer-only output that explores counterfactual variations
    of the fused scenario field from Phase 42.

    Invariants:
        - base_regime must be one of the 4 valid regimes
        - what_if_variants must contain exactly 4 variants (INV-P43-3)
        - variant_count must equal len(what_if_variants)
        - observer_only must be True (enforced)
    """

    # Core outputs (all required)
    base_regime: ScenarioRegime
    what_if_variants: Tuple[ScenarioVariant, ...]
    variant_count: int
    observer_only: Literal[True]

    # Metadata
    debug: Dict[str, Any] = field(default_factory=dict)
    version: str = P43_VERSION
    architectural_phase: str = "P43"

    def __post_init__(self) -> None:
        """Validate invariants on construction."""
        # INV-P43-4: observer_only must be True
        if self.observer_only is not True:
            raise ValueError("observer_only must be True (INV-P43-4)")

        # Validate base_regime
        if self.base_regime not in VALID_REGIMES:
            raise ValueError(
                f"Invalid base_regime: {self.base_regime}. "
                f"Must be one of {VALID_REGIMES}"
            )

        # INV-P43-3: Exactly 4 variants
        if len(self.what_if_variants) != NUM_VARIANTS:
            raise ValueError(
                f"Must have exactly {NUM_VARIANTS} variants, "
                f"got {len(self.what_if_variants)} (INV-P43-3)"
            )

        # Validate variant_count matches
        if self.variant_count != len(self.what_if_variants):
            raise ValueError(
                f"variant_count ({self.variant_count}) must equal "
                f"len(what_if_variants) ({len(self.what_if_variants)})"
            )

        # Validate each variant
        seen_ids = set()
        seen_perturbations = set()
        for variant in self.what_if_variants:
            if not isinstance(variant, ScenarioVariant):
                raise ValueError(
                    f"what_if_variants must contain ScenarioVariant objects, "
                    f"got {type(variant)}"
                )
            # Check unique variant_ids
            if variant.variant_id in seen_ids:
                raise ValueError(f"Duplicate variant_id: {variant.variant_id}")
            seen_ids.add(variant.variant_id)

            # Check unique perturbation types (one of each)
            if variant.perturbation_type in seen_perturbations:
                raise ValueError(
                    f"Duplicate perturbation_type: {variant.perturbation_type}"
                )
            seen_perturbations.add(variant.perturbation_type)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for observability."""
        return {
            "base_regime": self.base_regime,
            "what_if_variants": [v.to_dict() for v in self.what_if_variants],
            "variant_count": self.variant_count,
            "observer_only": self.observer_only,
            "version": self.version,
            "architectural_phase": self.architectural_phase,
            "debug": dict(self.debug) if self.debug else {},
        }


def create_scenario_variant(
    variant_id: str,
    perturbation_type: PerturbationType,
    resulting_regime: ScenarioRegime,
    delta_entropy: float,
    delta_confidence: float,
) -> ScenarioVariant:
    """
    Factory function to create ScenarioVariant safely.
    """
    return ScenarioVariant(
        variant_id=variant_id,
        perturbation_type=perturbation_type,
        resulting_regime=resulting_regime,
        delta_entropy=delta_entropy,
        delta_confidence=delta_confidence,
    )


def create_scenario_what_if_set(
    base_regime: ScenarioRegime,
    what_if_variants: List[ScenarioVariant],
    debug: Dict[str, Any] | None = None,
) -> ScenarioWhatIfSet:
    """
    Factory function to create ScenarioWhatIfSet safely.

    Always sets observer_only=True (enforced by design).
    Always sets variant_count from len(variants).
    """
    return ScenarioWhatIfSet(
        base_regime=base_regime,
        what_if_variants=tuple(what_if_variants),
        variant_count=len(what_if_variants),
        observer_only=True,
        debug=debug or {},
    )
