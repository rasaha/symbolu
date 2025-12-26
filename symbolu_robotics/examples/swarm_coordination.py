#!/usr/bin/env python3
# Symbolu Robotics - Swarm Coordination Example
"""
Demonstrates multi-robot swarm coordination using the 12D ontological framework.

This example shows:
- Multi-robot state sharing via O10_UNIFYING
- Distributed task allocation
- Formation control
- Consensus-based decision making
"""

import numpy as np
import time
from dataclasses import dataclass, field
from typing import Optional, List, Dict
from enum import Enum
import threading

from symbolu_robotics.core.types import (
    OntologicalLayer, SafetyLevel, SensorFrame, ActuatorCommand,
    Goal, RobotPose
)
from symbolu_robotics.core.ontology_12d import LAYER_NAMES
from symbolu_robotics.comms.swarm_protocol import SwarmProtocol, SwarmMessage, SwarmMessageType
from symbolu_robotics.tiers.factory import TierCascade, TierLevel
from symbolu_robotics.planning.world_model import WorldModel
from symbolu_robotics.state.localization import Localization


class FormationType(Enum):
    """Available swarm formations."""
    LINE = "line"
    CIRCLE = "circle"
    TRIANGLE = "triangle"
    GRID = "grid"
    V_SHAPE = "v_shape"


@dataclass
class SwarmConfig:
    """Configuration for swarm coordination."""
    num_robots: int = 4
    robot_radius: float = 0.25
    communication_range: float = 10.0
    control_rate_hz: float = 20.0
    formation_spacing: float = 1.0
    consensus_threshold: float = 0.8


@dataclass
class RobotState:
    """State of an individual robot in the swarm."""
    id: str
    position: np.ndarray
    velocity: np.ndarray
    heading: float
    state_12d: np.ndarray = field(default_factory=lambda: np.zeros(12))
    battery_level: float = 1.0
    is_active: bool = True


class SwarmRobot:
    """Individual robot in the swarm."""

    def __init__(self, robot_id: str, initial_position: np.ndarray):
        self.id = robot_id
        self.position = initial_position.copy()
        self.velocity = np.zeros(3)
        self.heading = 0.0

        # Initialize tier cascade (2 joints for differential drive)
        self.cascade = TierCascade(num_joints=2)

        # Swarm protocol
        self.swarm_protocol = SwarmProtocol(robot_id=robot_id)

        # State
        self.state_12d = np.zeros(12)
        self.neighbors: Dict[str, RobotState] = {}
        self.target_position: Optional[np.ndarray] = None

    def update_neighbors(self, neighbors: Dict[str, RobotState]):
        """Update known neighbor states."""
        self.neighbors = neighbors

    def compute_formation_target(
        self,
        formation: FormationType,
        center: np.ndarray,
        robot_index: int,
        total_robots: int,
        spacing: float
    ) -> np.ndarray:
        """Compute target position for formation."""
        if formation == FormationType.LINE:
            offset = (robot_index - total_robots / 2) * spacing
            return center + np.array([offset, 0.0, 0.0])

        elif formation == FormationType.CIRCLE:
            angle = 2 * np.pi * robot_index / total_robots
            return center + np.array([
                spacing * np.cos(angle),
                spacing * np.sin(angle),
                0.0
            ])

        elif formation == FormationType.TRIANGLE:
            if robot_index == 0:
                return center + np.array([0.0, spacing, 0.0])
            elif robot_index == 1:
                return center + np.array([-spacing * 0.866, -spacing * 0.5, 0.0])
            else:
                return center + np.array([spacing * 0.866, -spacing * 0.5, 0.0])

        elif formation == FormationType.V_SHAPE:
            side = robot_index % 2
            depth = robot_index // 2
            x_offset = (depth + 1) * spacing * (1 if side == 0 else -1)
            y_offset = -(depth + 1) * spacing
            return center + np.array([x_offset, y_offset, 0.0])

        elif formation == FormationType.GRID:
            grid_size = int(np.ceil(np.sqrt(total_robots)))
            row = robot_index // grid_size
            col = robot_index % grid_size
            return center + np.array([
                (col - grid_size / 2) * spacing,
                (row - grid_size / 2) * spacing,
                0.0
            ])

        return center

    def compute_control(self, target: np.ndarray, config: SwarmConfig) -> np.ndarray:
        """Compute velocity toward target with collision avoidance."""
        # Direction to target
        to_target = target - self.position
        dist_to_target = np.linalg.norm(to_target[:2])

        if dist_to_target < 0.1:
            return np.zeros(3)

        # Normalize and scale
        direction = to_target / dist_to_target
        speed = min(0.5, dist_to_target * 0.5)

        # Collision avoidance from neighbors
        avoidance = np.zeros(3)
        for neighbor_id, neighbor in self.neighbors.items():
            to_neighbor = neighbor.position - self.position
            dist = np.linalg.norm(to_neighbor[:2])

            if dist < config.robot_radius * 4:  # Avoidance zone
                if dist > 0.01:
                    repulsion = -to_neighbor / dist
                    strength = (config.robot_radius * 4 - dist) / (config.robot_radius * 4)
                    avoidance += repulsion * strength * 0.5

        velocity = direction * speed + avoidance
        return velocity

    def step(self, dt: float, config: SwarmConfig):
        """Execute one control step."""
        if self.target_position is None:
            return

        velocity = self.compute_control(self.target_position, config)
        self.position += velocity * dt
        self.velocity = velocity

        if np.linalg.norm(velocity[:2]) > 0.01:
            self.heading = np.arctan2(velocity[1], velocity[0])

        # Update 12D state (O10_UNIFYING for swarm)
        self.state_12d[OntologicalLayer.O10_UNIFYING] = 0.8  # Swarm active
        self.state_12d[OntologicalLayer.O3_EXECUTION] = np.linalg.norm(velocity)
        self.state_12d[OntologicalLayer.O8_PURPOSE] = 1.0 if self.target_position is not None else 0.0

    def get_state(self) -> RobotState:
        """Get current robot state."""
        return RobotState(
            id=self.id,
            position=self.position.copy(),
            velocity=self.velocity.copy(),
            heading=self.heading,
            state_12d=self.state_12d.copy(),
            is_active=True
        )


class SwarmCoordinator:
    """Coordinates a swarm of robots."""

    def __init__(self, config: Optional[SwarmConfig] = None):
        self.config = config or SwarmConfig()

        # Initialize robots
        self.robots: Dict[str, SwarmRobot] = {}
        self._initialize_robots()

        # Swarm state
        self.formation = FormationType.CIRCLE
        self.formation_center = np.array([0.0, 0.0, 0.0])
        self.consensus_value = 0.0

    def _initialize_robots(self):
        """Initialize swarm robots."""
        for i in range(self.config.num_robots):
            robot_id = f"robot_{i}"
            # Random initial positions
            initial_pos = np.array([
                np.random.uniform(-2, 2),
                np.random.uniform(-2, 2),
                0.0
            ])
            self.robots[robot_id] = SwarmRobot(robot_id, initial_pos)

    def set_formation(self, formation: FormationType, center: np.ndarray):
        """Set target formation for the swarm."""
        self.formation = formation
        self.formation_center = center

        # Compute target positions for each robot
        robot_list = list(self.robots.values())
        for i, robot in enumerate(robot_list):
            target = robot.compute_formation_target(
                formation,
                center,
                i,
                len(robot_list),
                self.config.formation_spacing
            )
            robot.target_position = target

        print(f"Formation set: {formation.value} at center {center[:2]}")

    def broadcast_states(self):
        """Broadcast all robot states to neighbors."""
        states = {rid: robot.get_state() for rid, robot in self.robots.items()}

        for robot_id, robot in self.robots.items():
            # Each robot sees all other robots within communication range
            neighbors = {}
            for other_id, other_state in states.items():
                if other_id != robot_id:
                    dist = np.linalg.norm(robot.position - other_state.position)
                    if dist < self.config.communication_range:
                        neighbors[other_id] = other_state

            robot.update_neighbors(neighbors)

    def compute_consensus(self) -> float:
        """Compute formation consensus (how well aligned robots are)."""
        if len(self.robots) < 2:
            return 1.0

        robot_list = list(self.robots.values())
        errors = []

        for i, robot in enumerate(robot_list):
            if robot.target_position is not None:
                error = np.linalg.norm(robot.position[:2] - robot.target_position[:2])
                errors.append(error)

        if not errors:
            return 1.0

        max_error = max(errors)
        if max_error > self.config.formation_spacing:
            return 0.0

        return 1.0 - (max_error / self.config.formation_spacing)

    def step(self, dt: float):
        """Execute one coordination step."""
        # Broadcast states
        self.broadcast_states()

        # Step each robot
        for robot in self.robots.values():
            robot.step(dt, self.config)

        # Update consensus
        self.consensus_value = self.compute_consensus()

    def get_swarm_state(self) -> Dict:
        """Get overall swarm state."""
        positions = np.array([r.position for r in self.robots.values()])
        centroid = np.mean(positions, axis=0)

        return {
            'num_robots': len(self.robots),
            'centroid': centroid,
            'formation': self.formation.value,
            'consensus': self.consensus_value,
            'positions': positions
        }

    def run_simulation(self, max_steps: int = 300):
        """Run swarm simulation."""
        print("\n=== Starting Swarm Coordination Simulation ===")
        print(f"Robots: {self.config.num_robots}")
        print(f"Formation: {self.formation.value}")
        print("=" * 50 + "\n")

        dt = 1.0 / self.config.control_rate_hz

        for step in range(max_steps):
            self.step(dt)

            # Log every 30 steps
            if step % 30 == 0:
                state = self.get_swarm_state()
                print(f"Step {step:4d} | Formation: {state['formation']:8s} | "
                      f"Consensus: {state['consensus']:.2f} | "
                      f"Centroid: ({state['centroid'][0]:5.2f}, {state['centroid'][1]:5.2f})")

            # Check if formation achieved
            if self.consensus_value > self.config.consensus_threshold:
                print(f"\n✓ Formation achieved at step {step} (consensus: {self.consensus_value:.2f})")
                break

            time.sleep(dt / 10)

        print("\n=== Swarm Simulation Complete ===\n")


def main():
    """Run the swarm coordination demo."""
    print("Symbolu Robotics - Swarm Coordination Demo")
    print("=" * 50)

    # Create swarm coordinator
    coordinator = SwarmCoordinator(SwarmConfig(
        num_robots=5,
        formation_spacing=1.5,
        communication_range=10.0
    ))

    # Print initial positions
    print("\nInitial robot positions:")
    for rid, robot in coordinator.robots.items():
        print(f"  {rid}: ({robot.position[0]:.2f}, {robot.position[1]:.2f})")

    # Test different formations
    formations = [
        (FormationType.CIRCLE, np.array([0.0, 0.0, 0.0])),
        (FormationType.LINE, np.array([0.0, 0.0, 0.0])),
        (FormationType.V_SHAPE, np.array([0.0, 2.0, 0.0])),
    ]

    for formation, center in formations:
        print(f"\n{'=' * 50}")
        coordinator.set_formation(formation, center)
        coordinator.run_simulation(max_steps=200)

        # Print final positions
        print("\nFinal robot positions:")
        for rid, robot in coordinator.robots.items():
            target = robot.target_position
            dist = np.linalg.norm(robot.position[:2] - target[:2])
            print(f"  {rid}: ({robot.position[0]:5.2f}, {robot.position[1]:5.2f}) "
                  f"-> target ({target[0]:5.2f}, {target[1]:5.2f}), error: {dist:.2f}m")

    print("\n" + "=" * 50)
    print("Swarm coordination demo complete!")
    print(f"O10_UNIFYING layer used for multi-robot state sharing")


if __name__ == "__main__":
    main()
