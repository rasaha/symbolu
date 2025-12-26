"""
Symbolu Robotics & Autonomous AI Module
========================================

Adapts the Symbolu ontological engine for autonomous AI systems including
robotics, drones, and autonomous vehicles.

Key Principle:
    Ontology-First, Compute-Light - Use the deterministic 12D STL for
    real-time control loops, reserving expensive inference for deliberative
    planning only.

Tier Architecture:
    - Tier R1 (Reflexive): STL-only, <1ms latency, safety-critical
    - Tier R2 (Reactive): STL + edge model, <10ms latency, behavioral
    - Tier R3 (Deliberative): Full planning + inference, <100ms latency

Modules:
    - core: 12D ontological backbone adapted for robotics
    - encoders: Sensor → 12D encoding (vision, proprioception, tactile, audio)
    - decoders: 12D → Actuator commands (motor, gripper, locomotion)
    - safety: Real-time safety layer (collision guard, constraints)
    - tiers: Reflexive, Reactive, Deliberative control tiers
    - planning: Task and motion planning
    - state: Robot state estimation and world modeling
    - comms: Multi-agent coordination and human interface
    - adapters: Hardware abstraction (ROS2, Isaac, MuJoCo)

Version: 1.0.0
"""

__version__ = "1.0.0"
__author__ = "Symbolu Team"

# Core types
from symbolu_robotics.core.types import (
    SensorFrame,
    ActuatorCommand,
    RobotPose,
    JointState,
    Layer12D,
)

# Tiers
from symbolu_robotics.tiers.reflexive import ReflexiveTier
from symbolu_robotics.tiers.reactive import ReactiveTier
from symbolu_robotics.tiers.deliberative import DeliberativeTier
from symbolu_robotics.tiers.factory import create_tier, TierLevel

# Safety
from symbolu_robotics.safety.collision_guard import CollisionGuard
from symbolu_robotics.safety.constraint_monitor import ConstraintMonitor

__all__ = [
    # Version
    "__version__",
    # Types
    "SensorFrame",
    "ActuatorCommand",
    "RobotPose",
    "JointState",
    "Layer12D",
    # Tiers
    "ReflexiveTier",
    "ReactiveTier",
    "DeliberativeTier",
    "create_tier",
    "TierLevel",
    # Safety
    "CollisionGuard",
    "ConstraintMonitor",
]
