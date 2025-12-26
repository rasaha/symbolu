"""
Learning System for Robotics
============================

Provides learning capabilities for continuous improvement of robot behavior.

Modules:
    - skill_learning: RL-based skill refinement from experience
    - dynamics_model: Learned dynamics for prediction and planning
    - calibration: Online sensor and actuator calibration
    - transfer: Sim2real transfer learning

Integration with Symbolu:
    - Uses 12D Layer as state representation
    - SCC (S1-S9) provides learning signal quality metrics
    - BCVF (B1-B3) action selection integrates learned policies
    - USE (U1-U4) coherence informs learning confidence

Design Principle:
    Learning is optional enhancement, not required for basic operation.
    All tiers function with default behaviors; learning improves them.
"""

from symbolu_robotics.learning.skill_learning import (
    SkillLearner,
    SkillConfig,
    Experience,
    LearnedSkill,
)
from symbolu_robotics.learning.dynamics_model import (
    DynamicsModel,
    DynamicsConfig,
    Prediction,
)
from symbolu_robotics.learning.calibration import (
    OnlineCalibrator,
    CalibrationConfig,
    CalibrationState,
)
from symbolu_robotics.learning.transfer import (
    SimToRealAdapter,
    TransferConfig,
    DomainGap,
)

__all__ = [
    # Skill Learning
    "SkillLearner",
    "SkillConfig",
    "Experience",
    "LearnedSkill",
    # Dynamics Model
    "DynamicsModel",
    "DynamicsConfig",
    "Prediction",
    # Calibration
    "OnlineCalibrator",
    "CalibrationConfig",
    "CalibrationState",
    # Transfer
    "SimToRealAdapter",
    "TransferConfig",
    "DomainGap",
]
