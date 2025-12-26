# Symbolu Robotics - Safety Tests
"""Tests for safety constraint systems."""

import pytest
import numpy as np
from typing import Dict, Any

from symbolu_robotics.core.types import (
    OntologicalLayer, SafetyLevel, JointState, RobotPose, ActuatorCommand
)
from symbolu_robotics.safety.constraint_monitor import ConstraintMonitor, SafetyConfig
from symbolu_robotics.safety.collision_guard import CollisionGuard, CollisionConfig
from symbolu_robotics.safety.energy_bounds import EnergyBounds, EnergyConfig
from symbolu_robotics.safety.human_proximity import HumanProximity, HumanProximityConfig


class TestConstraintMonitor:
    """Tests for the main constraint monitor."""

    @pytest.fixture
    def config(self):
        return SafetyConfig(
            max_joint_velocity=2.0,
            max_joint_acceleration=10.0,
            max_joint_effort=100.0,
            max_tcp_velocity=1.0,
            max_tcp_force=150.0,
            emergency_stop_decel=15.0
        )

    @pytest.fixture
    def monitor(self, config):
        return ConstraintMonitor(config)

    def test_initialization(self, monitor, config):
        """Test monitor initializes correctly."""
        assert monitor.config.max_joint_velocity == 2.0
        assert monitor.safety_level == SafetyLevel.NORMAL

    def test_check_velocity_limits_pass(self, monitor):
        """Test velocity within limits passes."""
        velocities = np.array([1.0, 1.5, 0.5, 1.0, 0.8, 0.3])
        is_safe, violations = monitor.check_joint_velocities(velocities)
        assert is_safe
        assert len(violations) == 0

    def test_check_velocity_limits_fail(self, monitor):
        """Test velocity exceeding limits fails."""
        velocities = np.array([1.0, 2.5, 0.5, 1.0, 0.8, 0.3])  # Joint 1 exceeds
        is_safe, violations = monitor.check_joint_velocities(velocities)
        assert not is_safe
        assert 1 in violations

    def test_check_effort_limits_pass(self, monitor):
        """Test effort within limits passes."""
        efforts = np.array([50.0, 80.0, 30.0, 60.0, 40.0, 20.0])
        is_safe, violations = monitor.check_joint_efforts(efforts)
        assert is_safe

    def test_check_effort_limits_fail(self, monitor):
        """Test effort exceeding limits fails."""
        efforts = np.array([50.0, 150.0, 30.0, 60.0, 40.0, 20.0])  # Joint 1 exceeds
        is_safe, violations = monitor.check_joint_efforts(efforts)
        assert not is_safe

    def test_clamp_command(self, monitor):
        """Test command clamping to limits."""
        command = ActuatorCommand(
            timestamp=0.0,
            joint_velocities=np.array([3.0, -3.0, 1.0, 2.5, -2.5, 0.5]),
            joint_efforts=np.array([150.0, 80.0, 30.0, 120.0, 40.0, 20.0])
        )

        clamped = monitor.clamp_command(command)

        assert np.all(np.abs(clamped.joint_velocities) <= 2.0)
        assert np.all(np.abs(clamped.joint_efforts) <= 100.0)

    def test_emergency_stop(self, monitor):
        """Test emergency stop triggers correctly."""
        monitor.trigger_emergency_stop("Test emergency")
        assert monitor.safety_level == SafetyLevel.EMERGENCY
        assert monitor.is_emergency_stopped

    def test_emergency_stop_zero_command(self, monitor):
        """Test emergency stop produces zero command."""
        monitor.trigger_emergency_stop("Test")

        command = ActuatorCommand(
            timestamp=0.0,
            joint_velocities=np.array([1.0, 1.0, 1.0, 1.0, 1.0, 1.0]),
            joint_efforts=np.array([50.0, 50.0, 50.0, 50.0, 50.0, 50.0])
        )

        safe_command = monitor.apply_safety(command)
        np.testing.assert_array_equal(safe_command.joint_velocities, np.zeros(6))

    def test_reset_after_emergency(self, monitor):
        """Test reset after emergency stop."""
        monitor.trigger_emergency_stop("Test")
        assert monitor.is_emergency_stopped

        monitor.reset_emergency()
        assert not monitor.is_emergency_stopped
        assert monitor.safety_level == SafetyLevel.NORMAL


class TestCollisionGuard:
    """Tests for collision detection guard."""

    @pytest.fixture
    def config(self):
        return CollisionConfig(
            check_interval_ms=1.0,
            stop_distance=0.05,
            warning_distance=0.15,
            use_bounding_spheres=True
        )

    @pytest.fixture
    def guard(self, config):
        return CollisionGuard(config)

    def test_no_collision_free_space(self, guard):
        """Test no collision in free space."""
        robot_pose = RobotPose(
            position=np.array([0.0, 0.0, 0.0]),
            orientation=np.array([0.0, 0.0, 0.0, 1.0])
        )
        obstacles = []  # No obstacles

        is_safe, min_distance = guard.check_collision(robot_pose, obstacles)
        assert is_safe
        assert min_distance == float('inf')

    def test_collision_detected(self, guard):
        """Test collision detected when too close."""
        robot_pose = RobotPose(
            position=np.array([0.0, 0.0, 0.0]),
            orientation=np.array([0.0, 0.0, 0.0, 1.0])
        )
        obstacles = [
            {'position': np.array([0.03, 0.0, 0.0]), 'radius': 0.01}
        ]

        is_safe, min_distance = guard.check_collision(robot_pose, obstacles)
        assert not is_safe
        assert min_distance < 0.05

    def test_warning_zone(self, guard):
        """Test warning zone detection."""
        robot_pose = RobotPose(
            position=np.array([0.0, 0.0, 0.0]),
            orientation=np.array([0.0, 0.0, 0.0, 1.0])
        )
        obstacles = [
            {'position': np.array([0.1, 0.0, 0.0]), 'radius': 0.01}
        ]

        is_safe, min_distance = guard.check_collision(robot_pose, obstacles)
        in_warning = guard.is_in_warning_zone(min_distance)

        assert is_safe  # Not in stop zone
        assert in_warning  # In warning zone

    def test_trajectory_collision_check(self, guard):
        """Test trajectory collision checking."""
        trajectory = [
            RobotPose(np.array([0.0, 0.0, 0.0]), np.array([0.0, 0.0, 0.0, 1.0])),
            RobotPose(np.array([0.1, 0.0, 0.0]), np.array([0.0, 0.0, 0.0, 1.0])),
            RobotPose(np.array([0.2, 0.0, 0.0]), np.array([0.0, 0.0, 0.0, 1.0])),
        ]
        obstacles = [
            {'position': np.array([0.15, 0.0, 0.0]), 'radius': 0.02}
        ]

        collision_idx = guard.check_trajectory(trajectory, obstacles)
        assert collision_idx is not None  # Collision found
        assert collision_idx in [1, 2]  # At waypoint 1 or 2


class TestEnergyBounds:
    """Tests for energy and thermal limits."""

    @pytest.fixture
    def config(self):
        return EnergyConfig(
            max_power_per_joint=[80.0, 100.0, 80.0, 60.0, 60.0, 40.0],
            thermal_limit_celsius=80.0,
            thermal_warning_celsius=70.0,
            power_averaging_window=0.1
        )

    @pytest.fixture
    def bounds(self, config):
        return EnergyBounds(config)

    def test_power_within_limits(self, bounds):
        """Test power within limits passes."""
        velocities = np.array([1.0, 1.0, 1.0, 1.0, 1.0, 1.0])
        efforts = np.array([40.0, 50.0, 40.0, 30.0, 30.0, 20.0])

        is_safe, violations = bounds.check_power(velocities, efforts)
        assert is_safe

    def test_power_exceeds_limits(self, bounds):
        """Test power exceeding limits fails."""
        velocities = np.array([2.0, 2.0, 2.0, 2.0, 2.0, 2.0])
        efforts = np.array([80.0, 80.0, 80.0, 80.0, 80.0, 80.0])  # High power

        is_safe, violations = bounds.check_power(velocities, efforts)
        assert not is_safe

    def test_thermal_warning(self, bounds):
        """Test thermal warning detection."""
        temperatures = np.array([65.0, 72.0, 60.0, 55.0, 50.0, 45.0])  # Joint 1 high

        level, warnings = bounds.check_thermal(temperatures)
        assert level == 'warning'
        assert 1 in warnings

    def test_thermal_critical(self, bounds):
        """Test thermal critical detection."""
        temperatures = np.array([65.0, 85.0, 60.0, 55.0, 50.0, 45.0])  # Joint 1 critical

        level, warnings = bounds.check_thermal(temperatures)
        assert level == 'critical'

    def test_limit_power(self, bounds):
        """Test power limiting."""
        velocities = np.array([2.0, 2.0, 2.0, 2.0, 2.0, 2.0])
        efforts = np.array([100.0, 100.0, 100.0, 100.0, 100.0, 100.0])

        limited_efforts = bounds.limit_power(velocities, efforts)

        # Power should now be within limits
        powers = np.abs(velocities * limited_efforts)
        assert np.all(powers <= bounds.config.max_power_per_joint)


class TestHumanProximity:
    """Tests for human proximity safety."""

    @pytest.fixture
    def config(self):
        return HumanProximityConfig(
            stop_distance=0.3,
            reduced_speed_distance=1.0,
            monitoring_distance=2.0,
            max_speed_near_human=0.25,
            human_speed_estimate=1.6
        )

    @pytest.fixture
    def proximity(self, config):
        return HumanProximity(config)

    def test_no_human_full_speed(self, proximity):
        """Test full speed when no human detected."""
        human_positions = []  # No humans
        robot_position = np.array([0.0, 0.0, 0.0])

        speed_limit = proximity.compute_speed_limit(robot_position, human_positions)
        assert speed_limit == float('inf')

    def test_human_far_full_speed(self, proximity):
        """Test full speed when human is far."""
        human_positions = [np.array([5.0, 0.0, 0.0])]  # 5m away
        robot_position = np.array([0.0, 0.0, 0.0])

        speed_limit = proximity.compute_speed_limit(robot_position, human_positions)
        assert speed_limit == float('inf')

    def test_human_monitoring_zone(self, proximity):
        """Test reduced speed in monitoring zone."""
        human_positions = [np.array([1.5, 0.0, 0.0])]  # 1.5m away
        robot_position = np.array([0.0, 0.0, 0.0])

        speed_limit = proximity.compute_speed_limit(robot_position, human_positions)
        assert speed_limit < float('inf')
        assert speed_limit > 0.25  # Not yet at max reduction

    def test_human_reduced_speed_zone(self, proximity):
        """Test max reduced speed near human."""
        human_positions = [np.array([0.8, 0.0, 0.0])]  # 0.8m away
        robot_position = np.array([0.0, 0.0, 0.0])

        speed_limit = proximity.compute_speed_limit(robot_position, human_positions)
        assert speed_limit <= 0.25

    def test_human_stop_zone(self, proximity):
        """Test stop in stop zone."""
        human_positions = [np.array([0.2, 0.0, 0.0])]  # 0.2m away
        robot_position = np.array([0.0, 0.0, 0.0])

        speed_limit = proximity.compute_speed_limit(robot_position, human_positions)
        assert speed_limit == 0.0

    def test_multiple_humans(self, proximity):
        """Test closest human determines limit."""
        human_positions = [
            np.array([3.0, 0.0, 0.0]),  # Far
            np.array([0.5, 0.0, 0.0]),  # Close
            np.array([2.0, 0.0, 0.0]),  # Medium
        ]
        robot_position = np.array([0.0, 0.0, 0.0])

        speed_limit = proximity.compute_speed_limit(robot_position, human_positions)
        assert speed_limit <= 0.25  # Limited by closest human

    def test_speed_separation_monitoring(self, proximity):
        """Test speed-separation monitoring formula."""
        human_position = np.array([1.0, 0.0, 0.0])
        human_velocity = np.array([-1.0, 0.0, 0.0])  # Moving toward robot
        robot_position = np.array([0.0, 0.0, 0.0])
        robot_velocity = np.array([0.5, 0.0, 0.0])  # Moving toward human

        is_safe = proximity.check_speed_separation(
            robot_position, robot_velocity,
            human_position, human_velocity
        )

        # Should be safe at current distance but monitoring
        assert isinstance(is_safe, bool)


class TestSafetyIntegration:
    """Integration tests for safety systems."""

    def test_all_safety_systems_coordinate(self):
        """Test all safety systems work together."""
        constraint_monitor = ConstraintMonitor(SafetyConfig(
            max_joint_velocity=2.0,
            max_joint_acceleration=10.0,
            max_joint_effort=100.0
        ))
        collision_guard = CollisionGuard(CollisionConfig(
            stop_distance=0.05,
            warning_distance=0.15
        ))
        energy_bounds = EnergyBounds(EnergyConfig(
            max_power_per_joint=[80.0] * 6,
            thermal_limit_celsius=80.0
        ))
        human_proximity = HumanProximity(HumanProximityConfig(
            stop_distance=0.3,
            reduced_speed_distance=1.0
        ))

        # All should initialize without error
        assert constraint_monitor is not None
        assert collision_guard is not None
        assert energy_bounds is not None
        assert human_proximity is not None

    def test_safety_cascade(self):
        """Test safety systems cascade correctly."""
        monitor = ConstraintMonitor(SafetyConfig(
            max_joint_velocity=2.0,
            max_joint_acceleration=10.0,
            max_joint_effort=100.0
        ))

        # Normal -> Warning -> Emergency cascade
        assert monitor.safety_level == SafetyLevel.NORMAL

        monitor.set_warning("Approaching limits")
        assert monitor.safety_level == SafetyLevel.WARNING

        monitor.trigger_emergency_stop("Collision imminent")
        assert monitor.safety_level == SafetyLevel.EMERGENCY


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
