#!/usr/bin/env python3
# Symbolu Robotics - Navigation Example
"""
Demonstrates autonomous navigation with obstacle avoidance.

This example shows:
- Path planning using A* in the deliberative tier
- Reactive obstacle avoidance
- Reflexive collision prevention
- LIDAR and proximity sensor integration
"""

import numpy as np
import time
from dataclasses import dataclass
from typing import Optional, List, Tuple

from symbolu_robotics.core.types import (
    OntologicalLayer, SafetyLevel, SensorFrame, ActuatorCommand,
    Goal, RobotPose
)
from symbolu_robotics.encoders.fusion_encoder import FusionEncoder, FusionConfig
from symbolu_robotics.decoders.locomotion_decoder import LocomotionDecoder, LocomotionConfig
from symbolu_robotics.safety.constraint_monitor import ConstraintMonitor, SafetyConfig
from symbolu_robotics.safety.collision_guard import CollisionGuard, CollisionConfig
from symbolu_robotics.tiers.factory import TierCascade, TierLevel
from symbolu_robotics.planning.path_planner import PathPlanner
from symbolu_robotics.planning.world_model import WorldModel
from symbolu_robotics.state.localization import Localization


@dataclass
class NavigationConfig:
    """Configuration for navigation task."""
    max_linear_velocity: float = 1.0  # m/s
    max_angular_velocity: float = 1.5  # rad/s
    control_rate_hz: float = 50.0
    goal_tolerance: float = 0.1  # meters
    obstacle_margin: float = 0.3  # meters
    robot_radius: float = 0.25  # meters


class NavigationDemo:
    """Demonstrates autonomous navigation using the three-tier architecture."""

    def __init__(self, config: Optional[NavigationConfig] = None):
        self.config = config or NavigationConfig()

        # Initialize tier cascade (using 2 joints for differential drive)
        self.cascade = TierCascade(num_joints=2)

        # Initialize encoder
        self.encoder = FusionEncoder(FusionConfig(
            enable_vision=True,
            enable_proprioception=True
        ))

        # Initialize locomotion decoder
        self.locomotion_decoder = LocomotionDecoder(LocomotionConfig(
            max_linear_velocity=self.config.max_linear_velocity,
            max_angular_velocity=self.config.max_angular_velocity,
            gait_type='differential'
        ))

        # Initialize safety
        self.safety = ConstraintMonitor(SafetyConfig(
            max_joint_velocity=self.config.max_linear_velocity,
            max_joint_acceleration=2.0,
            max_joint_effort=50.0
        ))
        self.collision_guard = CollisionGuard(CollisionConfig(
            stop_distance=0.1,
            warning_distance=0.3
        ))

        # Initialize planning
        self.path_planner = PathPlanner(
            grid_resolution=0.1,
            robot_radius=self.config.robot_radius
        )
        self.world_model = WorldModel(grid_resolution=0.1)

        # State
        self.localization = Localization()
        self.current_pose = RobotPose(
            position=np.array([0.0, 0.0, 0.0]),
            orientation=np.array([0.0, 0.0, 0.0, 1.0])
        )
        self.goal_position: Optional[np.ndarray] = None
        self.current_path: Optional[List[np.ndarray]] = None
        self.path_index: int = 0

    def add_obstacle(self, position: np.ndarray, radius: float):
        """Add a circular obstacle to the map."""
        self.world_model.add_obstacle(
            position=np.array([position[0], position[1], 0.0]),
            size=np.array([radius * 2, radius * 2, 1.0])
        )
        print(f"Added obstacle at ({position[0]:.2f}, {position[1]:.2f}), radius={radius:.2f}")

    def add_wall(self, start: np.ndarray, end: np.ndarray, thickness: float = 0.1):
        """Add a wall obstacle."""
        center = (start + end) / 2
        length = np.linalg.norm(end - start)
        self.world_model.add_obstacle(
            position=np.array([center[0], center[1], 0.0]),
            size=np.array([length, thickness, 1.0])
        )
        print(f"Added wall from ({start[0]:.2f}, {start[1]:.2f}) to ({end[0]:.2f}, {end[1]:.2f})")

    def set_navigation_goal(self, goal_position: np.ndarray):
        """Set navigation goal and plan path."""
        self.goal_position = goal_position

        # Plan path
        start = self.current_pose.position[:2]
        goal = goal_position[:2]

        self.current_path = self.path_planner.plan(start, goal, self.world_model)

        if self.current_path is None:
            print("Warning: No path found!")
            return False

        self.path_index = 0

        # Set goal in deliberative tier
        nav_goal = Goal(
            id="navigate",
            type="navigate",
            target_position=goal_position,
            priority=1.0
        )
        self.cascade.deliberative.set_goal(nav_goal)

        print(f"Navigation goal set: {goal_position}")
        print(f"Path has {len(self.current_path)} waypoints")
        return True

    def _simulate_lidar(self) -> np.ndarray:
        """Simulate LIDAR readings."""
        num_rays = 360
        max_range = 10.0
        readings = np.ones(num_rays) * max_range

        # Check obstacles
        robot_pos = self.current_pose.position[:2]
        for obstacle in self.world_model.get_obstacles():
            obs_pos = obstacle.position[:2]
            dist = np.linalg.norm(obs_pos - robot_pos)

            if dist < max_range:
                # Simple obstacle detection
                angle_to_obs = np.arctan2(
                    obs_pos[1] - robot_pos[1],
                    obs_pos[0] - robot_pos[0]
                )
                angle_idx = int((angle_to_obs + np.pi) / (2 * np.pi) * num_rays) % num_rays

                # Obstacle covers some angular range
                for offset in range(-10, 11):
                    idx = (angle_idx + offset) % num_rays
                    readings[idx] = min(readings[idx], dist - obstacle.size[0] / 2)

        return readings

    def _simulate_sensors(self, step: int) -> SensorFrame:
        """Simulate sensor readings."""
        lidar = self._simulate_lidar()

        # Simulated odometry (simple forward kinematics)
        return SensorFrame(
            timestamp=time.time(),
            lidar=lidar,
            joint_positions=np.array([0.0, 0.0]),  # Wheel positions
            joint_velocities=np.array([0.0, 0.0]),
            joint_efforts=np.array([0.0, 0.0]),
            proximity_sensors=np.ones(8) * 0.5
        )

    def _get_current_waypoint(self) -> Optional[np.ndarray]:
        """Get current target waypoint."""
        if self.current_path is None or self.path_index >= len(self.current_path):
            return None
        return self.current_path[self.path_index]

    def _check_waypoint_reached(self) -> bool:
        """Check if current waypoint is reached."""
        waypoint = self._get_current_waypoint()
        if waypoint is None:
            return False

        robot_pos = self.current_pose.position[:2]
        dist = np.linalg.norm(waypoint - robot_pos)
        return dist < self.config.goal_tolerance

    def _compute_control(self, waypoint: np.ndarray) -> Tuple[float, float]:
        """Compute velocity commands to reach waypoint."""
        robot_pos = self.current_pose.position[:2]
        robot_theta = 0.0  # Extract from quaternion in real implementation

        # Vector to waypoint
        dx = waypoint[0] - robot_pos[0]
        dy = waypoint[1] - robot_pos[1]
        dist = np.sqrt(dx * dx + dy * dy)

        # Angle to waypoint
        angle_to_waypoint = np.arctan2(dy, dx)
        angle_error = angle_to_waypoint - robot_theta

        # Normalize angle
        while angle_error > np.pi:
            angle_error -= 2 * np.pi
        while angle_error < -np.pi:
            angle_error += 2 * np.pi

        # Simple proportional control
        linear_vel = min(self.config.max_linear_velocity, dist * 0.5)
        angular_vel = np.clip(angle_error * 2.0, -self.config.max_angular_velocity,
                              self.config.max_angular_velocity)

        # Reduce linear velocity when turning
        if abs(angle_error) > 0.5:
            linear_vel *= 0.3

        return linear_vel, angular_vel

    def step(self, sensor_frame: Optional[SensorFrame] = None) -> Tuple[float, float]:
        """Execute one navigation step."""
        if sensor_frame is None:
            sensor_frame = self._simulate_sensors(0)

        # Update localization
        self.localization.update(sensor_frame)

        # Check if waypoint reached
        if self._check_waypoint_reached():
            self.path_index += 1
            if self.path_index < len(self.current_path):
                print(f"  Waypoint {self.path_index} reached")

        # Get current waypoint
        waypoint = self._get_current_waypoint()
        if waypoint is None:
            return 0.0, 0.0  # Goal reached or no path

        # Process through tier cascade
        raw_command = self.cascade.process(sensor_frame)

        # Compute control toward waypoint
        linear_vel, angular_vel = self._compute_control(waypoint)

        # Check for obstacles in LIDAR
        lidar = sensor_frame.lidar
        if lidar is not None:
            min_front = np.min(lidar[170:190])  # Front sector
            if min_front < 0.5:
                # Obstacle ahead, reduce speed
                linear_vel *= min_front / 0.5
                if min_front < 0.2:
                    linear_vel = 0.0
                    # Turn away
                    if np.mean(lidar[:180]) < np.mean(lidar[180:]):
                        angular_vel = -self.config.max_angular_velocity
                    else:
                        angular_vel = self.config.max_angular_velocity

        # Apply safety limits
        linear_vel = np.clip(linear_vel, -self.config.max_linear_velocity,
                            self.config.max_linear_velocity)
        angular_vel = np.clip(angular_vel, -self.config.max_angular_velocity,
                             self.config.max_angular_velocity)

        # Simulate robot motion (replace with actual motor commands)
        dt = 1.0 / self.config.control_rate_hz
        theta = 0.0  # Current heading
        self.current_pose.position[0] += linear_vel * np.cos(theta) * dt
        self.current_pose.position[1] += linear_vel * np.sin(theta) * dt

        return linear_vel, angular_vel

    def is_goal_reached(self) -> bool:
        """Check if navigation goal is reached."""
        if self.goal_position is None:
            return False
        dist = np.linalg.norm(self.current_pose.position[:2] - self.goal_position[:2])
        return dist < self.config.goal_tolerance

    def run_simulation(self, max_steps: int = 1000):
        """Run navigation simulation."""
        print("\n=== Starting Navigation Simulation ===\n")

        for step in range(max_steps):
            sensor_frame = self._simulate_sensors(step)
            linear_vel, angular_vel = self.step(sensor_frame)

            # Log every 100 steps
            if step % 100 == 0:
                pos = self.current_pose.position
                dist_to_goal = np.linalg.norm(pos[:2] - self.goal_position[:2])
                print(f"Step {step:4d} | Pos: ({pos[0]:5.2f}, {pos[1]:5.2f}) | "
                      f"Dist: {dist_to_goal:5.2f}m | "
                      f"Vel: ({linear_vel:4.2f}, {angular_vel:4.2f})")

            # Check goal reached
            if self.is_goal_reached():
                print(f"\n✓ Goal reached at step {step}!")
                break

            time.sleep(1.0 / self.config.control_rate_hz / 100)

        print("\n=== Navigation Complete ===\n")


def main():
    """Run the navigation demo."""
    print("Symbolu Robotics - Navigation Demo")
    print("=" * 50)

    # Create demo
    demo = NavigationDemo(NavigationConfig(
        max_linear_velocity=0.5,
        max_angular_velocity=1.0,
        robot_radius=0.25
    ))

    # Add obstacles
    demo.add_obstacle(np.array([2.0, 1.0]), radius=0.5)
    demo.add_obstacle(np.array([1.5, 2.5]), radius=0.3)
    demo.add_obstacle(np.array([3.0, 2.0]), radius=0.4)

    # Add walls
    demo.add_wall(np.array([0.0, 3.5]), np.array([4.0, 3.5]))
    demo.add_wall(np.array([4.0, 0.0]), np.array([4.0, 3.5]))

    # Set goal
    demo.set_navigation_goal(np.array([3.5, 3.0, 0.0]))

    # Run simulation
    demo.run_simulation(max_steps=500)

    # Final position
    print(f"Final position: {demo.current_pose.position[:2]}")
    print(f"Goal position: {demo.goal_position[:2]}")


if __name__ == "__main__":
    main()
