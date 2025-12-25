"""
Phase-5 Data Models
===================

Immutable dataclasses for Phase-5 dynamic resolution outputs.

CRITICAL: Phase-5 produces NUMERICAL trajectories, not semantic text.
All outputs are numbers, directions, and flags — never meanings.

Phase-5 CANNOT "fix" ontology issues.
Phase-5 only reveals whether issues are dynamic or structural.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Tuple, Optional


class Direction(str, Enum):
    """
    Direction of traversal in the layer stack.

    Phase-5 allows both upward AND downward traversal.
    This is dynamic movement, NOT reverse sublimation in ontology.
    """

    UP = "up"
    DOWN = "down"
    LATERAL = "lateral"


@dataclass(frozen=True)
class DynamicState:
    """
    A single state in the dynamic trajectory.

    All fields are numerical or categorical — no semantic text.
    This separation ensures Phase-5 cannot invent meanings.

    Attributes:
        time_step: The discrete time step (0-indexed)
        layer_id: Current ontological layer (e.g., "O1_POTENTIAL")
        layer_index: Numeric layer index (1-12)
        activation_level: Current activation (0.0 to 1.0)
        momentum: Accumulated directional force (-1.0 to 1.0)
            Positive = upward, Negative = downward
        direction: Current movement direction
        distortion_load: Accumulated distortion pressure (0.0+)
        sublimation_load: Accumulated sublimation pressure (0.0+)
        termination_flag: True if O12 termination occurred
        regression_flag: True if downward movement due to load
    """

    time_step: int
    layer_id: str
    layer_index: int
    activation_level: float
    momentum: float
    direction: Direction
    distortion_load: float
    sublimation_load: float
    termination_flag: bool
    regression_flag: bool

    def __post_init__(self) -> None:
        """Validate numerical bounds."""
        if not isinstance(self.time_step, int) or self.time_step < 0:
            raise ValueError(f"time_step must be non-negative int, got {self.time_step}")

        if not isinstance(self.layer_index, int) or not 1 <= self.layer_index <= 12:
            raise ValueError(f"layer_index must be 1-12, got {self.layer_index}")

        if not 0.0 <= self.activation_level <= 1.0:
            raise ValueError(
                f"activation_level must be 0.0-1.0, got {self.activation_level}"
            )

        if not -1.0 <= self.momentum <= 1.0:
            raise ValueError(f"momentum must be -1.0 to 1.0, got {self.momentum}")

        if self.distortion_load < 0.0:
            raise ValueError(
                f"distortion_load must be non-negative, got {self.distortion_load}"
            )

        if self.sublimation_load < 0.0:
            raise ValueError(
                f"sublimation_load must be non-negative, got {self.sublimation_load}"
            )

    def to_dict(self) -> dict:
        """Convert to plain dict for serialization."""
        return {
            "time_step": self.time_step,
            "layer_id": self.layer_id,
            "layer_index": self.layer_index,
            "activation_level": self.activation_level,
            "momentum": self.momentum,
            "direction": self.direction.value,
            "distortion_load": self.distortion_load,
            "sublimation_load": self.sublimation_load,
            "termination_flag": self.termination_flag,
            "regression_flag": self.regression_flag,
        }


@dataclass(frozen=True)
class DynamicsConfig:
    """
    Configuration for a dynamics resolution run.

    All parameters affect dynamic behavior, NOT ontology interpretation.

    Attributes:
        load: External load factor (0.0 to 1.0). Higher = more stress.
        time_steps: Number of discrete time steps to simulate.
        decay_constant: Rate of momentum decay per step (0.0 to 1.0).
        amplification_factor: Multiplier for momentum accumulation (0.5 to 2.0).
        allow_regression: If True, high load enables downward traversal.
        regression_threshold: Load level above which regression is possible.
        saturation_threshold: Momentum level at which saturation occurs.
        o8_damping_factor: How much O9_WITNESSES dampens momentum.
    """

    load: float
    time_steps: int
    decay_constant: float
    amplification_factor: float
    allow_regression: bool
    regression_threshold: float = 0.7
    saturation_threshold: float = 0.9
    o8_damping_factor: float = 0.5

    def __post_init__(self) -> None:
        """Validate configuration bounds."""
        if not 0.0 <= self.load <= 1.0:
            raise ValueError(f"load must be 0.0-1.0, got {self.load}")

        if not isinstance(self.time_steps, int) or self.time_steps < 1:
            raise ValueError(f"time_steps must be positive int, got {self.time_steps}")

        if not 0.0 <= self.decay_constant <= 1.0:
            raise ValueError(
                f"decay_constant must be 0.0-1.0, got {self.decay_constant}"
            )

        if not 0.5 <= self.amplification_factor <= 2.0:
            raise ValueError(
                f"amplification_factor must be 0.5-2.0, got {self.amplification_factor}"
            )

        if not 0.0 <= self.regression_threshold <= 1.0:
            raise ValueError(
                f"regression_threshold must be 0.0-1.0, got {self.regression_threshold}"
            )

        if not 0.0 <= self.saturation_threshold <= 1.0:
            raise ValueError(
                f"saturation_threshold must be 0.0-1.0, got {self.saturation_threshold}"
            )

        if not 0.0 <= self.o8_damping_factor <= 1.0:
            raise ValueError(
                f"o8_damping_factor must be 0.0-1.0, got {self.o8_damping_factor}"
            )


@dataclass(frozen=True)
class TrajectoryResult:
    """
    Complete result of a dynamics resolution.

    Contains the full trajectory plus summary statistics.

    Attributes:
        varna: Input varna token
        start_layer: Starting layer ID
        config: The DynamicsConfig used
        trajectory: Tuple of DynamicState objects (one per time step)
        final_layer: Ending layer ID
        peak_activation: Maximum activation reached
        peak_momentum: Maximum absolute momentum reached
        total_distortion: Sum of distortion loads
        total_sublimation: Sum of sublimation loads
        terminated: True if O12 termination occurred
        regressed: True if any downward regression occurred
        layers_visited: Set of layer IDs visited during trajectory
    """

    varna: str
    start_layer: str
    config: DynamicsConfig
    trajectory: Tuple[DynamicState, ...]
    final_layer: str
    peak_activation: float
    peak_momentum: float
    total_distortion: float
    total_sublimation: float
    terminated: bool
    regressed: bool
    layers_visited: Tuple[str, ...]

    def is_flat(self, threshold: float = 0.1) -> bool:
        """
        Check if trajectory shows minimal variation.

        A trajectory is "flat" if activation and momentum vary little.
        This helps identify when ontology flatness persists under dynamics.

        Args:
            threshold: Maximum variance to consider flat

        Returns:
            True if trajectory is flat
        """
        if len(self.trajectory) < 2:
            return True

        activations = [s.activation_level for s in self.trajectory]
        momenta = [s.momentum for s in self.trajectory]

        activation_range = max(activations) - min(activations)
        momentum_range = max(momenta) - min(momenta)

        return activation_range < threshold and momentum_range < threshold

    def to_dict(self) -> dict:
        """Convert to plain dict for serialization."""
        return {
            "varna": self.varna,
            "start_layer": self.start_layer,
            "config": {
                "load": self.config.load,
                "time_steps": self.config.time_steps,
                "decay_constant": self.config.decay_constant,
                "amplification_factor": self.config.amplification_factor,
                "allow_regression": self.config.allow_regression,
            },
            "trajectory": [s.to_dict() for s in self.trajectory],
            "final_layer": self.final_layer,
            "peak_activation": self.peak_activation,
            "peak_momentum": self.peak_momentum,
            "total_distortion": self.total_distortion,
            "total_sublimation": self.total_sublimation,
            "terminated": self.terminated,
            "regressed": self.regressed,
            "layers_visited": list(self.layers_visited),
        }


# =============================================================================
# Layer Ordering (Constant Reference)
# =============================================================================

LAYER_ORDER: Tuple[str, ...] = (
    "O1_POTENTIAL",
    "O2_IDENTITY",
    "O3_EXECUTION",
    "O4_STRUCTURE",
    "O5_COGNITION",
    "O6_AGENCY",
    "O7_REASONING",
    "O8_PURPOSE",
    "O9_WITNESSES",
    "O10_UNIFYING",
    "O11_INTEGRATION",
    "O12_ABSOLVING",
)

LAYER_TO_INDEX: dict = {layer: i + 1 for i, layer in enumerate(LAYER_ORDER)}
INDEX_TO_LAYER: dict = {i + 1: layer for i, layer in enumerate(LAYER_ORDER)}


def get_layer_index(layer_id: str) -> int:
    """Get numeric index (1-12) for a layer ID."""
    return LAYER_TO_INDEX.get(layer_id, 0)


def get_layer_by_index(index: int) -> Optional[str]:
    """Get layer ID for numeric index (1-12)."""
    return INDEX_TO_LAYER.get(index)
