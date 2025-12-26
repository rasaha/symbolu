"""
Symbolu Robotics Safety Module
==============================

Real-time safety layer implementing O12_ABSOLVING enforcement.

Safety Hierarchy:
- Layer 0: Hardware E-STOP (external)
- Layer 1: CollisionGuard (<1ms)
- Layer 2: ConstraintMonitor (<10ms)
- Layer 3: Safety Planning (deliberative)
- Layer 4: TrajectoryValidator (pre-execution)

Predictive Safety:
- Trajectory pre-validation before execution
- Predictive collision detection (look-ahead)
- Human proximity forecasting
- SCC coherence-based safety confidence
"""

from symbolu_robotics.safety.constraint_monitor import ConstraintMonitor, SafetyConfig
from symbolu_robotics.safety.collision_guard import CollisionGuard
from symbolu_robotics.safety.energy_bounds import EnergyBoundsMonitor
from symbolu_robotics.safety.human_proximity import HumanProximityMonitor
from symbolu_robotics.safety.trajectory_validator import (
    TrajectoryValidator,
    TrajectoryValidatorConfig,
    TrajectoryPoint,
    ValidationReport,
    ValidationResult,
    CollisionPrediction,
    CollisionType,
    PredictiveSafetyMonitor,
    JointLimits,
    WorkspaceBounds,
)

__all__ = [
    # Core safety
    "ConstraintMonitor",
    "SafetyConfig",
    "CollisionGuard",
    "EnergyBoundsMonitor",
    "HumanProximityMonitor",
    # Trajectory validation
    "TrajectoryValidator",
    "TrajectoryValidatorConfig",
    "TrajectoryPoint",
    "ValidationReport",
    "ValidationResult",
    "CollisionPrediction",
    "CollisionType",
    "PredictiveSafetyMonitor",
    "JointLimits",
    "WorkspaceBounds",
]
