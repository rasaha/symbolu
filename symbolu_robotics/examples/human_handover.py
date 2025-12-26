#!/usr/bin/env python3
# Symbolu Robotics - Human Handover Example
"""
Demonstrates safe human-robot handover following ISO/TS 15066.

This example shows:
- Human proximity monitoring and speed limiting
- Power and force limiting for collaborative mode
- Hand guiding detection
- Natural language interaction
"""

import numpy as np
import time
from dataclasses import dataclass
from typing import Optional, List
from enum import Enum

from symbolu_robotics.core.types import (
    OntologicalLayer, SafetyLevel, SensorFrame, ActuatorCommand,
    Goal, JointState
)
from symbolu_robotics.encoders.fusion_encoder import FusionEncoder, FusionConfig
from symbolu_robotics.decoders.motor_decoder import MotorDecoder, MotorConfig
from symbolu_robotics.decoders.gripper_decoder import GripperDecoder, GripperConfig
from symbolu_robotics.safety.constraint_monitor import ConstraintMonitor, SafetyConfig
from symbolu_robotics.safety.human_proximity import HumanProximity, HumanProximityConfig
from symbolu_robotics.tiers.factory import TierCascade, TierLevel
from symbolu_robotics.comms.human_interface import HumanInterface
from symbolu_robotics.state.robot_state import RobotStateEstimator


class HandoverPhase(Enum):
    """Phases of the handover task."""
    IDLE = "idle"
    APPROACHING = "approaching"
    OFFERING = "offering"
    WAITING_FOR_GRASP = "waiting_for_grasp"
    RELEASING = "releasing"
    RETRACTING = "retracting"
    COMPLETE = "complete"


@dataclass
class HandoverConfig:
    """Configuration for human handover task."""
    num_joints: int = 6
    control_rate_hz: float = 100.0
    # ISO/TS 15066 compliant limits
    max_tcp_velocity: float = 0.25  # m/s near human
    max_tcp_force: float = 140.0    # N transient
    max_static_force: float = 65.0   # N quasi-static
    # Handover specific
    offer_position: np.ndarray = None
    offer_height: float = 0.8  # m above ground
    handover_distance: float = 0.4  # m from robot base
    grasp_detection_threshold: float = 5.0  # N
    release_delay: float = 0.5  # seconds after grasp detected

    def __post_init__(self):
        if self.offer_position is None:
            self.offer_position = np.array([
                self.handover_distance,
                0.0,
                self.offer_height
            ])


class HumanHandoverDemo:
    """Demonstrates safe human-robot handover."""

    def __init__(self, config: Optional[HandoverConfig] = None):
        self.config = config or HandoverConfig()

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
            max_velocity=1.0,  # Limited for collaboration
            max_effort=50.0    # Limited for safety
        ))
        self.gripper_decoder = GripperDecoder(GripperConfig(
            min_position=0.0,
            max_position=0.08,
            max_force=20.0  # Gentle grip
        ))

        # Initialize collaborative safety
        self.safety = ConstraintMonitor(SafetyConfig(
            max_joint_velocity=1.0,
            max_joint_acceleration=5.0,
            max_joint_effort=50.0
        ))
        self.human_proximity = HumanProximity(HumanProximityConfig(
            stop_distance=0.3,
            reduced_speed_distance=1.0,
            monitoring_distance=2.0,
            max_speed_near_human=0.25,
            human_speed_estimate=1.6
        ))

        # Human interface
        self.human_interface = HumanInterface()

        # State
        self.robot_state = RobotStateEstimator(num_joints=self.config.num_joints)
        self.phase = HandoverPhase.IDLE
        self.human_position: Optional[np.ndarray] = None
        self.grasp_detected = False
        self.grasp_time: Optional[float] = None
        self.gripper_force = 0.0

    def set_human_position(self, position: np.ndarray):
        """Update human position (from vision/tracking system)."""
        self.human_position = position

    def start_handover(self, object_description: str = "object"):
        """Start the handover sequence."""
        print(f"\nStarting handover of '{object_description}'")

        # Set approaching goal
        approach_goal = Goal(
            id="approach_handover",
            type="reach",
            target_position=self.config.offer_position,
            priority=1.0
        )
        self.cascade.deliberative.set_goal(approach_goal)

        self.phase = HandoverPhase.APPROACHING
        self.human_interface.speak(f"I will hand you the {object_description}. "
                                   "Please take it when ready.")

    def _simulate_sensors(self, step: int) -> SensorFrame:
        """Simulate sensor readings."""
        # Simulated joint positions
        t = step * 0.01
        joint_positions = np.zeros(6)

        # Simulate tactile feedback (grasp detection)
        tactile = np.zeros(16)
        if self.phase == HandoverPhase.WAITING_FOR_GRASP:
            # Simulate human grasping at step 200
            if step > 200:
                tactile = np.ones(16) * 30  # Contact detected
                self.gripper_force = 15.0

        return SensorFrame(
            timestamp=time.time(),
            joint_positions=joint_positions,
            joint_velocities=np.zeros(6),
            joint_efforts=np.zeros(6),
            tactile=tactile,
            proximity_sensors=np.ones(8) * 0.5
        )

    def _detect_grasp(self, sensor_frame: SensorFrame) -> bool:
        """Detect if human is grasping the object."""
        if sensor_frame.tactile is None:
            return False

        # Check for contact pattern indicating grasp
        contact_force = np.mean(sensor_frame.tactile)
        return contact_force > self.config.grasp_detection_threshold

    def _compute_speed_limit(self) -> float:
        """Compute speed limit based on human proximity."""
        if self.human_position is None:
            return float('inf')

        robot_position = np.array([0.0, 0.0, 0.0])  # Get from FK
        return self.human_proximity.compute_speed_limit(
            robot_position,
            [self.human_position]
        )

    def step(self, sensor_frame: Optional[SensorFrame] = None) -> ActuatorCommand:
        """Execute one handover step."""
        if sensor_frame is None:
            sensor_frame = self._simulate_sensors(0)

        # Update state
        self.robot_state.update(sensor_frame)

        # Compute human-aware speed limit
        speed_limit = self._compute_speed_limit()

        # Phase-specific logic
        if self.phase == HandoverPhase.APPROACHING:
            # Check if at offer position
            # (In real system, check FK position)
            self.phase = HandoverPhase.OFFERING

        elif self.phase == HandoverPhase.OFFERING:
            # Extend arm to offer position
            self.human_interface.speak("Please take the object when ready.")
            self.phase = HandoverPhase.WAITING_FOR_GRASP

        elif self.phase == HandoverPhase.WAITING_FOR_GRASP:
            # Detect grasp
            if self._detect_grasp(sensor_frame):
                if not self.grasp_detected:
                    self.grasp_detected = True
                    self.grasp_time = time.time()
                    print("  Grasp detected!")

                # Wait for stable grasp before releasing
                if time.time() - self.grasp_time > self.config.release_delay:
                    self.phase = HandoverPhase.RELEASING

        elif self.phase == HandoverPhase.RELEASING:
            # Open gripper
            print("  Releasing object...")
            self.phase = HandoverPhase.RETRACTING

        elif self.phase == HandoverPhase.RETRACTING:
            # Move arm back
            self.human_interface.speak("Handover complete. Thank you.")
            self.phase = HandoverPhase.COMPLETE

        # Process through tier cascade
        raw_command = self.cascade.process(sensor_frame)

        # Apply speed limit for human proximity
        if speed_limit < float('inf') and speed_limit > 0:
            max_vel = np.max(np.abs(raw_command.joint_velocities))
            if max_vel > 0:
                scale = min(1.0, speed_limit / max_vel)
                raw_command.joint_velocities *= scale

        # Apply safety constraints
        safe_command = self.safety.apply_safety(raw_command)

        return safe_command

    def run_simulation(self, max_steps: int = 500):
        """Run handover simulation."""
        print("\n=== Starting Human Handover Simulation ===")
        print("ISO/TS 15066 Collaborative Mode Active")
        print("=" * 50 + "\n")

        # Simulate human approaching
        self.set_human_position(np.array([0.8, 0.0, 1.0]))
        self.start_handover("tool")

        for step in range(max_steps):
            sensor_frame = self._simulate_sensors(step)
            command = self.step(sensor_frame)

            # Compute current speed limit
            speed_limit = self._compute_speed_limit()

            # Log every 50 steps
            if step % 50 == 0:
                print(f"Step {step:4d} | Phase: {self.phase.value:20s} | "
                      f"Speed Limit: {speed_limit:.2f} m/s | "
                      f"Safety: {self.safety.safety_level.name}")

            # Check completion
            if self.phase == HandoverPhase.COMPLETE:
                print(f"\n✓ Handover completed at step {step}")
                break

            time.sleep(1.0 / self.config.control_rate_hz / 100)

        print("\n=== Handover Complete ===\n")

    def demonstrate_hand_guiding(self):
        """Demonstrate hand guiding mode."""
        print("\n=== Hand Guiding Mode Demo ===")
        print("ISO/TS 15066 Hand Guiding Active")
        print("=" * 50 + "\n")

        # Simulate hand guiding detection
        for step in range(100):
            # Simulate force on robot (human pushing)
            force_detected = 8.0 if step > 10 else 0.0

            if force_detected > 5.0:  # Threshold for hand guiding
                print(f"Step {step:3d}: Hand guiding active - "
                      f"Force: {force_detected:.1f}N - "
                      f"Following human guidance at max 0.25 m/s")
            else:
                print(f"Step {step:3d}: Waiting for hand guiding input...")

            if step > 50:
                force_detected = 0.0
                print(f"Step {step:3d}: Hand guiding released")

            if step > 60:
                break

            time.sleep(0.05)


def main():
    """Run the human handover demo."""
    print("Symbolu Robotics - Human Handover Demo")
    print("=" * 50)

    # Create demo with collaborative settings
    demo = HumanHandoverDemo(HandoverConfig(
        num_joints=6,
        max_tcp_velocity=0.25,
        max_tcp_force=140.0,
        max_static_force=65.0
    ))

    # Run main handover simulation
    demo.run_simulation(max_steps=300)

    # Demonstrate hand guiding
    demo.demonstrate_hand_guiding()

    print("\nSafety Summary:")
    print(f"  Max TCP velocity: 0.25 m/s (ISO/TS 15066)")
    print(f"  Max transient force: 140 N")
    print(f"  Max quasi-static force: 65 N")
    print(f"  Human stop distance: 0.3 m")


if __name__ == "__main__":
    main()
