# Symbolu Robotics - Safety Tests
"""Tests for safety constraint systems matching actual implementations."""

import pytest
import numpy as np
from typing import Dict, Any

from symbolu_robotics.core.types import (
    SafetyLevel, JointState, ActuatorCommand, SensorFrame, Layer12D
)
from symbolu_robotics.safety.constraint_monitor import (
    ConstraintMonitor, SafetyConfig, COLLABORATIVE_SAFETY, INDUSTRIAL_SAFETY
)
from symbolu_robotics.safety.collision_guard import CollisionGuard, CollisionZone
from symbolu_robotics.safety.energy_bounds import EnergyBoundsMonitor, EnergyLimits
from symbolu_robotics.safety.human_proximity import HumanProximityMonitor, HumanSafetyConfig


class TestConstraintMonitor:
    """Tests for the main constraint monitor (O12_ABSOLVING)."""

    @pytest.fixture
    def config(self):
        return SafetyConfig(
            max_joint_velocity=2.0,
            max_joint_acceleration=5.0,
            max_joint_effort=100.0,
            human_distance_threshold=1.0,
            collision_threshold=0.05,
        )

    @pytest.fixture
    def monitor(self, config):
        return ConstraintMonitor(config)

    def test_initialization(self, monitor, config):
        """Test monitor initializes correctly."""
        assert monitor.config.max_joint_velocity == 2.0
        assert monitor.safety_level == SafetyLevel.NOMINAL

    def test_constrain_velocity_within_limits(self, monitor):
        """Test velocity within limits passes unchanged."""
        command = ActuatorCommand(
            target_velocities=np.array([1.0, 1.5, 0.5, 1.0, 0.8, 0.3]),
        )
        layer_12d = np.zeros(12)  # Low constraint level

        constrained = monitor.constrain(command, layer_12d)
        np.testing.assert_array_almost_equal(
            constrained.target_velocities,
            command.target_velocities
        )

    def test_constrain_velocity_high_constraint(self, monitor):
        """Test velocity is reduced when O12 constraint is high."""
        command = ActuatorCommand(
            target_velocities=np.array([2.0, 2.0, 2.0, 2.0, 2.0, 2.0]),
        )
        layer_12d = np.zeros(12)
        layer_12d[11] = 0.9  # High O12_ABSOLVING constraint

        constrained = monitor.constrain(command, layer_12d)

        # Velocities should be reduced
        assert np.all(np.abs(constrained.target_velocities) < 2.0)

    def test_constrain_effort_limits(self, monitor):
        """Test effort is clipped to limits."""
        command = ActuatorCommand(
            target_efforts=np.array([150.0, 80.0, 30.0, 120.0, 40.0, 20.0]),
        )
        layer_12d = np.zeros(12)

        constrained = monitor.constrain(command, layer_12d)

        assert np.all(np.abs(constrained.target_efforts) <= 100.0)

    def test_safety_level_update(self, monitor):
        """Test safety level updates based on constraint."""
        layer_12d = np.zeros(12)
        command = ActuatorCommand(target_velocities=np.zeros(6))

        # Low constraint -> NOMINAL
        layer_12d[11] = 0.2
        monitor.constrain(command, layer_12d)
        assert monitor.safety_level == SafetyLevel.NOMINAL

        # Medium constraint -> CAUTION
        layer_12d[11] = 0.5
        monitor.constrain(command, layer_12d)
        assert monitor.safety_level == SafetyLevel.CAUTION

        # High constraint -> RESTRICTED
        layer_12d[11] = 0.8
        monitor.constrain(command, layer_12d)
        assert monitor.safety_level == SafetyLevel.RESTRICTED

        # Very high constraint -> EMERGENCY_STOP
        layer_12d[11] = 0.95
        monitor.constrain(command, layer_12d)
        assert monitor.safety_level == SafetyLevel.EMERGENCY_STOP

    def test_slow_motion_mode(self, monitor):
        """Test slow motion mode activates on high constraint."""
        command = ActuatorCommand(
            target_velocities=np.array([1.0, 1.0, 1.0, 1.0, 1.0, 1.0]),
        )
        layer_12d = np.zeros(12)
        layer_12d[11] = 0.85  # Triggers slow motion

        constrained = monitor.constrain(command, layer_12d)

        # Should be in slow motion (20% speed)
        assert constrained.safety_limited
        assert np.all(np.abs(constrained.target_velocities) < 0.5)

    def test_emergency_stop_passthrough(self, monitor):
        """Test emergency stop commands pass through unchanged."""
        command = ActuatorCommand(
            emergency_stop=True,
            target_velocities=np.zeros(6),
        )
        layer_12d = np.zeros(12)

        constrained = monitor.constrain(command, layer_12d)
        assert constrained.emergency_stop

    def test_check_command_safety(self, monitor):
        """Test command safety checking."""
        # Safe command
        safe_cmd = ActuatorCommand(
            target_velocities=np.array([1.0, 1.0, 1.0, 1.0, 1.0, 1.0]),
            target_efforts=np.array([50.0, 50.0, 50.0, 50.0, 50.0, 50.0]),
        )
        is_safe, violations = monitor.check_command_safety(safe_cmd)
        assert is_safe
        assert len(violations) == 0

        # Unsafe command - velocity exceeded
        unsafe_cmd = ActuatorCommand(
            target_velocities=np.array([3.0, 1.0, 1.0, 1.0, 1.0, 1.0]),
        )
        is_safe, violations = monitor.check_command_safety(unsafe_cmd)
        assert not is_safe
        assert "velocity_exceeded" in violations

    def test_preset_configurations(self):
        """Test preset safety configurations."""
        industrial = ConstraintMonitor(INDUSTRIAL_SAFETY)
        collaborative = ConstraintMonitor(COLLABORATIVE_SAFETY)

        assert industrial.config.max_joint_velocity > collaborative.config.max_joint_velocity
        assert industrial.config.max_joint_effort > collaborative.config.max_joint_effort


class TestCollisionGuard:
    """Tests for collision detection guard."""

    @pytest.fixture
    def guard(self):
        return CollisionGuard(
            min_distance=0.05,
            emergency_stop_distance=0.02,
        )

    def test_clear_no_sensors(self, guard):
        """Test clear returns True when no sensor data."""
        sensor_frame = SensorFrame(timestamp=0.0)
        is_clear = guard.clear(sensor_frame)
        assert is_clear

    def test_clear_far_obstacles(self, guard):
        """Test clear returns True when obstacles are far."""
        sensor_frame = SensorFrame(
            timestamp=0.0,
            proximity_distances=np.array([1.0, 0.8, 0.5, 0.7]),
        )
        is_clear = guard.clear(sensor_frame)
        assert is_clear

    def test_collision_detected_proximity(self, guard):
        """Test collision detected from proximity sensors."""
        sensor_frame = SensorFrame(
            timestamp=0.0,
            proximity_distances=np.array([0.5, 0.01, 0.3, 0.4]),  # Second sensor very close
        )
        is_clear = guard.clear(sensor_frame)
        assert not is_clear
        assert guard.is_collision_detected

    def test_collision_detected_lidar(self, guard):
        """Test collision detected from LIDAR."""
        sensor_frame = SensorFrame(
            timestamp=0.0,
            lidar_ranges=np.array([0.5, 0.3, 0.015, 0.4, 0.6]),  # One very close
        )
        is_clear = guard.clear(sensor_frame)
        assert not is_clear

    def test_safety_level_based_on_distance(self, guard):
        """Test safety level changes based on closest distance."""
        # Far - NOMINAL
        sensor_frame = SensorFrame(
            timestamp=0.0,
            proximity_distances=np.array([1.0, 0.8, 0.5]),
        )
        guard.clear(sensor_frame)
        assert guard.get_safety_level() == SafetyLevel.NOMINAL

        # Close but not critical - CAUTION
        sensor_frame = SensorFrame(
            timestamp=0.0,
            proximity_distances=np.array([0.12, 0.3, 0.4]),
        )
        guard.clear(sensor_frame)
        assert guard.get_safety_level() == SafetyLevel.CAUTION

        # Very close - RESTRICTED
        sensor_frame = SensorFrame(
            timestamp=0.0,
            proximity_distances=np.array([0.03, 0.3, 0.4]),
        )
        guard.clear(sensor_frame)
        assert guard.get_safety_level() == SafetyLevel.RESTRICTED

    def test_emergency_stop_command(self, guard):
        """Test emergency stop command generation."""
        estop = guard.emergency_stop()
        assert estop.emergency_stop
        np.testing.assert_array_equal(estop.target_velocities, np.zeros(6))

    def test_constrain_command_safe(self, guard):
        """Test command passes through when safe."""
        sensor_frame = SensorFrame(
            timestamp=0.0,
            proximity_distances=np.array([1.0, 0.8, 0.5]),
        )
        command = ActuatorCommand(
            target_velocities=np.array([1.0, 1.0, 1.0, 1.0, 1.0, 1.0]),
        )

        constrained = guard.constrain_command(command, sensor_frame)
        np.testing.assert_array_equal(
            constrained.target_velocities,
            command.target_velocities
        )

    def test_constrain_command_collision(self, guard):
        """Test emergency stop on collision."""
        sensor_frame = SensorFrame(
            timestamp=0.0,
            proximity_distances=np.array([0.01, 0.3, 0.4]),  # Collision!
        )
        command = ActuatorCommand(
            target_velocities=np.array([1.0, 1.0, 1.0, 1.0, 1.0, 1.0]),
        )

        constrained = guard.constrain_command(command, sensor_frame)
        assert constrained.emergency_stop

    def test_constrain_command_caution(self, guard):
        """Test velocity reduction in caution zone."""
        sensor_frame = SensorFrame(
            timestamp=0.0,
            proximity_distances=np.array([0.12, 0.3, 0.4]),  # Caution zone
        )
        command = ActuatorCommand(
            target_velocities=np.array([1.0, 1.0, 1.0, 1.0, 1.0, 1.0]),
        )

        constrained = guard.constrain_command(command, sensor_frame)
        assert constrained.safety_limited
        assert np.all(np.abs(constrained.target_velocities) < 1.0)

    def test_constraint_level(self, guard):
        """Test O12 constraint level calculation."""
        # Far - low constraint
        sensor_frame = SensorFrame(
            timestamp=0.0,
            proximity_distances=np.array([1.0]),
        )
        guard.clear(sensor_frame)
        assert guard.get_constraint_level() == 0.0

        # Collision - max constraint
        sensor_frame = SensorFrame(
            timestamp=0.0,
            proximity_distances=np.array([0.01]),
        )
        guard.clear(sensor_frame)
        assert guard.get_constraint_level() == 1.0

    def test_zone_intrusion(self, guard):
        """Test collision zone intrusion detection."""
        zone = CollisionZone(
            name="workspace",
            center=np.array([0.0, 0.0, 0.5]),
            radius=0.2,
        )
        guard.zones = [zone]

        # Inside zone
        is_intrusion, zone_hit = guard.check_zone_intrusion(np.array([0.0, 0.0, 0.5]))
        assert is_intrusion
        assert zone_hit.name == "workspace"

        # Outside zone
        is_intrusion, zone_hit = guard.check_zone_intrusion(np.array([1.0, 0.0, 0.5]))
        assert not is_intrusion
        assert zone_hit is None


class TestEnergyBoundsMonitor:
    """Tests for energy and thermal limits."""

    @pytest.fixture
    def limits(self):
        return EnergyLimits(
            max_power_per_joint=80.0,
            max_total_power=200.0,
            max_continuous_effort=80.0,
            max_peak_effort=150.0,
            thermal_time_constant=30.0,
        )

    @pytest.fixture
    def monitor(self, limits):
        return EnergyBoundsMonitor(limits=limits)

    def test_power_computation(self, monitor):
        """Test power computation (P = τ * ω)."""
        joints = JointState(
            positions=np.zeros(6),
            velocities=np.array([1.0, 2.0, 1.0, 1.0, 1.0, 1.0]),
            efforts=np.array([40.0, 30.0, 20.0, 25.0, 30.0, 20.0]),
        )

        power = monitor.compute_power(joints)

        # P = |τ * ω|
        expected = np.abs(joints.efforts * joints.velocities)
        np.testing.assert_array_almost_equal(power, expected)

    def test_check_limits_safe(self, monitor):
        """Test limits check passes when safe."""
        joints = JointState(
            positions=np.zeros(6),
            velocities=np.array([1.0, 1.0, 1.0, 1.0, 1.0, 1.0]),
            efforts=np.array([40.0, 30.0, 20.0, 25.0, 30.0, 20.0]),
        )

        violations = monitor.check_limits(joints)
        assert len(violations) == 0

    def test_check_limits_power_exceeded(self, monitor):
        """Test power limit violation detected."""
        joints = JointState(
            positions=np.zeros(6),
            velocities=np.array([2.0, 2.0, 2.0, 2.0, 2.0, 2.0]),
            efforts=np.array([100.0, 100.0, 100.0, 100.0, 100.0, 100.0]),  # High power
        )

        violations = monitor.check_limits(joints)
        assert any("power" in v for v in violations)

    def test_check_limits_peak_effort_exceeded(self, monitor):
        """Test peak effort limit violation detected."""
        joints = JointState(
            positions=np.zeros(6),
            velocities=np.zeros(6),
            efforts=np.array([50.0, 200.0, 50.0, 50.0, 50.0, 50.0]),  # One very high
        )

        violations = monitor.check_limits(joints)
        assert "peak_effort_exceeded" in violations

    def test_thermal_model_update(self, monitor):
        """Test thermal model updates over time."""
        joints = JointState(
            positions=np.zeros(6),
            velocities=np.ones(6),
            efforts=np.full(6, 50.0),
        )

        # Update multiple times to build up thermal state
        for _ in range(50):
            monitor.update(joints)

        thermal = monitor.get_thermal_percentage()
        assert np.all(thermal > 0)  # Should have accumulated

    def test_constrain_command_peak_effort(self, monitor):
        """Test command effort is clamped to peak limit."""
        command = ActuatorCommand(
            target_efforts=np.array([200.0, 100.0, 50.0, 50.0, 50.0, 50.0]),
        )
        joints = JointState(
            positions=np.zeros(6),
            velocities=np.ones(6),
            efforts=np.zeros(6),
        )

        constrained = monitor.constrain_command(command, joints)

        # Should be clamped to max_peak_effort
        assert np.all(np.abs(constrained.target_efforts) <= 150.0)

    def test_reset_thermal(self, monitor):
        """Test thermal model reset."""
        # Build up thermal state
        joints = JointState(
            positions=np.zeros(6),
            velocities=np.ones(6),
            efforts=np.full(6, 50.0),
        )
        for _ in range(20):
            monitor.update(joints)

        assert np.any(monitor.get_thermal_percentage() > 0)

        # Reset
        monitor.reset()
        np.testing.assert_array_equal(monitor.get_thermal_percentage(), np.zeros(6))


class TestHumanProximityMonitor:
    """Tests for human proximity safety."""

    @pytest.fixture
    def config(self):
        return HumanSafetyConfig(
            stop_distance=0.3,
            reduced_speed_distance=1.0,
            monitoring_distance=2.0,
            max_speed_near_human=0.25,
            reduced_speed=0.5,
        )

    @pytest.fixture
    def monitor(self, config):
        return HumanProximityMonitor(config)

    def test_no_human_detected(self, monitor):
        """Test no human detected state."""
        sensor_frame = SensorFrame(
            timestamp=0.0,
            human_detected=False,
        )

        monitor.update(sensor_frame)

        assert not monitor.human_detected
        assert monitor.safety_level == SafetyLevel.NOMINAL
        assert monitor.get_max_allowed_speed() == float('inf')

    def test_human_far_away(self, monitor):
        """Test human detected but far away."""
        sensor_frame = SensorFrame(
            timestamp=0.0,
            human_detected=True,
            human_distance=5.0,
        )

        monitor.update(sensor_frame)

        assert monitor.human_detected
        assert monitor.safety_level == SafetyLevel.NOMINAL

    def test_human_in_monitoring_zone(self, monitor):
        """Test human in monitoring zone."""
        sensor_frame = SensorFrame(
            timestamp=0.0,
            human_detected=True,
            human_distance=1.5,  # Between reduced_speed_distance and monitoring_distance
        )

        monitor.update(sensor_frame)

        assert monitor.safety_level == SafetyLevel.CAUTION
        assert monitor.get_max_allowed_speed() == 0.5

    def test_human_in_reduced_speed_zone(self, monitor):
        """Test human in reduced speed zone."""
        sensor_frame = SensorFrame(
            timestamp=0.0,
            human_detected=True,
            human_distance=0.8,  # Between stop_distance and reduced_speed_distance
        )

        monitor.update(sensor_frame)

        assert monitor.safety_level == SafetyLevel.RESTRICTED
        assert monitor.get_max_allowed_speed() == 0.25

    def test_human_in_stop_zone(self, monitor):
        """Test human in stop zone."""
        sensor_frame = SensorFrame(
            timestamp=0.0,
            human_detected=True,
            human_distance=0.2,  # Less than stop_distance
        )

        monitor.update(sensor_frame)

        assert monitor.safety_level == SafetyLevel.EMERGENCY_STOP
        assert monitor.get_max_allowed_speed() == 0.0

    def test_constraint_level(self, monitor):
        """Test O12 constraint level calculation."""
        # Far - no constraint
        sensor_frame = SensorFrame(
            timestamp=0.0,
            human_detected=True,
            human_distance=5.0,
        )
        monitor.update(sensor_frame)
        assert monitor.get_constraint_level() == 0.0

        # Stop zone - max constraint
        sensor_frame = SensorFrame(
            timestamp=0.0,
            human_detected=True,
            human_distance=0.2,
        )
        monitor.update(sensor_frame)
        assert monitor.get_constraint_level() == 1.0

    def test_constrain_command_no_human(self, monitor):
        """Test command unchanged when no human."""
        sensor_frame = SensorFrame(timestamp=0.0, human_detected=False)
        monitor.update(sensor_frame)

        command = ActuatorCommand(
            target_velocities=np.array([1.0, 1.0, 1.0, 1.0, 1.0, 1.0]),
        )

        constrained = monitor.constrain_command(command)
        np.testing.assert_array_equal(
            constrained.target_velocities,
            command.target_velocities
        )

    def test_constrain_command_human_close(self, monitor):
        """Test command constrained when human is close."""
        sensor_frame = SensorFrame(
            timestamp=0.0,
            human_detected=True,
            human_distance=0.8,  # Reduced speed zone
        )
        monitor.update(sensor_frame)

        command = ActuatorCommand(
            target_velocities=np.array([1.0, 1.0, 1.0, 1.0, 1.0, 1.0]),
        )

        constrained = monitor.constrain_command(command)

        # Should be limited to max_speed_near_human
        assert np.all(np.abs(constrained.target_velocities) <= 0.25)
        assert constrained.safety_limited

    def test_constrain_command_stop_zone(self, monitor):
        """Test emergency stop when human in stop zone."""
        sensor_frame = SensorFrame(
            timestamp=0.0,
            human_detected=True,
            human_distance=0.2,
        )
        monitor.update(sensor_frame)

        command = ActuatorCommand(
            target_velocities=np.array([0.5, 0.5, 0.5, 0.5, 0.5, 0.5]),
        )

        constrained = monitor.constrain_command(command)
        assert constrained.emergency_stop

    def test_proximity_fallback(self, monitor):
        """Test proximity sensors used as fallback for human detection."""
        sensor_frame = SensorFrame(
            timestamp=0.0,
            human_detected=False,
            proximity_distances=np.array([0.5, 1.5, 0.8]),  # Closest is 0.5m
        )
        monitor.update(sensor_frame)

        # Should be in reduced speed zone based on proximity
        assert monitor.closest_distance == 0.5
        assert monitor.safety_level == SafetyLevel.RESTRICTED

    def test_separation_distance_estimation(self, monitor):
        """Test safe separation distance estimation."""
        robot_velocity = np.array([0.5, 0.0, 0.0])
        human_velocity = np.array([-1.0, 0.0, 0.0])

        separation = monitor.estimate_separation_distance(robot_velocity, human_velocity)

        # Should return positive distance
        assert separation > 0
        # Should be reasonable for walking speeds
        assert separation < 5.0


class TestSafetyIntegration:
    """Integration tests for safety systems."""

    def test_all_safety_systems_initialize(self):
        """Test all safety systems initialize without error."""
        constraint_monitor = ConstraintMonitor(SafetyConfig())
        collision_guard = CollisionGuard()
        energy_monitor = EnergyBoundsMonitor()
        human_monitor = HumanProximityMonitor()

        assert constraint_monitor is not None
        assert collision_guard is not None
        assert energy_monitor is not None
        assert human_monitor is not None

    def test_safety_cascade(self):
        """Test safety systems can be chained."""
        # Create all monitors
        collision_guard = CollisionGuard()
        constraint_monitor = ConstraintMonitor()
        human_monitor = HumanProximityMonitor()

        # Create sensor frame with human nearby
        sensor_frame = SensorFrame(
            timestamp=0.0,
            human_detected=True,
            human_distance=0.8,
            proximity_distances=np.array([0.5, 1.0, 2.0]),
        )

        # Initial command
        command = ActuatorCommand(
            target_velocities=np.array([1.0, 1.0, 1.0, 1.0, 1.0, 1.0]),
        )

        # Apply collision constraints first
        command = collision_guard.constrain_command(command, sensor_frame)

        # Then apply human proximity constraints
        human_monitor.update(sensor_frame)
        command = human_monitor.constrain_command(command)

        # Then apply O12 constraints
        layer_12d = np.zeros(12)
        layer_12d[11] = human_monitor.get_constraint_level()
        command = constraint_monitor.constrain(command, layer_12d)

        # Should be significantly reduced
        assert np.all(np.abs(command.target_velocities) < 0.5)

    def test_combined_constraint_level(self):
        """Test combining constraint levels from multiple sources."""
        collision_guard = CollisionGuard()
        human_monitor = HumanProximityMonitor()

        # Sensor frame with moderate proximity
        sensor_frame = SensorFrame(
            timestamp=0.0,
            human_detected=True,
            human_distance=1.2,
            proximity_distances=np.array([0.15, 1.0, 2.0]),
        )

        collision_guard.clear(sensor_frame)
        human_monitor.update(sensor_frame)

        # Combine constraint levels (take max)
        collision_constraint = collision_guard.get_constraint_level()
        human_constraint = human_monitor.get_constraint_level()
        combined = max(collision_constraint, human_constraint)

        assert combined > 0  # Should have some constraint
        assert combined <= 1.0  # Should not exceed max


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
