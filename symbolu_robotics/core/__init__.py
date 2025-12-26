"""
Symbolu Robotics Core
=====================

Core ontological modules adapted for robotics applications.
Contains the 12D backbone, mirror pairs, and state management.
"""

from symbolu_robotics.core.types import (
    SensorFrame,
    ActuatorCommand,
    RobotPose,
    JointState,
    Layer12D,
    OntologicalLayer,
    SafetyLevel,
)
from symbolu_robotics.core.ontology_12d import (
    LAYER_NAMES,
    LAYER_INDICES,
    layer_to_index,
    index_to_layer,
    create_layer_vector,
    normalize_layer_vector,
)
from symbolu_robotics.core.mirror_pairs_12d import (
    MirrorPair12D,
    MIRROR_MAP_12D,
    MIRROR_INDEX_MAP,
    get_mirror_layer,
    get_mirror_index,
    MirrorBalance12D,
    compute_balance_12d,
    propagate_to_mirror_12d,
)
from symbolu_robotics.core.chitta_vritti import (
    VrittiMode,
    compute_vritti,
    get_dominant_vritti,
)
from symbolu_robotics.core.v27_state import (
    EMAConfig,
    EMAState,
    update_ema_state,
)

__all__ = [
    # Types
    "SensorFrame",
    "ActuatorCommand",
    "RobotPose",
    "JointState",
    "Layer12D",
    "OntologicalLayer",
    "SafetyLevel",
    # Ontology
    "LAYER_NAMES",
    "LAYER_INDICES",
    "layer_to_index",
    "index_to_layer",
    "create_layer_vector",
    "normalize_layer_vector",
    # Mirror pairs
    "MirrorPair12D",
    "MIRROR_MAP_12D",
    "MIRROR_INDEX_MAP",
    "get_mirror_layer",
    "get_mirror_index",
    "MirrorBalance12D",
    "compute_balance_12d",
    "propagate_to_mirror_12d",
    # Vritti
    "VrittiMode",
    "compute_vritti",
    "get_dominant_vritti",
    # State
    "EMAConfig",
    "EMAState",
    "update_ema_state",
]
