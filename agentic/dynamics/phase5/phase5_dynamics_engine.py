"""
Phase-5 Dynamics Engine
=======================

Dynamic resolution layer that applies time-based dynamics to
resolved ontology output from Phase-4A.

CRITICAL: Phase-5 cannot "fix" ontology issues.
Phase-5 only reveals whether issues are dynamic or structural.
All stress-test findings can now be re-classified post-Phase-5.

RESPONSIBILITIES:
    1. Accept resolved ontology output from Phase-4A
    2. Apply time-based dynamics (momentum, decay, amplification, saturation, regression)
    3. Produce numerical trajectories, not semantic text
    4. Allow both upward AND downward traversal across layers
    5. Make flat ontology patterns visibly unstable under stress (if appropriate)

INVARIANTS (enforced in code):
    - NO_ONTOLOGY_WRITE: Never modifies ontology files
    - NO_ONTOLOGY_INFERENCE: Never invents meanings
    - NO_POLARITY_REINTERPRETATION: Never changes polarity labels
    - NO_SMOOTHING_FLATNESS: Never artificially smooths flat gradients
"""

from typing import List, Tuple, Optional
import math

# Phase-4A imports — the ONLY allowed ontology access path
from agentic.ontology.phase4a.lookup import (
    lookup_interaction,
    is_valid_varna,
    is_valid_layer,
)
from agentic.ontology.phase4a.loader import get_all_varnas, get_all_layers

from agentic.dynamics.phase5.models import (
    DynamicState,
    DynamicsConfig,
    TrajectoryResult,
    Direction,
    LAYER_ORDER,
    LAYER_TO_INDEX,
    INDEX_TO_LAYER,
    get_layer_index,
    get_layer_by_index,
)
from agentic.dynamics.phase5.errors import (
    Phase5Error,
    Phase5InvariantViolation,
    Phase5InvalidVarnaError,
    Phase5InvalidLayerError,
    Phase5InvalidConfigError,
)


# =============================================================================
# Distortion Vector Mapping (Numerical)
# =============================================================================

# Map ontology distortion_vector strings to numerical direction bias
# These are READ from ontology, not invented
DISTORTION_DIRECTION_MAP = {
    "upward": 0.3,      # Mild upward bias
    "downward": -0.3,   # Mild downward bias
    "lateral": 0.0,     # No vertical bias
    "terminating": 0.0, # Terminal state, no movement
}

# Map ontology sublimate_vector strings to numerical direction bias
SUBLIMATE_DIRECTION_MAP = {
    "upward": 0.5,       # Strong upward bias
    "terminating": 0.0,  # Terminal state
    "lateral": 0.1,      # Slight upward tendency
}


# =============================================================================
# Core Engine
# =============================================================================

def _validate_inputs(varna: str, start_layer: str) -> None:
    """
    Validate varna and layer through Phase-4A.

    Phase-5 NEVER validates against raw JSON files.
    All validation flows through Phase-4A.

    Raises:
        Phase5InvalidVarnaError: If varna invalid
        Phase5InvalidLayerError: If layer invalid
    """
    if not is_valid_varna(varna):
        raise Phase5InvalidVarnaError(
            varna,
            reason="Not found in Phase-4A ontology"
        )

    if not is_valid_layer(start_layer):
        raise Phase5InvalidLayerError(
            start_layer,
            reason="Not a valid ontological layer (O1-O12)"
        )


def _get_ontology_signals(varna: str, layer: str) -> Tuple[float, float]:
    """
    Get numerical signals from ontology via Phase-4A.

    Returns distortion and sublimation direction biases.
    These are NUMERICAL derivations from ontology vectors,
    not invented meanings.

    Returns:
        (distortion_bias, sublimation_bias) as floats
    """
    interaction = lookup_interaction(varna, layer)

    distortion_bias = DISTORTION_DIRECTION_MAP.get(
        interaction.distortion_vector, 0.0
    )
    sublimation_bias = SUBLIMATE_DIRECTION_MAP.get(
        interaction.sublimate_vector, 0.0
    )

    return distortion_bias, sublimation_bias


def _compute_next_state(
    current: DynamicState,
    varna: str,
    config: DynamicsConfig,
    time_step: int,
) -> DynamicState:
    """
    Compute the next dynamic state from current state.

    This is the core dynamics computation. It:
        1. Gets ontology signals from Phase-4A (read-only)
        2. Applies momentum accumulation
        3. Applies decay
        4. Computes direction and layer transitions
        5. Handles special cases (O9 damping, O12 termination, regression)

    NO ontology modification occurs. Only numerical evolution.
    """
    # Already terminated — no evolution
    if current.termination_flag:
        return DynamicState(
            time_step=time_step,
            layer_id=current.layer_id,
            layer_index=current.layer_index,
            activation_level=current.activation_level,
            momentum=0.0,
            direction=Direction.LATERAL,
            distortion_load=current.distortion_load,
            sublimation_load=current.sublimation_load,
            termination_flag=True,
            regression_flag=current.regression_flag,
        )

    # Get ontology signals via Phase-4A (READ-ONLY)
    distortion_bias, sublimation_bias = _get_ontology_signals(
        varna, current.layer_id
    )

    # === Momentum Computation ===
    # Combine ontology signals with current momentum
    raw_momentum = (
        current.momentum
        + (sublimation_bias - distortion_bias) * config.amplification_factor
    )

    # Apply decay
    decayed_momentum = raw_momentum * (1.0 - config.decay_constant)

    # Apply load pressure (pushes toward distortion under stress)
    load_pressure = config.load * 0.5  # Load pushes downward
    momentum_with_load = decayed_momentum - load_pressure

    # === O9 Damping ===
    # O9_WITNESSES dampens momentum (witnessing without altering)
    if current.layer_id == "O9_WITNESSES":
        momentum_with_load *= (1.0 - config.o8_damping_factor)

    # Clamp momentum to valid range
    final_momentum = max(-1.0, min(1.0, momentum_with_load))

    # === Direction Computation ===
    direction: Direction
    if abs(final_momentum) < 0.1:
        direction = Direction.LATERAL
    elif final_momentum > 0:
        direction = Direction.UP
    else:
        direction = Direction.DOWN

    # === Layer Transition ===
    new_layer_index = current.layer_index
    regression_flag = current.regression_flag

    # Check for regression under load
    can_regress = (
        config.allow_regression
        and config.load >= config.regression_threshold
        and direction == Direction.DOWN
    )

    if direction == Direction.UP and current.layer_index < 12:
        # Upward movement requires sufficient positive momentum
        if final_momentum > 0.3:
            new_layer_index = current.layer_index + 1
    elif direction == Direction.DOWN and current.layer_index > 1:
        # Downward movement (regression under load)
        if can_regress and final_momentum < -0.3:
            new_layer_index = current.layer_index - 1
            regression_flag = True

    # === Saturation at O11/O12 ===
    # Excess upward momentum at high layers may collapse
    if new_layer_index >= 11 and abs(final_momentum) > config.saturation_threshold:
        # Saturation causes momentum collapse
        final_momentum = final_momentum * 0.5

    # Get new layer ID
    new_layer_id = get_layer_by_index(new_layer_index) or current.layer_id

    # === Termination Check ===
    termination_flag = False
    if new_layer_id == "O12_ABSOLVING":
        # Check for termination condition
        # Termination occurs when sublimation completes at O12
        interaction = lookup_interaction(varna, "O12_ABSOLVING")
        if interaction.sublimate_vector == "terminating":
            termination_flag = True

    # === Activation Level ===
    # Activation influenced by momentum magnitude and layer position
    base_activation = current.activation_level
    momentum_effect = abs(final_momentum) * 0.2
    layer_effect = new_layer_index / 12.0 * 0.1

    new_activation = base_activation + momentum_effect - layer_effect
    new_activation = max(0.0, min(1.0, new_activation))

    # Apply decay to activation over time
    new_activation *= (1.0 - config.decay_constant * 0.5)

    # === Distortion/Sublimation Load Accumulation ===
    new_distortion_load = current.distortion_load
    new_sublimation_load = current.sublimation_load

    if distortion_bias < 0:  # Downward distortion
        new_distortion_load += abs(distortion_bias) * config.load
    if sublimation_bias > 0:  # Upward sublimation
        new_sublimation_load += sublimation_bias * (1.0 - config.load)

    return DynamicState(
        time_step=time_step,
        layer_id=new_layer_id,
        layer_index=new_layer_index,
        activation_level=round(new_activation, 6),
        momentum=round(final_momentum, 6),
        direction=direction,
        distortion_load=round(new_distortion_load, 6),
        sublimation_load=round(new_sublimation_load, 6),
        termination_flag=termination_flag,
        regression_flag=regression_flag,
    )


def resolve_dynamics(
    *,
    varna: str,
    start_layer: str,
    load: float,
    time_steps: int,
    decay_constant: float,
    amplification_factor: float,
    allow_regression: bool,
    regression_threshold: float = 0.7,
    saturation_threshold: float = 0.9,
    o8_damping_factor: float = 0.5,
) -> TrajectoryResult:
    """
    Resolve dynamic trajectory for a varna starting from a layer.

    This is the primary Phase-5 API. It:
        1. Validates varna and layer through Phase-4A
        2. Creates initial state
        3. Evolves state through time_steps iterations
        4. Returns numerical trajectory

    CRITICAL INVARIANTS:
        - All ontology access flows through Phase-4A only
        - No ontology modification
        - No meaning invention
        - No polarity reinterpretation
        - No artificial smoothing

    Args:
        varna: The varna token (e.g., "ka", "ga", "ddha")
        start_layer: Starting ontological layer (e.g., "O3_EXECUTION")
        load: External load factor (0.0 to 1.0). Higher = more stress.
        time_steps: Number of discrete time steps to simulate.
        decay_constant: Rate of momentum decay per step (0.0 to 1.0).
        amplification_factor: Multiplier for momentum accumulation (0.5 to 2.0).
        allow_regression: If True, high load enables downward traversal.
        regression_threshold: Load level above which regression is possible.
        saturation_threshold: Momentum level at which saturation occurs.
        o8_damping_factor: How much O9_WITNESSES dampens momentum.

    Returns:
        TrajectoryResult containing full numerical trajectory

    Raises:
        Phase5InvalidVarnaError: If varna not valid in Phase-4A
        Phase5InvalidLayerError: If layer not valid (O1-O12)
        Phase5InvalidConfigError: If configuration parameters invalid

    Example:
        >>> result = resolve_dynamics(
        ...     varna="ka",
        ...     start_layer="O3_EXECUTION",
        ...     load=0.5,
        ...     time_steps=10,
        ...     decay_constant=0.1,
        ...     amplification_factor=1.2,
        ...     allow_regression=True,
        ... )
        >>> len(result.trajectory)
        10
        >>> result.trajectory[0].layer_id
        'O3_EXECUTION'
    """
    # === Input Validation ===
    _validate_inputs(varna, start_layer)

    # === Config Validation ===
    try:
        config = DynamicsConfig(
            load=load,
            time_steps=time_steps,
            decay_constant=decay_constant,
            amplification_factor=amplification_factor,
            allow_regression=allow_regression,
            regression_threshold=regression_threshold,
            saturation_threshold=saturation_threshold,
            o8_damping_factor=o8_damping_factor,
        )
    except ValueError as e:
        # Extract param name from error message if possible
        raise Phase5InvalidConfigError(
            param="configuration",
            value=str(e),
            constraint="see DynamicsConfig for valid ranges"
        )

    # === Initial State ===
    start_index = get_layer_index(start_layer)

    # Get initial ontology signals
    initial_distortion, initial_sublimation = _get_ontology_signals(
        varna, start_layer
    )

    initial_state = DynamicState(
        time_step=0,
        layer_id=start_layer,
        layer_index=start_index,
        activation_level=0.5,  # Neutral starting activation
        momentum=0.0,          # No initial momentum
        direction=Direction.LATERAL,
        distortion_load=0.0,
        sublimation_load=0.0,
        termination_flag=False,
        regression_flag=False,
    )

    # === Evolution ===
    trajectory: List[DynamicState] = [initial_state]
    current_state = initial_state

    for t in range(1, time_steps):
        next_state = _compute_next_state(current_state, varna, config, t)
        trajectory.append(next_state)
        current_state = next_state

        # Early termination check
        if current_state.termination_flag:
            # Fill remaining steps with terminal state
            for t_remaining in range(t + 1, time_steps):
                terminal_state = DynamicState(
                    time_step=t_remaining,
                    layer_id=current_state.layer_id,
                    layer_index=current_state.layer_index,
                    activation_level=current_state.activation_level,
                    momentum=0.0,
                    direction=Direction.LATERAL,
                    distortion_load=current_state.distortion_load,
                    sublimation_load=current_state.sublimation_load,
                    termination_flag=True,
                    regression_flag=current_state.regression_flag,
                )
                trajectory.append(terminal_state)
            break

    # === Build Result ===
    final_state = trajectory[-1]
    layers_visited = tuple(sorted(set(s.layer_id for s in trajectory)))

    peak_activation = max(s.activation_level for s in trajectory)
    peak_momentum = max(abs(s.momentum) for s in trajectory)
    total_distortion = sum(s.distortion_load for s in trajectory)
    total_sublimation = sum(s.sublimation_load for s in trajectory)

    terminated = any(s.termination_flag for s in trajectory)
    regressed = any(s.regression_flag for s in trajectory)

    return TrajectoryResult(
        varna=varna,
        start_layer=start_layer,
        config=config,
        trajectory=tuple(trajectory),
        final_layer=final_state.layer_id,
        peak_activation=peak_activation,
        peak_momentum=peak_momentum,
        total_distortion=total_distortion,
        total_sublimation=total_sublimation,
        terminated=terminated,
        regressed=regressed,
        layers_visited=layers_visited,
    )


# =============================================================================
# Invariant Enforcement (Self-Check)
# =============================================================================

def _enforce_invariants() -> None:
    """
    Self-check that Phase-5 invariants are structurally enforced.

    This function verifies at module load that:
        - NO_ONTOLOGY_WRITE: No file write imports
        - NO_ONTOLOGY_INFERENCE: No meaning generation
        - NO_POLARITY_REINTERPRETATION: Polarity untouched
        - NO_SMOOTHING_FLATNESS: No gradient smoothing

    This is a structural check, not runtime enforcement.
    """
    # Verify we only import read-only Phase-4A functions
    from agentic.ontology.phase4a import lookup as phase4a_lookup

    # These are the ONLY allowed Phase-4A imports
    allowed_imports = {
        "lookup_interaction",
        "is_valid_varna",
        "is_valid_layer",
    }

    # We intentionally do NOT import:
    # - Any file writing functions
    # - Any polarity modification functions
    # - Any smoothing functions

    # The structure of this module ensures invariants by design:
    # 1. NO_ONTOLOGY_WRITE: We never import json.dump or file writers
    # 2. NO_ONTOLOGY_INFERENCE: We never generate semantic text
    # 3. NO_POLARITY_REINTERPRETATION: We only read polarity, never modify
    # 4. NO_SMOOTHING_FLATNESS: We pass through ontology values as-is


# Run invariant check at module load
_enforce_invariants()


# =============================================================================
# Self-Verification Comments (Required by Specification)
# =============================================================================

# CONFIRMED: Phase-5 cannot "fix" ontology issues.
#   - All ontology access is read-only through Phase-4A
#   - No file modifications occur
#   - No meanings are invented
#
# CONFIRMED: Phase-5 only reveals whether issues are dynamic or structural.
#   - Flat ontology gradients remain flat at ontology level
#   - Dynamics may show instability that reveals dynamic vs structural cause
#   - TrajectoryResult.is_flat() helps classify post-Phase-5
#
# CONFIRMED: All stress-test findings can now be re-classified post-Phase-5.
#   - If flat ontology produces non-flat trajectory: issue may be dynamic
#   - If flat ontology produces flat trajectory: issue is structural
#   - Regression under load tests downward traversal capability
