#!/usr/bin/env python3
# Symbolu Robotics - Pick and Place Example
"""
Demonstrates a complete pick-and-place task using the three-tier architecture.

This example shows:
- Goal setting and planning in the deliberative tier
- Reactive behavior for approach and grasp
- Reflexive safety during execution
- Sensor-to-12D encoding and 12D-to-actuator decoding
"""

import numpy as np
import time
from dataclasses import dataclass
from typing import Optional, List

from symbolu_robotics.core.types import (
    OntologicalLayer, SafetyLevel, SensorFrame, ActuatorCommand,
    Goal, Plan, JointState
)
from symbolu_robotics.encoders.fusion_encoder import FusionEncoder, FusionConfig
from symbolu_robotics.decoders.motor_decoder import MotorDecoder, MotorConfig
from symbolu_robotics.decoders.gripper_decoder import GripperDecoder, GripperConfig
from symbolu_robotics.safety.constraint_monitor import ConstraintMonitor, SafetyConfig
from symbolu_robotics.tiers.factory import TierCascade, TierLevel
from symbolu_robotics.planning.goal_stack import GoalStack
from symbolu_robotics.planning.world_model import WorldModel
from symbolu_robotics.state.robot_state import RobotStateEstimator


@dataclass
class PickPlaceConfig:
    """Configuration for pick and place task."""
    num_joints: int = 6
    control_rate_hz: float = 100.0
    approach_height: float = 0.1
    grasp_height: float = 0.02
    place_height: float = 0.1
    gripper_open: float = 0.08
    gripper_closed: float = 0.02


class PickAndPlaceDemo:
    """Demonstrates pick and place using the three-tier architecture."""

    def __init__(self, config: Optional[PickPlaceConfig] = None):
        self.config = config or PickPlaceConfig()

        # Initialize tier cascade
        self.cascade = TierCascade(num_joints=self.config.num_joints)

        # Initialize encoders/decoders
        self.encoder = FusionEncoder(FusionConfig(
            enable_vision=True,
            enable_proprioception=True,
            enable_tactile=True
        ))
        self.motor_decoder = MotorDecoder(MotorConfig(
            num_joints=self.config.num_joints,
            max_velocity=2.0,
            max_effort=100.0
        ))
        self.gripper_decoder = GripperDecoder(GripperConfig(
            min_position=0.0,
            max_position=0.08,
            max_force=40.0
        ))

        # Initialize safety
        self.safety = ConstraintMonitor(SafetyConfig(
            max_joint_velocity=2.0,
            max_joint_acceleration=10.0,
            max_joint_effort=100.0
        ))

        # State tracking
        self.robot_state = RobotStateEstimator(num_joints=self.config.num_joints)
        self.world_model = WorldModel(grid_resolution=0.1)

        # Task state
        self.current_phase = "idle"
        self.target_object_id: Optional[str] = None
        self.place_position: Optional[np.ndarray] = None

    def add_object(self, object_id: str, position: np.ndarray, size: np.ndarray):
        """Add an object to the world model."""
        self.world_model.add_object(
            id=object_id,
            position=position,
            size=size
        )
        print(f"Added object '{object_id}' at position {position}")

    def set_pick_place_task(
        self,
        object_id: str,
        place_position: np.ndarray
    ):
        """Set up a pick and place task."""
        self.target_object_id = object_id
        self.place_position = place_position

        # Get object position
        obj = self.world_model.get_object(object_id)
        if obj is None:
            raise ValueError(f"Object '{object_id}' not found")

        # Create goal sequence
        pick_goal = Goal(
            id=f"pick_{object_id}",
            type="pick",
            target_position=obj.position,
            object_id=object_id,
            priority=1.0
        )

        place_goal = Goal(
            id=f"place_{object_id}",
            type="place",
            target_position=place_position,
            object_id=object_id,
            priority=0.9
        )

        # Push goals (place first since it's a stack)
        self.cascade.deliberative.goal_stack.push(place_goal)
        self.cascade.deliberative.goal_stack.push(pick_goal)

        self.current_phase = "approach"
        print(f"Task set: Pick '{object_id}' and place at {place_position}")

    def _simulate_sensors(self, step: int) -> SensorFrame:
        """Simulate sensor readings (replace with real sensors in deployment)."""
        # Simulated joint positions (moving toward target)
        t = step * 0.01
        joint_positions = np.array([
            0.1 * np.sin(t),
            0.5 + 0.1 * np.cos(t),
            -0.3 + 0.05 * np.sin(t * 2),
            0.0,
            0.2 + 0.05 * np.cos(t),
            0.0
        ])

        # Simulated vision (object detection would go here)
        vision = np.random.randint(50, 200, (48, 64, 3), dtype=np.uint8)

        # Simulated tactile (contact detection)
        tactile = np.zeros(16)
        if self.current_phase == "grasp":
            tactile = np.ones(16) * 30  # Contact detected

        # Proximity sensors (clear)
        proximity = np.ones(8) * 0.5

        return SensorFrame(
            timestamp=time.time(),
            vision=vision,
            joint_positions=joint_positions,
            joint_velocities=np.random.randn(6) * 0.1,
            joint_efforts=np.random.randn(6) * 10 + 20,
            tactile=tactile,
            proximity_sensors=proximity
        )

    def step(self, sensor_frame: Optional[SensorFrame] = None) -> ActuatorCommand:
        """Execute one control step."""
        if sensor_frame is None:
            sensor_frame = self._simulate_sensors(0)

        # Update state estimate
        self.robot_state.update(sensor_frame)

        # Process through tier cascade
        raw_command = self.cascade.process(sensor_frame)

        # Apply safety constraints
        safe_command = self.safety.apply_safety(raw_command)

        # Get active tier for logging
        active_tier = self.cascade.get_active_tier()

        # Update phase based on progress
        self._update_phase()

        return safe_command

    def _update_phase(self):
        """Update task phase based on progress."""
        # This would be replaced with actual progress tracking
        goal_stack = self.cascade.deliberative.goal_stack

        if goal_stack.is_empty():
            self.current_phase = "complete"
        elif self.current_phase == "approach":
            # Check if at approach position
            pass  # Transition logic here

    def run_simulation(self, max_steps: int = 500):
        """Run a simulated pick and place task."""
        print("\n=== Starting Pick and Place Simulation ===\n")

        for step in range(max_steps):
            sensor_frame = self._simulate_sensors(step)
            command = self.step(sensor_frame)

            # Log every 50 steps
            if step % 50 == 0:
                active_tier = self.cascade.get_active_tier()
                print(f"Step {step:4d} | Phase: {self.current_phase:10s} | "
                      f"Active: {active_tier.name:12s} | "
                      f"Safety: {self.safety.safety_level.name}")

            # Check completion
            if self.current_phase == "complete":
                print(f"\n✓ Task completed at step {step}")
                break

            # Simulate control rate
            time.sleep(1.0 / self.config.control_rate_hz / 100)  # Faster for simulation

        print("\n=== Simulation Complete ===\n")


def main():
    """Run the pick and place demo."""
    print("Symbolu Robotics - Pick and Place Demo")
    print("=" * 50)

    # Create demo instance
    demo = PickAndPlaceDemo(PickPlaceConfig(
        num_joints=6,
        control_rate_hz=100.0
    ))

    # Add objects to world
    demo.add_object(
        object_id="red_cube",
        position=np.array([0.4, 0.0, 0.025]),
        size=np.array([0.05, 0.05, 0.05])
    )
    demo.add_object(
        object_id="blue_cube",
        position=np.array([0.4, 0.2, 0.025]),
        size=np.array([0.05, 0.05, 0.05])
    )

    # Set task
    demo.set_pick_place_task(
        object_id="red_cube",
        place_position=np.array([0.3, -0.2, 0.025])
    )

    # Run simulation
    demo.run_simulation(max_steps=300)

    # Report final state
    print("Final robot state:")
    state = demo.robot_state.get_state()
    if state:
        print(f"  Position: {state.joint_positions}")
        print(f"  Safety level: {demo.safety.safety_level.name}")


if __name__ == "__main__":
    main()
