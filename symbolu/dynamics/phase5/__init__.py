"""
Phase-5 Dynamic Resolution Layer
=================================

Phase-5 introduces dynamic behavior to distinguish:
    - True ontology defects
    - Flatness caused by static inspection
    - Intentional modeling boundaries

CRITICAL INVARIANTS:
    - NO_ONTOLOGY_WRITE: Never modifies ontology files
    - NO_ONTOLOGY_INFERENCE: Never invents meanings
    - NO_POLARITY_REINTERPRETATION: Never changes polarity labels
    - NO_SMOOTHING_FLATNESS: Never artificially smooths flat gradients

Phase-5 exists BEFORE ontology revision to falsify misattributed criticism.
Downward movement in Phase-5 is NOT reverse sublimation in the ontology.

Usage:
    from symbolu.dynamics.phase5 import resolve_dynamics, DynamicState

    trajectory = resolve_dynamics(
        varna="ka",
        start_layer="O1_ACTING",
        load=0.5,
        time_steps=10,
        decay_constant=0.1,
        amplification_factor=1.2,
        allow_regression=True,
    )
"""

from symbolu.dynamics.phase5.models import (
    DynamicState,
    DynamicsConfig,
    TrajectoryResult,
    Direction,
)
from symbolu.dynamics.phase5.phase5_dynamics_engine import resolve_dynamics
from symbolu.dynamics.phase5.errors import (
    Phase5Error,
    Phase5InvariantViolation,
    Phase5InvalidVarnaError,
    Phase5InvalidLayerError,
    Phase5InvalidConfigError,
)

__all__ = [
    # Core API
    "resolve_dynamics",
    # Models
    "DynamicState",
    "DynamicsConfig",
    "TrajectoryResult",
    "Direction",
    # Errors
    "Phase5Error",
    "Phase5InvariantViolation",
    "Phase5InvalidVarnaError",
    "Phase5InvalidLayerError",
    "Phase5InvalidConfigError",
]
